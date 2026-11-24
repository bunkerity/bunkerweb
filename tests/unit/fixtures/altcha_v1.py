"""Local ALTCHA v1 QA service with fixed test credentials and one verifier process."""

import json
from argparse import ArgumentParser
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from ssl import PROTOCOL_TLS_SERVER, SSLContext
from threading import Lock
from time import time
from typing import NamedTuple
from urllib.parse import parse_qs, urlsplit

from altcha.v1 import ChallengeOptions, Payload, create_challenge, verify_solution


class Site(NamedTuple):
    secret: str
    signing_key: str


SITES = {
    "site-a": Site("qa-api-secret-a", "qa-challenge-signing-key-a"),
    "site-b": Site("qa-api-secret-b", "qa-challenge-signing-key-b"),
}


class Verifier:
    def __init__(self, lifetime: timedelta = timedelta(minutes=2)):
        self.lifetime = lifetime
        self.used: dict[str, float] = {}
        self.lock = Lock()

    def challenge(self, site: str) -> dict:
        options = ChallengeOptions(hmac_key=SITES[site].signing_key, expires=datetime.now(UTC) + self.lifetime, max_number=12_000)
        return create_challenge(options).to_dict()

    def verify(self, payload: str, secret: str) -> dict[str, bool | str]:
        denied: dict[str, bool | str] = {"verified": False}
        try:
            secret_bytes = secret.encode()
            site = next((key for key, credentials in SITES.items() if compare_digest(credentials.secret.encode(), secret_bytes)), None)
            if site is None:
                return denied
            proof = Payload.from_base64(payload)
            if not isinstance(proof.salt, str):
                return denied
            verified, _ = verify_solution(proof, SITES[site].signing_key)
            _, expiry, _ = proof.parse_salt()
        except (KeyError, TypeError, ValueError):
            return denied
        if not verified or expiry is None:
            return denied

        with self.lock:
            now = time()
            self.used = {signature: expires for signature, expires in self.used.items() if expires > now}
            if expiry <= now or proof.signature in self.used:
                return denied
            self.used[proof.signature] = expiry
        return {"verified": True, "apiKey": site}


def serve(role: str, host: str, port: int, verifier: Verifier, widget: bytes = b"") -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if role == "public":
                self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            request = urlsplit(self.path)
            if role == "public" and request.path == "/v1/challenge":
                keys = parse_qs(request.query).get("apiKey", [])
                if len(keys) == 1 and keys[0] in SITES:
                    self.respond(200, json.dumps(verifier.challenge(keys[0])).encode(), "application/json")
                    return
            elif role == "public" and request.path == "/assets/altcha.min.js" and widget:
                self.respond(200, widget, "application/javascript")
                return
            elif role == "upstream":
                self.respond(200, b"<!doctype html><html><head><title>Fixture</title></head><body><main id='qa-app'>Fixture</main></body></html>", "text/html")
                return
            self.send_error(404)

        def do_POST(self) -> None:
            if role != "verifier" or self.path != "/v1/verify/signature":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192 or self.headers.get_content_type() != "application/json":
                    raise ValueError
                request = json.loads(self.rfile.read(length))
                payload, secret = request["payload"], request["secret"]
                if not isinstance(payload, str) or not isinstance(secret, str):
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                self.send_error(400)
                return
            self.respond(200, json.dumps(verifier.verify(payload, secret)).encode(), "application/json")

    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("public", "verifier", "upstream"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--widget", type=Path)
    parser.add_argument("--cert", type=Path)
    parser.add_argument("--key", type=Path)
    parser.add_argument("--lifetime-seconds", type=int, default=120)
    args = parser.parse_args()
    if args.role == "public" and not (args.widget and args.cert and args.key):
        parser.error("public requires --widget, --cert and --key")

    widget = args.widget.read_bytes() if args.widget else b""
    verifier = Verifier(timedelta(seconds=args.lifetime_seconds))
    with serve(args.role, args.host, args.port, verifier, widget) as server:
        if args.role == "public":
            tls = SSLContext(PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(args.cert, args.key)
            server.socket = tls.wrap_socket(server.socket, server_side=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
