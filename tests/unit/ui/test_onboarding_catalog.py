"""The onboarding step catalog: gating, completion and the links steps point at.

Two gates decide whether a step renders, and dropping either one is invisible in a green
suite unless both directions are asserted. `requires` keeps write tasks away from readers;
`tracks` keeps reader orientation away from admins — the orientation steps are themselves
`requires="read"`, so `requires` alone would show an admin "Find out why a request was
blocked" on its own dashboard.
"""

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from jinja2 import ChainableUndefined, ChoiceLoader, DictLoader, Environment, FileSystemLoader

from app.models.onboarding import (  # noqa: E402
    CATALOG,
    HINT_PAGE_IDS,
    TRACKS,
    is_complete,
    progress,
    resolve_track,
    visible_steps,
)

ROUTES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes"
TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"

ALL_SIGNALS = {
    "is_initialized": True,
    "first_config_saved": True,
    "is_pro": True,
    "instances": 2,
    "services": 3,
    "certificates_total": 1,
    "blocks_total": 42,
    "workflows_total": 1,
    "workflows_available": True,
    "mfa": "SECRET",
    "acked_hints": ["home", "reports", "bans", "logs"],
}
NO_SIGNALS = {"workflows_available": True}


# --------------------------------------------------------------------------------------
# Targets — the anti-rot half
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("step", CATALOG, ids=[step.id for step in CATALOG])
def test_every_step_points_at_a_view_that_exists(step):
    """`url_for` on a dead endpoint renders "#", which reads as a working link and is not.
    Checked statically against the route modules so no app boot is needed."""
    module_name, _, view = step.endpoint.partition(".")
    source_file = ROUTES / f"{module_name}.py"

    assert source_file.is_file(), f"{step.id}: no route module {module_name}.py"
    source = source_file.read_text(encoding="utf-8")
    assert re.search(rf'Blueprint\(\s*["\']{re.escape(module_name)}["\']', source), f"{step.id}: blueprint is not named {module_name}"
    assert re.search(rf"^def {re.escape(view)}\(", source, re.MULTILINE), f"{step.id}: {module_name}.py has no view {view}()"


def _chrome_html():
    """The two templates that carry every anchor, rendered — not scanned.

    A literal scan would pass on `data-tour="nav-{{ endpoint }}"` while proving nothing about
    which entries actually come out of the loop; the whole point of the assertion is that
    `nav-bans` exists as a rendered attribute a `querySelector` can find."""
    # The language selector needs a context of its own and carries no anchor.
    env = Environment(
        loader=ChoiceLoader([DictLoader({"language-selector.html": ""}), FileSystemLoader(TEMPLATES)]),
        autoescape=True,
        undefined=ChainableUndefined,
    )
    env.globals.update(
        url_for=lambda endpoint, **kwargs: "/" + endpoint,
        csrf_token=lambda: "t",
        current_user=SimpleNamespace(is_authenticated=True, admin=True, get_id=lambda: "alice", list_roles=["admin"], list_permissions=["read", "write"]),
    )
    context = {
        "theme": "light",
        "plugins": {},
        "extra_pages": [],
        "current_endpoint": "home",
        "is_pro_version": False,
        "pro_diamond_url": "/d.svg",
        "bw_version": "1.7.0",
        "request": SimpleNamespace(path="/home", endpoint="home.home_page", args={}, values={}, blueprint="home"),
    }
    return env.get_template("menu.html").render(**context) + env.get_template("navbar.html").render(**context)


@pytest.mark.parametrize("step", [s for s in CATALOG if s.anchor], ids=lambda s: s.id)
def test_every_spotlight_anchor_exists_in_the_rendered_chrome(step):
    """The test that fails the moment a refactor deletes an anchor the walkthrough points at."""
    assert f'data-tour="{step.anchor}"' in _chrome_html(), f"{step.id}: nothing in the chrome answers to {step.anchor}"


def test_step_ids_are_unique():
    ids = [step.id for step in CATALOG]
    assert len(ids) == len(set(ids))


def test_the_kv_key_cannot_collide_with_a_datatables_id():
    """`key` is one shared namespace. A table id equal to the feature key would have them
    overwrite each other's blob."""
    from app.models.onboarding import PREFERENCE_KEY
    from app.utils import COLUMNS_PREFERENCES_DEFAULTS

    assert PREFERENCE_KEY not in COLUMNS_PREFERENCES_DEFAULTS


def test_hint_ids_are_derived_from_the_catalog():
    assert HINT_PAGE_IDS == {"home", "reports", "bans", "logs"}


# --------------------------------------------------------------------------------------
# Track resolution and the two gates
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("admin", "readonly", "expected"),
    [(True, False, "admin"), (True, True, "admin"), (False, False, "writer"), (False, True, "reader")],
)
def test_track_resolution(admin, readonly, expected):
    assert resolve_track(admin=admin, readonly=readonly) == expected


