# vim:set ft= ts=4 sw=4 et fdm=marker:
use Test::Nginx::Socket::Lua::Stream;
#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 3);

#no_diff();
#no_long_string();
no_shuffle();

run_tests();

__DATA__

=== TEST 1: sanity (inline)
--- stream_config
    init_by_lua_block { foo = "hello, FOO" }
--- stream_server_config
    content_by_lua_block { ngx.say(foo) }
--- stream_response
hello, FOO
--- no_error_log
[error]



=== TEST 2: sanity (file)
--- stream_config
    init_by_lua_file html/init.lua;
--- stream_server_config
    content_by_lua_block { ngx.say(foo) }
--- user_files
>>> init.lua
foo = "hello, FOO"
--- stream_response
hello, FOO
--- no_error_log
[error]



=== TEST 3: require
--- stream_config
    lua_package_path "$prefix/html/?.lua;;";
    init_by_lua_block { require "blah" }
--- stream_server_config
    content_by_lua_block {
        blah.go()
    }
--- user_files
>>> blah.lua
module(..., package.seeall)

function go()
    ngx.say("hello, blah")
end
--- stream_response
hello, blah
--- no_error_log
[error]



=== TEST 4: shdict (single)
--- stream_config
    lua_shared_dict dogs 1m;
    init_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("Jim", 6)
        dogs:get("Jim")
    }
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        ngx.say("Jim: ", dogs:get("Jim"))
    }
--- stream_response
Jim: 6
--- no_error_log
[error]



=== TEST 5: shdict (multi)
--- stream_config
    lua_shared_dict dogs 1m;
    lua_shared_dict cats 1m;
    init_by_lua_block {
        local dogs = ngx.shared.dogs
        dogs:set("Jim", 6)
        dogs:get("Jim")
        local cats = ngx.shared.cats
        cats:set("Tom", 2)
        dogs:get("Tom")
    }
--- stream_server_config
    content_by_lua_block {
        local dogs = ngx.shared.dogs
        ngx.say("Jim: ", dogs:get("Jim"))
    }
--- stream_response
Jim: 6
--- no_error_log
[error]



=== TEST 6: print
--- stream_config
    lua_shared_dict dogs 1m;
    lua_shared_dict cats 1m;
    init_by_lua_block {
        print("log from init_by_lua")
    }
--- stream_server_config
    content_by_lua_block { ngx.say('ok') }
--- stream_response
ok
--- grep_error_log chop
log from init_by_lua
--- grep_error_log_out eval
["log from init_by_lua\n", ""]



=== TEST 7: ngx.log
--- stream_config
    lua_shared_dict dogs 1m;
    lua_shared_dict cats 1m;
    init_by_lua_block {
        ngx.log(ngx.NOTICE, "log from init_by_lua")
    }
--- stream_server_config
    content_by_lua_block { ngx.say('ok') }
--- stream_response
ok
--- grep_error_log chop
log from init_by_lua
--- grep_error_log_out eval
["log from init_by_lua\n", ""]



=== TEST 8: require (with shm defined)
--- stream_config
    lua_package_path "$prefix/html/?.lua;;";
    lua_shared_dict dogs 1m;
    init_by_lua_block { require "blah" }
--- stream_server_config
    content_by_lua_block {
        blah.go()
    }
--- user_files
>>> blah.lua
module(..., package.seeall)

function go()
    ngx.say("hello, blah")
end
--- stream_response
hello, blah
--- no_error_log
[error]



=== TEST 9: coroutine API (inlined init_by_lua)
--- stream_config
    init_by_lua_block {
        local function f()
            foo = 32
            coroutine.yield(78)
            bar = coroutine.status(coroutine.running())
        end
        local co = coroutine.create(f)
        local ok, err = coroutine.resume(co)
        if not ok then
            print("Failed to resume our co: ", err)
            return
        end
        baz = err
        coroutine.resume(co)
    }
--- stream_server_config
    content_by_lua_block {
        ngx.say("foo = ", foo)
        ngx.say("bar = ", bar)
        ngx.say("baz = ", baz)
    }
--- stream_response
foo = 32
bar = running
baz = 78
--- no_error_log
[error]
Failed to resume our co: 



=== TEST 10: coroutine API (init_by_lua_file)
--- stream_config
    init_by_lua_file html/init.lua;

--- stream_server_config
    content_by_lua_block {
        ngx.say("foo = ", foo)
        ngx.say("bar = ", bar)
        ngx.say("baz = ", baz)
    }
--- user_files
>>> init.lua
local function f()
    foo = 32
    coroutine.yield(78)
    bar = coroutine.status(coroutine.running())
end
local co = coroutine.create(f)
local ok, err = coroutine.resume(co)
if not ok then
    print("Failed to resume our co: ", err)
    return
end
baz = err
coroutine.resume(co)

--- stream_response
foo = 32
bar = running
baz = 78
--- no_error_log
[error]
Failed to resume our co: 



=== TEST 11: access a field in the ngx. table
--- stream_config
    init_by_lua_block {
        print("INIT 1: foo = ", ngx.foo)
        ngx.foo = 3
        print("INIT 2: foo = ", ngx.foo)
    }
--- stream_server_config
    content_by_lua_block { ngx.say('ok') }
--- stream_response
ok
--- no_error_log
[error]
--- grep_error_log eval: qr/INIT \d+: foo = \S+/
--- grep_error_log_out eval
[
"INIT 1: foo = nil
INIT 2: foo = 3
",
"",
]
