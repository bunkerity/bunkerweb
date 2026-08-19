"""The recap's two surfaces: the modal raised after an upgrade and the permanent page.

The modal is gated on `whatsnew_releases` being non-empty — the same value the silent-stamp
rule produces — so the gate is asserted in both directions here. A caught-up user must download
neither the markup nor the script.
"""

from pathlib import Path
from types import SimpleNamespace

from conftest import english  # what a converted template renders for a key
from jinja2 import ChainableUndefined, ChoiceLoader, DictLoader, Environment, FileSystemLoader

from app.models.changelog import Entry, Release, render_inline

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"
JS = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "pages" / "whats-new.js"

STUBS = {
    "base.html": "{% block head %}{% endblock %}{% block page %}{% endblock %}",
    "dashboard.html": "{% block head %}{% endblock %}{% block page_head %}{% endblock %}{% block content %}{% endblock %}",
    "language-selector.html": "",
    "menu.html": "",
    "footer.html": "",
    "sidebar-notifications.html": "",
    "sidebar-news.html": "",
    "models/mode_pills.html": "",
}

RELEASES = (
    Release(version="v1.7.0", date="2026/07/??", entries=(Entry(tag="FEATURE", html=render_inline("something `new`")),)),
    Release(version="v1.6.14", date="2026/07/01", entries=(Entry(tag="SECURITY", html=render_inline("something fixed")),)),
)


def _render(template, without=(), **context):
    """`without` names the stubs to drop, so a test can render the real template it is about."""
    stubs = {name: body for name, body in STUBS.items() if name not in without}
    loaders = [DictLoader(stubs), FileSystemLoader(TEMPLATES)]
    env = Environment(loader=ChoiceLoader(loaders), autoescape=True, undefined=ChainableUndefined)
    env.globals.update(
        csrf_token=lambda: "t",
        url_for=lambda endpoint, **kwargs: "/" + "/".join([endpoint, *kwargs.values()]),
        current_user=SimpleNamespace(is_authenticated=True, admin=True, get_id=lambda: "alice", list_roles=["admin"], list_permissions=["read", "write"]),
        request=SimpleNamespace(path="/home", endpoint="home.home_page", args={}, values={}, blueprint="home"),
    )
    base = {"theme": "light", "script_nonce": "n", "style_nonce": "n", "bw_version": "1.7.0"}
    base.update(context)
    return env.get_template(template).render(**base)


# --------------------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------------------
def test_a_caught_up_user_gets_neither_the_modal_nor_its_script():
    html = _render("dashboard.html", without=("dashboard.html",), whatsnew_releases=())

    assert 'id="whats-new-modal"' not in html
    assert "js/pages/whats-new.js" not in html


def test_a_user_with_releases_to_see_gets_both():
    html = _render("dashboard.html", without=("dashboard.html",), whatsnew_releases=RELEASES)

    assert 'id="whats-new-modal"' in html
    assert "js/pages/whats-new.js" in html


# --------------------------------------------------------------------------------------
# The modal
# --------------------------------------------------------------------------------------
def test_the_modal_lists_every_release_in_the_interval():
    html = _render("models/whats_new_modal.html", whatsnew_releases=RELEASES)

    assert "v1.7.0" in html
    assert "v1.6.14" in html
    assert "something <code>new</code>" in html, "changelog markup is rendered, not shown raw"
    assert "FEATURE" in html and "SECURITY" in html


def test_the_modal_can_be_left_without_losing_anything():
    """Dismissing is a decision about a modal, not about the release notes."""
    html = _render("models/whats_new_modal.html", whatsnew_releases=RELEASES)

    assert english("button.see_all_releases") in html
    assert "/whats_new.whats_new_page" in html


def test_the_modal_is_dismissible_rather_than_a_wall():
    """`static_backdrop=false`: a click outside closes it, and closing stamps."""
    html = _render("models/whats_new_modal.html", whatsnew_releases=RELEASES)

    assert 'data-bs-backdrop="static"' not in html
    assert 'data-bs-dismiss="modal"' in html


def test_the_stamp_target_and_version_reach_the_script():
    html = _render("models/whats_new_modal.html", whatsnew_releases=RELEASES)

    assert 'data-state-url="/whats_new.update_whats_new_state"' in html
    assert 'data-version="1.7.0"' in html


# --------------------------------------------------------------------------------------
# The permanent page
# --------------------------------------------------------------------------------------
def test_the_page_shows_every_release_with_the_newest_open():
    html = _render("whats_new.html", releases=RELEASES, changelog_missing=False)

    assert 'aria-expanded="true"' in html
    assert html.count('data-bs-toggle="collapse"') == len(RELEASES)


def test_a_build_without_a_changelog_says_so_instead_of_showing_an_empty_page():
    html = _render("whats_new.html", releases=(), changelog_missing=True)

    assert english("whatsnew.missing_title") in html
    assert "github.com/bunkerity/bunkerweb/blob/master/CHANGELOG.md" in html


def test_the_version_in_the_sidebar_is_the_way_in():
    """No new nav entry: an operator looks for what changed under the version it is running."""
    html = _render("menu.html", without=("menu.html",), plugins={}, extra_pages=[], current_endpoint="home", is_pro_version=False, pro_diamond_url="/d.svg")

    assert "/whats_new.whats_new_page" in html


# --------------------------------------------------------------------------------------
# The script
# --------------------------------------------------------------------------------------
def test_any_way_of_closing_the_modal_counts_as_seen():
    """Escape, the cross, the backdrop and the button all mean the same thing."""
    source = JS.read_text()

    assert 'modalEl.addEventListener("hidden.bs.modal"' in source
    assert '"PATCH"' in source


def test_a_failed_stamp_lets_the_recap_come_back():
    source = JS.read_text()

    assert "stamped = false;" in source, "a lost stamp must not be recorded as done"


def test_a_long_recap_scrolls_inside_the_dialog():
    """A release with 50 entries otherwise pushes the footer buttons below the fold and
    scrolls the page behind the backdrop instead of the body."""
    html = _render("models/whats_new_modal.html", whatsnew_releases=RELEASES)

    assert "modal-dialog-scrollable" in html


def test_long_setting_names_wrap_instead_of_widening_the_dialog():
    """`METRICS_BASELINE_RETENTION_MAX_ROWS` in a `code` span made the modal scroll sideways."""
    css = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "css" / "overrides.css").read_text()
    html = _render("models/whats_new_modal.html", whatsnew_releases=RELEASES)

    assert "release-notes" in html
    assert "overflow-wrap: anywhere" in css.split(".release-notes code {", 1)[1].split("}", 1)[0]
