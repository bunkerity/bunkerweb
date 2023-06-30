# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

repeat_each(2);

plan tests => repeat_each() * 219;

our $HtmlDir = html_dir;

$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;
$ENV{TEST_NGINX_RESOLVER} ||= '8.8.8.8';

#log_level 'warn';
log_level 'debug';

no_long_string();
#no_diff();
run_tests();

__DATA__

=== TEST 1: sanity
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;

    location /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }

--- stream_response
connected: 1
request sent: 57
received: HTTP/1.1 200 OK
received: Server: nginx
received: Content-Type: text/plain
received: Content-Length: 4
received: Connection: close
received: 
received: foo
failed to receive a line: closed []
close: 1 nil
--- no_error_log
[error]



=== TEST 2: no trailing newline
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
                break
            end
        end

        sock:close()
        ngx.say("closed")
    }

--- config
    server_tokens off;

    location /foo {
        content_by_lua_block { ngx.print("foo") }
        more_clear_headers Date;
    }
--- stream_response
connected: 1
request sent: 57
received: HTTP/1.1 200 OK
received: Server: nginx
received: Content-Type: text/plain
received: Content-Length: 3
received: Connection: close
received: 
failed to receive a line: closed [foo]
closed
--- no_error_log
[error]



=== TEST 3: no resolver defined
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("agentzh.org", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)
    }
--- stream_response
failed to connect: no resolver defined to resolve "agentzh.org"
connected: nil
failed to send request: closed
--- error_log
attempt to send data on a closed socket:



=== TEST 4: with resolver
--- timeout: 10
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    resolver_timeout 3s;
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = 80
        local ok, err = sock:connect("agentzh.org", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET / HTTP/1.0\r\nHost: agentzh.org\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local line, err = sock:receive()
        if line then
            ngx.say("first line received: ", line)

        else
            ngx.say("failed to receive the first line: ", err)
        end

        line, err = sock:receive()
        if line then
            ngx.say("second line received: ", line)

        else
            ngx.say("failed to receive the second line: ", err)
        end
    }

--- stream_response_like
connected: 1
request sent: 56
first line received: HTTP\/1\.1 200 OK
second line received: (?:Date|Server): .*?
--- no_error_log
[error]
--- timeout: 10



=== TEST 5: connection refused (tcp)
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", 16787)
        ngx.say("connect: ", ok, " ", err)

        local bytes
        bytes, err = sock:send("hello")
        ngx.say("send: ", bytes, " ", err)

        local line
        line, err = sock:receive()
        ngx.say("receive: ", line, " ", err)

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }
--- stream_response
connect: nil connection refused
send: nil closed
receive: nil closed
close: nil closed
--- error_log eval
qr/connect\(\) failed \(\d+: Connection refused\)/



=== TEST 6: connection timeout (tcp)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    #lua_socket_connect_timeout 100ms;
    #lua_socket_send_timeout 100ms;
    #lua_socket_read_timeout 100ms;
    resolver_timeout 3s;
    content_by_lua_block {
        local sock = ngx.socket.tcp()

        sock:settimeout(100)  -- ms

        local ok, err = sock:connect("127.0.0.2", 12345)
        ngx.say("connect: ", ok, " ", err)

        local bytes
        bytes, err = sock:send("hello")
        ngx.say("send: ", bytes, " ", err)

        local line
        line, err = sock:receive()
        ngx.say("receive: ", line, " ", err)

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }
--- stream_response
connect: nil timeout
send: nil closed
receive: nil closed
close: nil closed
--- error_log
lua tcp socket connect timed out, when connecting to 127.0.0.2:12345
--- timeout: 10



=== TEST 7: not closed manually
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)
    }
--- stream_response
connected: 1
--- no_error_log
[error]



=== TEST 8: resolver error (host not found)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    resolver_timeout 3s;
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = 80
        local ok, err = sock:connect("blah-blah-not-found.agentzh.org", port)
        print("connected: ", ok, " ", err, " ", not ok)
        if not ok then
            ngx.say("failed to connect: ", err)
        end

        ngx.say("connected: ", ok)

        local req = "GET / HTTP/1.0\r\nHost: agentzh.org\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)
    }
--- stream_response_like
^failed to connect: blah-blah-not-found\.agentzh\.org could not be resolved(?: \(3: Host not found\))?
connected: nil
failed to send request: closed$
--- error_log
attempt to send data on a closed socket
--- timeout: 10



=== TEST 9: resolver error (timeout)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    resolver_timeout 1ms;
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = 80
        local ok, err = sock:connect("blah-blah-not-found.agentzh.org", port)
        print("connected: ", ok, " ", err, " ", not ok)
        if not ok then
            ngx.say("failed to connect: ", err)
        end

        ngx.say("connected: ", ok)

        local req = "GET / HTTP/1.0\r\nHost: agentzh.org\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)
    }
--- stream_response_like
^failed to connect: blah-blah-not-found\.agentzh\.org could not be resolved(?: \(\d+: (?:Operation timed out|Host not found)\))?
connected: nil
failed to send request: closed$
--- error_log
attempt to send data on a closed socket



=== TEST 10: explicit *l pattern for receive
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local line, err = sock:receive("*l")
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err)
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    location = /foo {
        server_tokens off;
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }
--- stream_response
connected: 1
request sent: 57
received: HTTP/1.1 200 OK
received: Server: nginx
received: Content-Type: text/plain
received: Content-Length: 4
received: Connection: close
received: 
received: foo
failed to receive a line: closed
close: 1 nil
--- no_error_log
[error]



=== TEST 11: *a pattern for receive
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local data, err = sock:receive("*a")
        if data then
            ngx.say("receive: ", data)
            ngx.say("err: ", err)

        else
            ngx.say("failed to receive: ", err)
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;

    location = /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }
