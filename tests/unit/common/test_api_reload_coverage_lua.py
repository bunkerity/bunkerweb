"""Full-module API reload/push decisions with OS and OpenResty boundaries controlled."""

import pytest

from _lua_core_helpers import BW_MODULES, LUA, run_core

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HARNESS = r"""
local S = OPTIONS
local marker_path = "/var/tmp/bunkerweb/reloading"
local generating_path = "/var/tmp/bunkerweb/generating"
local files = {}
if S.marker then files[marker_path] = S.marker end
files["/var/tmp/bunkerweb_needs_config"] = "pending"
local errno, now, signals, unlocked, closed, swaps = 0, 0, {}, 0, 0, 0
local commands, removed = {}, {}
local ready, ready_reads, proc_reads = false, 0, 0
ngx.HTTP_OK, ngx.HTTP_INTERNAL_SERVER_ERROR = 200, 500
ngx.HTTP_BAD_REQUEST, ngx.HTTP_SERVICE_UNAVAILABLE = 400, 503
ngx.HTTP_BAD_GATEWAY, ngx.HTTP_NOT_FOUND = 502, 404
ngx.worker = { pid = function() return 42 end, exiting = function() return S.exiting or false end }
ngx.var.connection = "77"
ngx.req = {
    start_time = function() return 0 end,
    get_uri_args = function() return {test = S.test} end,
}
ngx.now = function() return now end
ngx.update_time = function() end
ngx.sleep = function(seconds)
    assert(seconds > 0, "poll must advance clock")
    now = now + seconds
    assert(now < 20, "unbounded reload wait")
    if S.ready_after and now >= S.ready_after then ready = true end
    if S.drop_marker and now >= 0.1 then files[marker_path] = nil end
    if S.exit_after and now >= S.exit_after then S.exiting = true end
end
package.loaded["bunkerweb.banlease"] = {}
package.loaded["bit"] = {}
package.loaded["bunkerweb.helpers"] = {}
package.loaded["bunkerweb.datastore"] = { new = function()
    return { get = function(_, key)
        if key:match("^misc_ready_") then
            ready_reads = ready_reads + 1
            if S.race_ready and ready_reads == 2 then return "ok" end
            if ready then return "ok" end
        end
    end }
end }
package.loaded["bunkerweb.utils"] = {
    get_variable = function(key)
        if key == "WORKER_SHUTDOWN_TIMEOUT" then return S.shutdown or "0" end
        return "", "ok"
    end,
    parse_duration = function(value)
        if value == "invalid" then return nil end
        local number = tonumber(value:match("^(%d+)"))
        if value:sub(-2) == "ms" then return number end
        return number * 1000
    end,
}
package.loaded["ngx.process"] = { get_master_pid = function() return 123 end }
package.loaded["resty.signal"] = { kill = function(pid, signal)
    assert(pid == 123)
    signals[#signals + 1] = signal
    if S.signal_error then return nil, S.signal_error end
    return true
end }
package.loaded["resty.lock"] = { new = function(_, dict, options)
    assert(dict == "worker_lock" and options.exptime == 900)
    if S.lock_new_error then return nil, "no memory" end
    return {
        lock = function(_, key)
            assert(key == "pushswap")
            if S.lock_busy then return nil, "timeout" end
            return 0
        end,
        unlock = function() unlocked = unlocked + 1 end,
    }
end }
local parts = 0
package.loaded["resty.upload"] = { new = function(_, size)
    assert(size == 4096)
    if S.upload_error then return nil, "bad multipart" end
    return {
        set_timeout = function(_, ms) assert(ms == 1000) end,
        read = function()
            parts = parts + 1
            if S.read_error then return nil, nil, "truncated body" end
            if parts == 1 then return "header", "ignored" end
            if parts == 2 then return "body", "archive bytes" end
            return "eof"
        end,
    }
end }
package.loaded["bunkerweb.pushswap"] = {
    RESERVED_PREFIX = ".bw-",
    digest_file = function() if not S.no_digest then return "digest" end end,
    read_applied = function() if S.unchanged then return "digest" end end,
    swap = function(destination, staging)
        assert(staging == destination .. "/.bw-staging.42.77")
        swaps = swaps + 1
        if S.swap_throw then error("rename exploded") end
        if S.swap_error then return nil, "rename refused" end
        return true
    end,
    write_applied = function()
        if S.digest_throw then error("digest exploded") end
        if S.digest_error then return nil, "digest refused" end
        return true
    end,
}
os.remove = function(path)
    removed[#removed + 1] = path
    if files[path] == nil then return nil, "No such file" end
    files[path] = nil
    return true
end
local real_open = io.open
local coverage_dir = os.getenv("BW_LUA_COVERAGE_DIR")
io.open = function(path, mode)
    -- LuaCov persists process statistics through the global IO boundary at shutdown.
    if coverage_dir and path:sub(1, #coverage_dir + 1) == coverage_dir .. "/" then
        return real_open(path, mode)
    end
    if path == "/proc/uptime" then
        if S.no_uptime then return nil end
        return {read = function() return "1000.00 500.00" end, close = function() end}
    end
    if S.master and path:sub(1, 10) == "/proc/123/" then
        local value
        if path == "/proc/123/task/123/children" then
            if S.master.no_children then return nil end
            if #signals > 0 and S.master.lost_children then return nil end
            value = #signals == 0 and "42 43 " or (S.master.children or "42 43 ")
        elseif path == "/proc/123/status" then
            value = "Name:\tnginx\n" .. (S.master.status or "SigPnd:\t0000000000000000\nShdPnd:\t0000000000000000\n")
        elseif path == "/proc/123/wchan" then
            value = S.master.wchan
            proc_reads = proc_reads + 1
            if S.replace_marker and proc_reads == 2 then files[marker_path] = S.replace_marker end
        end
        if value == nil then return nil end
        return {read = function() return value end, close = function() end}
    end
    if mode == "w+" then
        if S.open_error then return nil, "disk full" end
        files[path] = ""
        return {
            write = function(_, data) files[path] = files[path] .. data end,
            flush = function() end, close = function() end,
        }
    end
    if files[path] == nil then return nil end
    return {
        read = function(_, size)
            if size == 0 and S.marker_directory then return nil, "Is a directory" end
            local value = files[path]
            if S.race_ready then files[path] = nil return nil end
            return value
        end,
        close = function() end,
    }
end
io.popen = function(command)
    commands[#commands + 1] = command
    if command:find("modsecurity_audit.py", 1, true) then
        if S.audit_throw then error("preflight exploded") end
        if S.audit_missing then return nil end
        return {read = function() return S.audit_output or "ModSecurity audit preflight successful\n" end,
                close = function() end}
    end
    return {read = function() return S.nginx_output or "configuration file /etc/nginx/nginx.conf test is successful" end,
            close = function() end}
end
os.execute = function(command)
    commands[#commands + 1] = command
    if command:find("tar xzf", 1, true) and S.extract_error then return 1 end
    if command:find("sudo", 1, true) then return S.sudo_result or 1 end
    return 0
end
local C = {}
C.fopen = function(path, mode)
    if path == generating_path then
        if S.generator_open_error then errno = 13 return nil end
        if S.generator_missing and mode == "re" then
            if S.generator_race and S.created_generator then return {path = path} end
            errno = 2 return nil
        end
        if mode == "wxe" then
            S.created_generator = true
            if S.generator_race then errno = 17 return nil end
        end
        return {path = path}
    end
    assert(path == marker_path and mode == "wxe")
    if S.marker_create_error then errno = 13 return nil end
    if files[path] ~= nil then errno = 17 return nil end
    files[path] = ""
    return {path = path}
end
C.fileno = function(file) return file end
C.fchmod = function(_, mode) assert(mode == 420) return 0 end
C.flock = function(_, operation)
    if operation == 8 then return 0 end
    if S.generator_lock_error then errno = 9 return -1 end
    if S.generator_busy then errno = 11 return -1 end
    return 0
end
C.fclose = function(file)
    if file.path == generating_path then closed = closed + 1 end
    if file.path == marker_path and S.marker_close_error then return -1 end
    return 0
end
C.fputs = function(token, file)
    if S.marker_write_error then return -1 end
    files[file.path] = token
    return 0
end
package.loaded["ffi"] = { C = C, os = "Linux", cdef = function() end, errno = function() return errno end }
local api = dofile(MODULE)
local self = api:new({bw = {uri = URI}})
local pattern = URI == "/reload" and "^/reload" or "^" .. URI .. "$"
local code, response = api.global.POST[pattern](self)
emit({code = code, response = response, marker = files[marker_path],
    needs_config = files[api.NEEDS_CONFIG_PATH], signals = signals, unlocked = unlocked,
    closed = closed, swaps = swaps, commands = commands, removed = removed, logs = LOGS, elapsed = now,
    upload = files["/var/tmp/bunkerweb/api_" .. URI:sub(2) .. ".42.77.tar.gz"]})
"""


