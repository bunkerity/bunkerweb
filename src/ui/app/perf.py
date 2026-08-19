#!/usr/bin/env python3
"""Per-request accounting of what the UI asked the API for.

Every UI page is assembled from API calls, and the thing that makes a page slow is almost
always their *number*, not any single one of them. This module counts them, times them, and
puts the totals where both a browser and a log can see them:

* `Server-Timing` on the response — readable in the browser's network panel, no tooling needed
* `X-Request-ID` on the response, and on every API call the request made, so one page render can
  be followed across the two services' logs

Nothing here is sampled or configurable: an integer counter and a float sum per request cost
nothing measurable, and a number you have to switch on is a number nobody has when it matters.

**No paths, no arguments, no user data** end up in the header — a `Server-Timing` value is
readable by anything that can read the response, including a shared browser session.
"""

from time import perf_counter
from typing import Optional

from flask import g, has_request_context

from base_api_client import REQUEST_CACHE  # type: ignore

# The header's `desc` is quoted; anything that could carry a quote or a newline stays out.
_HEADER = 'api;dur={api_ms:.1f};desc="{calls} calls", app;dur={app_ms:.1f}, total;dur={total_ms:.1f}'
_HEADER_CACHED = _HEADER + ', cache;desc="{hits} hits"'


def start(request_id: str) -> None:
    """Open the accounting *and* the per-request GET memo. Called once, from `before_request`."""
    g.request_id = request_id
    g.api_calls = 0
    g.api_cached = 0
    g.api_ms = 0.0
    g.request_started = perf_counter()
    REQUEST_CACHE.set({})


def finish() -> None:
    """Close the memo. Called from `teardown_request`, which runs even when `before_request`
    returned early — worker threads are reused, and a memo left open would be handed to the
    next request served by this thread."""
    REQUEST_CACHE.set(None)


def record_api_call(method: str, path: str, duration_ms: float, status: Optional[int]) -> None:
    """The observer handed to the API client. Runs on every call, including failed ones —
    a page that is slow because the API is timing out has to look slow here too."""
    if not has_request_context():
        return
    if status == "memo":
        # Answered from the per-request memo: no round trip happened, so it is not a call.
        g.api_cached = getattr(g, "api_cached", 0) + 1
        return
    g.api_calls = getattr(g, "api_calls", 0) + 1
    g.api_ms = getattr(g, "api_ms", 0.0) + duration_ms


def totals():
    """(calls, api_ms, total_ms) for the current request, or None outside one."""
    if not has_request_context() or not hasattr(g, "request_started"):
        return None
    total_ms = (perf_counter() - g.request_started) * 1000
    return getattr(g, "api_calls", 0), getattr(g, "api_ms", 0.0), total_ms


def server_timing() -> Optional[str]:
    """The `Server-Timing` value for this request, or None if it was never started.

    `app` is the time this process spent on its own — rendering, session handling, everything
    that is not waiting on the API. That split is the whole point: it says which of the two
    services to go and look at.
    """
    measured = totals()
    if measured is None:
        return None
    calls, api_ms, total_ms = measured
    hits = getattr(g, "api_cached", 0)
    template = _HEADER_CACHED if hits else _HEADER
    return template.format(api_ms=api_ms, calls=calls, app_ms=max(total_ms - api_ms, 0.0), total_ms=total_ms, hits=hits)
