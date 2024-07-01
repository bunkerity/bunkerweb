# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_on();
#workers(2);
#log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

#no_diff();
#no_long_string();

run_tests();

__DATA__

=== TEST 1: sanity
--- stream_server_config
    content_by_lua_block {
        local table = {"hello", nil, true, false, 32.5, 56}
        ngx.say(table)
    }
--- stream_response
helloniltruefalse32.556
--- no_error_log
[error]



=== TEST 2: nested table
--- stream_server_config
    content_by_lua_block {
        local table = {"hello", nil, true, false, 32.5, 56}
        local table2 = {table, "--", table}
        ngx.say(table2)
    }
--- stream_response
helloniltruefalse32.556--helloniltruefalse32.556
--- no_error_log
[error]



=== TEST 3: non-array table
--- stream_server_config
    content_by_lua_block {
        local table = {foo = 3}
        ngx.say(table)
    }
--- stream_response
--- error_log
bad argument #1 to 'say' (non-array table found)



=== TEST 4: bad data type in table
--- stream_server_config
    content_by_lua_block {
        local f = function () return end
        local table = {1, 3, f}
        ngx.say(table)
    }
--- stream_response
--- error_log
bad argument #1 to 'say' (bad data type function found)