def request(uri="/reload", **options):
    return run_core(BW_MODULES / "api.lua", HARNESS, OPTIONS=options, URI=uri)


def assert_error(result, code, message):
    assert result["code"] == code
    assert result["response"]["status"] == "error"
    assert message in result["response"]["msg"]


@pytest.mark.parametrize("options", [{"lock_new_error": True}, {"lock_busy": True}])
def test_reload_swap_contention_does_not_signal(options):
    result = request(**options)
    assert_error(result, 503, "a push swap is in progress")
    assert result["signals"] == {}
    assert result["unlocked"] == 0


@pytest.mark.parametrize(
    "options,code,message",
    [
        ({"generator_open_error": True}, 500, "cannot open"),
        ({"generator_lock_error": True}, 500, "cannot lock"),
        ({"generator_busy": True}, 503, "a configuration generation is in progress"),
        ({"marker": "old-token"}, 503, "a reload is in progress"),
        ({"marker": "old-token", "marker_directory": True}, 500, "is not a file"),
        ({"marker_create_error": True}, 500, "cannot create"),
        ({"marker_write_error": True}, 500, "cannot write"),
        ({"marker_close_error": True}, 500, "cannot write"),
    ],
)
def test_reload_refuses_unavailable_serialization(options, code, message):
    result = request(**options)
    assert_error(result, code, message)
    assert result["signals"] == {}
    assert result["unlocked"] == 1
    if options.get("generator_busy") or options.get("marker_write_error"):
        assert "marker" not in result
    if code == 503:
        assert 4 <= result["elapsed"] < 4.2


