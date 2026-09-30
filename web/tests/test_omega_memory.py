"""Omega-owned recall/reinforcement remains separate from kernel authority."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omega_memory import NativeOmegaMemory, clean_event, MAX_RECORDS
from agent_experience import ExperienceCourier
import bridge
from test_bridge import FakeAgentRuntime
from test_motion_player import Chooser


class Native:
    def __init__(self): self.docs = {}; self.stv = {}; self.serial = 0
    def remember(self, doc, embedding, timestamp):
        self.serial += 1; identity = str(self.serial)
        self.docs[identity] = doc
        return identity
    def query_with_ids(self, embedding, k):
        return [[i, 'time', d] for i, d in reversed(list(self.docs.items()))][:k]
    def get_stv(self, identity): return self.stv.get(identity, [.5, .5])
    def set_stv(self, identity, strength, confidence): self.stv[identity] = [strength, confidence]
    def forget_id(self, identity): self.docs.pop(identity, None)


def experience(identity='exp-1', page='farm', asset='butterfly'):
    return {'id': identity, 'page': page, 'kind': 'experience', 'source': 'jev',
            'subject': 'butterfly-1', 'asset': asset, 'moves': 6, 'turns': 3,
            'clips': ['flutter'], 'start': {'x': .5, 'y': .4}, 'end': {'x': .6, 'y': .3}}


class NativeMemory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.native = Native()
        self.memory = NativeOmegaMemory('omegajev', native=self.native, embed=lambda _: [1.0], directory=self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_native_remember_recall_and_strength_are_used(self):
        self.memory.remember([experience()])
        feedback = {'id': 'lesson-1', 'page': 'farm', 'kind': 'teaching', 'experience': 'exp-1',
                    'valence': 'positive', 'lesson': 'I like curved fluttering.'}
        self.memory.remember([feedback])
        notes = self.memory.recall('farm', 'improvise', 'butterfly')
        self.assertEqual(notes[0]['lesson'], feedback['lesson'])
        self.assertEqual(notes[0]['strength'], .6)
        self.assertNotIn('subject', notes[0]); self.assertNotIn('start', json.dumps(notes))
        self.assertNotIn('MOVE:', json.dumps(notes))

    def test_feedback_dedup_and_negative_reinforcement(self):
        self.memory.remember([experience()])
        feedback = {'id': 'lesson-1', 'page': 'farm', 'kind': 'teaching', 'experience': 'exp-1',
                    'valence': 'negative', 'lesson': 'Less straight movement.'}
        self.memory.remember([feedback]); self.memory.remember([feedback])
        self.assertEqual(self.native.get_stv('1'), [.4, .55])

    def test_store_reopen_keeps_memory_and_dedup_identity(self):
        self.memory.remember([experience()])
        reopened = NativeOmegaMemory('omegajev', native=self.native, embed=lambda _: [1.0], directory=self.tmp.name)
        self.assertEqual(reopened.remember([experience()])['stored'], 0)
        self.assertEqual(reopened.recall('farm', 'play')[0]['moves'], 6)

    def test_repeated_query_caches_embedding_and_background_encoding_does_not_block_recall(self):
        import threading
        entered, release = threading.Event(), threading.Event()
        calls = []
        def embed(text):
            calls.append(text)
            if 'exp-blocking' in text:
                entered.set(); release.wait(3)
            return [1.0]
        memory = NativeOmegaMemory('omegajev', native=self.native, embed=embed, directory=self.tmp.name)
        memory.remember([experience()])
        memory.recall('farm', 'play'); memory.recall('farm', 'play')
        self.assertEqual(calls.count('play'), 1)
        worker = threading.Thread(target=lambda: memory.remember([experience('exp-blocking')]))
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            start = time.monotonic()
            self.assertTrue(memory.recall('farm', 'play'))
            self.assertLess(time.monotonic() - start, .2)
        finally:
            release.set(); worker.join(3)

    def test_two_agents_have_distinct_indices_and_role_validation(self):
        llm = NativeOmegaMemory('omegallm', native=self.native, embed=lambda _: [1.0], directory=self.tmp.name)
        llm.remember([{'kind': 'conversation', 'id': 'chat-1', 'page': 'farm', 'text': 'Call me Fox.', 'reply': 'Hello Fox.'}])
        self.memory.remember([experience()])
        self.assertEqual(len(llm.recall('farm', 'name')), 1)
        self.assertEqual(llm.recall('farm', 'name')[0]['kind'], 'conversation')
        self.assertNotIn('Fox', json.dumps(self.memory.recall('farm', 'play')))
        with self.assertRaises(ValueError): llm.remember([experience()])

    def test_page_and_asset_isolation_even_when_native_retrieval_returns_other_records(self):
        self.memory.remember([experience(), experience('space-exp', 'space')])
        self.assertEqual(len(self.memory.recall('farm', 'play')), 1)
        self.assertEqual(self.memory.recall('beach', 'play'), [])
        self.assertEqual(self.memory.recall('farm', 'play', 'cow'), [])
        with self.assertRaises(ValueError):
            self.memory.remember([{'id': 'bad', 'page': 'beach', 'kind': 'teaching', 'experience': 'exp-1',
                                   'valence': 'positive', 'lesson': 'Wrong page.'}])

    def test_cap_eviction_and_restart(self):
        for n in range(MAX_RECORDS + 2): self.memory.remember([experience(str(n))])
        self.assertEqual(len(self.native.docs), MAX_RECORDS)
        self.assertEqual(len(json.loads(self.memory.path.read_text())), MAX_RECORDS)
        reopened = NativeOmegaMemory('omegajev', native=self.native, embed=lambda _: [1.0], directory=self.tmp.name)
        self.assertEqual(reopened.describe()['records'], MAX_RECORDS)

    def test_unknown_experience_and_malformed_evidence_cannot_create_a_reward(self):
        for change in ({'moves': 999}, {'start': {'x': float('nan'), 'y': .2}},
                       {'command': 'shell'}, {'kind': {}}, {'source': 'llm'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                clean_event({**experience(), **change}, 'omegajev')
        with self.assertRaises(ValueError):
            self.memory.remember([{'id': 'unknown', 'page': 'farm', 'kind': 'teaching', 'experience': 'invented',
                                   'valence': 'positive', 'lesson': 'Good.'}])
        self.assertEqual(self.memory.describe()['records'], 0)


class ExperienceHandoff(unittest.TestCase):
    def test_accepted_moves_create_bounded_episodes_and_grab_flushes_last_partial(self):
        jev = Chooser(); jev.remember = Mock(return_value={'ok': True})
        b = bridge.Bridge(jev_runtime=jev, continuous_motion=True, motion_threaded=False)
        now = [100.0]; b.motion_player.clock = lambda: now[0]
        try:
            b.animate({'sticker': 'butterfly-1', 'command_id': 'tap'})
            for _ in range(9):
                now[0] += .25; b.motion_player.observe(); b.motion_player.pump()
            b.hold({'sticker': 'butterfly-1'})
            records = b.experiences.describe()
            self.assertGreaterEqual(len(records), 2)
            self.assertTrue(all(0 <= e['moves'] <= 6 for e in records))
            self.assertTrue(all(e['source'] == 'jev' for e in records))
            self.assertNotIn('MOVE:', json.dumps(records))
            revision = b.kernel.revision
            bad = b.experiences.teach({'experience': 'invented', 'valence': 'positive', 'lesson': 'good'}, records)
            self.assertFalse(bad['ok']); self.assertEqual(b.kernel.revision, revision)
        finally: b.motion_player.close()

    def test_language_teaching_binds_to_offered_episode_and_changes_no_world_state(self):
        jev = Chooser(); jev.remember = Mock(return_value={'ok': True, 'stored': 1})
        llm = FakeAgentRuntime()
        b = bridge.Bridge(jev_runtime=jev, agent_runtime=llm)
        e = experience(); b.experiences.recent.append(e)
        llm.converse = lambda **_: {'ok': True, 'reply': 'You like curves.',
                                  'teaching': {'experience': e['id'], 'valence': 'positive', 'lesson': 'Likes curves.'}}
        revision = b.kernel.revision
        result = b.converse({'text': 'I like that twirl.'})
        self.assertTrue(result['teaching']['ok'])
        self.assertEqual(b.kernel.revision, revision)
        batch = jev.remember.call_args.args[0]
        self.assertEqual(batch[0], e); self.assertEqual(batch[1]['kind'], 'teaching')

    def test_grab_does_not_wait_for_memory_embedding_or_storage(self):
        import threading
        entered, release = threading.Event(), threading.Event()
        jev = Chooser()
        def remember(_): entered.set(); release.wait(3); return {'ok': True}
        jev.remember = remember
        b = bridge.Bridge(jev_runtime=jev, continuous_motion=True, motion_threaded=False)
        try:
            b.experiences.enqueue(experience()); self.assertTrue(entered.wait(1))
            start = time.monotonic(); self.assertTrue(b.hold({'sticker': 'butterfly-1'})['ok'])
            self.assertLess(time.monotonic() - start, .2)
        finally: release.set(); b.motion_player.close()

    def test_failed_feedback_storage_does_not_claim_the_preference_was_saved(self):
        jev = Chooser(); jev.remember = Mock(return_value={'ok': False, 'error': 'omega-memory-unavailable'})
        llm = FakeAgentRuntime()
        b = bridge.Bridge(jev_runtime=jev, agent_runtime=llm)
        e = experience(); b.experiences.recent.append(e)
        llm.converse = lambda **_: {'ok': True, 'reply': 'I will remember it.',
            'teaching': {'experience': e['id'], 'valence': 'positive', 'lesson': 'Likes curves.'}}
        revision = b.kernel.revision
        result = b.converse({'text': 'Remember that lovely curve.'})
        self.assertFalse(result['teaching']['ok'])
        self.assertIn("couldn't save", result['reply'])
        self.assertEqual(b.kernel.revision, revision)


if __name__ == '__main__': unittest.main()
