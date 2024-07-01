# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_process_enabled(1);
log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3);

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: use ngx.today in content_by_lua*
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.today()) }
--- stream_response_like: ^\d{4}-\d{2}-\d{2}$
--- no_error_log
[error]
