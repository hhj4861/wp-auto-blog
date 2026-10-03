"""Backend-only HTTP adapter. All discovery/review policy lives on the shared server."""
import json
import re
from urllib.parse import urlsplit, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError

class DiscoveryError(RuntimeError):
    pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None
class DiscoveryClient:
    def __init__(self, base_url, api_key, subject, *, allow_localhost=False):
        u = urlsplit(base_url)
        if (u.username or u.password or u.query or u.fragment or not (u.scheme == 'https' or allow_localhost and u.scheme == 'http' and u.hostname in ('localhost','127.0.0.1','::1')) or len(api_key) < 32 or '\n' in api_key or '\r' in api_key or not re.fullmatch('[a-f0-9]{64}',subject)):
            raise DiscoveryError('discovery_not_configured')
        self.base, self.key, self.subject = base_url.rstrip('/'), api_key, subject
    def request(self, path, value=None, key=None):
        headers={'Authorization':'Bearer '+self.key,'X-Discovery-Subject':self.subject,'Content-Type':'application/json'}
        if key: headers['Idempotency-Key']=key
        request=Request(self.base+path, data=None if value is None else json.dumps(value,ensure_ascii=False,allow_nan=False).encode(),headers=headers)
        try:
            with build_opener(NoRedirect()).open(request,timeout=120) as response:
                raw=response.read(2097153)
            if len(raw)>2097152: raise ValueError()
            result=json.loads(raw)
            if not isinstance(result,dict) or not isinstance(result.get('candidates'),list) or not isinstance(result.get('evidence'),list) or not isinstance(result.get('requestId'),str): raise ValueError()
            return result
        except HTTPError as exc:
            code='discovery_unavailable'
            try:
                error=json.loads(exc.read(1000)).get('error','')
                if re.fullmatch('[a-z_]{1,80}',error): code=error
            except Exception: pass
            exc.close()
            raise DiscoveryError(code) from None
        except Exception:
            raise DiscoveryError('discovery_unavailable') from None
    def discover(self,input,*,idempotency_key,generate,assert_connection):
        assert_connection(input['runtime'])
        result=self.request('/v1/discover',input,idempotency_key)
        stages=('research','draft') if input.get('workflow')=='research-v2' else (None,)
        seen=set()
        if result['state'] in ('complete','held'):return result
        if result['state']!='awaiting_generation':raise DiscoveryError('discovery_in_progress')
        try: offset=stages.index(result.get('action',{}).get('stage'))
        except (ValueError,AttributeError):raise DiscoveryError('invalid_generation_action') from None
        for index in range(offset,len(stages)):
            stage=stages[index]
            if result['state'] in ('complete','held'): return result
            if result['state']!='awaiting_generation': raise DiscoveryError('discovery_in_progress')
            path='/v1/discover/'+quote(result['requestId'],safe='')
            action=result.get('action')
            if not isinstance(action,dict) or not isinstance(action.get('id'),str) or action['id'] in seen or action.get('stage')!=stage or action.get('runtime')!=input['runtime'] or not isinstance(action.get('prompt'),str) or len(action['prompt'])>350000 or (input.get('workflow')=='research-v2' and result.get('usage',{}).get('generationClaims')!=index): raise DiscoveryError('invalid_generation_action')
            assert_connection(input['runtime'])
            result=self.request(path+'/claim',{'actionId':action['id']})
            if result.get('state')!='generating' or result.get('action')!=action or (input.get('workflow')=='research-v2' and result.get('usage',{}).get('generationClaims')!=index+1):raise DiscoveryError('invalid_generation_action')
            seen.add(action['id'])
            assert_connection(input['runtime'])
            try: output=generate(action['prompt'])
            except Exception:
                try: self.request(path+'/complete',{'actionId':action['id'],'runtime':input['runtime'],'generationError':True})
                except Exception: pass
                raise DiscoveryError('generation_failed') from None
            assert_connection(input['runtime'])
            result=self.request(path+'/complete',{'actionId':action['id'],'runtime':input['runtime'],'output':output})
        if result['state'] not in ('complete','held'): raise DiscoveryError('discovery_step_limit')
        return result
