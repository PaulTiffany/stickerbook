"""Native Omega recall informs Jev without extending its executable surface."""
import importlib.util
import json
import logging
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


class JevOmegaMemory(unittest.TestCase):
    def test_rpc_provider_projects_memory_and_rejects_unoffered_selection(self):
        directory = Path(__file__).resolve().parents[2] / 'jev' / 'omega_jev' / 'providers'
        providers = types.ModuleType('providers')
        providers.LLMProvider = object
        config = types.ModuleType('config'); config.config_get_by_key = lambda *a: None
        logger = types.ModuleType('src.logger'); logger.get_logger = logging.getLogger
        core = types.ModuleType('jev_core'); core.FAIL_CLOSED_OUTPUT = ''
        core.ACTIONS = {}; core.ACTION_CRITERIA = {}
        core.decide = Mock(return_value=('sb-return', {'action_id': 'CURRENT-MOVE'}))
        rpc = types.ModuleType('stickerbookrpc')
        request = {'goal': {'behavior': 'improvise'}, 'scene': {'page': 'beach',
            'subject': {'definition': 'butterfly'}, 'known_patterns': [{'label': 'happy dance'}]},
            'actions': {'CURRENT-MOVE': 'Move within current bounds', 'NOOP': 'Stop'}, 'turn': 1, 'max_turns': 3}
        rpc.current_request = Mock(return_value=request)
        rpc.recall_memory = Mock(return_value=[{'kind': 'teaching', 'lesson': 'Likes gentle curves.'}])
        rpc.stage_result = Mock(return_value=True)
        with patch.dict(sys.modules, {'providers': providers, 'config': config,
                'src.logger': logger, 'jev_core': core, 'sb_bridge': types.ModuleType('sb_bridge'),
                'stickerbookrpc': rpc}):
            spec = importlib.util.spec_from_file_location('jev_memory_test', directory / 'jev.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            provider = module.JevProvider(); provider.rpc_mode = True
            provider.model = 'test'; provider.transport = Mock()
            with patch.object(module, 'harden_llm_commands'):
                self.assertEqual(provider.chat('raw Omega history is ignored'), 'sb-return')
                view = core.decide.call_args.kwargs['state']
                self.assertEqual(view['scene']['known_patterns'], [{'label': 'happy dance'}])
                self.assertIn('gentle curves', json.dumps(view['scene']['omega_memory']))
                self.assertNotIn('omega_memory', request['scene'])
                rpc.recall_memory.assert_called_once_with('omegajev', 'beach', 'improvise', 'butterfly')
                self.assertEqual(set(core.decide.call_args.kwargs['actions']), {'CURRENT-MOVE', 'NOOP'})
                request['scene']['padding'] = 'x' * 3000
                request['scene']['starting_behavior'] = {'tendency': 'x' * 1200}
                provider.chat('ignored')
                trimmed = core.decide.call_args.kwargs['state']['scene']
                self.assertNotIn('starting_behavior', trimmed)
                self.assertEqual(trimmed['known_patterns'], [{'label': 'happy dance'}])
                self.assertIn('gentle curves', json.dumps(trimmed['omega_memory']))
                request['scene'].pop('padding')
                request['scene'].pop('starting_behavior')
                core.decide.return_value = ('arbitrary-command', {'action_id': 'INVENTED-MOVE'})
                provider.chat('ignored')
                self.assertFalse(rpc.stage_result.call_args.args[0]['ok'])
