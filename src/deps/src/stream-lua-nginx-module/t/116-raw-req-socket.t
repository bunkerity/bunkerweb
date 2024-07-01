# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

repeat_each(2);

plan tests => repeat_each() * 49;

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
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end

        local data, err = sock:receive(5)
        if not data then
            ngx.log(ngx.ERR, "server: failed to receive: ", err)
            return
        end

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



=== TEST 2: multiple raw req sockets
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end
        local sock2, err = ngx.req.socket(true)
        if not sock2 then
            ngx.log(ngx.ERR, "server: failed to get raw req socket2: ", err)
            return
        end

    }

--- stap2
F(ngx_stream_header_filter) {
    println("header filter")
}
F(ngx_stream_lua_req_socket) {
    println("lua req socket")
}
--- stream_response
--- error_log
server: failed to get raw req socket2: duplicate call



=== TEST 3: ngx.say after ngx.req.socket(true)
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end
        local ok, err = ngx.say("ok")
        if not ok then
            ngx.log(ngx.ERR, "failed to say: ", err)
            return
        end
    }

--- stream_response
ok
--- no_error_log
[error]



=== TEST 4: ngx.print after ngx.req.socket(true)
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end
        local ok, err = ngx.print("ok")
        if not ok then
            ngx.log(ngx.ERR, "failed to print: ", err)
            return
        end
    }

--- stream_response chomp
ok
--- no_error_log
[error]



=== TEST 5: ngx.eof after ngx.req.socket(true)
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end
        local ok, err = ngx.eof()
        if not ok then
            ngx.log(ngx.ERR, "failed to eof: ", err)
            return
        end
    }

--- config
    server_tokens off;

--- stream_response
--- no_error_log
[error]



=== TEST 6: ngx.flush after ngx.req.socket(true)
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end
        local ok, err = ngx.flush()
        if not ok then
            ngx.log(ngx.ERR, "failed to flush: ", err)
            return
        end
    }

--- stream_response
--- no_error_log
[error]



=== TEST 7: receive timeout
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end

        sock:settimeout(100)

        local data, err, partial = sock:receive(10)
        if not data then
            ngx.log(ngx.ERR, "server: 1: failed to receive: ", err, ", received: ", partial)
        end

        data, err, partial = sock:receive(10)
        if not data then
            ngx.log(ngx.ERR, "server: 2: failed to receive: ", err, ", received: ", partial)
        end

        ngx.exit(444)
    }

--- stream_request chomp
ab
--- stream_response
--- wait: 0.1
--- error_log
stream lua tcp socket read timed out
server: 1: failed to receive: timeout, received: ab
server: 2: failed to receive: timeout, received: 
--- no_error_log
[alert]



=== TEST 8: on_abort called during ngx.sleep()
--- stream_server_config
    lua_check_client_abort on;

    content_by_lua_block {
        local ok, err = ngx.on_abort(function (premature)
            ngx.log(ngx.WARN, "mysock handler aborted") end)
        if not ok then
            ngx.log(ngx.ERR, "failed to set on_abort handler: ", err)
            return
        end

        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end

        local data, err = sock:receive(5)
        if not data then
            ngx.log(ngx.ERR, "server: failed to receive: ", err)
            return
        end

        print("msg received: ", data)

        local bytes, err = sock:send("1: received: " .. data .. "\n")
        if not bytes then
            ngx.log(ngx.ERR, "server: failed to send: ", err)
            return
        end

        ngx.sleep(1)
    }

--- stream_request chomp
hello
--- stream_response
receive stream response error: timeout
--- abort
--- timeout: 0.2
--- error_log
mysock handler aborted
msg received: hello
--- no_error_log
[error]
--- wait: 1.1



=== TEST 9: on_abort called during sock:receive()
--- stream_server_config
    lua_check_client_abort on;

    content_by_lua_block {
        local ok, err = ngx.on_abort(function (premature) ngx.log(ngx.WARN, "mysock handler aborted") end)
        if not ok then
            ngx.log(ngx.ERR, "failed to set on_abort handler: ", err)
            return
        end

        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end

        local data, err = sock:receive(5)
        if not data then
            ngx.log(ngx.ERR, "server: failed to receive: ", err)
            return
        end

        print("msg received: ", data)

        local bytes, err = sock:send("1: received: " .. data .. "\n")
        if not bytes then
            ngx.log(ngx.ERR, "server: failed to send: ", err)
            return
        end

        local data, err = sock:receive()
        if not data then
            ngx.log(ngx.WARN, "failed to receive a line: ", err)
            return
        end
    }

--- stream_response
receive stream response error: timeout
--- timeout: 0.2
--- abort
--- error_log
server: failed to receive: client aborted
--- wait: 0.1



