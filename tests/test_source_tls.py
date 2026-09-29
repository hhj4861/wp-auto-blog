"""TLS completion retains trust-root and hostname verification (offline tests)."""
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
import ssl
import subprocess
from threading import Thread
from unittest.mock import Mock

import certifi
import pytest
import requests

from src import source_tls as tls


def test_bundled_intermediate_is_pinned_and_chains_to_existing_roots():
    pem = tls.INTERMEDIATE.read_text()
    assert sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest() == tls.FINGERPRINT
    result = subprocess.run(['openssl', 'verify', '-CAfile', certifi.where(), str(tls.INTERMEDIATE)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    context = tls.verified_context()
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN


def test_unknown_hosts_use_ordinary_verification_without_scoped_adapter(monkeypatch):
    get = Mock()
    monkeypatch.setattr(tls.requests, 'get', get)
    for host in ('www.kca.go.kr.evil.example', 'other.kca.go.kr', 'www.samsung.com'):
        tls.get('https://' + host + '/info', timeout=3)
        get.assert_called_with('https://' + host + '/info', timeout=3)


def test_corrupt_intermediate_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / 'wrong.pem'
    path.write_text(tls.INTERMEDIATE.read_text())
    tls.verified_context.cache_clear()
    monkeypatch.setattr(tls, 'FINGERPRINT', '0' * 64)
    monkeypatch.setattr(tls, 'INTERMEDIATE', path)
    with pytest.raises(requests.exceptions.SSLError):
        tls.verified_context()
    tls.verified_context.cache_clear()


@pytest.fixture(scope='module')
def certificate_chain(tmp_path_factory):
    """Server deliberately sends only its leaf, matching the observed KCA fault."""
    root = tmp_path_factory.mktemp('test-certificates')
    def run(*args):
        subprocess.run(['openssl', *args], cwd=root, check=True, capture_output=True)
    run('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
        '-subj', '/CN=Test Root', '-keyout', 'root.key', '-out', 'root.pem')
    for name in ('intermediate', 'leaf'):
        run('req', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=' + name,
            '-keyout', name + '.key', '-out', name + '.csr')
    (root / 'intermediate.ext').write_text('basicConstraints=critical,CA:TRUE,pathlen:0\nkeyUsage=critical,keyCertSign,cRLSign\n')
    (root / 'leaf.ext').write_text('basicConstraints=critical,CA:FALSE\nsubjectAltName=DNS:localhost\nextendedKeyUsage=serverAuth\n')
    for name, issuer in (('intermediate', 'root'), ('leaf', 'intermediate')):
        run('x509', '-req', '-in', name + '.csr', '-CA', issuer + '.pem',
            '-CAkey', issuer + '.key', '-CAcreateserial', '-days', '1',
            '-extfile', name + '.ext', '-out', name + '.pem')
    return root


@pytest.mark.parametrize('trusted_root,hostname,success', [
    (True, 'localhost', True), (True, '127.0.0.1', False), (False, 'localhost', False),
])
def test_missing_intermediate_recovered_but_wrong_host_and_untrusted_root_rejected(
        certificate_chain, monkeypatch, trusted_root, hostname, success):
    root = certificate_chain
    real_bundle = certifi.where()
    monkeypatch.setattr(tls.certifi, 'where', lambda: str(root / 'root.pem') if trusted_root else real_bundle)
    monkeypatch.setattr(tls, 'INTERMEDIATE', root / 'intermediate.pem')
    monkeypatch.setattr(tls, 'FINGERPRINT', sha256(ssl.PEM_cert_to_DER_cert(tls.INTERMEDIATE.read_text())).hexdigest())
    monkeypatch.setattr(tls, 'HOSTS', {'localhost', '127.0.0.1'})
    monkeypatch.setenv('NO_PROXY', 'localhost,127.0.0.1')
    tls.verified_context.cache_clear()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'verified')
        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(root / 'leaf.pem', root / 'leaf.key')
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f'https://{hostname}:{server.server_port}/'
        if success:
            assert tls.get(url, timeout=3, allow_redirects=False).text == 'verified'
        else:
            with pytest.raises(requests.exceptions.SSLError):
                tls.get(url, timeout=3, allow_redirects=False)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        tls.verified_context.cache_clear()
