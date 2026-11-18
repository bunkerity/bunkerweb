"""The API client retries over plain HTTP only when the peer is not speaking TLS.

S05A-F4: ``API.request`` retried over HTTP, bearer token and archive included, on any ``ConnectionError`` that was not a
pin mismatch, so whoever reset, dropped or let a handshake time out received both in cleartext. The retry is kept for the
one case it exists for, an instance that has no certificate yet and serves plain HTTP on the HTTPS port
(``confs/api.conf``): the TLS handshake then fails because what answers is not TLS. The test instance below behaves like
the real gate: it closes a plain request that carries no bearer token without answering.
"""

import os
import socket
import struct
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from ssl import PROTOCOL_TLS_SERVER, SSLContext
from threading import Event, Lock, Thread

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

ROOT = Path(os.environ.get("BW_C2_SOURCE_ROOT", Path(__file__).resolve().parents[3]))
for _p in (ROOT / "src" / "common" / "api", ROOT / "src" / "common" / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import API as api_module  # noqa: E402
from API import API  # noqa: E402

TOKEN = "secret-bearer-token"
HTTP_ANSWER = b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"


def _make_cert(directory: Path, name: str) -> Path:
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
        .sign(key, hashes.SHA512())
    )
    cert_path = directory / f"{name}.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (directory / f"{name}.key").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return cert_path


class _Instance:
    """One listening port: what a TLS ClientHello gets depends on ``tls_answer``, a plain request on the token check.

    tls_answer: bytes (sent back, then closed), "reset" (RST), "eof" (closed silently), "silent" (held open, never answered).
    """

    def __init__(self, tls_answer):
        self.tls_answer = tls_answer
        self.hellos = 0
        self.plain = []  # (request line, headers, body) of the plain requests that carried the token
        self.untokened = 0
        self.received = bytearray()
        self.lock = Lock()
        self.stop = Event()
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while not self.stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        try:
            conn.settimeout(5)
            head = conn.recv(65536)
            with self.lock:
                self.received += head
            if not head:
                return
            if head[0] == 0x16:  # a TLS ClientHello
                with self.lock:
                    self.hellos += 1
                if isinstance(self.tls_answer, bytes):
                    conn.sendall(self.tls_answer)
                elif self.tls_answer == "reset":
                    conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                elif self.tls_answer == "silent":
                    self.stop.wait(3)
                return
            while b"\r\n\r\n" not in head:
                more = conn.recv(65536)
                if not more:
                    return
                head += more
                with self.lock:
                    self.received += more
            header_block, body = head.split(b"\r\n\r\n", 1)
            lines = header_block.decode().split("\r\n")
            headers = {k.lower(): v.strip() for k, _, v in (line.partition(":") for line in lines[1:])}
            while len(body) < int(headers.get("content-length", 0)):
                more = conn.recv(65536)
                if not more:
                    break
                body += more
                with self.lock:
                    self.received += more
            if headers.get("authorization") != f"Bearer {TOKEN}":
                with self.lock:
                    self.untokened += 1
                return  # the real gate closes the connection (exit(HTTP_CLOSE)) before answering
            with self.lock:
                self.plain.append((lines[0], headers, body))
            payload = b'{"status": "success"}'
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s" % (len(payload), payload))
        except OSError:
            pass
        finally:
            conn.close()

    def close(self):
        self.stop.set()
        self.sock.close()


@pytest.fixture()
def instance_factory():
    made = []

    def make(tls_answer):
        made.append(_Instance(tls_answer))
        return made[-1]

    yield make
    for inst in made:
        inst.close()


class _Logger:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


@pytest.fixture()
def logger(monkeypatch):
    log = _Logger()
    monkeypatch.setattr(api_module, "getLogger", lambda *args, **kwargs: log)
    return log


@pytest.fixture()
def pin(tmp_path, monkeypatch):
    """The pin source pointed at a temp directory, every read trusted for no time at all, a fresh process state."""
    monkeypatch.setattr(api_module, "API_SERVER_CERT", tmp_path / "api-server-cert.pem", raising=False)
    monkeypatch.setattr(api_module, "_PIN_TTL", 0.0, raising=False)
    monkeypatch.setattr(api_module, "_PIN_FORCED_TTL", 0.0, raising=False)
    state = api_module._PIN
    monkeypatch.setattr(state, "fingerprints", [])
    monkeypatch.setattr(state, "checked", float("-inf"))
    monkeypatch.setattr(state, "warned", False)
    monkeypatch.setattr(state, "loader", None)
    return tmp_path


def _api(port):
    return API(f"https://127.0.0.1:{port}", token=TOKEN)