@pytest.mark.parametrize("options", [{}, {"generator_missing": True}, {"marker": "1.2.600"}])
def test_reload_readiness_and_stale_marker_recovery(options):
    result = request(ready_after=0.2, **options)
    assert result["code"] == 200
    assert result["response"] == {"status": "success", "msg": "reload successful", "confirmed": True}
    assert result["signals"] == ["HUP"]
    assert result["unlocked"] == 1
    if options.get("marker"):
        assert any("Removing orphaned reload marker" in entry[1] for entry in result["logs"])


@pytest.mark.parametrize("marker,no_uptime", [("1.2.700", False), ("malformed", False), ("1.2.600", True)])
def test_recent_or_unageable_marker_stays_blocking(marker, no_uptime):
    result = request(marker=marker, no_uptime=no_uptime)
    assert_error(result, 503, "a reload is in progress")
    assert result["marker"] == marker
    assert result["signals"] == {}


@pytest.mark.parametrize(
    "options,message",
    [
        ({"audit_output": "preflight refused"}, "preflight refused"),
        ({"audit_missing": True}, "cannot run ModSecurity"),
        ({"nginx_output": "syntax broken"}, "config check failed: syntax broken"),
        ({"audit_throw": True}, "reload failed:"),
        ({"signal_error": "not found"}, "err = not found"),
        ({"signal_error": "Operation not permitted"}, "err = Operation not permitted"),
    ],
)
def test_failed_checks_remove_own_marker_and_unlock(options, message):
    result = request(**options)
    assert_error(result, 500, message)
    assert "marker" not in result
    assert result["unlocked"] == 1
    if not options.get("signal_error"):
        assert result["signals"] == {}


