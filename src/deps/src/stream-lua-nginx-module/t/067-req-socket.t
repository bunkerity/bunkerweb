# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 9);

our $HtmlDir = html_dir;

#$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;

no_long_string();
#no_diff();
#log_level 'warn';
no_shuffle();

run_tests();

__DATA__

=== TEST 1: sanity
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket()
        if sock then
            ngx.say("got the request socket")
        else
            ngx.say("failed to get the request socket: ", err)
        end

        for i = 1, 3 do
            local data, err, part = sock:receive(5)
            if data then
                ngx.say("received: ", data)
            else
                ngx.say("failed to receive: ", err, " [", part, "]")
            end
        end
    }
--- stream_request chomp
hello world! my
--- stream_response
got the request socket
received: hello
received:  worl
received: d! my
--- no_error_log
[error]



=== TEST 2: multipart rfc sample (just partial streaming)
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket()
        if sock then
            ngx.say("got the request socket")
        else
            ngx.say("failed to get the request socket: ", err)
        end

        local boundary = "simple boundary"

        local read_to_boundary = sock:receiveuntil("\r\n--" .. boundary)
        local read_line = sock:receiveuntil("\r\n")

        local data, err, part = read_to_boundary()
        if data then
            ngx.say("preamble: [" .. data .. "]")
        else
            ngx.say("failed to read the first boundary: ", err)
            return
        end

        sock:settimeout(1000)

        local i = 1
        while true do
            local line, err = read_line()

            if not line then
                ngx.say("failed to read post-boundary line: ", err)
                return
            end

            m = ngx.re.match(line, "--$", "jo")
            if m then
                ngx.say("found the end of the stream")
                sock:receive() -- consume the epiloque.
                return
            end

            while true do
                local line, err = read_line()
                if not line then
                    ngx.say("failed to read part ", i, " header: ", err)
                    return
                end

                if line == "" then
                    -- the header part completes
                    break
                end

                ngx.say("part ", i, " header: [", line, "]")
            end

            local data, err, part = read_to_boundary()
            if data then
                ngx.say("part ", i, " body: [" .. data .. "]")
            else
                ngx.say("failed to read part ", i + 1, " boundary: ", err)
                return
            end

            i = i + 1
        end
    }
--- stream_request eval
"This is the preamble.  It is to be ignored, though it
is a handy place for mail composers to include an
explanatory note to non-MIME compliant readers.\r
--simple boundary\r
\r
This is implicitly typed plain ASCII text.
It does NOT end with a linebreak.\r
--simple boundary\r
Content-type: text/plain; charset=us-ascii\r
\r
This is explicitly typed plain ASCII text.
It DOES end with a linebreak.
\r
--simple boundary--\r
This is the epilogue.  It is also to be ignored.
"
--- stream_response
got the request socket
preamble: [This is the preamble.  It is to be ignored, though it
is a handy place for mail composers to include an
explanatory note to non-MIME compliant readers.]
part 1 body: [This is implicitly typed plain ASCII text.
It does NOT end with a linebreak.]
part 2 header: [Content-type: text/plain; charset=us-ascii]
part 2 body: [This is explicitly typed plain ASCII text.
It DOES end with a linebreak.
]
found the end of the stream
--- no_error_log
[error]



=== TEST 3: multipart rfc sample (completely streaming)
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket()
        if sock then
            ngx.say("got the request socket")
        else
            ngx.say("failed to get the request socket: ", err)
        end

        local boundary = "simple boundary"

        local read_to_boundary = sock:receiveuntil("\r\n--" .. boundary)
        local read_line = sock:receiveuntil("\r\n")

        local preamble = ""
        while true do
            local data, err, part = read_to_boundary(1)
            if data then
                preamble = preamble .. data

            elseif not err then
                break

            else
                ngx.say("failed to read the first boundary: ", err)
                return
            end
        end

        ngx.say("preamble: [" .. preamble .. "]")

        local i = 1
        while true do
            local line, err = read_line(50)

            if not line and err then
                ngx.say("1: failed to read post-boundary line: ", err)
                return
            end

            if line then
                local dummy
                dummy, err = read_line(1)
                if err then
                    ngx.say("2: failed to read post-boundary line: ", err)
                    return
                end

                if dummy then
                    ngx.say("bad post-boundary line: ", dummy)
                    return
                end

                m = ngx.re.match(line, "--$", "jo")
                if m then
                    ngx.say("found the end of the stream")
                    sock:receive() -- consume the epiloque.
                    return
                end
            end

            while true do
                local line, err = read_line(50)
                if not line and err then
                    ngx.say("failed to read part ", i, " header: ", err)
                    return
                end

                if line then
                    local line, err = read_line(1)
                    if line or err then
                        ngx.say("error")
                        return
                    end
                end

                if line == "" then
                    -- the header part completes
                    break
                end

                ngx.say("part ", i, " header: [", line, "]")
            end

            local body = ""

            while true do
                local data, err, part = read_to_boundary(1)
                if data then
                    body = body .. data

                elseif err then
                    ngx.say("failed to read part ", i + 1, " boundary: ", err)
                    return

                else
                    break
                end
            end

            ngx.say("part ", i, " body: [" .. body .. "]")

            i = i + 1
        end
    }
