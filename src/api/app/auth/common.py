from hmac import compare_digest
from typing import Optional
from fastapi import Request


def get_auth_header(request: Request) -> str:
    """Return the Authorization header (case-insensitive) or empty string."""
    return request.headers.get("Authorization") or request.headers.get("authorization") or ""


def parse_bearer_token(auth_header: str) -> Optional[str]:
    """Parse Bearer auth header and return the token string or None."""
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    try:
        return auth_header.split(" ", 1)[1].strip()
    except Exception:
        return None


def tokens_equal(provided: Optional[str], expected: Optional[str]) -> bool:
    """Constant-time comparison of a presented credential against the expected one.

    Encoded first: `hmac.compare_digest` raises TypeError on `str` carrying any non-ASCII
    character, and the left-hand value comes straight off an Authorization header, so comparing
    the strings turned a malformed header into a 500 for the caller.
    """
    if not provided or not expected:
        return False
    return compare_digest(provided.encode("utf-8", "surrogatepass"), expected.encode("utf-8", "surrogatepass"))
