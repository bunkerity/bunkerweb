"""Plugin-rendered ModSecurity confs are included whatever host renders them.

The ModSecurity rules files ``include`` the ``modsec``, ``modsec-crs``, ``crs-plugins-before`` and
``crs-plugins-after`` directories that plugins fill through ``confs/<context>/`` (the UI service's CRS
exclusions, the antibot allow-rule, the HTTP/3 fix, the ``ip-host.conf`` literal-Host exclusion, ...).
Those includes used to be guarded by ``is_custom_conf("/etc/nginx/<dir>")``, a glob on the RENDERING
host. ``push-configs`` renders into a private ``bw-render-*`` directory and ships it to the instance,
so on a worker (Docker, Autoconf, Kubernetes, Swarm, all-in-one) there is no ``/etc/nginx`` at all and
the guard was always false: in per-service CRS mode, the default, not one of those exclusions loaded.

``test_modsec_plugin_fragment_includes.py`` pins the render ORDER and redirects ``/etc/nginx`` onto the
output directory, which is the one setup where the old guard worked. This file renders the way the
worker does: ``/etc/nginx`` is an EMPTY directory of the rendering host and the output goes elsewhere.
The include must then be present exactly when a template of that context is rendered, and absent when
none is, so a deployment where nothing renders into the directory emits the same file as before.
"""

import logging
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"
CORE = ROOT / "src" / "common" / "core"
SETTINGS = ROOT / "src" / "common" / "settings.json"

PER_SERVICE_RULES = "server-http/modsecurity-rules.conf.modsec"
GLOBAL_CRS_RULES = "modsecurity-rules-global-crs.conf.modsec"
CONTEXTS = ("modsec", "modsec-crs", "crs-plugins-before", "crs-plugins-after")
SERVICE = "app1.example.com"

# What core ships: no core plugin renders into the two ``crs-plugins-*`` contexts.
CORE_CONTEXTS = {"modsec", "modsec-crs"}


@pytest.fixture(scope="module")
def render_on_a_worker(tmp_path_factory):
    """``render(contexts, multisite, global_crs)`` -> ``{relative path: text}`` of one full render.

    ``contexts`` is the set of ``confs/<context>/`` directories that exist in the render: the core
    ones are removed from a symlink copy of ``src/common/core`` when absent, the other ones are added
    as an external plugin. The rendering host's ``/etc/nginx`` is an empty sandbox directory and
    ``/etc/bunkerweb/configs`` an empty one too, as on a worker that has no custom config.
    """
    import Templator as T  # type: ignore  (src/common/gen is on sys.path, see conftest)
    from Configurator import Configurator  # type: ignore

    sandbox = tmp_path_factory.mktemp("worker")
    host_etc_nginx = sandbox / "host-etc-nginx"
    host_etc_nginx.mkdir()
    # What `push-configs` materialises from the database on the worker before it renders.
    host = {"custom_configs": sandbox / "host-custom-configs"}
    host["custom_configs"].mkdir()

    def probe(path: str) -> bool:
        for literal, replacement in (("/etc/nginx", host_etc_nginx), ("/etc/bunkerweb/configs", host["custom_configs"])):
            if path == literal or path.startswith(literal + "/"):
                path = str(replacement / path[len(literal) :].lstrip("/"))  # noqa: E203
                break
        return bool(list(Path(path).glob("*.conf"))) if Path(path).is_dir() else False

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(T.Templator, "is_custom_conf", staticmethod(probe))
    # `sep` roots the Jinja bytecode cache: rebinding it keeps the render out of /var/cache.
    monkeypatch.setattr(T, "sep", str(sandbox))

    empty_plugins = sandbox / "no-plugins"
    empty_plugins.mkdir()
    pro_plugins = sandbox / "pro-plugins"
    pro_plugins.mkdir()
    cache = {}

    def core_with(contexts):
        """A symlink copy of the core plugins that keeps only the wanted ``confs/<context>`` dirs."""
        core = sandbox / f"core-{'-'.join(sorted(contexts)) or 'none'}"
        if core.exists():
            return core
        core.mkdir()
        for entry in CORE.iterdir():
            if not (entry / "confs").is_dir():
                core.joinpath(entry.name).symlink_to(entry)
                continue
            plugin = core / entry.name
            plugin.mkdir()
            for item in entry.iterdir():
                if item.name != "confs":
                    plugin.joinpath(item.name).symlink_to(item)
            # A copy, not symlinks: Jinja's loader does not follow a symlinked directory.
            shutil.copytree(
                entry / "confs",
                plugin / "confs",
                ignore=lambda directory, names: [n for n in names if Path(directory) == entry / "confs" and n in CONTEXTS and n not in contexts],
            )
        return core

    def plugin_with(contexts):
        """An external plugin shipping one ``<context>/fragment.conf`` for each context core lacks."""
        plugins = sandbox / f"plugins-{'-'.join(sorted(contexts)) or 'none'}"
        for context in contexts - CORE_CONTEXTS:
            fragments = plugins / "fragments" / "confs" / context
            fragments.mkdir(parents=True, exist_ok=True)
            (fragments / "fragment.conf").write_text("# a plugin fragment\n")
        plugins.mkdir(exist_ok=True)
        return plugins

    def render(contexts, multisite, global_crs, custom=()):
        key = (frozenset(contexts), multisite, global_crs, frozenset(custom))
        if key not in cache:
            host["custom_configs"] = sandbox / f"custom-configs-{len(cache)}"
            for context in custom:
                (host["custom_configs"] / context).mkdir(parents=True)
                (host["custom_configs"] / context / "operator.conf").write_text("# an operator's own conf\n")
            variables = {
                "SERVER_NAME": SERVICE,
                "MULTISITE": "yes" if multisite else "no",
                "USE_MODSECURITY": "yes",
                "USE_MODSECURITY_CRS": "yes",
                "USE_MODSECURITY_CRS_PLUGINS": "yes",
                "USE_MODSECURITY_GLOBAL_CRS": "yes" if global_crs else "no",
            }
            core = core_with(contexts)
            config = Configurator(str(SETTINGS), str(core), str(empty_plugins), str(pro_plugins), variables, logging.getLogger("modsec-worker")).get_config(
                None
            )
            output = sandbox / f"out{len(cache)}"
            output.mkdir()
            # The output directory is NOT /etc/nginx: the instance reads it from there, the worker never does.
            templator = T.Templator(
                str(CONFS), str(core), str(plugin_with(contexts)), str(pro_plugins), str(output), "/etc/nginx", config, config.copy(), config.copy()
            )
            # The two passes `render()` runs, without its process pool: the pool pickles the Templator
            # and the sandboxed probe above is a closure.
            templator._render_global()
            templator._render_server(SERVICE)
            cache[key] = {str(path.relative_to(output)): path.read_text() for path in sorted(output.rglob("*")) if path.is_file()}
        return cache[key]

    try:
        yield render
    finally:
        monkeypatch.undo()
        shutil.rmtree(sandbox, ignore_errors=True)


