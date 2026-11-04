"""`send_files` must put the caller's read budget on the wire, uncapped.

Port of dev `0d3532e69` (row 55 of fold-in 9), the `ApiCaller.py` half.

`folder_push_timeout` already draws the line the module means to hold, and
`test_api_caller_busy_retry.py::test_the_folder_push_budget_scales_with_the_service_count`
pins it: the *derived* read budget is capped at 120s, but an explicit floor is caller intent and
is **not** capped -- `folder_push_timeout(300, 40) == (5, 300)`.

`send_files` then contradicted that. Its own docstring says the write budget "defaults to the read
budget, which is the one already sized for this archive", but the code ran the read budget through
`min(WRITE_TIMEOUT_CAP, ...)` with `WRITE_TIMEOUT_CAP = 120`. The socket carries the connect budget
until the body has been written, so that 120 is the real ceiling on the body of a folder push: a
caller that asked for 300s got 300s to *read* the answer and 120s to *send* the archive it sized
that floor for. Removing the cap is what makes the explicit floor mean the same thing end to end.
"""

import pytest

from ApiCaller import ApiCaller, folder_push_timeout


class _RecordingCaller(ApiCaller):
    """Stops at `send_to_apis` -- the wire is not what is under test, the budget handed to it is."""

    def __init__(self):
        super().__init__()
        self.sent = []

    def send_to_apis(self, method, url, files=None, data=None, timeout=(5, 10), response=False, write_timeout=None):
        body = files["archive.tar.gz"].read() if files else b""
        self.sent.append({"timeout": timeout, "write_timeout": write_timeout, "body": body})
        return True, {}


@pytest.fixture()
def payload(tmp_path):
    """A real directory, because `send_files` tars its argument before it calls anything."""
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "blacklist.list").write_text("1.2.3.4\n", encoding="utf-8")
    return (tmp_path / "cache").as_posix()


def test_an_explicit_floor_reaches_the_body_write(payload):
    """The case the cap silently undid: `folder_push_timeout`'s uncapped floor, back to 120s."""
    connect, read = folder_push_timeout(300, 40)
    assert (connect, read) == (5, 300), "guard: this test is about the budget folder_push_timeout hands out"

    caller = _RecordingCaller()
    caller.send_files(payload, "/cache", timeout=(connect, read))

    assert caller.sent[0]["write_timeout"] == 300


def test_the_derived_budget_is_still_what_it_always_was(payload):
    """The capped-by-derivation path is unchanged: 120 comes from folder_push_timeout, not from here."""
    caller = _RecordingCaller()
    caller.send_files(payload, "/cache", timeout=folder_push_timeout(30, 400))

    assert caller.sent[0]["write_timeout"] == 120


def test_a_scalar_timeout_is_used_as_the_body_budget(payload):
    """`timeout` is not always a tuple; the scalar form must not fall through as None."""
    caller = _RecordingCaller()
    caller.send_files(payload, "/cache", timeout=200)

    assert caller.sent[0]["write_timeout"] == 200


def test_a_caller_that_knows_better_still_wins(payload):
    """An explicit write_timeout is never derived from the read budget."""
    caller = _RecordingCaller()
    caller.send_files(payload, "/cache", timeout=(5, 300), write_timeout=15)

    assert caller.sent[0]["write_timeout"] == 15


def test_the_archive_still_reaches_send_to_apis(payload):
    """Non-vacuity floor: the recording subclass must be standing in for a real push, not short-circuiting one."""
    caller = _RecordingCaller()

    assert caller.send_files(payload, "/cache") is True
    assert len(caller.sent) == 1
    assert caller.sent[0]["body"].startswith(b"\x1f\x8b"), "a gzip archive, not an empty stand-in"
