"""``crowdsec:init()`` survives a cache-namespace collision, and ``/crowdsec/ping`` tells the whole
truth about the fleet.

Two halves of the port of dev ``c54c49e7e``, both invisible from the outside:

* ``cache_partition.prefixes()`` returns ``nil`` when two Local APIs hash into one namespace. Every
  loop below it indexes ``prefixes[entry.api_url]``, so without the guard init raises inside
  ``init_by_lua`` -- and the module-level ``bouncers`` / ``challenge_prefixes`` / ``failed_scopes``
  keep whatever the previous reload left there, which a later health check then reports as live.
* ``crowdsec:api()`` used to return on the first bouncer failure and never mention the services
  whose configuration was missing entirely. Those services are served **unchecked**, which is
  exactly what a health endpoint exists to surface, so a missing configuration and an unreachable
  Local API now have to be reported together.

``crowdsec.lua`` is loaded for real through ``dofile`` with OpenResty, middleclass, the plugin base
class and ``bunkerweb.utils`` stubbed, the way ``test_crowdsec_defer_lua`` does. ``io.open`` is
replaced *before* the load because ``read_file`` captures it as an upvalue at module level, which is
what lets a test hand init a fleet of rendered configurations without touching the filesystem.
"""

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[3]
CROWDSEC_LUA = ROOT / "src" / "common" / "core" / "crowdsec" / "crowdsec.lua"
CACHE_PATH = "/var/cache/bunkerweb/crowdsec/"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

SOURCE = CROWDSEC_LUA.read_text(encoding="utf-8")

HARNESS = """
local LOGS = {}

ngx = { ERR = "ERR", WARN = "WARN", OK = 0, HTTP_OK = 200, HTTP_INTERNAL_SERVER_ERROR = 500 }

-- read_file() binds io.open as an upvalue when the chunk loads, so the fleet's rendered
-- configurations are served from here and nothing touches the filesystem.
local FILES = %(files)s
io.open = function(path)
  local content = FILES[path]
  if not content then return nil end
  return { read = function() return content end, close = function() end }
end

package.loaded["middleclass"] = function(_, parent)
  local klass = {}
  klass.__index = klass
  setmetatable(klass, { __index = parent })
  return klass
end

-- The real cache_partition needs resty.sha256, which the plain lua binary has not got. What is
-- under test here is what init() does with its ANSWERS, so the answers are the fixture.
package.loaded["crowdsec.cache_partition"] = {
  api_url = function(content) return content:match("API_URL=(%%S*)") or "" end,
  prefixes = function(api_urls)
    if COLLIDE then return nil, "CrowdSec cache namespace collision" end
    local prefixes, distinct = {}, 0
    local seen = {}
    for _, api_url in ipairs(api_urls) do
      if api_url ~= "" and not seen[api_url] then
        seen[api_url] = true
        distinct = distinct + 1
        prefixes[api_url] = "v2|" .. api_url .. "|"
      end
    end
    return prefixes, distinct
  end,
  -- Real arity: init() calls it with (scope, rendered content, captcha template). Recording all
  -- three is what makes dropping or reordering an argument visible -- a stub taking only `scope`
  -- swallows the other two silently.
  challenge_prefix = function(scope, content, captcha_template)
    CHALLENGE_CALLS[#CHALLENGE_CALLS + 1] = tostring(scope) .. "/" .. tostring(#content) .. "/" .. tostring(captcha_template)
    return "captcha-v2|" .. scope .. "|"
  end,
}

package.loaded["bunkerweb.plugin"] = {
  initialize = function(self) self.logger = { log = function(_, level, msg) LOGS[#LOGS + 1] = level .. " " .. msg end } end,
  ret = function(_, ok, msg, status) return { ret = ok, msg = msg, status = status } end,
  log_throttled = function() end,
}

package.loaded["bunkerweb.utils"] = {
  has_variable = function() return HAS_VARIABLE end,
  get_variable = function() return MULTISITE end,
  get_multiple_variables = function(names)
    if names[1] == "USE_CROWDSEC" then return USE_CROWDSEC end
    return {}
  end,
  get_deny_status = function() return 403 end,
  get_security_mode = function() return "block" end,
  set_reason = function() end,
}

-- One fresh copy of the vendored bouncer per distinct configuration, as new_bouncer() asks for.
package.preload["crowdsec.lib.bouncer"] = function()
  local instance = {}
  instance.init = function(conf_file) INIT_CALLS[#INIT_CALLS + 1] = conf_file return BOUNCER_INIT_OK, "bouncer init refused" end
  instance.GetCaptchaTemplate = function() return CAPTCHA_TEMPLATE end
  instance.Health = function() return HEALTH_OK, HEALTH_ERR, HEALTH_CHECKED_LAPI end
  return instance
end

local crowdsec = dofile([==[%(lua)s]==])

local function plugin()
  local instance = setmetatable({}, crowdsec)
  instance:initialize({})
  instance.is_loading = false
  instance.is_request = false
  instance.variables = {}
  instance.ctx = { bw = { server_name = "app.example.com", uri = "/crowdsec/ping", request_method = "POST" } }
  return instance
end

local function show(prefix, res)
  print(prefix .. "=" .. tostring(res.ret) .. "|" .. tostring(res.msg) .. "|" .. tostring(res.status))
end

%(body)s

table.sort(CHALLENGE_CALLS)
for _, call in ipairs(CHALLENGE_CALLS) do print("CHALLENGE_CALL=" .. call) end
for _, line in ipairs(LOGS) do print("LOG=" .. line) end
"""