--- stream_request eval
"This is the preamble.  It is to be ignored, though it
is a handy place for mail composers to include an
explanatory note to non-MIME compliant readers.\r
--simple boundary\r
\r
This is implicitly typed plain ASCII text.
It does NOT end with a linebreak.\r
--simple boundary\r
Content-type: text/plain; charset=us-ascii\r
\r
This is explicitly typed plain ASCII text.
It DOES end with a linebreak.
\r
--simple boundary--\r
This is the epilogue.  It is also to be ignored.
"
--- stream_response
got the request socket
preamble: [This is the preamble.  It is to be ignored, though it
is a handy place for mail composers to include an
explanatory note to non-MIME compliant readers.]
part 1 body: [This is implicitly typed plain ASCII text.
It does NOT end with a linebreak.]
part 2 header: [Content-type: text/plain; charset=us-ascii]
part 2 body: [This is explicitly typed plain ASCII text.
It DOES end with a linebreak.
]
found the end of the stream
--- no_error_log
[error]



=== TEST 4: attempt to use the req socket across request boundary
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        test.go()
        ngx.say("done")
    }
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



=== TEST 5: receive until on request_body - receiveuntil(1) on the last byte of the body
See https://groups.google.com/group/openresty/browse_thread/thread/43cf01da3c681aba for details
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        test.go()
    }
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

   ngx.say("done")
   ngx.flush(true)

   local res, err = sock:shutdown('send')
   if not res then
       ngx.log(ngx.ERR, "server: failed to shutdown: ", err)
       return
   end
end
--- stream_request
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



=== TEST 6: pipelined POST requests
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        local test = require "test"
        test.go()
        ngx.say("done")
    }
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

   for i = 1, 5 do
       local data, err, part = sock:receive(4)
       if data then
          ngx.say("received: ", data)
       else
          ngx.say("failed to receive: ", err, " [", part, "]")
          return
       end
   end
end
--- stream_request chomp
hello, worldhiya, wo
--- stream_response
got the request socket
received: hell
received: o, w
received: orld
received: hiya
received: , wo
done
--- no_error_log
[error]



=== TEST 7: pipelined requests, big buffer, small steps
--- stream_server_config
    lua_socket_buffer_size 5;
    content_by_lua_block {
        local sock, err = ngx.req.socket()
        if sock then
            ngx.say("got the request socket")
        else
            ngx.say("failed to get the request socket: ", err)
        end

        for i = 1, 11 do
            local data, err, part = sock:receive(2)
            if data then
                ngx.say("received: ", data)
            else
                ngx.say("failed to receive: ", err, " [", part, "]")
            end
        end
    }
--- stap2
M(http-lua-req-socket-consume-preread) {
    println("preread: ", user_string_n($arg2, $arg3))
}

--- stream_request chomp
hello world
hiya globe
--- stream_response
got the request socket
received: he
received: ll
received: o 
received: wo
received: rl
received: d

received: hi
received: ya
received:  g
received: lo
received: be
--- no_error_log
[error]



=== TEST 8: failing reread after reading timeout happens
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket()

        if not sock then
           ngx.say("failed to get socket: ", err)
           return nil
        end

        sock:settimeout(100);

        local data, err, partial = sock:receive(4096)
        if err then
           ngx.say("err: ", err, ", partial: ", partial)
        end

        local data, err, partial = sock:receive(4096)
        if err then
           ngx.say("err: ", err, ", partial: ", partial)
           return
        end
    }

--- stream_request chomp
hello
--- stream_response
err: timeout, partial: hello
err: timeout, partial: 

--- error_log
stream lua tcp socket read timed out



=== TEST 9: successful reread after reading timeout happens (receive -> receive)
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        local bytes, err = sock:send("POST /back HTTP/1.0\r\nHost: localhost\r\nContent-Length: 1024\r\n\r\nabc")
        if not bytes then
            ngx.say("failed to send: ", err)
        else
            ngx.say("sent: ", bytes)
        end

        ngx.sleep(0.2)

        local bytes, err = sock:send("hello world")
        if not bytes then
            ngx.say("failed to send: ", err)
        else
            ngx.say("sent: ", bytes)
        end

        local reader = sock:receiveuntil("\r\n\r\n")
        local header, err = reader()
        if not header then
            ngx.say("failed to receive header: ", err)
            return
        end

        for i = 1, 2 do
            local line, err = sock:receive()
            if not line then
                ngx.say("failed to receive line: ", err)
                return
            end
            ngx.say("received: ", line)
        end
    }

