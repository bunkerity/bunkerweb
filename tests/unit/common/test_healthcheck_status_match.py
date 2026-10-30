"""`healthcheck.sh` must match `/healthz`'s answer exactly, and must accept `loading`.

Port of dev 3a66001b1. Two bugs in one: the default-status check used
``[[ ! " ${DEFAULT_STATUSES[*]} " =~ $check ]]``, a *substring* test against the space-joined list
-- an instance stuck answering an unexpected status containing "ok" as a substring (or worse, an
empty ``$check`` that regex-matches almost anything) would pass. And the default list only ever
covered ``ok``/``reloading``, never the new `loading` state `/healthz` (see
``src/common/confs/healthcheck.conf``) now answers with while `IS_LOADING=yes` or a reload is
in-flight -- flipping the container unhealthy for a state the instance leaves on its own pulls it
out of the k8s endpoints for nothing.

Only the part of the script after the ``nginx.pid`` existence guard is exercised: that guard reads
an absolute system path this test must not create or depend on. ``curl`` is stubbed so ``$check``
is fully controlled and no real HTTP call happens.
"""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
HEALTHCHECK_SH = ROOT / "src" / "common" / "helpers" / "healthcheck.sh"


def _tail_after_pid_guard() -> str:
    """The script from the curl call onward -- skips the shebang, arg parsing and pid guard."""
    source = HEALTHCHECK_SH.read_text(encoding="utf-8")
    marker = 'check="$(curl'
    idx = source.index(marker)
    return source[idx:]


def _run(reported_status: str, specific_status: str = "") -> subprocess.CompletedProcess:
    # SPECIFIC_STATUS is normally set by the arg-parsing block this test skips (see
    # _tail_after_pid_guard); assign it directly instead.
    script = f"""
        SPECIFIC_STATUS="{specific_status}"
        curl() {{ printf '%s' "{reported_status}"; return 0; }}
        {_tail_after_pid_guard()}
    """
    return subprocess.run(["/bin/bash", "-c", script], capture_output=True, text=True, check=False)


@pytest.mark.parametrize("status", ["ok", "loading"])
def test_healthy_statuses_pass(status):
    result = _run(status)
    assert result.returncode == 0, f"status {status!r} must be healthy: {result.stderr}"


@pytest.mark.parametrize("status", ["reloading", "needs_config", "", "not-ok", "ok-ish"])
def test_unrecognized_statuses_fail(status):
    """`reloading` is gone from the accepted set on purpose -- /healthz never answers it (only
    /health, the richer API endpoint, does); this script now only ever sees ok/loading from it."""
    result = _run(status)
    assert result.returncode == 1, f"status {status!r} must be unhealthy, got exit {result.returncode}"


def test_match_is_exact_not_substring():
    """The regression this ports: the old `=~` substring test against " ok reloading " would
    have accepted a `$check` that merely *contains* "ok", such as a curl error echoing "ok" in an
    unrelated word. The case statement must reject it."""
    result = _run("mistook")  # contains "ok" as a substring, is not equal to it
    assert result.returncode == 1, "a substring match on 'ok' must not pass"


def test_specific_status_argument_still_requires_an_exact_match():
    ok = _run("loading", specific_status="loading")
    assert ok.returncode == 0
    mismatch = _run("ok", specific_status="loading")
    assert mismatch.returncode == 1
