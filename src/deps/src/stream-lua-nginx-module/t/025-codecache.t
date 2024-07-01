# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

repeat_each(2);

plan tests => repeat_each() * 140;

#$ENV{LUA_PATH} = $ENV{HOME} . '/work/JSON4Lua-0.9.30/json/?.lua';

no_long_string();

our $HtmlDir = html_dir;

$ENV{TEST_NGINX_HTML_DIR} = $HtmlDir;
$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;

check_accum_error_log();
run_tests();

__DATA__

=== TEST 1: code cache on by default
--- stream_server_config
    content_by_lua_file html/test.lua;

--- stream_server_config2
    content_by_lua_block {
        -- os.execute("(echo HERE; pwd) > /dev/stderr")
        local f = assert(io.open("$TEST_NGINX_SERVER_ROOT/html/test.lua", "w"))
        f:write("ngx.say(101)")
        f:close()
        ngx.say("updated")
    }

--- stream_server_config3
    content_by_lua_file html/test.lua;

--- user_files
>>> test.lua
ngx.say(32)
--- stream_response
32
updated
32
--- no_error_log
[alert]
[error]



=== TEST 2: code cache explicitly on
--- stream_config
    lua_code_cache on;

--- stream_server_config
    content_by_lua_file html/test.lua;

--- stream_server_config2
    content_by_lua_block {
        -- os.execute("(echo HERE; pwd) > /dev/stderr")
        local f = assert(io.open("$TEST_NGINX_SERVER_ROOT/html/test.lua", "w"))
        f:write("ngx.say(101)")
        f:close()
        ngx.say("updated")
    }

--- stream_server_config3
    content_by_lua_file html/test.lua;

--- user_files
>>> test.lua
ngx.say(32)
--- stream_response
32
updated
32
--- no_error_log
[alert]
[error]



=== TEST 3: code cache explicitly off
--- stream_server_config
    lua_code_cache off;
    content_by_lua_file html/test.lua;

--- stream_server_config2
    content_by_lua_block {
        -- os.execute("(echo HERE; pwd) > /dev/stderr")
        local f = assert(io.open("$TEST_NGINX_SERVER_ROOT/html/test.lua", "w"))
        f:write("ngx.say(101)")
        f:close()
        ngx.say("updated")
    }

--- stream_server_config3
    lua_code_cache off;
    content_by_lua_file html/test.lua;

--- user_files
>>> test.lua
ngx.say(32)
--- stream_response
32
updated
101
--- no_error_log
[error]
--- error_log eval
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/



=== TEST 4: code cache explicitly off (stream {} level)
--- stream_config
    lua_code_cache off;

--- stream_server_config
    content_by_lua_file html/test.lua;

--- stream_server_config2
    content_by_lua_block {
        -- os.execute("(echo HERE; pwd) > /dev/stderr")
        local f = assert(io.open("$TEST_NGINX_SERVER_ROOT/html/test.lua", "w"))
        f:write("ngx.say(101)")
        f:close()
        ngx.say("updated")
    }

--- stream_server_config3
    content_by_lua_file html/test.lua;

--- user_files
>>> test.lua
ngx.say(32)

--- stream_response
32
updated
101
--- error_log eval
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/



=== TEST 5: code cache explicitly off (server level) but be overridden in the location
--- stream_config
    lua_code_cache off;

--- stream_server_config
    lua_code_cache on;
    content_by_lua_file html/test.lua;

--- stream_server_config2
    content_by_lua_block {
        -- os.execute("(echo HERE; pwd) > /dev/stderr")
        local f = assert(io.open("$TEST_NGINX_SERVER_ROOT/html/test.lua", "w"))
        f:write("ngx.say(101)")
        f:close()
        ngx.say("updated")
    }

--- stream_server_config3
    lua_code_cache on;
    content_by_lua_file html/test.lua;

--- user_files
>>> test.lua
ngx.say(32)
--- stream_response
32
updated
32
--- error_log eval
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/



=== TEST 6: code cache explicitly off (affects require) + content_by_lua
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';
    lua_code_cache off;"

--- stream_server_config
    content_by_lua_block {
        local foo = require "foo";
    }

