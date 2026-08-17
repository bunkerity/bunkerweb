"""BunkerWeb's own components must not be rate-limited by the API.

The UI, the Scheduler and the Worker all authenticate with the admin `API_TOKEN` from inside
the container network, so the per-IP limiter counted the whole control plane as one client: the
default 100 requests per minute was crossed by ordinary use (a single UI page render spends
several calls), and the UI then sat on the 429 until the window rolled over.

Importing `rate_limit.py` here would mean pulling fastapi + slowapi into the unit requirements
for one assertion -- see the note in `test_rate_limit_fallback.py`. This guards the call site
instead: the exemption is one line inside a function whose other branch (the
`API_RATE_LIMIT_EXEMPT_IPS` networks) reads as the complete implementation, so it is easy to
drop during an unrelated edit with nothing else in the suite noticing. Behaviour is covered by
the `ui` integration specs, which fail within a minute of login without it.
"""

from pathlib import Path
from re import DOTALL, search

RATE_LIMIT = Path(__file__).resolve().parents[3] / "src" / "api" / "app" / "rate_limit.py"


def _function_body(name: str) -> str:
    match = search(rf"\ndef {name}\(.*?\n(.*?)\n\n\n", RATE_LIMIT.read_text(encoding="utf-8"), DOTALL)
    assert match, f"{name}() not found in rate_limit.py"
    return match.group(1)


def test_a_request_carrying_the_admin_token_skips_the_limiter():
    assert "_carries_admin_token(request)" in _function_body("_is_exempt")


def test_the_token_comparison_goes_through_the_shared_helper():
    # tokens_equal is constant-time, and refuses an empty/missing side -- an unset API_TOKEN must
    # never turn every bearer-carrying request into an exempt one. Its behaviour is covered by
    # test_auth_token_comparison.py; what this pins is that the limiter uses it rather than
    # growing a second, subtly different comparison.
    assert "tokens_equal(" in _function_body("_carries_admin_token")
