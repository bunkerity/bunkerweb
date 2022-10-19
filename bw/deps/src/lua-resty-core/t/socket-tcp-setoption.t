# vim:set ft= ts=4 sw=4 et fdm=marker:

use lib '.';
use t::TestCore;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 - 1);

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

            ok, err = sock:setoption()
            if not ok then
                ngx.say("setoption failed: ", err)
            end

            ok, err = sock:setoption("sndbuf")
            if not ok then
                ngx.say("setoption failed: ", err)
            end

            sock:close()
        }
    }
--- request
GET /t
--- response_body
setoption failed: missing the "option" argument
setoption failed: missing the "value" argument
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

            local ok, err = sock:setoption("abc", 123)
            if not ok then
                ngx.say("setoption abc failed: ", err)
                return
            end

            sock:close()
        }
    }
--- request
GET /t
--- response_body
setoption abc failed: unsupported option abc
--- no_error_log
[error]



=== TEST 3: getoption before calling connect.
--- config
    set $port $TEST_NGINX_SERVER_PORT;

    location /t {
        content_by_lua_block {
            require "resty.core.socket"

            local sock = ngx.socket.tcp()
            local sndbuf, err = sock:setoption("sndbuf", 4000)
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



=== TEST 4: keepalive set by 1/0.
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
            local v1, err = sock:getoption("keepalive")
            if not v1 then
                ngx.say("get default keepalive failed: ", err)
                return
            end

            ok, err = sock:setoption("keepalive", 1)
            if not ok then
                ngx.say("enabling keepalive failed: ", err)
                return
            end
            local v2, err = sock:getoption("keepalive")
            if not v2 then
                ngx.say("get enabled keepalive failed: ", err)
                return
            end
            ngx.say("keepalive changes from ", v1, " to ", v2)

            ok, err = sock:setoption("keepalive", 0)
            if not ok then
                ngx.say("disable keepalive failed: ", err)
                return
            end
            local v3, err = sock:getoption("keepalive")
            if not v3 then
                ngx.say("get disabled keepalive failed: ", err)
                return
            end
            ngx.say("keepalive changes from ", v2, " to ", v3)

            sock:close()
        }
    }
--- request
GET /t
--- response_body
keepalive changes from 0 to 1
keepalive changes from 1 to 0
--- no_error_log
[error]



=== TEST 5: keepalive set by true/false.
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
            local v1, err = sock:getoption("keepalive")
            if not v1 then
                ngx.say("get default keepalive failed: ", err)
                return
            end

            ok, err = sock:setoption("keepalive", true)
            if not ok then
                ngx.say("enabling keepalive failed: ", err)
                return
            end
            local v2, err = sock:getoption("keepalive")
            if not v2 then
                ngx.say("get enabled keepalive failed: ", err)
                return
            end
            ngx.say("keepalive changes from ", v1, " to ", v2)

            ok, err = sock:setoption("keepalive", false)
            if not ok then
                ngx.say("disable keepalive failed: ", err)
                return
            end
            local v3, err = sock:getoption("keepalive")
            if not v3 then
                ngx.say("get disabled keepalive failed: ", err)
                return
            end
            ngx.say("keepalive changes from ", v2, " to ", v3)

            sock:close()
        }
    }
--- request
GET /t
--- response_body
keepalive changes from 0 to 1
keepalive changes from 1 to 0
--- no_error_log
[error]



=== TEST 6: keepalive set by ~0/0.
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
            local v1, err = sock:getoption("keepalive")
            if not v1 then
                ngx.say("get default keepalive failed: ", err)
                return
            end

            ok, err = sock:setoption("keepalive", 10)
            if not ok then
                ngx.say("enabling keepalive failed: ", err)
                return
            end
            local v2, err = sock:getoption("keepalive")
            if not v2 then
                ngx.say("get enabled keepalive failed: ", err)
                return
            end
            ngx.say("keepalive changes from ", v1, " to ", v2)

            ok, err = sock:setoption("keepalive", 0)
            if not ok then
                ngx.say("disable keepalive failed: ", err)
                return
            end
            local v3, err = sock:getoption("keepalive")
            if not v3 then
                ngx.say("get disabled keepalive failed: ", err)
                return
            end
            ngx.say("keepalive changes from ", v2, " to ", v3)

            sock:close()
        }
    }
--- request
GET /t
--- response_body
keepalive changes from 0 to 1
keepalive changes from 1 to 0
--- no_error_log
[error]



