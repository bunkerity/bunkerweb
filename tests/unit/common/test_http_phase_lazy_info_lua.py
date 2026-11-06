"""Run real generated HTTP Lua chunks: suppressed INFO must not build messages."""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONFS = ROOT / "src/common/confs"
PHASES = ("set", "access", "header", "log")
LUA = os.environ.get("BW_LUAJIT") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(not LUA, reason="no LuaJIT on PATH (BW_LUAJIT)")


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    # Exercise the real generator, including the service include paths.
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT / "src/common/gen"))
        import Templator as T
        from Configurator import Configurator

        sandbox = tmp_path_factory.mktemp("lazy-info")
        patch.setattr(T, "sep", str(sandbox))
        plugins = sandbox / "plugins"
        pro_plugins = sandbox / "pro-plugins"
        plugins.mkdir()
        pro_plugins.mkdir()
        trees = []
        for multisite in ("no", "yes"):
            config = Configurator(
                str(ROOT / "src/common/settings.json"),
                str(ROOT / "src/common/core"),
                str(plugins),
                str(pro_plugins),
                {"SERVER_NAME": "www.example.com", "MULTISITE": multisite},
                logging.getLogger("lazy-info"),
            ).get_config(None)
            output = sandbox / multisite
            output.mkdir()
            T.Templator(
                str(CONFS), str(ROOT / "src/common/core"), str(plugins), str(pro_plugins), str(output), "/etc/nginx", config, config.copy(), config.copy()
            ).render()
            service = output / "www.example.com" if multisite == "yes" else output
            server = (service / "server.conf").read_text()
            chunks = {}
            for phase in PHASES:
                name = f"{phase}-lua.conf"
                assert f"include /etc/nginx/{'www.example.com/' if multisite == 'yes' else ''}{name};" in server
                text = (service / name).read_text()
                chunks[phase] = text.split("{", 1)[1].rsplit("}", 1)[0]
            trees.append(chunks)
        assert trees[0] == trees[1]
        yield trees[0]


HARNESS = r"""
local level, phase, scenario = tonumber(arg[1]), arg[2], arg[3]
local info_calls, built, encoded, filter_calls = 0, 0, 0, 0
local logs = {}
local token = setmetatable({}, { __concat = function(a, b)
    built = built + 1
    return (type(a) == "table" and "success" or a) .. (type(b) == "table" and "success" or b)
end })
local ctx = { bw = { remote_addr = "192.0.2.1", server_name = "www.example.com", access_done = scenario == "internal" } }
ngx = {
    ERR = 4, WARN = 5, NOTICE = 6, INFO = 7, DEBUG = 8, OK = 0,
    HTTP_MOVED_TEMPORARILY = 302, HTTP_BAD_REQUEST = 400,
    HTTP_TOO_MANY_REQUESTS = 429, HTTP_NOT_ALLOWED = 405,
    ctx = ctx, var = { server_name = "www.example.com" }, shared = { internalstore = {} },
    req = { is_internal = function() return scenario == "internal" end },
    exit = function(s) return s end, redirect = function(u, s) return s end,
}
package.loaded["ngx.errlog"] = { get_sys_filter_level = function()
    filter_calls = filter_calls + 1
    return level
end }
package.loaded["bunkerweb.logger"] = { new = function()
    return { log = function(_, severity, message)
        if severity == ngx.INFO then info_calls = info_calls + 1 end
        if severity <= level then logs[#logs + 1] = severity .. ":" .. message end
    end }
end }
local order = { [phase] = { "missing", "broken", "no_method", "new_fail", "call_fail", "ret_fail", "success" } }
package.loaded["bunkerweb.datastore"] = { new = function()
    return { get = function() return order end }
end }
package.loaded["bunkerweb.cachestore"] = { new = function()
    return { update = function() return true end }
end }
package.loaded["bunkerweb.helpers"] = {
    fill_ctx = function() return true, "success", nil, ctx end,
    save_ctx = function() end,
    require_plugin = function(id)
        if id == "missing" then return nil, "missing plugin" end
        if id == "broken" then return false, "broken plugin" end
        if id == "no_method" then return {} end
        return { [phase] = true, id = id }
    end,
    new_plugin = function(p)
        if p.id == "new_fail" then return false, "new failed" end
        return true, p
    end,
    call_plugin = function(p)
        if p.id == "call_fail" then return false, "call failed" end
        if p.id == "ret_fail" then return true, { ret = false, msg = "ret failed" } end
        return true, { ret = true, msg = token, status = scenario == "status" and 201 or nil,
                       redirect = scenario == "redirect" and "/next" or nil }
    end,
}
package.loaded["bunkerweb.utils"] = {
    is_whitelisted = function() return scenario == "allowed" or scenario == "detect_allowed" end,
    is_ip_whitelisted = function() return false end,
    is_banned = function() return false end,
    set_reason = function() end, get_deny_status = function() return 403 end,
    save_session = function() return true, "session saved" end,
    get_security_mode = function() return scenario:match("^detect") and "detect" or "block" end,
    get_reason = function() return "test", {}, scenario:match("^detect") and "detect" or "block" end,
}
package.loaded["cjson"] = { encode = function()
    encoded = encoded + 1
    return "{}"
end }
local chunk = assert(loadfile(arg[4]))
chunk()
print(info_calls .. "|" .. built .. "|" .. encoded .. "|" .. filter_calls)
print(table.concat(logs, "\n"))
"""


def run_chunk(tmp_path, chunk, phase, level, scenario):
    script = tmp_path / "harness.lua"
    script.write_text(HARNESS)
    source = tmp_path / "chunk.lua"
    source.write_text(chunk)
    result = subprocess.run([LUA, str(script), str(level), phase, scenario, str(source)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    counts, _, logs = result.stdout.partition("\n")
    return tuple(map(int, counts.split("|"))), logs


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("scenario", ["normal", "internal", "allowed", "detect", "detect_allowed", "status", "redirect"])
@pytest.mark.parametrize("level", range(9), ids=["stderr", "emerg", "alert", "crit", "err", "warn", "notice", "info", "debug"])
def test_info_messages_are_lazy_and_visible_output_is_unchanged(tmp_path, rendered, phase, scenario, level):
    chunk = rendered[phase]
    # Remove only this optimization to run the original calls as the output control.
    control = re.sub(r"if info_on then (logger:log\([^\n]*\)) end", r"\1", chunk)
    before, expected = run_chunk(tmp_path, control, phase, level, scenario)
    after, actual = run_chunk(tmp_path, chunk, phase, level, scenario)
    assert before[0] > 0, "control must execute INFO calls"
    assert actual == expected
    if level < 7:
        assert after[0] == 0, f"suppressed INFO reached logger: {after[0]} calls"
        # status/redirect NOTICE lines also concatenate the plugin message.
        if scenario not in ("status", "redirect"):
            assert after[1:3] == (0, 0), "suppressed INFO built strings or encoded JSON"
    else:
        assert after[:3] == before[:3]
    assert after[3] == 1, "query effective log level once per chunk"


def test_all_42_info_calls_have_guards(rendered):
    calls = sum(len(re.findall(r"logger:log\((?:ngx\.)?INFO,", chunk)) for chunk in rendered.values())
    guarded = sum(len(re.findall(r"if info_on then logger:log\((?:ngx\.)?INFO,", chunk)) for chunk in rendered.values())
    assert calls == guarded == 42