DEFAULTS = {
    "COLLIDE": "false",
    "HAS_VARIABLE": "true",
    "MULTISITE": '"yes"',
    "USE_CROWDSEC": '{ ["app.example.com"] = { USE_CROWDSEC = "yes" } }',
    "BOUNCER_INIT_OK": "true",
    "HEALTH_OK": "true",
    "HEALTH_ERR": "nil",
    "HEALTH_CHECKED_LAPI": "true",
    "INIT_CALLS": "{}",
    "CHALLENGE_CALLS": "{}",
    "CAPTCHA_TEMPLATE": '"TPL"',
}

RENDERED = "API_URL=http://127.0.0.1:8080\nAPPSEC_URL=http://127.0.0.1:7422\n"
# Two services on two Local APIs. The two contents are deliberately of DIFFERENT length: the
# cache_partition stub records `#content`, so a port that stopped feeding the rendered
# configuration into the challenge hash shows up as two identical recordings.
TWO_APIS = {
    "app.example.com": "API_URL=http://a:8080\n",
    "shop.example.com": "API_URL=http://bbbb:8080\n",
}
# shop.example.com is enabled but has no rendered configuration: its requests are served
# UNCHECKED until the next reload, which is what the health endpoint has to say.
HALF_A_FLEET = {"app.example.com": RENDERED}
APP_LEN = len(TWO_APIS["app.example.com"])
SHOP_LEN = len(TWO_APIS["shop.example.com"])
BOTH_ENABLED = '{ ["app.example.com"] = { USE_CROWDSEC = "yes" }, ["shop.example.com"] = { USE_CROWDSEC = "yes" } }'


def run(body: str, *, files: dict | None = None, source: str | None = None, **globals_):
    """`files` is the rendered fleet, keyed by service scope; `globals_` overrides the fixture
    globals the stubs read."""
    fleet = {
        CACHE_PATH + (scope + "/" if scope != "global" else "") + "crowdsec.conf": content
        for scope, content in (files if files is not None else {"app.example.com": RENDERED}).items()
    }
    values = dict(DEFAULTS)
    values.update({k: v for k, v in globals_.items()})
    preamble = "\n".join(f"{k} = {v}" for k, v in values.items())
    lua_files = "{ " + ", ".join(f"[ [==[{k}]==] ] = [==[{v}]==]" for k, v in fleet.items()) + " }"
    with TemporaryDirectory() as tmp:
        lua_path = CROWDSEC_LUA
        if source is not None:
            # dofile() takes a path, so a mutated copy has to exist on disk -- never the shipped file.
            lua_path = Path(tmp) / "crowdsec.lua"
            lua_path.write_text(source, encoding="utf-8")
        script = preamble + "\n" + HARNESS % {"files": lua_files, "lua": str(lua_path), "body": body}
        return subprocess.run(["lua", "-e", script], capture_output=True, text=True)


def fields(out: str, key: str) -> list:
    return [line.split("=", 1)[1] for line in out.splitlines() if line.startswith(key + "=")]


def field(out: str, key: str) -> str:
    for line in out.splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    raise AssertionError(f"{key} missing from:\n{out}")


INIT_THEN_PING = """
show("INIT", plugin():init())
show("PING", plugin():api())
"""

# A healthy fleet, then a reload whose namespaces collide. `bouncers` and friends are module-level
# and survive between the two inits exactly as they do between two reloads of the same worker, so
# this is the only shape in which the reset is observable at all.
RELOAD_INTO_COLLISION = """
show("FIRST", plugin():init())
COLLIDE = true
show("SECOND", plugin():init())
show("PING", plugin():api())
"""


