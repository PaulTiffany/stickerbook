"""Generated pixels do not supply authority or place themselves in the world."""
import base64
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge
import creator_drafts
import sticker_creator
from test_bridge import FakeAgentRuntime


def png(width=256, height=256):
    def chunk(name, data):
        return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data))
    raw = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))
    raw += chunk(b'IDAT',zlib.compress((b'\x00'+b'\x80\x00\xff\xff'*width)*height))+chunk(b'IEND',b'')
    return 'data:image/png;base64,'+base64.b64encode(raw).decode()


class CreatorDrafts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.raw = {'kind':'sticker','name':'Purple dragon','frames':[png()]*4,
                    'owner':'agent:spoofed','capabilities':['shell'],'animations':['delete-file']}
    def tearDown(self): self.temp.cleanup()

    def test_four_png_poses_become_fixed_visual_vocabulary_not_provider_authority(self):
        draft = creator_drafts.publish(self.raw,self.temp.name)
        self.assertEqual(len(draft['asset']['sprites']),4)
        self.assertEqual(set(draft['asset']['clips']),{'rest','play'})
        self.assertNotIn('shell',json.dumps(draft)); self.assertNotIn('agent:spoofed',json.dumps(draft))
        self.assertEqual(len(list(Path(self.temp.name).rglob('*.png'))),4)

    def test_bad_frame_count_remote_urls_and_wrong_dimensions_fail_before_publication(self):
        for frames in ([png()]*3,[png()]*5,['https://example.com/image.png']*4,[png(128,128)]*4):
            with self.subTest(frames=len(frames)), self.assertRaises(ValueError):
                creator_drafts.publish({**self.raw,'frames':frames},self.temp.name)
        self.assertEqual(list(Path(self.temp.name).iterdir()),[])

    def test_generation_and_acceptance_do_not_place_any_sticker_and_placement_uses_kernel(self):
        llm = FakeAgentRuntime()
        llm.creator_draft = Mock(return_value={'ok':True,'draft':self.raw})
        b = bridge.Bridge(agent_runtime=llm)
        revision = b.kernel.revision
        with patch.object(bridge,'GENERATED_PAGE_DIR',self.temp.name):
            result = b.creator_draft({'kind':'sticker','prompt':'dragon','animation_intent':'animate','asset_schema_version':2})
        self.assertTrue(result['ok'])
        self.assertEqual(b.kernel.revision,revision)
        self.assertFalse(b.accept_sticker_draft({'draft':'invented'})['ok'])
        accepted = b.accept_sticker_draft({'draft':result['draft']['id']})
        self.assertTrue(accepted['ok']); self.assertEqual(b.kernel.revision,revision)
        definition = b.kernel.assets[accepted['asset']]
        self.assertEqual(definition.animations,('none','rest','play'))
        placed = b.place({'asset':accepted['asset'],'point':{'x':.5,'y':.5},'command_id':'child-place'})
        self.assertTrue(placed['receipt']['accepted'])
        sticker = b.kernel.sticker(placed['receipt']['object'])
        self.assertEqual(sticker.owner,'human:kid')
        scene = b.jev_controller._scene('human:kid',{'subject':sticker.id}, {})
        self.assertEqual(scene['subject']['name'],'Purple dragon')
        self.assertEqual(scene['subject']['clips'],['none','rest','play'])

    def test_page_draft_has_exact_landscape_and_portrait_artwork(self):
        draft = creator_drafts.publish({'kind':'page','images':{
            'landscape':png(1916,717),'portrait':png(941,1574)}},self.temp.name)
        self.assertEqual(draft['variants']['landscape']['width'],1916)
        self.assertEqual(draft['variants']['portrait']['height'],1574)

    def test_creator_rejects_model_endpoints_commands_and_unbounded_input(self):
        for raw in ({'kind':'shell','prompt':'run'}, {'kind':'sticker','prompt':'x','endpoint':'evil'},
                    {'kind':'sticker','prompt':'x'*501}, {'kind':'sticker','prompt':None}):
            self.assertEqual(sticker_creator.create(raw)['error'],'invalid-creator-request')
