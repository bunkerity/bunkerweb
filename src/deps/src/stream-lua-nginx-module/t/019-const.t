# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

repeat_each(2);

plan tests => blocks() * repeat_each() * 3;

#no_diff();
#no_long_string();

run_tests();

__DATA__

=== TEST 1: sanity
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.OK)
        ngx.say(ngx.AGAIN)
        ngx.say(ngx.DONE)
        ngx.say(ngx.ERROR)
        ngx.say(ngx.DECLINED)
    }
--- stream_response
0
-2
-4
-1
-5
--- no_error_log
[error]