--- stream_server_config2
    content_by_lua_block {
        -- os.execute("(echo HERE; pwd) > /dev/stderr")
        local f = assert(io.open("$TEST_NGINX_SERVER_ROOT/html/foo.lua", "w"))
        f:write("module(..., package.seeall); ngx.say(102);")
        f:close()
        ngx.say("updated")
    }

--- stream_server_config3
    content_by_lua_block {
        local foo = require "foo";
    }

--- user_files
>>> foo.lua
module(..., package.seeall); ngx.say(32);

--- stream_response
32
updated
102
--- error_log eval
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/



=== TEST 7: code cache explicitly off (affects require) + content_by_lua_file
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';
    lua_code_cache off;"

--- stream_server_config
    content_by_lua_file html/test.lua;

--- stream_server_config2
    content_by_lua_block {
        -- os.execute("(echo HERE; pwd) > /dev/stderr")
        local f = assert(io.open("$TEST_NGINX_SERVER_ROOT/html/foo.lua", "w"))
        f:write("module(..., package.seeall); ngx.say(102);")
        f:close()
        ngx.say("updated")
    }

--- stream_server_config3
    content_by_lua_file html/test.lua;

--- user_files
>>> test.lua
local foo = require "foo";
>>> foo.lua
module(..., package.seeall); ngx.say(32);
--- stream_response
32
updated
102
--- error_log eval
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/



=== TEST 8: no clear builtin lib "string" (file)
--- stream_server_config
    lua_code_cache off;
    content_by_lua_file html/test.lua;

--- stream_server_config2
    lua_code_cache off;
    content_by_lua_file html/test.lua;

--- user_files
>>> test.lua
ngx.say(string.len("hello"))
ngx.say(table.concat({1,2,3}, ", "))
--- stream_response
5
1, 2, 3
5
1, 2, 3
--- error_log eval
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/



=== TEST 9: no clear builtin lib "string" (inline)
--- stream_server_config
    lua_code_cache off;
    content_by_lua_block {
        ngx.say(string.len("hello"))
        ngx.say(table.concat({1,2,3}, ", "))
    }

--- stream_server_config2
    lua_code_cache off;
    content_by_lua_block {
        ngx.say(string.len("hello"))
        ngx.say(table.concat({1,2,3}, ", "))
    }

--- stream_response
5
1, 2, 3
5
1, 2, 3
--- error_log eval
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/



=== TEST 10: no clear builtin libs (misc)
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"

--- stream_server_config
    lua_code_cache off;
    content_by_lua_block {
        local test = require("test")
    }

--- stream_server_config2
    lua_code_cache off;
    content_by_lua_block {
        local test = require("test")
    }

--- user_files
>>> test.lua
module("test", package.seeall)

string = require("string")
math = require("math")
io = require("io")
os = require("os")
table = require("table")
coroutine = require("coroutine")
package = require("package")
ngx.say("OK")
--- stream_response
OK
OK
--- error_log eval
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/



=== TEST 11: do not skip luarocks
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';
     lua_code_cache off;"

--- stream_server_config
    content_by_lua_block {
        package.loaded.luarocks = nil;
        local foo = require "luarocks";
        foo.hi()
    }

--- stream_server_config2
    content_by_lua_block {
        local foo = package.loaded.luarocks
        if foo then
            ngx.say("found")
        else
            ngx.say("not found")
        end
    }

--- stream_server_config3
    content_by_lua_block {
        local foo = package.loaded.luarocks
        if foo then
            ngx.say("found")
        else
            ngx.say("not found")
        end
    }

--- user_files
>>> luarocks.lua
module(..., package.seeall);

ngx.say("loading");

function hi ()
    ngx.say("hello, foo")
end;
--- stream_response
loading
hello, foo
not found
not found
--- error_log eval
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/



=== TEST 12: do not skip luarocks*
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';
     lua_code_cache off;"
--- stream_server_config

    content_by_lua_block {
        package.loaded.luarocks2 = nil;
        local foo = require "luarocks2";
        foo.hi()
    }

--- stream_server_config2

    content_by_lua_block {
        local foo = package.loaded.luarocks2
        if foo then
            ngx.say("found")
        else
            ngx.say("not found")
        end
    }

--- stream_server_config3

    content_by_lua_block {
        local foo = package.loaded.luarocks2
        if foo then
            ngx.say("found")
        else
            ngx.say("not found")
        end
    }

