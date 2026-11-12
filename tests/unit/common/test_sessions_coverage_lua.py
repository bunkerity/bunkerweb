"""Session configuration, request checks and backend transitions using the real Lua plugin."""

import json

import pytest
from _lua_state_helpers import BASE_LUA, CORE, LUA, PLUGIN_LUA, ROOT, last_json, run_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")
MODULE = CORE / "sessions" / "sessions.lua"

BOUNDARIES = r"""
package.loaded["cjson"] = json
ngx.shared = {sessions_revocation={}}
VARIABLES = {SESSIONS_SECRET="secret",SESSIONS_NAME="sid",SESSIONS_IDLING_TIMEOUT="30m",
    SESSIONS_ROLLING_TIMEOUT="1h",SESSIONS_ABSOLUTE_TIMEOUT="1d",SESSIONS_CHECK_IP="yes",SESSIONS_CHECK_USER_AGENT="yes"}
ENV = {USE_REDIS="no",REDIS_HOST="redis.example",REDIS_PORT="6380",REDIS_DATABASE="0",
    REDIS_TIMEOUT="2s",REDIS_KEEPALIVE_IDLE="30s",REDIS_KEEPALIVE_POOL="12",REDIS_SSL="yes",REDIS_SSL_VERIFY="yes",
    REDIS_USERNAME="user",REDIS_PASSWORD="fixture"}
local u=package.loaded["bunkerweb.utils"]
u.get_variable=function(key) if key==MISSING_VAR then return nil,"lookup failed" end return ENV[key] or "" end
u.parse_duration=dofile(LUA_ROOT .. "/bunkerweb/duration.lua").parse_duration
u.rand=function(n) return string.rep("r",n) end
package.path=LUA_ROOT .. "/?.lua;" .. package.path
package.loaded["resty.session"]={init=function(config) CONFIG=config end}
CLUSTERSTORE={
    connect=function() if CONNECT_ERROR then return false,CONNECT_ERROR end return true end,
    call=function(_,cmd) assert(cmd=="ping") if PING_ERROR then return nil,PING_ERROR end return PING_OK end,
    close=function() CLOSED=true end,
}
PING_OK=true
GETS={}
local original_init=package.loaded["bunkerweb.plugin"].initialize
package.loaded["bunkerweb.plugin"].initialize=function(self,name,ctx)
    original_init(self,name,ctx)
    local get=self.internalstore.get
    self.internalstore.get=function(store,key) GETS[key]=(GETS[key] or 0)+1 return get(store,key) end
    self.kind=KIND or "http"
    self.log_throttled=function(_,level,key,msg) LOGS[#LOGS+1]={level,msg} end
    self.flush_log_recaps=function() FLUSHED=true end
end
"""


def run(body):
    script = BASE_LUA + PLUGIN_LUA + f"\nLUA_ROOT={json.dumps(str(ROOT / 'src/bw/lua'))}\n" + BOUNDARIES
    return last_json(run_lua(script + f"\nlocal plugin=dofile({json.dumps(str(MODULE))})\n" + body))


NEW = 'local p=new_plugin(plugin,{remote_addr="203.0.113.1",http_user_agent="fixture-agent"})\n'


def test_cookie_configuration_and_request_checks():
    out = run(NEW + """
local initialized=p:init()
local configured=p:set()
emit({initialized=initialized,configured=configured,config=CONFIG,checks=p.ctx.bw.sessions_checks,store=STORE})
""")
    assert out["initialized"]["ret"] and out["configured"]["ret"]
    assert out["config"] == {
        "secret": "secret",
        "cookie_name": "sid",
        "idling_timeout": 1800,
        "rolling_timeout": 3600,
        "absolute_timeout": 86400,
        "storage": "cookie",
        "revocation": "shm",
        "revocation_fail_mode": "open",
        "revocation_cache_ttl": 0,
        "revocation_error_cache_ttl": 0,
        "shm": {"zone": "sessions_revocation", "prefix": "revoked_"},
    }
    assert sorted(out["checks"]) == [["IP", "203.0.113.1"], ["USER_AGENT", "fixture-agent"]]
    assert out["store"]["storage_sessions_STORAGE"] == "cookie"
    assert json.loads(out["store"]["storage_sessions_CONFIG"]) == out["config"]


