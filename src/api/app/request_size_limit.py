"""ASGI request-size guard for certificate multipart uploads."""

from typing import Any, Awaitable, Callable, Dict

CERTIFICATE_UPLOAD_MAX_BODY_SIZE = (2 * 1024 * 1024) + (64 * 1024)
_TOO_LARGE_BODY = b'{"status":"error","message":"Certificate upload exceeds the 2 MiB request limit"}'


class _RequestTooLarge(Exception):
    pass


class CertificateUploadSizeLimitMiddleware:
    """Reject oversized certificate uploads before multipart parsing can spool them."""

    def __init__(self, app: Callable[..., Awaitable[None]], max_body_size: int = CERTIFICATE_UPLOAD_MAX_BODY_SIZE):
        self.app = app
        self.max_body_size = max_body_size

    @staticmethod
    async def _reject(send: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_TOO_LARGE_BODY)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": _TOO_LARGE_BODY})

    async def __call__(self, scope: Dict[str, Any], receive: Callable[..., Awaitable[Dict[str, Any]]], send) -> None:
        path = scope.get("path", "")
        root_path = scope.get("root_path", "").rstrip("/")
        if root_path and (path == root_path or path.startswith(f"{root_path}/")):
            path = path[len(root_path) :] or "/"  # noqa: E203
        if scope.get("type") != "http" or scope.get("method") != "POST" or path.rstrip("/") != "/customcert/certificates/upload":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        try:
            content_length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            content_length = 0
        if content_length > self.max_body_size:
            await self._reject(send)
            return

        received = 0

        async def limited_receive() -> Dict[str, Any]:
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_size:
                    raise _RequestTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestTooLarge:
            await self._reject(send)
