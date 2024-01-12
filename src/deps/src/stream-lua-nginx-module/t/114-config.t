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

=== TEST 1: ngx.config.debug
--- stream_server_config
    content_by_lua_block {
        ngx.say("debug: ", ngx.config.debug)
    }

--- stream_response_like chop
^debug: (?:true|false)$
--- no_error_log
[error]



=== TEST 2: ngx.config.subystem
--- stream_server_config
    content_by_lua_block {
        ngx.say("subsystem: ", ngx.config.subsystem)
    }
--- stream_response
subsystem: stream
--- no_error_log
[error]
