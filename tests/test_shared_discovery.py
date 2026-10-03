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
    def test_failed_verification_never_falls_back(self):
        client=Mock();client.discover.return_value={'state':'held','candidates':[]}
        with self.assertRaisesRegex(RuntimeError,'no_verified_topics'):shared.discover('테크',client=client,generator=Mock(),check=Mock())
    def test_connection_setting_change_blocks_completion(self):
        class Client:
            def discover(self,input,**options):
                os.environ['BLOG_CODEX_MODEL']='other-model'
                options['assert_connection'](input['runtime'])
        with self.assertRaisesRegex(RuntimeError,'connection_changed'):shared.discover('리뷰',client=Client(),generator=Mock(),check=Mock())
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
