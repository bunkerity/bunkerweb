#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Unary gRPC probe for `tests/core/grpc.yml`, run from the runner by a `script` action.

There is no gRPC assertion type and no gRPC client in `tests/requirements.txt`, so this speaks
the wire format directly on top of `httpx[http2]`, which the suite already ships. A unary call
is small enough to hand-roll: one length-prefixed message over an HTTP/2 POST whose
`content-type` is `application/grpc`.

Two shapes cover every backend method this spec calls, both from `moul/grpcbin`:

* ``hello.HelloService/SayHello`` takes ``HelloRequest{greeting = 1}`` and answers
  ``HelloResponse{reply = 1}`` = ``"hello " + greeting`` -- one protobuf string field each way,
  which is a two-byte header and the bytes.
* ``grpcbin.GRPCBin/HeadersUnary`` takes an empty message and answers with the request metadata
  it received. Assertions on it are substring matches against the raw response: the map values
  are plain strings in the wire encoding, so a header BunkerWeb added -- or the ``:authority``
  it rewrote -- is literally in the bytes. That is what makes `GRPC_HEADERS` and
  `GRPC_CUSTOM_HOST` observable without a protobuf runtime.

Trailers are deliberately not read: httpx exposes no HTTP/2 trailer API, so `grpc-status` is out
of reach. It is not needed -- a failed RPC answers trailers-only with an empty body, so every
`--expect` on the reply is already the success check.
"""

from argparse import ArgumentParser
from struct import pack
from sys import exit as sys_exit
from time import monotonic

import httpx


def protobuf_string(field: int, value: str) -> bytes:
    """A single length-delimited protobuf field. Values here are short, so the length is 1 byte."""
    raw = value.encode()
    if len(raw) > 127:
        raise ValueError("probe messages are short on purpose; a multi-byte varint length is not implemented")
    return bytes([field << 3 | 2, len(raw)]) + raw


def grpc_frame(message: bytes) -> bytes:
    """gRPC length-prefixed message: one compression flag byte then a big-endian uint32 length."""
    return b"\x00" + pack(">I", len(message)) + message


parser = ArgumentParser(prog="grpc probe", description="Send one unary gRPC call and assert on the answer.")
parser.add_argument("url", help="Full RPC URL, e.g. https://www.example.com/hello.HelloService/SayHello")
parser.add_argument("--greeting", default=None, help="HelloRequest.greeting; omit for an empty request message")
parser.add_argument("--header", action="append", default=[], metavar="NAME=VALUE", help="Extra request metadata (repeatable)")
parser.add_argument("--expect", action="append", default=[], metavar="SUBSTR", help="Substring the response must carry (repeatable)")
parser.add_argument("--not-expect", action="append", default=[], metavar="SUBSTR", help="Substring the response must NOT carry (repeatable)")
parser.add_argument("--status", type=int, default=200, help="Expected HTTP status (default 200)")
parser.add_argument("--min-seconds", type=float, default=None, help="The call must take at least this long")
parser.add_argument("--max-seconds", type=float, default=None, help="The call must take less than this")
# Above every timeout this spec configures, so a knob that is ignored shows up as the product's
# own 60s default rather than as a client-side timeout with nothing to read.
parser.add_argument("--timeout", type=float, default=120.0, help="Client timeout (default 120s)")
ARGS = parser.parse_args()

# gRPC mandates the TE trailers header on every request. Spelled in caps because httpcore
# lowercases every HTTP/2 header name on its way out (`httpcore/_sync/http2.py`), so the wire
# is unaffected, and only the upper-case spelling is in the repo's codespell ignore list.
headers = {"content-type": "application/grpc", "TE": "trailers", "grpc-accept-encoding": "identity"}
for raw_header in ARGS.header:
    name, _, value = raw_header.partition("=")
    headers[name] = value

message = protobuf_string(1, ARGS.greeting) if ARGS.greeting is not None else b""

failures = []
started = monotonic()
try:
    with httpx.Client(http2=True, verify=False, timeout=ARGS.timeout) as client:  # noqa: S501
        response = client.post(ARGS.url, content=grpc_frame(message), headers=headers)
except BaseException as exc:  # noqa: B036
    elapsed = monotonic() - started
    print(f"PROBE FAIL: request raised after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
    sys_exit(1)

elapsed = monotonic() - started
# latin-1 round-trips every byte, so a substring search over the protobuf payload is exact.
body_text = response.content.decode("latin-1")
header_text = "\n".join(f"{name}: {value}" for name, value in response.headers.items())
haystack = f"{header_text}\n{body_text}"

print(f"PROBE {ARGS.url}")
print(f"  protocol={response.http_version} status={response.status_code} elapsed={elapsed:.1f}s")
print(f"  headers={dict(response.headers)}")
print(f"  body={response.content!r}")

if response.http_version != "HTTP/2":
    failures.append(f"expected HTTP/2, got {response.http_version}")
if response.status_code != ARGS.status:
    failures.append(f"expected HTTP status {ARGS.status}, got {response.status_code}")
for needle in ARGS.expect:
    if needle not in haystack:
        failures.append(f"expected {needle!r} in the response")
for needle in ARGS.not_expect:
    if needle in haystack:
        failures.append(f"did not expect {needle!r} in the response")
if ARGS.min_seconds is not None and elapsed < ARGS.min_seconds:
    failures.append(f"expected the call to take at least {ARGS.min_seconds}s, it took {elapsed:.1f}s")
if ARGS.max_seconds is not None and elapsed >= ARGS.max_seconds:
    failures.append(f"expected the call to take less than {ARGS.max_seconds}s, it took {elapsed:.1f}s")

for failure in failures:
    print(f"PROBE FAIL: {failure}")
sys_exit(1 if failures else 0)