--- stream_response eval
"connected: 1
request sent: 57
receive: HTTP/1.1 200 OK\r
Server: nginx\r
Content-Type: text/plain\r
Content-Length: 4\r
Connection: close\r
\r
foo

err: nil
close: 1 nil
"
--- no_error_log
[error]



=== TEST 12: mixing *a and *l patterns for receive
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local line, err = sock:receive("*l")
        if line then
            ngx.say("receive: ", line)
            ngx.say("err: ", err)

        else
            ngx.say("failed to receive: ", err)
        end

        local data
        data, err = sock:receive("*a")
        if data then
            ngx.say("receive: ", data)
            ngx.say("err: ", err)

        else
            ngx.say("failed to receive: ", err)
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;
    location = /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }
--- stream_response eval
"connected: 1
request sent: 57
receive: HTTP/1.1 200 OK
err: nil
receive: Server: nginx\r
Content-Type: text/plain\r
Content-Length: 4\r
Connection: close\r
\r
foo

err: nil
close: 1 nil
"
--- no_error_log
[error]



=== TEST 13: receive by chunks
--- timeout: 5
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local data, err, partial = sock:receive(10)
            if data then
                local len = string.len(data)
                if len == 10 then
                    ngx.print("[", data, "]")
                else
                    ngx.say("ERROR: returned invalid length of data: ", len)
                end

            else
                ngx.say("failed to receive a line: ", err, " [", partial, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;

    location = /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }
--- stream_response eval
"connected: 1
request sent: 57
[HTTP/1.1 2][00 OK\r
Ser][ver: nginx][\r
Content-][Type: text][/plain\r
Co][ntent-Leng][th: 4\r
Con][nection: c][lose\r
\r
fo]failed to receive a line: closed [o
]
close: 1 nil
"
--- no_error_log
[error]



=== TEST 14: receive by chunks (very small buffer)
--- timeout: 5
--- stream_server_config
    lua_socket_buffer_size 1;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local data, err, partial = sock:receive(10)
            if data then
                local len = string.len(data)
                if len == 10 then
                    ngx.print("[", data, "]")
                else
                    ngx.say("ERROR: returned invalid length of data: ", len)
                end

            else
                ngx.say("failed to receive a line: ", err, " [", partial, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;
    location = /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }
--- stream_response eval
"connected: 1
request sent: 57
[HTTP/1.1 2][00 OK\r
Ser][ver: nginx][\r
Content-][Type: text][/plain\r
Co][ntent-Leng][th: 4\r
Con][nection: c][lose\r
\r
fo]failed to receive a line: closed [o
]
close: 1 nil
"
--- no_error_log
[error]



=== TEST 15: line reading (very small buffer)
--- stream_server_config
    lua_socket_buffer_size 1;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;
    location = /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }
--- stream_response
connected: 1
request sent: 57
received: HTTP/1.1 200 OK
received: Server: nginx
received: Content-Type: text/plain
received: Content-Length: 4
received: Connection: close
received: 
received: foo
failed to receive a line: closed []
close: 1 nil
--- no_error_log
[error]



=== TEST 16: ngx.socket.connect (working)
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.socket.connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not sock then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected.")

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;

    location = /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }
--- stream_response
connected.
request sent: 57
received: HTTP/1.1 200 OK
received: Server: nginx
received: Content-Type: text/plain
received: Content-Length: 4
received: Connection: close
received: 
received: foo
failed to receive a line: closed []
close: 1 nil
--- no_error_log
[error]



=== TEST 17: ngx.socket.connect() shortcut (connection refused)
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local sock, err = sock:connect("127.0.0.1", 16787)
        if not sock then
            ngx.say("failed to connect: ", err)
            return
        end

        local bytes
        bytes, err = sock:send("hello")
        ngx.say("send: ", bytes, " ", err)

        local line
        line, err = sock:receive()
        ngx.say("receive: ", line, " ", err)

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }
--- stap2
M(http-lua-info) {
    printf("tcp resume: %p\n", $coctx)
    print_ubacktrace()
}

--- stream_response
failed to connect: connection refused
--- error_log eval
qr/connect\(\) failed \(\d+: Connection refused\)/



=== TEST 18: receive by chunks (stringified size)
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local data, err, partial = sock:receive("10")
            if data then
                local len = string.len(data)
                if len == 10 then
                    ngx.print("[", data, "]")
                else
                    ngx.say("ERROR: returned invalid length of data: ", len)
                end

            else
                ngx.say("failed to receive a line: ", err, " [", partial, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;

    location = /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }
--- stream_response eval
"connected: 1
request sent: 57
[HTTP/1.1 2][00 OK\r
Ser][ver: nginx][\r
Content-][Type: text][/plain\r
Co][ntent-Leng][th: 4\r
Con][nection: c][lose\r
\r
fo]failed to receive a line: closed [o
]
close: 1 nil
"
--- no_error_log
[error]



=== TEST 19: cannot survive across request boundary (send)
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        test.go($TEST_NGINX_MEMCACHED_PORT)
    }
--- user_files
>>> test.lua
module("test", package.seeall)

local sock

function go(port)
    if not sock then
        sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)
    end

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
end
--- stream_response_like eval
"^(?:connected: 1
request sent: 11
received: OK|failed to send request: closed)\$"



=== TEST 20: cannot survive across request boundary (receive)
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        test.go($TEST_NGINX_MEMCACHED_PORT)
    }
--- user_files
>>> test.lua
module("test", package.seeall)

local sock

function go(port)
    if not sock then
        sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

    else
        local line, err, part = sock:receive()
        if line then
            ngx.say("received: ", line)

        else
            ngx.say("failed to receive a line: ", err, " [", part, "]")
        end
        return
    end

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
end

--- stap2
M(http-lua-info) {
    printf("tcp resume\n")
    print_ubacktrace()
}
--- stream_response_like eval
qr/^(?:connected: 1
request sent: 11
received: OK|failed to receive a line: closed \[nil\])$/



