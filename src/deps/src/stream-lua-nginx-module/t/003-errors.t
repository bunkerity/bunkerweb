# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

repeat_each(2);

plan tests => blocks() * (repeat_each() * 3);

#$ENV{LUA_PATH} = $ENV{HOME} . '/work/JSON4Lua-0.9.30/json/?.lua';

no_long_string();

run_tests();

__DATA__

=== TEST 1: syntax error in lua code chunk
--- stream_server_config
    content_by_lua_block {local a
        a = a+;
        return a}
--- stream_response
--- error_log eval
qr/failed to load inlined Lua code: content_by_lua\(nginx\.conf:\d+\):2: unexpected symbol near ';'/



=== TEST 2: syntax error in lua file
--- stream_server_config
    content_by_lua_file 'html/test.lua';
--- user_files
>>> test.lua
local a
a = 3 +;
return a
--- stream_response
--- error_log eval
qr{failed to load external Lua file ".*?html/test\.lua": .*?test\.lua:2: unexpected symbol near ';'}