def test_reader_sees_only_read_steps():
    for step in visible_steps("reader", ALL_SIGNALS):
        assert step.requires == "read", step.id


def test_reader_orientation_never_leaks_into_a_write_track():
    """The direction `requires` alone cannot enforce: orientation steps are `requires="read"`,
    which every track satisfies."""
    orientation = {step.id for step in CATALOG if step.tracks == ("reader",)}
    assert orientation, "no reader-only steps left to assert against"

    for track in ("admin", "writer"):
        assert not orientation & {step.id for step in visible_steps(track, ALL_SIGNALS)}, track


def test_requires_wins_when_a_step_declares_a_track_it_does_not_serve():
    """Across today's eleven steps `requires` never changes the outcome — every row's `tracks`
    already encodes the same restriction. It earns its keep on the next step somebody adds
    with the two disagreeing: a writer offered a task only an admin can finish. Asserted with
    a synthetic step because no shipped row exercises it."""
    from dataclasses import replace

    import app.models.onboarding as onboarding_module

    bad = replace(onboarding_module.CATALOG[0], id="admin_only_but_offered_to_writers", requires="admin", tracks=("admin", "writer"))
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(onboarding_module, "CATALOG", (bad,))

        assert [step.id for step in visible_steps("admin", ALL_SIGNALS)] == [bad.id]
        assert visible_steps("writer", ALL_SIGNALS) == ()


def test_every_shipped_step_is_reachable_by_every_track_it_declares():
    """The invariant that makes `requires` redundant today. Stated so that breaking it is a
    deliberate act rather than a step nobody can see."""
    satisfies = {"admin": ("read", "write", "admin"), "writer": ("read", "write"), "reader": ("read",)}

    for step in CATALOG:
        for track in step.tracks:
            assert step.requires in satisfies[track], f"{step.id} declares track {track} but requires {step.requires}"


def test_writer_never_sees_the_admin_only_step():
    assert "pro" in {step.id for step in visible_steps("admin", ALL_SIGNALS)}
    assert "pro" not in {step.id for step in visible_steps("writer", ALL_SIGNALS)}


def test_workflow_step_disappears_when_the_plugin_is_unavailable():
    signals = dict(ALL_SIGNALS, workflows_available=False)

    assert "workflow" in {step.id for step in visible_steps("admin", ALL_SIGNALS)}
    assert "workflow" not in {step.id for step in visible_steps("admin", signals)}


def test_mfa_is_the_one_step_every_track_shares():
    for track in TRACKS:
        assert "mfa" in {step.id for step in visible_steps(track, ALL_SIGNALS)}, track


# --------------------------------------------------------------------------------------
# Completion
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("track", TRACKS)
def test_nothing_is_done_without_signals(track):
    steps = visible_steps(track, NO_SIGNALS)
    done, total = progress(steps, NO_SIGNALS)

    assert done == 0
    assert total > 0
    assert not is_complete(steps, NO_SIGNALS)


@pytest.mark.parametrize("track", TRACKS)
def test_everything_is_done_with_full_signals(track):
    steps = visible_steps(track, ALL_SIGNALS)
    done, total = progress(steps, ALL_SIGNALS)

    assert done == total
    assert is_complete(steps, ALL_SIGNALS)


def test_optional_steps_do_not_hold_the_verdict_back():
    """A FREE install must not sit at 6/7 forever because it will never activate PRO."""
    signals = dict(ALL_SIGNALS, is_pro=False, workflows_total=0)
    steps = visible_steps("admin", signals)

    assert {step.id for step in steps} >= {"pro", "workflow"}
    assert is_complete(steps, signals)
    _, total = progress(steps, signals)
    assert total == len([step for step in steps if not step.optional])


# --------------------------------------------------------------------------------------
# The per-page hints (L3)
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("page_id", sorted(HINT_PAGE_IDS))
def test_a_hint_page_id_is_the_blueprint_of_the_step_it_completes(page_id):
    """The client matches a hint to a page with `request.blueprint`, so the id the catalog
    derives has to *be* that blueprint. Rename the blueprint without renaming the step and the
    hint silently never shows again — nothing else in the suite would notice."""
    step = next(step for step in CATALOG if step.id == f"read_{page_id}")

    assert step.endpoint.split(".")[0] == page_id


@pytest.mark.parametrize("page_id", sorted(HINT_PAGE_IDS))
def test_every_hint_has_its_own_copy_in_en_json(page_id):
    """Falling back to the checklist line would render "Find out why a request was blocked" as
    the explanation of the reports page, which explains nothing."""
    import json

    locales = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "locales"
    hints = json.loads((locales / "en.json").read_text())["onboarding"]["hint"]

    assert page_id in hints
    assert hints[page_id].strip()
