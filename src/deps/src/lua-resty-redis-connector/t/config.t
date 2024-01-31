use Test::Nginx::Socket::Lua;
use Cwd qw(cwd);

repeat_each(2);

plan tests => repeat_each() * blocks() * 2;

my $pwd = cwd();

our $HttpConfig = qq{
lua_package_path "$pwd/lib/?.lua;;";
lua_socket_log_errors Off;

init_by_lua_block {
    require("luacov.runner").init()
}
};

$ENV{TEST_NGINX_REDIS_PORT} ||= 6380;

no_long_string();
run_tests();

__DATA__

=== TEST 1: Default config
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local rc = assert(require("resty.redis.connector").new())
    }
}
--- request
GET /t
--- no_error_log
[error]


=== TEST 2: Defaults via new
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local config = {
            connect_timeout = 500,
            port = $TEST_NGINX_REDIS_PORT,
            db = 6,
        }
        local rc = require("resty.redis.connector").new(config)

        assert(config ~= rc.config, "config should not equal rc.config")
        assert(rc.config.connect_timeout == 500, "connect_timeout should be 500")
        assert(rc.config.db == 6, "db should be 6")
        assert(rc.config.role == "master", "role should be master")
    }
}
--- request
GET /t
--- no_error_log
[error]


=== TEST 3: Config via connect still overrides
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local rc = require("resty.redis.connector").new({
            connect_timeout = 500,
            port = $TEST_NGINX_REDIS_PORT,
            db = 6,
            keepalive_poolsize = 10,
        })

        assert(config ~= rc.config, "config should not equal rc.config")
        assert(rc.config.connect_timeout == 500, "connect_timeout should be 500")
        assert(rc.config.db == 6, "db should be 6")
        assert(rc.config.role == "master", "role should be master")
        assert(rc.config.keepalive_poolsize == 10,
            "keepalive_poolsize should be 10")

        local redis, err = rc:connect({
            port = $TEST_NGINX_REDIS_PORT,
            disabled_commands = { "set" }
        })

        if not redis or err then
            ngx.log(ngx.ERR, "connect failed: ", err)
            return
        end

        local ok, err = redis:set("foo", "bar")
            assert( ok == nil and (string.find(err, "disabled") ~= nil) , "Disabled commands not passed through" )
    }
}
--- request
GET /t
--- no_error_log
[error]


=== TEST 4: Unknown config errors, all config does not error
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        local rc, err = require("resty.redis.connector").new({
            connect_timeout = 500,
            port = $TEST_NGINX_REDIS_PORT,
            db = 6,
            foo = "bar",
        })

        assert(rc == nil, "rc should be nil")
        assert(string.find(err, "field foo does not exist"),
            "err should contain error")

        -- Provide all options, without errors

        assert(require("resty.redis.connector").new({
            connect_timeout = 100,
            send_timeout = 500,
            read_timeout = 1000,
            connection_options = { pool = "<host>::<port>" },
            keepalive_timeout = 60000,
            keepalive_poolsize = 30,

            host = "127.0.0.1",
            port = $TEST_NGINX_REDIS_PORT,
            path = "",
            username = "",
            password = "",
            db = 0,

            url = "",

            master_name = "mymaster",
            role = "master",
            sentinels = {},
        }), "new should return positively")

        -- Provide all options via connect, without errors

        local rc = require("resty.redis.connector").new()

        assert(rc:connect({
            connect_timeout = 100,
            send_timeout = 500,
            read_timeout = 1000,
            connection_options = { pool = "<host>::<port>" },
            keepalive_timeout = 60000,
            keepalive_poolsize = 30,

            host = "127.0.0.1",
            port = $TEST_NGINX_REDIS_PORT,
            path = "",
            username = "",
            password = "",
            db = 0,

            url = "",

            master_name = "mymaster",
            role = "master",
            sentinels = {},
        }), "rc:connect should return positively")
    }
}
--- request
GET /t
--- no_error_log
[error]


=== TEST 5: timeout defaults
--- http_config eval: $::HttpConfig
--- config
location /t {
    content_by_lua_block {
        -- global defaults
        local rc = require("resty.redis.connector").new({
            port = $TEST_NGINX_REDIS_PORT,
            db = 6,
            keepalive_poolsize = 10,
        })

        assert(rc.config.connect_timeout == 100, "connect_timeout should be 100")
        assert(rc.config.send_timeout == 1000, "send_timeout should be 1000")
        assert(rc.config.read_timeout == 1000, "read_timeout should be 1000")

        local redis = assert(rc:connect(), "rc:connect should return positively")
        assert(redis:set("foo", "bar"))
        rc:set_keepalive(redis)

        -- send_timeout defaults to read_timeout
        rc = require("resty.redis.connector").new({
            read_timeout = 500,
            port = $TEST_NGINX_REDIS_PORT,
            db = 6,
            keepalive_poolsize = 10,
        })

        assert(rc.config.connect_timeout == 100, "connect_timeout should be 100")
        assert(rc.config.send_timeout == 500, "send_timeout should be 500")
        assert(rc.config.read_timeout == 500, "read_timeout should be 500")

        local redis = assert(rc:connect(), "rc:connect should return positively")
        assert(redis:set("foo", "bar"))
        rc:set_keepalive(redis)

        -- send_timeout can be set separately from read_timeout
        rc = require("resty.redis.connector").new({
            send_timeout = 500,
            read_timeout = 200,
            port = $TEST_NGINX_REDIS_PORT,
            db = 6,
            keepalive_poolsize = 10,
        })

        assert(rc.config.connect_timeout == 100, "connect_timeout should be 100")
        assert(rc.config.send_timeout == 500, "send_timeout should be 500")
        assert(rc.config.read_timeout == 200, "read_timeout should be 200")
    }
}
--- request
GET /t
--- no_error_log
[error]
