# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;
#repeat_each(20000);

repeat_each(2);

#master_on();
#workers(1);
#log_level('debug');
#log_level('warn');
#worker_connections(1024);

plan tests => repeat_each() * (blocks() * 2);

$ENV{TEST_NGINX_MEMCACHED_PORT} ||= 11211;
$ENV{TEST_NGINX_MYSQL_PORT} ||= 3306;

our $LuaCpath = $ENV{LUA_CPATH} ||
    '/usr/local/openresty-debug/lualib/?.so;/usr/local/openresty/lualib/?.so;;';

#$ENV{LUA_PATH} = $ENV{HOME} . '/work/JSON4Lua-0.9.30/json/?.lua';

no_long_string();
#no_shuffle();

run_tests();

__DATA__

=== TEST 1: throw 500
--- stream_server_config
    preread_by_lua_block { ngx.exit(500);ngx.say('hi') }
    content_by_lua_block { ngx.exit(ngx.OK) }
--- error_log
finalize stream request: 500



=== TEST 2: throw 0
--- stream_server_config
    preread_by_lua_block { ngx.say('Hi'); ngx.eof(); ngx.exit(0);ngx.say('world') }
    content_by_lua_block { ngx.exit(ngx.OK) }
--- stream_response
Hi