--- config
    location = /back {
        lua_socket_log_errors on;
        content_by_lua_block {
            ngx.send_headers()
            ngx.flush(true)

            local sock, err = ngx.req.socket()

            if not sock then
               ngx.say("failed to get socket: ", err)
               return nil
            end

            sock:settimeout(100);

            local data, err, partial = sock:receive(4096)
            if err then
                ngx.log(ngx.ERR, "err: ", err)
                ngx.say("err: ", err, ", partial: ", partial)
            else
                ngx.say("received: ", data)
            end

            ngx.sleep(0.1)

            local data, err, partial = sock:receive(11)
            if err then
               ngx.say("err: ", err, ", partial: ", partial)
            else
                ngx.say("received: ", data)
            end
        }
    }

--- stream_response
sent: 65
sent: 11
received: err: timeout, partial: abc
received: received: hello world

--- error_log
lua tcp socket read timed out



=== TEST 10: successful reread after reading timeout happens (receive -> receiveuntil)
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        local bytes, err = sock:send("POST /back HTTP/1.0\r\nHost: localhost\r\nContent-Length: 1024\r\n\r\nabc")
        if not bytes then
            ngx.say("failed to send: ", err)
        else
            ngx.say("sent: ", bytes)
        end

        ngx.sleep(0.2)

        local bytes, err = sock:send("hello world\n")
        if not bytes then
            ngx.say("failed to send: ", err)
        else
            ngx.say("sent: ", bytes)
        end

        local reader = sock:receiveuntil("\r\n\r\n")
        local header, err = reader()
        if not header then
            ngx.say("failed to receive header: ", err)
            return
        end

        for i = 1, 2 do
            local line, err = sock:receive()
            if not line then
                ngx.say("failed to receive line: ", err)
                return
            end
            ngx.say("received: ", line)
        end
    }

--- config
    location = /back {
        lua_socket_log_errors on;
        content_by_lua_block {
            ngx.send_headers()
            ngx.flush(true)

            local sock, err = ngx.req.socket()

            if not sock then
               ngx.say("failed to get socket: ", err)
               return nil
            end

            sock:settimeout(100);

            local data, err, partial = sock:receive(4096)
            if err then
               ngx.say("err: ", err, ", partial: ", partial)
            else
                ngx.say("received: ", data)
            end

            ngx.sleep(0.1)

            local reader = sock:receiveuntil("\n")
            local data, err, partial = reader()
            if err then
               ngx.say("err: ", err, ", partial: ", partial)
            else
                ngx.say("received: ", data)
            end
        }
    }

--- stream_response
sent: 65
sent: 12
received: err: timeout, partial: abc
received: received: hello world

--- error_log
lua tcp socket read timed out



=== TEST 11: successful reread after reading timeout happens (receiveuntil -> receive)
--- stream_server_config
    content_by_lua_block {
        local sock = ngx.socket.tcp()
        local ok, err = sock:connect("127.0.0.1", $TEST_NGINX_SERVER_PORT)
        if not ok then
            ngx.say("failed to connect: ", err)
            return
        end

        local bytes, err = sock:send("POST /back HTTP/1.0\r\nHost: localhost\r\nContent-Length: 1024\r\n\r\nabc")
        if not bytes then
            ngx.say("failed to send: ", err)
        else
            ngx.say("sent: ", bytes)
        end

        ngx.sleep(0.2)

        local bytes, err = sock:send("hello world\n")
        if not bytes then
            ngx.say("failed to send: ", err)
        else
            ngx.say("sent: ", bytes)
        end

        local reader = sock:receiveuntil("\r\n\r\n")
        local header, err = reader()
        if not header then
            ngx.say("failed to receive header: ", err)
            return
        end

        for i = 1, 2 do
            local line, err = sock:receive()
            if not line then
                ngx.say("failed to receive line: ", err)
                return
            end
            ngx.say("received: ", line)
        end
    }

--- config
    location = /back {
        lua_socket_log_errors on;
        content_by_lua_block {
            ngx.send_headers()
            ngx.flush(true)

            local sock, err = ngx.req.socket()

            if not sock then
               ngx.say("failed to get socket: ", err)
               return nil
            end

            sock:settimeout(100);

            local reader = sock:receiveuntil("no-such-terminator")
            local data, err, partial = reader()
            if not data then
               ngx.say("err: ", err, ", partial: ", partial)
            else
                ngx.say("received: ", data)
            end

            ngx.sleep(0.1)

            local data, err, partial = sock:receive()
            if err then
               ngx.say("err: ", err, ", partial: ", partial)
            else
                ngx.say("received: ", data)
            end
        }
    }

