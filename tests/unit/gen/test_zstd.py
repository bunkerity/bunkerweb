import json
import re
from pathlib import Path

import jinja2
import pytest

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "src/common/core/zstd"


def settings():
    assert (PLUGIN / "plugin.json").is_file(), "zstd plugin is not shipped"
    return json.loads((PLUGIN / "plugin.json").read_text())["settings"]


@pytest.mark.parametrize(
    "name,accepted,rejected",
    [
        ("USE_ZSTD", ["yes", "no"], ["", "on", "yes; zstd on"]),
        ("ZSTD_COMP_LEVEL", [str(level) for level in range(1, 20)], ["0", "20", "22", "-1", "03", "3; zstd on"]),
        ("ZSTD_MIN_LENGTH", ["0", "1000", "1048576"], ["", "-1", "1k", "1000; zstd on"]),
        ("ZSTD_TYPES", ["text/plain", "application/json text/css"], ["", "text", "text/plain; zstd on", "text/plain\ntext/css"]),
    ],
)
def test_zstd_settings_validate_values(name, accepted, rejected):
    regex = settings()[name]["regex"]
    assert all(re.search(regex, value) for value in accepted)
    assert not any(re.search(regex, value) for value in rejected)


def test_zstd_defaults_and_select_values():
    schema = settings()
    assert {name: item["default"] for name, item in schema.items()} == {
        "USE_ZSTD": "no",
        "ZSTD_TYPES": json.loads((ROOT / "src/common/core/brotli/plugin.json").read_text())["settings"]["BROTLI_TYPES"]["default"],
        "ZSTD_MIN_LENGTH": "1000",
        "ZSTD_COMP_LEVEL": "3",
    }
    assert schema["ZSTD_COMP_LEVEL"]["select"] == [str(level) for level in range(1, 20)]
    assert all(item["context"] == "multisite" and re.search(item["regex"], item["default"]) for item in schema.values())


@pytest.mark.parametrize("enabled", ["no", "yes"])
def test_zstd_template(enabled):
    values = {name: item["default"] for name, item in settings().items()}
    values["USE_ZSTD"] = enabled
    template = jinja2.Environment(undefined=jinja2.StrictUndefined).from_string((PLUGIN / "confs/server-http/zstd.conf").read_text())
    rendered = template.render(**values).strip()
    assert rendered == (f"zstd on;\nzstd_types {values['ZSTD_TYPES']};\nzstd_comp_level 3;\nzstd_min_length 1000;" if enabled == "yes" else "")


def test_zstd_filter_is_loaded_after_brotli_before_modsecurity():
    modules = re.findall(r"^load_module\s+\S*/(\w+\.so);", (ROOT / "src/common/confs/nginx.conf").read_text(), re.MULTILINE)
    assert "ngx_http_zstd_filter_module.so" in modules
    assert modules.index("ngx_http_brotli_static_module.so") < modules.index("ngx_http_zstd_filter_module.so")
    assert modules.index("ngx_http_zstd_filter_module.so") < modules.index("ngx_http_modsecurity_module.so")
    assert "ngx_http_zstd_static_module.so" not in modules
