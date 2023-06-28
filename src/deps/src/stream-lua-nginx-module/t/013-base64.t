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

=== TEST 1: base64 encode hello
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.encode_base64("hello")) }
--- stream_response
aGVsbG8=
--- no_error_log
[error]



=== TEST 2: nil string to ngx.encode_base64
--- stream_server_config
    content_by_lua_block { ngx.say("left" .. ngx.encode_base64(nil) .. "right") }
--- stream_response
leftright
--- no_error_log
[error]



=== TEST 3: empty string to ngx.encode_base64
--- stream_server_config
    content_by_lua_block { ngx.say("left" .. ngx.encode_base64("") .. "right") }
--- stream_response
leftright
--- no_error_log
[error]



=== TEST 4: base64 encode hello
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.decode_base64("aGVsbG8=")) }
--- stream_response
hello
--- no_error_log
[error]



=== TEST 5: null string to ngx.decode_base64
--- stream_server_config
    content_by_lua_block { ngx.say("left" .. ngx.decode_base64("") .. "right") }
--- stream_response
leftright
--- no_error_log
[error]



=== TEST 6: use ngx.decode_base64 in content_by_lua (nil)
--- stream_server_config
    content_by_lua_block { ngx.say("left" .. ngx.decode_base64(nil) .. "right") }
--- stream_response
--- error_log
string argument only



=== TEST 7: base64 encode number
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.encode_base64(32)) }
--- stream_response
MzI=
--- no_error_log
[error]



=== TEST 8: base64 decode number
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.decode_base64(32)) }
--- stream_response
--- error_log
string argument only



=== TEST 9: base64 decode error
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.decode_base64("^*~")) }
--- stream_response
nil
--- no_error_log
[error]



=== TEST 10: base64 encode without padding (explicit true to no_padding)
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.encode_base64("hello", true)) }
--- stream_response
aGVsbG8
--- no_error_log
[error]



=== TEST 11: base64 encode short string
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.encode_base64("w")) }
--- stream_response
dw==
--- no_error_log
[error]



=== TEST 12: base64 encode short string with padding (explicit false to no_padding)
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.encode_base64("w", false)) }
--- stream_response
dw==
--- no_error_log
[error]



=== TEST 13: base64 encode with wrong 2nd parameter
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.encode_base64("w", 0)) }
--- stream_response
--- error_log eval
qr/runtime error: content_by_lua\(nginx\.conf:\d+\):\d+: bad no_padding: boolean expected, got number/