--- stream_response
sent: 65
sent: 12
received: err: timeout, partial: abc
received: received: hello world

--- error_log
lua tcp socket read timed out



=== TEST 12: req socket GC'd
--- stream_server_config
    content_by_lua_block {
        do
            local sock, err = ngx.req.socket()
            if sock then
                ngx.say("got the request socket")
            else
                ngx.say("failed to get the request socket: ", err)
            end
        end
        collectgarbage()
        ngx.log(ngx.WARN, "GC cycle done")

        ngx.say("done")
    }
--- stream_response
got the request socket
done
--- no_error_log
[error]
--- grep_error_log eval: qr/stream lua finalize socket|GC cycle done/
--- grep_error_log_out
stream lua finalize socket
GC cycle done



=== TEST 13: sanity of raw req socket receive any
--- stream_server_config

    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end
        ngx.log(ngx.INFO, "Got raw req socket")
        local data, err = sock:receiveany(500)
        if not data then
            ngx.log(ngx.ERR, "server: failed to receive: ", err)
            return
        end
        ngx.log(ngx.INFO, "Got: ", #data, " bytes")

        local bytes, err = sock:send("1: received: " .. data .. "\n")
        if not bytes then
            ngx.log(ngx.ERR, "server: failed to send: ", err)
            return
        end
    }

--- stream_request: hello
--- stream_response
1: received: hello
--- no_error_log
stream lua socket tcp_nodelay
[error]
--- error_log
Got raw req socket
Got: 5 bytes



=== TEST 14: receiveany small block size for a big size block
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end
        sock:settimeouts(500, 100, 500)
        ngx.sleep(0.2)
        ngx.log(ngx.INFO, 'receiveany every 3 bytes per read ...')
        local i = 0
        while true do
            i = i + 1
            ngx.log(ngx.INFO, 'reading: ', i)
            local data, err = sock:receiveany(3)
            if not data then
                if err == 'closed' then
                    ngx.log(ngx.INFO, 'client closed')
                    break
                end
                if err == 'timeout' then
                    ngx.log(ngx.INFO, 'client timeout, considered as closed')
                    break
                end
                ngx.log(ngx.ERR, 'server receiveany error: ', err)
                break
            end
            if i == 1 then
                ngx.log(ngx.INFO, 'send back ok ...')
                local ok, err = sock:send("ok\n")
                if not ok then
                    ngx.log(ngx.ERR, "failed to send: ", err)
                    return
                end
            end
            ngx.log(ngx.INFO, "Time ", i, " - got ", #data, " bytes: ", data)
            sock:send("receive: " .. data .. "\n")
        end
    }

--- stream_request: hello, stream receiveany!
--- stream_response
ok
receive: hel
receive: lo,
receive:  st
receive: rea
receive: m r
receive: ece
receive: ive
receive: any
receive: !
--- no_error_log
receiveany error: 
--- error_log
read timed out
client timeout



=== TEST 15: receiveany with limited, max <= 0
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if sock == nil then
            ngx.log(ngx.ERR, 'raw req socket error: ', err)
            return
        end
        sock:settimeouts(500, 500, 500)

        local function receiveany_log_err(...)
            local ok, err = pcall(sock.receiveany, sock, ...)
            if not ok then
                ngx.log(ngx.ERR, 'failed receiveany ', err)
            end
        end


        receiveany_log_err(0)
        receiveany_log_err(-1)
        receiveany_log_err(100, 200)
        receiveany_log_err()
        receiveany_log_err(nil)
    }
--- error_log
bad argument #2 to '?' (bad max argument)
bad argument #2 to '?' (bad max argument)
expecting 2 arguments (including the object), but got 3
expecting 2 arguments (including the object), but got 1
bad argument #2 to '?' (bad max argument)



=== TEST 16: receiveany send data after read side timeout
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if sock == nil then
            ngx.log(ngx.ERR, 'failed to get raw req socket', err)
            return
        end
        sock:settimeouts(500, 500, 500)

        local data, err, bytes
        while true do
            data, err = sock:receiveany(1024)
            if err then
                if err ~= 'closed' then
                    ngx.log(ngx.ERR, 'receiveany unexpected err: ', err)
                    break
                end

                data = "send data after read side closed"
                bytes, err = sock:send(data)
                if not bytes then
                    ngx.log(ngx.ERR, 'failed to send after error ',err)
                end

                break
            end
            ngx.say(data)
        end

        local bytes, err2 = sock:send("send data after read side ")
        if not bytes then
            ngx.log(ngx.ERR, "failed to send: ", err2)
        end

        local bytes, err2 = sock:send(err)
        if not bytes then
            ngx.log(ngx.ERR, "failed to send: ", err2)
        end
    }
--- stream_response chomp
send data after read side timeout
--- error_log
receiveany unexpected err: timeout
