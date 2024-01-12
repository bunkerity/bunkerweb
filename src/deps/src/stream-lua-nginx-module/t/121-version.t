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

=== TEST 1: nginx version
--- stream_server_config
    content_by_lua_block {
        ngx.say("version: ", ngx.config.nginx_version)
    }
--- stream_response_like chop
^version: \d+$
--- no_error_log
[error]



=== TEST 2: ngx_lua_version
--- stream_server_config
    content_by_lua_block {
        ngx.say("version: ", ngx.config.ngx_lua_version)
    }
--- stream_response_like chop
^version: \d+$
--- no_error_log
[error]
