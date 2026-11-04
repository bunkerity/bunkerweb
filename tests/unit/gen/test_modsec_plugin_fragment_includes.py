"""The ModSecurity rules file probes the tree the SAME render is writing -- pin that.

``modsecurity-rules.conf.modsec`` emits two families of ``include`` lines, and only the first one
is about the operator's custom configs:

* ``/etc/bunkerweb/configs/<type>[/<service>]`` -- what ``push-configs`` materialises from the
  database (``_materialize_custom_configs``) and ships to every instance as ``/custom_configs``;
* ``/etc/nginx/<type>`` (single-site) / ``/etc/nginx/<service>/<type>`` (multisite) -- the
  ``modsec/`` and ``modsec-crs/`` fragments **core plugins ship as templates**
  (``antibot/confs/modsec-crs/antibot.conf``, ``modsecurity/confs/modsec-crs/http3.conf``,
  ``ui/confs/modsec/ui.conf``, ``ui/confs/modsec-crs/ui.conf``), which this very render writes into
  its own output directory.

The second family only works because of an ordering contract inside ``_render_server``: the
``modsec`` and ``modsec-crs`` contexts come before ``server-http`` in the list handed to
``_find_templates``, so the fragments are on disk by the time the rules file globs for them.
Reorder that list and every one of those includes silently disappears -- no error, no log line,
and the UI's CRS exclusions (``ui.conf``) plus the antibot challenge allow-rule stop loading.

``is_custom_conf`` globs the literal ``/etc/nginx``, so the probe is only self-consistent while
``gen/main.py`` renders with ``--output /etc/nginx`` -- which every call site does
(``push-configs.py:374`` on the worker, and the default for ``bw/entrypoint.sh:140`` /
``linux/scripts/start.sh:228``). The tests below redirect that literal onto the sandbox output
directory, which is exactly what a real deployment does by making the two paths the same.

**Scope, stated so it is not over-read: this file pins the ORDER, not that coupling.** The redirect
above is precisely the output-relative probe a fix for the coupling would install, so a render that
moved ``--output`` elsewhere -- the staging-directory idea in ``report-W1.md`` -- would keep every
test here green while production silently emitted none of these includes. Pinning the coupling needs
the probe itself to become output-relative first.

Second uncovered break vector, same contract: ``_find_templates`` memoises on
``frozenset(contexts)`` (``Templator.py:752-778``) while promising its result "in the same order as
contexts". Inert today -- the two call sites pass disjoint context sets -- but a third one passing
these same six in another order would serve the first caller's ordering to both, and nothing here
would notice.
"""

import logging
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"
CORE = ROOT / "src" / "common" / "core"
SETTINGS = ROOT / "src" / "common" / "settings.json"

RULES = "server-http/modsecurity-rules.conf.modsec"


