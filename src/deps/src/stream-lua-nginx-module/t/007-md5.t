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

=== TEST 1: set md5 hello
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.md5("hello")) }
--- stream_response
5d41402abc4b2a76b9719d911017c592
--- no_error_log
[error]



=== TEST 2: nil string to ngx.md5
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.md5(nil)) }
--- stream_response
d41d8cd98f00b204e9800998ecf8427e
--- no_error_log
[error]



=== TEST 3: empty string to ngx.md5
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.md5("")) }
--- stream_response
d41d8cd98f00b204e9800998ecf8427e
--- no_error_log
[error]



=== TEST 4: md5(number)
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.md5(45)) }
--- stream_response
6c8349cc7260ae62e3b1396831a8398f
--- no_error_log
[error]
