"""Finite-body composition, fresh snapshots and human precedence on double tap."""
import json
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge
import farm
from jev_controller import MAX_DOUBLE_TAP_TURNS
from stickerbook_core import StickerInstance, Command, MOVE_STICKER


class ScriptJev:
    def __init__(self, choices):
        self.choices = choices
        self.calls = []
        self.hook = None

    def available(self):
        return True

    def choose(self, **kwargs):
        self.calls.append(kwargs)
        if self.hook:
            self.hook(kwargs)
        choice = self.choices[min(len(self.calls) - 1, len(self.choices) - 1)]
        return choice if isinstance(choice, dict) else {'ok': True, 'choice': choice}


class Improvisation(unittest.TestCase):
    def setUp(self):
        self.jev = ScriptJev(['NOOP'])
        self.bridge = bridge.Bridge(jev_runtime=self.jev)
        self.kernel = self.bridge.kernel
        for sticker, x in [('frog-1', .5), ('frog-2', .2)]:
            self.kernel.place_sticker(StickerInstance(sticker, farm.HUMAN_ID,
                farm.HUMAN_ID, 'frog', self.kernel.page, x=x, y=.5, animation='rest'))

    def tap(self):
        return self.bridge.animate({'sticker': 'frog-1', 'command_id': 'double-tap'})

    def move(self, subject, x):
        return self.bridge.propose_move({'sticker': subject, 'command_id': 'human-' + subject,
                                        'point': {'x': x, 'y': .7}})

    def test_surface_contains_moves_clips_facing_noop_but_no_resize_or_other_subjects(self):
        result = self.tap()
        call = self.jev.calls[0]
        actions = call['actions']
        for prefix in ('MOVE:', 'ANIMATE:', 'FACE:'):
            self.assertTrue(any(key.startswith(prefix) for key in actions))
        self.assertIn('NOOP', actions)
        self.assertTrue(all(key == 'NOOP' or key.split(':')[1] == 'frog-1' for key in actions))
        self.assertFalse(any(key.startswith(('RESIZE:', 'REMOVE:', 'ADD:')) for key in actions))
        self.assertEqual(call['goal'], {'subject': 'frog-1', 'intent': 'control', 'behavior': 'improvise'})
        self.assertEqual(call['max_turns'], 3)
        self.assertEqual(result['jev']['stopped'], 'noop')

    def test_move_composition_rebuilds_tables_coordinates_and_revisions_every_turn(self):
        self.jev.choices = ['MOVE:frog-1:STEP-E', 'MOVE:frog-1:STEP-E', 'ANIMATE:frog-1:hop']
        result = self.tap()['jev']
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['stopped'], 'turn-limit')
        self.assertEqual(len(result['trace']), MAX_DOUBLE_TAP_TURNS)
        self.assertAlmostEqual(self.kernel.sticker('frog-1').x, .62)
        self.assertEqual(self.kernel.sticker('frog-1').animation, 'hop')
        scenes = [call['scene'] for call in self.jev.calls]
        self.assertEqual([scene['subject']['x'] for scene in scenes], [.5, .56, .62])
        self.assertEqual(len({scene['revision'] for scene in scenes}), 3)
        self.assertNotEqual(self.jev.calls[0]['actions']['MOVE:frog-1:STEP-E'],
                            self.jev.calls[1]['actions']['MOVE:frog-1:STEP-E'])
        for step, scene in zip(result['trace'], scenes):
            receipt = step['receipt']
            self.assertTrue(receipt['accepted'])
            self.assertEqual(receipt['basedOnRevision'], scene['revision'])
            self.assertEqual(receipt['requestedBy'], farm.HUMAN_ID)
            self.assertIsNone(receipt['translatedBy'])
            self.assertEqual(receipt['selectedBy'], farm.AGENT_ID)

    def test_facing_then_move_then_noop_composes_three_legal_primitives(self):
        self.jev.choices = ['FACE:frog-1:LEFT', 'MOVE:frog-1:STEP-N', 'NOOP']
        result = self.tap()['jev']
        self.assertTrue(result['ok'])
        self.assertEqual(result['stopped'], 'noop')
        self.assertEqual(self.kernel.sticker('frog-1').facing, 'left')
        self.assertAlmostEqual(self.kernel.sticker('frog-1').y, .44)
        self.assertEqual(len(self.jev.calls), 3)

    def test_noop_stops_first_turn_without_mutation(self):
        revision = self.kernel.revision
        result = self.tap()['jev']
        self.assertTrue(result['ok'])
        self.assertEqual(result['stopped'], 'noop')
        self.assertEqual(self.kernel.revision, revision)
        self.assertEqual(len(self.jev.calls), 1)

    def test_unknown_or_other_sticker_key_fails_closed(self):
        for choice in ('shell anything', 'MOVE:frog-2:STEP-E', 'MOVE:frog-1:x=.99:y=.99'):
            with self.subTest(choice=choice):
                self.jev.choices, self.jev.calls = [choice], []
                revision = self.kernel.revision
                result = self.tap()['jev']
                self.assertEqual(result['error'], 'unknown-jev-choice')
                self.assertEqual(self.kernel.revision, revision)

    def test_untrusted_coordinates_cannot_override_host_destination(self):
        self.jev.choices = [{'ok': True, 'choice': 'MOVE:frog-1:STEP-E',
                             'point': {'x': .99, 'y': .99}}, 'NOOP']
        self.assertTrue(self.tap()['ok'])
        self.assertAlmostEqual(self.kernel.sticker('frog-1').x, .56)
        self.assertAlmostEqual(self.kernel.sticker('frog-1').y, .5)

    def test_stale_same_subject_without_human_provenance_is_refused_without_retry(self):
        self.jev.choices = ['MOVE:frog-1:STEP-E']
        def mutate(_):
            self.kernel.propose(Command(MOVE_STICKER, farm.HUMAN_ID, 'external',
                object_id='frog-1', params=(('x', .3), ('y', .3))))
        self.jev.hook = mutate
        result = self.tap()['jev']
        self.assertEqual(result['error'], 'jev-action-refused')
        self.assertEqual(result['trace'][0]['receipt']['reason'], 'stale-revision')
        self.assertEqual(len(self.jev.calls), 1)
        self.assertAlmostEqual(self.kernel.sticker('frog-1').x, .3)

    def test_human_same_subject_move_during_unlocked_think_time_supersedes(self):
        entered, release = threading.Event(), threading.Event()
        self.jev.choices = ['MOVE:frog-1:STEP-E']
        def wait(_):
            entered.set()
            self.assertTrue(release.wait(3))
        self.jev.hook = wait
        result = []
        worker = threading.Thread(target=lambda: result.append(self.tap()))
        worker.start()
        self.assertTrue(entered.wait(2))
        self.assertTrue(self.move('frog-1', .8)['receipt']['accepted'])
        release.set()
        worker.join(4)
        self.assertFalse(worker.is_alive())
        episode = result[0]['jev']
        self.assertEqual(episode['error'], 'human-superseded')
        self.assertTrue(episode['trace'][0]['superseded'])
        self.assertEqual(episode['trace'][0]['receipt']['reason'], 'stale-revision')
        self.assertEqual(len(self.jev.calls), 1)
        self.assertAlmostEqual(self.kernel.sticker('frog-1').x, .8)

    def test_different_sticker_human_move_does_not_supersede_subject(self):
        self.jev.choices = ['MOVE:frog-1:STEP-E', 'NOOP']
        self.jev.hook = lambda _: self.move('frog-2', .8)
        result = self.tap()['jev']
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['trace'][0]['receipt']['accepted'])
        self.assertEqual(result['stopped'], 'noop')
        self.assertAlmostEqual(self.kernel.sticker('frog-1').x, .56)

    def test_taught_patterns_are_bounded_advisory_context_not_action_grants(self):
        self.jev.choices = ['MOVE:frog-1:STEP-E', 'NOOP']
        self.tap()
        remembered = self.bridge.jev_controller.remember_recent(subject_id='frog-1',
                     label='happy dance', learned_by=farm.HUMAN_ID)
        self.assertTrue(remembered['ok'])
        self.jev.calls, self.jev.choices = [], ['NOOP']
        self.bridge.animate({'sticker': 'frog-1', 'command_id': 'learned-tap'})
        call = self.jev.calls[0]
        patterns = call['scene']['known_patterns']
        self.assertEqual(patterns[0]['label'], 'happy dance')
        self.assertLessEqual(len(patterns), 8)
        self.assertNotIn('MOVE:frog-1:', json.dumps(patterns))
        self.assertNotIn('transcript', call['scene'])
        self.assertNotIn('steps', call['goal'])
        self.assertFalse(any(key.startswith('RESIZE:') for key in call['actions']))

    def test_missing_subject_after_first_step_fails_closed(self):
        self.jev.choices = ['MOVE:frog-1:STEP-E']
        self.jev.hook = lambda _: self.bridge.remove({'sticker': 'frog-1', 'command_id': 'remove'})
        result = self.tap()['jev']
        self.assertFalse(result['ok'])
        self.assertEqual(result['trace'][0]['receipt']['reason'], 'unknown-action-key')
        self.assertEqual(len(self.jev.calls), 1)

    def test_first_turn_noop_cannot_reach_back_to_an_older_demonstration(self):
        self.jev.choices = ['MOVE:frog-1:STEP-E']
        self.tap()
        self.jev.calls, self.jev.choices = [], ['NOOP']
        self.bridge.animate({'sticker': 'frog-1', 'command_id': 'new-noop-episode'})
        saved = self.bridge.jev_controller.remember_recent(subject_id='frog-1',
                 label='not demonstrated', learned_by=farm.HUMAN_ID)
        self.assertEqual(saved['error'], 'no-accepted-pattern-steps')
