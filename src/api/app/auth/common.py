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
