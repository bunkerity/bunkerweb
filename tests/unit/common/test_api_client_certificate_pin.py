"""The API client pins the certificate of the instances' HTTPS API instead of trusting any.

`API.request` called the instances with ``verify=False`` and nothing else, so whoever answered on
the HTTPS port was believed, bearer token included. The api-server-cert job generates the
certificate the instances serve and the scheduler restores it on disk (the web UI, the API service
and bwcli read it from the database job cache), so the client knows exactly what to expect. It pins
the SHA-256 fingerprint, because the instances are reached by IP, service name or pod name and a
hostname check cannot work.

A mismatch still retries over HTTP, as before, with a warning. Every test here handshakes with a
real local TLS server, so the pin is checked by urllib3 and not by a mock.
"""

import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from select import select
from socket import MSG_PEEK, create_connection
from socketserver import BaseRequestHandler, ThreadingTCPServer
from ssl import PROTOCOL_TLS_SERVER, SSLContext
from threading import Thread

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[3]
for _p in (ROOT / "src" / "common" / "api", ROOT / "src" / "common" / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import API as api_module  # noqa: E402
from API import API  # noqa: E402


def _make_cert(directory: Path, name: str):
    """A self-signed certificate the way the job makes one: a name nobody connects to."""
    key = ec.generate_private_key(ec.SECP384R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "www.example.org")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("www.example.org")]), critical=False)
        .sign(key, hashes.SHA512())
    )
    cert_path, key_path = directory / f"{name}.pem", directory / f"{name}.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return cert_path, key_path


class _Handler(BaseHTTPRequestHandler):
    scheme = "plain"

    def do_GET(self):
        self.server.hits.append(self.scheme)  # type: ignore[attr-defined]
        body = b'{"status": "success"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _Server(ThreadingHTTPServer):
    """Answers TLS and plain HTTP on one port, the way an instance does when the retry lands on it.

    The first byte tells them apart: a TLS ClientHello starts with 0x16.
    """

    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.context = SSLContext(PROTOCOL_TLS_SERVER)
        self.hits = []

    def handle_error(self, request, client_address):
        pass  # a client dropping the connection on a refused pin is expected, not a traceback

    def serve(self, cert):
        self.context.load_cert_chain(*cert)

    def finish_request(self, request, client_address):
        try:
            tls = request.recv(1, MSG_PEEK) == b"\x16"
            if tls:
                request = self.context.wrap_socket(request, server_side=True)
        except OSError:
            return  # a client that walked away mid-handshake is what a refused pin looks like from here
        type("_Tagged", (_Handler,), {"scheme": "tls" if tls else "plain"})(request, client_address, self)


@pytest.fixture()
def certs(tmp_path):
    return {name: _make_cert(tmp_path, name) for name in ("a", "b", "c")}


@pytest.fixture()
def server(certs):
    srv = _Server()
    srv.serve(certs["a"])
    thread = Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()


class _Logger:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


@pytest.fixture()
def pin(tmp_path, monkeypatch):
    """The pin source pointed at a temp file, with every read trusted for no time at all."""
    monkeypatch.setattr(api_module, "API_SERVER_CERT", tmp_path / "api-server-cert.pem", raising=False)
    monkeypatch.setattr(api_module, "_PIN_TTL", 0.0, raising=False)
    monkeypatch.setattr(api_module, "_PIN_FORCED_TTL", 0.0, raising=False)
    state = getattr(api_module, "_PIN", None)
    if state is not None:
        monkeypatch.setattr(state, "fingerprints", [])
        monkeypatch.setattr(state, "checked", float("-inf"))
        monkeypatch.setattr(state, "warned", False)
        monkeypatch.setattr(state, "loader", None)
    return tmp_path / "api-server-cert.pem"


@pytest.fixture()
def logger(monkeypatch):
    log = _Logger()
    monkeypatch.setattr(api_module, "getLogger", lambda *args, **kwargs: log)
    return log


def _call(server, scheme="https", **kwargs):
    return API(f"{scheme}://127.0.0.1:{server.server_address[1]}", token="t").request("GET", "ping", **kwargs)


def _publish(pin, certs, name):
    pin.write_bytes(certs[name][0].read_bytes())


def test_the_pinned_certificate_is_accepted(server, certs, pin, logger):
    _publish(pin, certs, "a")

    ok, _, status, body = _call(server)

    assert (ok, status, body) == (True, 200, {"status": "success"})
    assert server.hits == ["tls"]
    assert logger.warnings == []


def test_another_certificate_is_refused_and_the_call_falls_back_to_http(server, certs, pin, logger):
    _publish(pin, certs, "a")
    server.serve(certs["b"])

    ok, _, status, _ = _call(server)

    assert (ok, status) == (True, 200)
    assert server.hits == ["plain"], "the TLS attempt must not reach the handler, only the plain retry"
    assert len(logger.warnings) == 1
    assert "did not match the pinned API server certificate" in logger.warnings[0]
    assert f"127.0.0.1:{server.server_address[1]}" in logger.warnings[0], "the warning names the instance"


def test_a_renewal_is_picked_up_without_a_restart(server, certs, pin, logger):
    _publish(pin, certs, "a")
    assert _call(server)[0] and server.hits == ["tls"]

    # The scheduler renews first: the file holds B while the instance still serves A.
    _publish(pin, certs, "b")
    assert _call(server)[0] and server.hits == ["tls", "tls"], "the previous certificate stays accepted"

    # The instance catches up.
    server.serve(certs["b"])
    assert _call(server)[0] and server.hits == ["tls", "tls", "tls"]
    assert logger.warnings == []

    # Only the current and the previous one are accepted, so a third certificate is refused.
    server.serve(certs["c"])
    assert _call(server)[0] and server.hits[-1] == "plain"
    assert "did not match" in logger.warnings[0]


