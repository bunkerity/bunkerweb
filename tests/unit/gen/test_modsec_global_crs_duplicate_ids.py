"""Global CRS mode must not load the same BunkerWeb rule twice.

With ``USE_MODSECURITY_GLOBAL_CRS=yes`` the http-scope rules file includes both ``/etc/nginx/modsec-crs/*.conf``
(the per-service fragments, which a single-site render writes) and ``/etc/nginx/http/*.modsec-crs`` (the global
twins). A fragment present on both sides emits its rule ID twice and libmodsecurity refuses the configuration
with ``Rule id: N is duplicated``. ``ip-host`` is already split between the two; ``antibot`` and ``http3`` were not.
"""

import logging
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"
CORE = ROOT / "src" / "common" / "core"
SETTINGS = ROOT / "src" / "common" / "settings.json"

GLOBAL_RULES = "http/modsecurity-rules-global-crs.conf.modsec"
BASE = {"USE_MODSECURITY": "yes", "USE_MODSECURITY_CRS": "yes", "USE_ANTIBOT": "captcha", "MODSECURITY_CRS_VERSION": "3"}


@pytest.fixture
def render(tmp_path, monkeypatch):
    """``render(**variables) -> output Path`` with the server pass and the global (http) pass of one render."""
    import Templator as T  # type: ignore  (src/common/gen is on sys.path, see conftest)
    from Configurator import Configurator  # type: ignore

    output = tmp_path / "out"
    output.mkdir()
    custom_configs = tmp_path / "custom-configs"
    custom_configs.mkdir()

    def probe(path: str) -> bool:
        # /etc/nginx is this render's output, /etc/bunkerweb/configs an empty sandbox: never read the host's /etc
        for literal, sandbox in (("/etc/nginx", output), ("/etc/bunkerweb/configs", custom_configs)):
            if path == literal or path.startswith(literal + "/"):
                path = str(sandbox / path[len(literal) :].lstrip("/"))  # noqa: E203
                break
        return bool(list(Path(path).glob("*.conf"))) if Path(path).is_dir() else False

    monkeypatch.setattr(T.Templator, "is_custom_conf", staticmethod(probe))
    monkeypatch.setattr(T, "sep", str(tmp_path))
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    pro_plugins = tmp_path / "pro-plugins"
    pro_plugins.mkdir()

    def _render(**variables):
        config = Configurator(str(SETTINGS), str(CORE), str(plugins), str(pro_plugins), dict(variables), logging.getLogger("modsec-dup")).get_config(None)
        templator = T.Templator(str(CONFS), str(CORE), str(plugins), str(pro_plugins), str(output), "/etc/nginx", config, config.copy(), config.copy())
        for server in variables["SERVER_NAME"].split():
            assert templator._render_server(server) == []
        assert templator._render_global_templates(deferred=False) == []
        # the global rules file probes the fragments the server pass staged, so it renders last
        assert templator._render_global_templates(deferred=True) == []
        return output

    return _render


def loaded_rule_ids(output: Path, rules_file: Path):
    """IDs of every rule in the BunkerWeb-generated files that ``rules_file`` includes (CRS and operator files excluded)."""
    ids = []
    for include in re.findall(r"^include (/etc/nginx/\S+)$", rules_file.read_text(), re.M):
        for generated in sorted(output.glob(include[len("/etc/nginx/") :])):  # noqa: E203
            ids += [int(found) for found in re.findall(r"\bid:'?(\d+)", generated.read_text())]
    return ids


def test_single_site_global_crs_loads_each_antibot_and_http3_rule_once(render):
    output = render(SERVER_NAME="www.example.com", MULTISITE="no", USE_MODSECURITY_GLOBAL_CRS="yes", **BASE)
    ids = loaded_rule_ids(output, output / GLOBAL_RULES)

    assert 9801500 in ids and 900230 in ids, "the rules this test guards are not loaded at all"
    assert [i for i in ids if ids.count(i) > 1] == [], "a rule ID is loaded twice"


@pytest.mark.parametrize("multisite", ["no", "yes"])
def test_without_global_crs_the_service_still_emits_the_antibot_and_http3_rules_once(render, multisite):
    output = render(SERVER_NAME="www.example.com", MULTISITE=multisite, USE_MODSECURITY_GLOBAL_CRS="no", **BASE)
    fragments = output / "modsec-crs" if multisite == "no" else output / "www.example.com" / "modsec-crs"
    text = "".join(path.read_text() for path in sorted(fragments.glob("*.conf")))

    assert len(re.findall(r"\bid:9801500\b", text)) == 1
    assert len(re.findall(r"\bid:900230\b", text)) == 1


def test_multisite_global_crs_keeps_the_global_antibot_and_http3_rules(render):
    output = render(SERVER_NAME="www.example.com", MULTISITE="yes", USE_MODSECURITY_GLOBAL_CRS="yes", **BASE)
    ids = loaded_rule_ids(output, output / GLOBAL_RULES)

    assert ids.count(9801500) == 1 and ids.count(900230) == 1


@pytest.mark.parametrize("antibot, copies", [("captcha", 1), ("no", 0)])
def test_single_site_global_crs_exempts_the_antibot_uri_only_when_antibot_is_on(render, antibot, copies):
    base = {**BASE, "USE_ANTIBOT": antibot}
    output = render(SERVER_NAME="www.example.com", MULTISITE="no", USE_MODSECURITY_GLOBAL_CRS="yes", **base)
    ids = loaded_rule_ids(output, output / GLOBAL_RULES)

    assert ids.count(9801500) == copies
