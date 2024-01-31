# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;
repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 11);

our $HtmlDir = html_dir;

#$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;

no_long_string();
#no_diff();
#log_level 'warn';

run_tests();

__DATA__

=== TEST 1: sanity
--- stream_server_config
    preread_by_lua_block {
        local sock, err = ngx.req.socket()
        if sock then
            ngx.say("got the request socket")
        else
            ngx.say("failed to get the request socket: ", err)
        end

        for i = 1, 2 do
            local data, err, part = sock:receive(5)
            if data then
                ngx.say("received: ", data)
            else
                ngx.say("failed to receive: ", err, " [", part, "]")
            end
        end

        local data, err, part = sock:receive(1)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err, " [", part, "]")
            return
        end
    }
    content_by_lua return;
--- stream_request chop
hello world
--- stream_response
got the request socket
received: hello
received:  worl
received: d
--- no_error_log
[error]



=== TEST 2: attempt to use the req socket across request boundary
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    preread_by_lua_block {
        local test = require "test"
        test.go()
        ngx.say("done")
    }
    content_by_lua return;
--- user_files
>>> test.lua
module("test", package.seeall)

local sock, err

function go()
    if not sock then
        sock, err = ngx.req.socket()
        if sock then
            ngx.say("got the request socket")
        else
            ngx.say("failed to get the request socket: ", err)
        end
    else
        for i = 1, 3 do
            local data, err, part = sock:receive(5)
            if data then
                ngx.say("received: ", data)
            else
                ngx.say("failed to receive: ", err, " [", part, "]")
            end
        end
    end
end
--- stream_response_like
(?:got the request socket
|failed to receive: closed [d]
)?done
--- no_error_log
[alert]



=== TEST 3: receive until on request_body - receiveuntil(1) on the last byte of the body
See https://groups.google.com/group/openresty/browse_thread/thread/43cf01da3c681aba for details
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    preread_by_lua_block {
            local test = require "test"
            test.go()
            ngx.say("done")
    }
    content_by_lua return;
--- user_files
>>> test.lua
module("test", package.seeall)

function go()
   local sock, err = ngx.req.socket()
   if sock then
      ngx.say("got the request socket")
   else
      ngx.say("failed to get the request socket: ", err)
      return
   end

   local data, err, part = sock:receive(56)
   if data then
      ngx.say("received: ", data)
   else
      ngx.say("failed to receive: ", err, " [", part, "]")
   end

   local discard_line = sock:receiveuntil('\r\n')

   local data, err, part = discard_line(8192)
   if data then
      ngx.say("received len: ", #data)
   else
      ngx.say("failed to receive: ", err, " [", part, "]")
   end

   local data, err, part = discard_line(1)
   if data then
      ngx.say("received: ", data)
   else
      ngx.say("failed to receive: ", err, " [", part, "]")
   end
end
--- stream_request chop
-----------------------------820127721219505131303151179################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################################$
--- stream_response
got the request socket
received: -----------------------------820127721219505131303151179
received len: 8192
received: $
done
--- no_error_log
[error]
--- timeout: 10



=== TEST 4: read from preread buffer
--- stream_server_config
    ssl_preread on;

    preread_by_lua_block {
        local sock, err = ngx.req.socket()
        if sock then
            ngx.say("got the request socket")
        else
            ngx.say("failed to get the request socket: ", err)
            return
        end

        for i = 1, 2 do
            local data, err, part = sock:receive(5)
            if data then
                ngx.say("received: ", data)
            else
                ngx.say("failed to receive: ", err, " [", part, "]")
                return
            end
        end

        local data, err, part = sock:receive(1)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err, " [", part, "]")
            return
        end
    }
    content_by_lua return;
--- stream_request chop
hello world
--- stream_response
got the request socket
received: hello
received:  worl
received: d
--- no_error_log
[error]



=== TEST 5: small preread buffer
--- stream_server_config
    ssl_preread on;
    preread_buffer_size 5;

    preread_by_lua_block {
        local sock, err = ngx.req.socket()
        if sock then
            ngx.say("got the request socket")
        else
            ngx.say("failed to get the request socket: ", err)
            return
        end

        for i = 1, 2 do
            local data, err, part = sock:receive(5)
            if data then
                ngx.say("received: ", data)
            else
                ngx.say("failed to receive: ", err, " [", part, "]")
                return
            end
        end

        local data, err, part = sock:receive(1)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err, " [", part, "]")
            return
        end
    }
    content_by_lua return;
--- stream_request chop
hello world
--- stream_response
got the request socket
received: hello
received:  worl
received: d
--- no_error_log
[error]



=== TEST 6: peeking preread buffer
--- stream_server_config
    preread_by_lua_block {
        local sock, err = ngx.req.socket()
        if sock then
            ngx.say("got the request socket")
        else
            ngx.say("failed to get the request socket: ", err)
            return
        end

        local data, err = sock:peek(5)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err)
            return
        end

        data, err = sock:peek(10)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err)
            return
        end
    }

    proxy_pass 127.0.0.1:$TEST_NGINX_RAND_PORT_1;