=== TEST 21: cannot survive across request boundary (close)
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        test.go($TEST_NGINX_MEMCACHED_PORT)
    }
--- user_files
>>> test.lua
module("test", package.seeall)

local sock

function go(port)
    if not sock then
        sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

    else
        local ok, err = sock:close()
        if ok then
            ngx.say("successfully closed")

        else
            ngx.say("failed to close: ", err)
        end
        return
    end

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
end
--- stream_response_like eval
qr/^(?:connected: 1
request sent: 11
received: OK|failed to close: closed)$/



=== TEST 22: cannot survive across request boundary (connect)
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        test.go($TEST_NGINX_MEMCACHED_PORT)
        test.go($TEST_NGINX_MEMCACHED_PORT)
    }
--- user_files
>>> test.lua
module("test", package.seeall)

local sock

function go(port)
    if not sock then
        sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

    else
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect again: ", err)
            return
        end

        ngx.say("connected again: ", ok)
    end

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
end
--- stream_response_like eval
qr/^(?:connected(?: again)?: 1
request sent: 11
received: OK
){2}$/
--- error_log
lua reuse socket upstream ctx
--- no_error_log
[error]
--- SKIP



=== TEST 23: connect again immediately
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_MEMCACHED_PORT

        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected again: ", ok)

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

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }
--- stream_response
connected: 1
connected again: 1
request sent: 11
received: OK
close: 1 nil
--- no_error_log
[error]
--- error_log eval
["lua reuse socket upstream", "lua tcp socket reconnect without shutting down"]



=== TEST 24: two sockets mix together
--- stream_server_config
    content_by_lua_block {
        local sock1 = ngx.socket.tcp()
        local sock2 = ngx.socket.tcp()

        local port1 = $TEST_NGINX_MEMCACHED_PORT
        local port2 = $TEST_NGINX_SERVER_PORT

        local ok, err = sock1:connect("127.0.0.1", port1)
        if not ok then
            ngx.say("1: failed to connect: ", err)
            return
        end

        ngx.say("1: connected: ", ok)

        ok, err = sock2:connect("127.0.0.1", port2)
        if not ok then
            ngx.say("2: failed to connect: ", err)
            return
        end

        ngx.say("2: connected: ", ok)

        local req1 = "flush_all\r\n"
        local bytes, err = sock1:send(req1)
        if not bytes then
            ngx.say("1: failed to send request: ", err)
            return
        end
        ngx.say("1: request sent: ", bytes)

        local req2 = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        local bytes, err = sock2:send(req2)
        if not bytes then
            ngx.say("2: failed to send request: ", err)
            return
        end
        ngx.say("2: request sent: ", bytes)

        local line, err, part = sock1:receive()
        if line then
            ngx.say("1: received: ", line)

        else
            ngx.say("1: failed to receive a line: ", err, " [", part, "]")
        end

        line, err, part = sock2:receive()
        if line then
            ngx.say("2: received: ", line)

        else
            ngx.say("2: failed to receive a line: ", err, " [", part, "]")
        end

        ok, err = sock1:close()
        ngx.say("1: close: ", ok, " ", err)

        ok, err = sock2:close()
        ngx.say("2: close: ", ok, " ", err)
    }

--- config
    server_tokens off;
    location = /foo {
        echo foo;
        more_clear_headers Date;
    }
--- stream_response
1: connected: 1
2: connected: 1
1: request sent: 11
2: request sent: 57
1: received: OK
2: received: HTTP/1.1 200 OK
1: close: 1 nil
2: close: 1 nil
--- no_error_log
[error]



=== TEST 25: send tables of string fragments
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = {"GET", " ", "/foo", " HTTP/", 1, ".", 0, "\r\n",
                     "Host: localhost\r\n", "Connection: close\r\n",
                     "\r\n"}
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;

    location /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }
--- stream_response
connected: 1
request sent: 57
received: HTTP/1.1 200 OK
received: Server: nginx
received: Content-Type: text/plain
received: Content-Length: 4
received: Connection: close
received: 
received: foo
failed to receive a line: closed []
close: 1 nil
--- no_error_log
[error]



=== TEST 26: send tables of string fragments (bad type "nil")
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = {"GET", " ", "/foo", " HTTP/", nil, 1, ".", 0, "\r\n",
                     "Host: localhost\r\n", "Connection: close\r\n",
                     "\r\n"}
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;
    location = /foo {
        echo foo;
        more_clear_headers Date;
    }
--- stream_response
connected: 1
--- error_log
bad argument #1 to 'send' (bad data type nil found)



=== TEST 27: send tables of string fragments (bad type "boolean")
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = {"GET", " ", "/foo", " HTTP/", true, 1, ".", 0, "\r\n",
                     "Host: localhost\r\n", "Connection: close\r\n",
                     "\r\n"}
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;
    location = /foo {
        echo foo;
        more_clear_headers Date;
    }
--- stream_response
connected: 1
--- error_log
bad argument #1 to 'send' (bad data type boolean found)



=== TEST 28: send tables of string fragments (bad type ngx.null)
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = {"GET", " ", "/foo", " HTTP/", ngx.null, 1, ".", 0, "\r\n",
                     "Host: localhost\r\n", "Connection: close\r\n",
                     "\r\n"}
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;
    location = /foo {
        echo foo;
        more_clear_headers Date;
    }
--- stream_response
connected: 1
--- error_log
bad argument #1 to 'send' (bad data type userdata found)



=== TEST 29: CR in a line
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;
    location = /foo {
        echo "foo\r\rbar\rbaz";
        more_clear_headers Date;
    }
--- stream_response
connected: 1
request sent: 57
received: HTTP/1.1 200 OK
received: Server: nginx
received: Content-Type: text/plain
received: Content-Length: 13
received: Connection: close
received: 
received: foobarbaz
failed to receive a line: closed []
close: nil closed
--- no_error_log
[error]
--- SKIP



