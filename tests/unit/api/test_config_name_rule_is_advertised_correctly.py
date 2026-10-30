"""What the API advertises about config names must be what it enforces.

Four places tell an operator the rule, and none of them is the rule:

    schemas.py:28    the error message returned by validate_config_name()
    schemas.py:229   the OpenAPI description on ConfigCreateRequest.name
    configs.py:103   the upload_configs docstring
    configs.py:214   the create_config docstring

`NAME_RX` (schemas.py:19) is the rule. It drifted from all four twice in this repo's history and
both drifts were invisible to every existing test:

1. `$` vs `\\Z`. `re.match(r"^[\\w_-]{1,255}$", "name\\n")` is a MATCH -- `$` also matches before a
   trailing newline -- so the regex was hardened to `\\Z` while the documentation kept promising
   `$`. Code right, every word the operator reads wrong.
2. Doubled backslashes in a RAW string. `r"…(^[\\\\w_-]{1,255}\\\\Z)"` is not an escape, it is two
   literal backslashes, and the rendered OpenAPI description read `^[\\\\w_-]{1,255}\\\\Z`. The
   docstrings alongside it are NORMAL strings where `\\\\w` renders as `\\w`, so the same visual
   spelling is correct in one and wrong in the other -- which is exactly why eyeballing missed it.

So this asserts the RENDERED text against `NAME_RX.pattern` rather than against a literal. A test
that hard-coded the expected string would need editing every time the rule legitimately changes,
and would pin whatever was there the day it was written (RULE 19).
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# `from schemas import ...`, NOT `from app.schemas import ...`, and no sys.path work of its own:
# `conftest.py:15-18` already puts `src/api/app` on the path for exactly this ("app/ for `schemas`").
#
# The spelling is load-bearing, not style. Inserting `src/api` and importing `app.schemas` binds
# `sys.modules["app"]` to **src/api/app** -- and the UI defines an `app` package too. `tests/unit/api`
# sorts before `tests/unit/ui`, so the UI's conftest then dies on
# `ModuleNotFoundError: No module named 'app.models.ui_database'` at COLLECTION time, which
# interrupts the whole run: `pytest tests/unit` collected 2565 with 1 error instead of 4764, and CI
# runs exactly that command. It cost ~2200 tests. `tests/unit/api_app/` exists for tests that really
# do need the API's `app` package, and it is opt-in and exclusive for this reason; every other file
# in this directory reads API source by path instead. Pinned by
# tests/unit/ui/test_api_app_lane_isolation.py.
from schemas import NAME_RX, ConfigCreateRequest, validate_config_name  # noqa: E402

CONFIGS_PY = ROOT / "src" / "api" / "app" / "routers" / "configs.py"

# RULE 13: a floor. Another advertisement of the same rule is collaboration, not a regression.
MINIMUM_ADVERTISEMENTS = 4


def _docstring(function_name):
    """Resolve a docstring WITHOUT importing the router.

    `configs.py` pulls in the FastAPI app's dependency graph, which is not installed for unit
    runs. `ast.get_docstring` resolves escape sequences exactly as the interpreter does -- which
    is the whole point here, since the defect being guarded IS an escaping one. Reading the file
    as raw text instead would compare the source spelling, not what an operator is shown.
    """
    tree = ast.parse(CONFIGS_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return ast.get_docstring(node)
    raise AssertionError(f"{function_name} no longer exists in {CONFIGS_PY.name} -- re-read this file")


def _advertisements():
    """Every rendered place the rule is stated, resolved as the reader sees it."""
    return {
        "validate_config_name message": validate_config_name("definitely not valid!"),
        "ConfigCreateRequest.name description": ConfigCreateRequest.model_fields["name"].description,
        "upload_configs docstring": _docstring("upload_configs"),
        "create_config docstring": _docstring("create_config"),
    }


def test_every_advertisement_quotes_the_pattern_actually_enforced():
    for where, text in _advertisements().items():
        assert text, f"{where} is empty"
        assert NAME_RX.pattern in text, f"{where} does not quote {NAME_RX.pattern!r}; it says: {text.strip()[:140]!r}"


def test_no_advertisement_carries_a_doubled_backslash():
    """The raw-string defect. `\\\\w` in rendered text means the operator is shown two backslashes."""
    for where, text in _advertisements().items():
        assert "\\\\" not in text, f"{where} renders doubled backslashes -- raw string with escaped escapes: {text.strip()[:140]!r}"


def test_the_rule_being_advertised_is_the_one_that_matters():
    """Anti-vacuity: if NAME_RX ever loses `\\Z` the assertions above still pass (they compare
    against whatever the pattern is), so pin the property the pattern exists for."""
    assert NAME_RX.match("a_config-1"), "a legal name must match"
    assert not NAME_RX.match("a_config\n"), "a trailing newline must NOT match -- that is what \\Z buys over $"
    assert not NAME_RX.match("a config"), "a space must not match"
    assert validate_config_name("a_config\n") is not None, "the validator must reject what the regex rejects"


def test_the_advertisement_set_has_not_shrunk():
    """RULE 13 floor: a parametrised-style guard over an empty set reports success over nothing."""
    found = _advertisements()
    assert len(found) >= MINIMUM_ADVERTISEMENTS, f"only {len(found)} advertisements collected"
    assert re.search(r"\{1,255\}", NAME_RX.pattern), "NAME_RX no longer looks like the config-name rule; re-read this file"
