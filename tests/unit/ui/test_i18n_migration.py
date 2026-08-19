"""Which templates have been converted to server-side translation, and the rules they follow.

Native i18n moves translation from the browser to the server one template at a time. A converted
template renders `{{ _('some.key') }}` and arrives translated; an unconverted one still carries
`data-i18n` and is rewritten by i18next after paint. Both are correct — but a template that is
*half* converted is not, and nothing about it looks wrong in a diff.

So the set of converted templates is written down here. Adding a `data-i18n` back to one fails;
converting a new one without listing it fails.
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "src" / "ui" / "app" / "templates"

# Every template renders through Flask-Babel and must contain no `data-i18n*` attribute at all.
# This used to be a hand-maintained list of the ones already converted; Lot C finished the
# migration, so the list is the directory itself and what is written down is the *exemption*
# below -- the handful that render no copy of their own.
EVERY_TEMPLATE = tuple(sorted(str(path.relative_to(TEMPLATES)) for path in TEMPLATES.rglob("*.html")))

# The attributes i18next reads. A converted template may use none of them.
CLIENT_SIDE_MARKERS = ("data-i18n", "data-i18n-options", "data-i18n-attr", "data-i18n-aria-label", "data-i18n-title", "data-i18n-placeholder")


def _function_body(source, opening, closing):
    """One function's source. Extracted rather than sliced inline: black wants spaces around a
    slice built from expressions, and flake8 rejects them (E203)."""
    start = source.index(opening)
    end = source.index(closing, start)
    return source[start:end]


def _markup(name):
    """Template source with Jinja comments stripped — several of them discuss `data-i18n` by
    name, and a comment translates nothing."""
    from re import DOTALL, sub

    return sub(r"\{#.*?#\}", "", (TEMPLATES / name).read_text(encoding="utf-8"), flags=DOTALL)


@pytest.mark.parametrize("name", EVERY_TEMPLATE)
def test_a_converted_template_has_no_client_side_translation_left(name):
    """Mixing the two in one file is how a page ends up half-translated after a language switch:
    i18next rewrites its half, the server-rendered half keeps whatever it was rendered with."""
    markup = _markup(name)

    for marker in CLIENT_SIDE_MARKERS:
        assert marker not in markup, f"{name} still uses {marker}"


# A handful of shared macros render no human-readable copy of their own -- a chart canvas, a
# code editor host, the auth page's decorative SVG. They are converted (nothing client-side is
# left in them) but there is nothing in them to translate.
NO_COPY_OF_THEIR_OWN = {
    "base.html",  # the document shell: <head>, asset tags, block placeholders
    "global_settings.html",  # a mount point; every string comes from the settings partials
    "language-selector.html",  # each language is named in its own language, never translated
    "macros/docs_link.html",  # builds a URL and takes its label from the caller
    "reports.html",  # panes are filled by reports-*.js; its one literal is the required DB-IP
    # attribution, which is a vendor credit rather than copy
    "components/auth-deco.html",
    "components/chart-area.html",
    "components/chart-donut.html",
    "components/code-editor.html",
    "components/geo-map.html",
    "components/lottie.html",
    "components/release-notes.html",
    # every <option> it emits is a service name -- data, and never translated
    "components/service-options.html",
    "components/timeline.html",
}


@pytest.mark.parametrize("name", EVERY_TEMPLATE)
def test_a_converted_template_actually_translates(name):
    """The other half of the check: a template with no `data-i18n` *and* no `_()` is not
    converted, it is untranslated."""
    if name in NO_COPY_OF_THEIR_OWN:
        pytest.skip("renders no copy of its own")
    assert "_(" in _markup(name), f"{name} has no gettext calls"


def test_the_no_copy_list_does_not_outlive_its_templates():
    """A stale exemption is how a template silently stops being checked."""
    missing = sorted(name for name in NO_COPY_OF_THEIR_OWN if name not in EVERY_TEMPLATE)

    assert not missing, f"listed as copy-free but no longer converted: {missing}"


def test_the_switcher_reloads_so_both_halves_stay_in_step():
    """A converted template is rendered once, by the server. The language switcher used to change
    i18next's language in place and never reload, which would leave every converted element in
    the previous language until the next navigation."""
    source = (REPO / "src" / "ui" / "app" / "static" / "js" / "i18n.js").read_text(encoding="utf-8")
    switch = _function_body(source, "function changeLanguage", "\n}")

    assert "window.location.reload()" in switch
    assert "saveLanguage(" in switch, "the reload has to wait for the server to record the choice"


def test_the_switcher_only_reloads_once_the_server_agrees():
    """Reloading on a failed request would re-render in the *old* language and look like the
    switch silently did nothing."""
    source = (REPO / "src" / "ui" / "app" / "static" / "js" / "i18n.js").read_text(encoding="utf-8")

    assert "if (recorded) window.location.reload();" in source


def test_the_save_refuses_nobody():
    """`saveLanguage` used to return early on a read-only database, and again on the setup wizard.
    Both were wrong once the page stopped being translated in the browser: this endpoint is the
    only way the server learns the choice, and it needs neither an account nor a writable database
    — only a session. Refusing either left that user stuck in one language for good."""
    source = (REPO / "src" / "ui" / "app" / "static" / "js" / "i18n.js").read_text(encoding="utf-8")
    save = _function_body(source, "function saveLanguage", "\n}\n")

    assert "dbReadOnly" not in save
    assert "isSetup" not in save


def test_the_switcher_still_has_an_endpoint_where_there_is_no_navigation():
    """The URL is derived from the home link, which the setup wizard does not render — deriving it
    from an empty value used to throw before the request was ever made."""
    source = (REPO / "src" / "ui" / "app" / "static" / "js" / "i18n.js").read_text(encoding="utf-8")

    assert 'const homePath = $("#home-path").val();' in source
    assert ': "/set_language";' in source


# --------------------------------------------------------------------------------------
# The keys the converted templates build at render time
# --------------------------------------------------------------------------------------
def test_every_navigation_key_the_menu_can_build_exists():
    """`menu.html` composes keys (`"navigation." ~ endpoint`), so no static check — neither
    `pybabel extract` nor a grep — can see them. A missing one renders as the raw key in the
    sidebar of every page.
    """
    import json
    import re

    catalog = json.loads((TEMPLATES.parent / "static" / "locales" / "en.json").read_text(encoding="utf-8"))

    def flatten(node, prefix=""):
        for key, value in node.items():
            if isinstance(value, dict):
                yield from flatten(value, f"{prefix}{key}.")
            else:
                yield f"{prefix}{key}"

    keys = set(flatten(catalog))
    menu = (TEMPLATES / "menu.html").read_text(encoding="utf-8")

    groups = re.findall(r'"header": "(\w+)"', menu)
    endpoints = re.findall(r'^\s+"([a-z-]+)": \{"url"', menu, re.MULTILINE)
    assert groups and len(endpoints) > 15, "the menu structure moved; this test is reading nothing"

    expected = {f"navigation.{group}" for group in groups}
    expected |= {f"navigation.{endpoint.replace('-', '_')}" for endpoint in endpoints}
    expected |= {"navigation.edition_pro", "navigation.edition_community"}

    assert expected <= keys, f"missing from en.json: {sorted(expected - keys)}"