=== TEST 30: receive(0)
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local data, err, part = sock:receive(0)
        if not data then
            ngx.say("failed to receive(0): ", err)
            return
        end

        ngx.say("receive(0): [", data, "]")

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;
    location = /foo {
        echo foo;
        more_clear_headers Date;
    }
--- stream_response
connected: 1
request sent: 57
receive(0): []
close: 1 nil
--- no_error_log
[error]



=== TEST 31: send("")
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local bytes, err = sock:send("")
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("send(\"\"): ", bytes)

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;
    location = /foo {
        echo foo;
        more_clear_headers Date;
    }
--- stream_response
connected: 1
request sent: 57
send(""): 0
close: 1 nil
--- no_error_log
[error]
[alert]



=== TEST 32: connection refused (tcp) - lua_socket_log_errors off
--- stream_server_config
    lua_socket_log_errors off;
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", 16787)
        ngx.say("connect: ", ok, " ", err)

        local bytes
        bytes, err = sock:send("hello")
        ngx.say("send: ", bytes, " ", err)

        local line
        line, err = sock:receive()
        ngx.say("receive: ", line, " ", err)

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }
--- stream_response
connect: nil connection refused
send: nil closed
receive: nil closed
close: nil closed
--- no_error_log eval
[qr/connect\(\) failed \(\d+: Connection refused\)/]



=== TEST 33: reread after a read time out happen (receive -> receive)
--- stream_server_config
    lua_socket_read_timeout 100ms;
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local line
        line, err = sock:receive()
        if line then
            ngx.say("received: ", line)
        else
            ngx.say("failed to receive: ", err)

            line, err = sock:receive()
            if not line then
                ngx.say("failed to receive: ", err)
            end
        end
    }
--- stream_response
connected: 1
failed to receive: timeout
failed to receive: timeout
--- error_log
lua tcp socket read timeout: 100
lua tcp socket connect timeout: 60000
lua tcp socket read timed out



=== TEST 34: successful reread after a read time out happen (receive -> receive)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        local bytes, err = sock:send("GET /back HTTP/1.1\r\nHost: localhost\r\n\r\n")
        if not bytes then
            ngx.say("failed to send: ", err)
            return
        end

        local reader = sock:receiveuntil("\r\n\r\n")
        local header, err = reader()
        if not header then
            ngx.say("failed to read the response header: ", err)
            return
        end

        sock:settimeout(100)

        local data, err, partial = sock:receive(100)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err, ", partial: ", partial)

            sock:settimeout(123)
            ngx.sleep(0.1)
            local line, err = sock:receive()
            if not line then
                ngx.say("failed to receive: ", err)
                return
            end
            ngx.say("received: ", line)

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to receive: ", err)
                return
            end
            ngx.say("received: ", line)
        end
    }

--- config
    location = /back {
        content_by_lua_block {
            ngx.print("hi")
            ngx.flush(true)
            ngx.sleep(0.2)
            ngx.print("world")
        }
    }
--- stream_response eval
"failed to receive: timeout, partial: 2\r
hi\r

received: 5
received: world
"
--- error_log
lua tcp socket read timed out
--- no_error_log
[alert]



=== TEST 35: successful reread after a read time out happen (receive -> receiveuntil)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        local bytes, err = sock:send("GET /back HTTP/1.1\r\nHost: localhost\r\n\r\n")
        if not bytes then
            ngx.say("failed to send: ", err)
            return
        end

        local reader = sock:receiveuntil("\r\n\r\n")
        local header, err = reader()
        if not header then
            ngx.say("failed to read the response header: ", err)
            return
        end

        sock:settimeout(100)

        local data, err, partial = sock:receive(100)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err, ", partial: ", partial)

            ngx.sleep(0.1)

            sock:settimeout(123)
            local reader = sock:receiveuntil("\r\n")

            local line, err = reader()
            if not line then
                ngx.say("failed to receive: ", err)
                return
            end
            ngx.say("received: ", line)

            local line, err = reader()
            if not line then
                ngx.say("failed to receive: ", err)
                return
            end
            ngx.say("received: ", line)
        end
    }

--- config
    server_tokens off;
    location = /back {
        content_by_lua_block {
            ngx.print("hi")
            ngx.flush(true)
            ngx.sleep(0.2)
            ngx.print("world")
        }
    }
--- stream_response eval
"failed to receive: timeout, partial: 2\r
hi\r

received: 5
received: world
"
--- error_log
lua tcp socket read timed out
--- no_error_log
[alert]



=== TEST 36: successful reread after a read time out happen (receiveuntil -> receiveuntil)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        local bytes, err = sock:send("GET /back HTTP/1.1\r\nHost: localhost\r\n\r\n")
        if not bytes then
            ngx.say("failed to send: ", err)
            return
        end

        local reader = sock:receiveuntil("\r\n\r\n")
        local header, err = reader()
        if not header then
            ngx.say("failed to read the response header: ", err)
            return
        end

        sock:settimeout(100)

        local reader = sock:receiveuntil("no-such-terminator")
        local data, err, partial = reader()
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err, ", partial: ", partial)

            ngx.sleep(0.1)

            sock:settimeout(123)

            local reader = sock:receiveuntil("\r\n")

            local line, err = reader()
            if not line then
                ngx.say("failed to receive: ", err)
                return
            end
            ngx.say("received: ", line)

            local line, err = reader()
            if not line then
                ngx.say("failed to receive: ", err)
                return
            end
            ngx.say("received: ", line)
        end
    }

--- config
    server_tokens off;
    location = /back {
        content_by_lua_block {
            ngx.print("hi")
            ngx.flush(true)
            ngx.sleep(0.2)
            ngx.print("world")
        }
    }
--- stream_response eval
"failed to receive: timeout, partial: 2\r
hi\r

received: 5
received: world
"
--- error_log
lua tcp socket read timed out
--- no_error_log
[alert]



