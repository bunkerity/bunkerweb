# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

repeat_each(2);

plan tests => repeat_each() * (3 * blocks() + 14);

our $HtmlDir = html_dir;

$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;
$ENV{TEST_NGINX_RESOLVER} ||= '8.8.8.8';

#log_level 'warn';

no_long_string();
#no_diff();
#no_shuffle();
check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: sanity
--- stream_server_config

    content_by_lua_block {
        local socket = ngx.socket
        -- local socket = require "socket"

        local udp = socket.udp()

        local port = $TEST_NGINX_MEMCACHED_PORT
        udp:settimeout(1000) -- 1 sec

        local ok, err = udp:setpeername("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected")

        local req = "\0\1\0\0\0\1\0\0flush_all\r\n"
        local ok, err = udp:send(req)
        if not ok then
            ngx.say("failed to send: ", err)
            return
        end

        local data, err = udp:receive()
        if not data then
            ngx.say("failed to receive data: ", err)
            return
        end
        ngx.print("received ", #data, " bytes: ", data)
    }

--- config
    server_tokens off;
--- stream_response eval
"connected\nreceived 12 bytes: \x{00}\x{01}\x{00}\x{00}\x{00}\x{01}\x{00}\x{00}OK\x{0d}\x{0a}"
--- no_error_log
[error]
--- log_level: debug
--- error_log
lua udp socket receive buffer size: 8192



=== TEST 2: multiple parallel queries
--- stream_server_config

    content_by_lua_block {
        local socket = ngx.socket
        -- local socket = require "socket"

        local udp = socket.udp()

        local port = $TEST_NGINX_MEMCACHED_PORT
        udp:settimeout(1000) -- 1 sec

        local ok, err = udp:setpeername("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected")

        local req = "\0\1\0\0\0\1\0\0flush_all\r\n"
        local ok, err = udp:send(req)
        if not ok then
            ngx.say("failed to send: ", err)
            return
        end

        req = "\0\2\0\0\0\1\0\0flush_all\r\n"
        ok, err = udp:send(req)
        if not ok then
            ngx.say("failed to send: ", err)
            return
        end

        ngx.sleep(0.05)

        local data, err = udp:receive()
        if not data then
            ngx.say("failed to receive data: ", err)
            return
        end
        ngx.print("1: received ", #data, " bytes: ", data)

        data, err = udp:receive()
        if not data then
            ngx.say("failed to receive data: ", err)
            return
        end
        ngx.print("2: received ", #data, " bytes: ", data)
    }

--- config
    server_tokens off;
--- stream_response_like eval
"^connected\n"
."1: received 12 bytes: "
."\x{00}[\1\2]\x{00}\x{00}\x{00}\x{01}\x{00}\x{00}OK\x{0d}\x{0a}"
."2: received 12 bytes: "
."\x{00}[\1\2]\x{00}\x{00}\x{00}\x{01}\x{00}\x{00}OK\x{0d}\x{0a}\$"
--- no_error_log
[error]



=== TEST 3: access a TCP interface
--- stream_server_config

    content_by_lua_block {
        local socket = ngx.socket
        -- local socket = require "socket"

        local udp = socket.udp()

        local port = $TEST_NGINX_SERVER_PORT
        udp:settimeout(1000) -- 1 sec

        local ok, err = udp:setpeername("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected")

        local req = "\0\1\0\0\0\1\0\0flush_all\r\n"
        local ok, err = udp:send(req)
        if not ok then
            ngx.say("failed to send: ", err)
            return
        end

        local data, err = udp:receive()
        if not data then
            ngx.say("failed to receive data: ", err)
            return
        end
        ngx.print("received ", #data, " bytes: ", data)
    }

--- config
    server_tokens off;
--- stream_response
connected
failed to receive data: connection refused
--- error_log eval
qr/recv\(\) failed \(\d+: Connection refused\)/



=== TEST 4: access conflicts of connect() on shared udp objects
--- stream_config
    lua_package_path '$prefix/html/?.lua;;';
--- stream_server_config
    content_by_lua_block {
        local function f()
            local port = $TEST_NGINX_MEMCACHED_PORT
            local foo = require "foo"
            local udp = foo.get_udp()

            udp:settimeout(100) -- 100 ms

            local ok, err = udp:setpeername("127.0.0.1", port)
            if not ok then
                ngx.log(ngx.ERR, "failed to connect: ", err)
                return
            end

            print("test: connected")

            local data, err = udp:receive()
            if not data then
                ngx.say("failed to receive data: ", err)
                return
            end
            print("test: received ", #data, " bytes: ", data)
        end
        for i = 1, 170 do
            assert(ngx.timer.at(0, f))
        end
    }

--- user_files
>>> foo.lua
module("foo", package.seeall)

local udp

function get_udp()
    if not udp then
        udp = ngx.socket.udp()
    end

    return udp
end

--- stap2
M(http-lua-info) {
    printf("udp resume: %p\n", $coctx)
    print_ubacktrace()
}

--- stream_response
--- error_log eval
qr/content_by_lua\(nginx\.conf:\d+\):9: bad request/



=== TEST 5: access conflicts of receive() on shared udp objects
--- stream_config
    lua_package_path '$prefix/html/?.lua;;';
--- stream_server_config
    content_by_lua_block {
        function f()
            local port = $TEST_NGINX_MEMCACHED_PORT
            local foo = require "foo"
            local udp = foo.get_udp(port)

            local data, err = udp:receive()
            if not data then
                ngx.log(ngx.ERR, "failed to receive data: ", err)
                return ngx.exit(500)
            end
            ngx.print("received ", #data, " bytes: ", data)
        end

        for i = 1, 170 do
            assert(ngx.timer.at(0, f))
        end
    }

--- user_files
>>> foo.lua
module("foo", package.seeall)

local udp

function get_udp(port)
    if not udp then
        udp = ngx.socket.udp()

        udp:settimeout(100) -- 100ms

        local ok, err = udp:setpeername("127.0.0.1", port)
        if not ok then
            ngx.log(ngx.ERR, "failed to connect: ", err)
            return ngx.exit(500)
        end
    end

    return udp
end
--- stream_response
--- error_log eval
qr/content_by_lua\(nginx\.conf:\d+\):7: bad request/



=== TEST 6: connect again immediately
--- stream_server_config

    content_by_lua_block {
        local sock = ngx.socket.udp()
        local port = $TEST_NGINX_MEMCACHED_PORT

        local ok, err = sock:setpeername("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        ok, err = sock:setpeername("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected again: ", ok)

        local req = "\0\1\0\0\0\1\0\0flush_all\r\n"
        local ok, err = sock:send(req)
        if not ok then
            ngx.say("failed to send request: ", err)
            return
        end
        ngx.say("request sent: ", ok)

        local line, err = sock:receive()
        if line then
            ngx.say("received: ", line)

        else
            ngx.say("failed to receive: ", err)
        end

        ok, err = sock:close()
        ngx.say("close: ", ok, " ", err)
    }

--- stream_response eval
"connected: 1
connected again: 1
request sent: 1
received: \0\1\0\0\0\1\0\0OK\r\n
close: 1 nil
"
--- no_error_log
[error]
--- error_log eval
["lua reuse socket upstream", "lua udp socket reconnect without shutting down"]
--- log_level: debug



=== TEST 7: recv timeout
--- stream_server_config

    content_by_lua_block {
        local port = $TEST_NGINX_MEMCACHED_PORT

        local sock = ngx.socket.udp()
        sock:settimeout(100) -- 100 ms

        local ok, err = sock:setpeername("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected: ", ok)

        local line, err = sock:receive()
        if line then
            ngx.say("received: ", line)

        else
            ngx.say("failed to receive: ", err)
        end

        -- ok, err = sock:close()
        -- ngx.say("close: ", ok, " ", err)
    }

--- stream_response
connected: 1
failed to receive: timeout
--- error_log
lua udp socket read timed out



=== TEST 8: with an explicit receive buffer size argument
--- stream_server_config

    content_by_lua_block {
        local socket = ngx.socket
        -- local socket = require "socket"

        local udp = socket.udp()

        local port = $TEST_NGINX_MEMCACHED_PORT
        udp:settimeout(1000) -- 1 sec

        local ok, err = udp:setpeername("127.0.0.1", port)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected")

        local req = "\0\1\0\0\0\1\0\0flush_all\r\n"
        local ok, err = udp:send(req)
        if not ok then
            ngx.say("failed to send: ", err)
            return
        end

        local data, err = udp:receive(1400)
        if not data then
            ngx.say("failed to receive data: ", err)
            return
        end
        ngx.print("received ", #data, " bytes: ", data)
    }

--- stream_response eval
"connected\nreceived 12 bytes: \x{00}\x{01}\x{00}\x{00}\x{00}\x{01}\x{00}\x{00}OK\x{0d}\x{0a}"
--- no_error_log
[error]
--- log_level: debug
--- error_log
lua udp socket receive buffer size: 1400



=== TEST 9: read timeout and re-receive
--- stream_server_config
    content_by_lua_block {
        local udp = ngx.socket.udp()
        udp:settimeout(30)
        local ok, err = udp:setpeername("127.0.0.1", 19232)
        if not ok then
            ngx.say("failed to setpeername: ", err)
            return
        end
        local ok, err = udp:send("blah")
        if not ok then
            ngx.say("failed to send: ", err)
            return
        end
        for i = 1, 2 do
            local data, err = udp:receive()
            if err == "timeout" then
                -- continue
            else
                if not data then
                    ngx.say("failed to receive: ", err)
                    return
                end
                ngx.say("received: ", data)
                return
            end
        end

        ngx.say("timed out")
    }

--- udp_listen: 19232
--- udp_reply: hello world
--- udp_reply_delay: 45ms
--- stream_response
received: hello world
--- error_log
lua udp socket read timed out



=== TEST 10: access the google DNS server (using IP addr)
--- stream_server_config
    content_by_lua_block {
        local socket = ngx.socket
        -- local socket = require "socket"

        local udp = socket.udp()

        udp:settimeout(2000) -- 2 sec

        local ok, err = udp:setpeername("$TEST_NGINX_RESOLVER", 53)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        local req = "\0}\1\0\0\1\0\0\0\0\0\0\3www\6google\3com\0\0\1\0\1"

        -- ngx.print(req)
        -- do return end

        local ok, err = udp:send(req)
        if not ok then
            ngx.say("failed to send: ", err)
            return
        end

        local data, err = udp:receive()
        if not data then
            ngx.say("failed to receive data: ", err)
            return
        end

        if string.match(data, "\3www\6google\3com") then
            ngx.say("received a good response.")
        else
            ngx.say("received a bad response: ", #data, " bytes: ", data)
        end
    }

--- stream_response
received a good response.
--- no_error_log
[error]
--- log_level: debug
--- error_log
lua udp socket receive buffer size: 8192



=== TEST 11: access the google DNS server (using domain names)
--- stream_server_config
    resolver $TEST_NGINX_RESOLVER ipv6=off;
    content_by_lua_block {
        -- avoid flushing google in "check leak" testing mode:
        local counter = package.loaded.counter
        if not counter then
            counter = 1
        elseif counter >= 2 then
            return ngx.exit(503)
        else
            counter = counter + 1
        end
        package.loaded.counter = counter

        local socket = ngx.socket
        -- local socket = require "socket"

        local udp = socket.udp()

        udp:settimeout(2000) -- 2 sec

        local ok, err = udp:setpeername("google-public-dns-a.google.com", 53)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        local req = "\0}\1\0\0\1\0\0\0\0\0\0\3www\6google\3com\0\0\1\0\1"

        -- ngx.print(req)
        -- do return end

        local ok, err = udp:send(req)
        if not ok then
            ngx.say("failed to send: ", err)
            return
        end

        local data, err = udp:receive()
        if not data then
            ngx.say("failed to receive data: ", err)
            return
        end

        if string.match(data, "\3www\6google\3com") then
            ngx.say("received a good response.")
        else
            ngx.say("received a bad response: ", #data, " bytes: ", data)
        end
    }

--- stream_response
received a good response.
--- no_error_log
[error]
--- log_level: debug
--- error_log
lua udp socket receive buffer size: 8192



=== TEST 12: datagram unix domain socket
--- stream_server_config

    content_by_lua_block {
        local socket = ngx.socket
        -- local socket = require "socket"

        local udp = socket.udp()

        udp:settimeout(2000) -- 1 sec

        local ok, err = udp:setpeername("unix:a.sock")
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        ngx.say("connected")

        local req = "hello,\nserver"
        local ok, err = udp:send(req)
        if not ok then
            ngx.say("failed to send: ", err)
            return
        end

        local data, err = udp:receive()
        if not data then
            ngx.say("failed to receive data: ", err)
            return
        end
        ngx.print("received ", #data, " bytes: ", data)
    }

--- udp_listen: a.sock
--- udp_reply
hello,
client

--- stream_response
connected
received 14 bytes: hello,
client

--- stap2
probe syscall.socket, syscall.connect {
    print(name, "(", argstr, ")")
}

probe syscall.socket.return, syscall.connect.return {
    println(" = ", retstr)
}
--- no_error_log
[error]
[crit]
--- skip_eval: 3: $^O ne 'linux'



=== TEST 13: bad request tries to setpeer
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config

    content_by_lua_block {
        local test = require "test"
        local sock = test.new_sock()
        local ok, err = sock:setpeername("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        if not ok then
            ngx.say("failed to set peer: ", err)
        else
            ngx.say("peer set")
        end
        function f()
            local sock = test.get_sock()
            sock:setpeername("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        end
        ngx.timer.at(0, f)
        ngx.sleep(0.001)
    }
--- user_files
>>> test.lua
module("test", package.seeall)

local sock

function new_sock()
    sock = ngx.socket.udp()
    return sock
end

function get_sock()
    return sock
end
--- stream_response
peer set

--- error_log eval
qr/runtime error: content_by_lua\(nginx\.conf:\d+\):12: bad request/

--- no_error_log
[alert]



=== TEST 14: bad request tries to send
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config

    content_by_lua_block {
        local test = require "test"
        local sock = test.new_sock()
        local ok, err = sock:setpeername("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        if not ok then
            ngx.say("failed to set peer: ", err)
        else
            ngx.say("peer set")
        end
        function f()
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
    sock = ngx.socket.udp()
    return sock
end

function get_sock()
    return sock
end
--- stream_response
peer set

--- error_log eval
qr/runtime error: content_by_lua\(nginx\.conf:\d+\):12: bad request/

--- no_error_log
[alert]



=== TEST 15: bad request tries to receive
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config

    content_by_lua_block {
        local test = require "test"
        local sock = test.new_sock()
        local ok, err = sock:setpeername("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        if not ok then
            ngx.say("failed to set peer: ", err)
        else
            ngx.say("peer set")
        end

        local function f()
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
    sock = ngx.socket.udp()
    return sock
end

function get_sock()
    return sock
end
--- stream_response
peer set

--- error_log eval
qr/runtime error: content_by_lua\(nginx\.conf:\d+\):13: bad request/

--- no_error_log
[alert]



=== TEST 16: bad request tries to close
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        local sock = test.new_sock()
        local ok, err = sock:setpeername("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        if not ok then
            ngx.say("failed to set peer: ", err)
        else
            ngx.say("peer set")
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
    sock = ngx.socket.udp()
    return sock
end

function get_sock()
    return sock
end
--- stream_response
peer set

--- error_log eval
qr/runtime error: content_by_lua\(nginx\.conf:\d+\):12: bad request/

--- no_error_log
[alert]



=== TEST 17: the upper bound of port range should be 2^16 - 1
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.udp()
        local ok, err = sock:setpeername("127.0.0.1", 65536)
        if not ok then
            ngx.say("failed to connect: ", err)
        end
    }
--- stream_response
failed to connect: bad port number: 65536
--- no_error_log
[error]



=== TEST 18: send boolean and nil
--- stream_server_config
    content_by_lua_block {
        local socket = ngx.socket
        local udp = socket.udp()
        local port = ngx.var.port
        udp:settimeout(1000) -- 1 sec

        local ok, err = udp:setpeername("127.0.0.1", $TEST_NGINX_MEMCACHED_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        local function send(data)
            local bytes, err = udp:send(data)
            if not bytes then
                ngx.say("failed to send: ", err)
                return
            end
            ngx.say("sent ok")
        end

        send(true)
        send(false)
        send(nil)
    }
--- stream_response
sent ok
sent ok
sent ok
--- no_error_log
[error]
--- grep_error_log eval
qr/sendto: fd:\d+ \d+ of \d+/
--- grep_error_log_out eval
qr/sendto: fd:\d+ 4 of 4
sendto: fd:\d+ 5 of 5
sendto: fd:\d+ 3 of 3/
--- log_level: debug



=== TEST 19: UDP socket GC'ed in preread phase without Lua content phase
--- stream_server_config
    preread_by_lua_block {
        do
            local udpsock = ngx.socket.udp()

            local res, err = udpsock:setpeername("127.0.0.1", 1234)
            if not res then
                ngx.log(ngx.ERR, err)
            end
        end

        ngx.timer.at(0, function()
            collectgarbage()
            ngx.log(ngx.WARN, "GC cycle done")
        end)
    }

    return 1;

--- stream_response chomp
1
--- no_error_log
[error]
--- error_log
cleanup lua udp socket upstream request
GC cycle done
