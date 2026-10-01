"""FIX-D addendum (from FIX-H's M26 review): `login.html`'s docs link never picked up the
resolved language.

`macros/docs_link.html`'s `docs_url` reads `language` and `bw_version` off the *calling
template's* render context -- but a Jinja macro import sees none of that context unless it says
`with context`. `login.html` imported the macro without it (`{% from 'macros/docs_link.html'
import docs_url %}`), so inside the macro `language` was always `Undefined`, and the troubleshooting
link never got its `/fr`, `/de`, `/es`, `/zh` prefix on the login page, whatever locale it rendered
in. `totp.html` does not use the macro at all, so it needed no change.
"""

from pathlib import Path

from test_auth_shell import _render

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"


def test_the_macro_import_carries_context():
    source = (TEMPLATES / "login.html").read_text(encoding="utf-8")

    assert "{% from 'macros/docs_link.html' import docs_url with context %}" in source


def test_the_docs_link_picks_up_the_resolved_language():
    html = _render("login.html", language="fr")

    assert 'href="https://docs.bunkerweb.io/latest/fr/troubleshooting/' in html


def test_the_docs_link_has_no_prefix_for_english():
    html = _render("login.html", language="en")

    assert 'href="https://docs.bunkerweb.io/latest/troubleshooting/' in html
    assert "/latest/en/troubleshooting" not in html