=== TEST 37: successful reread after a read time out happen (receiveuntil -> receive)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        local bytes, err = sock:send("GET /back HTTP/1.1\r\nHost: localhost\r\n\r\n")
        if not bytes then
            ngx.say("failed to send: ", err)
            return
        end

        local reader = sock:receiveuntil("\r\n\r\n")
        local header, err = reader()
        if not header then
            ngx.say("failed to read the response header: ", err)
            return
        end

        sock:settimeout(100)

        local reader = sock:receiveuntil("no-such-terminator")
        local data, err, partial = reader()
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err, ", partial: ", partial)

            ngx.sleep(0.1)

            sock:settimeout(123)

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to receive: ", err)
                return
            end
            ngx.say("received: ", line)

            local line, err = sock:receive()
            if not line then
                ngx.say("failed to receive: ", err)
                return
            end
            ngx.say("received: ", line)
        end
    }

--- config
    server_tokens off;
    location = /back {
        content_by_lua_block {
            ngx.print("hi")
            ngx.flush(true)
            ngx.sleep(0.2)
            ngx.print("world")
        }
    }
--- stream_response eval
"failed to receive: timeout, partial: 2\r
hi\r

received: 5
received: world
"
--- error_log
lua tcp socket read timed out
--- no_error_log
[alert]



=== TEST 38: receive(0)
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local data, err = sock:receive(0)
        if not data then
            ngx.say("failed to receive: ", err)
            return
        end

        ngx.say("received: ", data)

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;
    location = /back {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }

--- stream_response
connected: 1
received: 
close: 1 nil
--- no_error_log
[error]



=== TEST 39: empty options table
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT
        local ok, err = sock:connect("127.0.0.1", port, {})
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- stream_response
connected: 1
close: 1 nil
--- no_error_log
[error]



=== TEST 40: u->coctx left over bug
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        local ready = false
        local fatal = false

        function f()
            local line, err, part = sock:receive()
            if not line then
                ngx.say("failed to receive the 1st line: ", err, " [", part, "]")
                fatal = true
                return
            end
            ready = true
            ngx.sleep(1)
        end

        local st = ngx.thread.spawn(f)
        while true do
            if fatal then
                return
            end

            if not ready then
                ngx.sleep(0.01)
            else
                break
            end
        end

        while true do
            local line, err, part = sock:receive()
            if line then
                -- ngx.say("received: ", line)

            else
                -- ngx.say("failed to receive a line: ", err, " [", part, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
        ngx.exit(0)
    }

--- config
    server_tokens off;
    location = /foo {
        content_by_lua_block { ngx.sleep(0.1) ngx.say("foo") }
        more_clear_headers Date;
    }

--- stream_response
connected: 1
request sent: 57
close: 1 nil
--- no_error_log
[error]
--- error_log
lua clean up the timer for pending ngx.sleep



=== TEST 41: bad request tries to connect
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        test.new_sock()
        local sock = test.get_sock()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
        else
            ngx.say("connected")
        end

        local function f()
            local sock = test.get_sock()
            local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to connect: ", err)
            end
        end

        ngx.timer.at(0, f)
        ngx.sleep(0.001)
    }

--- user_files
>>> test.lua
module("test", package.seeall)

local sock

function new_sock()
    sock = ngx.socket.tcp()
end

function get_sock()
    return sock
end
--- stream_response
connected

--- error_log eval
qr/runtime error: content_by_lua\(nginx\.conf:\d+\):14: bad request/

--- no_error_log
[alert]



=== TEST 42: bad request tries to receive
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        local sock = test.new_sock()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
        else
            ngx.say("connected")
        end
        local function f()
            local test = require "test"
            local sock = test.get_sock()
            sock:receive()
        end
        ngx.timer.at(0, f)
        ngx.sleep(0.001)
    }
--- user_files
>>> test.lua
module("test", package.seeall)

local sock

function new_sock()
    sock = ngx.socket.tcp()
    return sock
end

function get_sock()
    return sock
end
--- stream_response
connected

--- error_log eval
qr/runtime error: content_by_lua\(nginx\.conf:\d+\):13: bad request/

--- no_error_log
[alert]



=== TEST 43: bad request tries to send
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        local sock = test.new_sock()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
        else
            ngx.say("connected")
        end
        local function f()
            local sock = test.get_sock()
            sock:send("a")
        end
        ngx.timer.at(0, f)
        ngx.sleep(0.001)
    }
--- user_files
>>> test.lua
module("test", package.seeall)

local sock

function new_sock()
    sock = ngx.socket.tcp()
    return sock
end

function get_sock()
    return sock
end
--- stream_response
connected

--- error_log eval
qr/runtime error: content_by_lua\(nginx\.conf:\d+\):12: bad request/

--- no_error_log
[alert]



=== TEST 44: bad request tries to close
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        local sock = test.new_sock()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
        else
            ngx.say("connected")
        end
        local function f()
            local sock = test.get_sock()
            sock:close()
        end
        ngx.timer.at(0, f)
        ngx.sleep(0.001)
    }
--- user_files
>>> test.lua
module("test", package.seeall)

local sock

function new_sock()
    sock = ngx.socket.tcp()
    return sock
end

function get_sock()
    return sock
end
--- stream_response
connected

--- error_log eval
qr/runtime error: content_by_lua\(nginx\.conf:\d+\):12: bad request/

--- no_error_log
[alert]



=== TEST 45: bad request tries to set keepalive
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        local sock = test.new_sock()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
        else
            ngx.say("connected")
        end
        local function f()
            local sock = test.get_sock()
            sock:setkeepalive()
        end
        ngx.timer.at(0, f)
        ngx.sleep(0.001)
    }
--- user_files
>>> test.lua
module("test", package.seeall)

local sock

function new_sock()
    sock = ngx.socket.tcp()
    return sock
end

function get_sock()
    return sock
end
--- stream_response
connected

