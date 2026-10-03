import json
import os
import unittest
from unittest.mock import patch, Mock
from src import shared_discovery as shared

class SharedDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'DISCOVERY_ENABLED':'1','DISCOVERY_REQUEST_ID':'test-run-001','BLOG_CODEX_HOME':'/private/test-login','BLOG_CODEX_MODEL':'test-model'})
        self.env.start()
    def tearDown(self):self.env.stop()
    def test_keeps_selected_runtime_and_no_local_acceptance(self):
        accepted={'title':'검증 주제','keyword':'키워드','decision':'accepted'}
        class Client:
            def discover(self,input,**options):
                self.input=input;self.key=options['idempotency_key']
                options['assert_connection'](input['runtime'])
                options['generate']('server-owned prompt')
                options['assert_connection'](input['runtime'])
                return {'requestId':'r','state':'complete','candidates':[accepted,{'decision':'held'}]}
        client=Client();generate=Mock(return_value='{"candidates":[]}');check=Mock()
        result,report=shared.discover('리뷰',['이전 주제'],client=client,generator=generate,check=check)
        self.assertEqual(result,[accepted]);self.assertEqual(client.input['runtime'],{'provider':'codex','model':'test-model'})
        self.assertEqual(client.input['history'],[{'title':'이전 주제'}]);generate.assert_called_once_with('server-owned prompt')
    def test_research_workflow_is_explicit_opt_in(self):
        client=Mock();client.discover.return_value={'state':'complete','candidates':[{'decision':'accepted'}]}
        for workflow in ('','research-v2'):
            with patch.dict(os.environ,{'DISCOVERY_WORKFLOW':workflow}):
                shared.discover('테크',client=client,generator=Mock(),check=Mock())
            sent=client.discover.call_args.args[0]
            self.assertEqual(sent.get('workflow'),workflow or None)
    def test_failed_verification_never_falls_back(self):
        client=Mock();client.discover.return_value={'state':'held','candidates':[]}
        with self.assertRaisesRegex(RuntimeError,'no_verified_topics'):shared.discover('테크',client=client,generator=Mock(),check=Mock())
    def test_connection_setting_change_blocks_completion(self):
        class Client:
            def discover(self,input,**options):
                os.environ['BLOG_CODEX_MODEL']='other-model'
                options['assert_connection'](input['runtime'])
        with self.assertRaisesRegex(RuntimeError,'connection_changed'):shared.discover('리뷰',client=Client(),generator=Mock(),check=Mock())
    def test_native_draft_disables_search_and_tools_in_spawn_arguments(self):
        import tempfile
        from pathlib import Path
        from src.codex_client import CodexSubscriptionClient
        def launch(command, **options):
            self.assertIn('web_search="disabled"',command)
            for feature in ('shell_tool','apps','multi_agent','computer_use','browser_use','image_generation'):
                self.assertIn(f'features.{feature}=false',command)
            self.assertNotIn('--search',command)
            self.assertIn('--ignore-user-config',command)
            output=Path(command[command.index('--output-last-message')+1])
            process=Mock(returncode=0)
            process.communicate.side_effect=lambda *a,**k: output.write_text('{"candidates":[]}')
            return process
        with tempfile.TemporaryDirectory() as home, patch('src.codex_client.require_private_actions'), patch('src.codex_client.shutil.which',return_value='/synthetic/codex'), patch('src.codex_client.subprocess.Popen',side_effect=launch) as spawn:
            native=CodexSubscriptionClient(home=home)
            self.assertEqual(native.generate('server evidence',draft_only=True),'{"candidates":[]}')
            spawn.assert_called_once()
        class Client:
            def discover(self,input,**options):
                options['generate']('server draft')
                return {'state':'complete','candidates':[{'decision':'accepted'}]}
        with patch('src.codex_client.CodexSubscriptionClient') as factory:
            factory.return_value.generate.return_value='{"candidates":[]}'
            shared.discover('테크',client=Client(),check=Mock())
            factory.return_value.generate.assert_called_once_with('server draft',draft_only=True)
    def test_unverified_related_keywords_cannot_enter_market_pool(self):
        from src import market_topics as market
        observed=[]
        class Stop(Exception):pass
        def inspect(stats,*args):
            observed.extend(stats);raise Stop()
        approved=[{'keyword':'검증키워드','title':'검증주제','decision':'accepted'}]
        with patch.object(shared,'discover',return_value=(approved,{'requestId':'r'})), patch.object(market,'demand_candidates',return_value={'검증키워드':{'keyword':'검증키워드','monthly':500},'새관련키워드':{'keyword':'새관련키워드','monthly':9000}}), patch.object(market,'_selection_pool',side_effect=inspect), patch.object(market,'discover_youtube') as youtube, patch.object(market,'merge_cak_candidates') as cak:
            with self.assertRaises(Stop):market.select_category('테크',titles=[])
            self.assertEqual(observed,['검증키워드']);youtube.assert_not_called();cak.assert_not_called()
if __name__=='__main__':unittest.main()
