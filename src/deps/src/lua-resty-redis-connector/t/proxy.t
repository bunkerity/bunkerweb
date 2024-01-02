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

no_long_string();
run_tests();

__DATA__

=== TEST 1: Proxy mode disables commands
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local rc = require("resty.redis.connector").new({
            port = $TEST_NGINX_REDIS_PORT,
            connection_is_proxied = true
        })

        local redis, err = assert(rc:connect(params),
            "connect should return positively")

        assert(redis:set("dog", "an animal"),
            "redis:set should return positively")

        local ok, err = redis:multi()
        assert(ok == nil, "redis:multi should return nil")
        assert(err == "Command multi is disabled")

        redis:close()
    }
}
--- request
GET /t
--- no_error_log
[error]


=== TEST 2: Proxy mode disables custom commands
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local rc = require("resty.redis.connector").new({
            port = $TEST_NGINX_REDIS_PORT,
            connection_is_proxied = true,
            disabled_commands = { "foobar", "hget"}
        })

        local redis, err = assert(rc:connect(params),
            "connect should return positively")

        assert(redis:set("dog", "an animal"),
            "redis:set should return positively")

        assert(redis:multi(),
            "redis:multi should return positively")

        local ok, err = redis:hget()
        assert(ok == nil, "redis:hget should return nil")
        assert(err == "Command hget is disabled")

        local ok, err = redis:foobar()
        assert(ok == nil, "redis:foobar should return nil")
        assert(err == "Command foobar is disabled")

        redis:close()
    }
}
--- request
GET /t
--- no_error_log
[error]

=== TEST 3: Proxy mode does not switch DB
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local redis = require("resty.redis.connector").new({
            port = $TEST_NGINX_REDIS_PORT,
            db = 2
        }):connect()

        local proxy = require("resty.redis.connector").new({
            port = $TEST_NGINX_REDIS_PORT,
            connection_is_proxied = true,
            db = 2
        }):connect()

        assert(redis:set("proxy", "test"),
            "redis:set should return positively")

        assert(proxy:get("proxy") == ngx.null,
             "proxy key should not exist in proxy")

        redis:seelct(2)
        assert(redis:get("proxy") == "test",
            "proxy key should be 'test' in db 1")

        redis:close()
    }
}
--- request
GET /t
--- no_error_log
[error]


=== TEST 4: Commands are disabled without proxy mode
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local rc = require("resty.redis.connector").new({
            port = $TEST_NGINX_REDIS_PORT,
            disabled_commands = { "foobar", "hget"}
        })

        local redis, err = assert(rc:connect(params),
            "connect should return positively")

        assert(redis:set("dog", "an animal"),
            "redis:set should return positively")

        assert(redis:multi(),
            "redis:multi should return positively")

        local ok, err = redis:hget()
        assert(ok == nil, "redis:hget should return nil")
        assert(err == "Command hget is disabled")

        local ok, err = redis:foobar()
        assert(ok == nil, "redis:foobar should return nil")
        assert(err == "Command foobar is disabled")

        redis:close()
    }
}
--- request
GET /t
--- no_error_log
[error]
