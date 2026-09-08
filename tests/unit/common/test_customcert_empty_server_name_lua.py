"""``customcert:init()`` refuses an empty ``SERVER_NAME`` instead of raising (DS-B6).

The single-site branch of ``init()`` built its cache paths from ``server_name:match("%S+")``.
``get_variable`` answers ``""`` -- not ``nil`` -- for a ``SERVER_NAME`` that reached the instance
empty, so ``not server_name`` does not catch it, the match yields ``nil`` and the concatenation
aborts init inside ``init_by_lua``::

    [INIT] customcert:init() failed : .../customcert/customcert.lua:191:
           attempt to concatenate a nil value

``certificates.lua`` already guards the same shape a few lines into its own init. The difference
here is what the guard does with the rest of the function: the default server's own certificate
(``DEFAULT_SERVER_SSL_CERT``/``_KEY``) is independent of any service -- the job says so too
(``jobs/custom-cert.py``: "the default server exists whether or not any service does") -- so the
guard records the failure and lets init finish rather than returning on the spot.

What made ``SERVER_NAME`` empty in the first place was ``db_methods/config_read.py``; that half is
covered in ``tests/unit/db/test_default_server_multisite_gate.py``. This one is the second line of
defence: whatever empties the variable, the instance must not lose its init phase over it.
"""

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[3]
CUSTOMCERT_LUA = ROOT / "src" / "common" / "core" / "customcert" / "customcert.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

# `read_files` is the only thing between the guard and the filesystem, so it is the probe: every
# path init asks for is recorded and nothing is ever opened.
HARNESS = """
local LOGS, READS = {}, {}

ngx = { ERR = "ERR", WARN = "WARN" }

package.loaded["middleclass"] = function(_, parent)
  local klass = {}
  klass.__index = klass
  setmetatable(klass, { __index = parent })
  return klass
end

package.loaded["bunkerweb.plugin"] = {
  initialize = function(self)
    self.logger = { log = function(_, level, msg) LOGS[#LOGS + 1] = level .. " " .. msg end }
    self.internalstore = { set = function() return true end, get = function() return nil, "not found" end }
  end,
  ret = function(_, ok, msg) return { ret = ok, msg = msg } end,
}

package.loaded["bunkerweb.utils"] = {
  has_variable = function() return true end,
  get_variable = function(name)
    if name == "MULTISITE" then return "no" end
    if name == "SERVER_NAME" then return SERVER_NAME end
    return nil, "not found"
  end,
  get_multiple_variables = function() return {} end,
  read_files = function(paths)
    for _, path in ipairs(paths) do READS[#READS + 1] = path end
    return false, "no such file"
  end,
}

-- Only needed so the module-level requires resolve; nothing below the guard parses anything.
package.loaded["ngx.ssl"] = { parse_pem_cert = function() return nil, "stub" end,
                              parse_pem_priv_key = function() return nil, "stub" end,
                              server_name = function() return nil end }
package.loaded["resty.openssl.pkey"] = {}
package.loaded["resty.openssl.x509"] = {}

local customcert = dofile([==[%(lua)s]==])

local instance = setmetatable({}, customcert)
instance:initialize({})
instance.variables = {}

local res = instance:init()
print("RET=" .. tostring(res.ret))
print("MSG=" .. tostring(res.msg))
for _, path in ipairs(READS) do print("READ=" .. path) end
for _, line in ipairs(LOGS) do print("LOG=" .. line) end
"""


def run(server_name: str, *, source: str | None = None) -> subprocess.CompletedProcess:
    with TemporaryDirectory() as tmp:
        lua_path = CUSTOMCERT_LUA
        if source is not None:
            # dofile() takes a path, so a mutated copy has to exist on disk -- never the shipped file.
            lua_path = Path(tmp) / "customcert.lua"
            lua_path.write_text(source, encoding="utf-8")
        script = f"SERVER_NAME = [==[{server_name}]==]\n" + HARNESS % {"lua": str(lua_path)}
        return subprocess.run(["lua", "-e", script], capture_output=True, text=True)


def field(out: str, key: str) -> str:
    for line in out.splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    raise AssertionError(f"{key} missing from:\n{out}")


def fields(out: str, key: str) -> list:
    return [line.split("=", 1)[1] for line in out.splitlines() if line.startswith(key + "=")]


DEFAULT_SERVER_READS = (
    "/var/cache/bunkerweb/customcert/default-server/default-server-cert.pem",
    "/var/cache/bunkerweb/customcert/default-server-cert.pem",
)


def test_an_empty_server_name_does_not_abort_init():
    """The regression itself: `""` used to raise, which nginx reports as a failed init phase."""
    result = run("")
    assert result.returncode == 0, result.stderr
    assert "attempt to concatenate a nil value" not in result.stderr
    assert field(result.stdout, "RET") == "false"
    assert "server name" in field(result.stdout, "MSG")


def test_the_refusal_says_which_variable_is_empty():
    """A `ret(false)` with no explanation is the same support ticket as the raise."""
    logs = fields(run("").stdout, "LOG")
    assert [line for line in logs if line.startswith("ERR ") and "SERVER_NAME" in line], logs


def test_no_service_certificate_is_read_for_an_empty_server_name():
    """The paths the raise never got to build must not be built from a nil token either."""
    reads = fields(run("").stdout, "READ")
    assert not [path for path in reads if path.endswith("/cert.pem") or path.endswith("/key.pem")], reads


def test_the_default_server_certificate_is_still_looked_up():
    """Why the guard is not an early `return`: DEFAULT_SERVER_SSL_CERT is independent of any
    service, so an empty roster must not cost the default server its own certificate."""
    reads = fields(run("").stdout, "READ")
    assert set(DEFAULT_SERVER_READS) <= set(reads), reads


@pytest.mark.parametrize(
    ("server_name", "expected"),
    [
        ("default-server", "default-server"),
        ("www.example.com", "www.example.com"),
        # Single-site renders ONE block from the whole string; the cache directory is the first
        # token of it, which is what `custom-cert.py` writes and what the guard must not change.
        ("app.example.com alias.example.com", "app.example.com"),
        ("   spaced.example.com  ", "spaced.example.com"),
    ],
)
def test_a_configured_server_name_still_reads_its_own_cache(server_name, expected):
    reads = fields(run(server_name).stdout, "READ")
    assert f"/var/cache/bunkerweb/customcert/{expected}/cert.pem" in reads, reads
    assert f"/var/cache/bunkerweb/customcert/{expected}/key.pem" in reads, reads


def test_the_guard_is_the_thing_under_test():
    """RULE 13: the assertions above all pass against an init that never reads anything at all.
    Mutating the guard to fire unconditionally has to turn the configured case red."""
    source = CUSTOMCERT_LUA.read_text(encoding="utf-8").replace('local first_server = server_name:match("%S+")', "local first_server = nil")
    assert source != CUSTOMCERT_LUA.read_text(encoding="utf-8"), "the guard was renamed -- update this test"
    reads = fields(run("www.example.com", source=source).stdout, "READ")
    assert "/var/cache/bunkerweb/customcert/www.example.com/cert.pem" not in reads, reads
