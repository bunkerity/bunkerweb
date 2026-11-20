#!/usr/bin/env python3
"""IPv6-only upstream, peer echo and deliberately malformed blacklist feed."""

import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/list":
            body = b"fe80::1%eth0\nfd42:1618:2::/64\n"
        elif self.path == "/empty":
            body = b"# empty negative control\n"
        else:
            body = json.dumps({"fixture": "ipv6-only", "peer": self.client_address[0], "xff": self.headers.get("X-Forwarded-For")}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Server(ThreadingHTTPServer):
    address_family = socket.AF_INET6


if __name__ == "__main__":
    Server(("::", 8080), Handler).serve_forever()
