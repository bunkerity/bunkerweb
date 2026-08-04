"""The scheduler's poll loop must count *consecutive* failures, not failures ever.

``main.py`` cannot be imported here (its top-level name clashes with ``src/api/app/main.py`` --
see this package's conftest) and the loop it lives in never terminates, so the invariant is
checked on the syntax tree instead. That is enough: the whole defect was a missing reset, which
is a structural property of the loop rather than a runtime one.

Why it matters: past ``errors > 5`` the loop calls ``stop(1)``. With no reset the counter only
ever climbs, so six unrelated hiccups spread over days -- a 429 from the API's own rate limit, a
momentary database lock -- end in a scheduler that exits for good.
"""

import ast
from pathlib import Path

import pytest

MAIN = Path(__file__).resolve().parents[3] / "src" / "scheduler" / "main.py"
COUNTER = "errors"


def _is_reset(node):
    """Whether ``node`` is exactly ``errors = 0``."""
    return (
        isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == COUNTER for t in node.targets)
        and isinstance(node.value, ast.Constant)
        and node.value.value == 0
    )


def _guarded_try():
    """The ``try`` whose handler gives up on the scheduler once the counter is exhausted."""
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    found = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Try)
        and any(isinstance(inner, ast.Name) and inner.id == COUNTER for handler in node.handlers for inner in ast.walk(handler))
        and any(
            isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id == "stop"
            for handler in node.handlers
            for inner in ast.walk(handler)
        )
    ]
    assert len(found) == 1, f"expected exactly one error-budget try/except in main.py, found {len(found)}"
    return found[0]


def test_a_clean_pass_clears_the_error_budget():
    assert any(
        _is_reset(node) for node in _guarded_try().orelse
    ), "the poll loop's try/except has no `else: errors = 0`, so the budget counts failures for the life of the process, not consecutive ones"


def test_every_early_exit_from_the_loop_body_clears_it_too():
    """``continue`` leaves the try statement, so the ``else`` never runs. On a read-only
    instance that is the branch taken almost every second, which would strand the counter."""
    body = _guarded_try().body
    unguarded = []

    for parent in ast.walk(ast.Module(body=body, type_ignores=[])):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(parent, field, None)
            if not isinstance(block, list):
                continue
            for index, node in enumerate(block):
                if isinstance(node, ast.Continue) and not (index and _is_reset(block[index - 1])):
                    unguarded.append(node.lineno)

    assert not unguarded, f"`continue` at main.py line(s) {unguarded} skips the error-budget reset"


@pytest.mark.parametrize("attribute", ["orelse", "handlers"])
def test_the_shape_the_other_tests_rely_on_is_still_there(attribute):
    """Guards the guards: if the try/except is ever restructured, fail loudly here rather than
    let the two assertions above pass against a shape that no longer means anything."""
    assert getattr(_guarded_try(), attribute), f"the error-budget try no longer has a non-empty {attribute}"