--- user_files
>>> luarocks2.lua
module(..., package.seeall);

ngx.say("loading");

function hi ()
    ngx.say("hello, foo")
end;
--- stream_response
loading
hello, foo
not found
not found
--- error_log eval
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/



=== TEST 13: clear _G table
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    lua_code_cache off;
    content_by_lua_block {
        if not _G.foo then
            _G.foo = 1
        else
            _G.foo = _G.foo + 1
        end
        ngx.say("_G.foo: ", _G.foo)
    }
--- stream_response
_G.foo: 1
--- error_log eval
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/



=== TEST 14: github #257: globals cleared when code cache off
--- stream_config
    lua_code_cache off;
    init_by_lua_block {
      test = setfenv(
        function()
          ngx.say(tostring(table))
        end,
        setmetatable({},
        {
          __index = function(self, key)
              return rawget(self, key) or _G[key]
          end
        }))
    }
--- stream_server_config
    content_by_lua_block { test() }

--- stream_response_like chop
^table: 0x\d*?[1-9a-fA-F]
--- no_error_log
[error]
--- error_log eval
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/



=== TEST 15: lua_code_cache off + FFI-based Lua modules
--- stream_config
    lua_code_cache off;
    lua_package_path "$prefix/html/?.lua;;";

--- stream_server_config
    content_by_lua_block {
        if not jit then
            ngx.say("skipped for non-LuaJIT")
        else
            local test = require("test")
            ngx.say("test module loaded: ", test and true or false)
            collectgarbage()
        end
    }
--- user_files
>>> test.lua
local ffi = require "ffi"

ffi.cdef[[
    int my_test_function_here(void *p);
    int my_test_function_here2(void *p);
    int my_test_function_here3(void *p);
]]

return {
}
--- stream_response_like chop
^(?:skipped for non-LuaJIT|test module loaded: true)$
--- no_error_log
[error]
--- error_log eval
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/



=== TEST 16: ngx.timer.*
--- stream_server_config
    lua_code_cache off;
    content_by_lua_block {
        ngx.timer.at(0, function ()
            local foo = ngx.unescape_uri("a%20b")
            ngx.log(ngx.WARN, "foo = ", foo)
        end)
        ngx.say("ok")
    }
--- stream_response
ok
--- wait: 0.2
--- no_error_log
[error]
--- error_log eval
["foo = a b",
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/
]



=== TEST 17: lua_max_pending_timers - chained timers (non-zero delay) - not exceeding
--- stream_config
    lua_max_pending_timers 1;
    lua_code_cache off;

