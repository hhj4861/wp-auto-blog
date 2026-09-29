"""Complete KCA's missing intermediate chain without weakening TLS validation.

The bundled intermediate is signed by a root already in certifi. It is never
used as a partial-chain trust anchor. No network certificate discovery occurs.
"""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import ssl
from urllib.parse import urlsplit

import certifi
import requests
from requests.adapters import HTTPAdapter

INTERMEDIATE = Path(__file__).resolve().parents[1] / 'assets/certs/sectigo-dv-r36.pem'
FINGERPRINT = '8c54c334b66ba4e426772af4a3f9136c19a1aec729fdb28c535c07a5a4ef22e0'
HOSTS = frozenset({'www.kca.go.kr', 'kca.go.kr'})


@lru_cache(maxsize=1)
def verified_context():
    try:
        pem = INTERMEDIATE.read_text(encoding='ascii')
        if sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest() != FINGERPRINT:
            raise ValueError('Unexpected intermediate certificate')
        context = ssl.create_default_context(cafile=certifi.where())
        context.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
        context.load_verify_locations(cadata=pem)
        return context
    except (OSError, ValueError, ssl.SSLError) as error:
        raise requests.exceptions.SSLError('Verified intermediate unavailable') from error


class _ChainAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = verified_context()
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **kwargs):
        kwargs['ssl_context'] = verified_context()
        return super().proxy_manager_for(proxy, **kwargs)


def get(url, **kwargs):
    if urlsplit(url).hostname not in HOSTS:
        return requests.get(url, **kwargs)
    with requests.Session() as session:
        session.mount('https://', _ChainAdapter())
        # A file path avoids Requests replacing the adapter's context with its
        # preloaded context. Certificate/hostname/time validation remain enabled.
        return session.get(url, verify=certifi.where(), **kwargs)
