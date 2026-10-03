"""The blog supplies its existing subscription runtime; selection stays remote."""
import hashlib
import json
import os
import subprocess
from src.shared_discovery_client import DiscoveryClient, DiscoveryError

def enabled():
    return os.environ.get('DISCOVERY_ENABLED') == '1'

def discover(category, titles=(), *, brief=None, client=None, generator=None, check=None):
    from src.codex_client import CodexSubscriptionClient
    request_key=os.environ.get('DISCOVERY_REQUEST_ID') or os.environ.get('GITHUB_RUN_ID')
    if not request_key:
        raise DiscoveryError('discovery_request_id_required')
    home=os.environ.get('BLOG_CODEX_HOME','')
    model=os.environ.get('BLOG_CODEX_MODEL','')
    runtime={'provider':'codex','model':model or 'provider-default'}
    native=None if generator else CodexSubscriptionClient(home=home,model=model,timeout=180)
    def assert_connection(expected):
        if expected != runtime or os.environ.get('BLOG_CODEX_HOME','') != home or os.environ.get('BLOG_CODEX_MODEL','') != model:
            raise DiscoveryError('connection_changed')
        if check:
            check(expected);return
        env={k:os.environ[k] for k in ('PATH','HOME','LANG','SSL_CERT_FILE') if k in os.environ}
        env['CODEX_HOME']=home
        result=subprocess.run(['codex','login','status'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15)
        if result.returncode:raise DiscoveryError('connection_unavailable')
    def generate(prompt):
        value=generator(prompt) if generator else native.generate(prompt)
        return json.loads(value) if isinstance(value,str) else value
    client=client or DiscoveryClient(os.environ.get('DISCOVERY_URL',''),os.environ.get('DISCOVERY_API_KEY',''),os.environ.get('DISCOVERY_SUBJECT',''),allow_localhost=os.environ.get('DISCOVERY_ALLOW_LOCALHOST')=='1')
    result=client.discover({'profile':'content','category':category,
        'brief':brief or '실제 사례와 일상에 도움이 되는 의외의 답을 갖춘 블로그 주제를 찾습니다. 독자는 한국어 사용자입니다. 허위 사용 후기와 효능을 만들지 마세요.',
        'runtime':runtime,'history':[{'title':t[:1000]} for t in list(titles)[-100:] if isinstance(t,str) and t.strip()]},
        idempotency_key='blog-'+hashlib.sha256((request_key+':'+category).encode()).hexdigest(),generate=generate,assert_connection=assert_connection)
    accepted=[c for c in result['candidates'] if c.get('decision')=='accepted']
    if result.get('state')!='complete' or not accepted:
        raise DiscoveryError('no_verified_topics')
    return accepted,result