--- error_log eval
qr/runtime error: content_by_lua\(nginx\.conf:\d+\):12: bad request/

--- no_error_log
[alert]



=== TEST 46: bad request tries to receiveuntil
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        local sock = test.new_sock()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
        else
            ngx.say("connected")
        end
        local function f()
            local sock = test.get_sock()
            local it, err = sock:receiveuntil("abc")
            if it then
                it()
            end
        end
        ngx.timer.at(0, f)
        ngx.sleep(0.001)
    }
--- user_files
>>> test.lua
module("test", package.seeall)

local sock

function new_sock()
    sock = ngx.socket.tcp()
    return sock
end

function get_sock()
    return sock
end
--- stream_response
connected

--- error_log eval
qr/runtime error: content_by_lua\(nginx\.conf:\d+\):14: bad request/

--- no_error_log
[alert]



=== TEST 47: cosocket resolving aborted by coroutine yielding failures (require)
--- stream_config
    lua_package_path "$prefix/html/?.lua;;";
    resolver $TEST_NGINX_RESOLVER ipv6=off;

--- stream_server_config
    content_by_lua_block {
        package.loaded.myfoo = nil
        require "myfoo"
    }
--- user_files
>>> myfoo.lua
local sock = ngx.socket.tcp()
local ok, err = sock:connect("agentzh.org")
if not ok then
    ngx.log(ngx.ERR, "failed to connect: ", err)
    return
end

--- stream_response
--- wait: 0.3
--- error_log
resolve name done
runtime error: attempt to yield across C-call boundary
--- no_error_log
[alert]



=== TEST 48: cosocket resolving aborted by coroutine yielding failures (xpcall err)
--- stream_config
    lua_package_path "$prefix/html/?.lua;;";
    resolver $TEST_NGINX_RESOLVER ipv6=off;

--- stream_server_config
    content_by_lua_block {
        local function f()
            return error(1)
        end
        local function err()
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("agentzh.org")
            if not ok then
                ngx.log(ngx.ERR, "failed to connect: ", err)
                return
            end
        end
        xpcall(f, err)
        ngx.say("ok")
    }
--- stream_response
ok
--- wait: 0.3
--- error_log
resolve name done
--- no_error_log
[error]
[alert]
could not cancel



=== TEST 49: tcp_nodelay on
--- stream_server_config
    tcp_nodelay on;
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;

    location = /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }

--- stream_response
connected: 1
request sent: 57
received: HTTP/1.1 200 OK
received: Server: nginx
received: Content-Type: text/plain
received: Content-Length: 4
received: Connection: close
received: 
received: foo
failed to receive a line: closed []
close: 1 nil
--- error_log
stream lua socket tcp_nodelay
--- no_error_log
[error]



=== TEST 50: tcp_nodelay off
--- stream_server_config
    tcp_nodelay off;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT
        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- config
    server_tokens off;
    location = /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }

--- stream_response
connected: 1
request sent: 57
received: HTTP/1.1 200 OK
received: Server: nginx
received: Content-Type: text/plain
received: Content-Length: 4
received: Connection: close
received: 
received: foo
failed to receive a line: closed []
close: 1 nil
--- no_error_log
stream lua socket tcp_nodelay
[error]



=== TEST 51: IPv6
--- http_config
    server_tokens off;

    server {
        listen [::1]:$TEST_NGINX_SERVER_PORT;

        location = /foo {
            content_by_lua_block { ngx.say("foo") }
            more_clear_headers Date;
        }
    }
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("[::1]", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        -- req = "OK"

        local bytes, err = sock:send(req)
        if not bytes then
            ngx.say("failed to send request: ", err)
            return
        end

        ngx.say("request sent: ", bytes)

        while true do
            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)

            else
                ngx.say("failed to receive a line: ", err, " [", part, "]")
                break
            end
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- stream_response
connected: 1
request sent: 57
received: HTTP/1.1 200 OK
received: Server: nginx
received: Content-Type: text/plain
received: Content-Length: 4
received: Connection: close
received: 
received: foo
failed to receive a line: closed []
close: 1 nil
--- no_error_log
[error]
--- skip_eval: 3: system("ping6 -c 1 ::1 >/dev/null 2>&1") ne 0



=== TEST 52: kill a thread with a connecting socket
--- stream_server_config
    lua_socket_connect_timeout 1s;
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    resolver_timeout 3s;

    content_by_lua_block {
        local sock

        local thr = ngx.thread.spawn(function ()
            sock = ngx.socket.tcp()
            local ok, err = sock:connect("127.0.0.2", 12345)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)
        end)

        ngx.sleep(0.002)
        ngx.thread.kill(thr)
        ngx.sleep(0.001)

        local ok, err = sock:setkeepalive()
        if not ok then
            ngx.say("failed to setkeepalive: ", err)
        else
            ngx.say("setkeepalive: ", ok)
        end
    }

--- stream_response
failed to setkeepalive: closed
--- error_log
stream lua tcp socket connect timeout: 100
--- timeout: 10



=== TEST 53: reuse cleanup
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT

        for i = 1, 2 do
            local ok, err = sock:connect("127.0.0.1", port)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)

            local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"

            local bytes, err = sock:send(req)
            if not bytes then
                ngx.say("failed to send request: ", err)
                return
            end

            ngx.say("request sent: ", bytes)

            while true do
                local line, err, part = sock:receive()
                if not line then
                    ngx.say("failed to receive a line: ", err, " [", part, "]")
                    break
                end
            end

            ok, err = sock:close()
            ngx.say("close: ", ok, " ", err)
        end
    }

--- config
    server_tokens off;
    location = /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }

--- stream_response
connected: 1
request sent: 57
failed to receive a line: closed []
close: 1 nil
connected: 1
request sent: 57
failed to receive a line: closed []
close: 1 nil
--- error_log
lua stream cleanup reuse



