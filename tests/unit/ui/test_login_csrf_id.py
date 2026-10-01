"""B3: the language switcher on the login and TOTP pages silently did nothing.

`i18n.js:227` reads the CSRF token via `$("#csrf_token").val()` -- every other CSRF-bearing form
in this codebase gives that hidden input `id="csrf_token"` for exactly this reason (see
`navbar.html`, `pro.html`, `config_edit.html`, `template_edit.html`, `plugins.html`, ...). `login.html`
and `totp.html` were the two outliers: a bare `name="csrf_token"` with no `id`, so the jQuery
selector found nothing, `saveLanguage()` logged "CSRF token not found" and returned without ever
posting to `/set_language` -- the switch silently no-opped.
"""

from pathlib import Path

import pytest

from test_auth_shell import _render

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"


@pytest.mark.parametrize("page", ["login.html", "totp.html"])
def test_the_csrf_input_has_the_id_i18n_js_reads(page):
    html = _render(page)

    assert 'id="csrf_token"' in html, f"{page}: i18n.js's $('#csrf_token') finds nothing without it"


@pytest.mark.parametrize("page", ["login.html", "totp.html"])
def test_the_csrf_input_is_still_posted_by_name(page):
    """The id is additive -- the form still needs to submit the token under Flask-WTF's expected
    field name."""
    html = _render(page)

    assert 'name="csrf_token"' in html


@pytest.mark.parametrize("page", ["login.html", "totp.html"])
def test_exactly_one_csrf_id_on_the_page(page):
    """A duplicate id would make the jQuery selector ambiguous again in a different way."""
    html = _render(page)

    assert html.count('id="csrf_token"') == 1
