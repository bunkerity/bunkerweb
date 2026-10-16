"""UI readers of the duration settings: the report ban default and the three wizard ZeroSSL inputs."""

import ast
from pathlib import Path

import pytest

from common_utils import parse_duration_int

ROOT = Path(__file__).resolve().parents[3]
UTILS = ROOT / "src" / "ui" / "app" / "routes" / "utils.py"
SETUP_HTML = ROOT / "src" / "ui" / "app" / "templates" / "setup.html"


def _get_default_ban_time():
    # routes/utils.py needs qrcode and the app singletons at import; the function itself needs only the parser
    tree = ast.parse(UTILS.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "get_default_ban_time")
    namespace = {"parse_duration_int": parse_duration_int}
    exec(compile(ast.Module([node], []), str(UTILS), "exec"), namespace)  # noqa: S102
    assert "parse_duration_int" in UTILS.read_text(encoding="utf-8").split("def get_default_ban_time")[0], "the module must import the parser"
    return namespace["get_default_ban_time"]


@pytest.mark.parametrize(
    ("config", "server", "expected"),
    [
        ({}, "", 86400),
        ({"BAD_BEHAVIOR_BAN_TIME": "1d"}, "www.example.com", 86400),
        ({"BAD_BEHAVIOR_BAN_TIME": "2h"}, "", 7200),
        ({"BAD_BEHAVIOR_BAN_TIME": "3600"}, "_", 3600),
        ({"BAD_BEHAVIOR_BAN_TIME": "1d", "www.example.com_BAD_BEHAVIOR_BAN_TIME": "30m"}, "www.example.com", 1800),
        ({"BAD_BEHAVIOR_BAN_TIME": "0"}, "", 0),
        ({"BAD_BEHAVIOR_BAN_TIME": "junk"}, "", 86400),
    ],
)
def test_default_ban_time_reads_suffixed_values(config, server, expected):
    assert _get_default_ban_time()(config, server) == expected


@pytest.mark.parametrize("name", ["LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY", "LETS_ENCRYPT_ZEROSSL_API_CONNECT_TIMEOUT", "LETS_ENCRYPT_ZEROSSL_API_MAX_TIME"])
def test_wizard_zerossl_time_inputs_take_a_suffix(name):
    html = SETUP_HTML.read_text(encoding="utf-8")
    block = html[html.index(f'<input id="{name}"') :]
    block = block[: block.index("/>")]
    assert 'type="text"' in block
    assert 'type="number"' not in block and "min=" not in block
    assert "[shdwMy]" in block, "the fallback pattern must accept the suffixes"