def test_checks_disabled_and_missing_user_agent():
    out = run(NEW + """
VARIABLES.SESSIONS_CHECK_IP="no" p.ctx.bw.http_user_agent=nil
p:set() local ua=p.ctx.bw.sessions_checks
VARIABLES.SESSIONS_CHECK_USER_AGENT="no" p:set()
emit({ua=ua,none=p.ctx.bw.sessions_checks})
""")
    assert out == {"ua": [["USER_AGENT", ""]], "none": {}}


@pytest.mark.parametrize("setup", ["IS_LOADING=true", 'KIND="stream"'])
def test_lifecycle_skips_loading_and_stream(setup):
    out = run(setup + "\n" + NEW + "emit({init=p:init(),set=p:set(),timer=p:timer(),config=CONFIG})")
    assert out["init"]["msg"] == "init not needed"
    assert out["set"]["msg"] == "set not needed"
    assert out["timer"]["msg"] == "timer not needed"
    assert "config" not in out


@pytest.mark.parametrize("cached", [False, True])
def test_random_secret_and_cookie_name_are_reused(cached):
    setup = 'VARIABLES.SESSIONS_SECRET="random" VARIABLES.SESSIONS_NAME="random"\n'
    if cached:
        setup += 'STORE.storage_sessions_SESSIONS_SECRET="old-secret" STORE.storage_sessions_SESSIONS_NAME="old-name"\n'
    out = run(setup + NEW + "local result=p:init()\nemit({result=result,config=CONFIG,store=STORE})")
    assert out["result"]["ret"]
    assert out["config"]["secret"] == ("old-secret" if cached else "r" * 16)
    assert out["config"]["cookie_name"] == ("old-name" if cached else "r" * 16)
    assert out["store"]["storage_sessions_SESSIONS_SECRET"] == out["config"]["secret"]
    assert out["store"]["storage_sessions_SESSIONS_NAME"] == out["config"]["cookie_name"]


RANDOM = 'VARIABLES.SESSIONS_SECRET="random" VARIABLES.SESSIONS_NAME="random"\n'
RANDOM_KEYS = ("storage_sessions_SESSIONS_SECRET", "storage_sessions_SESSIONS_NAME")


def test_request_constructor_does_not_read_random_values_from_shared_memory():
    out = run(RANDOM + NEW + """
p:init()
GETS={}
for _=1,5 do new_plugin(plugin,{remote_addr="203.0.113.1"}) end
emit({gets=GETS})
""")
    assert not any(out["gets"].get(key) for key in RANDOM_KEYS), out["gets"]


def test_random_values_are_recovered_once_and_exposed_on_randoms():
    out = run(RANDOM + 'STORE.storage_sessions_SESSIONS_SECRET="old-secret" STORE.storage_sessions_SESSIONS_NAME="old-name"\n' + NEW + """
p:init()
local q=new_plugin(plugin,{remote_addr="203.0.113.1"})
emit({gets=GETS,config=CONFIG,request_randoms=q.randoms,sets=STORE_SET_LOG})
""")
    expected = {"SESSIONS_SECRET": "old-secret", "SESSIONS_NAME": "old-name"}
    assert out["config"]["secret"] == "old-secret" and out["config"]["cookie_name"] == "old-name"
    assert out["request_randoms"] == expected
    assert [out["gets"].get(key) for key in RANDOM_KEYS] == [1, 1]
    assert not any(key in out["sets"] for key in RANDOM_KEYS)


def test_generated_random_values_are_stored_once_and_survive_a_reload():
    out = run(RANDOM + NEW + """
local n=0
u.rand=function(len) n=n+1 return string.rep(tostring(n),len) end
p:init()
local first={secret=CONFIG.secret,name=CONFIG.cookie_name,randoms=new_plugin(plugin,{remote_addr="203.0.113.1"}).randoms}
local reloaded=new_plugin(plugin,{remote_addr="203.0.113.1"})
reloaded:init()
emit({first=first,second=CONFIG,randoms=new_plugin(plugin,{remote_addr="203.0.113.1"}).randoms,store=STORE,calls=n})
""")
    assert out["calls"] == 2  # one secret and one name, nothing regenerated on reload
    assert out["first"]["randoms"] == {"SESSIONS_SECRET": "1" * 16, "SESSIONS_NAME": "2" * 16}
    assert out["second"]["secret"] == out["first"]["secret"] and out["second"]["cookie_name"] == out["first"]["name"]
    assert out["randoms"] == out["first"]["randoms"]
    assert out["store"]["storage_sessions_SESSIONS_SECRET"] == "1" * 16


