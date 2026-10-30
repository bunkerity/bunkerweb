"""Four request-path fixes ported from dev, and the two places a verbatim port would have hurt.

* **F-LUA-1** (`6396a2236`) `utils.get_variable` — a per-service table that *exists* but does not
  carry the requested key used to shadow the global value, so the caller got "not found" for a
  setting that was configured. Every multisite service with a partial settings table was affected.
* **F-LUA-3** (`331b7c1aa`) `utils.get_reason` — when the upstream itself answers with the deny
  status, BunkerWeb labelled the request its own `"unknown"` denial. That misattribution lands in
  the access log, in Reports and in the metrics counters.
* **F-LUA-4** (`60bf0d783`) `whitelist:init` — the stored per-service lists only ever contained what
  the URL download job wrote, so a manually configured `WHITELIST_*` entry never reached
  `utils.is_ip_whitelisted` or the default server.
* **F-LUA-5** (`ad83bdbf7`) the ban branch in both request phases — the whitelist flag tested before
  it reflects only the *cache*, which nothing can fill while the IP stays banned, so whitelisting a
  banned IP could never rescue it.

**F-LUA-4 depends on F-LUA-1** and the pair must stay together: the new lookup is
``get_variable("WHITELIST_" .. kind, true, {bw = {server_name = key}})``, which is exactly the call
shape F-LUA-1 repairs. Without it, any service with a partial settings table silently drops its
globally configured whitelist entries — the fix would look applied and do nothing for those services.

**F-LUA-5 was relocated, not applied.** dev's stream half predates 1.7's `security_mode` detect
branch and always denies; applying that hunk verbatim would have deleted detect mode from the stream
path. The guard below pins the detect branch in both phases so a future re-port cannot quietly drop
it. (`F-LUA-7`/`a2ffba152` needed nothing — 1.7 already carries both halves, `.luacheckrc` included.)
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UTILS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"
WHITELIST_LUA = ROOT / "src" / "common" / "core" / "whitelist" / "whitelist.lua"
ACCESS_CONF = ROOT / "src" / "common" / "confs" / "server-http" / "access-lua.conf"
PREREAD_CONF = ROOT / "src" / "common" / "confs" / "server-stream" / "preread-stream-lua.conf"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

# `utils.lua` requires resty and mmdb at module level, so it cannot be dofile'd outside OpenResty.
# The function's real source is lifted instead -- the behaviour under test is the function's own.
GET_VARIABLE_HARNESS = """local VARIABLES = {
  global = { MULTISITE = "yes", USE_ANTIBOT = "captcha", LOG_LEVEL = "info" },
  ["svc.example.com"] = { USE_ANTIBOT = "no" },
}
local internalstore = { get = function() return VARIABLES, nil end }
local var = { server_name = "svc.example.com" }
local utils = {}
%s
local value, err = utils.get_variable(arg[1], true)
print(tostring(value) .. "|" .. tostring(err))
"""


def lua_source(name: str) -> str:
    match = re.search(rf"^utils\.{name} = function.*?^end$", UTILS_LUA.read_text(encoding="utf-8"), re.S | re.M)
    assert match, f"utils.{name} not found -- renamed?"
    return match.group(0)


@needs_lua
@pytest.mark.parametrize(
    ("variable", "expected"),
    [
        ("USE_ANTIBOT", "no|success"),  # the service overrides it: service value still wins
        ("LOG_LEVEL", "info|success"),  # F-LUA-1: only globally set, must survive a partial table
        ("NOPE", "nil|not found"),  # set nowhere: must still be "not found", not a false fallback
    ],
)
def test_a_partial_service_table_does_not_hide_a_global_setting(tmp_path, variable, expected):
    script = tmp_path / "gv.lua"
    script.write_text(GET_VARIABLE_HARNESS % lua_source("get_variable"), encoding="utf-8")
    result = subprocess.run([LUA, str(script), variable], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


@needs_lua
@pytest.mark.parametrize(
    ("upstream_status", "ours"),
    [
        (None, True),  # no upstream was contacted: the denial is BunkerWeb's
        ("403", False),  # F-LUA-3: the upstream said 403, not us
        ("502, 403", False),  # nginx joins retries with a comma; the LAST one is the answer
        ("502 : 403", False),  # and with " : " across an internal redirect
        ("200", True),  # upstream was fine, something here turned it into a 403
        ("403, 200", True),  # the final attempt succeeded, so a 403 now is ours
        ("-", True),  # nginx writes "-" when there was no upstream
        ("", True),  # empty string is truthy in Lua: must not crash, must not misattribute
    ],
)
def test_an_upstream_denial_is_not_credited_to_the_waf(tmp_path, upstream_status, ours):
    """The expression alone -- the rest of get_reason needs a live request context."""
    literal = "nil" if upstream_status is None else '"%s"' % upstream_status
    script = tmp_path / "us.lua"
    script.write_text(
        "local upstream_status = %s\n"
        "local ngx = { status = 403 }\n"
        'local upstream_denied = upstream_status and tonumber(upstream_status:match("(%%d%%d%%d)%%s*$")) == ngx.status\n'
        'print((ngx.status == 403 and not upstream_denied) and "unknown" or "not-ours")\n' % literal,
        encoding="utf-8",
    )
    result = subprocess.run([LUA, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ("unknown" if ours else "not-ours")


def test_the_upstream_probe_matches_the_shipped_expression_and_is_actually_used():
    """Anti-drift: the parametrised cases above test a *copy* of the expression, so the shipped one
    must match it -- **and must gate the branch**.

    An earlier version of this test asserted only that the probe was computed. Deleting
    ``and not upstream_denied`` from the ``if`` left it green while restoring the whole defect: the
    probe was still there, just ignored. Computing a value is not using it.
    """
    body = lua_source("get_reason")
    assert 'tonumber(upstream_status:match("(%d%d%d)%s*$")) == ngx.status' in body, "the probe expression drifted from the one tested above"
    assert "if ngx.status == utils.get_deny_status() and not upstream_denied then" in body, "the probe is computed but no longer gates the unknown branch"


def test_configured_whitelist_entries_reach_the_stored_lists():
    body = WHITELIST_LUA.read_text(encoding="utf-8")
    merge = re.search(r'get_variable\("WHITELIST_" \.\. kind, true, \{ bw = \{ server_name = key \} \}\)', body)
    assert merge, "F-LUA-4: configured WHITELIST_* entries are not merged into the stored lists"
    # Order matters: merging after the dedup would leave duplicates in the stored list.
    assert body.index(merge.group(0)) < body.index("whitelists[kind] = deduplicate_list(whitelists[kind])")


@pytest.mark.parametrize("conf", [ACCESS_CONF, PREREAD_CONF], ids=["http-access", "stream-preread"])
def test_a_banned_ip_is_re_checked_against_the_whitelist(conf):
    body = conf.read_text(encoding="utf-8")
    assert "local is_ip_whitelisted = utils.is_ip_whitelisted" in body, f"{conf.name}: the helper is not in scope"
    banned = body.index("elseif banned then")
    check = body.index("local whitelisted, wl_info = is_ip_whitelisted(", banned)
    marked = body.index("ctx.bw.is_banned = true", banned)
    assert check < marked, f"{conf.name}: the re-check must happen BEFORE the request is marked banned"


@pytest.mark.parametrize("conf", [ACCESS_CONF, PREREAD_CONF], ids=["http-access", "stream-preread"])
def test_detect_mode_survives_in_the_ban_branch(conf):
    """dev's stream hunk predates this branch and always denies. Porting it verbatim would delete
    detect mode from the stream path -- this is the guard against a future re-port doing that."""
    body = conf.read_text(encoding="utf-8")
    banned = body.index("elseif banned then")
    end = body.index('logger:log(INFO, "IP " .. ctx.bw.remote_addr .. " is not banned")', banned)
    branch = body[banned:end]
    assert 'if security_mode == "block" then' in branch, f"{conf.name}: detect mode is gone from the ban branch"
    assert "detected IP " in branch, f"{conf.name}: the detect-mode log line is gone"


# --- F-LUA-5 behavioural half (RULE 12) ------------------------------------------------------
# The two tests above assert that the whitelist re-check EXISTS and runs before the ban is marked.
# Both survive the realistic revert, which is a neutering rather than a deletion: keep the helper
# in scope, keep the call where it is, and ignore what it returns. A whitelisted banned IP is then
# still banned and every source-order assertion passes. These run the branch instead.
BAN_BRANCH_HARNESS = """local DENY = 403
local OK = 0
local exited = nil
local logged = {}
local ctx = { bw = { remote_addr = "1.2.3.4", server_name = "svc.example.com" } }
local reason, reason_data, ttl = "manual", {}, 60
local security_mode = "%s"
local WHITELISTED = %s
local is_ip_whitelisted = function() return WHITELISTED, "test-info" end
local set_reason = function() end
local save_ctx = function() end
local get_deny_status = function() return DENY end
local exit = function(code) exited = code return code end
local logger = { log = function(_, _, msg) logged[#logged + 1] = msg end }
local WARN, ERR = "WARN", "ERR"
local banned = true
-- wrapped in a function because the shipped branch ends in `return exit(...)`: at script level that
-- returns before the print and the harness reports an empty line, which reads as a parse failure.
local function branch()
%s
end
branch()
print(tostring(ctx.bw.is_banned) .. "|" .. tostring(exited) .. "|" .. table.concat(logged, "~"))
"""


def ban_branch(conf: Path) -> str:
    """The shipped branch, lifted verbatim. `elseif` becomes `if` so it can stand alone; nothing else
    is rewritten, because a rewritten branch would test the rewrite."""
    body = conf.read_text(encoding="utf-8")
    start = body.index("elseif banned then")
    end = body.index('logger:log(INFO, "IP " .. ctx.bw.remote_addr .. " is not banned")', start)
    branch = body[start:end].replace("elseif banned then", "if banned then", 1)
    return branch[: branch.rindex("else")] + "end"


def run_branch(tmp_path: Path, conf: Path, security_mode: str, whitelisted: str) -> tuple:
    script = tmp_path / "branch.lua"
    script.write_text(BAN_BRANCH_HARNESS % (security_mode, whitelisted, ban_branch(conf)))
    result = subprocess.run([LUA, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    is_banned, exited, logs = result.stdout.strip().split("|")
    return is_banned, exited, logs


@needs_lua
@pytest.mark.parametrize("conf", [ACCESS_CONF, PREREAD_CONF], ids=["http-access", "stream-preread"])
def test_a_whitelisted_ip_is_not_banned_even_in_block_mode(tmp_path, conf):
    """The behaviour F-LUA-5 exists for. Marker tests cannot see this: they check the call is made,
    not that its result decides anything."""
    is_banned, exited, logs = run_branch(tmp_path, conf, "block", "true")

    assert is_banned == "nil", f"{conf.name}: a whitelisted IP was still marked banned"
    assert exited == "nil", f"{conf.name}: a whitelisted IP was still denied"
    assert "ignoring the ban" in logs


@needs_lua
@pytest.mark.parametrize("conf", [ACCESS_CONF, PREREAD_CONF], ids=["http-access", "stream-preread"])
def test_a_non_whitelisted_ip_is_denied_in_block_mode(tmp_path, conf):
    """The control: without it, a branch that never bans anything would pass the test above."""
    is_banned, exited, logs = run_branch(tmp_path, conf, "block", "false")

    assert is_banned == "true", f"{conf.name}: the ban was not applied"
    assert exited == "403", f"{conf.name}: block mode did not deny"


@needs_lua
@pytest.mark.parametrize(
    ("conf", "expected_exit"),
    # The two paths leave detect mode differently ON PURPOSE, and the conf says so: HTTP calls
    # exit(OK) to skip the remaining access plugins, stream returns bare because a stream `exit(OK)`
    # is not the same primitive. This asserted "0" for both at first and stream failed -- the test
    # was wrong, not the code. Encoded per path rather than relaxed to accept either, since "either"
    # would also accept a stream branch that had silently started denying.
    [(ACCESS_CONF, "0"), (PREREAD_CONF, "nil")],
    ids=["http-access", "stream-preread"],
)
def test_detect_mode_marks_the_ban_but_does_not_deny(tmp_path, conf, expected_exit):
    """dev's stream hunk always denies. This is the same guard as the source-order one above, run
    rather than read -- it is what a verbatim re-port would break."""
    is_banned, exited, logs = run_branch(tmp_path, conf, "detect", "false")

    assert is_banned == "true", f"{conf.name}: detect mode must still record the ban"
    assert exited == expected_exit, f"{conf.name}: detect mode must not deny (403 would be a denial)"
    assert exited != "403", f"{conf.name}: detect mode denied the request"
    assert "detected IP " in logs


# --- F-LUA-4 behavioural half (RULE 12) ------------------------------------------------------
# The source-order test above asserts the merge call exists and sits before the dedup. Both facts
# survive the neutering: `table.insert({}, data)` keeps the call, keeps the order, and discards the
# entry. The stored list then holds only what the download job wrote -- which is the bug F-LUA-4
# fixed. These run the loop.
WHITELIST_MERGE_HARNESS = """local CACHED = %s
local CONFIGURED = %s
local URLS = %s
local whitelists = { IP = {} }
local get_variable = function(name)
  if name == "WHITELIST_IP" then return CONFIGURED end
  -- The loop reads <KIND>.list only while WHITELIST_<KIND>_URLS is configured, because that
  -- setting is the file's only producer and a list withdrawn from the configuration must stop
  -- being enforced. CACHED stands for a list the download job just wrote, so the default here
  -- configures the URLs; run_merge(urls="nil") exercises the retired case.
  if name == "WHITELIST_IP_URLS" then return URLS end
  return nil
end
local open = function()
  if #CACHED == 0 then return nil end
  local n = 0
  return { lines = function() return function() n = n + 1 return CACHED[n] end end, close = function() end }
end
local deduplicate_list = function(list)
  local seen, out = {}, {}
  for _, v in ipairs(list) do
    if not seen[v] then seen[v] = true out[#out + 1] = v end
  end
  return out
end
local key, i = "svc.example.com", 0
%s
print(table.concat(whitelists.IP, ","))
"""


def whitelist_merge_loop() -> str:
    body = WHITELIST_LUA.read_text(encoding="utf-8")
    start = body.index("for kind, _ in pairs(whitelists) do")
    end = body.index("whitelists[kind] = deduplicate_list(whitelists[kind])", start)
    return body[start:end] + "whitelists[kind] = deduplicate_list(whitelists[kind])\n\t\tend"


def run_merge(tmp_path: Path, cached: str, configured: str, urls: str = '"http://custom-api:8000/list/ip"') -> list:
    script = tmp_path / "merge.lua"
    script.write_text(WHITELIST_MERGE_HARNESS % (cached, configured, urls, whitelist_merge_loop()))
    result = subprocess.run([LUA, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return [entry for entry in result.stdout.strip().split(",") if entry]


@needs_lua
def test_configured_whitelist_entries_end_up_in_the_stored_list(tmp_path):
    """The behaviour F-LUA-4 exists for: before it, the stored lists held only what the download job
    wrote, so a manually configured WHITELIST_IP never reached utils.is_ip_whitelisted."""
    stored = run_merge(tmp_path, '{"10.0.0.1"}', '"1.1.1.1 2.2.2.2"')

    assert "1.1.1.1" in stored and "2.2.2.2" in stored, "configured entries never reached the stored list"
    assert "10.0.0.1" in stored, "merging the configured entries dropped the downloaded ones"


@needs_lua
def test_an_entry_in_both_sources_is_stored_once(tmp_path):
    """Pins the ORDER by its consequence rather than by source position: merging after the dedup
    leaves the duplicate in, and a duplicate is what a reader would see."""
    stored = run_merge(tmp_path, '{"10.0.0.1", "1.1.1.1"}', '"1.1.1.1"')

    assert stored.count("1.1.1.1") == 1, f"duplicate survived -- merge ran after the dedup: {stored}"


@needs_lua
def test_no_configured_entries_leaves_the_downloaded_list_intact(tmp_path):
    """The control. Without it a loop that fabricated entries would pass both tests above."""
    stored = run_merge(tmp_path, '{"10.0.0.1"}', "nil")

    assert stored == ["10.0.0.1"]


@needs_lua
def test_the_downloaded_list_is_ignored_once_its_url_setting_is_gone(tmp_path):
    """Keeps the three tests above honest. They all feed CACHED through the file read, so a harness
    whose WHITELIST_IP_URLS answers nil stops loading it and they pass on an empty list instead --
    which is exactly how this file went red-then-vacuous when the retired-list guard landed. The
    guard itself is covered in test_whitelist_retired_lists_lua.py; this only pins that CACHED is
    still reaching the loop."""
    stored = run_merge(tmp_path, '{"10.0.0.1"}', '"1.1.1.1"', urls="nil")

    assert stored == ["1.1.1.1"], "a retired IP.list must not be read, but the configured entry must survive"
