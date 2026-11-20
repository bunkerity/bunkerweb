"""``MODSECURITY_SEC_AUDIT_LOG_FORMAT`` (Native|JSON) renders ``SecAuditLogFormat`` in both ModSecurity templates.

* the per-service rules file and the global CRS one both render ``SecAuditLogFormat JSON`` next to ``SecAuditLogType`` when asked;
* the default ``Native`` renders no directive (ModSecurity's own default), so an http-level line never overrides a server-level custom
  ``SecAuditLogFormat JSON`` from an existing install; ``JSON`` is the Splunk-friendly opt-in;
* the plugin.json regex refuses anything else.
"""

import json
import logging
import re
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src" / "common" / "confs"
CORE = ROOT / "src" / "common" / "core"
SETTINGS = ROOT / "src" / "common" / "settings.json"
PLUGIN_JSON = CORE / "modsecurity" / "plugin.json"

# Configurator / Templator live in src/common/gen; appended so no other suite's bare imports are shadowed.
_GEN = str(ROOT / "src" / "common" / "gen")
if _GEN not in sys.path:
    sys.path.append(_GEN)

FORMAT = "MODSECURITY_SEC_AUDIT_LOG_FORMAT"


@pytest.fixture(scope="module")
def render():
    """``render(**variables)`` -> ``{relative path: text}`` of every file the real Templator writes."""
    import Templator as T  # type: ignore
    from Configurator import Configurator  # type: ignore

    with tempfile.TemporaryDirectory() as root:
        sandbox = Path(root)
        original_sep = T.sep
        T.sep = str(sandbox)
        plugins = sandbox / "plugins"
        plugins.mkdir()
        pro_plugins = sandbox / "pro-plugins"
        pro_plugins.mkdir()
        count = 0

        def _render(**variables):
            nonlocal count
            config = Configurator(str(SETTINGS), str(CORE), str(plugins), str(pro_plugins), dict(variables), logging.getLogger("audit")).get_config(None)
            output = sandbox / f"out{count}"
            count += 1
            output.mkdir()
            T.Templator(str(CONFS), str(CORE), str(plugins), str(pro_plugins), str(output), "/etc/nginx", config, config.copy(), config.copy()).render()
            return {str(path.relative_to(output)): path.read_text() for path in sorted(output.rglob("*")) if path.is_file()}

        try:
            yield _render
        finally:
            T.sep = original_sep


def format_lines(text: str) -> list:
    return [line for line in text.splitlines() if line.startswith("SecAuditLogFormat")]


def service_rules(tree: dict) -> str:
    return next(text for name, text in tree.items() if name.endswith("server-http/modsecurity-rules.conf.modsec"))


def global_rules(tree: dict) -> str:
    return tree["http/modsecurity-rules-global-crs.conf.modsec"]


class TestPerServiceTemplate:
    def test_default_renders_no_directive(self, render):
        text = service_rules(render(MULTISITE="no", SERVER_NAME="www.example.com"))
        assert format_lines(text) == []

    def test_json_renders_json(self, render):
        text = service_rules(render(MULTISITE="no", SERVER_NAME="www.example.com", **{FORMAT: "JSON"}))
        assert format_lines(text) == ["SecAuditLogFormat JSON"]

    def test_directive_sits_right_before_the_log_type(self, render):
        text = service_rules(render(MULTISITE="no", SERVER_NAME="www.example.com", **{FORMAT: "JSON"}))
        assert re.search(r"^SecAuditLogFormat JSON\nSecAuditLogType Serial\n", text, re.M)

    def test_multisite_override_is_per_service(self, render):
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com b.example.com", **{"a.example.com_" + FORMAT: "JSON"})
        by_service = {name.split("/")[0]: text for name, text in tree.items() if name.endswith("server-http/modsecurity-rules.conf.modsec")}
        assert format_lines(by_service["a.example.com"]) == ["SecAuditLogFormat JSON"]
        assert format_lines(by_service["b.example.com"]) == []


class TestGlobalCrsTemplate:
    def test_default_renders_no_directive(self, render):
        text = global_rules(render(MULTISITE="yes", SERVER_NAME="a.example.com", USE_MODSECURITY_GLOBAL_CRS="yes"))
        assert format_lines(text) == []

    def test_default_does_not_override_server_level_custom_json(self, render):
        """Regression: an http-level ``SecAuditLogFormat Native`` overrides a server-level custom config ``SecAuditLogFormat JSON``."""
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", USE_MODSECURITY_GLOBAL_CRS="yes")
        assert "SecAuditLogFormat" not in global_rules(tree)
        assert "SecAuditLogFormat" not in service_rules(tree)
        assert re.search(r"^SecAuditLogType Serial$", global_rules(tree), re.M)

    def test_json_renders_json(self, render):
        text = global_rules(render(MULTISITE="yes", SERVER_NAME="a.example.com", USE_MODSECURITY_GLOBAL_CRS="yes", **{FORMAT: "JSON"}))
        assert format_lines(text) == ["SecAuditLogFormat JSON"]
        assert re.search(r"^SecAuditLogFormat JSON\nSecAuditLogType Serial\n", text, re.M)

    def test_service_file_renders_no_format_in_global_mode(self, render):
        tree = render(MULTISITE="yes", SERVER_NAME="a.example.com", USE_MODSECURITY_GLOBAL_CRS="yes", **{FORMAT: "JSON"})
        assert format_lines(service_rules(tree)) == []


class TestSettingDefinition:
    @pytest.fixture(scope="class")
    def setting(self):
        return json.loads(PLUGIN_JSON.read_text())["settings"][FORMAT]

    def test_shape(self, setting):
        assert (setting["context"], setting["default"], setting["type"], setting["label"]) == ("multisite", "Native", "select", "SecAuditLogFormat")
        assert setting["select"] == ["Native", "JSON"]
        assert len(setting["help"]) <= 512

    @pytest.mark.parametrize("value", ["Native", "JSON"])
    def test_regex_accepts(self, setting, value):
        assert re.match(setting["regex"], value)

    @pytest.mark.parametrize("value", ["", "json", "native", "JSON ", "XML", "Native;", "JSON\nNative"])
    def test_regex_rejects(self, setting, value):
        assert not re.match(setting["regex"], value)
