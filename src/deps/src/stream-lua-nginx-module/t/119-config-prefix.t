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

=== TEST 1: content_by_lua
--- stream_server_config
    content_by_lua_block {
        ngx.say("prefix: ", ngx.config.prefix())
    }
--- stream_response_like chop
^prefix: \/\S+$
--- no_error_log
[error]
