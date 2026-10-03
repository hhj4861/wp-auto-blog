"""GitHub OIDC -> Cloudflare: only the blog's discovery key, never model tokens."""
import hashlib
import os
from pathlib import Path
import re
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit
import requests

BROKER = 'https://cak-credential-broker.guswhd1085.workers.dev'


def load(env, http=requests, emit=print):
    if env.get('GITHUB_ACTIONS') != 'true' or env.get('GITHUB_REPOSITORY') != 'hhj4861/wp-auto-blog' or env.get('GITHUB_REF') != 'refs/heads/main':
        raise ValueError('trusted_main_runner_required')
    target = env.get('GITHUB_ENV')
    if not target:
        raise ValueError('github_env_required')
    oidc = urlsplit(env.get('ACTIONS_ID_TOKEN_REQUEST_URL', ''))
    if oidc.scheme != 'https' or not oidc.hostname or not oidc.hostname.endswith('.actions.githubusercontent.com') or oidc.username or oidc.password or oidc.fragment or oidc.port not in (None, 443):
        raise ValueError('invalid_oidc_url')
    token = env.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN', '')
    if not token:
        raise ValueError('oidc_unavailable')
    query = [(k, v) for k, v in parse_qsl(oidc.query) if k != 'audience'] + [('audience', 'cak-cloudflare-secrets')]
    url = urlunsplit((oidc.scheme, oidc.netloc, oidc.path, urlencode(query), ''))
    def data(response):
        if response.status_code != 200 or len(response.content) > 16384:
            raise ValueError('credential_request_failed')
        return response.json()
    jwt = data(http.get(url, headers={'authorization': 'Bearer ' + token}, timeout=20, allow_redirects=False)).get('value')
    if not isinstance(jwt, str) or not jwt or len(jwt) > 12000 or '\n' in jwt or '\r' in jwt:
        raise ValueError('invalid_oidc_response')
    # GitHub-only workflow command escaping, before any possible downstream output.
    mask = lambda v: emit('::add-mask::' + v.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A'))
    mask(jwt)
    values = data(http.post(BROKER + '/github/secrets', headers={'authorization': 'Bearer ' + jwt}, json={}, timeout=20, allow_redirects=False)).get('values')
    if not isinstance(values, dict) or set(values) != {'DISCOVERY_BLOG_KEY'}:
        raise ValueError('invalid_discovery_credentials')
    key = values['DISCOVERY_BLOG_KEY']
    if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,1024}', key):
        raise ValueError('invalid_discovery_credentials')
    mask(key)
    subject = hashlib.sha256(b'wp-auto-blog:1126598753:general').hexdigest()
    with Path(target).open('a', encoding='utf-8') as output:
        output.write(f'DISCOVERY_API_KEY={key}\nDISCOVERY_SUBJECT={subject}\n')
    emit('Cloudflare discovery credential loaded (one platform)')


if __name__ == '__main__':
    try:
        load(os.environ)
    except Exception:
        # No upstream body, URL query, key or raw exception in CI logs.
        print('Discovery credential loading failed; recommendation was not started.')
        raise SystemExit(1)