@pytest.mark.parametrize(
    "options",
    [
        {"nginx_output": "syntax is ok\nPermission denied nginx.pid"},
        {"nginx_output": "syntax is ok\nPermission denied /var/log/nginx/error.log"},
        {"signal_error": "Operation not permitted", "sudo_result": True},
        {"signal_error": "Operation not permitted", "sudo_result": 0},
        {"test": "no", "nginx_output": "broken"},
    ],
)
def test_reload_accepts_supported_validation_and_signal_paths(options):
    result = request(ready_after=0.1, **options)
    assert result["code"] == 200
    assert result["response"]["confirmed"] is True
    if options.get("test") == "no":
        assert not any(" -t " in command for command in result["commands"])


@pytest.mark.parametrize(
    "shutdown,reason", [("invalid", "invalid or unreadable"), ("1", "leaves no time"), ("500ms", "leaves no time"), ("2", "timed out"), ("0", "timed out")]
)
def test_unconfirmed_reload_keeps_marker_and_reports_wait_budget(shutdown, reason):
    result = request(shutdown=shutdown)
    assert result["code"] == 200
    assert result["response"]["confirmed"] is False
    assert reason in result["response"]["msg"]
    assert result["marker"]
    assert result["unlocked"] == 1
    assert result["elapsed"] <= 10.2


@pytest.mark.parametrize("race", [False, True])
def test_removed_marker_requires_readiness_confirmation(race):
    result = request(drop_marker=True, race_ready=race)
    if race:
        assert result["code"] == 200
        assert result["response"]["confirmed"] is True
    else:
        assert_error(result, 500, "initialization did not confirm readiness")
    assert result["unlocked"] == 1


def test_rejected_master_reload_releases_marker_and_reports_failure():
    result = request(master={"wchan": "sigsuspend"})
    assert_error(result, 500, "rejected")
    assert result["response"]["confirmed"] is False
    assert "marker" not in result
    assert result["signals"] == ["HUP"]
    assert result["unlocked"] == 1


@pytest.mark.parametrize(
    "master,exiting",
    [
        ({"wchan": "sigsuspend", "children": "42 43 50 51 "}, False),
        ({"wchan": "sigsuspend"}, True),
        ({"wchan": "hrtimer_nanosleep"}, False),
        ({"wchan": "0"}, False),
        ({}, False),
        ({"wchan": "sigsuspend", "no_children": True}, False),
        ({"wchan": "sigsuspend", "lost_children": True}, False),
        ({"wchan": "sigsuspend", "children": ""}, False),
        ({"wchan": "sigsuspend", "status": "SigPnd:\t0000000000000001\nShdPnd:\t0000000000000000\n"}, False),
        ({"wchan": "sigsuspend", "status": "SigPnd:\t0000000000000000\nShdPnd:\t0000000000000001\n"}, False),
        ({"wchan": "sigsuspend", "status": "unreadable"}, False),
    ],
)
def test_slow_or_unknown_reload_keeps_marker(master, exiting):
    result = request(master=master, exiting=exiting)
    assert result["code"] == 200
    assert result["response"]["confirmed"] is False
    assert result["marker"]
    assert result["unlocked"] == 1


def test_rejection_never_clears_another_reload_token():
    result = request(master={"wchan": "sigsuspend"}, replace_marker="next-token")
    assert_error(result, 500, "rejected")
    assert result["marker"] == "next-token"
    assert result["unlocked"] == 1