def test_an_instance_ahead_of_the_last_read_is_followed(server, certs, pin, logger, monkeypatch):
    monkeypatch.setattr(api_module, "_PIN_TTL", 1000.0, raising=False)
    _publish(pin, certs, "a")
    assert _call(server)[0] and server.hits == ["tls"]

    # The file moved and the instance with it, but the last read is still trusted: a mismatch re-reads.
    _publish(pin, certs, "b")
    server.serve(certs["b"])
    assert _call(server)[0] and server.hits == ["tls", "tls"]
    assert logger.warnings == []

    # A certificate that is nowhere in the source stays refused after that re-read.
    server.serve(certs["c"])
    assert _call(server)[0] and server.hits[-1] == "plain"
    assert len(logger.warnings) == 1


def test_without_a_pinned_certificate_the_call_goes_through_as_before(server, certs, pin, logger):
    server.serve(certs["b"])

    assert _call(server)[0] and _call(server)[0]

    assert server.hits == ["tls", "tls"], "no certificate to pin: HTTPS is still used and not downgraded"
    assert len(logger.warnings) == 1, "one warning per process, not one per call"
    assert "No API server certificate to pin" in logger.warnings[0]


def test_the_database_supplies_the_certificate_when_there_is_no_file(server, certs, pin, logger):
    class _Db:
        def get_job_cache_file(self, job_name, file_name, *, plugin_id=""):
            assert (job_name, file_name, plugin_id) == ("api-server-cert", "api-server-cert.pem", "jobs")
            return certs["a"][0].read_bytes()

    API.pin_from_database(_Db())

    assert _call(server)[0] and server.hits == ["tls"]

    server.serve(certs["b"])
    assert _call(server)[0] and server.hits[-1] == "plain"
    assert "did not match" in logger.warnings[0]


def test_an_http_endpoint_does_not_touch_the_pin(server, certs, pin, logger):
    server.serve(certs["b"])
    _publish(pin, certs, "a")

    assert _call(server, "http")[0]

    assert server.hits == ["plain"]
    assert logger.warnings == []


class _ConnectProxy(ThreadingTCPServer):
    """A CONNECT tunnel: it relays bytes and never looks inside, as a forward proxy does for HTTPS."""

    daemon_threads = True
    allow_reuse_address = True

    class Handler(BaseRequestHandler):
        def handle(self):
            head = b""
            while b"\r\n\r\n" not in head:
                chunk = self.request.recv(4096)
                if not chunk:
                    return
                head += chunk
            method, target, _ = head.split(b"\r\n", 1)[0].split(b" ")
            if method != b"CONNECT":
                return
            self.server.connects.append(target.decode())  # type: ignore[attr-defined]
            host, port = target.decode().rsplit(":", 1)
            with create_connection((host, int(port))) as upstream:
                self.request.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
                sockets = [self.request, upstream]
                while True:
                    ready, _, _ = select(sockets, [], [], 5)
                    if not ready:
                        return
                    for sock in ready:
                        data = sock.recv(65536)
                        if not data:
                            return
                        (upstream if sock is self.request else self.request).sendall(data)

    def __init__(self):
        super().__init__(("127.0.0.1", 0), self.Handler)
        self.connects = []


@pytest.fixture()
def proxy(monkeypatch):
    """HTTPS_PROXY pointed at a local tunnel; the instance is 127.0.0.1, so NO_PROXY must be empty."""
    srv = _ConnectProxy()
    Thread(target=srv.serve_forever, daemon=True).start()
    for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HTTPS_PROXY", f"http://127.0.0.1:{srv.server_address[1]}")
    yield srv
    srv.shutdown()
    srv.server_close()


def test_the_pin_holds_through_a_proxy(server, certs, pin, logger, proxy):
    _publish(pin, certs, "a")

    assert _call(server)[0]
    assert proxy.connects == [f"127.0.0.1:{server.server_address[1]}"], "the call must have gone through the tunnel"
    assert server.hits == ["tls"]
    assert logger.warnings == []


def test_another_certificate_is_refused_through_a_proxy(server, certs, pin, logger, proxy):
    _publish(pin, certs, "a")
    server.serve(certs["b"])

    assert _call(server)[0]
    assert proxy.connects, "the TLS attempt must have gone through the tunnel"
    assert server.hits == ["plain"], "the TLS attempt must not reach the handler, only the plain retry"
    assert len(logger.warnings) == 1
    assert "did not match the pinned API server certificate" in logger.warnings[0]


def test_the_pin_holds_with_a_write_timeout(server, certs, pin, logger):
    _publish(pin, certs, "a")

    assert _call(server, write_timeout=5)[0]
    assert server.hits == ["tls"]
    assert logger.warnings == []


def test_another_certificate_is_refused_with_a_write_timeout(server, certs, pin, logger):
    _publish(pin, certs, "a")
    server.serve(certs["b"])

    ok, _, status, _ = _call(server, write_timeout=5)

    assert (ok, status) == (True, 200)
    assert server.hits == ["plain"], "the TLS attempt must not reach the handler, only the plain retry"
    assert len(logger.warnings) == 1
    assert "did not match the pinned API server certificate" in logger.warnings[0]


def test_the_pin_holds_with_a_write_timeout_through_a_proxy(server, certs, pin, logger, proxy):
    _publish(pin, certs, "a")
    server.serve(certs["b"])

    assert _call(server, write_timeout=5)[0]
    assert proxy.connects
    assert server.hits == ["plain"]
    assert "did not match the pinned API server certificate" in logger.warnings[0]
