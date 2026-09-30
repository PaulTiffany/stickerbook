"""Visual observation transport and narration never bypass host authority."""
import base64
import json
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from visual_context import clean_visual, visual_input
import test_pattern_provider as provider_tests
from test_bridge import FakeAgentRuntime
import bridge
from test_motion_player import Chooser


def observation(page='farm', revision=0):
    # Dimension-bearing JPEG header fixture; actual image qualification is live.
    header = b'\xff\xd8\xff\xc0' + struct.pack('>HBHH', 8, 8, 3, 2) + b'\x00\xff\xd9'
    return {'page': page, 'revision': revision, 'width': 2, 'height': 3,
            'image': 'data:image/jpeg;base64,' + base64.b64encode(header).decode()}


class VisualBounds(unittest.TestCase):
    def test_page_revision_and_actual_dimensions_are_checked(self):
        raw = observation(revision=4)
        self.assertEqual(clean_visual(raw, page='farm', revision=5), raw)
        for change in ({'page': 'beach'}, {'revision': 6}, {'revision': True},
                       {'width': 3}, {'height': 2048}, {'image': 'https://evil/image.jpg'},
                       {'image': 'data:image/jpeg;base64,!!'}, {'command': 'MOVE:any'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                clean_visual({**raw, **change}, page='farm', revision=5)

    def test_image_never_appears_inside_text_content(self):
        raw = {'text': 'tell a story', 'scene': {'visual': observation(), 'stickers': []}}
        text, image = visual_input(raw)
        self.assertNotIn('image', text['scene']['visual'])
        self.assertEqual(image, raw['scene']['visual'])
        self.assertIn('image', raw['scene']['visual'])

    def test_invalid_visual_cannot_reach_runtime(self):
        runtime = FakeAgentRuntime()
        runtime.converse = Mock()
        b = bridge.Bridge(agent_runtime=runtime)
        revision = b.kernel.revision
        result = b.converse({'text': 'fly around sun', 'visual': observation('beach')})
        self.assertFalse(result['ok'])
        runtime.converse.assert_not_called()
        self.assertEqual(b.kernel.revision, revision)

    def test_host_admits_observation_as_data_and_narration_has_no_receipt(self):
        runtime = FakeAgentRuntime()
        b = bridge.Bridge(agent_runtime=runtime)
        revision = b.kernel.revision
        result = b.converse({'text': 'Tell a story', 'visual': observation(revision=revision)})
        self.assertTrue(result['ok'])
        self.assertEqual(b.kernel.revision, revision)
        self.assertEqual(runtime.last_scene['visual']['page'], 'farm')
        self.assertEqual(runtime.last_scene['picture']['features'], [])
        self.assertNotIn('goal', result)
        self.assertNotIn('kernel', runtime.last_scene)

    def test_visual_goal_reaches_jev_as_semantics_without_pixels_or_new_authority(self):
        runtime = FakeAgentRuntime()
        goal = {'subject': 'butterfly-1', 'intent': 'control', 'behavior': 'circle around sun',
                'target': {'kind': 'point', 'x': .8, 'y': .2}}
        runtime.converse = lambda **_: {'ok': True, 'reply': 'Let me try.', 'goal': goal, 'image_used': True}
        jev = Chooser()
        b = bridge.Bridge(agent_runtime=runtime, jev_runtime=jev,
                          continuous_motion=True, motion_threaded=False)
        try:
            result = b.converse({'text': 'Fly around sun', 'visual': observation(revision=b.kernel.revision)})
            self.assertTrue(result['observation']['imageUsed'])
            self.assertEqual(result['jev']['result'], 'playing')
            b.motion_player.pump()
            self.assertEqual(jev.calls[0]['goal'], goal)
            self.assertNotIn('image', json.dumps(jev.calls[0]['scene']))
            self.assertNotIn('visual', jev.calls[0]['scene'])
            self.assertNotIn('kernel', jev.calls[0]['scene'])
        finally:
            b.motion_player.close()


class VisualProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        provider_tests.PatternProvider.setUpClass()
        cls.module = provider_tests.PatternProvider.module

    def test_both_protocols_have_real_image_blocks_not_json_image_text(self):
        for name, block_type in [('OpenAICompatibleTransport', 'image_url'),
                                 ('AnthropicTransport', 'image')]:
            with self.subTest(protocol=name):
                transport = getattr(self.module, name)('unused', 'unused', 1)
                transport._token = lambda: 'test-placeholder'
                transport._request = Mock(return_value={'choices': [{'message': {'content': '{}'}}],
                                                        'content': [{'type': 'text', 'text': '{}'}]})
                transport.complete('locked-model', {'text': 'story', 'scene': {'visual': observation()}}, 100)
                body = transport._request.call_args.args[0]
                content = body['messages'][-1]['content']
                self.assertEqual(content[1]['type'], block_type)
                self.assertNotIn('base64', content[0]['text'])

    def test_no_image_preserves_existing_text_only_transport(self):
        transport = self.module.OpenAICompatibleTransport('unused', 'unused', 1)
        transport._token = lambda: 'placeholder'
        transport._request = Mock(return_value={'choices': [{'message': {'content': '{}'}}]})
        transport.complete('model', {'scene': {}, 'text': 'hello'}, 100)
        self.assertIsInstance(transport._request.call_args.args[0]['messages'][1]['content'], str)

    def test_verified_text_fallback_discloses_missing_vision_instead_of_failing_or_faking_it(self):
        raw = {'text': 'fly around sun', 'scene': {'visual': observation(), 'stickers': []}}
        prepared = self.module.prepare_visual_inference(raw, 'openrouter', 'z-ai/glm-5.2')
        self.assertNotIn('visual', prepared['scene'])
        self.assertEqual(prepared['scene']['visualUnavailable'], 'selected-model-text-only')
        self.assertEqual(self.module.prepare_visual_inference(raw, 'asicloud', 'minimax/minimax-m3'), raw)

    def test_narration_stages_no_goal_and_changes_no_world_state(self):
        fixture = provider_tests.PatternProvider(methodName='test_valid_shapes_match_host_normalization')
        fixture.setUp()
        try:
            before = fixture.bridge.kernel.revision
            result = fixture.staged(None, {'text': 'tell a story', 'scene': {'visual': observation()}, 'inference': {}})
            self.assertTrue(result['ok'])
            self.assertNotIn('goal', result)
            self.assertEqual(fixture.bridge.kernel.revision, before)
        finally:
            fixture.tearDown()

    def test_visual_targets_use_existing_goal_schema_and_kernel_rejects_unbounded_points(self):
        for point in ({'kind': 'point', 'x': .75, 'y': .12},
                      {'kind': 'sticker', 'id': 'butterfly-1'}):
            goal = {'subject': 'butterfly-1', 'intent': 'control', 'behavior': 'circle around sun', 'target': point}
            self.assertEqual(self.module.clean_goal(goal), goal)
        with self.assertRaises(ValueError):
            self.module.clean_goal({'subject': 'butterfly-1', 'intent': 'move',
                                    'target': {'kind': 'point', 'x': 900, 'y': .1}})

    def test_browser_snapshot_uses_authoritative_endpoints_and_never_proposes(self):
        source = (Path(__file__).resolve().parents[1] / 'static/app.js').read_text(encoding='utf-8')
        capture = source.split('async function captureVisualContext() {', 1)[1].split('async function converseWithStickerBook', 1)[0]
        self.assertIn('sticker.x * metrics.width', capture)
        self.assertNotIn('visual.position', capture)
        self.assertNotIn('world.propose', capture)
        self.assertIn('url.origin !== location.origin', capture)
        self.assertIn('world.name === "public mechanical"', capture)
        self.assertIn('revokeObjectURL', capture)

    def test_actual_browser_capture_rewrites_tweens_inlines_art_and_skips_public(self):
        source = (Path(__file__).resolve().parents[1] / 'static/app.js').read_text(encoding='utf-8')
        function = 'async function captureVisualContext() {' + source.split('async function captureVisualContext() {', 1)[1].split('async function converseWithStickerBook', 1)[0]
        harness = r'''
const assert=require('node:assert/strict');
let world={name:'local governed'}, state={page:{id:'farm'},revision:7,stickers:[{id:'bird-1',x:.2,y:.3,scale:1,facing:'right'}]};
const activePageMetrics=()=>({width:1916,height:717});
let transforms=[],removed=[],fetches=[],revoked=0,draws=0,clones=0;
const sticker={dataset:{id:'bird-1'},setAttribute:(k,v)=>transforms.push([k,v])};
const art={getAttribute:()=>'/static/art.svg',setAttribute:(k,v)=>{assert.equal(k,'href');assert(v.startsWith('data:image/'));},removeAttributeNS(){}};
const svg={cloneNode:()=>{clones++;return {setAttribute(){},querySelector:id=>({remove:()=>removed.push(id)}),querySelectorAll:sel=>sel==='.sticker'?[sticker]:[art]};}};
const location={href:'http://localhost:8758/',origin:'http://localhost:8758'};
const fetch=async u=>{fetches.push(u);return {ok:true,blob:async()=>new Blob(['art'],{type:'image/svg+xml'})};};
class FileReader {readAsDataURL(){this.result='data:image/svg+xml;base64,YXJ0';this.onload();}}
class XMLSerializer {serializeToString(){return '<svg/>';}}
class Image {set src(v){this.onload();}}
const document={createElement:()=>({width:0,height:0,getContext:()=>({fillRect(){},drawImage(){draws++;}}),toDataURL:()=> 'data:image/jpeg;base64,YQ=='})};
const nativeRevoke=URL.revokeObjectURL;URL.revokeObjectURL=u=>{revoked++;nativeRevoke(u);};
'''
        tail = r'''
(async()=>{
const image=await captureVisualContext();
assert.equal(image.width,1024);assert.equal(image.height,383);
assert.equal(image.revision,7);assert.equal(image.page,'farm');
assert.equal(transforms[0][1],'translate(383.20000000000005 215.1) scale(1 1)');
assert.deepEqual(removed,['#reference-layer','#placement-layer']);
assert.equal(fetches.length,1);assert.equal(draws,1);assert.equal(revoked,1);
world.name='public mechanical';assert.equal(await captureVisualContext(),null);assert.equal(clones,1);
world.name='local governed';art.getAttribute=()=> 'https://elsewhere.invalid/art';
await assert.rejects(captureVisualContext(),/nonlocal-artwork/);assert.equal(fetches.length,1);
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        result = subprocess.run(['node', '-e', harness + function + tail], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
