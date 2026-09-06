"""A safe loader for `download-crs-plugins.py`'s pure helpers.

The job file is a SCRIPT, not a module: everything from its top-level `try:` onward runs
immediately on import (network calls, `sys_exit`, filesystem writes under `/var/cache`,
`/var/tmp`). Importing it for real is neither safe nor useful for unit-testing the retry/cache
helpers, which is why `test_crs_staging_purge.py` (the other test in this package) works off the
source text instead.

`load_job_helpers()` gives the retry helpers a real, safe way to be exercised: it execs only the
portion of the file BEFORE that `try:` line (imports, constants, `request_with_retry`,
`should_keep_previous_cache` and friends) into a fresh namespace, so the functions under test are
the actual production code, not a re-typed copy of it, without ever running the script body.

Deliberately NOT named `conftest.py`: pytest imports every `conftest.py` under the bare module
name `conftest`, and `sys.modules` caches by that name -- a second directory's `from conftest
import X` can silently resolve to the FIRST `conftest.py` pytest happened to import in the same
process, not its own. That collision is real here: `tests/unit/gen/conftest.py` also exists, and
`pytest tests/unit/modsecurity tests/unit/gen` (or any ordering pytest-randomly picks) fails
collection entirely depending on which one wins the race. A uniquely-named sibling module has no
such landmine.

Caution for the next test author: `should_keep_previous_cache` is a pure predicate, safe to call
freely. `swap_and_cache_plugins` is NOT -- it starts with `rmtree(CRS_PLUGINS_DIR)` against the
real `/var/cache/bunkerweb/modsecurity/crs/plugins`. Nothing in this package calls it; don't,
without monkeypatching `CRS_PLUGINS_DIR`/`NEW_PLUGINS_DIR`/`JOB` in the returned namespace first.
"""

import sys
from pathlib import Path
from types import ModuleType

# `from magic import Magic` runs at module top-level (needed for the exec'd prefix to import
# cleanly) but python-magic isn't a unit-venv dependency -- only `Magic(...).from_buffer(...)`,
# inside the script body we never execute, would actually need it.
if "magic" not in sys.modules:
    _magic_stub = ModuleType("magic")

    class _MagicStub:
        def __init__(self, *_args, **_kwargs):
            pass

        def from_buffer(self, *_args, **_kwargs):  # pragma: no cover -- script body, not under test
            raise NotImplementedError("magic is stubbed in the unit venv")

    _magic_stub.Magic = _MagicStub
    sys.modules["magic"] = _magic_stub

JOB_PATH = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "modsecurity" / "jobs" / "download-crs-plugins.py"
_SCRIPT_BOUNDARY = "\ntry:\n"


def load_job_helpers() -> dict:
    """Return a fresh namespace holding the job file's imports/constants/helper functions --
    everything up to (not including) its top-level `try:` -- without running the script body."""
    source = JOB_PATH.read_text(encoding="utf-8")
    boundary = source.index(_SCRIPT_BOUNDARY)
    prefix = source[:boundary]
    namespace: dict = {"__name__": "download_crs_plugins_prefix", "__file__": str(JOB_PATH)}
    exec(compile(prefix, str(JOB_PATH), "exec"), namespace)  # noqa: S102 - trusted first-party source, test-only
    return namespace
