"""A busy instance answers 503; that is not a failed push.

Port of dev `462c1e851`, together with the folder-push budget the same commit fixed.

**Where the 503 comes from.** An instance serialises its push swaps and reloads on one lock and
answers 503 while it is held -- dev `32a2985ab`, ported as row 22. `POST /confs` queues
`PUSH_LOCK_WAIT` for the key and `POST /reload` queues `SWAP_WAIT_TIMEOUT`; whichever loses answers
503, and this retry is what keeps a busy instance from being reported as a failed push. Both waits
are kept well under the callers' `(5, 30)` read budget on purpose: a refusal written after the
caller stopped listening arrives as a `ReadTimeout` with NO status, and a status-less answer never
reaches this retry at all, because it keys on the 503.
`test_api_lock_wait_budgets.py` pins that coupling against every caller that declares its own budget.

The same applies to `write_timeout`: `src/common/api/API.py`'s `request` takes the argument since
row 20 (dev `7a6bf2c70`), so `_accepts_write_timeout` now puts it on the wire. `_WriteTimeoutApi`
below pins the contract that port has to satisfy.
"""

from io import BytesIO

import pytest

import ApiCaller as api_caller_module
from ApiCaller import BUSY_ATTEMPTS, ApiCaller, folder_push_timeout


class _Api:
    """An API client whose `request` does NOT take a write_timeout (1.7's, before dev 7a6bf2c70)."""

    endpoint = "http://bw-1:5000/"

    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = []

    def request(self, method, url, files=None, data=None, timeout=None):
        self.calls.append({"timeout": timeout, "body": files["archive.tar.gz"].read() if files else None})
        status = self.statuses.pop(0) if self.statuses else 200
        return status == 200, "", status, {"msg": "ok"}


class _WriteTimeoutApi(_Api):
    """The same client once it accepts the body-write budget."""

    def request(self, method, url, files=None, data=None, timeout=None, write_timeout=None):
        self.calls.append({"timeout": timeout, "write_timeout": write_timeout})
        status = self.statuses.pop(0) if self.statuses else 200
        return status == 200, "", status, {"msg": "ok"}


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr(api_caller_module, "sleep", lambda *_: None)


def test_a_busy_instance_is_retried_and_the_push_succeeds():
    api = _Api([503, 200])
    caller = ApiCaller([api])

    sent, _ = caller.send_to_apis("POST", "/cache")

    assert sent is True, "a 503 from a busy instance was reported as a failed push"
    assert len(api.calls) == 2


def test_an_instance_that_stays_busy_eventually_fails():
    api = _Api([503] * (BUSY_ATTEMPTS + 2))
    caller = ApiCaller([api])

    sent, _ = caller.send_to_apis("POST", "/cache")

    assert sent is False
    assert len(api.calls) == BUSY_ATTEMPTS, "the retry budget is not bounded"


def test_a_real_error_is_not_retried():
    """Only 503 means "busy": retrying a 500 would multiply the load on a broken instance."""
    api = _Api([500, 200])
    caller = ApiCaller([api])

    sent, _ = caller.send_to_apis("POST", "/cache")

    assert sent is False
    assert len(api.calls) == 1


def test_the_retry_rewinds_the_body():
    """The first attempt consumed the buffer; without a rewind the retry uploads nothing."""
    api = _Api([503, 200])
    caller = ApiCaller([api])

    caller.send_to_apis("POST", "/cache", files={"archive.tar.gz": BytesIO(b"archive")})

    assert [call["body"] for call in api.calls] == [b"archive", b"archive"], "the retry uploaded an empty body"


def test_the_write_timeout_reaches_a_client_that_accepts_it():
    api = _WriteTimeoutApi([200])
    caller = ApiCaller([api])

    caller.send_to_apis("POST", "/cache", timeout=(5, 90), write_timeout=90)

    assert api.calls[0]["write_timeout"] == 90


def test_a_client_without_the_argument_is_not_broken_by_it():
    """`send_files` always passes one; a TypeError here would read as "every instance is down"."""
    api = _Api([200])
    caller = ApiCaller([api])

    sent, _ = caller.send_to_apis("POST", "/cache", write_timeout=90)

    assert sent is True


@pytest.mark.parametrize(
    ("min_timeout", "service_count", "expected"),
    (
        (30, 1, 30),  # the previous flat default, unchanged for a single service
        (30, 40, 120),  # 3s per service, capped
        (30, 400, 120),  # the cap holds
        (300, 40, 300),  # an explicit floor is caller intent and is NOT capped
        (30, 0, 30),  # no service yet: still the floor, never 0
    ),
)
def test_the_folder_push_budget_scales_with_the_service_count(min_timeout, service_count, expected):
    connect, read = folder_push_timeout(min_timeout, service_count)

    assert connect == 5, "the connect budget must stay short so a dead host fails fast"
    assert read == expected
