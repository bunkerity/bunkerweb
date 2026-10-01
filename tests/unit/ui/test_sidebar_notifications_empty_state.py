"""M19: after "Clear All", the notifications drawer must be able to show its empty state.

`sidebar-notifications.html` used to render *either* the toast container *or* the empty-state
paragraph (`{% if flash_messages %}...{% else %}<p>...</p>{% endif %}`) -- never both. Clearing
notifications is a client-side action (`static/js/utils.js:clearNotifications`): it empties the
toast container, then reveals the empty-state paragraph by removing `d-none` from
`#data-notifications-container p[data-i18n='status.no_notifications']`. That selector matched
nothing whenever the page had started with messages present, because the server never rendered
that paragraph into the DOM at all in that branch -- there was nothing to reveal.

The fix's first pass used `data-i18n` as the JS hook and broke
`test_i18n_migration.py::test_a_converted_template_has_no_client_side_translation_left` --
`data-i18n` is reserved for markup a script builds itself, never server-rendered copy (see that
file and `i18n.js`'s own comments); this file is server-translated. The hook is a plain `id`
instead, `#notifications-empty-state`.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"


def _render(flash_messages):
    environment = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    environment.globals.setdefault("url_for", lambda endpoint, **values: f"/{endpoint}")
    return environment.get_template("sidebar-notifications.html").render(
        theme="light",
        script_nonce="nonce",
        flash_messages=flash_messages,
        dismissed_notices={"newsletter": True},
    )


def test_the_empty_state_paragraph_is_always_in_the_dom():
    """Present (and addressable by `static/js/utils.js`'s selector) whether or not there are
    messages at render time -- only its visibility, via `d-none`, should depend on that."""
    with_messages = _render([("hi", "message", "2026-01-01T00:00:00")])
    without_messages = _render([])

    for html in (with_messages, without_messages):
        assert 'id="notifications-empty-state"' in html
        assert 'id="notifications-toast-container"' in html


def test_the_empty_state_starts_hidden_when_there_are_messages():
    html = _render([("hi", "message", "2026-01-01T00:00:00")])

    empty_state_start = html.index('id="notifications-empty-state"')
    tag_start = html.rindex("<p", 0, empty_state_start)
    tag = html[tag_start : html.index(">", empty_state_start)]

    assert "d-none" in tag
    assert 'id="notifications-toast-container"' in html
    toast_container_tag = html[html.index('id="notifications-toast-container"') - 200 : html.index('id="notifications-toast-container"')]
    assert "d-none" not in toast_container_tag


def test_the_toast_container_starts_hidden_when_there_are_no_messages():
    html = _render([])

    toast_start = html.index('id="notifications-toast-container"')
    tag = html[html.rindex("<div", 0, toast_start) : html.index(">", toast_start)]

    assert "d-none" in tag


def test_the_empty_state_hook_is_not_a_client_side_translation_marker():
    """This file is server-translated (`_()`); `data-i18n*` is only for markup a script builds
    itself. Regression guard for the fix's own first, wrong attempt."""
    source = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates" / "sidebar-notifications.html").read_text(encoding="utf-8")

    assert "data-i18n" not in source


def test_the_clear_all_js_targets_the_id_not_a_data_i18n_selector():
    source = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "static" / "js" / "utils.js").read_text(encoding="utf-8")

    assert '$("#notifications-empty-state")' in source
    assert "data-i18n" not in source[source.index("clearNotifications") : source.index("clearNotifications") + 1500]