=== TEST 7: reuseaddr set by 1/0.
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
            local v1, err = sock:getoption("reuseaddr")
            if not v1 then
                ngx.say("get default reuseaddr failed: ", err)
                return
            end

            ok, err = sock:setoption("reuseaddr", 1)
            if not ok then
                ngx.say("enabling reuseaddr failed: ", err)
                return
            end
            local v2, err = sock:getoption("reuseaddr")
            if not v2 then
                ngx.say("get enabled reuseaddr failed: ", err)
                return
            end
            ngx.say("reuseaddr changes from ", v1, " to ", v2)

            ok, err = sock:setoption("reuseaddr", 0)
            if not ok then
                ngx.say("disable reuseaddr failed: ", err)
                return
            end
            local v3, err = sock:getoption("reuseaddr")
            if not v3 then
                ngx.say("get disabled reuseaddr failed: ", err)
                return
            end
            ngx.say("reuseaddr changes from ", v2, " to ", v3)

            sock:close()
        }
    }
--- request
GET /t
--- response_body
reuseaddr changes from 0 to 1
reuseaddr changes from 1 to 0
--- no_error_log
[error]



=== TEST 8: reuseaddr set by true/false.
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
            local v1, err = sock:getoption("reuseaddr")
            if not v1 then
                ngx.say("get default reuseaddr failed: ", err)
                return
            end

            ok, err = sock:setoption("reuseaddr", true)
            if not ok then
                ngx.say("enabling reuseaddr failed: ", err)
                return
            end
            local v2, err = sock:getoption("reuseaddr")
            if not v2 then
                ngx.say("get enabled reuseaddr failed: ", err)
                return
            end
            ngx.say("reuseaddr changes from ", v1, " to ", v2)

            ok, err = sock:setoption("reuseaddr", false)
            if not ok then
                ngx.say("disable reuseaddr failed: ", err)
                return
            end
            local v3, err = sock:getoption("reuseaddr")
            if not v3 then
                ngx.say("get disabled reuseaddr failed: ", err)
                return
            end
            ngx.say("reuseaddr changes from ", v2, " to ", v3)

            sock:close()
        }
    }
--- request
GET /t
--- response_body
reuseaddr changes from 0 to 1
reuseaddr changes from 1 to 0
--- no_error_log
[error]



=== TEST 9: reuseaddr set by ~0/0.
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
            local v1, err = sock:getoption("reuseaddr")
            if not v1 then
                ngx.say("get default reuseaddr failed: ", err)
                return
            end

            ok, err = sock:setoption("reuseaddr", 10)
            if not ok then
                ngx.say("enabling reuseaddr failed: ", err)
                return
            end
            local v2, err = sock:getoption("reuseaddr")
            if not v2 then
                ngx.say("get enabled reuseaddr failed: ", err)
                return
            end
            ngx.say("reuseaddr changes from ", v1, " to ", v2)

            ok, err = sock:setoption("reuseaddr", 0)
            if not ok then
                ngx.say("disable reuseaddr failed: ", err)
                return
            end
            local v3, err = sock:getoption("reuseaddr")
            if not v3 then
                ngx.say("get disabled reuseaddr failed: ", err)
                return
            end
            ngx.say("reuseaddr changes from ", v2, " to ", v3)

            sock:close()
        }
    }
--- request
GET /t
--- response_body
reuseaddr changes from 0 to 1
reuseaddr changes from 1 to 0
--- no_error_log
[error]



=== TEST 10: tcp-nodelay set by 1/0.
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
            local v1, err = sock:getoption("tcp-nodelay")
            if not v1 then
                ngx.say("get default tcp-nodelay failed: ", err)
                return
            end

            ok, err = sock:setoption("tcp-nodelay", 1)
            if not ok then
                ngx.say("enabling tcp-nodelay failed: ", err)
                return
            end
            local v2, err = sock:getoption("tcp-nodelay")
            if not v2 then
                ngx.say("get enabled tcp-nodelay failed: ", err)
                return
            end
            ngx.say("tcp-nodelay changes from ", v1, " to ", v2)

            ok, err = sock:setoption("tcp-nodelay", 0)
            if not ok then
                ngx.say("disable tcp-nodelay failed: ", err)
                return
            end
            local v3, err = sock:getoption("tcp-nodelay")
            if not v3 then
                ngx.say("get disabled tcp-nodelay failed: ", err)
                return
            end
            ngx.say("tcp-nodelay changes from ", v2, " to ", v3)

            sock:close()
        }
    }
--- request
GET /t
--- response_body
tcp-nodelay changes from 0 to 1
tcp-nodelay changes from 1 to 0
--- no_error_log
[error]



=== TEST 11: tcp-nodelay set by true/false.
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
            local v1, err = sock:getoption("tcp-nodelay")
            if not v1 then
                ngx.say("get default tcp-nodelay failed: ", err)
                return
            end

            ok, err = sock:setoption("tcp-nodelay", true)
            if not ok then
                ngx.say("enabling tcp-nodelay failed: ", err)
                return
            end
            local v2, err = sock:getoption("tcp-nodelay")
            if not v2 then
                ngx.say("get enabled tcp-nodelay failed: ", err)
                return
            end
            ngx.say("tcp-nodelay changes from ", v1, " to ", v2)

            ok, err = sock:setoption("tcp-nodelay", false)
            if not ok then
                ngx.say("disable tcp-nodelay failed: ", err)
                return
            end
            local v3, err = sock:getoption("tcp-nodelay")
            if not v3 then
                ngx.say("get disabled tcp-nodelay failed: ", err)
                return
            end
            ngx.say("tcp-nodelay changes from ", v2, " to ", v3)

            sock:close()
        }
    }