=== TEST 54: reuse cleanup in ngx.timer (fake_request)
--- stream_server_config
    content_by_lua_block {
        local total_send_bytes = 0
        local port = $TEST_NGINX_SERVER_PORT

        local function network()
            local sock = ngx.socket.tcp()

            local ok, err = sock:connect("127.0.0.1", port)
            if not ok then
                ngx.log(ngx.ERR, "failed to connect: ", err)
                return
            end

            local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"

            local bytes, err = sock:send(req)
            if not bytes then
                ngx.log(ngx.ERR, "failed to send request: ", err)
                return
            end

            total_send_bytes = total_send_bytes + bytes

            while true do
                local line, err, part = sock:receive()
                if not line then
                    break
                end
            end

            ok, err = sock:close()
        end

        local done = false

        local function double_network()
            network()
            network()
            done = true
        end

        local ok, err = ngx.timer.at(0, double_network)
        if not ok then
            ngx.say("failed to create timer: ", err)
        end

        i = 1
        while not done do
            local time = 0.005 * i
            if time > 0.1 then
                time = 0.1
            end
            ngx.sleep(time)
            i = i + 1
        end

        collectgarbage("collect")

        ngx.say("total_send_bytes: ", total_send_bytes)
    }

--- config
    server_tokens off;
    location = /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }

--- stream_response
total_send_bytes: 114
--- error_log
lua stream cleanup reuse



=== TEST 55: free cleanup in ngx.timer (without sock:close)
--- stream_server_config
    content_by_lua_block {
        local total_send_bytes = 0

        local function network()
            local sock = ngx.socket.tcp()

            local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
            if not ok then
                ngx.log(ngx.ERR, "failed to connect: ", err)
                return
            end

            local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"

            local bytes, err = sock:send(req)
            if not bytes then
                ngx.log(ngx.ERR, "failed to send request: ", err)
                return
            end

            total_send_bytes = total_send_bytes + bytes

            while true do
                local line, err, part = sock:receive()
                if not line then
                    break
                end
            end
        end

        local done = false

        local function double_network()
            network()
            network()
            done = true
        end

        local ok, err = ngx.timer.at(0, double_network)
        if not ok then
            ngx.say("failed to create timer: ", err)
        end

        i = 1
        while not done do
            local time = 0.005 * i
            if time > 0.1 then
                time = 0.1
            end
            ngx.sleep(time)
            i = i + 1
        end

        collectgarbage("collect")

        ngx.say("total_send_bytes: ", total_send_bytes)
    }

--- config
    server_tokens off;

    location = /foo {
        content_by_lua_block { ngx.say("foo") }
        more_clear_headers Date;
    }

--- stream_response
total_send_bytes: 114
--- no_error_log
[error]



=== TEST 56: setkeepalive on socket already shutdown
--- stream_server_config
    lua_socket_connect_timeout 1s;
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    resolver_timeout 3s;

    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("openresty.org", 443)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local ok, err = sock:shutdown('send')
        if not ok then
            ngx.log(ngx.ERR, 'failed to shutdown socket: ', err)
            return
        end

        local ok, err = sock:setkeepalive()
        if not ok then
            ngx.log(ngx.ERR, "failed to setkeepalive: ", err)
        end
    }

--- stream_response
connected: 1
--- error_log
stream lua shutdown socket write direction
failed to setkeepalive: closed



=== TEST 57: options_table is nil
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT

        local ok, err = sock:connect("127.0.0.1", port, nil)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }
--- stream_response
connected: 1
close: 1 nil
--- no_error_log
[error]



=== TEST 58: resolver send query failing immediately in connect()
this case did not clear coctx->cleanup properly and would lead to memory invalid accesses.

this test case requires the following iptables rule to work properly:

sudo iptables -I OUTPUT 1 -p udp --dport 10086 -j REJECT

--- stream_server_config
    resolver 127.0.0.1:10086 ipv6=off;
    resolver_timeout 10ms;

    content_by_lua_block {
        local sock = ngx.socket.tcp()

        for i = 1, 3 do -- retry
            local ok, err = sock:connect("www.google.com", 80)
            if not ok then
                ngx.say("failed to connect: ", err)
            end
        end

        ngx.say("hello!")
    }
--- stream_response_body_like
failed to connect: www.google.com could not be resolved(?: \(\d+: Operation timed out\))?
failed to connect: www.google.com could not be resolved(?: \(\d+: Operation timed out\))?
failed to connect: www.google.com could not be resolved(?: \(\d+: Operation timed out\))?
hello!
--- error_log eval
qr{\[alert\] .*? send\(\) failed \(\d+: Operation not permitted\) while resolving}



=== TEST 59: the upper bound of port range should be 2^16 - 1
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.socket.connect("127.0.0.1", 65536)
        if not sock then
            ngx.say("failed to connect: ", err)
        end
    }

--- stream_response
failed to connect: bad port number: 65536
--- no_error_log
[error]



=== TEST 60: send boolean and nil
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local port = $TEST_NGINX_SERVER_PORT

        local ok, err = sock:connect("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        local function send(data)
            local bytes, err = sock:send(data)
            if not bytes then
                ngx.say("failed to send request: ", err)
                return
            end
        end

        local req = "GET /foo HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\nTest: "
        send(req)
        send(true)
        send(false)
        send(nil)
        send("\r\n\r\n")

        while true do
            local line, err, part = sock:receive()
            if line then
                ngx.say("received: ", line)
            else
                break
            end
        end

        ok, err = sock:close()
    }
--- config
    location /foo {
        server_tokens off;
        more_clear_headers Date;
        echo $http_test;
    }
--- stream_response
received: HTTP/1.1 200 OK
received: Server: nginx
received: Content-Type: text/plain
received: Connection: close
received: 
received: truefalsenil
--- no_error_log
[error]