class TestANamespaceCollisionIsSurvivable:
    """Two Local APIs hashing into one namespace is a refusal, not a crash and not a half-loaded
    fleet."""

    def test_init_reports_the_collision_instead_of_raising(self):
        res = run(INIT_THEN_PING, files=TWO_APIS, COLLIDE="true", USE_CROWDSEC=BOTH_ENABLED)
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "INIT") == "false|CrowdSec cache namespace collision|nil"

    def test_nothing_is_left_loaded_behind_it(self):
        """A collision leaves every service unchecked, so the health endpoint has to say so rather
        than report the bouncers of the reload before it."""
        res = run(RELOAD_INTO_COLLISION, files=TWO_APIS, USE_CROWDSEC=BOTH_ENABLED)
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "FIRST").startswith("true|2 bouncer(s)")
        assert field(res.stdout, "SECOND") == "false|CrowdSec cache namespace collision|nil"
        assert field(res.stdout, "PING") == "true|No CrowdSec bouncer loaded|500"

    def test_the_failed_scopes_of_the_previous_reload_go_too(self):
        """`bouncers` is only one of the three tables the arm clears. A reload that had a service
        with no rendered configuration, followed by a colliding one, must not keep naming that
        service -- the collision made every service unchecked, not just that one."""
        res = run(RELOAD_INTO_COLLISION, files=HALF_A_FLEET, USE_CROWDSEC=BOTH_ENABLED)
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "FIRST").startswith("true|1 bouncer(s)")
        assert field(res.stdout, "PING") == "true|No CrowdSec bouncer loaded|500"

    def test_clearing_only_the_bouncers_leaves_a_misleading_report(self):
        """Mutation: narrow the reset to `bouncers`. Still a 500, but it names one service as the
        problem when the whole fleet is unchecked."""
        mutated = SOURCE.replace(
            "\t\tbouncers, challenge_prefixes, failed_scopes = {}, {}, {}\n\t\treturn self:ret(false, distinct_apis)",
            "\t\tbouncers = {}\n\t\treturn self:ret(false, distinct_apis)",
        )
        assert mutated != SOURCE, "the collision reset no longer reads as expected -- update this mutation"
        res = run(RELOAD_INTO_COLLISION, files=HALF_A_FLEET, USE_CROWDSEC=BOTH_ENABLED, source=mutated)
        assert field(res.stdout, "PING").startswith("true|No CrowdSec configuration loaded for service(s) shop.example.com")

    def test_the_reset_is_what_stops_the_stale_report(self):
        """Mutation: refuse the collision without clearing the tables, and the health endpoint keeps
        reporting the previous reload's bouncers as live -- on a fleet where nothing is checked."""
        mutated = SOURCE.replace(
            "\t\tbouncers, challenge_prefixes, failed_scopes = {}, {}, {}\n\t\treturn self:ret(false, distinct_apis)",
            "\t\treturn self:ret(false, distinct_apis)",
        )
        assert mutated != SOURCE, "the collision reset no longer reads as expected -- update this mutation"
        res = run(RELOAD_INTO_COLLISION, files=TWO_APIS, USE_CROWDSEC=BOTH_ENABLED, source=mutated)
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "PING").startswith("true|Authenticated Local API checks succeeded"), "stale bouncers"

    def test_the_guard_is_what_makes_it_survivable(self):
        """Mutation: drop the guard and `prefixes[entry.api_url]` indexes nil, inside init_by_lua,
        with no bouncer loaded anywhere in the fleet."""
        assert SOURCE.count("\tif not prefixes then\n") == 1
        mutated = SOURCE.replace("\tif not prefixes then\n", "\tif false then\n")
        res = run(INIT_THEN_PING, files=TWO_APIS, COLLIDE="true", USE_CROWDSEC=BOTH_ENABLED, source=mutated)
        assert res.returncode != 0
        assert "attempt to index" in res.stderr, res.stderr

    def test_the_normal_fleet_still_initializes(self):
        res = run(INIT_THEN_PING, files=TWO_APIS, USE_CROWDSEC=BOTH_ENABLED)
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "INIT").startswith("true|2 bouncer(s) initialized for 2 service(s)")
        assert "partitioned across 2 local API(s)" in field(res.stdout, "INIT")


