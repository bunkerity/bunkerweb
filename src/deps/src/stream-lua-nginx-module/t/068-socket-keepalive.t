# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

plan tests => repeat_each() * (blocks() * 4 + 32);

our $HtmlDir = html_dir;

$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;
$ENV{TEST_NGINX_HTML_DIR} = $HtmlDir;
$ENV{TEST_NGINX_REDIS_PORT} ||= 6379;
$ENV{TEST_NGINX_RESOLVER} ||= '8.8.8.8';

log_level('debug');
no_long_string();
no_shuffle();

run_tests();

__DATA__

=== TEST 1: sanity
--- stream_server_config
    content_by_lua_block {
        local function go(port)
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("127.0.0.1", port)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end
            ngx.say("connected: ", ok, ", reused: ", sock:getreusedtimes())

            local bytes, err = sock:send("flush_all\r\n")
            if not bytes then
                ngx.say("failed to send request: ", err)
                return
            end
            ngx.say("request sent: ", bytes)

            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
            end

            local ok, err = sock:setkeepalive()
            if not ok then
                ngx.say("failed to setkeepalive: ", err)
                return
            end
        end

        go($TEST_NGINX_MEMCACHED_PORT)
        go($TEST_NGINX_MEMCACHED_PORT)
    }
--- stream_response
connected: 1, reused: 0
request sent: 11
received: OK
connected: 1, reused: 1
request sent: 11
received: OK
--- error_log eval
qq{
lua tcp socket get keepalive peer: using connection
lua tcp socket keepalive create connection pool for key "127\.0\.0\.1:$ENV{TEST_NGINX_MEMCACHED_PORT}"
}
--- no_error_log eval
[
"[error]",
"lua tcp socket keepalive: free connection pool for "
]



=== TEST 2: free up the whole connection pool if no active connections
--- stream_server_config
    content_by_lua_block {
       local function go(port, keepalive)
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("127.0.0.1", port)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end
            ngx.say("connected: ", ok, ", reused: ", sock:getreusedtimes())

            local bytes, err = sock:send("flush_all\r\n")
            if not bytes then
                ngx.say("failed to send request: ", err)
                return
            end
            ngx.say("request sent: ", bytes)

            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
            end

            if keepalive then
                local ok, err = sock:setkeepalive()
                if not ok then
                    ngx.say("failed to setkeepalive: ", err)
                    return
                end

            else
                sock:close()
            end
        end

        go($TEST_NGINX_MEMCACHED_PORT, true)
        go($TEST_NGINX_MEMCACHED_PORT, false)
    }
--- stream_response
connected: 1, reused: 0
request sent: 11
received: OK
connected: 1, reused: 1
request sent: 11
received: OK
--- error_log eval
[
"lua tcp socket get keepalive peer: using connection",
"lua tcp socket keepalive: free connection pool for "
]
--- no_error_log
[error]



=== TEST 3: upstream sockets close prematurely
--- config
    location /foo {
        server_tokens off;
        keepalive_timeout 100ms;
        echo foo;
    }
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeouts(1000, 1000, 1000)

        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.1\r\nHost: localhost\r\nConnection: keepalive\r\n\r\n"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local reader = sock:receiveuntil("\r\n0\r\n\r\n")
        local data, err = reader()
        if not data then
            ngx.say("failed to receive response body: ", err)
            return
        end

        ngx.say("received response of ", #data, " bytes")

        local ok, err = sock:setkeepalive()
        if not ok then
            ngx.say("failed to set reusable: ", err)
            return
        end

        ngx.sleep(1)

        ngx.say("done")
    }
--- stream_response
connected: 1
request sent: 61
received response of 156 bytes
done
--- error_log eval
[
"lua tcp socket keepalive close handler",
"lua tcp socket keepalive: free connection pool for "
]
--- no_error_log
[error]
--- timeout: 3



=== TEST 4: http keepalive
--- config
    location /foo {
        server_tokens off;
        keepalive_timeout 60s;
        echo foo;
    }
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeouts(1000, 1000, 1000)

        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.1\r\nHost: localhost\r\nConnection: keepalive\r\n\r\n"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local reader = sock:receiveuntil("\r\n0\r\n\r\n")
        local data, err = reader()
        if not data then
            ngx.say("failed to receive response body: ", err)
            return
        end

        ngx.say("received response of ", #data, " bytes")

        local ok, err = sock:setkeepalive()
        if not ok then
            ngx.say("failed to set reusable: ", err)
            return
        end

        ngx.sleep(1)

        ngx.say("done")
    }
--- stream_response
connected: 1
request sent: 61
received response of 156 bytes
done
--- no_error_log eval
[
"lua tcp socket keepalive close handler",
"lua tcp socket keepalive: free connection pool for "
]
--- timeout: 4



=== TEST 5: lua_socket_keepalive_timeout
--- config
    location /foo {
        server_tokens off;
        keepalive_timeout 60s;
        echo foo;
    }
--- stream_server_config
    lua_socket_keepalive_timeout 100ms;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeouts(1000, 1000, 1000)

        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.1\r\nHost: localhost\r\nConnection: keepalive\r\n\r\n"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local reader = sock:receiveuntil("\r\n0\r\n\r\n")
        local data, err = reader()
        if not data then
            ngx.say("failed to receive response body: ", err)
            return
        end

        ngx.say("received response of ", #data, " bytes")

        local ok, err = sock:setkeepalive()
        if not ok then
            ngx.say("failed to set reusable: ", err)
            return
        end

        ngx.sleep(1)

        ngx.say("done")
    }
--- stream_response
connected: 1
request sent: 61
received response of 156 bytes
done
--- no_error_log
[error]
--- error_log eval
["lua tcp socket keepalive close handler",
"lua tcp socket keepalive: free connection pool for ",
"lua tcp socket keepalive timeout: 100 ms",
qr/lua tcp socket connection pool size: 30\b/]
--- timeout: 4



=== TEST 6: lua_socket_pool_size
--- config
    location /foo {
        server_tokens off;
        keepalive_timeout 60s;
        echo foo;
    }
--- stream_server_config
    lua_socket_keepalive_timeout 100ms;
    lua_socket_pool_size 1;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeouts(1000, 1000, 1000)

        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.1\r\nHost: localhost\r\nConnection: keepalive\r\n\r\n"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local reader = sock:receiveuntil("\r\n0\r\n\r\n")
        local data, err = reader()
        if not data then
            ngx.say("failed to receive response body: ", err)
            return
        end

        ngx.say("received response of ", #data, " bytes")

        local ok, err = sock:setkeepalive()
        if not ok then
            ngx.say("failed to set reusable: ", err)
            return
        end

        ngx.sleep(1)

        ngx.say("done")
    }
