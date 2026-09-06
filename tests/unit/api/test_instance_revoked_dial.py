"""A revoked instance must not be dialled — and must not fall back to the global API_TOKEN.

Revocation is only worth something if the control plane actually stops being able to reach the
instance. The tempting shape (clear the per-instance credential and let ``from_instance`` fall
back to ``token=``) does the opposite: it hands the caller the shared token, which the instance
still accepts. So the refusal lives in ``API.request()`` — the single funnel both the scheduler
and the Celery worker's push path go through, rather than in any of the ~18 call sites that build
an ``API`` from a database row.

The flag read here is ``credential_revoked``, a projection of the ``credential_revoked_at`` column,
and deliberately NOT the derived ``enrollment_state`` string: issuing a new code on a revoked row
derives to ``"pending"``, so reading the string lifted the revocation the moment an admin started
the re-enrollment -- with the credential columns already cleared, the dial silently went back to
the global token. ``tests/unit/db/test_instance_enrollment.py`` pins that end to end against a real
row; the cases here pin the ``API`` half.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
for _p in (ROOT / "src" / "common" / "api", ROOT / "src" / "common" / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from API import API  # noqa: E402


def _row(**overrides):
    row = {"hostname": "bw-1", "port": 5000, "server_name": "bwapi", "listen_https": False, "https_port": 5443}
    row.update(overrides)
    return row


def test_revoked_row_never_reaches_the_network():
    api = API.from_instance(_row(credential_revoked=True, credential=None), token="the-global-token")
    with patch("API.request") as network:
        sent, err, status, resp = api.request("GET", "/ping")
    network.assert_not_called()
    assert sent is False
    assert status is None
    assert "revoked" in err


def test_revoked_row_does_not_carry_the_global_token(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "the-environment-token")
    api = API.from_instance(_row(credential_revoked=True), token="the-global-token")
    # Name-mangled read: the point is that neither the passed fallback NOR API.__init__'s own
    # getenv("API_TOKEN") fallback was silently attached. `None` would take the getenv branch.
    assert not getattr(api, "_API__token")


@pytest.mark.parametrize("state", ("none", "pending", "enrolled", None))
def test_every_other_state_still_dials(state):
    """`credential_revoked` is False for every one of them -- including "pending", which is what a
    re-enrollment in flight derives to and what used to be indistinguishable from a lifted
    revocation."""
    row = _row(credential="per-instance") if state is None else _row(enrollment_state=state, credential_revoked=False, credential="per-instance")
    api = API.from_instance(row, token="the-global-token")
    with patch("API.request") as network:
        network.return_value = type("R", (), {"status_code": 200, "json": lambda self: {"status": "ok"}, "text": "{}"})()
        api.request("GET", "/ping")
    network.assert_called_once()
    assert network.call_args.kwargs["headers"]["Authorization"] == "Bearer per-instance"


def test_unenrolled_row_still_falls_back_to_the_global_token():
    api = API.from_instance(_row(enrollment_state="none", credential_revoked=False), token="the-global-token")
    assert getattr(api, "_API__token") == "the-global-token"
