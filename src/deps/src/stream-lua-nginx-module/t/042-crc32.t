# vim:set ft= ts=4 sw=4 et fdm=marker:
use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_process_enabled(1);
log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 2);

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: short sanity
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.crc32_short("hello, world"))
    }
--- stream_response
4289425978



=== TEST 2: long sanity
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.crc32_long("hello, world"))
    }
--- stream_response
4289425978



=== TEST 3: long sanity (empty)
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.crc32_long(""))
    }
--- stream_response
0