--- stream_response
connected: 1
request sent: 61
received response of 156 bytes
done
--- no_error_log
[error]
--- error_log eval
["lua tcp socket keepalive close handler",
"lua tcp socket keepalive: free connection pool for ",
"lua tcp socket keepalive timeout: 100 ms",
qr/lua tcp socket connection pool size: 1\b/]
--- timeout: 4



=== TEST 7: "lua_socket_keepalive_timeout 0" means unlimited
--- config
    location /foo {
        server_tokens off;
        keepalive_timeout 60s;
        echo foo;
    }
--- stream_server_config
    lua_socket_keepalive_timeout 0;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeouts(1000, 1000, 1000)

        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.1\r\nHost: localhost\r\nConnection: keepalive\r\n\r\n"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local reader = sock:receiveuntil("\r\n0\r\n\r\n")
        local data, err = reader()
        if not data then
            ngx.say("failed to receive response body: ", err)
            return
        end

        ngx.say("received response of ", #data, " bytes")

        local ok, err = sock:setkeepalive()
        if not ok then
            ngx.say("failed to set reusable: ", err)
            return
        end

        ngx.sleep(1)

        ngx.say("done")
    }
--- stream_response
connected: 1
request sent: 61
received response of 156 bytes
done
--- no_error_log
[error]
--- error_log eval
["lua tcp socket keepalive timeout: unlimited",
qr/lua tcp socket connection pool size: 30\b/]
--- timeout: 4



=== TEST 8: setkeepalive(timeout) overrides lua_socket_keepalive_timeout
--- config
    location /foo {
        server_tokens off;
        keepalive_timeout 60s;
        echo foo;
    }
--- stream_server_config
    lua_socket_keepalive_timeout 60s;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeouts(1000, 1000, 1000)

        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.1\r\nHost: localhost\r\nConnection: keepalive\r\n\r\n"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local reader = sock:receiveuntil("\r\n0\r\n\r\n")
        local data, err = reader()
        if not data then
            ngx.say("failed to receive response body: ", err)
            return
        end

        ngx.say("received response of ", #data, " bytes")

        local ok, err = sock:setkeepalive(123)
        if not ok then
            ngx.say("failed to set reusable: ", err)
            return
        end

        ngx.sleep(1)

        ngx.say("done")
    }
--- stream_response
connected: 1
request sent: 61
received response of 156 bytes
done
--- no_error_log
[error]
--- error_log eval
["lua tcp socket keepalive close handler",
"lua tcp socket keepalive: free connection pool for ",
"lua tcp socket keepalive timeout: 123 ms",
qr/lua tcp socket connection pool size: 30\b/]
--- timeout: 4



=== TEST 9: sock:setkeepalive(timeout, size) overrides lua_socket_pool_size
--- config
    location /foo {
        server_tokens off;
        keepalive_timeout 100ms;
        echo foo;
    }
--- stream_server_config
    lua_socket_keepalive_timeout 60s;
    lua_socket_pool_size 100;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeouts(1000, 1000, 1000)

        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.1\r\nHost: localhost\r\nConnection: keepalive\r\n\r\n"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local reader = sock:receiveuntil("\r\n0\r\n\r\n")
        local data, err = reader()
        if not data then
            ngx.say("failed to receive response body: ", err)
            return
        end

        ngx.say("received response of ", #data, " bytes")

        local ok, err = sock:setkeepalive(101, 25)
        if not ok then
            ngx.say("failed to set reusable: ", err)
            return
        end

        ngx.sleep(1)

        ngx.say("done")
    }
--- stream_response
connected: 1
request sent: 61
received response of 156 bytes
done
--- no_error_log
[error]
--- error_log eval
["lua tcp socket keepalive close handler",
"lua tcp socket keepalive: free connection pool for ",
"lua tcp socket keepalive timeout: 101 ms",
qr/lua tcp socket connection pool size: 25\b/]
--- timeout: 4



=== TEST 10: setkeepalive() 'pool_size' should be greater than zero
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.socket.connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        if not sock then
            ngx.say(err)
            return
        end

        local ok, err = pcall(sock.setkeepalive, sock, 0, 0)
        if not ok then
            ngx.say(err)
            return
        end
        ngx.say(ok)
    }
--- stream_response
bad argument #3 to '?' (bad "pool_size" option value: 0)
--- no_error_log
[error]



=== TEST 11: sock:keepalive_timeout(0) means unlimited
--- config
    location /foo {
        server_tokens off;
        keepalive_timeout 60s;
        echo foo;
    }
--- stream_server_config
    lua_socket_keepalive_timeout 1000ms;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeouts(1000, 1000, 1000)

        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.1\r\nHost: localhost\r\nConnection: keepalive\r\n\r\n"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local reader = sock:receiveuntil("\r\n0\r\n\r\n")
        local data, err = reader()
        if not data then
            ngx.say("failed to receive response body: ", err)
            return
        end

        ngx.say("received response of ", #data, " bytes")

        local ok, err = sock:setkeepalive(0)
        if not ok then
            ngx.say("failed to set reusable: ", err)
            return
        end

        ngx.sleep(1)

        ngx.say("done")
    }
--- stream_response
connected: 1
request sent: 61
received response of 156 bytes
done
--- no_error_log
[error]
--- error_log eval
["lua tcp socket keepalive timeout: unlimited",
qr/lua tcp socket connection pool size: 30\b/]
--- timeout: 4



=== TEST 12: sanity (uds)
--- http_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock;
        default_type 'text/plain';
        server_tokens off;

        location /foo {
            echo foo;
            more_clear_headers Date;
        }
    }
--- stream_server_config
    content_by_lua_block {
        local function go(path)
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("unix:" .. path)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok, ", reused: ", sock:getreusedtimes())

            local req = "GET /foo HTTP/1.1\r\nHost: localhost\r\nConnection: keepalive\r\n\r\n"

            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send request: ", err)
                return
            end
            ngx.say("request sent: ", bytes)

            local reader = sock:receiveuntil("\r\n0\r\n\r\n")
            local data, err = reader()

            if not data then
                ngx.say("failed to receive response body: ", err)
                return
            end

            ngx.say("received response of ", #data, " bytes")

            local ok, err = sock:setkeepalive()
            if not ok then
                ngx.say("failed to set reusable: ", err)
            end
        end

        go("$TEST_NGINX_HTML_DIR/nginx.sock")
        go("$TEST_NGINX_HTML_DIR/nginx.sock")
    }
