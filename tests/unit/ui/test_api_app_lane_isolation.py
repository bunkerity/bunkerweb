"""The `api_app` lane must be opt-in AND exclusive, and both spellings of the ignore are load-bearing.

RULE 14a: this fix was written in response to a specific measured failure and shipped with no test.
The failure was `BW_API_APP_LANE=1 pytest tests/unit` collecting **0 of 4130** and reporting one
error naming `app.models.ui_database` -- i.e. pointing at the UI rather than at the lane that caused
it. A CI job that exports the flag once in its environment gets a silent coverage hole that way.

RULE 14b: it has **two** code paths and each needs its own assertion, because each is guarded by a
different spelling in `tests/unit/conftest.py`:

    "api_app"      ignores the DIRECTORY node -> stops a tree walk descending in and executing
                   api_app/conftest.py, which unconditionally puts `src/api` on sys.path as `app`
    "api_app/*"    ignores the FILES          -> still applies when the directory is NAMED on the
                   command line, where the directory pattern is not consulted

Removing either one leaves the other's path working, so a single test over one path would stay green
while the other regressed. That is 14b exactly: one guard per behaviour is not one guard per path.

Each case shells out to a real pytest collection, because the behaviour under test *is* pytest's
collection and no in-process assertion can stand in for it. `--collect-only` keeps it ~2s.

**Widened after a second door opened.** `api_app` was never the only way for a second `app` package
to reach this interpreter, and the guard above only ever claimed that one. On 2026-08-20 a new file
in `tests/unit/api/` -- the ordinary, always-collected API lane -- did its own
`sys.path.insert(0, src/api)` and `from app.schemas import ...`. `tests/unit/api` sorts before
`tests/unit/ui`, so `sys.modules["app"]` was the API's by the time the UI's conftest ran, and
`pytest tests/unit` collected **2565 with 1 error instead of 4764**: the UI lane, ~2200 tests, did
not run and the summary line said "2565 collected" rather than anything red about the UI. CI runs
exactly that command (`.github/workflows/unit-tests.yml:121`).

So the last two tests here are about the *name*, not about the lane: whoever holds `app` in a
whole-tree run, every lane must still collect. The fix was to restore the API lane's own documented
convention -- `conftest.py:15-18` puts `src/api/app` on the path so its tests import `schemas`
bare, never `app.schemas` -- and the source-level test below is what stops that convention being
bypassed again by a file that looks perfectly ordinary.
"""

import os
import shutil
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
UNIT = REPO / "tests" / "unit"