def test_explicit_setting_change_replaces_the_random_value_on_next_configuration():
    out = run(RANDOM + NEW + """
p:init()
VARIABLES.SESSIONS_SECRET="fixed-secret" VARIABLES.SESSIONS_NAME="fixed-name"
local q=new_plugin(plugin,{remote_addr="203.0.113.1"})
q:init()
local explicit={config=CONFIG,randoms=new_plugin(plugin,{remote_addr="203.0.113.1"}).randoms}
VARIABLES.SESSIONS_SECRET="random" VARIABLES.SESSIONS_NAME="random"
local r=new_plugin(plugin,{remote_addr="203.0.113.1"})
r:init()
emit({explicit=explicit,back=CONFIG,back_randoms=new_plugin(plugin,{remote_addr="203.0.113.1"}).randoms})
""")
    assert out["explicit"]["config"]["secret"] == "fixed-secret"
    assert out["explicit"]["config"]["cookie_name"] == "fixed-name"
    assert out["explicit"]["randoms"] == {}
    # the stored random value comes back when the setting returns to "random"
    assert out["back"]["secret"] == "r" * 16 and out["back_randoms"]["SESSIONS_SECRET"] == "r" * 16


def test_standalone_redis_configuration():
    out = run(NEW + 'ENV.USE_REDIS="yes"\np:init()\nemit(CONFIG)')
    assert out["storage"] == "redis"
    assert out["redis"] == {
        "prefix": "sessions_",
        "username": "user",
        "password": "fixture",
        "connect_timeout": 2000,
        "send_timeout": 2000,
        "read_timeout": 2000,
        "keepalive_timeout": 30000,
        "pool_size": 12,
        "ssl": True,
        "ssl_verify": True,
        "database": 0,
        "host": "redis.example",
        "port": 6380,
    }


def test_sentinel_configuration_parses_ipv6_and_default_port():
    out = run(NEW + """
ENV.USE_REDIS="yes" ENV.REDIS_SENTINEL_HOSTS="sentinel.example [2001:db8::1]:26380"
ENV.REDIS_SENTINEL_MASTER="primary" ENV.REDIS_SENTINEL_USERNAME="sentinel-user" ENV.REDIS_SENTINEL_PASSWORD="fixture-sentinel"
p:init() emit(CONFIG)
""")
    redis = out["redis"]
    assert out["storage"] == "redis" and redis["master"] == "primary" and redis["role"] == "master"
    assert redis["sentinels"] == [{"host": "sentinel.example", "port": 26379}, {"host": "[2001:db8::1]", "port": 26380}]
    assert redis["sentinel_username"] == "sentinel-user" and redis["sentinel_password"] == "fixture-sentinel"
    assert "host" not in redis


def test_cluster_configuration_bounds_retries_and_omits_database():
    out = run(NEW + 'ENV.USE_REDIS="yes" ENV.REDIS_CLUSTER_NODES="redis.example:7000 [2001:db8::1]:7001"\np:init()\nemit(CONFIG)')
    redis = out["redis"]
    assert out["storage"] == "redis"
    assert redis["nodes"] == [{"ip": "redis.example", "port": 7000}, {"ip": "[2001:db8::1]", "port": 7001}]
    assert redis["name"] == "bw" and redis["lock_zone"] == "redis_cluster_locks"
    assert redis["lock_prefix"] == "bw_sessions_refresh_"
    assert redis["max_redirections"] == 2 and redis["max_connection_attempts"] == 1
    assert redis["max_connection_timeout"] == 2000 and "database" not in redis


def test_invalid_cluster_config_falls_back_to_cookie():
    out = run(NEW + 'ENV.USE_REDIS="yes" ENV.REDIS_CLUSTER_NODES="redis.example:7000" ENV.REDIS_DATABASE="1"\np:init()\nemit({config=CONFIG,logs=LOGS})')
    assert out["config"]["storage"] == "cookie" and "redis" not in out["config"]
    assert any("invalid redis configuration" in entry[1] for entry in out["logs"])


def test_missing_variable_stops_initialization():
    out = run(NEW + 'MISSING_VAR="REDIS_HOST"\nemit({result=p:init(),config=CONFIG})')
    assert out["result"]["ret"] is False
    assert out["result"]["msg"] == "can't get REDIS_HOST variable : lookup failed"
    assert "config" not in out