--- stream_response
connected: 1, reused: 0
request sent: 61
received response of 119 bytes
connected: 1, reused: 1
request sent: 61
received response of 119 bytes
--- error_log eval
[
"lua tcp socket get keepalive peer: using connection",
'lua tcp socket keepalive create connection pool for key "unix:'
]
--- no_error_log eval
[
"[error]",
"lua tcp socket keepalive: free connection pool for "
]



=== TEST 13: github issue #108: ngx.locaiton.capture + redis.set_keepalive
--- SKIP: ngx_http_lua only



=== TEST 14: github issue #110: ngx.exit with HTTP_NOT_FOUND causes worker process to exit
--- SKIP: ngx_http_lua only



=== TEST 15: custom pools (different pool for the same host:port) - tcp
--- stream_server_config
    content_by_lua_block {
        local function go(port, pool)
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("127.0.0.1", port, { pool = pool })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok, ", reused: ", sock:getreusedtimes())

            local ok, err = sock:setkeepalive()
            if not ok then
                ngx.say("failed to set reusable: ", err)
            end
        end

        go($TEST_NGINX_MEMCACHED_PORT, "A")
        go($TEST_NGINX_MEMCACHED_PORT, "B")
    }
--- stream_response
connected: 1, reused: 0
connected: 1, reused: 0
--- error_log
lua tcp socket keepalive create connection pool for key "A"
lua tcp socket keepalive create connection pool for key "B"
--- no_error_log eval
[
"[error]",
"lua tcp socket keepalive: free connection pool for ",
"lua tcp socket get keepalive peer: using connection"
]



=== TEST 16: custom pools (same pool for different host:port) - tcp
--- stream_server_config
    content_by_lua_block {
        local function go(port, pool)
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("127.0.0.1", port, { pool = pool })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok, ", reused: ", sock:getreusedtimes())

            local ok, err = sock:setkeepalive()
            if not ok then
                ngx.say("failed to set reusable: ", err)
            end
        end

        go($TEST_NGINX_MEMCACHED_PORT, "foo")
        go($TEST_NGINX_MEMCACHED_PORT, "foo")
    }
--- stream_response
connected: 1, reused: 0
connected: 1, reused: 1
--- error_log
lua tcp socket keepalive create connection pool for key "foo"
lua tcp socket get keepalive peer: using connection
--- no_error_log eval
[
"[error]",
"lua tcp socket keepalive: free connection pool for ",
]



=== TEST 17: custom pools (different pool for the same host:port) - unix
--- http_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock;
        default_type 'text/plain';
        server_tokens off;

        location /foo {
            echo foo;
            more_clear_headers Date;
        }
    }
--- stream_server_config
    content_by_lua_block {
        local function go(pool)
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock", { pool = pool })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok, ", reused: ", sock:getreusedtimes())

            local ok, err = sock:setkeepalive()
            if not ok then
                ngx.say("failed to set reusable: ", err)
            end
        end

        go("A")
        go("B")
    }
--- stream_response
connected: 1, reused: 0
connected: 1, reused: 0
--- error_log
lua tcp socket keepalive create connection pool for key "A"
lua tcp socket keepalive create connection pool for key "B"
--- no_error_log eval
[
"[error]",
"lua tcp socket keepalive: free connection pool for ",
"lua tcp socket get keepalive peer: using connection"
]



=== TEST 18: custom pools (same pool for the same path) - unix
--- http_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock;
        default_type 'text/plain';
        server_tokens off;

        location /foo {
            echo foo;
            more_clear_headers Date;
        }
    }
--- stream_server_config
    content_by_lua_block {
        local function go(pool)
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx.sock", { pool = pool })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok, ", reused: ", sock:getreusedtimes())

            local ok, err = sock:setkeepalive()
            if not ok then
                ngx.say("failed to set reusable: ", err)
            end
        end

        go("A")
        go("A")
    }
--- stream_response
connected: 1, reused: 0
connected: 1, reused: 1
--- error_log
lua tcp socket keepalive create connection pool for key "A"
lua tcp socket get keepalive peer: using connection
--- no_error_log eval
[
"[error]",
"lua tcp socket keepalive: free connection pool for ",
]



=== TEST 19: numeric pool option value
--- stream_server_config
    content_by_lua_block {
        local function go(port, pool)
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("127.0.0.1", port, { pool = pool })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok, ", reused: ", sock:getreusedtimes())

            local ok, err = sock:setkeepalive()
            if not ok then
                ngx.say("failed to set reusable: ", err)
            end
        end

        go($TEST_NGINX_MEMCACHED_PORT, 3.14)
        go($TEST_NGINX_SERVER_PORT, 3.14)
    }
--- stream_response
connected: 1, reused: 0
connected: 1, reused: 1
--- error_log
lua tcp socket keepalive create connection pool for key "3.14"
lua tcp socket get keepalive peer: using connection
--- no_error_log eval
[
"[error]",
"lua tcp socket keepalive: free connection pool for ",
]



=== TEST 20: nil pool option value
--- stream_server_config
    content_by_lua_block {
        local function go(port, pool)
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("127.0.0.1", port, { pool = pool })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok, ", reused: ", sock:getreusedtimes())

            local ok, err = sock:setkeepalive()
            if not ok then
                ngx.say("failed to set reusable: ", err)
            end
        end

        go($TEST_NGINX_MEMCACHED_PORT, nil)
        go($TEST_NGINX_SERVER_PORT, nil)
    }
--- stream_response
connected: 1, reused: 0
connected: 1, reused: 0
--- no_error_log
[error]



=== TEST 21: (bad) table pool option value
--- stream_server_config
    content_by_lua_block {
        local function go(port, pool)
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("127.0.0.1", port, { pool = pool })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok, ", reused: ", sock:getreusedtimes())

            local ok, err = sock:setkeepalive()
            if not ok then
                ngx.say("failed to set reusable: ", err)
            end
        end

        go($TEST_NGINX_MEMCACHED_PORT, {})
        go($TEST_NGINX_SERVER_PORT, {})
    }
