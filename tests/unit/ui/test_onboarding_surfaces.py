"""The walkthrough's chrome: the navbar pill and the drawer behind it.

Both are gated on `onboarding_active` so a user who finished or dismissed the walkthrough
downloads none of it and issues no request for it — that gate is the feature's whole cost
story, so it is asserted in both directions.
"""

from pathlib import Path
from types import SimpleNamespace

from conftest import english  # what a converted template renders for a key
import re

import pytest

from jinja2 import ChainableUndefined, ChoiceLoader, DictLoader, Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"

# Enough of the shell for the partials under test; every other block is left empty.
STUBS = {
    "base.html": "{% block head %}{% endblock %}{% block page %}{% endblock %}",
    "language-selector.html": '<div class="lang-sel">EN</div>',
    "menu.html": "",
    "footer.html": "",
    "sidebar-notifications.html": "",
    "sidebar-news.html": "",
    "models/mode_pills.html": "",
}


# ChainableUndefined covers attribute chains but not the ints/lists profile.html does
# arithmetic and length checks on.
_PROFILE_CTX = {"is_totp": False, "total_sessions": 0, "last_sessions": [], "webauthn_enabled": False, "webauthn_credentials": [], "totp_recovery_codes": []}


def _render(template, **context):
    env = Environment(
        loader=ChoiceLoader([DictLoader(STUBS), FileSystemLoader(TEMPLATES)]),
        autoescape=True,
        undefined=ChainableUndefined,
    )
    env.globals.update(
        csrf_token=lambda: "t",
        url_for=lambda endpoint, **kwargs: "/" + "/".join([endpoint, *kwargs.values()]),
        current_user=SimpleNamespace(
            is_authenticated=True, admin=True, get_id=lambda: "alice", list_roles=["admin"], list_permissions=["read", "write"], totp_secret=None
        ),
        request=SimpleNamespace(path="/home", endpoint="home.home_page", args={}, values={}, blueprint="home"),
    )
    base = {"theme": "light", "script_nonce": "n", "style_nonce": "n"}
    base.update(context)
    return env.get_template(template).render(**base)


# --------------------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("active", [True, False])
def test_the_navbar_pill_follows_the_active_flag(active):
    html = _render("navbar.html", onboarding_active=active)

    assert ('id="onboarding-button"' in html) is active


@pytest.mark.parametrize("active", [True, False])
def test_the_dashboard_only_includes_the_drawer_when_active(active):
    """A suite that renders the partial directly cannot see the caller dropping the include."""
    html = _render("dashboard.html", onboarding_active=active)

    assert ('id="side-offcanvas-onboarding"' in html) is active
    assert ('id="onboarding-root"' in html) is active


def test_no_script_is_shipped_to_a_user_who_finished():
    html = _render("dashboard.html", onboarding_active=False)

    assert "js/pages/onboarding.js" not in html


# --------------------------------------------------------------------------------------
# The drawer itself
# --------------------------------------------------------------------------------------
def test_the_drawer_turns_off_the_social_row_and_the_newsletter_footer():
    """`components/drawer.html` defaults both to true; forgetting them ships a Sendinblue
    newsletter signup at the bottom of the getting-started panel."""
    html = _render("models/onboarding_drawer.html", onboarding_active=True)

    assert "social-buttons" not in html
    assert "newsletter" not in html.lower()


def test_the_drawer_carries_its_state_endpoint_and_script():
    html = _render("models/onboarding_drawer.html", onboarding_active=True)

    assert 'data-state-url="/onboarding.onboarding_state"' in html
    assert "js/pages/onboarding.js" in html
    assert "libs/canvas-confetti" in html


def test_the_drawer_announces_step_changes():
    html = _render("models/onboarding_drawer.html", onboarding_active=True)

    assert 'id="onboarding-steps"' in html
    assert 'aria-live="polite"' in html


