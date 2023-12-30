use Test::Nginx::Socket 'no_plan';
use Cwd qw(cwd);

my $pwd = cwd();

our $HttpConfig = qq{
lua_package_path "$pwd/lib/?.lua;;";
lua_socket_log_errors Off;

init_by_lua_block {
    require("luacov.runner").init()
}
};

$ENV{TEST_NGINX_RESOLVER} = '8.8.8.8';
$ENV{TEST_NGINX_REDIS_PORT} ||= 6380;
$ENV{TEST_NGINX_REDIS_PORT_SL1} ||= 6381;
$ENV{TEST_NGINX_REDIS_PORT_SL2} ||= 6382;
$ENV{TEST_NGINX_SENTINEL_PORT1} ||= 6390;
$ENV{TEST_NGINX_SENTINEL_PORT2} ||= 6391;
$ENV{TEST_NGINX_SENTINEL_PORT3} ||= 6392;
$ENV{TEST_NGINX_SENTINEL_PORT_AUTH} ||= 6393;

no_long_string();
run_tests();

__DATA__

=== TEST 1: Get the master
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local rc = require("resty.redis.connector").new()
        local rs = require("resty.redis.sentinel")

        local sentinel, err = rc:connect{ url = "redis://127.0.0.1:$TEST_NGINX_SENTINEL_PORT1" }
        assert(sentinel and not err, "sentinel should connect without errors but got " .. tostring(err))

        local master, err = rs.get_master(sentinel, "mymaster")

        assert(master and not err, "get_master should return the master")

        assert(master.host == "127.0.0.1" and tonumber(master.port) == $TEST_NGINX_REDIS_PORT,
            "host should be 127.0.0.1 and port should be $TEST_NGINX_REDIS_PORT")

        master, err = rs.get_master(sentinel, "invalid-mymaster")

        assert(not master and err, "invalid master name should result in error")

        sentinel:close()
    }
}
--- request
GET /t
--- no_error_log
[error]


=== TEST 1b: Get the master directly
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local rc = require("resty.redis.connector").new()

        local master, err = rc:connect({
            url = "sentinel://mymaster:m/3",
            sentinels = {
                { host = "127.0.0.1", port = $TEST_NGINX_SENTINEL_PORT1 }
            }
        })

        assert(master and not err, "get_master should return the master")
        assert(master:set("foo", "bar"), "set should run without error")
        assert(master:get("foo") == "bar", "get(foo) should return bar")

        master:close()
    }
}
--- request
GET /t
--- no_error_log
[error]


=== TEST 2: Get slaves
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local rc = require("resty.redis.connector").new()
        local rs = require("resty.redis.sentinel")

        local sentinel, err = rc:connect{ url = "redis://127.0.0.1:$TEST_NGINX_SENTINEL_PORT1" }
        assert(sentinel and not err, "sentinel should connect without error")

        local slaves, err = rs.get_slaves(sentinel, "mymaster")

        assert(slaves and not err, "slaves should be returned without error")

        local slaveports = { ["$TEST_NGINX_REDIS_PORT_SL1"] = false, ["$TEST_NGINX_REDIS_PORT_SL2"] = false }

        for _,slave in ipairs(slaves) do
            slaveports[tostring(slave.port)] = true
        end

        assert(slaveports["$TEST_NGINX_REDIS_PORT_SL1"] == true and slaveports["$TEST_NGINX_REDIS_PORT_SL2"] == true,
            "slaves should both be found")

        slaves, err = rs.get_slaves(sentinel, "invalid-mymaster")

        assert(not slaves and err, "invalid master name should result in error")

        sentinel:close()
    }
}
--- request
    GET /t
--- no_error_log
[error]