--- stream_response
--- error_log
bad argument #3 to 'connect' (bad "pool" option type: table)



=== TEST 22: (bad) boolean pool option value
--- stream_server_config
    content_by_lua_block {
        local function go(port, pool)
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("127.0.0.1", port, { pool = pool })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok, ", reused: ", sock:getreusedtimes())

            local ok, err = sock:setkeepalive()
            if not ok then
                ngx.say("failed to set reusable: ", err)
            end
        end

        go($TEST_NGINX_MEMCACHED_PORT, true)
        go($TEST_NGINX_SERVER_PORT, false)
    }
--- stream_response
--- error_log
bad argument #3 to 'connect' (bad "pool" option type: boolean)



=== TEST 23: clear the redis store
--- SKIP: ngx_http_lua only



=== TEST 24: bug in send(): clear the chain writer ctx
--- SKIP
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        local port = ngx.var.port
        test.go($TEST_NGINX_REDIS_PORT)
    }
--- user_files
>>> test.lua
module("test", package.seeall)

function go(port)
    local sock = ngx.socket.tcp()
    local ok, err = sock:connect("127.0.0.1", port)
    if not ok then
        ngx.say("failed to connect: ", err)
        return
    end

    local bytes, err = sock:send({})
    if err then
        ngx.say("failed to send empty request: ", err)
        return
    end

    local req = "*2\r\n$3\r\nget\r\n$3\r\ndog\r\n"

    local bytes, err = sock:send(req)
    if not bytes then
        ngx.say("failed to send request: ", err)
        return
    end

    local line, err, part = sock:receive()
    if line then
        ngx.say("received: ", line)

    else
        ngx.say("failed to receive a line: ", err, " [", part, "]")
    end

    local ok, err = sock:setkeepalive()
    if not ok then
        ngx.say("failed to set reusable: ", err)
    end

    ngx.say("done")
end
--- stap2
global active
M(stream-lua-socket-tcp-send-start) {
    active = 1
    printf("send [%s] %d\n", text_str(user_string_n($arg3, $arg4)), $arg4)
}
M(stream-lua-socket-tcp-receive-done) {
    printf("receive [%s]\n", text_str(user_string_n($arg3, $arg4)))
}
F(ngx_output_chain) {
    #printf("ctx->in: %s\n", ngx_chain_dump($ctx->in))
    #printf("ctx->busy: %s\n", ngx_chain_dump($ctx->busy))
    printf("output chain: %s\n", ngx_chain_dump($in))
}
F(ngx_linux_sendfile_chain) {
    printf("linux sendfile chain: %s\n", ngx_chain_dump($in))
}
F(ngx_chain_writer) {
    printf("chain writer ctx out: %p\n", $data)
    printf("nginx chain writer: %s\n", ngx_chain_dump($in))
}
F(ngx_stream_lua_socket_tcp_setkeepalive) {
    delete active
}
M(stream-lua-socket-tcp-setkeepalive-buf-unread) {
    printf("setkeepalive unread: [%s]\n", text_str(user_string_n($arg3, $arg4)))
}
probe syscall.recvfrom {
    if (active && pid() == target()) {
        printf("recvfrom(%s)", argstr)
    }
}
probe syscall.recvfrom.return {
    if (active && pid() == target()) {
        printf(" = %s, data [%s]\n", retstr, text_str(user_string_n($ubuf, $size)))
    }
}
probe syscall.writev {
    if (active && pid() == target()) {
        printf("writev(%s)", ngx_iovec_dump($vec, $vlen))
        /*
        for (i = 0; i < $vlen; i++) {
            printf(" %p [%s]", $vec[i]->iov_base, text_str(user_string_n($vec[i]->iov_base, $vec[i]->iov_len)))
        }
        */
    }
}
probe syscall.writev.return {
    if (active && pid() == target()) {
        printf(" = %s\n", retstr)
    }
}
--- stream_response
received: $-1
done
--- no_error_log
[error]



=== TEST 25: setkeepalive() with explicit nil args
--- config
    location /foo {
        server_tokens off;
        keepalive_timeout 100ms;
        echo foo;
    }
--- stream_server_config
    lua_socket_keepalive_timeout 100ms;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeouts(1000, 1000, 1000)

        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.1\r\nHost: localhost\r\nConnection: keepalive\r\n\r\n"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local reader = sock:receiveuntil("\r\n0\r\n\r\n")
        local data, res = reader()

        if not data then
            ngx.say("failed to receive response body: ", err)
            return
        end

        ngx.say("received response of ", #data, " bytes")

        local ok, err = sock:setkeepalive(nil, nil)
        if not ok then
            ngx.say("failed to set reusable: ", err)
        end

        ngx.sleep(1)

        ngx.say("done")
    }
--- stream_response
connected: 1
request sent: 61
received response of 156 bytes
done
--- error_log eval
[
"lua tcp socket keepalive close handler",
"lua tcp socket keepalive: free connection pool for ",
"lua tcp socket keepalive timeout: 100 ms",
qr/lua tcp socket connection pool size: 30\b/
]
--- no_error_log
[error]
--- timeout: 4



=== TEST 26: conn queuing: connect() verifies the options for connection pool
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()

        local function check_opts_for_connect(opts)
            local ok, err = pcall(function()
                sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT, opts)
            end)
            if not ok then
                ngx.say(err)
            else
                ngx.say("ok")
            end
        end

        check_opts_for_connect({pool_size = 'a'})
        check_opts_for_connect({pool_size = 0})
        check_opts_for_connect({backlog = -1})
        check_opts_for_connect({backlog = 0})
    }
--- stream_response_like
.+ 'connect' \(bad "pool_size" option type: string\)
.+ 'connect' \(bad "pool_size" option value: 0\)
.+ 'connect' \(bad "backlog" option value: -1\)
ok
--- no_error_log
[error]



