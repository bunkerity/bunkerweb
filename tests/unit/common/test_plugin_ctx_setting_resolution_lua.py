"""`plugin:initialize` resolves a multisite setting against the RUNNER-BOUND context.

The default server's three phase runners (`confs/partials/default-server-*-lua.conf`) rebind
`ctx.bw.server_name` to the reserved `default-server` id so the plugins they call read the settings
an operator edits on the Default server page (PO ruling 1). That rebind only reaches a plugin if
`plugin:initialize` hands its context to `utils.get_variable`: without the third argument the
lookup falls back to `ngx.var.server_name` (`utils.lua:243`), which inside the default server block
is the literal `_` from `server_name _;` -- so every value on that page is silently ignored and the
page means nothing.

Both halves under test are the SHIPPED source, lifted out of the two files and executed together:
`utils.get_variable` verbatim, and `plugin:initialize`'s settings loop verbatim. A test that
re-implemented either would pass on a plugin.lua that dropped the argument again.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UTILS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"
PLUGIN_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "plugin.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

# `_` is what `ngx.var.server_name` really is in the default server block (`server_name _;`), and
# `default-server` is what the runner writes into the context. The two tables disagree on ERRORS on
# purpose: which one the loop reads is the whole assertion.
HARNESS = """local VARIABLES = {
  global = { MULTISITE = "yes", ERRORS = "global-value", USE_REDIS = "no" },
  ["default-server"] = { ERRORS = "reserved-value" },
}
local internalstore = { get = function() return VARIABLES, nil end }
local var = { server_name = "_" }
local utils = {}
%s
local get_variable = utils.get_variable

local metadata = { settings = { ERRORS = { context = "multisite" } } }
local err
local self = {
  is_request = true,
  ctx = { bw = { server_name = "%s" } },
  log_throttled = function() end,
}
local WARN = "WARN"
%s
print(tostring(self.variables.ERRORS))
"""


def lua_source(path: Path, pattern: str, what: str) -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.S | re.M)
    assert match, f"{what} not found in {path.name} -- renamed?"
    return match.group(0)


def settings_loop() -> str:
    """`plugin:initialize`'s per-setting resolution loop, verbatim."""
    return lua_source(PLUGIN_LUA, r"^\tself\.variables = \{\}.*?^\tend$", "the settings loop")


def run(tmp_path: Path, bound_server_name: str, loop: str) -> str:
    script = tmp_path / "resolve.lua"
    script.write_text(
        HARNESS % (lua_source(UTILS_LUA, r"^utils\.get_variable = function.*?^end$", "utils.get_variable"), bound_server_name, loop),
        encoding="utf-8",
    )
    result = subprocess.run([LUA, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@needs_lua
def test_the_bound_context_selects_the_reserved_services_setting(tmp_path):
    """The default server case. `ngx.var.server_name` is `_`, which has no table of its own, so
    without the context this returns the global value."""
    assert run(tmp_path, "default-server", settings_loop()) == "reserved-value"


@needs_lua
def test_dropping_the_context_argument_falls_back_to_the_nginx_variable(tmp_path):
    """The mutation, executed rather than described: the same loop with the third argument removed
    reads `_` and silently serves the global value. This is what the shipped line prevents."""
    mutated = settings_loop().replace(", self.ctx)", ")")
    assert mutated != settings_loop(), "the mutation did not apply -- the call was reshaped"
    assert run(tmp_path, "default-server", mutated) == "global-value"


@needs_lua
def test_a_service_block_is_unaffected(tmp_path):
    """No-op everywhere else: `ctx.bw.server_name` is assigned from `var.server_name`
    (`helpers.lua:344`), so in a service block the two are the same string and the argument changes
    nothing. Proven by making them agree."""
    assert run(tmp_path, "_", settings_loop()) == "global-value"
