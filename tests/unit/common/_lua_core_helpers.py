"""Shared harness for the Lua behaviour tests of the core ``src/bw/lua/bunkerweb`` modules.

Every test runs the **real** module under plain ``lua`` with OpenResty stubbed at its boundary
(``ngx``, ``ngx.errlog``, ``resty.*``, ``ffi``, ``geoip.mmdb``). Everything else the module requires
(``middleclass``, ``bunkerweb.logger``, ``bunkerweb.rediskeys``) is the real file: ``package.path`` points
at ``src/bw/lua``. The stand-ins are small and driven by globals the test sets, so an assertion is about
what the module decided, not about the stub.

``module_path`` lets a mutation run point a test at a mutated **copy** of a module through an
environment variable (``BW_L4_<NAME>``), without ever touching ``src/``.
"""

import json
import os
from pathlib import Path

from _lua_state_helpers import BASE_LUA, LUA, last_json, run_lua, to_lua  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
BW_LUA = ROOT / "src" / "bw" / "lua"
BW_MODULES = BW_LUA / "bunkerweb"

__all__ = ["BW_LUA", "BW_MODULES", "LUA", "module_path", "run_core", "to_lua"]


def module_path(env_name: str, default: Path) -> Path:
    """The module under test: the real file, or the mutated copy named by ``BW_L4_<env_name>``."""
    return Path(os.environ.get(f"BW_L4_{env_name}", str(default)))


# ``MODULE`` and ``BW_LUA`` are prepended by ``run_core``.
PRELUDE = r"""
package.path = BW_LUA .. "/?.lua;" .. package.path

PHASE = PHASE or "access"
NOW = 1000000
LOGS = {}
NULL = setmetatable({}, { __tostring = function() return "ngx.null" end })

ngx = {
    ERR = "ERR", WARN = "WARN", INFO = "INFO", NOTICE = "NOTICE", OK = "OK",
    null = NULL,
    var = {},
    shared = {},
    config = { subsystem = SUBSYSTEM or "http" },
    get_phase = function() return PHASE end,
    time = function() return NOW end,
}
package.loaded["ngx.errlog"] = { raw_log = function(level, msg) LOGS[#LOGS + 1] = { level, msg } end }
package.loaded["cjson"] = json
unpack = unpack or table.unpack
"""


def run_core(module: Path, body: str, *, subsystem: str = "http", phase: str = "access", **env):
    """Run ``body`` after the prelude and return the value it ``emit``-ted.

    ``env`` entries become Lua globals (through :func:`to_lua`) before the body runs, so a test can
    seed state without string-formatting Lua by hand.
    """
    assigned = "".join(f"{name} = {to_lua(value)}\n" for name, value in env.items())
    header = (
        f"BW_LUA = {json.dumps(str(BW_LUA))}\n"
        f"MODULE = {json.dumps(str(module))}\n"
        f"SUBSYSTEM = {json.dumps(subsystem)}\n"
        f"PHASE = {json.dumps(phase)}\n"
    )
    return last_json(run_lua(BASE_LUA + header + PRELUDE + assigned + body))
