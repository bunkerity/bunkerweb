"""The rate limiter must survive a Redis it cannot reach.

slowapi lets a storage error propagate out of the limit check, so every endpoint answers 500
-- including /ping, which is how the scheduler decides the API is reachable, so an unreachable
Redis stops config pushes to the whole fleet. `in_memory_fallback_enabled` is what turns that
into a logged warning plus in-process counting.

Measured against the pinned slowapi 0.1.10 / limits 5.8.0, with the dependency shape of
`limiter_dep_dynamic` and a Redis nobody listens on: three GETs answer
`[500, 500, 500]` without the flag and `[200, 200, 200]` with it.

Reproducing that here would mean pulling fastapi + slowapi + httpx into the unit
requirements for one test, so this guards the call site instead: the flag is easy to drop
during an unrelated edit and nothing else in the suite would notice.
"""

from pathlib import Path
from re import DOTALL, search

RATE_LIMIT = Path(__file__).resolve().parents[3] / "src" / "api" / "app" / "rate_limit.py"


def test_the_limiter_keeps_serving_when_its_storage_is_unreachable():
    limiter_call = search(r"_limiter = Limiter\((.*?)\n    \)", RATE_LIMIT.read_text(encoding="utf-8"), DOTALL)
    assert limiter_call, "Limiter(...) construction not found in rate_limit.py"
    assert "in_memory_fallback_enabled=True" in limiter_call.group(1)