--- stream_server_config
    content_by_lua_block {
        local s = ""

        local function fail(...)
            ngx.log(ngx.ERR, ...)
        end

        local function g()
            s = s .. "[g]"
            print("trace: ", s)
        end

        local function f()
            local ok, err = ngx.timer.at(0.01, g)
            if not ok then
                fail("failed to set timer: ", err)
                return
            end
            s = s .. "[f]"
        end
        local ok, err = ngx.timer.at(0.01, f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.say("registered timer")
        s = "[m]"
    }
--- stream_response
registered timer

--- wait: 0.2
--- no_error_log
[error]
stream lua decrementing the reference count for Lua VM: 3

--- error_log eval
[
"lua ngx.timer expired",
"stream lua finalize fake request",
"trace: [m][f][g]",
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/,
"stream lua close the global Lua VM",
"stream lua decrementing the reference count for Lua VM: 2",
"stream lua decrementing the reference count for Lua VM: 1",
]



=== TEST 18: lua variable sharing via upvalue
--- stream_config
    lua_code_cache off;
--- stream_server_config
    content_by_lua_block {
        local begin = ngx.now()
        local foo
        local function f()
            foo = 3
            print("elapsed: ", ngx.now() - begin)
        end
        local ok, err = ngx.timer.at(0.05, f)
        if not ok then
            ngx.say("failed to set timer: ", err)
            return
        end
        ngx.say("registered timer")
        ngx.sleep(0.06)
        ngx.say("foo = ", foo)
    }
--- stream_response
registered timer
foo = 3

--- wait: 0.1
--- no_error_log
[error]
decrementing the reference count for Lua VM: 3

--- error_log eval
[
"stream lua ngx.timer expired",
"stream lua finalize fake request",
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/,
"stream lua close the global Lua VM",
"stream lua decrementing the reference count for Lua VM: 2",
"stream lua decrementing the reference count for Lua VM: 1",
]



=== TEST 19: lua_max_running_timers (just not enough)
--- stream_config
    lua_max_running_timers 1;
--- stream_server_config
    lua_code_cache off;
    content_by_lua_block {
        local s = ""

        local function fail(...)
            ngx.log(ngx.ERR, ...)
        end

        local f, g

        g = function ()
            print("HERE in g")
            ngx.sleep(0.01)
            -- collectgarbage()
            print("HERE out g")
        end

        f = function ()
            print("HERE in f")
            ngx.sleep(0.01)
            -- collectgarbage()
            print("HERE out f")
        end
        local ok, err = ngx.timer.at(0, f)
        if not ok then
            ngx.say("failed to set timer f: ", err)
            return
        end
        local ok, err = ngx.timer.at(0, g)
        if not ok then
            ngx.say("failed to set timer g: ", err)
            return
        end
        ngx.say("registered timer")
        s = "[m]"
    }
--- stream_response
registered timer

--- wait: 0.2
--- no_error_log
[error]

--- error_log eval
[
"stream lua: 1 lua_max_running_timers are not enough",
"stream lua ngx.timer expired",
"stream lua finalize fake request",
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/,
"stream lua decrementing the reference count for Lua VM: 3",
"stream lua decrementing the reference count for Lua VM: 2",
"stream lua decrementing the reference count for Lua VM: 1",
"stream lua close the global Lua VM",
]



=== TEST 20: GC issue with the on_abort thread object
--- stream_server_config
    lua_code_cache off;
    lua_check_client_abort on;

    content_by_lua_block {
        ngx.on_abort(function () end)
        collectgarbage()
        ngx.sleep(1)
    }
--- abort
--- timeout: 0.2
--- wait: 1
--- stream_response
receive stream response error: timeout
--- no_error_log
[error]
stream lua decrementing the reference count for Lua VM: 2
stream lua decrementing the reference count for Lua VM: 3
--- error_log eval
["stream lua decrementing the reference count for Lua VM: 1",
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/,
"stream lua close the global Lua VM",
]



=== TEST 21: multiple parallel timers
--- stream_server_config
    lua_code_cache off;
    content_by_lua_block {
        local s = ""

        local function fail(...)
            ngx.log(ngx.ERR, ...)
        end

        local function g()
            s = s .. "[g]"
            print("trace: ", s)
        end

        local function f()
            s = s .. "[f]"
        end
        local ok, err = ngx.timer.at(0.01, f)
        if not ok then
            fail("failed to set timer: ", err)
            return
        end
        local ok, err = ngx.timer.at(0.01, g)
        if not ok then
            fail("failed to set timer: ", err)
            return
        end
        ngx.say("registered timer")
        s = "[m]"
    }
--- stream_response
registered timer

--- wait: 0.2
--- no_error_log
[error]
stream lua decrementing the reference count for Lua VM: 4

--- error_log eval
[
"stream lua ngx.timer expired",
"stream lua finalize fake request",
"trace: [m][f][g]",
"stream lua decrementing the reference count for Lua VM: 3",
"stream lua decrementing the reference count for Lua VM: 2",
"stream lua decrementing the reference count for Lua VM: 1",
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/,
"stream lua close the global Lua VM",
]



=== TEST 22: cosocket connection pool timeout (after Lua VM destroys)
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    lua_code_cache off;
    content_by_lua_block {
        local test = require "test"
        local port = $TEST_NGINX_MEMCACHED_PORT
        test.go(port)
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

    local ok, err = sock:setkeepalive(1)
    if not ok then
        ngx.say("failed to set reusable: ", err)
    end
end
--- stream_response
connected: 1, reused: 0
request sent: 11
received: OK
--- no_error_log
[error]
stream lua tcp socket keepalive max idle timeout

--- error_log eval
[
qq{stream lua tcp socket keepalive create connection pool for key "127.0.0.1:$ENV{TEST_NGINX_MEMCACHED_PORT}"},
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/,
qr/\blua tcp socket keepalive: free connection pool [0-9A-F]+ for "127.0.0.1:/,
]



=== TEST 23: cosocket connection pool timeout (before Lua VM destroys)
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    lua_code_cache off;
    content_by_lua_block {
        local test = require "test"
        local port = $TEST_NGINX_MEMCACHED_PORT
        test.go(port)
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

    local ok, err = sock:setkeepalive(1)
    if not ok then
        ngx.say("failed to set reusable: ", err)
    end
    ngx.sleep(0.01)
end
--- stream_response
connected: 1, reused: 0
request sent: 11
received: OK
--- no_error_log
[error]
--- error_log eval
[
qq{stream lua tcp socket keepalive create connection pool for key "127.0.0.1:$ENV{TEST_NGINX_MEMCACHED_PORT}"},
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/,
"stream lua tcp socket keepalive: free connection pool for ",
"stream lua tcp socket keepalive max idle timeout",
]



=== TEST 24: lua_max_running_timers (just not enough, also low lua_max_pending_timers)
--- stream_config
    lua_max_running_timers 1;
    lua_max_pending_timers 10;
--- stream_server_config
    lua_code_cache off;
    content_by_lua_block {
        local s = ""

        local function fail(...)
            ngx.log(ngx.ERR, ...)
        end

        local f, g

        g = function ()
            ngx.sleep(0.01)
            collectgarbage()
        end

        f = function ()
            ngx.sleep(0.01)
            collectgarbage()
        end
        local ok, err = ngx.timer.at(0, f)
        if not ok then
            ngx.say("failed to set timer f: ", err)
            return
        end
        local ok, err = ngx.timer.at(0, g)
        if not ok then
            ngx.say("failed to set timer g: ", err)
            return
        end
        ngx.say("registered timer")
        s = "[m]"
    }
--- stream_response
registered timer

--- wait: 0.1
--- no_error_log
[error]

--- error_log eval
[
"stream lua: 1 lua_max_running_timers are not enough",
"stream lua ngx.timer expired",
"stream lua finalize fake request",
qr/\[alert\] \S+ stream lua_code_cache is off; this will hurt performance/,
"stream lua decrementing the reference count for Lua VM: 3",
"stream lua decrementing the reference count for Lua VM: 2",
"stream lua decrementing the reference count for Lua VM: 1",
"stream lua close the global Lua VM",
]



=== TEST 25: make sure inline code keys are correct
--- stream_config
    include ../html/a/proxy.conf;
    include ../html/b/proxy.conf;
    include ../html/c/proxy.conf;
--- stream_server_config
    content_by_lua_block {
        for _, n in ipairs({ 1, 2, 1, 3 }) do
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx" .. n .. ".sock")
            if not ok then
                ngx.log(ngx.ERR, "could not connect: ", err)
                return
            end

            local res, err = sock:receive(11)
            if not res then
                ngx.log(ngx.ERR, "could not receive: ", err)
                return
            end

            ngx.say(res)

            sock:close()
        end
    }
--- user_files
>>> a/proxy.conf
server {
    listen unix:$TEST_NGINX_HTML_DIR/nginx1.sock;
    content_by_lua_block { ngx.say("1 is called") }
}

>>> b/proxy.conf
server {
    listen unix:$TEST_NGINX_HTML_DIR/nginx2.sock;
    content_by_lua_block { ngx.say("2 is called") }
}

>>> c/proxy.conf
server {
    listen unix:$TEST_NGINX_HTML_DIR/nginx3.sock;
    content_by_lua_block { ngx.say("2 is called") }
}
--- stream_response
1 is called
2 is called
1 is called
2 is called
--- grep_error_log eval: qr/looking up Lua code cache with key '=content_by_lua\(proxy\.conf:\d+\).*?'/
--- grep_error_log_out eval
[
"looking up Lua code cache with key '=content_by_lua(proxy.conf:3)nhli_ad58d60a0f20ae31b1a282e74053d356'
looking up Lua code cache with key '=content_by_lua(proxy.conf:3)nhli_9c867c93f28b91041fe132817b43ad07'
looking up Lua code cache with key '=content_by_lua(proxy.conf:3)nhli_ad58d60a0f20ae31b1a282e74053d356'
looking up Lua code cache with key '=content_by_lua(proxy.conf:3)nhli_9c867c93f28b91041fe132817b43ad07'
",
"looking up Lua code cache with key '=content_by_lua(proxy.conf:3)nhli_ad58d60a0f20ae31b1a282e74053d356'
looking up Lua code cache with key '=content_by_lua(proxy.conf:3)nhli_9c867c93f28b91041fe132817b43ad07'
looking up Lua code cache with key '=content_by_lua(proxy.conf:3)nhli_ad58d60a0f20ae31b1a282e74053d356'
looking up Lua code cache with key '=content_by_lua(proxy.conf:3)nhli_9c867c93f28b91041fe132817b43ad07'
looking up Lua code cache with key '=content_by_lua(proxy.conf:3)nhli_ad58d60a0f20ae31b1a282e74053d356'
looking up Lua code cache with key '=content_by_lua(proxy.conf:3)nhli_9c867c93f28b91041fe132817b43ad07'
looking up Lua code cache with key '=content_by_lua(proxy.conf:3)nhli_ad58d60a0f20ae31b1a282e74053d356'
looking up Lua code cache with key '=content_by_lua(proxy.conf:3)nhli_9c867c93f28b91041fe132817b43ad07'
"]
--- log_level: debug
--- no_error_log
[error]



=== TEST 26: make sure inline code keys are correct
--- stream_config
    include ../html/a/proxy.conf;
    include ../html/b/proxy.conf;
    include ../html/c/proxy.conf;
--- stream_server_config
    content_by_lua_block {
        for _, n in ipairs({ 1, 2, 1, 3 }) do
            local sock = ngx.socket.tcp()
            sock:settimeouts(1000, 1000, 1000)

            local ok, err = sock:connect("unix:$TEST_NGINX_HTML_DIR/nginx" .. n .. ".sock")
            if not ok then
                ngx.log(ngx.ERR, "could not connect: ", err)
                return
            end

            local res, err = sock:receive(11)
            if not res then
                ngx.log(ngx.ERR, "could not receive: ", err)
                return
            end

            ngx.say(res)

            sock:close()
        end
    }
--- user_files
>>> a.lua
ngx.say("1 is called")

>>> b.lua
ngx.say("2 is called")

>>> c.lua
ngx.say("2 is called")

>>> a/proxy.conf
server {
    listen unix:$TEST_NGINX_HTML_DIR/nginx1.sock;
    content_by_lua_file html/a.lua;
}

>>> b/proxy.conf
server {
    listen unix:$TEST_NGINX_HTML_DIR/nginx2.sock;
    content_by_lua_file html/b.lua;
}

>>> c/proxy.conf
server {
    listen unix:$TEST_NGINX_HTML_DIR/nginx3.sock;
    content_by_lua_file html/c.lua;
}
--- stream_response
1 is called
2 is called
1 is called
2 is called
--- grep_error_log eval: qr/looking up Lua code cache with key 'nhlf_.*?'/
--- grep_error_log_out eval
[
"looking up Lua code cache with key 'nhlf_48a9a7def61143c003a7de1644e026e4'
looking up Lua code cache with key 'nhlf_68f5f4e946c3efd1cc206452b807e8b6'
looking up Lua code cache with key 'nhlf_48a9a7def61143c003a7de1644e026e4'
looking up Lua code cache with key 'nhlf_042c9b3a136fbacbbd0e4b9ad10896b7'
",
"looking up Lua code cache with key 'nhlf_48a9a7def61143c003a7de1644e026e4'
looking up Lua code cache with key 'nhlf_68f5f4e946c3efd1cc206452b807e8b6'
looking up Lua code cache with key 'nhlf_48a9a7def61143c003a7de1644e026e4'
looking up Lua code cache with key 'nhlf_042c9b3a136fbacbbd0e4b9ad10896b7'
looking up Lua code cache with key 'nhlf_48a9a7def61143c003a7de1644e026e4'
looking up Lua code cache with key 'nhlf_68f5f4e946c3efd1cc206452b807e8b6'
looking up Lua code cache with key 'nhlf_48a9a7def61143c003a7de1644e026e4'
looking up Lua code cache with key 'nhlf_042c9b3a136fbacbbd0e4b9ad10896b7'
"]
--- log_level: debug
--- no_error_log
[error]