def _collect(*args, lane=False, execute=False):
    env = dict(os.environ)
    env.pop("BW_API_APP_LANE", None)
    if lane:
        env["BW_API_APP_LANE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *([] if execute else ["--collect-only"]), "-q", "-p", "no:cacheprovider", *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    out = proc.stdout + proc.stderr
    # RULE 18: a path that does not exist, and two paths joined into one argument, BOTH print
    # "no tests collected" -- byte-identical to a legitimately empty collection. Measured: rc 4 in
    # both cases, rc 5 for the real thing. A caller reading only `ids` would get [] and a verdict
    # shaped like an answer, so the caller bug dies here instead of becoming a green test.
    if proc.returncode == pytest.ExitCode.USAGE_ERROR:
        raise AssertionError(f"pytest rejected the arguments {args!r} -- this is a bug in the test, not a result:\n{out[-1000:]}")
    # Exit code, never prose. "Interrupted" is also the name of a test class in this tree
    # (backup/test_backup_archive.py::TestInterruptedWrite), so a substring sentinel over the
    # output reports a broken collection on a perfectly healthy one.
    ids = [line.strip() for line in out.split("\n") if "::" in line and line.strip().startswith("tests/")]
    return pytest.ExitCode(proc.returncode), ids, out


# The two tests that RUN the lane need the lane's own dependencies, and those are opt-in by design:
# `biscuit-python` needs a Rust toolchain, so it is pinned in `tests/unit/api_app/requirements.txt`
# and deliberately kept out of `tests/unit/requirements.txt` (see `api_app/README.md`).
#
# RULE 21 -- this gate exists because the failure was wearing this guard's verdict. Without it, a
# host that never installed the lane sees `AssertionError: the flagged tree run did not collect
# cleanly (INTERRUPTED)` from a *lane isolation* test, and the real cause -- one absent wheel --
# is four lines further down the captured output. It misled a reader today into recording the
# missing wheel as a misdiagnosis of an unrelated `app`-package collision. A missing dependency is
# neither "isolation held" nor "isolation broke", so it must produce neither.
#
# The skip is loud on purpose: it names the wheel and the exact install line. It is also a real
# coverage hole rather than a tidy-up -- CI installs `tests/unit/requirements.txt` only, so these
# two never run there. Recorded for the PO, not closed here.
_LANE_DEPS = find_spec("biscuit_auth") is not None
_needs_lane_deps = pytest.mark.skipif(
    not _LANE_DEPS,
    reason="the api_app lane's own dependencies are not installed: .venv-unit/bin/pip install --require-hashes -r tests/unit/api_app/requirements.txt",
)


def test_the_skip_condition_above_matches_what_the_lane_actually_declares():
    """Never skips, on purpose. A `skipif` whose reason has gone stale reads exactly like one that
    is still true, and two of the five tests here hang off this one boolean."""
    declared = (UNIT / "api_app" / "requirements.in").read_text(encoding="utf-8")

    assert "biscuit-python" in declared, "the lane no longer pins biscuit-python; the skip above is gating on the wrong module"
    assert [p for p in (UNIT / "api_app").glob("test_*.py")], "the api_app lane has no test files -- the two tests below would prove nothing even unskipped"


@_needs_lane_deps
def test_the_flag_selects_the_lane_instead_of_merely_unhiding_it():
    """The regression: an ADDITIVE flag ignored nothing when set, so both `app` packages landed in
    one interpreter and the whole tree failed to collect."""
    code, ids, out = _collect(str(UNIT), lane=True)

    assert code is pytest.ExitCode.OK, f"the flagged tree run did not collect cleanly ({code!r}):\n{out[-2000:]}"
    assert ids, "nothing was collected at all"
    assert all("api_app/" in node for node in ids), f"other lanes collected alongside api_app -- the flag is additive again: {ids[:5]}"


PROBE = "api_package_path_never_leaks"


def test_the_api_package_path_never_leaks_into_this_interpreter():
    """The in-process half of the directory spelling, and the only assertion that can see it.
    `api_app/conftest.py` puts `src/api` at `sys.path[0]`; from then on `import app` in this lane
    resolves to the API package. Trivially true when only `tests/unit/ui` is run -- the walk never
    goes near the lane -- and load-bearing during a whole-tree run, which the next test forces."""
    assert str(REPO / "src" / "api") not in sys.path, "src/api is on sys.path -- api_app/conftest.py executed in the UI's interpreter"


def test_the_ordinary_run_never_walks_into_the_lane():
    """The directory spelling, exercised by the run everyone actually makes: `pytest tests/unit`.

    Asserting "no api_app node ids were collected" is NOT this behaviour and does not test it:
    `"api_app/*"` alone hides every file, so the ids are absent either way while the conftest still
    runs. Measured with the directory spelling removed: `src/api` on sys.path False -> True, node
    ids unchanged. So this drives the whole-tree walk and defers the verdict to the probe above,
    which is the assertion that moves."""
    code, _ids, out = _collect(str(UNIT), "-k", PROBE, execute=True)

    assert code is pytest.ExitCode.OK, f"the whole-tree run did not stay isolated ({code!r}):\n{out[-2000:]}"


def test_naming_the_lane_without_the_flag_still_collects_nothing():
    """The glob spelling. A directory pattern is not consulted for a path the user asks for by
    name, so `"api_app"` alone would let this run the lane unflagged."""
    code, ids, out = _collect(str(UNIT / "api_app"))

    assert ids == [], f"the lane was collected without the flag:\n{ids}"
    assert code is pytest.ExitCode.NO_TESTS_COLLECTED, f"naming the lane errored instead of collecting nothing ({code!r}):\n{out[-1000:]}"


@_needs_lane_deps
def test_a_lane_added_after_this_guard_was_written_is_still_excluded(request):
    """MUTANT H: the flagged branch enumerates `tests/unit`'s children at import time, and every
    child that exists today is one the guard's author saw. The half that matters -- "a directory
    nobody anticipated is excluded too" -- is unreachable over real data, and it is exactly the
    half that silently degrades if the comprehension is narrowed to a hardcoded list. The only way
    in is to synthesise a lane that did not exist when the guard was written."""
    scratch = UNIT / "zz_synthetic_lane"
    request.addfinalizer(lambda: shutil.rmtree(scratch, ignore_errors=True))
    scratch.mkdir()
    (scratch / "test_synthetic.py").write_text("def test_synthetic():\n    assert True\n", encoding="utf-8")

    code, ids, out = _collect(str(UNIT), lane=True)

    assert code is pytest.ExitCode.OK, f"the flagged run broke on an unfamiliar sibling ({code!r}):\n{out[-2000:]}"
    assert not [
        node for node in ids if "zz_synthetic_lane" in node
    ], "the flagged run collected a lane the guard never saw -- the exclusion is hardcoded, not derived"


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(str(UNIT / "api_app_TYPO"), id="path-that-does-not-exist"),
        pytest.param(f"{UNIT / 'ui'} {UNIT / 'api_app'}", id="two-paths-joined-into-one-argument"),
    ],
)
def test_a_caller_bug_is_raised_rather_than_returned_as_an_empty_result(bad):
    """RULE 18, and the branch no correct caller reaches -- so only synthetic input can test it.

    Measured: pytest answers BOTH of these with the same "no tests collected" line it prints for a
    genuinely empty collection, and rc 4 rather than 5 is the only thing that separates them. A
    helper that returned `ids == []` here would hand back a verdict shaped like an answer, and the
    test asserting "the lane collected nothing" would go green for the wrong reason.
    """
    with pytest.raises(AssertionError, match="bug in the test, not a result"):
        _collect(bad)