@pytest.mark.parametrize("autoopen", [True, False])
def test_autoopen_is_a_data_attribute_not_a_render_branch(autoopen):
    """The drawer markup is identical either way — only the flag the script reads changes."""
    html = _render("models/onboarding_drawer.html", onboarding_active=True, onboarding_autoopen=autoopen)

    assert f'data-autoopen="{"yes" if autoopen else "no"}"' in html


# --------------------------------------------------------------------------------------
# Restart, and the checklist macro's new affordance
# --------------------------------------------------------------------------------------
def test_profile_offers_a_way_back_once_the_walkthrough_is_gone():
    """The pill and drawer are not rendered at all after dismissal, so without this there is
    nothing left to click."""
    html = _render("profile.html", **_PROFILE_CTX, db_readonly=False)

    assert 'id="onboarding-restart"' in html
    assert english("onboarding.restart") in html


def test_the_restart_button_is_disabled_on_a_read_only_database():
    html = _render("profile.html", **_PROFILE_CTX, db_readonly=True)

    at = html.index('id="onboarding-restart"')
    start, end = at - 400, at + 200
    marker = html[start:end]
    assert "disabled" in marker


def test_checklist_items_can_carry_a_go_link_only_while_pending():
    source = '{% from "components/checklist.html" import checklist %}{{ checklist(items=items) }}'
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    html = env.from_string(source).render(
        items=[
            {"text": "Pending one", "done": False, "href": "/services"},
            {"text": "Finished one", "done": True, "href": "/services"},
        ]
    )

    assert html.count('href="/services"') == 1, "a finished task has nowhere left to send the reader"


# --------------------------------------------------------------------------------------
# The per-page hint (L3)
# --------------------------------------------------------------------------------------
def test_the_drawer_partial_ships_a_hint_host_and_the_page_it_is_on():
    """The hint is rendered client-side into this host, and the only thing the server tells
    it is which page the user is looking at — the catalog decides the rest."""
    html = _render("models/onboarding_drawer.html", onboarding_active=True)

    assert 'id="onboarding-hint"' in html
    assert 'data-page-id="home"' in html


def test_the_hint_host_is_gated_with_the_rest_of_the_walkthrough():
    """A user who dismissed the walkthrough must not get a hint on their next page view."""
    assert 'id="onboarding-hint"' not in _render("dashboard.html", onboarding_active=False)
    assert 'id="onboarding-hint"' in _render("dashboard.html", onboarding_active=True)


def test_the_hint_is_driven_by_the_catalog_not_by_a_page_list():
    """Source contract: the hint looks up `read_<page-id>` in the state the server sent, so a
    step added to the catalog gets a hint for free and a page with no step gets none."""
    source = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "pages" / "onboarding.js").read_text()

    assert "`read_${PAGE_ID}`" in source
    assert "if (!step || step.done) return;" in source, "a hint must disappear once its step is done"


def test_acknowledging_a_hint_is_the_only_thing_that_writes():
    """The close button retires the hint for this page view only. Ticking the step off without
    the reader having said so would make the checklist lie."""
    source = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "pages" / "onboarding.js").read_text()

    assert 'request("PATCH", { ack_hint: PAGE_ID })' in source
    assert source.count("ack_hint") == 1, "only the acknowledge button may write a hint"
    assert 'close.addEventListener("click", () => hintEl.replaceChildren());' in source


# --------------------------------------------------------------------------------------
# The spotlight (L4)
# --------------------------------------------------------------------------------------
JS = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "pages" / "onboarding.js"


