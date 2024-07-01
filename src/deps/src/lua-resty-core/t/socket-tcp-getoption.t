# vim:set ft= ts=4 sw=4 et fdm=marker:

use lib '.';
use t::TestCore;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 2 + 7);

#worker_connections(1024);
#no_diff();
no_long_string();

run_tests();

__DATA__

=== TEST 1: no parameters.
--- config
    set $port $TEST_NGINX_SERVER_PORT;

    location /t {
        content_by_lua_block {
            require "resty.core.socket"

            local port = ngx.var.port
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.1", port)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ok, err = sock:getoption()
            if not ok then
                ngx.say("getoption failed: ", err)
                return
            end

            sock:close()
        }
    }
--- request
GET /t
--- response_body
getoption failed: missing the "option" argument
--- no_error_log
[error]



=== TEST 2: unsuppotrted option name.
--- config
    set $port $TEST_NGINX_SERVER_PORT;

    location /t {
        content_by_lua_block {
            require "resty.core.socket"

            local port = ngx.var.port
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.1", port)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local sndbuf, err = sock:getoption("abc")
            if not sndbuf then
                ngx.say("getoption abc failed: ", err)
                return
            end

            sock:close()
        }
    }
--- request
GET /t
--- response_body
getoption abc failed: unsupported option abc
--- no_error_log
[error]



=== TEST 3: getoption before calling connect.
--- config
    set $port $TEST_NGINX_SERVER_PORT;

    location /t {
        content_by_lua_block {
            require "resty.core.socket"

            local sock = ngx.socket.tcp()
            local sndbuf, err = sock:getoption("sndbuf")
            if not sndbuf then
                ngx.say("getoption sndbuf failed: ", err)
                return
            end

            sock:close()
        }
    }
--- request
GET /t
--- error_code: 500
--- error_log
socket is never created nor connected



=== TEST 4: get keepalive.
--- config
    set $port $TEST_NGINX_SERVER_PORT;

    location /t {
        content_by_lua_block {
            require "resty.core.socket"

            local port = ngx.var.port
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.1", port)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local val, err = sock:getoption("keepalive")
            if not val then
                ngx.say("getoption keepalive failed: ", err)
                return
            end

            ngx.say("keepalive: ", val)

            sock:close()
        }
    }
--- request
GET /t
--- response_body_like eval
qr/keepalive: \d+/
--- no_error_log
[error]



=== TEST 5: get reuseaddr.
--- config
    set $port $TEST_NGINX_SERVER_PORT;

    location /t {
        content_by_lua_block {
            require "resty.core.socket"

            local port = ngx.var.port
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.1", port)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local val, err = sock:getoption("reuseaddr")
            if not val then
                ngx.say("getoption reuseaddr failed: ", err)
                return
            end

            ngx.say("reuseaddr: ", val)

            sock:close()
        }
    }
--- request
GET /t
--- response_body_like eval
qr/reuseaddr: \d+/
--- no_error_log
[error]



=== TEST 6: get tcp-nodelay.
--- config
    set $port $TEST_NGINX_SERVER_PORT;

    location /t {
        content_by_lua_block {
            require "resty.core.socket"

            local port = ngx.var.port
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.1", port)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local val, err = sock:getoption("tcp-nodelay")
            if not val then
                ngx.say("getoption tcp-nodelay failed: ", err)
                return
            end

            ngx.say("tcp-nodelay: ", val)

            sock:close()
        }
    }
--- request
GET /t
--- response_body_like eval
qr/tcp-nodelay: \d+/
--- no_error_log
[error]



=== TEST 7: get sndbuf.
--- config
    set $port $TEST_NGINX_SERVER_PORT;

    location /t {
        content_by_lua_block {
            require "resty.core.socket"

            local port = ngx.var.port
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.1", port)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local val, err = sock:getoption("sndbuf")
            if not val then
                ngx.say("getoption sndbuf failed: ", err)
                return
            end

            ngx.say("sndbuf: ", val)

            sock:close()
        }
    }
--- request
GET /t
--- response_body_like eval
qr/sndbuf: \d+/
--- no_error_log
[error]



=== TEST 8: get rcvbuf.
--- config
    set $port $TEST_NGINX_SERVER_PORT;

    location /t {
        content_by_lua_block {
            require "resty.core.socket"

            local port = ngx.var.port
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.1", port)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local val, err = sock:getoption("rcvbuf")
            if not val then
                ngx.say("getoption rcvbuf failed: ", err)
                return
            end

            ngx.say("rcvbuf: ", val)

            sock:close()
        }
    }
--- request
GET /t
--- response_body_like eval
qr/rcvbuf: \d+/
--- no_error_log
[error]
