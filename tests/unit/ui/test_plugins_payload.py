"""The shared `plugins` context: who reads what off it, and what it therefore has to carry.

`/plugins?type=all` is the single most expensive call in a page render — 228 KB and ~30 ms on a
stock install, of which the declared settings schema is 216 KB. It is fetched once per render,
on every page, and almost every page only wants the plugin *names* for the sidebar.

So the shared context asks for identities only, except on the pages listed in
`SETTINGS_HUNGRY_PATH_PREFIXES`. That split is only safe while the list and the templates agree,
and a template that reads settings from a page not on the list fails *silently* — an empty
shelf, a missing button — which is exactly the failure a test has to catch instead.
"""

import re
from pathlib import Path

from app.utils import SETTINGS_HUNGRY_PATH_PREFIXES

UI = Path(__file__).resolve().parents[3] / "src" / "ui"
TEMPLATES = UI / "app" / "templates"

# Every template that reads the shared `plugins` context, and the page prefix it renders under.
# None = it reads identities only (name, type, icon, page), so it works on every page.
CONSUMERS = {
    "menu.html": None,  # the sidebar plugin list — names and types
    "models/template_steps_body.html": None,  # the template editor's plugin badge
    "plugins.html": "/plugins",  # the grid's "manage activation" gate
    "models/compose_shelf.html": "/services",  # the shelf rows, one per plugin with settings
    "models/plugins_settings_raw.html": "/services",  # the raw pane walks every declared key
    "models/request_path_strip.html": "/services",  # the strip's per-plugin settings lookup
}

# `plugin_data["settings"]` / `plugin_data.get('settings', ...)` — a read of the schema off a
# plugin. Only meaningful in a template that took its plugin from the shared context: a page
# that resolves one itself (plugin_settings_page.html, via `resolve_plugin` on the route's own
# full `get_plugins()`) is unaffected by what the context carries.
SCHEMA_READ = re.compile(r"""plugin_data\s*(?:\[|\.get\()\s*["']settings["']""")
# Any use of the shared context var at all — `.items()`, `.values()`, a subscript, anything.
CONTEXT_USE = re.compile(r"""\bplugins\s*(?:\.\w+\(|\[)""")


def _templates():
    for path in sorted(TEMPLATES.rglob("*.html")):
        yield str(path.relative_to(TEMPLATES)), path.read_text()


def _uncommented(source):
    """Jinja comments carry a lot of prose in this codebase, including the very patterns this
    file greps for. Strip them or the header of compose_shelf.html registers as five consumers."""
    return re.sub(r"\{#.*?#\}", "", source, flags=re.DOTALL)


def test_every_reader_of_the_shared_plugins_context_is_accounted_for():
    """A new template reading `plugins` is the moment to decide whether its page needs the
    schema. Left undecided, it renders empty and nothing complains."""
    found = {name for name, source in _templates() if CONTEXT_USE.search(_uncommented(source))}

    assert found == set(CONSUMERS), f"unaccounted readers: {sorted(found - set(CONSUMERS))}, gone: {sorted(set(CONSUMERS) - found)}"


def test_every_page_that_renders_a_settings_schema_asks_for_one():
    """The list in `app/utils.py` is what makes the slim payload safe; this is the check that
    it still covers every template that needs the schema."""
    for name, source in _templates():
        source = _uncommented(source)
        if not (SCHEMA_READ.search(source) and CONTEXT_USE.search(source)):
            continue
        prefix = CONSUMERS.get(name)
        assert prefix is not None, f"{name} reads a settings schema but is declared identities-only"
        assert prefix in SETTINGS_HUNGRY_PATH_PREFIXES, f"{name} renders under {prefix}, which is not in SETTINGS_HUNGRY_PATH_PREFIXES"


def test_the_identity_only_readers_really_are_identity_only():
    """The other half of the same guard: a template declared cheap must stay cheap, or every
    page it appears on quietly goes back to paying 216 KB."""
    for name, prefix in CONSUMERS.items():
        if prefix is not None:
            continue
        source = _uncommented((TEMPLATES / name).read_text())
        assert not SCHEMA_READ.search(source), f"{name} is on every page — it cannot read the settings schema"


def test_the_shared_context_asks_for_the_slim_shape_off_the_hungry_pages():
    source = (UI / "main.py").read_text()

    assert "BW_CONFIG.get_plugins(with_settings=request.path.startswith(SETTINGS_HUNGRY_PATH_PREFIXES))" in source


def test_the_pages_that_need_the_schema_are_the_ones_that_render_it():
    """Recorded so shrinking the list is a deliberate act: dropping a prefix here is what makes
    a settings page render empty."""
    assert SETTINGS_HUNGRY_PATH_PREFIXES == ("/global-config", "/global-settings", "/services", "/plugins")


def test_the_client_only_sends_the_flag_when_it_is_turning_the_schema_off():
    """`with_settings` defaults to true API-side; sending it on every call would put a
    meaningless parameter in every access log line and in the per-request memo's key."""
    source = (UI / "app" / "api_client.py").read_text()

    assert 'if not with_settings:\n            params["with_settings"] = "false"' in source