def test_the_server_does_not_ask_the_drawer_to_open_itself_over_a_page():
    """The drawer is a 400 px fixed overlay on the right edge with no backdrop, and the first page
    a session renders is whatever the user asked for — a bookmarked list page as readily as the
    dashboard. Auto-opened there it covered `Create new service` and `Create custom config`
    completely; `document.elementFromPoint` at the button's centre returned the drawer, so the
    click never reached the button.

    `onboarding.js` already carries the rule this broke — `spotlight()` hides the drawer before
    pointing at anything, because the drawer covers the chrome it points at.

    The `data-autoopen` plumbing and the JS branch behind it stay (the parametrised test above
    still covers both values); what this pins is that the *server* does not request it while the
    drawer has nowhere to open into. Turning it back on is a layout change — the page must reflow
    and the navbar it would push is `position: fixed` and shared by every page — not a flag flip,
    so it should not come back by accident.
    """
    source = (Path(__file__).resolve().parents[3] / "src" / "ui" / "main.py").read_text(encoding="utf-8")
    # The whole resolve-the-flag block, not the file: `onboarding_autoopen = False` also appears
    # above it as the initialisation, and matching that one made an earlier version of this test
    # pass against every mutation put to it.
    block = source.split("if onboarding_active is None:", 1)[1].split("# The post-upgrade recap", 1)[0]
    assignments = re.findall(r"onboarding_autoopen\s*=\s*(.+)", block)

    assert assignments == ["False"], f"the server computes auto-open again: {assignments}"


def test_the_spotlight_is_opt_in_and_survives_a_missing_anchor():
    """Nothing spotlights itself, and an anchor a refactor deleted must be a dead button, not
    a thrown exception that takes the rest of the drawer down with it."""
    source = JS.read_text()

    assert 'show.addEventListener("click", () => spotlight(step));' in source
    assert "if (!target) return;" in source
    assert "setTimeout(clear, 8000)" in source, "a highlight left on the chrome forever is litter"


def test_the_spotlight_gets_the_drawer_out_of_its_own_way():
    """The offcanvas covers the sidebar it is pointing at."""
    source = JS.read_text()

    hide = source.index("instance.hide();", source.index("function spotlight"))
    point = source.index('target.classList.add("bw-tour-target")')
    assert hide < point


def test_the_spotlight_respects_reduced_motion():
    source = JS.read_text()

    assert '"(prefers-reduced-motion: reduce)"' in source
    assert 'behavior: reduced ? "auto" : "smooth"' in source


def test_the_highlight_cannot_shift_the_chrome_it_highlights():
    """A border would resize the nav entry and push everything below it down."""
    css = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "css" / "overrides.css").read_text()
    rule = css.split(".bw-tour-target {", 1)[1].split("}", 1)[0]

    assert "outline:" in rule
    assert "border:" not in rule


# --------------------------------------------------------------------------------------
# What a browser found that no render test could
# --------------------------------------------------------------------------------------
def test_copy_never_renders_a_blank_row():
    """The drawer once rendered six blank rows: i18next answered "" for every key until its
    catalog had loaded, and `defaultValue` did not save you. The catalog is a global loaded ahead
    of this file now, so there is nothing to wait for — but an empty answer still has to lose to
    the English fallback, which is the half of that fix that is still load-bearing."""
    source = JS.read_text()

    guard = source.split("const t = (key, fallback)", 1)[1].split("};", 1)[0]
    assert "if (!window.t) return fallback;" in guard
    assert 'return typeof value === "string" && value ? value : fallback;' in guard
    assert "i18nextReady" not in source, "nothing sets that flag any more; waiting on it never resolves"


def test_an_optional_step_says_so_while_it_is_still_pending():
    """The chip used to be the `else` branch of the Go link, so the one moment it mattered —
    a pending optional step — was the one moment it never rendered."""
    source = JS.read_text()
    chip_block = source.split("if (step.optional) {", 1)[1].split('t("status.optional"', 1)[0]

    assert "step.done" not in chip_block, "the chip must not depend on completion"


def test_both_floating_surfaces_follow_the_theme():
    """Sneat pins popover and toast backgrounds to white in both themes while the text colour
    follows the theme: dark mode rendered white on white, twice."""
    css = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "css" / "overrides.css").read_text()
    source = JS.read_text()

    toast = css.split("#onboarding-hint .toast {", 1)[1].split("}", 1)[0]
    assert "var(--bs-body-bg)" in toast and "var(--bs-body-color)" in toast

    popover = css.split(".bw-tour-popover {", 1)[1].split("}", 1)[0]
    assert "--bs-popover-bg: var(--bs-body-bg)" in popover
    assert 'customClass: "bw-tour-popover"' in source, "the rule only applies if the popover carries the class"
