"""RFC 6125 wildcard resolution in `letsencrypt.lua`.

`*.example.com` covers exactly ONE label under the base (RFC 6125 section 6.4.3). Both wildcard
resolvers in `letsencrypt.lua` tested the suffix alone, so a `*.example.com` certificate was
selected for `deep.app.example.com` and `a.b.c.example.com` -- hosts it does not cover. Measured by
lifting the loop and running it, not by reading it.

`customcert.lua` already applied the single-label rule (F-LE-3 part A), so the two plugins answered
the same question differently in the same phase. That asymmetry is what this closes; the shared
predicate is now identical on both sides, and `test_wildcard_rule_agrees_with_customcert` pins it.

Two resolution sites existed: the `local function resolve_wildcard_base` used by `init()`, and a
verbatim copy inlined in `ssl_certificate()`. The copy is gone -- `ssl_certificate()` calls the
shared resolver -- so `test_ssl_certificate_*` exercises the real selection path rather than the
helper alone. Without it a mutant that restores the inline loop passes every helper-level case.

Lua only, no OpenResty: `ssl.server_name`, the internalstore and `plugin.ret` are stubbed, which is
the same approach `test_customcert_wildcard_sni.py` and `test_lua_request_path_ports.py` take.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
LETSENCRYPT_LUA = ROOT / "src" / "common" / "core" / "letsencrypt" / "letsencrypt.lua"
CUSTOMCERT_LUA = ROOT / "src" / "common" / "core" / "customcert" / "customcert.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

# The helper alone. `resolve_wildcard_base` closes over nothing but `ipairs`, which is global here.
HELPER_HARNESS = """%s
local bases = {}
for base in arg[2]:gmatch("[^,]+") do bases[#bases + 1] = base end
print(tostring(resolve_wildcard_base(arg[1], bases)))
"""

# The real `ssl_certificate` phase, lifted verbatim. `sni` is the client's SNI; the internalstore
# holds one certificate per published base, so the printed value names the certificate the phase
# would actually serve -- "nil" means it falls through to the default one.
PHASE_HARNESS = """local lower, gsub = string.lower, string.gsub
%s
local sni = arg[1]
local function ssl_server_name() return sni, nil end
local letsencrypt = {}
%s
local bases = {}
for base in arg[2]:gmatch("[^,]+") do bases[#bases + 1] = base end
-- arg[3] is the published `wildcard_servers` map: "host=alias" entries, "host=false" for a host
-- whose service does not use Let's Encrypt at all. Empty means no service claimed any name.
local servers = {}
for entry in (arg[3] or ""):gmatch("[^,]+") do
    local host, value = entry:match("^([^=]+)=(.*)$")
    servers[host] = value ~= "false" and value or false
end
local store = { plugin_letsencrypt_wildcard_servers = servers, plugin_letsencrypt_wildcard_bases = bases }
for _, base in ipairs(bases) do
    store["plugin_letsencrypt_" .. base] = "cert-for-" .. base
end
local self = {
    internalstore = {
        get = function(_, key)
            if store[key] == nil then
                return nil, "not found"
            end
            return store[key], nil
        end,
    },
    ret = function(_, ok, msg, data)
        return { ok = ok, msg = msg, data = data }
    end,
}
local result = letsencrypt.ssl_certificate(self)
print(tostring(result.data))
"""


def lua_source(path: Path, pattern: str) -> str:
    """Lift a real definition's source. Both files require ngx/cjson at module level."""
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.S | re.M)
    assert match, f"{pattern!r} not found in {path.name} -- renamed or removed?"
    return match.group(0)


def le_helper() -> str:
    return lua_source(LETSENCRYPT_LUA, r"^local function resolve_wildcard_base\(.*?^end$")


def le_normalize() -> str:
    """`ssl_certificate` folds the client SNI before it looks anything up, so the phase does not
    run without it."""
    return lua_source(LETSENCRYPT_LUA, r"^local function normalize_hostname\(.*?^end$")


def run(tmp_path, name: str, script: str, *args: str) -> str:
    # A script FILE, not `lua -e`: after `-e`, lua treats the first positional as a script name,
    # so the arguments never reach `arg[1]` and the harness dies indexing nil.
    path = tmp_path / name
    path.write_text(script, encoding="utf-8")
    result = subprocess.run([LUA, str(path), *args], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def resolve(tmp_path, hostname: str, bases: str) -> str:
    return run(tmp_path, "resolve.lua", HELPER_HARNESS % le_helper(), hostname, bases)


def served_certificate(tmp_path, sni: str, bases: str, servers: str = "") -> str:
    phase = lua_source(LETSENCRYPT_LUA, r"^function letsencrypt:ssl_certificate\(.*?^end$")
    helpers = le_normalize() + "\n" + le_helper()
    return run(tmp_path, "phase.lua", PHASE_HARNESS % (helpers, phase), sni, bases, servers)


WILDCARD_CASES = [
    # One label under the base is what a wildcard covers.
    ("app.example.com", "example.com", "example.com"),
    # RFC 6125 section 6.4.3: `*.example.com` matches ONE label. Serving the wildcard here hands
    # the client a certificate its own validation rejects.
    ("deep.app.example.com", "example.com", "nil"),
    ("a.b.c.example.com", "example.com", "nil"),
    # A neighbouring domain must never borrow the certificate.
    ("app.notexample.com", "example.com", "nil"),
    ("example.com.evil.test", "example.com", "nil"),
    # Bases are published longest-first, so the most specific one still wins -- and a base whose
    # suffix matches but whose label test fails must keep looking, not stop the search.
    ("a.sub.example.com", "sub.example.com,example.com", "sub.example.com"),
    ("b.a.sub.example.com", "sub.example.com,example.com", "nil"),
    # No bases published at all: the wildcard path is inert.
    ("app.example.com", "", "nil"),
]


@needs_lua
@pytest.mark.parametrize(("hostname", "bases", "expected"), WILDCARD_CASES)
def test_wildcard_resolution(tmp_path, hostname, bases, expected):
    assert resolve(tmp_path, hostname, bases) == expected


@needs_lua
def test_the_apex_stays_covered(tmp_path):
    """Not the wildcard rule, and deliberately kept.

    In wildcard mode `build_wildcard_groups` puts BOTH `*.example.com` and `example.com` in the
    lineage for base `example.com`, so the apex really is covered by that certificate. Tightening
    the wildcard rule must not take the apex with it -- `customcert` has no equivalent branch only
    because it derives its bases from `*.` SAN entries alone.
    """
    assert resolve(tmp_path, "example.com", "example.com") == "example.com"


@needs_lua
@pytest.mark.parametrize(
    ("sni", "bases", "expected"),
    [
        ("app.example.com", "example.com", "cert-for-example.com"),
        # The regression this row closes: before the fix the inlined copy of the rule in
        # `ssl_certificate` selected the wildcard certificate for a host two labels down.
        ("deep.app.example.com", "example.com", "nil"),
        ("a.b.c.example.com", "example.com", "nil"),
        ("a.sub.example.com", "sub.example.com,example.com", "cert-for-sub.example.com"),
    ],
)
def test_ssl_certificate_serves_only_what_the_wildcard_covers(tmp_path, sni, bases, expected):
    assert served_certificate(tmp_path, sni, bases) == expected


@needs_lua
def test_ssl_certificate_uses_the_shared_resolver(tmp_path):
    """The selection path must not carry its own copy of the rule.

    A helper-level suite passes unchanged against a re-inlined loop, because it never calls the
    phase. This is the case that fails if `ssl_certificate` ever grows its own matcher again.
    """
    assert served_certificate(tmp_path, "deep.app.example.com", "example.com") == "nil"
    assert served_certificate(tmp_path, "app.example.com", "example.com") == "cert-for-example.com"


@needs_lua
@pytest.mark.parametrize(("hostname", "bases", "expected"), WILDCARD_CASES)
def test_wildcard_rule_agrees_with_customcert(tmp_path, hostname, bases, expected):
    """The actual defect being closed: two plugins answering the same question differently.

    Run the SAME cases through `customcert.lua`'s resolver. Every case above except the apex is a
    pure wildcard question, so both files must agree on all of them.
    """
    harness = """local lower = string.lower
%s
%s
local bases = {}
for base in arg[2]:gmatch("[^,]+") do bases[#bases + 1] = base end
print(tostring(resolve_wildcard_base(arg[1], bases)))
""" % (
        lua_source(CUSTOMCERT_LUA, r"^local function normalize_hostname\(.*?^end$"),
        lua_source(CUSTOMCERT_LUA, r"^local function resolve_wildcard_base\(.*?^end$"),
    )
    assert run(tmp_path, "customcert.lua", harness, hostname, bases) == expected


@needs_lua
@pytest.mark.parametrize(
    ("sni", "servers", "expected"),
    [
        # The defect: `bw2.example.com` belongs to a service that does not use Let's Encrypt, so
        # `init()` claims the name with `false`. Without that claim the host is unknown to the map
        # and falls through to the base scan, which hands it the neighbouring service's wildcard
        # certificate -- a certificate issued for someone else.
        ("bw2.example.com", "bw2.example.com=false", "nil"),
        # SNI is client-supplied: the claim has to survive case and a trailing dot, or the opt-out
        # is trivially bypassed by asking for the same host in capitals.
        ("BW2.Example.COM", "bw2.example.com=false", "nil"),
        ("bw2.example.com.", "bw2.example.com=false", "nil"),
        # A service that DOES use Let's Encrypt but has no wildcard maps to itself, not to false,
        # so it keeps its own certificate instead of borrowing the base's.
        ("bw2.example.com", "bw2.example.com=bw2.example.com", "nil"),
        ("example.com", "example.com=example.com", "cert-for-example.com"),
        # A host no service claims still falls back to the wildcard base, which is what the
        # fallback exists for.
        ("unclaimed.example.com", "", "cert-for-example.com"),
    ],
)
def test_a_service_that_opted_out_is_never_served_a_neighbours_wildcard(tmp_path, sni, servers, expected):
    """`wildcard_servers` is an authority list, not a hint.

    `false` means "this name belongs to a service that does not use Let's Encrypt"; the phase must
    stop there rather than continue into the wildcard base scan.
    """
    assert served_certificate(tmp_path, sni, "example.com", servers) == expected