# --------------------------------------------------------------------------------------
# The second door: `tests/unit/api`, which is collected on every ordinary run
# --------------------------------------------------------------------------------------
# RULE 13 floors. `>=`, because both lanes grow; the numbers only exist so the two tests below
# cannot pass over a collection that quietly stopped early. Measured 2026-08-20: api 383, ui 2122.
MINIMUM_API_NODES = 300
MINIMUM_UI_NODES = 2000


def test_the_whole_tree_run_collects_every_lane():
    """The regression, stated as the thing an operator loses: not "an error appeared" but "~2200
    tests stopped running while the summary line still printed a four-digit number".

    Asserting only `ExitCode.OK` would be satisfied by a run that collected the API lane and nothing
    else, which is exactly the shape of the failure -- so both lanes are counted, with a floor under
    each. The two that collide over the name `app` are the two named here.
    """
    code, ids, out = _collect(str(UNIT))

    assert code is pytest.ExitCode.OK, f"the whole tree did not collect ({code!r}):\n{out[-2000:]}"

    api = [node for node in ids if node.startswith("tests/unit/api/")]
    ui = [node for node in ids if node.startswith("tests/unit/ui/")]

    assert len(api) >= MINIMUM_API_NODES, f"the api lane collected {len(api)} nodes, floor is {MINIMUM_API_NODES} -- it was interrupted or excluded"
    assert len(ui) >= MINIMUM_UI_NODES, f"the ui lane collected {len(ui)} nodes, floor is {MINIMUM_UI_NODES} -- it was interrupted or excluded"


def test_the_two_app_packages_still_collect_side_by_side():
    """The minimal reproduction, kept separate from the whole-tree run on purpose.

    `pytest tests/unit/api tests/unit/ui` is two lines of command line and reproduces the whole
    thing; the tree run above takes ~2s more and buries which pair broke. When this pair goes red
    and the tree run goes red together, this one names the cause.
    """
    code, ids, out = _collect(str(UNIT / "api"), str(UNIT / "ui"))

    assert code is pytest.ExitCode.OK, f"api and ui cannot collect in one interpreter again ({code!r}):\n{out[-2000:]}"
    assert len([node for node in ids if node.startswith("tests/unit/api/")]) >= MINIMUM_API_NODES
    assert len([node for node in ids if node.startswith("tests/unit/ui/")]) >= MINIMUM_UI_NODES


def test_no_ordinary_api_test_claims_the_app_package():
    """The source-level half, and the one that names the cause instead of the symptom.

    The two tests above fail with `ModuleNotFoundError: No module named 'app.models.ui_database'`
    raised from the UI's conftest -- pointing at the victim. This one points at the line that did
    it, and it fails on a file that has not been run yet.

    `tests/unit/api/conftest.py:15-18` inserts `src/api/app` (not `src/api`) precisely so this
    lane's tests import `schemas` bare and never bind the global name `app`. Every other file in
    the directory reads API source by path. `tests/unit/api_app/` exists for tests that genuinely
    need the API's `app` package and is opt-in and exclusive for that reason -- so this scan is
    about `api/` only, and moving a file into `api_app/` is a real answer to it (at the price of
    that file leaving the ordinary run, which is a decision, not a workaround).
    """
    api_dir = UNIT / "api"
    sources = sorted(api_dir.glob("*.py"))

    # RULE 13: an empty glob would make the loop below vacuously clean.
    assert len(sources) >= 20, f"only {len(sources)} python files found under {api_dir} -- the scan would be vacuous"

    offenders = []
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or '"""' in stripped:
                continue  # a comment or a docstring line describing the rule is not breaking it
            if "sys.path" in stripped and '"src"' in stripped and '"api"' in stripped and '"app"' not in stripped:
                offenders.append(f"{source.name}:{number}: puts src/api on sys.path, which makes `app` the API's")
            if stripped.startswith(("from app.", "import app")) or stripped.startswith("from app import"):
                offenders.append(f"{source.name}:{number}: imports the API `app` package; import the submodule bare instead")

    assert offenders == [], "these bind `app` to src/api and break the UI lane in any run that collects both:\n  " + "\n  ".join(offenders)