def test_init_storage_failures_log_without_losing_configuration():
    out = run('VARIABLES.SESSIONS_SECRET="random" VARIABLES.SESSIONS_NAME="random"\n' + NEW + """
STORE_SET_ERROR="full" ngx.shared.sessions_revocation=nil
local result=p:init()
emit({result=result,config=CONFIG,logs=LOGS})
""")
    assert out["result"]["ret"] and out["config"]["storage"] == "cookie"
    assert "revocation" not in out["config"]
    assert sum("error from internalstore:set : full" in entry[1] for entry in out["logs"]) == 4
    assert any("revocation is disabled" in entry[1] for entry in out["logs"])


@pytest.mark.parametrize(
    ("setup", "storage", "changed", "message"),
    [
        ('ENV.USE_REDIS="no" STORE.storage_sessions_STORAGE="redis"', "cookie", True, "timer done"),
        ('ENV.USE_REDIS="no" STORE.storage_sessions_STORAGE="cookie"', "cookie", False, "timer done"),
        ('ENV.USE_REDIS="yes" STORE.storage_sessions_STORAGE="cookie"', "redis", True, "timer done"),
        ('ENV.USE_REDIS="yes" STORE.storage_sessions_STORAGE="redis"', "redis", False, "timer done"),
        ('ENV.USE_REDIS="yes" STORE.storage_sessions_STORAGE="redis" CONNECT_ERROR="offline"', "cookie", True, "redis connect error : offline"),
        ('ENV.USE_REDIS="yes" STORE.storage_sessions_STORAGE="cookie" CONNECT_ERROR="offline"', "cookie", False, "redis connect error : offline"),
        ('ENV.USE_REDIS="yes" STORE.storage_sessions_STORAGE="redis" PING_ERROR="timeout"', "cookie", True, "error while sending ping"),
        ('ENV.USE_REDIS="yes" STORE.storage_sessions_STORAGE="redis" PING_OK=false', "cookie", True, "ping failed"),
    ],
)
def test_backend_transitions(setup, storage, changed, message):
    out = run(
        NEW
        + "p:init()\n"
        + setup
        + "\nlocal result=p:timer()\np:set()\nemit({result=result,store=STORE,config=CONFIG,logs=LOGS,closed=CLOSED,flushed=FLUSHED})"
    )
    assert out["result"]["ret"] and message in out["result"]["msg"]
    assert out["store"]["storage_sessions_STORAGE"] == storage
    assert out["store"]["storage_sessions_CHANGE"] is changed
    assert out["config"]["storage"] == storage
    if 'ENV.USE_REDIS="yes"' in setup:
        assert out["flushed"]
        if "CONNECT_ERROR" not in setup:
            assert out["closed"]
        if storage == "cookie":
            assert any("falling back to cookie storage" in entry[1] for entry in out["logs"])
        elif changed:
            assert any("redis is available again" in entry[1] for entry in out["logs"])


@pytest.mark.parametrize("redis", ["yes", "no"])
def test_timer_write_failure_returns_error(redis):
    out = run(NEW + f'ENV.USE_REDIS="{redis}" STORE_SET_ERROR="full"\nlocal result=p:timer()\nemit({{result=result,logs=LOGS}})')
    assert out["result"]["ret"] is False
    assert ("failed to set storage_sessions_STORAGE" if redis == "yes" else "redis disabled -> cookie") in out["result"]["msg"]
    assert any("failed to set storage_sessions_STORAGE: full" in entry[1] for entry in out["logs"])


def test_timer_missing_previous_storage_logs_and_recovers():
    out = run(NEW + 'ENV.USE_REDIS="yes"\nlocal result=p:timer()\nemit({result=result,store=STORE,logs=LOGS})')
    assert out["result"]["ret"] and out["store"]["storage_sessions_STORAGE"] == "redis"
    assert out["store"]["storage_sessions_CHANGE"] is True
    assert any("assuming cookie" in entry[1] for entry in out["logs"])


@pytest.mark.xfail(strict=True, reason="Redis-disabled timer updates storage marker but leaves worker session config on redis")
def test_disabling_redis_updates_configuration_used_by_next_request():
    out = run(NEW + """
ENV.USE_REDIS="yes" p:init()
ENV.USE_REDIS="no" local result=p:timer()
p:set()
emit({result=result,store=STORE,config=CONFIG})
""")
    assert out["result"]["ret"] and out["store"]["storage_sessions_STORAGE"] == "cookie"
    assert out["config"]["storage"] == "cookie"
