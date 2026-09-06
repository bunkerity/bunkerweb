"""jobs.html's deferred-run pill.

A job that left its change flags pending on purpose (push-configs: every instance down) is
recorded `success=True` with `error` prefixed `"deferred: "` -- see
`src/common/utils/jobs.py:JOB_DEFERRAL_PREFIX` and `src/worker/tasks.py`'s `execute_job`. Without
its own pill it renders exactly like an ordinary success (`elif last_run['success']` swallows it),
so an operator reading `/jobs` cannot tell "waiting for an instance" from "ran fine, nothing
changed" -- the exact gap this lane closes. Nothing exercised the template side until now: the
Python relay and the worker fold both have their own tests (`tests/unit/common/`,
`tests/unit/worker/`), but a rename of either side's mirrored `JOB_DEFERRAL_PREFIX`, or a template
typo in the `startswith`/slice, would leave the pill silently dead with the rest of the suite green.

Standalone-Jinja-env harness, the pattern `test_row_actions.py`'s `_render_dashboard_page`
established for this exact template (own copy here -- new file, not an edit to that one, per this
wave's `tests/unit/**` = new-files-only constraint).
"""

import re
from pathlib import Path

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"
JOBS_UTILS = Path(__file__).resolve().parents[3] / "src" / "common" / "utils" / "jobs.py"
JOBS_TEMPLATE = TEMPLATES / "jobs.html"


def _render_dashboard_page(template, **context):
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"dashboard.html": "{% block content %}{% endblock %}"}),
                FileSystemLoader(TEMPLATES),
            ]
        ),
        autoescape=True,
    )
    env.globals.update(
        csrf_token=lambda: "test-token",
        url_for=lambda endpoint, **_kwargs: f"/{endpoint}",
        # conftest's real-catalog `_` (installed into Jinja's DEFAULT_NAMESPACE) echoes
        # "status.deferred_tooltip" as-is (not in the catalog yet -- handed to the coordinator's
        # merge in i18n-keys-L-H3.json, same interim state as every other lane's pending key) and
        # drops the "reason" kwarg since the key has no "%(reason)s" to substitute into. That
        # would swallow the very interpolation the tooltip test exists to check, so this harness
        # overrides `_` the same way test_instances_enrollment_ui.py's does for its own un-merged
        # keys: echo the key plus its variables.
        _=lambda key, **variables: key + ("|" + "|".join(f"{k}={v}" for k, v in sorted(variables.items())) if variables else ""),
    )
    return env.get_template(template).render(**context)


def _jobs_context(success=True, error=None, has_history=True, is_readonly=False):
    history = [{"start_date": "2026-01-01", "end_date": "2026-01-01", "success": success, "error": error}] if has_history else []
    job_data = {
        "plugin_id": "jobs",
        "every": "day",
        "reload": True,
        "async": False,
        "history": history,
        "cache": [],
    }
    return dict(
        jobs={"push-configs": job_data},
        columns_preferences_defaults={"jobs": {}},
        columns_preferences={},
        is_readonly=is_readonly,
        theme="light",
        script_nonce="nonce",
        style_nonce="nonce",
    )


DEFERRED_REASON = "All 1 registered BunkerWeb instance(s) are down; leaving the changes pending for a later run"
DEFERRED_ERROR = f"deferred: {DEFERRED_REASON}"

# The hidden `<i>` hooks jobs.js's searchPanes filter matches on (jobs.js:362-390). Exact strings,
# not bare substrings -- "bx-check"/"bx-x" alone also appear in the unrelated Reload/Async badge
# cells (components/badge.html's `icon=` markup, a different, non-hidden `<i class="bx {icon}
# me-1">`), so a substring check would false-positive against those.
SUCCESS_ICON = '<i class="bx bx-check d-none" aria-hidden="true"></i>'
FAILED_ICON = '<i class="bx bx-x d-none" aria-hidden="true"></i>'
DEFERRED_ICON = '<i class="bx bx-time d-none" aria-hidden="true"></i>'


# The history dropdown's own icon (jobs.html:188-195) is a second, independent branch on the same
# success/error pair -- not the hidden filter-hook icon above. Untested until Criticos flagged it:
# deleting that branch's `{% if %}` left all other assertions green.
HISTORY_DEFERRED_ICON = '<i class="bx bx-time text-warning"></i>'


