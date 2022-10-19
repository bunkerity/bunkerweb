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
use t::TestCore::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 5);

$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = "$t::TestCore::Stream::lua_package_path";

#worker_connections(1024);
#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: set_timeouts
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    server {
        listen $TEST_NGINX_RAND_PORT_1;
        return "fake origin\n";
    }

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(1.234, 5.678, 7.689))
            assert(b.set_current_peer("127.0.0.1", tonumber($TEST_NGINX_RAND_PORT_1)))
        }
    }
--- stream_server_config
    proxy_pass backend;
--- response_body
fake origin
--- grep_error_log eval: qr/event timer add: \d+: (?:1234|5678|7689):/
--- grep_error_log_out eval
qr/\Aevent timer add: \d+: 1234:
event timer add: \d+: 7689:
\z/
--- no_error_log
[warn]



=== TEST 2: set_timeouts (nil connect timeout)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    proxy_connect_timeout 1234ms;

    server {
        listen $TEST_NGINX_RAND_PORT_1;
        return "fake origin\n";
    }

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(nil, 5.678, 7.689))
            assert(b.set_current_peer("127.0.0.1", tonumber($TEST_NGINX_RAND_PORT_1)))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- stream_response
fake origin
--- grep_error_log eval: qr/event timer add: \d+: (?:1234|5678|7689):/
--- grep_error_log_out eval
qr/\Aevent timer add: \d+: 1234:
event timer add: \d+: 7689:
\z/
--- no_error_log
[warn]



=== TEST 3: set_timeouts (nil send timeout)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    proxy_timeout 5678ms;

    server {
        listen $TEST_NGINX_RAND_PORT_1;
        return "fake origin\n";
    }

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(1.234, nil, 7.689))
            assert(b.set_current_peer("127.0.0.1", tonumber($TEST_NGINX_RAND_PORT_1)))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- stream_response
fake origin
--- grep_error_log eval: qr/event timer add: \d+: (?:1234|5678|7689):/
--- grep_error_log_out eval
qr/\Aevent timer add: \d+: 1234:
event timer add: \d+: 7689:
\z/
--- no_error_log
[warn]



=== TEST 4: set_timeouts (nil read timeout)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    proxy_timeout 7689ms;

    server {
        listen $TEST_NGINX_RAND_PORT_1;
        return "fake origin\n";
    }

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(1.234, 5.678, nil))
            assert(b.set_current_peer("127.0.0.1", tonumber($TEST_NGINX_RAND_PORT_1)))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- stream_response
fake origin
--- grep_error_log eval: qr/event timer add: \d+: (?:1234|5678|7689):/
--- grep_error_log_out eval
qr/\Aevent timer add: \d+: 1234:
event timer add: \d+: 5678:
\z/
--- no_error_log
[warn]



=== TEST 5: set connect timeout to 0
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(0, 1.234, 5.678))
            assert(b.set_current_peer("127.0.0.1", tonumber($TEST_NGINX_RAND_PORT_1)))
        }
    }
--- stream_server_config
    proxy_pass backend;
--- error_log eval
qr/\[error\] .*? balancer_by_lua:3: bad connect timeout/
--- no_error_log
[warn]



=== TEST 6: set connect timeout to -1
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(-1, 1.234, 5.678))
            assert(b.set_current_peer("127.0.0.1", tonumber($TEST_NGINX_RAND_PORT_1)))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- error_log eval
qr/\[error\] .*? balancer_by_lua:3: bad connect timeout/
--- no_error_log
[warn]



=== TEST 7: set send timeout to 0
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(1.234, 0, 5.678))
            assert(b.set_current_peer("127.0.0.1", tonumber($TEST_NGINX_RAND_PORT_1)))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- error_log eval
qr/\[error\] .*? balancer_by_lua:3: bad send timeout/
--- no_error_log
[warn]



=== TEST 8: set send timeout to -1
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(1.234, -1, 5.678))
            assert(b.set_current_peer("127.0.0.1", tonumber($TEST_NGINX_RAND_PORT_1)))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- error_log eval
qr/\[error\] .*? balancer_by_lua:3: bad send timeout/
--- no_error_log
[warn]



=== TEST 9: set read timeout to 0
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(1.234, 4.567, 0))
            assert(b.set_current_peer("127.0.0.1", tonumber($TEST_NGINX_RAND_PORT_1)))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- error_log eval
qr/\[error\] .*? balancer_by_lua:3: bad read timeout/
--- no_error_log
[warn]



=== TEST 10 set read timeout to -1
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_timeouts(1.234, 4.567, -1))
            assert(b.set_current_peer("127.0.0.1", tonumber($TEST_NGINX_RAND_PORT_1)))
        }
    }
--- stream_server_config
        proxy_pass backend;
--- error_log eval
qr/\[error\] .*? balancer_by_lua:3: bad read timeout/
--- no_error_log
[warn]



=== TEST 11: set_timeouts called in a wrong context
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

--- stream_server_config

       content_by_lua_block {
            local balancer = require "ngx.balancer"
            local ok, err = balancer.set_timeouts(1, 1, 1)
            if not ok then
                ngx.say("failed to call: ", err)
                return
            end
            ngx.say("unexpected success!")
        }

--- stream_response
failed to call: API disabled in the current context
--- no_error_log
[error]
[alert]



=== TEST 12: set_timeouts called with a non-numerical parameter
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";

    upstream backend {
        server 0.0.0.1:1234;
        balancer_by_lua_block {
            local balancer = require "ngx.balancer"
            local ok, err = balancer.set_timeouts("1.234", 1, 1)
            if not ok then
                ngx.log(ngx.ERR, "failed to call: ", err)
            end
        }
    }

--- stream_server_config
        proxy_pass backend;
--- error_log eval
qr/\[error\] .*? bad connect timeout/
--- no_error_log
[alert]