=== TEST 3: Get only healthy slaves
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local rc = require("resty.redis.connector").new()

        local sentinel, err = rc:connect({ url = "redis://127.0.0.1:$TEST_NGINX_SENTINEL_PORT1" })
        assert(sentinel and not err, "sentinel should connect without error")

        local slaves, err = require("resty.redis.sentinel").get_slaves(
            sentinel,
            "mymaster"
        )

        assert(slaves and not err, "slaves should be returned without error")

        local slaveports = { ["$TEST_NGINX_REDIS_PORT_SL1"] = false, ["$TEST_NGINX_REDIS_PORT_SL2"] = false }

        for _,slave in ipairs(slaves) do
            slaveports[tostring(slave.port)] = true
        end

        assert(slaveports["$TEST_NGINX_REDIS_PORT_SL1"] == true and slaveports["$TEST_NGINX_REDIS_PORT_SL2"] == true,
            "slaves should both be found")

        -- connect to one and remove it
        local r = require("resty.redis.connector").new():connect({
            port = $TEST_NGINX_REDIS_PORT_SL1,
        })
        r:slaveof("127.0.0.1", 7000)

        ngx.sleep(9)

        local slaves, err = require("resty.redis.sentinel").get_slaves(
            sentinel,
            "mymaster"
        )

        assert(slaves and not err, "slaves should be returned without error")

        local slaveports = { ["$TEST_NGINX_REDIS_PORT_SL1"] = false, ["$TEST_NGINX_REDIS_PORT_SL2"] = false }

        for _,slave in ipairs(slaves) do
            slaveports[tostring(slave.port)] = true
        end

        assert(slaveports["$TEST_NGINX_REDIS_PORT_SL1"] == false and slaveports["$TEST_NGINX_REDIS_PORT_SL2"] == true,
            "only $TEST_NGINX_REDIS_PORT_SL2 should be found")

        r:slaveof("127.0.0.1", $TEST_NGINX_REDIS_PORT)

        sentinel:close()
    }
}
--- request
GET /t
--- timeout: 10
--- no_error_log
[error]


=== TEST 4: connector.connect_via_sentinel
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local rc = require("resty.redis.connector").new()

        local params = {
            sentinels = {
                { host = "127.0.0.1", port = $TEST_NGINX_SENTINEL_PORT1 },
                { host = "127.0.0.1", port = $TEST_NGINX_SENTINEL_PORT2 },
                { host = "127.0.0.1", port = $TEST_NGINX_SENTINEL_PORT3 },
            },
            master_name = "mymaster",
            role = "master",
        }

        local redis, err = rc:connect_via_sentinel(params)
        assert(redis and not err, "redis should connect without error")

        params.role = "slave"

        local redis, err = rc:connect_via_sentinel(params)
        assert(redis and not err, "redis should connect without error")
    }
}
--- request
GET /t
--- no_error_log
[error]


=== TEST 5: regression for slave sorting (iss12)
--- http_config eval: $::HttpConfig
--- config
location /t {
    lua_socket_log_errors Off;
    content_by_lua_block {
        local rc = require("resty.redis.connector").new()

        local params = {
            sentinels = {
                { host = "127.0.0.1", port = $TEST_NGINX_SENTINEL_PORT1 },
                { host = "127.0.0.1", port = $TEST_NGINX_SENTINEL_PORT2 },
                { host = "127.0.0.1", port = $TEST_NGINX_SENTINEL_PORT3 },
            },
            master_name = "mymaster",
            role = "slave",
        }

        -- hotwire get_slaves to expose sorting issue
        local sentinel = require("resty.redis.sentinel")
        sentinel.get_slaves = function()
            return {
                { host = "127.0.0.1", port = $TEST_NGINX_REDIS_PORT_SL1 },
                { host = "127.0.0.1", port = $TEST_NGINX_REDIS_PORT_SL2 },
                { host = "134.123.51.2", port = $TEST_NGINX_REDIS_PORT_SL1 },
            }
        end

        local redis, err = rc:connect_via_sentinel(params)
        assert(redis and not err, "redis should connect without error")
    }
}
--- request
GET /t
--- no_error_log
[error]

=== TEST 6: connect with acl
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local rc = require("resty.redis.connector").new()
        local redis, err = rc:connect({
            username = "redisuser",
            password = "redisuserpass",
            sentinels = {
                { host = "127.0.0.1", port = $TEST_NGINX_SENTINEL_PORT_AUTH }
            },
            master_name = "mymaster",
            sentinel_username = "sentineluser",
            sentinel_username = "sentineluserpass",
        })
        assert(redis and not err, "redis should connect without error")
        local username = assert(redis:acl("whoami"))
        assert(username == "redisuser", "should connect as 'redisuser' but got " .. tostring(username))
    }
}
--- request
GET /t
--- no_error_log
[error]
