"""Pre-parser certificate upload size-limit contracts."""

import asyncio
import re
from pathlib import Path

from request_size_limit import CertificateUploadSizeLimitMiddleware  # type: ignore

ROOT = Path(__file__).resolve().parents[3]


def _scope(path="/customcert/certificates/upload", *, content_length=None, root_path=""):
    headers = [] if content_length is None else [(b"content-length", str(content_length).encode("ascii"))]
    return {"type": "http", "method": "POST", "path": path, "root_path": root_path, "headers": headers}


def test_content_length_rejected_before_downstream_reads_body():
    called = False
    sent = []

    async def downstream(_scope, _receive, _send):
        nonlocal called
        called = True

    async def receive():
        raise AssertionError("oversized declared body must not be read")

    async def send(message):
        sent.append(message)

    middleware = CertificateUploadSizeLimitMiddleware(downstream, max_body_size=10)
    asyncio.run(middleware(_scope(content_length=11), receive, send))

    assert called is False
    assert sent[0]["status"] == 413


def test_chunked_body_is_counted_before_multipart_parser_can_finish():
    messages = iter(
        [
            {"type": "http.request", "body": b"123456", "more_body": True},
            {"type": "http.request", "body": b"78901", "more_body": False},
        ]
    )
    sent = []

    async def receive():
        return next(messages)

    async def downstream(_scope, receive_limited, _send):
        while (await receive_limited()).get("more_body"):
            pass

    async def send(message):
        sent.append(message)

    middleware = CertificateUploadSizeLimitMiddleware(downstream, max_body_size=10)
    asyncio.run(middleware(_scope(), receive, send))

    assert sent[0]["status"] == 413


def test_root_path_prefixed_scope_is_still_limited():
    called = False
    sent = []

    async def downstream(_scope, _receive, _send):
        nonlocal called
        called = True

    async def receive():
        raise AssertionError("oversized declared body must not be read")

    async def send(message):
        sent.append(message)

    middleware = CertificateUploadSizeLimitMiddleware(downstream, max_body_size=10)
    scope = _scope("/api/customcert/certificates/upload", root_path="/api", content_length=11)
    asyncio.run(middleware(scope, receive, send))

    assert called is False
    assert sent[0]["status"] == 413


def test_other_routes_are_untouched():
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"large", "more_body": False}

    async def downstream(_scope, _receive, send):
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def send(message):
        sent.append(message)

    middleware = CertificateUploadSizeLimitMiddleware(downstream, max_body_size=1)
    asyncio.run(middleware(_scope("/plugins/upload", content_length=100), receive, send))

    assert sent[0]["status"] == 204


def test_api_app_registers_the_pre_parser_limit():
    source = (ROOT / "src" / "api" / "app" / "main.py").read_text(encoding="utf-8")
    assert re.search(r"app\.add_middleware\(\s*CertificateUploadSizeLimitMiddleware", source)