def test_a_deferred_run_renders_its_own_pill_not_success_or_failed():
    html = _render_dashboard_page("jobs.html", **_jobs_context(success=True, error=DEFERRED_ERROR))

    assert 'data-value="deferred"' in html
    assert DEFERRED_ICON in html
    # Not conflated with either of the other two states. This is the failure mode a constant or
    # template drift produces: `elif last_run['success']` silently swallows a deferral into the
    # ordinary success pill, and the two assertions above alone would not catch it.
    assert SUCCESS_ICON not in html
    assert FAILED_ICON not in html
    assert HISTORY_DEFERRED_ICON in html


def test_the_tooltip_carries_the_full_sentence_and_the_reason():
    """PO ruling 2026-09-02: the pill/filter stay short ("Deferred"), the full sentence plus the
    specific reason move to the tooltip via a second key (status.deferred_tooltip)."""
    html = _render_dashboard_page("jobs.html", **_jobs_context(success=True, error=DEFERRED_ERROR))

    assert 'data-bs-original-title="status.deferred_tooltip|reason=' in html
    assert DEFERRED_REASON in html
    # The raw "deferred: " marker is an internal convention for the DB row, not operator-facing
    # copy -- it must never leak into what actually reaches the page.
    assert DEFERRED_ERROR not in html


def test_the_pill_itself_stays_short():
    """The pill/filter-pane label is the short "Deferred" (i18n_key=status.deferred, no reason
    interpolated into it) -- only the tooltip's separate key (status.deferred_tooltip) carries the
    reason, per the same PO ruling."""
    html = _render_dashboard_page("jobs.html", **_jobs_context(success=True, error=DEFERRED_ERROR))

    # This harness's `_` echoes "<key>" verbatim for a call with no variables, and "<key>|k=v" for
    # one with variables (see _render_dashboard_page) -- so the bare, unpiped key is the pill.
    assert "<span>status.deferred</span>" in html
    assert "status.deferred|" not in html


def test_a_plain_success_still_renders_the_success_pill():
    """Anti-vacuity: a run that never deferred (error=None) must not be swept into the new branch
    -- the far more common case, and the one a careless `if last_run['error']` (dropping the
    `.startswith` half) would break silently."""
    html = _render_dashboard_page("jobs.html", **_jobs_context(success=True, error=None))

    assert SUCCESS_ICON in html
    assert DEFERRED_ICON not in html
    assert 'data-value="deferred"' not in html
    assert HISTORY_DEFERRED_ICON not in html


def test_a_real_failure_still_renders_the_failed_pill():
    """`success=False` must win over any stray error text -- a crash is never a deferral, whatever
    its message happens to start with."""
    html = _render_dashboard_page("jobs.html", **_jobs_context(success=False, error="Job crashed: boom"))

    assert FAILED_ICON in html
    assert DEFERRED_ICON not in html
    assert 'data-value="deferred"' not in html


def test_the_templates_mirrored_prefix_constant_matches_the_python_source_of_truth():
    """The one unguarded point of silent failure: jobs.html hand-mirrors
    `src/common/utils/jobs.py`'s `JOB_DEFERRAL_PREFIX` (a Jinja template cannot import a Python
    constant). A rename on either side without the other leaves the branch permanently unreachable
    -- every deferred run quietly renders as a plain success -- while every other test above still
    passes, because they all go through the template's own (now-wrong) constant.
    """
    python_source = JOBS_UTILS.read_text(encoding="utf-8")
    template_source = JOBS_TEMPLATE.read_text(encoding="utf-8")

    python_match = re.search(r'JOB_DEFERRAL_PREFIX = "([^"]*)"', python_source)
    template_match = re.search(r"\{%\s*set JOB_DEFERRAL_PREFIX = '([^']*)'\s*%\}", template_source)

    assert python_match, "src/common/utils/jobs.py no longer defines JOB_DEFERRAL_PREFIX the way this test expects"
    assert template_match, "jobs.html no longer defines its mirrored JOB_DEFERRAL_PREFIX the way this test expects"
    assert template_match.group(1) == python_match.group(1)
