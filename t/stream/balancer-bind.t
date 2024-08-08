# vim:set ft= ts=4 sw=4 et fdm=marker:
use lib '.';
use t::TestCore::Stream;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 4);

$ENV{TEST_NGINX_LUA_PACKAGE_PATH} = "$t::TestCore::Stream::lua_package_path";

$ENV{TEST_NGINX_UPSTREAM_PORT} ||= get_unused_port 12345;

no_long_string();
run_tests();

__DATA__

=== TEST 1: balancer
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    upstream backend {
        server 0.0.0.1:1234 down;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_current_peer("127.0.0.1", $TEST_NGINX_UPSTREAM_PORT))
        }
    }
    server {
        listen 127.0.0.1:$TEST_NGINX_UPSTREAM_PORT;
        content_by_lua_block {
            ngx.print(ngx.var.remote_addr, ":", ngx.var.remote_port)
        }
    }
--- stream_server_config
    proxy_pass backend;
--- request
    GET /t
--- response_body eval
[
qr/127.0.0.1/,
]
--- error_code: 200
--- no_error_log
[error]
[warn]



=== TEST 2: balancer with bind_to_local_addr (addr)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    upstream backend {
        server 0.0.0.1:1234 down;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_current_peer("127.0.0.1", $TEST_NGINX_UPSTREAM_PORT))
            assert(b.bind_to_local_addr("127.0.0.4"))
        }
    }
    server {
        listen 127.0.0.1:$TEST_NGINX_UPSTREAM_PORT;
        content_by_lua_block {
            ngx.print(ngx.var.remote_addr, ":", ngx.var.remote_port)
        }
    }
--- stream_server_config
    proxy_pass backend;
--- request
    GET /t
--- response_body eval
[
qr/127.0.0.4/,
]
--- error_code: 200
--- no_error_log
[error]
[warn]



=== TEST 3: balancer with bind_to_local_addr (addr and port)
--- stream_config
    lua_package_path "$TEST_NGINX_LUA_PACKAGE_PATH";
    upstream backend {
        server 0.0.0.1:1234 down;
        balancer_by_lua_block {
            local b = require "ngx.balancer"
            assert(b.set_current_peer("127.0.0.1", $TEST_NGINX_UPSTREAM_PORT))
            assert(b.bind_to_local_addr("127.0.0.8:23456"))
        }
    }
    server {
        listen 127.0.0.1:$TEST_NGINX_UPSTREAM_PORT;
        content_by_lua_block {
            ngx.print(ngx.var.remote_addr, ":", ngx.var.remote_port)
        }
    }
--- stream_server_config
    proxy_pass backend;
--- request
    GET /t
--- response_body eval
[
qr/127.0.0.8/,
]
--- error_code: 200
--- no_error_log
[error]
[warn]
