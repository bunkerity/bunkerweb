"""A local HTTP and HTTPS file server for the URL-download jobs, so no test touches the internet.

``url_server`` serves ``routes`` (path -> ``(status, body, headers)``) on 127.0.0.1 over plain HTTP
and over HTTPS with a throwaway self-signed certificate. ``requests`` is pointed at that certificate
through ``REQUESTS_CA_BUNDLE``, so the HTTPS path runs with certificate verification ON, exactly as
the jobs do in production. A body given as a list is sent chunked, with no Content-Length.
A route may also be a callable taking the request headers and returning that tuple.
"""

import ssl
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address

import pytest

# Imported here, at collection, before tests/unit/plugins_download is collected. That module loads the
# download jobs inside patch.dict(sys.modules), which on exit evicts every module first imported inside
# it -- http.cookiejar among them -- while the surviving `http` package keeps its attribute pointing at
# the evicted copy. A requests imported after that binds two different CookieJar classes and every
# request fails with "You can only merge into CookieJar".
import requests  # noqa: F401
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def _self_signed(tmp_path):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.IPAddress(ip_address("127.0.0.1"))]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "server.crt", tmp_path / "server.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return cert_path, key_path


class UrlServer:
    def __init__(self, tmp_path):
        self.routes = {}
        self.hits = []
        routes, hits = self.routes, self.hits

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 -- http.server's naming
                hits.append(self.path)
                route = routes.get(self.path, (404, b"not found", {}))
                status, body, headers = route(self.headers) if callable(route) else route
                self.send_response(status)
                for header, value in headers.items():
                    self.send_header(header, value)
                if isinstance(body, list):
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    for chunk in body:
                        self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                    self.wfile.write(b"0\r\n\r\n")
                    return
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        Handler.protocol_version = "HTTP/1.1"
        self._http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._https = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.cert_path, key_path = _self_signed(tmp_path)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert_path, key_path)
        self._https.socket = context.wrap_socket(self._https.socket, server_side=True)
        for server in (self._http, self._https):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    def http(self, path):
        return f"http://127.0.0.1:{self._http.server_address[1]}{path}"

    def https(self, path):
        return f"https://127.0.0.1:{self._https.server_address[1]}{path}"

    def close(self):
        for server in (self._http, self._https):
            server.shutdown()
            server.server_close()


@pytest.fixture
def url_server(tmp_path, monkeypatch):
    server = UrlServer(tmp_path)
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(server.cert_path))
    for proxy in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(proxy, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    try:
        yield server
    finally:
        server.close()
