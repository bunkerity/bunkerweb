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

=== TEST 1: bytecode (not stripped)
--- stream_server_config
    content_by_lua_block {
        local f = assert(loadstring("local a = a and a + 1 or 1 ngx.say('a = ', a)", "=code"))
        local bc = string.dump(f)
        local f = assert(io.open("$TEST_NGINX_SERVER_ROOT/html/a.luac", "w"))
        f:write(bc)
        f:close()
    }
--- stream_server_config2
    content_by_lua_file html/a.luac;
--- stream_response
a = 1
--- no_error_log
[error]



=== TEST 2: bytecode (stripped)
--- stream_server_config
    content_by_lua_block {
        local f = assert(loadstring("local a = a and a + 1 or 1 ngx.say('a = ', a)", "=code"))
        local bc = string.dump(f, true)
        local f = assert(io.open("$TEST_NGINX_SERVER_ROOT/html/a.luac", "w"))
        f:write(bc)
        f:close()
    }
--- stream_server_config2
    content_by_lua_file html/a.luac;
--- stream_response
a = 1
--- no_error_log
[error]
