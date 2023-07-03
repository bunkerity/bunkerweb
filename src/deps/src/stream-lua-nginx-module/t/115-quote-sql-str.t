# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;
repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

#log_level("warn");
no_long_string();

run_tests();

__DATA__

=== TEST 1: \0
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.quote_sql_str("a\0b\0"))
    }

--- config
--- stream_response
'a\0b\0'
--- no_error_log
[error]



=== TEST 2: \t
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.quote_sql_str("a\tb\t"))
    }

--- config
--- stream_response
'a\tb\t'
--- no_error_log
[error]



=== TEST 3: \b
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.quote_sql_str("a\bb\b"))
    }

--- config
--- stream_response
'a\bb\b'
--- no_error_log
[error]



=== TEST 4: \Z
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.quote_sql_str("a\026b\026"))
    }

--- config
--- stream_response
'a\Zb\Z'
--- no_error_log
[error]
