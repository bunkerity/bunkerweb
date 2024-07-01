# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_process_enabled(1);
log_level('warn');

repeat_each(1);

plan tests => repeat_each() * (blocks() * 3);

#no_diff();
no_long_string();
run_tests();

__DATA__

=== TEST 1: use ngx.localtime in content_by_lua
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.localtime()) }
--- stream_response_like: ^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$
--- no_error_log
[error]



=== TEST 2: use ngx.time in content_by_lua
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.time()) }
--- stream_response_like: ^\d{10,}$
--- no_error_log
[error]



=== TEST 3: use ngx.time in content_by_lua
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.time())
        ngx.say(ngx.localtime())
        ngx.say(ngx.utctime())
    }
--- stream_response_like chomp
^\d{10,}
\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}
\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}
--- no_error_log
[error]



=== TEST 4: use ngx.now in content_by_lua
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.now()) }
--- stream_response_like: ^\d{10,}(\.\d{1,3})?$
--- no_error_log
[error]



=== TEST 5: use ngx.update_time & ngx.now in content_by_lua
--- stream_server_config
    content_by_lua_block {
        ngx.update_time()
        ngx.say(ngx.now())
    }
--- stream_response_like: ^\d{10,}(\.\d{1,3})?$
--- no_error_log
[error]
