# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#log_level('warn');

#master_on();
#repeat_each(120);
repeat_each(2);

plan tests => blocks() * (repeat_each() * 3);

our $HtmlDir = html_dir;
#warn $html_dir;

#$ENV{LUA_PATH} = "$html_dir/?.lua";

#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: sanity
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;./?.lua;;';"
--- stream_server_config
    # load
    content_by_lua_block {
        package.loaded.foo = nil;
        collectgarbage()
        local foo = require "foo";
        foo.hi()
    }

--- stream_server_config2
    # check
    content_by_lua_block {
        local foo = package.loaded.foo
        if foo then
            ngx.say("found")
            foo.hi()
        else
            ngx.say("not found")
        end
    }

--- stream_server_config3
    # check
    content_by_lua_block {
        local foo = package.loaded.foo
        if foo then
            ngx.say("found")
            foo.hi()
        else
            ngx.say("not found")
        end
    }
--- user_files
>>> foo.lua
local _M = {}

ngx.say("loading");

function _M.hi ()
    ngx.say("hello, foo")
end

return _M
--- stream_response
loading
hello, foo
found
hello, foo
found
hello, foo
--- no_error_log
[error]



=== TEST 2: sanity
--- stream_config eval
    "lua_package_cpath '$::HtmlDir/?.so';"
--- stream_server_config
    content_by_lua_block {
        ngx.print(package.cpath);
    }
--- stream_response_like: ^[^;]+/servroot(_\d+)?/html/\?\.so$
--- no_error_log
[error]



=== TEST 3: expand default path (after)
--- stream_config eval
    "lua_package_path '$::HtmlDir/?.lua;;';"
--- stream_server_config
    content_by_lua_block {
        ngx.print(package.path)
    }
--- stream_response_like: ^[^;]+/servroot(_\d+)?/html/\?\.lua;(.+\.lua)?;*$
--- no_error_log
[error]



=== TEST 4: expand default cpath (after)
--- stream_config eval
    "lua_package_cpath '$::HtmlDir/?.so;;';"
--- stream_server_config
    content_by_lua_block {
        ngx.print(package.cpath)
    }
--- stream_response_like: ^[^;]+/servroot(_\d+)?/html/\?\.so;(.+\.so)?;*$
--- no_error_log
[error]



=== TEST 5: expand default path (before)
--- stream_config eval
    "lua_package_path ';;$::HtmlDir/?.lua';"
--- stream_server_config
    content_by_lua_block {
        ngx.print(package.path);
    }
--- stream_response_like: ^(.+\.lua)?;*?[^;]+/servroot(_\d+)?/html/\?\.lua$
--- no_error_log
[error]



=== TEST 6: expand default cpath (before)
--- stream_config eval
    "lua_package_cpath ';;$::HtmlDir/?.so';"
--- stream_server_config
    content_by_lua_block {
        ngx.print(package.cpath);
    }
--- stream_response_like: ^(.+\.so)?;*?[^;]+/servroot(_\d+)?/html/\?\.so$
--- no_error_log
[error]



=== TEST 7: require "ngx" (content_by_lua_block)
--- stream_server_config
    content_by_lua_block {
        local ngx = require "ngx"
        ngx.say("hello, world")
    }
--- stream_response
hello, world
--- no_error_log
[error]
