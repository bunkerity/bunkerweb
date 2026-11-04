"""#4106: the scheduler must not render, push and reload a second time after once-jobs that changed nothing.

src/scheduler/main.py runs the whole scheduler at import time, so the pieces under test are pulled out
of its AST and executed in a small namespace. MAIN_PY points the test at another copy of the file (the
unfixed one, to watch it fail).
"""

import ast
import logging
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[3]
MAIN = Path(os.environ.get("MAIN_PY", REPO / "src" / "scheduler" / "main.py"))
SOURCE = MAIN.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def segment(node):
    return ast.get_source_segment(SOURCE, node)


def find(kind, predicate, what):
    matches = [n for n in ast.walk(TREE) if isinstance(n, kind) and predicate(n)]
    if not matches:
        raise AssertionError(f"{what} not found in {MAIN}")
    return min(matches, key=lambda n: n.end_lineno - n.lineno)


def run_once_jobs_block(*, pre_push_done=True, pre_push_rendered=True, first_start=False, readonly=False, jobs_changed=False, jobs_need_generation=False):
    """Execute the real `if RUN_JOBS_ONCE and not pre_push_failed:` block; return its namespace."""
    block = find(ast.If, lambda n: segment(n.test) == "RUN_JOBS_ONCE and not pre_push_failed", "the once-jobs block")
    scheduler = SimpleNamespace(
        reload=lambda *args, **kwargs: True,
        failed_jobs=[],
        db=SimpleNamespace(readonly=readonly),
        consume_pending_publication=lambda: (jobs_changed, jobs_need_generation),
    )
    helper = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "once_jobs_republish"]
    namespace = {
        "SCHEDULER": scheduler,
        "LOGGER": logging.getLogger("test-once-jobs"),
        "IGNORE_FAIL_SENDING_CONFIG": False,
        "getenv": lambda key, default=None: default,
        "generate_caches": lambda: set(),
        "env": {},
        "changed_plugins": [],
        "RELOAD_MIN_TIMEOUT": 15,
        "SEND_FILES_MIN_TIMEOUT": 15,
        "FIRST_START": first_start,
        "RUN_JOBS_ONCE": True,
        "pre_push_failed": False,
        "pre_push_done": pre_push_done,
        "pre_push_rendered": pre_push_rendered,
        "CONFIG_NEED_GENERATION": False,
        "healthcheck_job_run": True,
        "republish_after_jobs": True,
    }
    if helper:
        exec(compile(ast.Module(helper, []), "helper", "exec"), namespace)
    exec(compile(ast.Module([block], []), "block", "exec"), namespace)
    return namespace


def test_nothing_changed_after_a_pushed_configuration_is_not_rendered_again():
    assert run_once_jobs_block(jobs_changed=False)["CONFIG_NEED_GENERATION"] is False


def test_nothing_changed_skips_the_second_reload():
    assert run_once_jobs_block(jobs_changed=False).get("republish_after_jobs") is False


@pytest.mark.parametrize("jobs_changed, jobs_need_generation", [(True, False), (True, True), (False, True)])
def test_a_job_that_changed_something_is_published(jobs_changed, jobs_need_generation):
    ns = run_once_jobs_block(jobs_changed=jobs_changed, jobs_need_generation=jobs_need_generation)
    assert ns["CONFIG_NEED_GENERATION"] is True
    assert ns["republish_after_jobs"] is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"first_start": True},
        {"readonly": True},
        {"pre_push_done": False},
    ],
)
def test_the_cases_that_never_skip_still_publish(kwargs):
    ns = run_once_jobs_block(jobs_changed=False, **kwargs)
    assert ns["republish_after_jobs"] is True


def test_an_unconfirmed_push_accepted_by_ignore_fail_sending_config_still_publishes():
    ns = run_once_jobs_block(jobs_changed=False)
    helper = ns.get("once_jobs_republish")
    assert helper is not None, "once_jobs_republish missing"
    ns["IGNORE_FAIL_SENDING_CONFIG"] = True
    assert helper(False, True, True, False, False) is True
