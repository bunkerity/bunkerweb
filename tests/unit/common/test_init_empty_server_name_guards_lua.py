"""No ``init()`` raises on an empty ``SERVER_NAME`` (DS-B6, the siblings of the customcert red).

``customcert.lua`` was the plugin CI caught, and it is covered on its own in
``test_customcert_empty_server_name_lua.py``. The same shape -- ``server_name:match("%S+")``
concatenated straight into a cache path in the single-site branch of ``init()`` -- was in
``selfsigned.lua`` and ``letsencrypt.lua`` too. ``get_variable`` answers ``""`` rather than ``nil``
for a variable that reached the instance empty, so the ``if not server_name`` above each of them
does not fire, the match yields ``nil`` and init dies inside ``init_by_lua``::

    [INIT] <plugin>:init() failed : ...: attempt to concatenate a nil value

Neither guard returns early, for the same reason ``customcert``'s does not: what follows the
branch is not about any one service. ``letsencrypt`` publishes
``plugin_letsencrypt_wildcard_servers`` / ``_bases`` after it, and its own ``ssl_certificate()``
refuses every handshake when those keys are missing -- so returning on the spot would turn a
misconfiguration into an outage on the services that ARE configured.

``certificates.lua`` already had this guard and is the shape both new ones follow.
"""

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

# One harness for both modules: the stubs are the union of what they require, and `read_files` is
# the probe -- every path init asks for is recorded and nothing is ever opened.
HARNESS = """
local LOGS, READS = {}, {}

ngx = { ERR = "ERR", WARN = "WARN", NOTICE = "NOTICE", OK = 0,
        HTTP_OK = 200, HTTP_NOT_FOUND = 404, HTTP_BAD_REQUEST = 400, HTTP_INTERNAL_SERVER_ERROR = 500 }

package.loaded["cjson"] = { decode = function() return {} end, encode = function() return "{}" end }

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
    return VARIABLES[name] or "no"
  end,
  get_multiple_variables = function() return {} end,
  read_files = function(paths)
    for _, path in ipairs(paths) do READS[#READS + 1] = path end
    return false, "no such file"
  end,
}

package.loaded["ngx.ssl"] = { parse_pem_cert = function() return nil, "stub" end,
                              parse_pem_priv_key = function() return nil, "stub" end,
                              server_name = function() return nil end }

local mod = dofile([==[%(lua)s]==])

local instance = setmetatable({}, mod)
instance:initialize({})
instance.variables = {}

local res = instance:init()
print("RET=" .. tostring(res.ret))
print("MSG=" .. tostring(res.msg))
for _, path in ipairs(READS) do print("READ=" .. path) end
for _, line in ipairs(LOGS) do print("LOG=" .. line) end
"""

# (module, extra get_variable answers, cache path template). The extras are the other variables the
# single-site branch reads before it reaches the guard.
PLUGINS = {
    "selfsigned": (CORE / "selfsigned" / "selfsigned.lua", {}, "/var/cache/bunkerweb/selfsigned/%s/cert.pem"),
    "letsencrypt": (
        CORE / "letsencrypt" / "letsencrypt.lua",
        {"USE_LETS_ENCRYPT_WILDCARD": "no", "LETS_ENCRYPT_CHALLENGE": "http"},
        "/var/cache/bunkerweb/letsencrypt/etc/live/%s/fullchain.pem",
    ),
}


def run(plugin: str, server_name: str, *, source: str | None = None) -> subprocess.CompletedProcess:
    lua_file, extras, _ = PLUGINS[plugin]
    variables = "{ " + ", ".join(f'["{key}"] = "{value}"' for key, value in extras.items()) + " }"
    with TemporaryDirectory() as tmp:
        lua_path = lua_file
        if source is not None:
            # dofile() takes a path, so a mutated copy has to exist on disk -- never the shipped file.
            lua_path = Path(tmp) / lua_file.name
            lua_path.write_text(source, encoding="utf-8")
        preamble = f"SERVER_NAME = [==[{server_name}]==]\nVARIABLES = {variables}\n"
        return subprocess.run(["lua", "-e", preamble + HARNESS % {"lua": str(lua_path)}], capture_output=True, text=True)


def field(out: str, key: str) -> str:
    for line in out.splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    raise AssertionError(f"{key} missing from:\n{out}")


def fields(out: str, key: str) -> list:
    return [line.split("=", 1)[1] for line in out.splitlines() if line.startswith(key + "=")]


@pytest.mark.parametrize("plugin", sorted(PLUGINS))
def test_an_empty_server_name_does_not_abort_init(plugin):
    result = run(plugin, "")
    assert result.returncode == 0, result.stderr
    assert "attempt to concatenate a nil value" not in result.stderr
    assert field(result.stdout, "RET") == "false"
    assert "server name" in field(result.stdout, "MSG")


@pytest.mark.parametrize("plugin", sorted(PLUGINS))
def test_the_refusal_names_the_empty_variable(plugin):
    logs = fields(run(plugin, "").stdout, "LOG")
    assert [line for line in logs if line.startswith("ERR ") and "SERVER_NAME" in line], logs


@pytest.mark.parametrize("plugin", sorted(PLUGINS))
def test_nothing_is_read_from_a_nil_token(plugin):
    assert fields(run(plugin, "").stdout, "READ") == []


@pytest.mark.parametrize("plugin", sorted(PLUGINS))
@pytest.mark.parametrize("server_name", ("www.example.com", "app.example.com alias.example.com", "  spaced.example.com "))
def test_a_configured_server_name_still_reads_its_own_cache(plugin, server_name):
    """The control: single-site renders ONE block and the cache directory is the FIRST token of the
    whole string, which is what the job writes. The guard must not move it."""
    expected = PLUGINS[plugin][2] % server_name.split()[0]
    assert expected in fields(run(plugin, server_name).stdout, "READ")


@pytest.mark.parametrize("plugin", sorted(PLUGINS))
def test_the_guard_is_the_thing_under_test(plugin):
    """RULE 13: every assertion above is satisfied by an init that reads nothing at all, because
    most of them assert an absence. Force the guard on and the configured case has to go red."""
    lua_file = PLUGINS[plugin][0]
    original = lua_file.read_text(encoding="utf-8")
    token, subject = ("cert_identifier", "server_names") if plugin == "letsencrypt" else ("first_server", "server_name")
    # `letsencrypt.lua` carries the same line twice -- the multisite branch first, then the
    # single-site one under test -- so the mutation lands on the LAST occurrence, not the first.
    # Nilling the multisite copy changes nothing here and the check below would pass anyway.
    head, sep, tail = original.rpartition(f'local {token} = {subject}:match("%S+")')
    assert sep, f"the {plugin} guard was renamed -- update this test"
    source = head + f"local {token} = nil" + tail
    assert fields(run(plugin, "www.example.com", source=source).stdout, "READ") == []
