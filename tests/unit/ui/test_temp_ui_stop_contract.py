"""`handle_stop` must not re-send SIGTERM from inside the SIGTERM handler.

`src/ui/temp.py` runs the wizard's temporary UI. `stop(status, _stop=True)` kills gunicorn and
exits; `handle_stop`, which is bound to SIGINT and SIGTERM, calls `stop(0, False)` so that the
signal path exits *without* killing anything — the signal is already the shutdown.

This file exists because of a specific re-port hazard. dev's `1569c176e`
("stop the temp setup UI without a TypeError") changes exactly this call:

    -    stop(0, False)
    +    stop(0)

In **dev** that is correct: dev's signature is `def stop(status)`, one parameter, so `stop(0, False)`
raised `TypeError` and the fix removes the extra argument. In **1.7** the signature is
`def stop(status, _stop: bool = True)` — the parameter exists, `stop(0, False)` is valid, and the
`False` is the whole point. Applying dev's one-line diff here silently flips `_stop` to `True` and
re-enables `call(["kill", "-SIGTERM", pid])` from inside the handler that SIGTERM just triggered.

A row that reads "tiny fix, one line, same file" is exactly the one nobody re-derives. The probe
says "probably build it" for it (RULE 6 clause 2: that is a question, not a verdict). These
assertions are the answer, kept next to the code so it does not have to be re-derived a third time.

`temp.py` is still live: `src/ui/entrypoint.sh` manages `tmp-ui.pid` at `:17-23`, `:54` and
`:102-107`, and the Linux packaging names it in `bunkerweb-ui.service`.

**There are TWO copies of this function**, found by running RULE 11 backwards over this closed row:
`src/ui/temp.py:25` for the wizard's temporary UI (`tmp-ui.pid`) and `src/ui/app/utils.py:166` for
the main UI (`ui.pid`). Identical signature, identical `_stop` guard, identical `stop(0, False)`
caller. Guarding only the one dev's commit happens to name would leave the **higher-impact** copy
open — a re-port landing on `app/utils.py` SIGTERMs the real UI's gunicorn, not the wizard's.

One contract, two homes, and the duplication itself is the underlying defect. Recorded for the
closing chantier rather than deduplicated here: the two differ only in their pid file, and merging
them is a shared-module decision across `temp.py` and `app/utils.py`.
"""

import ast
from pathlib import Path

import pytest

_UI = Path(__file__).resolve().parents[3] / "src" / "ui"
# (file, the pid it kills) -- both carry the same contract; see the module docstring.
SHUTDOWN_SITES = [("temp.py", "tmp-ui.pid"), ("app/utils.py", "ui.pid")]


def _function(relative, name):
    tree = ast.parse((_UI / relative).read_text(encoding="utf-8"))
    found = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name), None)
    assert found is not None, f"{name}() is gone from {relative} -- the shutdown path was restructured, re-read the row"
    return found


def test_the_sweep_sees_both_copies():
    """Anti-vacuity, and it is not decoration: mutant D on this file emptied `SHUTDOWN_SITES`, and
    pytest reported **3 skipped, 0 failed** -- every assertion below gone, nothing red. An emptied
    parametrize list is the same plausible-emptiness that has bitten this host ten times today, and
    a guard whose source list can be silently emptied is a guard with no floor."""
    assert len(SHUTDOWN_SITES) == 2, f"expected both stop() copies, got {SHUTDOWN_SITES}"
    assert {relative for relative, _ in SHUTDOWN_SITES} == {"temp.py", "app/utils.py"}
    for relative, _ in SHUTDOWN_SITES:
        assert (_UI / relative).is_file(), f"{relative} is gone -- re-read the row before deleting this guard"


@pytest.mark.parametrize("relative,pid_file", SHUTDOWN_SITES, ids=[r for r, _ in SHUTDOWN_SITES])
def test_stop_still_takes_the_suppression_flag(relative, pid_file):
    """If this parameter ever goes away, dev's one-liner becomes correct here and this file's
    reasoning expires. Fail loudly rather than keep guarding a contract that no longer exists."""
    stop = _function(relative, "stop")
    names = [arg.arg for arg in stop.args.args]

    assert names == ["status", "_stop"], f"{relative}: stop() signature changed to {names}"
    assert len(stop.args.defaults) == 1 and stop.args.defaults[0].value is True, "_stop no longer defaults to True"


@pytest.mark.parametrize("relative,pid_file", SHUTDOWN_SITES, ids=[r for r, _ in SHUTDOWN_SITES])
def test_the_signal_handler_suppresses_the_kill(relative, pid_file):
    """The regression a verbatim port of `1569c176e` would introduce."""
    handler = _function(relative, "handle_stop")
    calls = [n for n in ast.walk(handler) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "stop"]

    assert len(calls) == 1, f"{relative}: handle_stop makes {len(calls)} stop() calls, expected 1"
    call = calls[0]
    positional = [getattr(a, "value", None) for a in call.args]
    keyword = {k.arg: getattr(k.value, "value", None) for k in call.keywords}

    assert positional[1:] == [False] or keyword.get("_stop") is False, (
        f"{relative}: handle_stop() no longer passes _stop=False -- it will SIGTERM gunicorn from "
        "inside the SIGTERM handler. This is what porting dev's 1569c176e verbatim does; see the docstring."
    )


@pytest.mark.parametrize("relative,pid_file", SHUTDOWN_SITES, ids=[r for r, _ in SHUTDOWN_SITES])
def test_the_kill_is_still_what_the_flag_guards(relative, pid_file):
    """Pins *why* the flag matters. If the kill moves out of `stop`, the two tests above are
    guarding an argument that no longer protects anything."""
    stop = _function(relative, "stop")
    guard = next((n for n in stop.body if isinstance(n, ast.If)), None)

    assert guard is not None and ast.unparse(guard.test) == "_stop", f"{relative}: stop() no longer guards its body on _stop"
    body = ast.unparse(guard)
    assert "SIGTERM" in body, f"{relative}: the SIGTERM kill is no longer inside the _stop guard"
    assert pid_file in body, f"{relative}: expected it to kill {pid_file} -- the two copies may have been merged"