def _tls_never_answered(instance):
    """Nothing but the ClientHello reached the instance: no plain request, so no token on the wire."""
    assert instance.plain == [] and instance.untokened == 0
    assert TOKEN.encode() not in bytes(instance.received)


# ---------------------------------------------------------------- S05A-F4


@pytest.mark.parametrize("answer", [HTTP_ANSWER, b"hello, this is not tls at all\n", b"\x00" * 40], ids=["http-400", "garbage", "zeros"])
def test_a_peer_that_does_not_speak_tls_gets_one_credentialed_http_retry(instance_factory, pin, logger, answer):
    inst = instance_factory(answer)

    ok, _, status, body = _api(inst.port).request("GET", "ping")

    assert (ok, status, body) == (True, 200, {"status": "success"})
    assert inst.hellos == 1
    assert len(inst.plain) == 1, "exactly one HTTP retry"
    assert inst.plain[0][1]["authorization"] == f"Bearer {TOKEN}"
    assert any("trying HTTP" in w for w in logger.warnings)


def test_a_certificate_less_instance_receives_the_retry_and_the_cache_push(instance_factory, pin, logger):
    """The recovery path: the instance only answers once the bearer token is there, as the real gate does."""
    inst = instance_factory(HTTP_ANSWER)
    archive = b"PK-archive-bytes" * 100

    ok, _, status, body = _api(inst.port).request("POST", "cache", data=archive, write_timeout=5)

    assert (ok, status, body) == (True, 200, {"status": "success"})
    assert inst.untokened == 0
    request_line, headers, received = inst.plain[0]
    assert request_line.startswith("POST /cache ")
    assert headers["authorization"] == f"Bearer {TOKEN}"
    assert received == archive


def test_the_retry_also_happens_with_a_pin_when_the_peer_is_not_speaking_tls(instance_factory, pin, logger):
    """An instance restarted without its certificate: the scheduler knows the pin, the peer is still plain HTTP."""
    (pin / "api-server-cert.pem").write_bytes(_make_cert(pin, "a").read_bytes())
    inst = instance_factory(HTTP_ANSWER)

    assert _api(inst.port).request("GET", "ping")[0]
    assert len(inst.plain) == 1


@pytest.mark.parametrize("answer", ["reset", "eof", "silent"])
def test_reset_eof_and_timeout_never_send_the_token_over_http(instance_factory, pin, logger, answer):
    inst = instance_factory(answer)

    ok, err, status, _ = _api(inst.port).request("GET", "ping", timeout=(0.5, 0.5))

    assert (ok, status) == (False, None) and err
    assert inst.hellos == 1
    _tls_never_answered(inst)
    assert not any("trying HTTP" in w for w in logger.warnings)


def test_a_refused_connection_is_not_retried_over_http(instance_factory, pin, logger):
    inst = instance_factory("eof")
    inst.close()

    ok, err, status, _ = _api(inst.port).request("GET", "ping", timeout=(0.5, 0.5))

    assert (ok, status) == (False, None) and err
    assert not any("trying HTTP" in w for w in logger.warnings)


def test_a_tls_alert_is_not_a_plaintext_peer(instance_factory, pin, logger):
    """A TLS alert means the peer does speak TLS: no downgrade."""
    inst = instance_factory(b"\x15\x03\x03\x00\x02\x02\x28")

    ok, err, _, _ = _api(inst.port).request("GET", "ping")

    assert not ok and err
    _tls_never_answered(inst)


class _TlsServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, cert: Path):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.server.hits.append(self.path)  # type: ignore[attr-defined]
                body = b'{"status": "success"}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        super().__init__(("127.0.0.1", 0), Handler)
        self.hits = []
        context = SSLContext(PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, cert.with_suffix(".key"))
        self.socket = context.wrap_socket(self.socket, server_side=True)
        Thread(target=self.serve_forever, daemon=True).start()

    def handle_error(self, request, client_address):
        pass

    def close(self):
        self.shutdown()
        self.server_close()


@pytest.fixture()
def tls_server_factory():
    made = []

    def make(cert):
        made.append(_TlsServer(cert))
        return made[-1]

    yield make
    for server in made:
        server.close()


def test_a_pin_mismatch_is_refused_and_nothing_goes_over_http(tls_server_factory, pin, logger):
    (pin / "api-server-cert.pem").write_bytes(_make_cert(pin, "a").read_bytes())
    server = tls_server_factory(_make_cert(pin, "other"))

    ok, err, _, _ = _api(server.server_address[1]).request("GET", "ping")

    assert not ok and "did not match the pinned API server certificate" in err
    assert server.hits == []
