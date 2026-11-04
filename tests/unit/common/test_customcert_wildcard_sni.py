"""Wildcard SNI fallback for custom certificates (F-LE-3, `a331fa3ed`).

A custom certificate covering `*.example.com` was only ever served for the exact server names
configured on the service. A request for a sub-domain that matches the wildcard but is not itself a
configured `SERVER_NAME` fell through to the default certificate, so the browser got a name
mismatch for a certificate the operator had supplied precisely to cover it.

1.7 already had this pattern in `letsencrypt.lua` — publish `plugin_<id>_wildcard_bases` to the
internalstore in `init()`, resolve against it in `ssl_certificate()`. `customcert` now uses the same
convention, with one difference forced by the source of the data: letsencrypt knows its wildcard
bases from the configuration it requested them for, whereas a custom certificate is supplied by the
operator, so the bases are derived from the certificate's own SAN entries.

`get_wildcard_bases` needs `resty.openssl` and OpenResty, so it is not reachable from a stand-alone
interpreter; what is tested here is the resolution rule, which is where the security-relevant
decision lives. See the ledger for the matching-rule asymmetry this exposed in `letsencrypt.lua`.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CUSTOMCERT_LUA = ROOT / "src" / "common" / "core" / "customcert" / "customcert.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

HARNESS = """-- customcert.lua localises these at module level; the lifted functions close over them.
local lower = string.lower
%s
%s
local bases = {}
for base in arg[2]:gmatch("[^,]+") do bases[#bases + 1] = base end
print(tostring(resolve_wildcard_base(arg[1], bases)))
"""


def lua_function(name: str) -> str:
    """Lift a local function's real source. `customcert.lua` requires ngx at module level."""
    match = re.search(rf"^local function {name}\(.*?^end$", CUSTOMCERT_LUA.read_text(encoding="utf-8"), re.S | re.M)
    assert match, f"{name} not found in customcert.lua -- renamed or removed?"
    return match.group(0)


def resolve(tmp_path, hostname: str, bases: str) -> str:
    # A script FILE, not `lua -e`: after `-e`, lua treats the first positional as a script name to
    # run, so the arguments never reach `arg[1]`/`arg[2]` and the harness dies indexing nil.
    script = tmp_path / "resolve.lua"
    script.write_text(HARNESS % (lua_function("normalize_hostname"), lua_function("resolve_wildcard_base")), encoding="utf-8")
    result = subprocess.run([LUA, str(script), hostname, bases], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@needs_lua
@pytest.mark.parametrize(
    ("hostname", "bases", "expected"),
    [
        # The fix: one label under the base resolves to it.
        ("app.example.com", "example.com", "example.com"),
        ("APP.Example.COM", "example.com", "example.com"),  # SNI casing is not normalised by nginx
        ("app.example.com.", "example.com", "example.com"),  # trailing dot is a legal FQDN
        # RFC 6125: `*.example.com` matches ONE label. Serving the wildcard here would hand the
        # client a certificate its own validation rejects -- a worse outcome than not matching,
        # because the fallback that would have worked is skipped.
        ("deep.app.example.com", "example.com", "nil"),
        # The base itself is not a wildcard match; the exact-name lookup already handled it.
        ("example.com", "example.com", "nil"),
        # A neighbouring domain must never borrow the certificate.
        ("app.notexample.com", "example.com", "nil"),
        ("example.com.evil.test", "example.com", "nil"),
        # Bases are published longest-first, so the most specific one wins.
        ("a.sub.example.com", "sub.example.com,example.com", "sub.example.com"),
        # No bases configured at all: the wildcard path is simply inert.
        ("app.example.com", "", "nil"),
    ],
)
def test_wildcard_resolution(tmp_path, hostname, bases, expected):
    assert resolve(tmp_path, hostname, bases) == expected


@needs_lua
def test_the_matching_rule_is_present_at_all(tmp_path):
    """RULE 13 for a single-function guard: the cases above all pass against a function that
    returns nil unconditionally, because most of them expect nil. Pin the one that does not."""
    assert resolve(tmp_path, "app.example.com", "example.com") == "example.com"
