"""The shared full-screen auth shell used by login, TOTP and the setup wizard.

`c074b46fe` reskinned login and TOTP onto the design-kit `setup-screen` shell but left the
setup wizard on the legacy chrome, so the install flow changed appearance halfway through.
The wizard now uses the same shell, and the decoration the three pages share lives in one
partial instead of three inlined copies.

Render tests follow ``test_bans_stats.py``'s standalone-Jinja-env pattern. ``ChainableUndefined``
stands in for the ~25 context keys the setup route passes; none of them drive the chrome.
"""

from pathlib import Path

import pytest
from jinja2 import ChainableUndefined, ChoiceLoader, DictLoader, Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"
STATIC = TEMPLATES.parent / "static"

AUTH_PAGES = ("login.html", "totp.html", "setup.html")
DECO_PARTIAL = "components/auth-deco.html"


def _render(template, **context):
    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader(
                    {
                        "base.html": "{% block head %}{% endblock %}{% block page %}{% endblock %}",
                        "language-selector.html": '<div class="lang-sel">EN</div>',
                    }
                ),
                FileSystemLoader(TEMPLATES),
            ]
        ),
        autoescape=True,
        undefined=ChainableUndefined,
    )
    env.globals.update(
        csrf_token=lambda: "test-token",
        url_for=lambda endpoint, **kwargs: "/" + "/".join([endpoint, *kwargs.values()]),
        current_user=type("_User", (), {"is_authenticated": False})(),
        request=type("_Request", (), {"values": {}, "args": {}, "path": "/"})(),
    )
    # `plugins_settings` is a real dict the wizard calls `.get()` on, so ChainableUndefined
    # cannot stand in for it. Everything else the route passes only feeds step content.
    base = {"theme": "light", "style_nonce": "nonce", "script_nonce": "nonce", "plugins_settings": {}}
    base.update(context)
    return env.get_template(template).render(**base)


# --------------------------------------------------------------------------------------
# The shared decoration partial
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("page", AUTH_PAGES)
def test_every_auth_page_includes_the_shared_deco_partial(page):
    """A suite that renders the partial directly cannot see a page dropping the include."""
    source = (TEMPLATES / page).read_text(encoding="utf-8")

    assert f'{{% include "{DECO_PARTIAL}" %}}' in source


@pytest.mark.parametrize("page", AUTH_PAGES)
def test_no_auth_page_inlines_its_own_copy_of_the_decoration(page):
    """Three inlined copies is what the partial replaced; they drifted apart silently."""
    source = (TEMPLATES / page).read_text(encoding="utf-8")

    assert 'class="sw-deco sw-hatch"' not in source


@pytest.mark.parametrize("page", AUTH_PAGES)
def test_the_decoration_actually_reaches_the_rendered_page(page):
    """Proves the include resolves, not just that the line is present in the source."""
    html = _render(page)

    assert 'class="sw-deco sw-hatch"' in html
    assert 'class="sw-deco sw-poly"' in html


def test_the_decoration_is_hidden_from_assistive_technology():
    html = _render(DECO_PARTIAL)

    assert html.count('aria-hidden="true"') == html.count("sw-deco")


# --------------------------------------------------------------------------------------
# The setup wizard on the shared shell
# --------------------------------------------------------------------------------------
def test_setup_wizard_uses_the_same_full_screen_shell_as_login():
    html = _render("setup.html")

    assert '<div class="setup-screen">' in html
    # The legacy shell it replaces.
    assert "theme-bg-surface" not in html
    assert "login-background" not in html


def test_setup_wizard_adopts_the_kit_title_and_wand():
    """`sw-title` and `sw-wand` were shipped in login.css for this page and used by nothing."""
    html = _render("setup.html")

    assert 'class="sw-title"' in html
    assert "sw-wand" in html
    # The legacy title/brand chrome is gone.
    assert "card-title" not in html
    assert "app-brand-logo" not in html


def test_setup_wizard_loads_both_the_kit_shell_and_the_legacy_layout_sheet():
    """auth-legacy.css still owns the wrapper that centres the wizard column. Dropping it
    is not a cleanup — it silently changes the wizard's layout."""
    html = _render("setup.html")

    assert "css/pages/login.css" in html
    assert "css/pages/auth-legacy.css" in html


# --------------------------------------------------------------------------------------
# The two CSS rules that only exist because the wizard mixes both sheets
# --------------------------------------------------------------------------------------
def test_kit_shell_switches_off_the_legacy_ornaments():
    """Both sheets paint decorations; without this the wizard renders two ornament sets."""
    css = (STATIC / "css" / "pages" / "login.css").read_text(encoding="utf-8")

    assert ".setup-screen .authentication-inner::before" in css
    assert ".setup-screen .authentication-inner::after" in css


def test_vertical_tagline_is_dropped_on_the_full_width_wizard():
    """It is positioned in a 78px gutter that only exists beside the narrow login card."""
    css = (STATIC / "css" / "pages" / "login.css").read_text(encoding="utf-8")

    assert ".setup-screen:has(.authentication-wrapper) .sw-vertical-text" in css
