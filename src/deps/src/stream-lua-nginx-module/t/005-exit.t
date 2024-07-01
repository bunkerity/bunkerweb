# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

#repeat_each(20000);
repeat_each(2);
#master_on();
#workers(1);
#log_level('debug');
#log_level('warn');
#worker_connections(1024);

plan tests => repeat_each() * (blocks() * 3);

$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;
$ENV{TEST_NGINX_MYSQL_PORT} ||= 3306;

our $LuaCpath = $ENV{LUA_CPATH} ||
    '/usr/local/openresty-debug/lualib/?.so;/usr/local/openresty/lualib/?.so;;';

#$ENV{LUA_PATH} = $ENV{HOME} . '/work/JSON4Lua-0.9.30/json/?.lua';

no_long_string();

run_tests();

__DATA__

=== TEST 1: throw error
--- stream_server_config
    content_by_lua_block { ngx.exit(ngx.ERROR);ngx.say('hi') }
--- stream_response
--- no_error_log
[error]



=== TEST 2: throw error after sending the header and partial body
--- stream_server_config
    content_by_lua_block { ngx.say('hi');ngx.exit(ngx.ERROR);ngx.say(', you') }
--- no_error_log
[error]
--- stream_response
hi



=== TEST 3: throw 0
--- stream_server_config
    content_by_lua_block { ngx.say('Hi'); ngx.eof(); ngx.exit(0);ngx.say('world') }
--- stream_response
Hi
--- no_error_log
[error]



=== TEST 4: pcall safe
--- stream_server_config
    content_by_lua_block {
        function f ()
            ngx.say("hello")
            ngx.exit(200)
        end

        pcall(f)
        ngx.say("world")
    }
--- stream_response
hello
--- no_error_log
[error]



=== TEST 5: throw 444 after sending out responses
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok');
        return ngx.exit(444)
    }
--- stream_response
ok
--- log_level: debug
--- no_error_log
[error]



=== TEST 6: throw 499 after sending out responses
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok');
        return ngx.exit(499)
    }
--- stream_response
ok
--- log_level: debug
--- no_error_log
[error]



=== TEST 7: throw 408 after sending out responses
--- stream_server_config
    content_by_lua_block {
        ngx.say('ok');
        return ngx.exit(408)
    }
--- stream_response
ok
--- log_level: debug
--- no_error_log
[error]
