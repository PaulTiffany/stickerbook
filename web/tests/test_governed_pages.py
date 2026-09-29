"""Six real HTTP page worlds, with page-local evidence and model cancellation."""
import json
from pathlib import Path
import sys
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import book
import bridge
import farm
from test_bridge import GoalAgentRuntime
from stickerbook_core import StickerInstance


class MoveJev:
    def __init__(self):
        self.calls = []
        self.entered = self.release = None

    def available(self):
        return True

    def choose(self, **kwargs):
        self.calls.append(kwargs)
        if self.entered:
            self.entered.set()
            assert self.release.wait(5)
        key = next((key for key in kwargs['actions'] if key.endswith(':STEP-E')), 'NOOP')
        return {'ok': True, 'choice': key if len(self.calls) == 1 else 'NOOP'}


class GovernedPages(unittest.TestCase):
    def setUp(self):
        self.llm = GoalAgentRuntime()
        self.jev = MoveJev()
        self.server, self.book = bridge.serve(port=0, quiet=True,
                                            agent_runtime=self.llm, jev_runtime=self.jev)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, route, body=None):
        request = urllib.request.Request(self.base + route,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'})
        try:
            response = urllib.request.urlopen(request, timeout=8)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def switch(self, page):
        return self.request('/api/select-page', {'page': page})[1]

    def place(self, asset, command):
        return self.request('/api/place', {'asset': asset, 'command_id': command,
                             'point': {'x': .5, 'y': .5}})[1]['receipt']['object']

    def test_exact_six_pages_open_with_shared_catalog_and_both_art_variants(self):
        pages = self.request('/api/book')[1]['pages']
        self.assertEqual({p['id'] for p in pages},
                         {'farm', 'beach', 'playground', 'space', 'school', 'theater'})
        for page in pages:
            with self.subTest(page=page['id']):
                state = self.switch(page['id'])['state']
                self.assertEqual(state['page']['id'], page['id'])
                self.assertEqual({d['id'] for d in state['definitions']}, set(farm.ASSETS))
                if page['id'] != 'farm':
                    self.assertEqual(state['stickers'], [])
                for orientation in ('landscape', 'portrait'):
                    path = book.PAGES[page['id']]['variants'][orientation]['src']
                    with urllib.request.urlopen(self.base + '/' + path) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIn(b'<svg', response.read())
        original = self.book.kernel
        self.assertEqual(self.request('/api/select-page', {'page': 'unknown'})[0], 400)
        self.assertIs(self.book.kernel, original)
        self.assertFalse(self.switch([])['ok'])

    def test_stickers_receipts_history_and_paths_are_page_local_and_restored(self):
        frog = self.place('frog', 'farm-frog')
        self.book.observe_page_path({'duration_ms': 500, 'samples': [
            {'t': 0, 'x': .2, 'y': .4}, {'t': 1, 'x': .4, 'y': .4}]})
        farm_session = self.book._pages['farm']
        farm_receipts = len(farm_session.kernel.receipts)
        self.switch('beach')
        self.assertEqual(self.book.state()['stickers'], [])
        self.assertEqual(len(self.book.kernel.receipts), 0)
        self.assertEqual(self.book.observed_inputs.after(0), ())
        crab = self.place('crab', 'beach-crab')
        self.llm.goal = {'subject': crab, 'intent': 'move', 'behavior': 'east'}
        result = self.request('/api/agent/converse', {'text': 'Move the crab east'})[1]
        self.assertTrue(result['jev']['trace'][0]['receipt']['accepted'])
        self.assertAlmostEqual(self.book.kernel.sticker(crab).x, .56)
        self.assertEqual(self.book.kernel.sticker(crab).page, book.PAGES['beach']['world_page'])
        self.assertIs(self.book.jev_controller.kernel, self.book.kernel)
        beach_session = self.book._pages['beach']
        self.switch('farm')
        self.assertEqual(self.book.kernel.sticker(frog).asset, 'frog')
        self.assertEqual(len(self.book.kernel.receipts), farm_receipts)
        self.assertNotIn('crab', [s['definition'] for s in self.book.state()['stickers']])
        self.assertIsNot(self.book.history, beach_session.history)
        self.assertIsNot(self.book.page_paths, beach_session.page_paths)
        self.assertIsNot(self.book.interactions, beach_session.interactions)
        self.assertIsNot(self.book.trajectory_executions, beach_session.trajectory_executions)
        self.assertIsNone(self.book.pending_reference)
        self.assertEqual(self.book.observed_inputs.after(self.book._input_marker), ())

    def test_book_wide_asset_pattern_is_advisory_but_history_is_not_shared(self):
        farm_session = self.book._pages['farm']
        receipt = self.book.kernel.propose_key(farm.HUMAN_ID, 'ANIMATE:cow-1:chew', 'teach')
        farm_session.history.record(receipt, origin='gesture-jev', key='ANIMATE:cow-1:chew', subject_id='cow-1')
        saved = farm_session.jev_controller.remember_recent(subject_id='cow-1', label='happy dance', learned_by=farm.HUMAN_ID)
        self.assertTrue(saved['ok'])
        self.switch('space')
        self.assertIs(self.book.patterns, farm_session.patterns)
        self.assertEqual(self.book.patterns.describe_for_scene('cow')[0]['label'], 'happy dance')
        self.assertEqual(self.book.history.describe_for_scene(), [])

    def test_delayed_jev_cannot_mutate_after_switch_even_when_returned_to_farm(self):
        self.jev.entered, self.jev.release = threading.Event(), threading.Event()
        self.llm.goal = {'subject': 'cow-1', 'intent': 'move'}
        original = self.book.kernel.sticker('cow-1').x
        result = []
        worker = threading.Thread(target=lambda: result.append(self.book.converse({'text': 'Move cow'})))
        worker.start()
        self.assertTrue(self.jev.entered.wait(3))
        self.switch('beach')
        self.switch('farm')
        self.jev.release.set()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result[0]['error'], 'page-changed')
        self.assertEqual(self.book.kernel.sticker('cow-1').x, original)

    def test_old_page_request_is_refused_instead_of_touching_matching_id(self):
        self.switch('beach')
        result = self.request('/api/place', {'_page': 'farm', 'asset': 'frog',
                      'command_id': 'late', 'point': {'x': .5, 'y': .5}})[1]
        self.assertEqual(result['error'], 'page-changed')
        self.assertEqual(self.book.state()['stickers'], [])
