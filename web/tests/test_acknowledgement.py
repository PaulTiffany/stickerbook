"""The optional parallel utterance has no route to semantic or kernel work."""
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bridge
from test_bridge import FakeAgentRuntime

class AcknowledgementBoundary(unittest.TestCase):
    def runtime(self):
        runtime=FakeAgentRuntime()
        runtime.capabilities=lambda:{'conversational_agent':True,'creator_agent':False,'conversation_acknowledgement':True}
        runtime.acknowledge=Mock(return_value={'ok':True,'reply':'Let me consider that.'})
        runtime.converse=Mock()
        return runtime

    def test_speech_does_not_change_world_or_invoke_goal_path(self):
        runtime=self.runtime();b=bridge.Bridge(agent_runtime=runtime)
        before=b.kernel.revision
        self.assertEqual(b.acknowledge({'text':'Make the butterfly fly.'}),{'ok':True,'reply':'Let me consider that.'})
        self.assertEqual(b.kernel.revision,before)
        runtime.converse.assert_not_called()
        for bad in ({'ok':True,'reply':'Move!','goal':{'intent':'move'}},
                    {'ok':True,'reply':'x'*241}, {'ok':True,'reply':[]}, {'ok':False}):
            runtime.acknowledge.return_value=bad
            self.assertEqual(b.acknowledge({'text':'hello'}),{'ok':False})
            self.assertEqual(b.kernel.revision,before)

    def test_page_exit_and_runtime_failure_discard_speech(self):
        runtime=self.runtime();b=bridge.Bridge(agent_runtime=runtime)
        def leave(text):
            b._activation_serial+=1
            return {'ok':True,'reply':'Old page reply'}
        runtime.acknowledge.side_effect=leave
        self.assertEqual(b.acknowledge({'text':'hello'}),{'ok':False})
        runtime.acknowledge.side_effect=TimeoutError
        self.assertEqual(b.acknowledge({'text':'hello'}),{'ok':False})

    def test_disabled_lane_and_extra_fields_do_not_call_runtime(self):
        runtime=self.runtime();b=bridge.Bridge(agent_runtime=runtime)
        self.assertEqual(b.acknowledge({'text':'hello','goal':{}}),{'ok':False})
        runtime.capabilities=lambda:{'conversational_agent':True}
        self.assertEqual(b.acknowledge({'text':'hello'}),{'ok':False})
        runtime.acknowledge.assert_not_called()
