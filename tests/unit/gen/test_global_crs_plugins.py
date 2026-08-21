"""Downloaded CRS plugins must load in global-CRS mode too, and only in one place.

``USE_MODSECURITY_GLOBAL_CRS=yes`` loads one CRS in the ``http`` context for the whole instance
instead of one per server. The downloaded-plugin includes existed only in the per-service template,
which renders nothing at all in that mode -- so ``USE_MODSECURITY_GLOBAL_CRS=yes`` together with
``MODSECURITY_CRS_PLUGINS=<x>`` downloaded the plugin, shipped it to every instance, and loaded none
of its rules. Two deliberate opt-ins are needed to reach it (both settings default off), which is
why it went unseen; it hits precisely the operators who configured CRS plugins on purpose.

The per-service block keys off ``service_plugins.get(service_id, [])`` and there is no service_id in
the ``http`` context, so the fix is not a copy-paste: global CRS loads **the union of every
service's plugins**. That is what the mode already means, and the same template already does exactly
this for ``ALLOWED_METHODS`` -- it merges every server's value into one ``tx.allowed_methods``.

The two templates are mutually exclusive by their opening ``if``, and this file pins that: whichever
mode is set, exactly one of them may emit plugin includes. A double-include would load every plugin
rule twice and collide on rule ids.
"""

import json
from importlib import import_module
from pathlib import Path

import pytest

jinja2 = pytest.importorskip("jinja2")

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "core" / "modsecurity" / "confs"
GLOBAL_TEMPLATE = CONFS / "http" / "modsecurity-rules-global-crs.conf.modsec"
SERVICE_TEMPLATE = CONFS / "server-http" / "modsecurity-rules.conf.modsec"
CACHE_DIR = "/var/cache/bunkerweb/modsecurity"

FLEET = ("app1.example.com", "app2.example.com", "app3.example.com")

# app3 configures no plugins: a service that contributes nothing must not break the union.
PLUGINS = {
    "app1.example.com": ["wordpress-rule-exclusions-1.0.0", "shared-1.0.0"],
    "app2.example.com": ["fake-bot-1.2.0", "shared-1.0.0"],
}

BASE = {
    "MODSECURITY_CRS_VERSION": "4",
    "SECURITY_MODE": "block",
    "MODSECURITY_SEC_RULE_ENGINE": "On",
    "MODSECURITY_SEC_REQUEST_BODY_LIMIT": "13107200",
    "MAX_CLIENT_SIZE": "10m",
    "MODSECURITY_REQ_BODY_NO_FILES_LIMIT": "131072",
    "MODSECURITY_SEC_REQUEST_BODY_LIMIT_ACTION": "Reject",
    "MODSECURITY_SEC_AUDIT_ENGINE": "Off",
    "MODSECURITY_SEC_AUDIT_LOG_PARTS": "ABCFHZ",
    "USE_MODSECURITY_CRS": "yes",
    "USE_MODSECURITY_CRS_PLUGINS": "yes",
    "USE_WHITELIST": "no",
    "ALLOWED_METHODS": "GET|POST|HEAD",
    "DENY_HTTP_STATUS": "403",
    "MULTISITE": "yes",
    "all": {f"{server}_ALLOWED_METHODS": "GET|POST|HEAD" for server in FLEET},
}


@pytest.fixture
def cache(tmp_path):
    """A plausible ``/var/cache/bunkerweb/modsecurity`` as ``download-crs-plugins`` leaves it."""
    root = tmp_path / "modsecurity"
    (root / "crs" / "plugins").mkdir(parents=True)
    for plugin_id in sorted({p for plugins in PLUGINS.values() for p in plugins}):
        plugin_dir = root / "crs" / "plugins" / plugin_id
        plugin_dir.mkdir()
        name = plugin_id.rsplit("-", 1)[0]
        for suffix in ("config", "before", "after"):
            plugin_dir.joinpath(f"{name}-{suffix}.conf").write_text(f"# {plugin_id} {suffix}\n", encoding="utf-8")
    root.joinpath("crs-plugins.json").write_text(json.dumps(PLUGINS), encoding="utf-8")
    return root


