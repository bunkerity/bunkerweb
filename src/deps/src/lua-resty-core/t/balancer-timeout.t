# vim:set ft= ts=4 sw=4 et fdm=marker:

BEGIN {
    if (!defined $ENV{LD_PRELOAD}) {
        $ENV{LD_PRELOAD} = '';
    }

    if ($ENV{LD_PRELOAD} !~ /\bmockeagain\.so\b/) {
        $ENV{LD_PRELOAD} = "mockeagain.so $ENV{LD_PRELOAD}";
    }

    if (defined $ENV{MOCKEAGAIN} && $ENV{MOCKEAGAIN} eq 'r') {
        $ENV{MOCKEAGAIN} = 'rw';

    } else {
        $ENV{MOCKEAGAIN} = 'w';
    }

    $ENV{TEST_NGINX_EVENT_TYPE} = 'poll';
    $ENV{TEST_NGINX_POSTPONE_OUTPUT} = 1;
}

use lib '.';
use t::TestCore;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4);

$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = $t::TestCore::lua_package_path;

#worker_connections(1024);
#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: set_timeouts
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(1.234, 5.678, 7.689))
            assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend/back;
    }
    location = /back {
        echo "fake origin";
    }
--- request
    GET /t
--- response_body
fake origin
--- grep_error_log eval: qr/event timer add: \d+: (?:1234|5678|7689):/
--- grep_error_log_out eval
qr/\Aevent timer add: \d+: 1234:
event timer add: \d+: 5678:
event timer add: \d+: 7689:
\z/
--- no_error_log
[warn]



=== TEST 2: set_timeouts (nil connect timeout)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    proxy_connect_timeout 1234ms;

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(nil, 5.678, 7.689))
            assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend/back;
    }
    location = /back {
        echo "fake origin";
    }
--- request
    GET /t
--- response_body
fake origin
--- grep_error_log eval: qr/event timer add: \d+: (?:1234|5678|7689):/
--- grep_error_log_out eval
qr/\Aevent timer add: \d+: 1234:
event timer add: \d+: 5678:
event timer add: \d+: 7689:
\z/
--- no_error_log
[warn]



=== TEST 3: set_timeouts (nil send timeout)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    proxy_send_timeout 5678ms;

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(1.234, nil, 7.689))
            assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend/back;
    }
    location = /back {
        echo "fake origin";
    }
--- request
    GET /t
--- response_body
fake origin
--- grep_error_log eval: qr/event timer add: \d+: (?:1234|5678|7689):/
--- grep_error_log_out eval
qr/\Aevent timer add: \d+: 1234:
event timer add: \d+: 5678:
event timer add: \d+: 7689:
\z/
--- no_error_log
[warn]



=== TEST 4: set_timeouts (nil read timeout)
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    proxy_read_timeout 7689ms;

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(1.234, 5.678, nil))
            assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend/back;
    }
    location = /back {
        echo "fake origin";
    }
--- request
    GET /t
--- response_body
fake origin
--- grep_error_log eval: qr/event timer add: \d+: (?:1234|5678|7689):/
--- grep_error_log_out eval
qr/\Aevent timer add: \d+: 1234:
event timer add: \d+: 5678:
event timer add: \d+: 7689:
\z/
--- no_error_log
[warn]



=== TEST 5: set connect timeout to 0
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
            local b = require "ngx.balancer"
            assert(b.set_timeouts(0, 1.234, 5.678))
            assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend/back;
    }
    location = /back {
        echo "fake origin";
    }
--- request
    GET /t
--- response_body_like: 500 Internal Server Error
--- error_code: 500
--- error_log eval
qr/\[error\] .*? balancer_by_lua\(nginx.conf:\d+\):4: bad connect timeout/
--- no_error_log
[warn]



=== TEST 6: set connect timeout to -1
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
            local b = require "ngx.balancer"
            assert(b.set_timeouts(-1, 1.234, 5.678))
            assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend/back;
    }
    location = /back {
        echo "fake origin";
    }
--- request
    GET /t
--- response_body_like: 500 Internal Server Error
--- error_code: 500
--- error_log eval
qr/\[error\] .*? balancer_by_lua\(nginx.conf:\d+\):4: bad connect timeout/
--- no_error_log
[warn]



=== TEST 7: set send timeout to 0
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
            local b = require "ngx.balancer"
            assert(b.set_timeouts(1.234, 0, 5.678))
            assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend/back;
    }
    location = /back {
        echo "fake origin";
    }
--- request
    GET /t
--- response_body_like: 500 Internal Server Error
--- error_code: 500
--- error_log eval
qr/\[error\] .*? balancer_by_lua\(nginx.conf:\d+\):4: bad send timeout/
--- no_error_log
[warn]



=== TEST 8: set send timeout to -1
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
            local b = require "ngx.balancer"
            assert(b.set_timeouts(1.234, -1, 5.678))
            assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend/back;
    }
    location = /back {
        echo "fake origin";
    }
--- request
    GET /t
--- response_body_like: 500 Internal Server Error
--- error_code: 500
--- error_log eval
qr/\[error\] .*? balancer_by_lua\(nginx.conf:\d+\):4: bad send timeout/
--- no_error_log
[warn]



=== TEST 9: set read timeout to -1
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            print("hello from balancer by lua!")
            local b = require "ngx.balancer"
            assert(b.set_timeouts(1.234, 5.678, -1))
            assert(b.set_current_peer("127.0.0.1", tonumber(ngx.var.server_port)))
        }
    }
--- config
    location = /t {
        proxy_pass http://backend/back;
    }
    location = /back {
        echo "fake origin";
    }
--- request
    GET /t
--- response_body_like: 500 Internal Server Error
--- error_code: 500
--- error_log eval
qr/\[error\] .*? balancer_by_lua\(nginx.conf:\d+\):4: bad read timeout/
--- no_error_log
[warn]



=== TEST 10: set_timeouts called in a wrong context
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

--- config

    location = /t {
       content_by_lua_block {
            local balancer = require "ngx.balancer"
            local ok, err = balancer.set_timeouts(1, 1, 1)
            if not ok then
                ngx.say("failed to call: ", err)
                return
            end
            ngx.say("unexpected success!")
        }
    }

--- request
GET /t
--- response_body
failed to call: no upstream found
--- no_error_log
[error]
[alert]



=== TEST 11: set_timeouts called with a non-numerical parameter
--- http_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1;
        balancer_by_lua_block {
            local balancer = require "ngx.balancer"
            local ok, err = balancer.set_timeouts("1.234", 1, 1)
            if not ok then
                ngx.log(ngx.ERR, "failed to call: ", err)
            end
        }
    }

--- config
    location = /t {
        proxy_pass http://backend;
    }
--- request
GET /t
--- response_body_like: 500 Internal Server Error
--- error_code: 500
--- error_log eval
qr/\[error\] .*? bad connect timeout/
--- no_error_log
[alert]