=== TEST 10: receiveuntil
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end

        local reader = sock:receiveuntil("rld")
        local data, err = reader()
        if not data then
            ngx.log(ngx.ERR, "server: failed to receive: ", err)
            return
        end

        local bytes, err = sock:send("1: received: " .. data .. "\n")
        if not bytes then
            ngx.log(ngx.ERR, "server: failed to send: ", err)
            return
        end

        local LINGERING_TIME = 30 -- 30 seconds
        local LINGERING_TIMEOUT = 5000 -- 5 seconds

        local ok, err = sock:shutdown("send")
        if not ok then
            ngx.log(ngx.ERR, "failed to shutdown ", err)
            return
        end

        local deadline = ngx.time() + LINGERING_TIME

        sock:settimeouts(nil, nil, LINGERING_TIMEOUT)

        repeat
            local data, _, partial = sock:receive(1024)
        until (not data and not partial) or ngx.time() >= deadline
    }

--- stream_request
hello, world
--- stream_response
1: received: hello, wo
--- error_log
stream lua shutdown socket write direction
attempt to receive data on a closed socket



=== TEST 11: request body not read yet
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end

        local data, err = sock:receive(5)
        if not data then
            ngx.log(ngx.ERR, "failed to receive: ", err)
            return
        end

        local ok, err = sock:send("HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\n" .. data)
        if not ok then
            ngx.log(ngx.ERR, "failed to send: ", err)
            return
        end

        local res, err = sock:shutdown('send')
        if not res then
            ngx.log(ngx.ERR, "server: failed to shutdown: ", err)
            return
        end
    }

--- stream_request
hello
--- stream_response eval
"HTTP/1.1 200 OK\r
Content-Length: 5\r
\r
hello"

--- no_error_log
[error]



=== TEST 12: read chunked request body with raw req socket
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "failed to new: ", err)
            return
        end
        local function myerr(...)
            ngx.log(ngx.ERR, ...)
            return ngx.exit(400)
        end
        local num = tonumber
        local MAX_CHUNKS = 1000
        local eof = false
        local chunks = {}
        for i = 1, MAX_CHUNKS do
            local line, err = sock:receive()
            if not line then
                myerr("failed to receive chunk size: ", err)
            end

            local size = num(line, 16)
            if not size then
                myerr("bad chunk size: ", line)
            end

            if size == 0 then -- last chunk
                -- receive the last line
                line, err = sock:receive()
                if not line then
                    myerr("failed to receive last chunk: ", err)
                end

                if line ~= "" then
                    myerr("bad last chunk: ", line)
                end

                eof = true
                break
            end

            local chunk, err = sock:receive(size)
            if not chunk then
                myerr("failed to receive chunk of size ", size, ": ", err)
            end

            local data, err = sock:receive(2)
            if not data then
                myerr("failed to receive chunk terminator: ", err)
            end

            if data ~= "\r\n" then
                myerr("bad chunk terminator: ", data)
            end

            chunks[i] = chunk
        end

        if not eof then
            myerr("too many chunks (more than ", MAX_CHUNKS, ")")
        end

        local concat = table.concat
        local body = concat{"got ", #chunks, " chunks.\nrequest body: "}
                     .. concat(chunks) .. "\n"
        local ok, err = sock:send(body)
        if not ok then
            myerr("failed to send response: ", err)
        end
    }

--- config
--- stream_request eval
"5\r
hey, \r
b\r
hello world\r
0\r
\r
"
--- stream_response
got 2 chunks.
request body: hey, hello world

--- no_error_log
[error]
[alert]



=== TEST 13: shutdown can only be called once and prevents all further output
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end

        local data, err = sock:receive(5)
        if not data then
            ngx.log(ngx.ERR, "failed to receive: ", err)
            return
        end

        local ok, err = sock:send("it works\n")
        if not ok then
            ngx.log(ngx.ERR, "failed to send: ", err)
            return
        end

        local ok, err = sock:shutdown("send")
        if not ok then
            ngx.log(ngx.ERR, "failed to shutdown ", err)
            return
        end

        ok, err = sock:shutdown("send")
        if ok or err ~= "already shutdown" then
            ngx.log(ngx.ERR, "shutdown called multiple times without proper error: ", err)
            return
        end

        ok, err = ngx.say("this should not work")
        if ok or err ~= "seen eof" then
            ngx.log(ngx.ERR, "ngx.say completed without proper error: ", err)
            return
        end

        ok, err = sock:send("this should not work")
        if ok or err ~= "closed" then
            ngx.log(ngx.ERR, "sock:send completed without proper error: ", err)
            return
        end
    }

--- stream_request
hello
--- stream_response
it works
--- error_log
stream lua shutdown socket write direction



=== TEST 14: simulated lingering close
--- stream_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "server: failed to get raw req socket: ", err)
            return
        end

        local data, err = sock:receive(5)
        if not data then
            ngx.log(ngx.ERR, "failed to receive: ", err)
            return
        end

        local ok, err = sock:shutdown("send")
        if not ok then
            ngx.log(ngx.ERR, "failed to shutdown ", err)
            return
        end

        sock:settimeouts(nil, nil, 5000)

        repeat
            local data = sock:receive(1024)
        until not data
    }

--- stream_request
1234567890
--- error_log
stream lua shutdown socket write direction