class TestThePingReportsEveryThingThatIsWrong:

    def test_a_service_without_a_configuration_is_named(self):
        res = run(INIT_THEN_PING, files=HALF_A_FLEET, USE_CROWDSEC=BOTH_ENABLED)
        assert res.returncode == 0, res.stderr
        ping = field(res.stdout, "PING")
        assert ping.startswith("true|No CrowdSec configuration loaded for service(s) shop.example.com")
        assert "bypass CrowdSec until the next reload" in ping
        assert ping.endswith("|500")

    def test_it_is_named_together_with_an_unreachable_local_api(self):
        """Reporting only the first failure hid the other until someone fixed it and pinged again."""
        res = run(
            INIT_THEN_PING,
            files=HALF_A_FLEET,
            USE_CROWDSEC=BOTH_ENABLED,
            HEALTH_OK="false",
            HEALTH_ERR='"Local API request failed"',
        )
        ping = field(res.stdout, "PING")
        assert "shop.example.com" in ping, "the missing configuration"
        assert "Local API request failed" in ping, "the unreachable Local API"

    def test_a_healthy_fleet_says_the_local_api_was_checked(self):
        res = run(INIT_THEN_PING)
        assert field(res.stdout, "PING") == "true|Authenticated Local API checks succeeded; AppSec health is not checked|200"

    def test_a_fleet_without_a_local_api_says_so_instead_of_claiming_a_check(self):
        """AppSec-only services: Health() reports `checked_lapi = false`, and claiming an
        authenticated check succeeded would be a lie."""
        res = run(INIT_THEN_PING, HEALTH_CHECKED_LAPI="false")
        assert field(res.stdout, "PING") == "true|CrowdSec configuration loaded; no Local API configured; AppSec health is not checked|200"

    def test_the_probe_is_refused_when_crowdsec_is_off_fleet_wide(self):
        res = run(INIT_THEN_PING, HAS_VARIABLE="false")
        assert field(res.stdout, "PING") == "true|CrowdSec plugin is not enabled|200"


class TestEveryScopeGetsItsOwnChallengeNamespace:
    """`init()` computes one challenge namespace **per scope**, from that scope's own name, its
    rendered configuration and its captcha template.

    This is the half of the per-service isolation that lives in `crowdsec.lua`; the half that lives
    in `lib/bouncer.lua` (keys actually kept apart once the prefixes differ) is pinned by
    `test_crowdsec_challenge_lua.py::TestChallengeStateIsPerService`. Neither is worth anything
    alone: a constant scope here puts every service back in one namespace with the bouncer-side
    tests still green.
    """

    def test_the_scope_its_configuration_and_its_template_all_reach_the_prefix(self):
        res = run(INIT_THEN_PING, files=TWO_APIS, USE_CROWDSEC=BOTH_ENABLED)
        assert res.returncode == 0, res.stderr
        assert fields(res.stdout, "CHALLENGE_CALL") == [
            f"app.example.com/{APP_LEN}/TPL",
            f"shop.example.com/{SHOP_LEN}/TPL",
        ]

    def test_a_constant_scope_is_what_puts_them_back_together(self):
        """Mutation: hash a constant instead of the scope. Two services keep one namespace, and
        every bouncer-side test stays green because the prefixes it is handed still differ by
        construction."""
        mutated = SOURCE.replace(
            "cache_partition.challenge_prefix(entry.scope, entry.content",
            'cache_partition.challenge_prefix("shared", entry.content',
        )
        assert mutated != SOURCE, "the challenge_prefix call no longer reads as expected -- update this mutation"
        res = run(
            INIT_THEN_PING,
            files=TWO_APIS,
            USE_CROWDSEC=BOTH_ENABLED,
            source=mutated,
        )
        assert fields(res.stdout, "CHALLENGE_CALL") == [f"shared/{APP_LEN}/TPL", f"shared/{SHOP_LEN}/TPL"]

    def test_the_rendered_configuration_reaches_it_too(self):
        """Mutation: drop the configuration from the call. Two services whose rendered configuration
        differs -- different Local APIs, different AppSec, different captcha policy -- would then be
        told apart by name only, and a rename would silently reuse the old namespace."""
        mutated = SOURCE.replace(
            "cache_partition.challenge_prefix(entry.scope, entry.content",
            'cache_partition.challenge_prefix(entry.scope, ""',
        )
        assert mutated != SOURCE, "the challenge_prefix call no longer reads as expected -- update this mutation"
        res = run(
            INIT_THEN_PING,
            files=TWO_APIS,
            USE_CROWDSEC=BOTH_ENABLED,
            source=mutated,
        )
        assert fields(res.stdout, "CHALLENGE_CALL") == ["app.example.com/0/TPL", "shop.example.com/0/TPL"]

    def test_reporting_only_the_first_failure_is_what_hid_the_other(self):
        """Mutation: return on the bouncer failure instead of remembering it. The service with no
        rendered configuration disappears from the answer, and stays hidden until someone fixes the
        Local API and pings again -- which is how it went unnoticed."""
        assert SOURCE.count("\n\t\t\t\t\tbreak\n") == 1
        mutated = SOURCE.replace(
            "\n\t\t\t\t\tbreak\n",
            "\n\t\t\t\t\treturn self:ret(true, bouncer_failure, HTTP_INTERNAL_SERVER_ERROR)\n",
        )
        res = run(
            INIT_THEN_PING,
            files=HALF_A_FLEET,
            USE_CROWDSEC=BOTH_ENABLED,
            HEALTH_OK="false",
            HEALTH_ERR='"Local API request failed"',
            source=mutated,
        )
        ping = field(res.stdout, "PING")
        assert "Local API request failed" in ping
        assert "shop.example.com" not in ping, "the missing configuration was hidden by the early return"