=== TEST 27: conn queuing: connect() can specify 'pool_size' which overrides setkeepalive()
--- stream_server_config
    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT;

        local function go()
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("127.0.0.1", port, { pool_size = 1 })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok, ", reused: ", sock:getreusedtimes())

            local req = "flush_all\r\n"
            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send request: ", err)
                return
            end
            ngx.say("request sent: ", bytes)

            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)
            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
            end

            local ok, err = sock:setkeepalive(0, 20)
            if not ok then
                ngx.say("failed to set reusable: ", err)
            end
        end

        -- reuse ok
        go()
        go()

        local sock1 = ngx.socket.connect("127.0.0.1", port)
        local sock2 = ngx.socket.connect("127.0.0.1", port)
        local ok, err = sock1:setkeepalive(0, 20)
        if not ok then
            ngx.say(err)
        end
        local ok, err = sock2:setkeepalive(0, 20)
        if not ok then
            ngx.say(err)
        end

        -- the pool_size is 1 instead of 20
        sock1 = ngx.socket.connect("127.0.0.1", port)
        sock2 = ngx.socket.connect("127.0.0.1", port)
        ngx.say("reused: ", sock1:getreusedtimes())
        ngx.say("reused: ", sock2:getreusedtimes())
        sock1:setkeepalive(0, 20)
        sock2:setkeepalive(0, 20)
    }
--- stream_response
connected: 1, reused: 0
request sent: 11
received: OK
connected: 1, reused: 1
request sent: 11
received: OK
reused: 1
reused: 0
--- error_log eval
[
qq{lua tcp socket keepalive create connection pool for key "127.0.0.1:$ENV{TEST_NGINX_MEMCACHED_PORT}"},
"lua tcp socket connection pool size: 1",
]
--- no_error_log eval
[
"[error]",
"lua tcp socket keepalive: free connection pool for ",
"lua tcp socket connection pool size: 20"
]



=== TEST 28: conn queuing: connect() can specify 'pool_size' for unix domain socket
--- http_config
    server {
        listen unix:$TEST_NGINX_HTML_DIR/nginx.sock;
    }
--- stream_server_config
    content_by_lua_block {
        local path = "unix:" .. "$TEST_NGINX_HTML_DIR/nginx.sock";

        local function go()
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect(path, { pool_size = 1 })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok, ", reused: ", sock:getreusedtimes())

            local ok, err = sock:setkeepalive(0, 20)
            if not ok then
                ngx.say("failed to set reusable: ", err)
            end
        end

        go()
        go()

        local sock1 = ngx.socket.connect(path)
        local sock2 = ngx.socket.connect(path)
        local ok, err = sock1:setkeepalive(0, 20)
        if not ok then
            ngx.say(err)
        end
        local ok, err = sock2:setkeepalive(0, 20)
        if not ok then
            ngx.say(err)
        end

        -- the pool_size is 1 instead of 20
        sock1 = ngx.socket.connect(path)
        sock2 = ngx.socket.connect(path)
        ngx.say("reused: ", sock1:getreusedtimes())
        ngx.say("reused: ", sock2:getreusedtimes())
        sock1:setkeepalive(0, 20)
        sock2:setkeepalive(0, 20)
    }
--- stream_response
connected: 1, reused: 0
connected: 1, reused: 1
reused: 1
reused: 0
--- error_log eval
[
"lua tcp socket get keepalive peer: using connection",
'lua tcp socket keepalive create connection pool for key "unix:',
"lua tcp socket connection pool size: 1",
]
--- no_error_log eval
[
"[error]",
"lua tcp socket keepalive: free connection pool for ",
"lua tcp socket connection pool size: 20"
]



=== TEST 29: conn queuing: connect() can specify 'pool_size' for custom pool
--- stream_server_config
    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT

        local function go(pool)
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("127.0.0.1", port, {
                pool = pool,
                pool_size = 1
            })
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", pool, ", reused: ", sock:getreusedtimes())

            local ok, err = sock:setkeepalive(0, 20)
            if not ok then
                ngx.say("failed to set reusable: ", err)
            end
        end

        go("A")
        go("B")
        go("A")
        go("B")

        local sock1 = ngx.socket.connect("127.0.0.1", port, {pool = 'A'})
        local sock2 = ngx.socket.connect("127.0.0.1", port, {pool = 'A'})
        local ok, err = sock1:setkeepalive(0, 20)
        if not ok then
            ngx.say(err)
        end
        local ok, err = sock2:setkeepalive(0, 20)
        if not ok then
            ngx.say(err)
        end

        -- the pool_size is 1 instead of 20
        sock1 = ngx.socket.connect("127.0.0.1", port, {pool = 'A'})
        sock2 = ngx.socket.connect("127.0.0.1", port, {pool = 'A'})
        ngx.say("reused: ", sock1:getreusedtimes())
        ngx.say("reused: ", sock2:getreusedtimes())
        sock1:setkeepalive(0, 20)
        sock2:setkeepalive(0, 20)
    }
--- stream_response
connected: A, reused: 0
connected: B, reused: 0
connected: A, reused: 1
connected: B, reused: 1
reused: 1
reused: 0
--- no_error_log eval
[
"[error]",
"lua tcp socket keepalive: free connection pool for ",
"lua tcp socket connection pool size: 20"
]
--- error_log eval
[
qq{lua tcp socket keepalive create connection pool for key "A"},
qq{lua tcp socket keepalive create connection pool for key "B"},
"lua tcp socket connection pool size: 1"
]



=== TEST 30: conn queuing: connect() uses lua_socket_pool_size as default if 'backlog' is given
--- stream_server_config
    lua_socket_pool_size 1234;

    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local sock, err = ngx.socket.connect("127.0.0.1", port, { backlog = 0 })
        if not sock then
            ngx.say(err)
        else
            ngx.say("ok")
        end
    }
--- stream_response
ok
--- error_log
lua tcp socket connection pool size: 1234
--- no_error_log
[error]



=== TEST 31: conn queuing: more connect operations than 'backlog' size
--- stream_server_config
    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT

        local opts = {pool_size = 2, backlog = 0}
        local sock = ngx.socket.connect("127.0.0.1", port, opts)
        local not_reused_socket, err = ngx.socket.connect("127.0.0.1", port, opts)
        if not not_reused_socket then
            ngx.say(err)
            return
        end
        -- burst
        local ok, err = ngx.socket.connect("127.0.0.1", port, opts)
        if not ok then
            ngx.say(err)
        end

        local ok, err = sock:setkeepalive()
        if not ok then
            ngx.say(err)
            return
        end

        ok, err = sock:connect("127.0.0.1", port, opts)
        if not ok then
            ngx.say(err)
        end
        ngx.say("reused: ", sock:getreusedtimes())
        -- both queue and pool is full
        ok, err = ngx.socket.connect("127.0.0.1", port, opts)
        if not ok then
            ngx.say(err)
        end
    }