def test_queued_graceful_shutdown_is_processed_before_rejection():
    result = request(master={"wchan": "sigsuspend"}, exit_after=0.1)
    assert result["code"] == 200
    assert result["response"]["confirmed"] is False
    assert result["marker"]


def test_no_wait_budget_keeps_marker_even_with_master_observation():
    result = request(shutdown="1", master={"wchan": "sigsuspend"})
    assert result["code"] == 200
    assert result["response"]["confirmed"] is False
    assert result["marker"]
    assert result["elapsed"] == 0


@pytest.mark.parametrize("failure", [False, True])
def test_stop_reports_signal_result(failure):
    result = request("/stop", **({"signal_error": "not found"} if failure else {}))
    assert result["signals"] == ["QUIT"]
    if failure:
        assert_error(result, 500, "err = not found")
    else:
        assert result["response"] == {"status": "success", "msg": "stop successful"}


DESTINATIONS = {
    "/confs": "/etc/nginx",
    "/data": "/data",
    "/cache": "/var/cache/bunkerweb",
    "/custom_configs": "/etc/bunkerweb/configs",
    "/plugins": "/etc/bunkerweb/plugins",
    "/pro_plugins": "/etc/bunkerweb/pro/plugins",
}


@pytest.mark.parametrize("uri,destination", DESTINATIONS.items())
@pytest.mark.parametrize("unchanged", [False, True])
def test_push_aliases_save_or_skip_and_only_confs_clears_repair_marker(uri, destination, unchanged):
    result = request(uri, unchanged=unchanged)
    assert result["code"] == 200
    prefix = "already applied at " if unchanged else "saved data at "
    assert result["response"] == {"status": "success", "msg": prefix + destination}
    assert result["swaps"] == (0 if unchanged else 1)
    assert result["unlocked"] == (0 if unchanged else 1)
    assert "upload" not in result
    assert ("needs_config" not in result) == (uri == "/confs")


@pytest.mark.parametrize(
    "options,code,message",
    [
        ({"upload_error": True}, 400, "bad multipart"),
        ({"open_error": True}, 500, "disk full"),
        ({"read_error": True}, 400, "truncated body"),
        ({"extract_error": True}, 500, "cannot extract archive"),
        ({"audit_output": "preflight refused"}, 500, "preflight refused"),
        ({"audit_throw": True}, 500, "preflight exploded"),
        ({"lock_busy": True}, 503, "another push swap is in progress"),
        ({"generator_open_error": True}, 500, "cannot open"),
        ({"generator_lock_error": True}, 500, "cannot lock"),
        ({"generator_busy": True}, 503, "a configuration generation is in progress"),
        ({"swap_throw": True}, 500, "swap failed:"),
        ({"swap_error": True}, 500, "rename refused"),
    ],
)
def test_failed_push_preserves_repair_marker_and_removes_archive(options, code, message):
    result = request("/confs", **options)
    assert_error(result, code, message)
    assert result["needs_config"] == "pending"
    assert "upload" not in result
    assert result["unlocked"] == int(
        any(options.get(key) for key in ("generator_open_error", "generator_lock_error", "generator_busy", "swap_throw", "swap_error"))
    )
    if options.get("extract_error") or options.get("audit_output") or options.get("lock_busy"):
        assert result["commands"][-1] == "rm -rf '/etc/nginx/.bw-staging.42.77'"


@pytest.mark.parametrize(
    "options",
    [{"generator_missing": True}, {"generator_missing": True, "generator_race": True}, {"digest_error": True}, {"digest_throw": True}, {"no_digest": True}],
)
def test_push_generator_creation_and_nonfatal_digest_failure(options):
    result = request("/confs", **options)
    assert result["code"] == 200
    assert result["response"]["msg"] == "saved data at /etc/nginx"
    assert result["closed"] == 1
    assert result["unlocked"] == 1
    if options.get("digest_error") or options.get("digest_throw"):
        assert any("cannot record the applied digest" in entry[1] for entry in result["logs"])