--- request
GET /t
--- response_body
tcp-nodelay changes from 0 to 1
tcp-nodelay changes from 1 to 0
--- no_error_log
[error]



=== TEST 12: tcp-nodelay set by ~0/0.
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
            local v1, err = sock:getoption("tcp-nodelay")
            if not v1 then
                ngx.say("get default tcp-nodelay failed: ", err)
                return
            end

            ok, err = sock:setoption("tcp-nodelay", 10)
            if not ok then
                ngx.say("enabling tcp-nodelay failed: ", err)
                return
            end
            local v2, err = sock:getoption("tcp-nodelay")
            if not v2 then
                ngx.say("get enabled tcp-nodelay failed: ", err)
                return
            end
            ngx.say("tcp-nodelay changes from ", v1, " to ", v2)

            ok, err = sock:setoption("tcp-nodelay", 0)
            if not ok then
                ngx.say("disable tcp-nodelay failed: ", err)
                return
            end
            local v3, err = sock:getoption("tcp-nodelay")
            if not v3 then
                ngx.say("get disabled tcp-nodelay failed: ", err)
                return
            end
            ngx.say("tcp-nodelay changes from ", v2, " to ", v3)

            sock:close()
        }
    }
--- request
GET /t
--- response_body
tcp-nodelay changes from 0 to 1
tcp-nodelay changes from 1 to 0
--- no_error_log
[error]



=== TEST 13: sndbuf.
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
            local v1, err = sock:getoption("sndbuf")
            if not v1 then
                ngx.say("get default sndbuf failed: ", err)
                return
            end

            ok, err = sock:setoption("sndbuf", 4096)
            if not ok then
                ngx.say("enabling sndbuf failed: ", err)
                return
            end
            local v2, err = sock:getoption("sndbuf")
            if not v2 then
                ngx.say("get enabled sndbuf failed: ", err)
                return
            end
            ngx.say("sndbuf changes from ", v1, " to ", v2)

            sock:close()
        }
    }
--- request
GET /t
--- response_body_like eval
qr/\Asndbuf changes from \d+ to \d+\n\z/
--- no_error_log
[error]



=== TEST 14: rcvbuf.
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
            local v1, err = sock:getoption("rcvbuf")
            if not v1 then
                ngx.say("get default rcvbuf failed: ", err)
                return
            end

            ok, err = sock:setoption("rcvbuf", 4096)
            if not ok then
                ngx.say("enabling rcvbuf failed: ", err)
                return
            end
            local v2, err = sock:getoption("rcvbuf")
            if not v2 then
                ngx.say("get enabled rcvbuf failed: ", err)
                return
            end
            ngx.say("rcvbuf changes from ", v1, " to ", v2)

            sock:close()
        }
    }
--- request
GET /t
--- response_body_like eval
qr/\Arcvbuf changes from \d+ to \d+\n\z/
--- no_error_log
[error]



=== TEST 15: strerr.
--- config
    set $port $TEST_NGINX_SERVER_PORT;

    location /t {
        content_by_lua_block {
            require "resty.core.socket"
            local ffi = require "ffi"
            local base = require "resty.core.base"

            ffi.cdef[[
            typedef struct ngx_http_lua_socket_tcp_upstream_s
                ngx_http_lua_socket_tcp_upstream_t;

            int ngx_http_lua_ffi_socket_tcp_hack_fd(
                    ngx_http_lua_socket_tcp_upstream_t *u, int fd,
                    unsigned char *errstr, size_t *errlen);
            ]]

            local port = ngx.var.port
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.1", port)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            local errstr = base.get_string_buf(4096)
            local errlen = base.get_size_ptr()
            errlen[0] = 4096
            local SOCKET_CTX_INDEX = 1
            local tcpsock = sock[SOCKET_CTX_INDEX]

            -- hack the fd of the socket
            local bad_fd = 12345
            local realfd = ffi.C.ngx_http_lua_ffi_socket_tcp_hack_fd(tcpsock,
                                    bad_fd, errstr, errlen)
            if realfd == -1 then
                ngx.say("hack fd failed: ", ffi.string(err, errlen[0]))
                return
            end

            ok, err = sock:setoption("rcvbuf", 4096)
            if not ok then
                ngx.say("enabling rcvbuf failed: ", err)

                -- restore the fd of the socket
                ffi.C.ngx_http_lua_ffi_socket_tcp_hack_fd(tcpsock,
                                realfd, errstr, errlen)
                return
            end
        }
    }
--- request
GET /t
--- response_body_like eval
qr/\Aenabling rcvbuf failed: [\/\s\w]+\n\z/
--- no_error_log
[error]