--- stream_config
server {
    listen 127.0.0.1:$TEST_NGINX_RAND_PORT_1;

    content_by_lua_block {
        local sock, err = ngx.req.socket()
        if sock then
            ngx.say("got the request socket")
        else
            ngx.say("failed to get the request socket: ", err)
            return
        end

        local data, err = sock:receive(11)
        if data then
            ngx.log(ngx.DEBUG, "upstream received: ", data)

        else
            ngx.say("failed to receive: ", err)
            return
        end

        ngx.say("done")
    }
}
--- stream_request chop
hello world
--- stream_response
got the request socket
received: hello
received: hello worl
got the request socket
done
--- error_log
upstream received: hello world
--- no_error_log
[error]



=== TEST 7: peeking preread buffer, buffer size is small
--- stream_server_config
    preread_buffer_size 10;

    preread_by_lua_block {
        local sock = assert(ngx.req.socket())

        local data, err = sock:peek(5)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err)
            return
        end

        data, err = sock:peek(11)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err)
            return
        end
    }

    return done;
--- stream_request chop
hello world
--- error_log
preread buffer full while prereading client data
finalize stream session: 400
--- no_error_log
[warn]



=== TEST 8: peeking preread buffer, timedout
--- stream_server_config
    preread_timeout 100ms;

    preread_by_lua_block {
        local sock = assert(ngx.req.socket())

        local data, err = sock:peek(5)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err)
            return
        end

        ngx.flush(true)

        data, err = sock:peek(12)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err)
            return
        end
    }

    return done;
--- stream_request chop
hello world
--- stream_response
received: hello
--- error_log
finalize stream session: 200
--- no_error_log
[warn]
[error]



=== TEST 9: peek in wrong phase
--- stream_server_config
    content_by_lua_block {
        local sock = assert(ngx.req.socket())

        local data, err = sock:peek(5)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err)
            return
        end
    }
--- stream_request chop
hello world
--- error_log
API disabled in the context of content_by_lua*
--- no_error_log
[warn]



=== TEST 10: peek busy reading
--- stream_server_config
    preread_by_lua_block {
        local sock, err = ngx.req.socket()
        if sock then
            ngx.say("got the request socket")
        else
            ngx.say("failed to get the request socket: ", err)
            return
        end

        ngx.thread.spawn(function()
            local data, err = sock:peek(15)
            if data then
                ngx.say("received: ", data)
            else
                ngx.say("failed to receive: ", err)
                return
            end
        end)

        local data, err = sock:peek(5)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err)
            return ngx.exit(ngx.OK)
        end
    }

    return done;
--- stream_request
--- stream_response chop
got the request socket
failed to receive: socket busy reading
done
--- no_error_log
[warn]
[error]



=== TEST 11: peek before and after receive
--- stream_server_config
    preread_by_lua_block {
        local sock, err = ngx.req.socket()
        if sock then
            ngx.say("got the request socket")
        else
            ngx.say("failed to get the request socket: ", err)
            return
        end

        local data, err = sock:peek(5)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err)
            return
        end

        ngx.flush(true)

        data, err = sock:receive(11)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err)
            return
        end

        ngx.flush(true)

        data, err = sock:peek(1)
        if data then
            ngx.say("received: ", data)
        else
            ngx.say("failed to receive: ", err)
            return
        end
    }

    return done;
--- stream_request chop
hello world
--- stream_response
got the request socket
received: hello
received: hello world
--- error_log
attempt to peek on a consumed socket
--- no_error_log
[warn]



=== TEST 12: peek works with other preread handlers
--- stream_server_config
    ssl_preread on;
    preread_by_lua_block {
        local rsock = assert(ngx.req.socket())

        local data, err = rsock:peek(2)
        if not data then
            ngx.log(ngx.ERR, "failed to peek the request socket: ", err)
            return
        end

        local n = ngx.var.ssl_preread_server_name
        if not n or n == '' then
            ngx.log(ngx.INFO, "$ssl_preread_server_name is empty")

        else
            ngx.log(ngx.INFO, "$ssl_preread_server_name = ", n)
        end


        if n == "my.sni.server.name" then
            assert(string.byte(data:sub(1, 1)) == 0x16)
            assert(string.byte(data:sub(2, 2)) == 0x03)
            ngx.exit(200)
        end

        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", tonumber(ngx.var.server_port))
        if not ok then
            ngx.say(err)
            return ngx.exit(500)
        end

        local _, err = sock:sslhandshake(nil, "my.sni.server.name")
        if not err then
            ngx.say("did not error as expected")
            return ngx.exit(500)
        end

        sock:close()
    }

    return done;
--- stream_request chop
hello
--- stream_response chop
done
--- error_log
$ssl_preread_server_name is empty while prereading client data
$ssl_preread_server_name = my.sni.server.name while prereading client data
--- no_error_log
[crit]
[warn]
assertion failed!
lua entry thread aborted
