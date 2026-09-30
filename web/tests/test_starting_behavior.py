"""Starting tendencies remain advisory and reference only declared clips."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import governed_world,bridge
from starting_behavior import starting_behavior
from test_motion_player import Chooser

class StartingBehavior(unittest.TestCase):
    def test_all_existing_definitions_have_bounded_non_executable_priors(self):
        for asset,definition in governed_world.ASSETS.items():
            prior=starting_behavior(asset,definition.animations)
            self.assertTrue(prior['advisory'])
            self.assertLessEqual(len(prior['tendency']),160)
            self.assertLessEqual(len(prior['poses']),3)
            self.assertTrue(set(prior['poses']).issubset(definition.animations))
            self.assertIn('override',prior['precedence'])
            self.assertEqual(set(prior),{'advisory','tendency','poses','precedence'})

    def test_flying_hopping_stationary_and_custom_definitions_differ_without_permissions(self):
        butterfly=starting_behavior('butterfly',('rest','flutter','land'))
        frog=starting_behavior('frog',('rest','hop','land'))
        flower=starting_behavior('flower',('rest','sway','bloom'))
        custom=starting_behavior('made-new',('rest','play'))
        self.assertIn('curves',butterfly['tendency'])
        self.assertIn('hops',frog['tendency'])
        self.assertIn('placed spot',flower['tendency'])
        self.assertEqual(custom['poses'],['play'])
        butterfly['poses'].clear()
        self.assertIn('flutter',starting_behavior('butterfly',('flutter',))['poses'])

    def test_jev_and_language_receive_priors_but_world_and_known_memory_are_preserved(self):
        jev=Chooser()
        b=bridge.Bridge(jev_runtime=jev,continuous_motion=True,motion_threaded=False)
        try:
            before=b.kernel.revision
            scene=b._conversation_scene()
            self.assertEqual(b.kernel.revision,before)
            self.assertTrue(all('startingBehavior' in d for d in scene['definitions']))
            result=b.animate({'sticker':'butterfly-1','command_id':'starter'})
            self.assertTrue(result['ok'])
            b.motion_player.pump()
            call=jev.calls[0]
            self.assertIn('curves',call['scene']['starting_behavior']['tendency'])
            self.assertIn('known_patterns',call['scene'])
            self.assertTrue(call['actions'])
            self.assertNotIn('starting_behavior',call['actions'])
        finally:b.motion_player.close()
