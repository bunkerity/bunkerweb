# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;
repeat_each(2);

plan tests => repeat_each() * (blocks() * 5);

our $HtmlDir = html_dir;

$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;
$ENV{TEST_NGINX_HTML_DIR} = $HtmlDir;
#$ENV{TEST_NGINX_REDIS_PORT} ||= 6379;

$ENV{LUA_PATH} ||=
    '/usr/local/openresty-debug/lualib/?.lua;/usr/local/openresty/lualib/?.lua;;';

no_long_string();
#no_diff();
#log_level 'warn';

no_shuffle();

run_tests();

__DATA__

=== TEST 1: sanity
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    preread_by_lua_block {
        local test = require "test"
        local port = $TEST_NGINX_MEMCACHED_PORT
        test.go(port)
        test.go(port)
    }
    content_by_lua return;
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

    local ok, err = sock:setkeepalive()
    if not ok then
        ngx.say("failed to set reusable: ", err)
    end
end
--- stream_response_like
^connected: 1, reused: \d+
request sent: 11
received: OK
connected: 1, reused: [1-9]\d*
request sent: 11
received: OK
--- no_error_log eval
["[error]",
"lua tcp socket keepalive: free connection pool for "]
--- grep_error_log eval
qr/lua tcp socket get keepalive peer: using connection|lua tcp socket keepalive create connection pool for key "[^"]+"/

--- grep_error_log_out eval
[
qq{lua tcp socket keepalive create connection pool for key "127.0.0.1:$ENV{TEST_NGINX_MEMCACHED_PORT}"
lua tcp socket get keepalive peer: using connection
},
"lua tcp socket get keepalive peer: using connection
lua tcp socket get keepalive peer: using connection
"]



=== TEST 2: free up the whole connection pool if no active connections
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    preread_by_lua_block {
        local test = require "test"
        local port = $TEST_NGINX_MEMCACHED_PORT
        test.go(port, true)
        test.go(port, false)
    }

    content_by_lua return;
--- user_files
>>> test.lua
module("test", package.seeall)

function go(port, keepalive)
    local sock = ngx.socket.tcp()
    local ok, err = sock:connect("127.0.0.1", port)
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

    if keepalive then
        local ok, err = sock:setkeepalive()
        if not ok then
            ngx.say("failed to set reusable: ", err)
        end

    else
        sock:close()
    end
end
--- stream_response_like
^connected: 1, reused: \d+
request sent: 11
received: OK
connected: 1, reused: [1-9]\d*
request sent: 11
received: OK
--- no_error_log
[error]
--- error_log eval
["lua tcp socket get keepalive peer: using connection",
"lua tcp socket keepalive: free connection pool for "]