--- stream_response
too many waiting connect operations
reused: 1
too many waiting connect operations
--- no_error_log
[error]



=== TEST 32: conn queuing: once 'pool_size' is reached and pool has 'backlog'
--- stream_server_config
    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local opts = {pool_size = 2, backlog = 2}
        local sock1 = ngx.socket.connect("127.0.0.1", port, opts)

        ngx.timer.at(0, function(premature)
            local sock2, err = ngx.socket.connect("127.0.0.1", port, opts)
            if not sock2 then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.log(ngx.WARN, "start to handle timer")
            ngx.sleep(0.1)
            sock2:close()
            -- resume connect operation
            ngx.log(ngx.WARN, "continue to handle timer")
        end)

        ngx.sleep(0.05)
        ngx.log(ngx.WARN, "start to handle cosocket")
        local sock3, err = ngx.socket.connect("127.0.0.1", port, opts)
        if not sock3 then
            ngx.say(err)
            return
        end
        ngx.log(ngx.WARN, "continue to handle cosocket")

        local req = "flush_all\r\n"
        local bytes, err = sock3:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end
        ngx.say("request sent: ", bytes)

        local line, err, part = sock3:receive()
        if line then
            ngx.say("received: ", line)
        else
            ngx.say("failed to receive a line: ", err, " [", part, "]")
        end

        local ok, err = sock3:setkeepalive()
        if not ok then
            ngx.say("failed to set reusable: ", err)
        end
        ngx.say("setkeepalive: OK")
    }
--- stream_response
request sent: 11
received: OK
setkeepalive: OK
--- no_error_log
[error]
--- error_log
lua tcp socket queue connect operation for connection pool "127.0.0.1
--- grep_error_log eval: qr/(start|continue) to handle \w+/
--- grep_error_log_out
start to handle timer
start to handle cosocket
continue to handle timer
continue to handle cosocket



=== TEST 33: conn queuing: do not count failed connect operations
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    resolver_timeout 3s;

    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local opts = {pool = "test", pool_size = 1, backlog = 0}

        local sock = ngx.socket.tcp()
        sock:settimeouts(100, 3000, 3000)
        local ok, err = sock:connect("127.0.0.2", 12345, opts)
        if not ok then
            ngx.say(err)
        end

        local sock, err = ngx.socket.connect("127.0.0.1", port, opts)
        if not sock then
            ngx.say(err)
        end
        ngx.say("ok")
    }
--- error_log
lua tcp socket connect timed out, when connecting to
--- stream_response
timeout
ok



=== TEST 34: conn queuing: connect until backlog is reached
--- stream_server_config
    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local opts = {pool_size = 1, backlog = 1}
        local sock1 = ngx.socket.connect("127.0.0.1", port, opts)

        ngx.timer.at(0.01, function(premature)
            ngx.log(ngx.WARN, "start to handle timer")
            local sock2, err = ngx.socket.connect("127.0.0.1", port, opts)
            if not sock2 then
                ngx.log(ngx.ERR, err)
                return
            end

            ngx.sleep(0.02)
            local ok, err = sock2:close()
            if not ok then
                ngx.log(ngx.ERR, err)
            end
            ngx.log(ngx.WARN, "continue to handle timer")
        end)

        ngx.sleep(0.02)
        local sock3, err = ngx.socket.connect("127.0.0.1", port, opts)
        if not sock3 then
            ngx.say(err)
        end
        local ok, err = sock1:setkeepalive()
        if not ok then
            ngx.say(err)
            return
        end
        ngx.sleep(0.01) -- run sock2

        ngx.log(ngx.WARN, "start to handle cosocket")
        local sock3, err = ngx.socket.connect("127.0.0.1", port, opts)
        if not sock3 then
            ngx.say(err)
            return
        end
        ngx.log(ngx.WARN, "continue to handle cosocket")

        local ok, err = sock3:setkeepalive()
        if not ok then
            ngx.say(err)
        end
    }
--- stream_response
too many waiting connect operations
--- error_log
lua tcp socket queue connect operation for connection pool "127.0.0.1
--- no_error_log
[error]
--- grep_error_log eval: qr/queue connect operation for connection pool|(start|continue) to handle \w+/
--- grep_error_log_out
start to handle timer
queue connect operation for connection pool
start to handle cosocket
queue connect operation for connection pool
continue to handle timer
continue to handle cosocket



=== TEST 35: conn queuing: memory reuse for host in queueing connect operation ctx
--- stream_server_config
    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local opts = {pool = "test", pool_size = 1, backlog = 3}
        local sock = ngx.socket.connect("127.0.0.1", port, opts)

        ngx.timer.at(0.01, function(premature)
            local sock, err = ngx.socket.connect("0.0.0.0", port, opts)
            if not sock then
                ngx.log(ngx.ERR, err)
                return
            end

            local ok, err = sock:close()
            if not ok then
                ngx.log(ngx.ERR, err)
            end
        end)

        ngx.timer.at(0.015, function(premature)
            local sock, err = ngx.socket.connect("127.0.0.1", port, opts)
            if not sock then
                ngx.log(ngx.ERR, err)
                return
            end

            local ok, err = sock:close()
            if not ok then
                ngx.log(ngx.ERR, err)
            end
        end)

        ngx.timer.at(0.02, function(premature)
            local sock, err = ngx.socket.connect("0.0.0.0", port, opts)
            if not sock then
                ngx.log(ngx.ERR, err)
                return
            end

            local ok, err = sock:close()
            if not ok then
                ngx.log(ngx.ERR, err)
            end
        end)

        ngx.sleep(0.03)
        local ok, err = sock:setkeepalive()
        if not ok then
            ngx.say(err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
ok
--- grep_error_log eval: qr/queue connect operation for connection pool/
--- grep_error_log_out
queue connect operation for connection pool
queue connect operation for connection pool
queue connect operation for connection pool
--- no_error_log
[error]



=== TEST 36: conn queuing: connect() returns error after connect operation resumed
--- stream_server_config
    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local opts = {pool = "test", pool_size = 1, backlog = 1}
        local sock = ngx.socket.connect("127.0.0.1", port, opts)

        ngx.timer.at(0, function(premature)
            local sock, err = ngx.socket.connect("", port, opts)
            if not sock then
                ngx.log(ngx.WARN, err)
            end
        end)

        ngx.sleep(0.01)
        -- use 'close' to force parsing host instead of reusing conn
        local ok, err = sock:close()
        if not ok then
            ngx.say(err)
            return
        end
        ngx.say("ok")
    }
