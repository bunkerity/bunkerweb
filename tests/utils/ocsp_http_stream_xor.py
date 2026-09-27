#!/usr/bin/env python3
"""
Compare OCSP staple outcomes on the HTTP listener vs the stream listener.

Pages (non-zero exit / should_page=True) only on XOR:
  - exactly one of the two handshakes receives a staple, or
  - both staple but sha256(DER) differs.

Both absent or both present with the same digest stay quiet. Absolute "no
staple" is already visible via Must-Staple / client errors; this probe is for
HTTP (ssl-certificate-lua.conf) vs stream (bunkerweb.ocsp) drift.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import select
import socket
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class StapleOutcome:
    has_staple: bool
    der_sha256: Optional[str]  # lowercase hex when a staple was received

    def normalized_sha(self) -> Optional[str]:
        if not self.has_staple or not self.der_sha256:
            return None
        return self.der_sha256.lower()


def xor_outcomes(http: StapleOutcome, stream: StapleOutcome) -> bool:
    """True when HTTP and stream disagree (page). Quiet when both agree."""
    if http.has_staple != stream.has_staple:
        return True
    if http.has_staple and stream.has_staple:
        return http.normalized_sha() != stream.normalized_sha()
    return False


def fetch_ocsp_staple(
    host: str,
    port: int = 443,
    sni: Optional[str] = None,
    timeout: float = 10.0,
) -> StapleOutcome:
    """
    TLS client handshake that requests status_request and returns the OCSP
    staple DER digest when the server sends one. No PEM files under /tmp.
    """
    sni = sni or host
    try:
        from cryptography.hazmat.bindings.openssl.binding import Binding
    except ImportError as exc:  # pragma: no cover - cryptography is a project dep
        raise RuntimeError("cryptography is required to fetch OCSP staples") from exc

    binding = Binding()
    lib, ffi = binding.lib, binding.ffi

    method = lib.TLS_client_method()
    ctx = lib.SSL_CTX_new(method)
    if ctx == ffi.NULL:
        raise RuntimeError("SSL_CTX_new failed")
    sock = None
    ssl = None
    try:
        lib.SSL_CTX_set_verify(ctx, lib.SSL_VERIFY_NONE, ffi.NULL)
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.setblocking(False)
        ssl = lib.SSL_new(ctx)
        if ssl == ffi.NULL:
            raise RuntimeError("SSL_new failed")
        lib.SSL_set_fd(ssl, sock.fileno())
        # Binding may expose these as macros that return None; ignore return value.
        lib.SSL_set_tlsext_host_name(ssl, sni.encode("idna"))
        status_ok = lib.SSL_set_tlsext_status_type(ssl, lib.TLSEXT_STATUSTYPE_ocsp)
        if status_ok is not None and status_ok != 1:
            raise RuntimeError("SSL_set_tlsext_status_type failed")
        lib.SSL_set_connect_state(ssl)

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ret = lib.SSL_do_handshake(ssl)
            if ret == 1:
                break
            err = lib.SSL_get_error(ssl, ret)
            remaining = max(0.0, deadline - time.monotonic())
            if err == lib.SSL_ERROR_WANT_READ:
                select.select([sock], [], [], remaining)
            elif err == lib.SSL_ERROR_WANT_WRITE:
                select.select([], [sock], [], remaining)
            else:
                raise RuntimeError(f"TLS handshake failed SSL_get_error={err}")
        else:
            raise TimeoutError(f"TLS handshake timed out for {sni}@{host}:{port}")

        resp_ptr = ffi.new("unsigned char **")
        length = lib.SSL_get_tlsext_status_ocsp_resp(ssl, resp_ptr)
        if length is None or length <= 0 or resp_ptr[0] == ffi.NULL:
            return StapleOutcome(has_staple=False, der_sha256=None)
        der = bytes(ffi.buffer(resp_ptr[0], length))
        return StapleOutcome(has_staple=True, der_sha256=hashlib.sha256(der).hexdigest().lower())
    finally:
        if ssl is not None and ssl != ffi.NULL:
            lib.SSL_free(ssl)
        if ctx != ffi.NULL:
            lib.SSL_CTX_free(ctx)
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass


def probe_http_stream(
    sni: str,
    http_host: str,
    http_port: int,
    stream_host: str,
    stream_port: int,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """Run both handshakes and report whether on-call should page."""
    http = fetch_ocsp_staple(http_host, http_port, sni=sni, timeout=timeout)
    stream = fetch_ocsp_staple(stream_host, stream_port, sni=sni, timeout=timeout)
    page = xor_outcomes(http, stream)
    reason = "ok"
    if page:
        if http.has_staple != stream.has_staple:
            reason = "presence_xor"
        else:
            reason = "der_sha256_mismatch"
    return {
        "sni": sni,
        "http": {"host": http_host, "port": http_port, **asdict(http)},
        "stream": {"host": stream_host, "port": stream_port, **asdict(stream)},
        "should_page": page,
        "reason": reason,
    }


def _self_test() -> None:
    quiet_pairs = [
        (StapleOutcome(False, None), StapleOutcome(False, None)),
        (StapleOutcome(True, "a" * 64), StapleOutcome(True, "a" * 64)),
        (StapleOutcome(True, "A" * 64), StapleOutcome(True, "a" * 64)),  # case-insensitive
    ]
    page_pairs = [
        (StapleOutcome(True, "a" * 64), StapleOutcome(False, None)),
        (StapleOutcome(False, None), StapleOutcome(True, "a" * 64)),
        (StapleOutcome(True, "a" * 64), StapleOutcome(True, "b" * 64)),
        (StapleOutcome(True, None), StapleOutcome(True, "a" * 64)),  # missing hash vs set
    ]
    for http, stream in quiet_pairs:
        assert not xor_outcomes(http, stream), (http, stream)
    for http, stream in page_pairs:
        assert xor_outcomes(http, stream), (http, stream)

    # Live smoke: a public host known to staple (best-effort; skip if unreachable).
    try:
        outcome = fetch_ocsp_staple("www.digicert.com", 443, sni="www.digicert.com", timeout=15.0)
    except Exception as exc:  # pragma: no cover
        print(f"self-test: skip live fetch ({exc})", file=sys.stderr)
    else:
        assert outcome.has_staple is True
        assert outcome.der_sha256 and len(outcome.der_sha256) == 64
        # Same endpoint twice must not XOR.
        assert not xor_outcomes(outcome, outcome)

    print("self-test: ok")


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="Run unit checks and exit")
    parser.add_argument("--sni", help="SNI / server name for both handshakes")
    parser.add_argument("--http-host", default="127.0.0.1", help="HTTP TLS listener host")
    parser.add_argument("--http-port", type=int, default=443, help="HTTP TLS listener port")
    parser.add_argument("--stream-host", default=None, help="Stream TLS listener host (default: http-host)")
    parser.add_argument("--stream-port", type=int, default=None, help="Stream TLS listener port")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--json", action="store_true", help="Print result as JSON")
    args = parser.parse_args(argv)

    if args.self_test:
        _self_test()
        return 0

    if not args.sni or args.stream_port is None:
        parser.error("--sni and --stream-port are required (or use --self-test)")

    stream_host = args.stream_host or args.http_host
    result = probe_http_stream(
        sni=args.sni,
        http_host=args.http_host,
        http_port=args.http_port,
        stream_host=stream_host,
        stream_port=args.stream_port,
        timeout=args.timeout,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"sni={result['sni']} http_staple={result['http']['has_staple']} "
            f"stream_staple={result['stream']['has_staple']} "
            f"http_sha={(result['http']['der_sha256'] or '-')[:16]} "
            f"stream_sha={(result['stream']['der_sha256'] or '-')[:16]} "
            f"should_page={result['should_page']} reason={result['reason']}"
        )
    return 1 if result["should_page"] else 0


if __name__ == "__main__":
    sys.exit(main())
