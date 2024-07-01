# vim:set ft= ts=4 sw=4 et fdm=marker:
use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);
#repeat_each(1);

plan tests => repeat_each() * (blocks() * 3);

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: $prefix
--- stream_config: lua_package_path "$prefix/html/?.lua;;";
--- stream_server_config
    content_by_lua_block {
        local foo = require "foo"
        foo.go()
    }
--- user_files
>>> foo.lua
module("foo", package.seeall)

function go()
    ngx.say("Greetings from module foo.")
end
--- stream_response
Greetings from module foo.
--- no_error_log
[error]



=== TEST 2: ${prefix}
--- stream_config: lua_package_path "${prefix}html/?.lua;;";
--- stream_server_config
    content_by_lua_block {
        local foo = require "foo"
        foo.go()
    }
--- user_files
>>> foo.lua
module("foo", package.seeall)

function go()
    ngx.say("Greetings from module foo.")
end
--- stream_response
Greetings from module foo.
--- no_error_log
[error]