=== TEST 61: TCP socket GC'ed in preread phase without Lua content phase
--- stream_server_config
    lua_socket_connect_timeout 1s;
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    resolver_timeout 3s;

    preread_by_lua_block {
        do
            local sock = ngx.socket.tcp()
            local ok, err = sock:connect("openresty.org", 443)
            if not ok then
                ngx.say("failed to connect: ", err)
                return
            end

            ngx.say("connected: ", ok)
        end

        ngx.timer.at(0, function()
            collectgarbage()
            ngx.log(ngx.WARN, "GC cycle done")
        end)
    }

    return 1;

--- stream_response chomp
connected: 1
1
--- no_error_log
[error]
--- error_log
cleanup lua tcp socket request
GC cycle done



=== TEST 62: receiveany method in cosocket
--- config
    location = /foo {
        server_tokens off;

        content_by_lua_block {
            local resp = {
                '1',
                '22',
                'hello world',
            }

            local length = 0
            for _, v in ipairs(resp) do
                length = length + #v
            end

            -- flush http header
            ngx.header['Content-Length'] = length
            ngx.flush(true)
            ngx.sleep(0.01)

            -- send http body
            for _, v in ipairs(resp) do
                ngx.print(v)
                ngx.flush(true)
                ngx.sleep(0.01)
            end
        }
    }
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(500)

        assert(sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT))
        local req = {
            'GET /foo HTTP/1.0\r\n',
            'Host: localhost\r\n',
            'Connection: close\r\n\r\n',
        }
        local ok, err = sock:send(req)
        if not ok then
            ngx.say("send request failed: ", err)
            return
        end

        -- skip http header
        while true do
            local data, err, _ = sock:receive('*l')
            if err then
                ngx.say('unexpected error occurs when receiving http head: ', err)
                return
            end

            if #data == 0 then -- read last line of head
                break
            end
        end

        -- receive http body
        while true do
            local data, err = sock:receiveany(1024)
            if err then
                if err ~= 'closed' then
                    ngx.say('unexpected err: ', err)
                end
                break
            end
            ngx.say(data)
        end

        sock:close()
    }
--- stream_response
1
22
hello world
--- no_error_log
[error]
--- error_log
lua tcp socket read any



=== TEST 63: receiveany send data after read side closed
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(500)
        assert(sock:connect("127.0.0.1", $TEST_NGINX_RAND_PORT_1))

        while true do
            local data, err = sock:receiveany(1024)
            if err then
                if err ~= 'closed' then
                    ngx.say('unexpected err: ', err)
                    break
                end

                local data = "send data after read side closed"
                local bytes, err = sock:send(data)
                if not bytes then
                    ngx.say(err)
                end

                break
            end
            ngx.say(data)
        end

        sock:close()
    }
--- tcp_listen: $TEST_NGINX_RAND_PORT_1
--- tcp_shutdown: 1
--- tcp_query eval: "send data after read side closed"
--- tcp_query_len: 32
--- stream_response
--- no_error_log
[error]



=== TEST 64: receiveany with limited, max <= 0
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(500)
        assert(sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT))

        local function receiveany_say_err(...)
            local ok, err = pcall(sock.receiveany, sock, ...)
            if not ok then
                ngx.say(err)
            end
        end


        receiveany_say_err(0)
        receiveany_say_err(-1)
        receiveany_say_err()
        receiveany_say_err(nil)
    }
--- stream_response
bad argument #2 to '?' (bad max argument)
bad argument #2 to '?' (bad max argument)
expecting 2 arguments (including the object), but got 1
bad argument #2 to '?' (bad max argument)
--- no_error_log
[error]



=== TEST 65: receiveany with limited, max is larger than data
--- config
    location = /foo {
        server_tokens off;

        content_by_lua_block {
            local resp = 'hello world'
            local length = #resp

            ngx.header['Content-Length'] = length
            ngx.flush(true)
            ngx.sleep(0.01)

            ngx.print(resp)
        }
    }
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(500)

        assert(sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT))
        local req = {
            'GET /foo HTTP/1.0\r\n',
            'Host: localhost\r\n',
            'Connection: close\r\n\r\n',
        }
        local ok, err = sock:send(req)
        if not ok then
            ngx.say("send request failed: ", err)
            return
        end

        while true do
            local data, err, _ = sock:receive('*l')
            if err then
                ngx.say('unexpected error occurs when receiving http head: ', err)
                return
            end

            if #data == 0 then -- read last line of head
                break
            end
        end

        local data, err = sock:receiveany(128)
        if err then
            if err ~= 'closed' then
                ngx.say('unexpected err: ', err)
            end
        else
            ngx.say(data)
        end

        sock:close()
    }
--- stream_response
hello world
--- no_error_log
[error]
--- error_log
lua tcp socket calling receiveany() method to read at most 128 bytes



=== TEST 66: receiveany with limited, max is smaller than data
--- config
    location = /foo {
        server_tokens off;

        content_by_lua_block {
            local resp = 'hello world'
            local length = #resp

            ngx.header['Content-Length'] = length
            ngx.flush(true)
            ngx.sleep(0.01)

            ngx.print(resp)
        }
    }
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        sock:settimeout(500)

        assert(sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT))
        local req = {
            'GET /foo HTTP/1.0\r\n',
            'Host: localhost\r\n',
            'Connection: close\r\n\r\n',
        }
        local ok, err = sock:send(req)
        if not ok then
            ngx.say("send request failed: ", err)
            return
        end

        while true do
            local data, err, _ = sock:receive('*l')
            if err then
                ngx.say('unexpected error occurs when receiving http head: ', err)
                return
            end

            if #data == 0 then -- read last line of head
                break
            end
        end

        while true do
            local data, err = sock:receiveany(7)
            if err then
                if err ~= 'closed' then
                    ngx.say('unexpected err: ', err)
                end
                break

            else
                ngx.say(data)
            end
        end

        sock:close()
    }
--- stream_response
hello w
orld
--- no_error_log
[error]
--- error_log
lua tcp socket calling receiveany() method to read at most 7 bytes
