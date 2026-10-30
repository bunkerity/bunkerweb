"""Failed registration backs off without losing the job's previous exit status."""

import sys
from datetime import datetime, timedelta, timezone
from json import dumps, loads
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

JOB_PATH = Path(__file__).resolve().parents[3] / "src/common/core/bunkernet/jobs/bunkernet-register.py"
NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)


class Clock(datetime):
    current = NOW

    @classmethod
    def now(cls, tz=None):
        return cls.current


def _run(cache, reply):
    job = Mock()
    job.get_cache.side_effect = cache.get

    def save(name, data):
        cache[name] = data
        return True, ""

    job.cache_file.side_effect = save
    job.del_cache.side_effect = lambda name: (cache.pop(name, None) is not None, "")
    register = Mock(return_value=reply)
    stubs = {name: ModuleType(name) for name in ("bunkernet", "jobs", "logger")}
    stubs["bunkernet"].register = register
    stubs["jobs"].Job = Mock(return_value=job)
    stubs["logger"].getLogger = Mock(return_value=Mock())
    with patch.dict(sys.modules, stubs), patch.dict("os.environ", {"MULTISITE": "no", "USE_BUNKERNET": "yes"}), patch("datetime.datetime", Clock):
        with pytest.raises(SystemExit) as result:
            exec(compile(JOB_PATH.read_text(), str(JOB_PATH), "exec"), {"__file__": str(JOB_PATH)})
    return result.value.code, register, job


@pytest.mark.parametrize(
    "reply,code",
    [
        ((False, None, "unavailable"), 2),
        ((True, 429, {}), 0),
        ((True, 403, {}), 0),
        ((True, 200, "invalid"), 2),
        ((True, 500, {"data": "error"}), 2),
        ((True, 200, {"result": "ko", "data": "error"}), 2),
        ((True, 200, {"result": "ok", "data": None}), 2),
    ],
)
def test_failure_saves_deadline_and_next_run_skips(reply, code):
    Clock.current = NOW
    cache = {}
    assert _run(cache, reply)[0] == code
    retry = loads(cache["register.retry"])
    assert retry["attempt"] == 1
    assert retry["code"] == code
    assert datetime.fromisoformat(retry["deadline"]) == NOW + timedelta(hours=1)
    Clock.current = NOW + timedelta(minutes=30)
    status, register, _ = _run(cache, reply)
    assert status == code
    register.assert_not_called()


@pytest.mark.parametrize("attempt,hours", [(1, 2), (2, 4), (3, 8), (4, 16), (5, 24), (10, 24)])
def test_expired_deadline_retries_with_capped_exponential_delay(attempt, hours):
    Clock.current = NOW
    cache = {"register.retry": dumps({"attempt": attempt, "deadline": NOW.isoformat(), "code": 2}).encode()}
    status, register, _ = _run(cache, (False, None, "unavailable"))
    assert status == 2
    register.assert_called_once_with()
    retry = loads(cache["register.retry"])
    assert retry["attempt"] == attempt + 1
    assert datetime.fromisoformat(retry["deadline"]) == NOW + timedelta(hours=hours)


@pytest.mark.parametrize("existing", [False, True])
def test_registered_id_clears_retry_cache(existing):
    Clock.current = NOW
    cache = {"register.retry": b"invalid-json"}
    if existing:
        cache["instance.id"] = b"registered-id"
    status, register, job = _run(cache, (True, 200, {"result": "ok", "data": "registered-id"}))
    assert status == (0 if existing else 1)
    assert cache["instance.id"] == b"registered-id"
    assert "register.retry" not in cache
    if existing:
        register.assert_not_called()
    else:
        job.cache_file.assert_any_call("instance.id", b"registered-id")
