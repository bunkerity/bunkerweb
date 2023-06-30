# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Dgram;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 1);

our $HtmlDir = html_dir;

#$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;

no_long_string();
#no_diff();
#log_level 'warn';
no_shuffle();

run_tests();

__DATA__

=== TEST 1: sanity
--- dgram_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket()
        if not sock then
            ngx.log(ngx.ERR, "failed to get the request socket: ", err)
            return ngx.exit(ngx.ERROR)
        end

        local data, err = sock:receive()
        if not data then
            ngx.log(ngx.ERR, "failed to receive: ", err)
            return ngx.exit(ngx.ERROR)
        end

        -- print("data: ", data)

        local ok, err = sock:send("received: " .. data)
        if not ok then
            ngx.log(ngx.ERR, "failed to send: ", err)
            return ngx.exit(ngx.ERROR)
        end
    }
--- dgram_request chomp
hello world! my
--- dgram_response chomp
received: hello world! my
--- no_error_log
[error]



=== TEST 2: pipelined POST requests
--- dgram_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- dgram_server_config
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
      ngx.ctx.sock = sock
   else
      sock:send("failed to get the request socket: ", err)
      return
   end

   local resp = "got the request socket\n"

   for i = 1, 5 do
       local data, err, part = sock:receive(4)
       if data then
          resp = resp .. "received: " .. data .. "\n"
       else
          resp = resp .. "failed to receive: " .. err .. " [" .. part .. "]" .. "\n"
          return
       end
   end

   sock:send(resp)
end
--- dgram_request chomp
hello, worldhiya, wo
--- dgram_response
got the request socket
received: hell
received: o, w
received: orld
received: hiya
received: , wo
--- no_error_log
[error]



=== TEST 3: pipelined requests, big buffer, small steps
--- dgram_server_config
    lua_socket_buffer_size 5;
    content_by_lua_block {
        local resp = ""

        local sock, err = ngx.req.socket()
        if sock then
            resp = "got the request socket\n"
        else
            resp = "failed to get the request socket: " .. err .. "\n"
        end

        for i = 1, 11 do
            local data, err, part = sock:receive(2)
            if data then
                resp = resp .. "received: " .. data .. "\n"
            else
                resp = resp .. "failed to receive: " .. err .. " [" .. part .. "]" .. "\n"
            end
        end

        sock:send(resp)
    }
--- stap2
M(http-lua-req-socket-consume-preread) {
    println("preread: ", user_string_n($arg2, $arg3))
}

--- dgram_request chomp
hello world
hiya globe
--- dgram_response
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



=== TEST 4: failing reread after reading timeout happens
--- dgram_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket()
        local resp = ""

        if not sock then
           resp = "failed to get socket: " .. err
           sock:send(resp)

           return nil
        end

        local data, err, partial = sock:receive(4096)
        if data then
           resp = resp .. "data: " .. (data or "nil") .. ", err: " .. (err or "nil") .. ", partial: " .. (partial or "nil") .. "\n"
        end

        local data, err, partial = sock:receive(4096)
        if err then
           resp = resp .. "data: " .. (data or "nil") .. ", err: " .. (err or "nil") .. ", partial: " .. (partial or "nil") .. "\n"
        end

        sock:send(resp)
    }

--- dgram_request chomp
hello
--- dgram_response
data: hello, err: nil, partial: nil
data: nil, err: no more data, partial: nil

--- no_error_log
[error]



=== TEST 5: req socket GC'd
--- dgram_server_config
    content_by_lua_block {
        do
            local sock, err = ngx.req.socket()
            if sock then
                sock:send("got the request socket")
            else
                sock:send("failed to get the request socket: ", err)
            end
        end
        collectgarbage()
        ngx.log(ngx.WARN, "GC cycle done")

    }
--- dgram_response chomp
got the request socket
--- no_error_log
[error]
--- grep_error_log eval: qr/stream lua finalize socket|GC cycle done/
--- grep_error_log_out
stream lua finalize socket
GC cycle done



=== TEST 6: ngx.req.socket with raw argument, argument is ignored
--- dgram_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket(true)
        if not sock then
            ngx.log(ngx.ERR, "failed to get the request socket: ", err)
            return ngx.exit(ngx.ERROR)
        end

        local data, err = sock:receive()
        if not data then
            ngx.log(ngx.ERR, "failed to receive: ", err)
            return ngx.exit(ngx.ERROR)
        end

        -- print("data: ", data)

        local ok, err = sock:send("received: " .. data)
        if not ok then
            ngx.log(ngx.ERR, "failed to send: ", err)
            return ngx.exit(ngx.ERROR)
        end
    }
--- dgram_request chomp
hello world! my
--- dgram_response chomp
received: hello world! my
--- no_error_log
[error]



=== TEST 7: request on secondary ip address
sudo ip addr add 10.254.254.1/24 dev lo
sudo ip addr add 10.254.254.2/24 dev lo
nmap will be blocked by travis , use dig to send dns request.
--- dgram_server_config
    content_by_lua_block {
        local sock, err = ngx.req.socket()
        if not sock then
            ngx.log(ngx.ERR,"ngx.req.socket error : ", err)
            return ngx.exit(ngx.ERROR)
        end

        local data = sock:receive()
        local ok, err = sock:send(data)
        if not ok then
            ngx.log(ngx.ERR, "failed to send: ", err)
            return ngx.exit(ngx.ERROR)
        end
    }
--- config
     location = /dns {
         content_by_lua_block {
            local cmd = "dig -b 10.254.254.1 @10.254.254.2 openresty.org -p " .. tostring(ngx.var.server_port + 1)
            local f = io.popen(cmd, "r")
            ngx.sleep(0.2)
            local result = f:read("*a")
            f:close()
            ngx.say("hello")
         }
     }
--- request
GET /dns
--- response_body
hello
--- grep_error_log eval: qr/sendto: fd.*$/
--- grep_error_log_out eval
qr/sendto: fd:\d+ \d+ of \d+ to "10.254.254.1"/
