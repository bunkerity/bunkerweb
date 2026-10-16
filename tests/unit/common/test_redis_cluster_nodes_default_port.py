"""REDIS_CLUSTER_NODES keeps 1.6.16's language: a host without a port means 6379 (dev d94517729, 5469882c2).

1.7 still rejects what is truly invalid (port out of range, unbracketed IPv6, junk), so
``cluster_config_error`` keeps leaving Redis unused on a bad list.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

import redis_keys

ROOT = Path(__file__).resolve().parents[3]
REDISKEYS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "rediskeys.lua"
LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

VALID = [
    ("redis1", [("redis1", 6379)]),
    ("redis1 redis2", [("redis1", 6379), ("redis2", 6379)]),
    ("10.0.0.1", [("10.0.0.1", 6379)]),
    ("redis1 [::1] h:7000", [("redis1", 6379), ("::1", 6379), ("h", 7000)]),
    ("[::1]:7001", [("::1", 7001)]),
    ("  r1:7000   r2  ", [("r1", 7000), ("r2", 6379)]),
]
INVALID = ["r1:", "r1:0", "r1:65536", "r1:abc", "::1:7000", "r1:7000 g@rbage", "[zz]", "[not-ip]:7000", "[::1"]


@pytest.mark.parametrize(("value", "expected"), VALID)
def test_python_parse_nodes_defaults_the_port(value, expected):
    assert redis_keys.parse_nodes(value) == expected


@pytest.mark.parametrize("value", INVALID)
def test_python_parse_nodes_still_rejects_invalid_nodes(value):
    with pytest.raises(ValueError):
        redis_keys.parse_nodes(value)
    assert redis_keys.cluster_config_error(value, "", "0") is not None


@pytest.mark.parametrize("value", [v for v, _ in VALID])
def test_python_cluster_config_error_accepts_a_portless_list(value):
    assert redis_keys.cluster_config_error(value, "", "0") is None


def _lua(tmp_path, expr):
    script = tmp_path / "nodes.lua"
    script.write_text("""
package.preload["bunkerweb.utils"] = function()
    return { is_ipv6 = function(host) return host:find(":", 1, true) ~= nil and not host:find("[^%x:.]") end }
end
local rediskeys = dofile(arg[1])
""" + expr)
    out = subprocess.run([LUA, str(script), str(REDISKEYS_LUA)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


@needs_lua
@pytest.mark.parametrize(("value", "expected"), VALID)
def test_lua_parse_nodes_defaults_the_port(tmp_path, value, expected):
    got = _lua(
        tmp_path,
        'local nodes, err = rediskeys.parse_nodes("%s")\nassert(nodes, err)\nlocal out = {}\nfor _, n in ipairs(nodes) do out[#out + 1] = n.ip .. "|" .. n.port end\nprint(table.concat(out, ","))'
        % value,
    )
    # the Lua side keeps the brackets on IPv6, tcpsock:connect() needs them
    assert got == ",".join((f"[{h}]" if ":" in h else h) + f"|{p}" for h, p in expected)


@needs_lua
@pytest.mark.parametrize("value", INVALID)
def test_lua_parse_nodes_still_rejects_invalid_nodes(tmp_path, value):
    got = _lua(
        tmp_path,
        'local nodes, err = rediskeys.parse_nodes("%s")\nprint(nodes == nil and "ERR" or "OK")\nprint(rediskeys.cluster_config_error("%s", "", "0") ~= nil)'
        % (value, value),
    )
    assert got.splitlines() == ["ERR", "true"]


@needs_lua
def test_lua_cluster_config_error_accepts_a_portless_list(tmp_path):
    assert _lua(tmp_path, 'print(tostring(rediskeys.cluster_config_error("redis1 [::1] h:7000", "", "0")))') == "nil"