--- stream_response
ok
--- error_log
failed to parse host name
--- no_error_log
[error]
--- grep_error_log eval: qr/queue connect operation for connection pool/
--- grep_error_log_out
queue connect operation for connection pool



=== TEST 37: conn queuing: in uthread
--- stream_server_config
    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local opts = {pool_size = 1, backlog = 2}

        local conn_sock = function()
            local sock, err = ngx.socket.connect("127.0.0.1", port, opts)
            if not sock then
                ngx.say(err)
                return
            end
            ngx.say("start to handle uthread")

            ngx.sleep(0.01)
            sock:close()
            ngx.say("continue to handle other uthread")
        end

        local sock, err = ngx.socket.connect("127.0.0.1", port, opts)
        if not sock then
            ngx.log(ngx.ERR, err)
            return
        end

        local co1 = ngx.thread.spawn(conn_sock)
        local co2 = ngx.thread.spawn(conn_sock)
        local co3 = ngx.thread.spawn(conn_sock)

        local ok, err = sock:setkeepalive()
        if not ok then
            ngx.log(ngx.ERR, err)
        end

        ngx.thread.wait(co1)
        ngx.thread.wait(co2)
        ngx.thread.wait(co3)
        ngx.say("all uthreads ok")
    }
--- stream_response
too many waiting connect operations
start to handle uthread
continue to handle other uthread
start to handle uthread
continue to handle other uthread
all uthreads ok
--- no_error_log
[error]
--- grep_error_log eval: qr/queue connect operation for connection pool/
--- grep_error_log_out
queue connect operation for connection pool
queue connect operation for connection pool



=== TEST 38: conn queuing: in access_by_lua
--- SKIP: ngx_http_lua only



=== TEST 39: conn queuing: in rewrite_by_lua
--- SKIP: ngx_http_lua only



=== TEST 40: conn queuing: in subrequest
--- SKIP: ngx_http_lua only



=== TEST 41: conn queuing: timeouts when 'connect_timeout' is reached
--- stream_server_config
    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local opts = {pool_size = 1, backlog = 1}
        local sock1 = ngx.socket.connect("127.0.0.1", port, opts)

        local sock2 = ngx.socket.tcp()
        sock2:settimeouts(100, 3000, 3000)
        local ok, err = sock2:connect("127.0.0.1", port, opts)
        if not ok then
            ngx.say(err)
        end
    }
--- stream_response
timeout
--- error_log eval
"lua tcp socket queued connect timed out, when trying to connect to 127.0.0.1:$ENV{TEST_NGINX_MEMCACHED_PORT}"



=== TEST 42: conn queuing: set timeout via lua_socket_connect_timeout
--- stream_server_config
    lua_socket_connect_timeout 100ms;

    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local opts = {pool_size = 1, backlog = 1}
        local sock1 = ngx.socket.connect("127.0.0.1", port, opts)

        local sock2 = ngx.socket.tcp()
        local ok, err = sock2:connect("127.0.0.1", port, opts)
        if not ok then
            ngx.say(err)
        end
    }
--- stream_response
timeout
--- error_log eval
"lua tcp socket queued connect timed out, when trying to connect to 127.0.0.1:$ENV{TEST_NGINX_MEMCACHED_PORT}"



=== TEST 43: conn queuing: client aborting while connect operation is queued
--- stream_server_config
    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local opts = {pool_size = 1, backlog = 1}
        local sock1 = ngx.socket.connect("127.0.0.1", port, opts)

        local sock2 = ngx.socket.tcp()
        sock2:settimeouts(3000, 3000, 3000)
        local ok, err = sock2:connect("127.0.0.1", port, opts)
        if not ok then
            ngx.say(err)
        end
    }
--- ignore_stream_response
--- timeout: 0.1
--- abort
--- no_error_log
[error]



=== TEST 44: conn queuing: resume next connect operation if resumed connect failed immediately
--- stream_server_config
    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local opts = {pool = "test", pool_size = 1, backlog = 2}

        local conn_sock = function(should_timeout)
            local sock = ngx.socket.tcp()
            local ok, err
            if should_timeout then
                ok, err = sock:connect("", port, opts)
            else
                ok, err = sock:connect("127.0.0.1", port, opts)
            end
            if not ok then
                ngx.say(err)
                return
            end
            ngx.say("connected in uthread")
            sock:close()
        end

        local sock, err = ngx.socket.connect("127.0.0.1", port, opts)
        if not sock then
            ngx.log(ngx.ERR, err)
            return
        end

        local co1 = ngx.thread.spawn(conn_sock, true)
        local co2 = ngx.thread.spawn(conn_sock)

        local ok, err = sock:close()
        if not ok then
            ngx.log(ngx.ERR, err)
        end

        ngx.thread.wait(co1)
        ngx.thread.wait(co2)
        ngx.say("ok")
    }
--- stream_response
failed to parse host name "": no host
connected in uthread
ok
--- no_error_log
[error]



=== TEST 45: conn queuing: resume connect operation if resumed connect failed (timeout)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    resolver_timeout 3s;

    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local opts = {pool = "test", pool_size = 1, backlog = 1}

        local conn_sock = function(should_timeout)
            local sock = ngx.socket.tcp()
            local ok, err
            if should_timeout then
                sock:settimeouts(100, 3000, 3000)
                ok, err = sock:connect("127.0.0.2", 12345, opts)
            else
                ok, err = sock:connect("127.0.0.1", port, opts)
            end
            if not ok then
                ngx.say(err)
                return
            end
            ngx.say("connected in uthread")
            sock:close()
        end

        local co1 = ngx.thread.spawn(conn_sock, true)
        local co2 = ngx.thread.spawn(conn_sock)

        ngx.thread.wait(co1)
        ngx.thread.wait(co2)
        ngx.say("ok")
    }
--- stream_response
timeout
connected in uthread
ok
--- error_log
queue connect operation for connection pool "test"
lua tcp socket connect timed out, when connecting to