def include_line(context: str, multisite: bool) -> str:
    return f"include /etc/nginx/{SERVICE}/{context}/*.conf" if multisite else f"include /etc/nginx/{context}/*.conf"


def included(text: str, context: str, multisite: bool) -> bool:
    return include_line(context, multisite) in text.splitlines()


@pytest.mark.parametrize("multisite", [False, True], ids=["single-site", "multisite"])
@pytest.mark.parametrize("present", [*CONTEXTS, None], ids=[*CONTEXTS, "nothing-rendered"])
def test_per_service_crs_includes_exactly_the_contexts_that_render(render_on_a_worker, present, multisite):
    tree = render_on_a_worker({present} if present else set(), multisite, global_crs=False)
    rules = tree[f"{SERVICE}/{PER_SERVICE_RULES}" if multisite else PER_SERVICE_RULES]

    for context in CONTEXTS:
        assert included(rules, context, multisite) == (context == present), f"{context!r} with {present!r} rendered: expected {context == present}"


@pytest.mark.parametrize("multisite", [False, True], ids=["single-site", "multisite"])
@pytest.mark.parametrize("present", ["modsec", None], ids=["modsec", "nothing-rendered"])
def test_global_crs_server_block_includes_the_modsec_context_that_renders(render_on_a_worker, present, multisite):
    tree = render_on_a_worker({present} if present else set(), multisite, global_crs=True)
    rules = tree[f"{SERVICE}/server-http/{GLOBAL_CRS_RULES}" if multisite else f"server-http/{GLOBAL_CRS_RULES}"]

    assert included(rules, "modsec", multisite) == (present == "modsec")


@pytest.mark.parametrize("present", [*(c for c in CONTEXTS if c != "modsec"), None], ids=[*(c for c in CONTEXTS if c != "modsec"), "nothing-rendered"])
def test_global_crs_http_block_includes_the_single_site_contexts_that_render(render_on_a_worker, present):
    rules = render_on_a_worker({present} if present else set(), False, global_crs=True)[f"http/{GLOBAL_CRS_RULES}"]

    for context in ("crs-plugins-before", "modsec-crs", "crs-plugins-after"):
        assert included(rules, context, False) == (context == present), f"{context!r} with {present!r} rendered"


def test_global_crs_http_block_in_multisite_never_includes_a_per_service_directory(render_on_a_worker):
    """Plugin fragments of a multisite fleet live under ``<service>/``: the http block has no such path."""
    rules = render_on_a_worker(set(CONTEXTS), True, global_crs=True)[f"http/{GLOBAL_CRS_RULES}"]

    assert not [line for line in rules.splitlines() if line.startswith("include /etc/nginx/") and "/*.conf" in line]


@pytest.mark.parametrize("context", CONTEXTS)
def test_every_include_sits_on_a_line_of_its_own(render_on_a_worker, context):
    """A whitespace-control marker on a block tag glued the include onto the comment above it.

    ``{%- if ... %}`` ahead of the ``crs-plugins-after`` include removed the newline that ended the
    ``# custom CRS plugins configurations after loading plugins`` comment, so the first include of the
    block was part of that comment and never loaded, whatever fed it.
    """
    tree = render_on_a_worker(set(CONTEXTS), False, global_crs=False, custom={context})
    rules = tree[PER_SERVICE_RULES]

    assert f"include /etc/bunkerweb/configs/{context}/*.conf" in rules.splitlines(), "the operator's custom config include is missing or glued to another line"
    assert included(rules, context, False), "the plugin fragment include is missing or glued to another line"
    assert not [line for line in rules.splitlines() if line.count("include /") > 1 or (line.startswith("#") and "include /" in line)]


@pytest.mark.parametrize("context", [c for c in CONTEXTS if c != "modsec"])
def test_global_crs_http_block_keeps_operator_confs_on_their_own_line(render_on_a_worker, context):
    rules = render_on_a_worker(set(CONTEXTS), False, global_crs=True, custom={context})[f"http/{GLOBAL_CRS_RULES}"]

    assert f"include /etc/bunkerweb/configs/{context}/*.conf" in rules.splitlines()
    assert included(rules, context, False)
    assert not [line for line in rules.splitlines() if line.count("include /") > 1 or (line.startswith("#") and "include /" in line)]