@pytest.fixture
def render_server(tmp_path, monkeypatch):
    """``render_server(**variables) -> output Path``, one server rendered, no process pool.

    ``Templator.render()`` fans the per-server pass out over a ``ProcessPoolExecutor``;
    ``_render_server`` is called directly instead so the redirected probe below needs no pickling.
    The pass under test is the same one either way.
    """
    import Templator as T  # type: ignore  (src/common/gen is on sys.path, see conftest)
    from Configurator import Configurator  # type: ignore

    output = tmp_path / "out"
    output.mkdir()
    custom_configs = tmp_path / "custom-configs"
    custom_configs.mkdir()

    def probe(path: str) -> bool:
        """``is_custom_conf`` with both probed roots pointing inside the sandbox.

        ``/etc/nginx`` -> this render's output directory, which is what a real deployment achieves
        by making the two the same path. ``/etc/bunkerweb/configs`` -> an empty sandbox directory,
        because a unit test must not read ``/etc``: that directory exists on any host with a Linux
        package installed (and on this repo's workstation), so a single ``.conf`` left in it by an
        unrelated install would turn the family-1 assertions below into false reds.
        """
        for literal, sandbox in (("/etc/nginx", output), ("/etc/bunkerweb/configs", custom_configs)):
            if path == literal or path.startswith(literal + "/"):
                path = str(sandbox / path[len(literal) :].lstrip("/"))  # noqa: E203
                break
        return bool(list(Path(path).glob("*.conf"))) if Path(path).is_dir() else False

    # Before the constructor: `_base_template_vars` captures the attribute at __init__ time.
    monkeypatch.setattr(T.Templator, "is_custom_conf", staticmethod(probe))
    # Same trick as `render_tree` in conftest: `sep` is the module's only use of os.path.sep and
    # it is what roots the Jinja bytecode cache, so rebinding it keeps the render out of /var/cache.
    monkeypatch.setattr(T, "sep", str(tmp_path))

    plugins = tmp_path / "plugins"
    plugins.mkdir()
    pro_plugins = tmp_path / "pro-plugins"
    pro_plugins.mkdir()

    def _render(**variables):
        config = Configurator(str(SETTINGS), str(CORE), str(plugins), str(pro_plugins), dict(variables), logging.getLogger("modsec-render")).get_config(None)
        templator = T.Templator(str(CONFS), str(CORE), str(plugins), str(pro_plugins), str(output), "/etc/nginx", config, config.copy(), config.copy())
        templator._render_server(variables["SERVER_NAME"].split()[0])
        return output

    _render.custom_configs = custom_configs
    return _render


def test_single_site_rules_include_the_plugin_fragments_this_render_wrote(render_server):
    output = render_server(SERVER_NAME="www.example.com", MULTISITE="no", USE_MODSECURITY="yes", USE_MODSECURITY_CRS="yes")

    assert (output / "modsec-crs" / "antibot.conf").is_file(), "the plugin fragment itself was never rendered"
    rules = (output / RULES).read_text()

    assert "include /etc/nginx/modsec-crs/*.conf" in rules, "the CRS exclusions core plugins ship are not loaded"
    assert "include /etc/nginx/modsec/*.conf" in rules, "the after-CRS rules core plugins ship are not loaded"


def test_multisite_rules_include_the_service_s_own_plugin_fragments(render_server):
    output = render_server(SERVER_NAME="app1.example.com", MULTISITE="yes", USE_MODSECURITY="yes", USE_MODSECURITY_CRS="yes")

    assert (output / "app1.example.com" / "modsec-crs" / "antibot.conf").is_file()
    rules = (output / "app1.example.com" / RULES).read_text()

    assert "include /etc/nginx/app1.example.com/modsec-crs/*.conf" in rules
    assert "include /etc/nginx/app1.example.com/modsec/*.conf" in rules


def test_the_custom_config_family_is_probed_separately(render_server):
    """The ``/etc/bunkerweb/configs`` family is NOT what the fragments above satisfy.

    The two are independent probes of two different producers -- the operator's custom configs,
    materialised from the database by ``push-configs._materialize_custom_configs``, against the
    plugin fragments this render writes -- and neither is a fallback for the other. Asserted in
    both directions so that a change collapsing them into one is visible here.
    """
    empty = render_server(SERVER_NAME="www.example.com", MULTISITE="no") / RULES
    assert "include /etc/bunkerweb/configs/modsec-crs/*.conf" not in empty.read_text()
    assert "include /etc/nginx/modsec-crs/*.conf" in empty.read_text()

    custom = render_server.custom_configs / "modsec-crs"
    custom.mkdir()
    custom.joinpath("operator.conf").write_text("# an operator's own CRS exclusion\n")

    rules = (render_server(SERVER_NAME="www2.example.com", MULTISITE="no") / RULES).read_text()
    assert "include /etc/bunkerweb/configs/modsec-crs/*.conf" in rules
    assert "include /etc/nginx/modsec-crs/*.conf" in rules