=== TEST 46: conn queuing: resume connect operation if resumed connect failed (could not be resolved)
--- stream_server_config
    resolver 127.0.0.2:12345 ipv6=off;
    resolver_timeout 1s;

    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local opts = {pool = "test", pool_size = 1, backlog = 1}

        local conn_sock = function(should_timeout)
            local sock = ngx.socket.tcp()
            local ok, err
            if should_timeout then
                sock:settimeouts(1, 3000, 3000)
                ok, err = sock:connect("agentzh.org", 80, opts)
            else
                ok, err = sock:connect("127.0.0.1", port, opts)
            end
            if not ok then
                ngx.say(err)
                return
            end
            ngx.say("connected in uthread")
            sock:close()
        end

        local co1 = ngx.thread.spawn(conn_sock, true)
        local co2 = ngx.thread.spawn(conn_sock)

        ngx.thread.wait(co1)
        ngx.thread.wait(co2)
        ngx.say("ok")
    }
--- stream_response
agentzh.org could not be resolved (110: Operation timed out)
connected in uthread
ok
--- error_log
queue connect operation for connection pool "test"



=== TEST 47: conn queuing: resume connect operation if resumed connect failed (connection refused)
--- stream_server_config
    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT
        local opts = {pool = "test", pool_size = 1, backlog = 1}

        local conn_sock = function(should_timeout)
            local sock = ngx.socket.tcp()
            local ok, err
            if should_timeout then
                sock:settimeouts(100, 3000, 3000)
                ok, err = sock:connect("127.0.0.1", 62345, opts)
            else
                ok, err = sock:connect("127.0.0.1", port, opts)
            end
            if not ok then
                ngx.say(err)
                return
            end
            ngx.say("connected in uthread")
            sock:close()
        end

        local co1 = ngx.thread.spawn(conn_sock, true)
        local co2 = ngx.thread.spawn(conn_sock)

        ngx.thread.wait(co1)
        ngx.thread.wait(co2)
        ngx.say("ok")
    }
--- stream_response
connection refused
connected in uthread
ok
--- error_log
queue connect operation for connection pool "test"



=== TEST 48: conn queuing: resume connect operation if resumed connect failed (uthread aborted while resolving)
--- stream_server_config
    resolver 127.0.0.1 ipv6=off;
    resolver_timeout 100s;

    content_by_lua_block {
        local function sub()
            local semaphore = require "ngx.semaphore"
            local sem = semaphore.new()

            local function f()
                sem:wait(0.1)
                ngx.exit(0)
            end

            local port = $TEST_NGINX_MEMCACHED_PORT
            local opts = {pool = "test", pool_size = 1, backlog = 1}

            ngx.timer.at(0, function()
                sem:post()
                local sock2, err = ngx.socket.connect("127.0.0.1", port, opts)
                package.loaded.for_timer_to_resume:post()
                if not sock2 then
                    ngx.log(ngx.ALERT, "resume connect failed: ", err)
                    return
                end

                ngx.log(ngx.INFO, "resume success")
            end)

            ngx.thread.spawn(f)
            local sock1, err = ngx.socket.connect("openresty.org", 80, opts)
            if not sock1 then
                ngx.say(err)
                return
            end
        end

        local function t()
            local semaphore = require "ngx.semaphore"
            local for_timer_to_resume = semaphore.new()
            package.loaded.for_timer_to_resume = for_timer_to_resume

            ngx.thread.spawn(sub)
            for_timer_to_resume:wait(0.1)
        end

        t()
    }
--- no_error_log
[alert]
--- error_log
resume success



=== TEST 49: conn queuing: resume connect operation if resumed connect failed (uthread killed while resolving)
--- stream_server_config
    resolver 127.0.0.1 ipv6=off;
    resolver_timeout 100s;

    content_by_lua_block {
        local opts = {pool = "test", pool_size = 1, backlog = 1}
        local port = $TEST_NGINX_MEMCACHED_PORT

        local function resolve()
            local sock1, err = ngx.socket.connect("openresty.org", 80, opts)
            if not sock1 then
                ngx.say(err)
                return
            end
        end

        local th = ngx.thread.spawn(resolve)
        local ok, err = ngx.thread.kill(th)
        if not ok then
            ngx.log(ngx.ALERT, "kill thread failed: ", err)
            return
        end

        local sock2, err = ngx.socket.connect("127.0.0.1", port, opts)
        if not sock2 then
            ngx.log(ngx.ALERT, "resume connect failed: ", err)
            return
        end

        ngx.log(ngx.INFO, "resume success")
    }
--- no_error_log
[alert]
--- error_log
resume success



=== TEST 50: conn queuing: increase the counter for connections created before creating the pool with setkeepalive()
--- stream_server_config
    content_by_lua_block {
        local function connect()
            local sock, err = ngx.socket.connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
            if not sock then
                error("connect failed: " .. err)
            end

            return sock
        end

        local sock1 = connect()
        local sock2 = connect()
        assert(sock1:setkeepalive())
        assert(sock2:setkeepalive())

        local sock1 = connect()
        local sock2 = connect()
        assert(sock1:close())
        assert(sock2:close())

        ngx.say("ok")
    }
--- stream_response
ok
--- no_error_log
[error]



=== TEST 51: conn queuing: only decrease the counter for connections which were counted by the pool
--- stream_server_config
    content_by_lua_block {
        local function connect()
            local sock, err = ngx.socket.connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
            if not sock then
                error("connect failed: " .. err)
            end

            return sock
        end

        local sock1 = connect()
        local sock2 = connect()
        assert(sock1:setkeepalive(1000, 1))
        assert(sock2:setkeepalive(1000, 1))

        local sock1 = connect()
        local sock2 = connect()
        assert(sock1:close())
        assert(sock2:close())

        ngx.say("ok")
    }
--- stream_response
ok
--- no_error_log
[error]



=== TEST 52: conn queuing: clean up pending connect operations which are in queue
--- stream_server_config
    content_by_lua_block {
        local function sub()
            local opts = {pool = "test", pool_size = 1, backlog = 1}
            local sock, err = ngx.socket.connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT, opts)
            if not sock then
                ngx.say("connect failed: " .. err)
                return
            end

            local function f()
                assert(ngx.socket.connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT, opts))
            end

            local th = ngx.thread.spawn(f)
            local ok, err = ngx.thread.kill(th)
            if not ok then
                ngx.log(ngx.ERR, "kill thread failed: ", err)
                return
            end

            sock:close()
        end

        local function t()
            ngx.thread.spawn(sub)
            -- let pending connect operation resumes first
            ngx.sleep(0)
            ngx.say("ok")
        end

        t()
    }
--- stream_response
ok
--- error_log
lua tcp socket abort queueing
--- no_error_log
[error]
