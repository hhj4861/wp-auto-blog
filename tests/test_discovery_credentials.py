import json
from types import SimpleNamespace
import pytest
from scripts.load_discovery_credentials import load, BROKER

KEY = 'fixture_' + 'a' * 40

def environment(tmp_path):
    return {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'hhj4861/wp-auto-blog',
            'GITHUB_REF': 'refs/heads/main', 'GITHUB_ENV': str(tmp_path / 'github-env'),
            'ACTIONS_ID_TOKEN_REQUEST_URL': 'https://unit.actions.githubusercontent.com/idtoken?x=1',
            'ACTIONS_ID_TOKEN_REQUEST_TOKEN': 'runner-token'}

class Http:
    def __init__(self, values=None, status=200):
        self.values = values if values is not None else {'DISCOVERY_BLOG_KEY': KEY}
        self.status = status
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append(('GET', url, kwargs))
        return SimpleNamespace(status_code=200, content=b'jwt', json=lambda: {'value': 'signed-jwt'})
    def post(self, url, **kwargs):
        self.calls.append(('POST', url, kwargs))
        return SimpleNamespace(status_code=self.status, content=b'fixture', json=lambda: {'values': self.values})

def test_load_only_one_scoped_key_and_stable_identity(tmp_path):
    env, http, logs = environment(tmp_path), Http(), []
    load(env, http, logs.append)
    content = (tmp_path / 'github-env').read_text()
    assert f'DISCOVERY_API_KEY={KEY}\n' in content
    assert len(content.split('DISCOVERY_SUBJECT=')[1].strip()) == 64
    assert logs[:2] == ['::add-mask::signed-jwt', '::add-mask::' + KEY]
    assert 'audience=cak-cloudflare-secrets' in http.calls[0][1]
    assert http.calls[1][1] == BROKER + '/github/secrets'
    assert all(c[2]['allow_redirects'] is False for c in http.calls)
    assert 'DISCOVERY_API_KEY' not in env

@pytest.mark.parametrize('values', [{}, {'OTHER_KEY': KEY}, {'DISCOVERY_BLOG_KEY': KEY, 'DISCOVERY_CLI_KEY': KEY}, {'DISCOVERY_BLOG_KEY': 'short'}, {'DISCOVERY_BLOG_KEY': KEY + '\nINJECTED=1'}])
def test_malformed_response_never_writes_env(tmp_path, values):
    with pytest.raises(ValueError):
        load(environment(tmp_path), Http(values), lambda _: None)
    assert not (tmp_path / 'github-env').exists()

@pytest.mark.parametrize('patch', [
    {'GITHUB_REF': 'refs/heads/pr'}, {'GITHUB_REPOSITORY': 'attacker/fork'}, {'GITHUB_ACTIONS': 'false'},
    {'ACTIONS_ID_TOKEN_REQUEST_URL': 'https://actions.githubusercontent.com.evil.test/'},
    {'ACTIONS_ID_TOKEN_REQUEST_URL': 'http://unit.actions.githubusercontent.com/'},
    {'ACTIONS_ID_TOKEN_REQUEST_URL': 'https://user@unit.actions.githubusercontent.com/'},
])
def test_untrusted_runner_and_oidc_urls_make_no_requests(tmp_path, patch):
    http = Http()
    with pytest.raises(ValueError):
        load({**environment(tmp_path), **patch}, http, lambda _: None)
    assert not http.calls

def test_broker_failure_does_not_write_env(tmp_path):
    with pytest.raises(ValueError):
        load(environment(tmp_path), Http(status=503), lambda _: None)
    assert not (tmp_path / 'github-env').exists()
