"""``ip_identity.normalize_ip``, the Python twin of ``src/bw/lua/bunkerweb/ipaddr.lua``."""

import shutil
import subprocess
from pathlib import Path

import pytest

from ip_identity import normalize_ip

ROOT = Path(__file__).resolve().parents[3]
LUA = shutil.which("lua") or shutil.which("luajit")

SPELLINGS = [
    ("2001:0DB8:0:0:0:0:0:1", "2001:db8::1"),
    ("2001:db8::1", "2001:db8::1"),
    ("2001:DB8:0::1", "2001:db8::1"),
    ("2001:db8:0:0:1:0:0:1", "2001:db8::1:0:0:1"),
    ("1:0:0:2:0:0:0:3", "1:0:0:2::3"),
    ("1:2:3:4:5:6:7:0", "1:2:3:4:5:6:7:0"),
    ("0:0:0:0:0:0:0:0", "::"),
    ("::1", "::1"),
    ("::ffff:192.0.2.1", "192.0.2.1"),
    ("::FFFF:C000:201", "192.0.2.1"),
    ("::ffff:0:1", "0.0.0.1"),
    ("::1.2.3.4", "::1.2.3.4"),
    ("::102:304", "::1.2.3.4"),
    ("::2", "::2"),
    ("192.0.2.1", "192.0.2.1"),
    (" 192.0.2.1 ", "192.0.2.1"),
]


@pytest.mark.parametrize(("given", "canonical"), SPELLINGS)
def test_one_address_has_one_canonical_text(given, canonical):
    assert normalize_ip(given) == canonical


@pytest.mark.parametrize("bad", ["fe80::1%eth0", "[2001:db8::1]", "2001:db8::1/64", "1.2.3.4/32", "1::2::3", "example.com", "", None, 7])
def test_what_is_not_a_bare_address_is_refused(bad):
    with pytest.raises(ValueError):
        normalize_ip(bad)


@pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
def test_python_and_lua_agree_on_the_canonical_text():
    """A ban written by the API and a client address printed by NGINX are the same key only if both sides agree."""
    inputs = [given.strip() for given, _ in SPELLINGS]
    script = (
        f'package.path = {str(ROOT / "src/bw/lua/?.lua")!r} .. ";" .. package.path\n'
        'local ipaddr = require("bunkerweb.ipaddr")\n'
        "for line in io.lines() do print(ipaddr.normalize(line)) end\n"
    )
    result = subprocess.run([str(LUA), "-e", script], input="\n".join(inputs) + "\n", capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == [normalize_ip(given) for given in inputs]