def render(template: Path, cache_root: Path, **variables) -> str:
    """Render one template with the Templator's whitespace settings and its ``import`` global.

    The cache path is baked into the template as a literal, so it is rewritten to the fixture rather
    than mocked -- the ``is_file()`` / ``iterdir()`` calls this guards are real filesystem calls and
    the point is that they answer at *render* time.
    """
    environment = jinja2.Environment(undefined=jinja2.ChainableUndefined, lstrip_blocks=True, trim_blocks=True, keep_trailing_newline=True)
    environment.globals["import"] = import_module
    source = template.read_text(encoding="utf-8").replace(CACHE_DIR, cache_root.as_posix())
    return environment.from_string(source).render({**BASE, "is_custom_conf": lambda _path: False, **variables})


def plugin_includes(rendered: str) -> list:
    """Just the filenames of the downloaded-plugin includes, in emitted order."""
    return [Path(line.split()[1]).name for line in rendered.splitlines() if line.startswith("include ") and "/crs/plugins/" in line]


def test_global_mode_loads_the_union_of_every_service_s_plugins(cache):
    rendered = render(GLOBAL_TEMPLATE, cache, USE_MODSECURITY_GLOBAL_CRS="yes", SERVER_NAME=" ".join(FLEET))
    assert plugin_includes(rendered) == [
        "fake-bot-config.conf",
        "fake-bot-before.conf",
        "shared-config.conf",
        "shared-before.conf",
        "wordpress-rule-exclusions-config.conf",
        "wordpress-rule-exclusions-before.conf",
        "fake-bot-after.conf",
        "shared-after.conf",
        "wordpress-rule-exclusions-after.conf",
    ], "the union is wrong -- every distinct plugin exactly once, deduplicated, in a stable order"


def test_plugin_rules_land_on_the_right_side_of_the_crs_ruleset(cache):
    """``-config``/``-before`` must precede the CRS rules and ``-after`` must follow them.

    Emitting them in one block would be simpler and would silently change what the plugins do.
    """
    lines = render(GLOBAL_TEMPLATE, cache, USE_MODSECURITY_GLOBAL_CRS="yes", SERVER_NAME=" ".join(FLEET)).splitlines()
    crs_rules = next(n for n, line in enumerate(lines) if "coreruleset-v4/rules" in line)
    positions = {Path(line.split()[1]).name: n for n, line in enumerate(lines) if line.startswith("include ") and "/crs/plugins/" in line}

    assert len(positions) == 9, "nothing to place -- the union block is missing, not merely misordered"
    assert all(n < crs_rules for name, n in positions.items() if name.endswith(("-config.conf", "-before.conf")))
    assert all(n > crs_rules for name, n in positions.items() if name.endswith("-after.conf"))


@pytest.mark.parametrize("mode", ("yes", "no"))
def test_exactly_one_template_emits_the_plugin_includes(cache, mode):
    """Both emitting means every plugin rule loads twice and collides on rule ids."""
    shared = render(GLOBAL_TEMPLATE, cache, USE_MODSECURITY_GLOBAL_CRS=mode, SERVER_NAME=" ".join(FLEET))
    per_service = [render(SERVICE_TEMPLATE, cache, USE_MODSECURITY_GLOBAL_CRS=mode, SERVER_NAME=server) for server in FLEET]

    emitted_globally = bool(plugin_includes(shared))
    emitted_per_service = any(plugin_includes(rendered) for rendered in per_service)
    assert emitted_globally is (mode == "yes")
    assert emitted_per_service is (mode == "no")


def test_a_service_with_no_plugins_of_its_own_still_gets_the_shared_ruleset(cache):
    """``app3`` configures none. In global mode it is served by the same shared CRS as everyone
    else, which is the whole point of the mode -- and in per-service mode it gets nothing."""
    assert plugin_includes(render(SERVICE_TEMPLATE, cache, USE_MODSECURITY_GLOBAL_CRS="no", SERVER_NAME="app3.example.com")) == []
    assert plugin_includes(render(GLOBAL_TEMPLATE, cache, USE_MODSECURITY_GLOBAL_CRS="yes", SERVER_NAME="app3.example.com")) != []


def test_an_empty_plugin_manifest_emits_nothing(cache):
    """Anti-vacuity in the other direction: the block must be driven by the data, not unconditional."""
    cache.joinpath("crs-plugins.json").write_text("{}", encoding="utf-8")
    assert plugin_includes(render(GLOBAL_TEMPLATE, cache, USE_MODSECURITY_GLOBAL_CRS="yes", SERVER_NAME=" ".join(FLEET))) == []
