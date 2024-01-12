# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua::Stream;

repeat_each(2);

plan tests => repeat_each() * (blocks() * 3 + 3);

no_long_string();

run_tests();

__DATA__

=== TEST 1: escape uri in content_by_lua
--- stream_server_config
    content_by_lua_block {ngx.say(ngx.escape_uri('a 你'))}
--- stream_response
a%20%E4%BD%A0
--- no_error_log
[error]



=== TEST 2: unescape uri in content_by_lua
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.unescape_uri('a%20%e4%bd%a0')) }
--- stream_response
a 你
--- no_error_log
[error]



=== TEST 3: escape uri in content_by_lua
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.escape_uri('a+b')) }
--- stream_response
a%2Bb
--- no_error_log
[error]



=== TEST 4: escape uri in content_by_lua
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.escape_uri('"a/b={}:<>;&[]\\^')) }
--- stream_response
%22a%2Fb%3D%7B%7D%3A%3C%3E%3B%26%5B%5D%5C%5E
--- no_error_log
[error]



=== TEST 5: escape a string that cannot be escaped
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.escape_uri('abc')) }
--- stream_response
abc
--- no_error_log
[error]



=== TEST 6: escape an empty string that cannot be escaped
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.escape_uri('')) }
--- stream_response eval: "\n"
--- no_error_log
[error]



=== TEST 7: escape nil
--- stream_server_config
    content_by_lua_block { ngx.say("[", ngx.escape_uri(nil), "]") }
--- stream_response
[]
--- no_error_log
[error]



=== TEST 8: escape numbers
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.escape_uri(32)) }
--- stream_response
32
--- no_error_log
[error]



=== TEST 9: unescape nil
--- stream_server_config
    content_by_lua_block { ngx.say("[", ngx.unescape_uri(nil), "]") }
--- stream_response
[]
--- no_error_log
[error]



=== TEST 10: unescape numbers
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.unescape_uri(32)) }
--- stream_response
32
--- no_error_log
[error]



=== TEST 11: escape type
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.escape_uri("https://www.google.com/?t=abc@ :", 0))
        ngx.say(ngx.escape_uri("https://www.google.com/?t=abc@ :", 1))
        ngx.say(ngx.escape_uri("https://www.google.com/?t=abc@ :", 2))
        ngx.say(ngx.escape_uri("https://www.google.com/?t=abc@ :", 3))
        ngx.say(ngx.escape_uri("https://www.google.com/?t=abc@ :", 4))
        ngx.say(ngx.escape_uri("https://www.google.com/?t=abc@ :", 5))
        ngx.say(ngx.escape_uri("https://www.google.com/?t=abc@ :", 6))
    }
--- stream_response
https://www.google.com/%3Ft=abc@%20:
https://www.google.com/%3Ft=abc@%20:
https%3A%2F%2Fwww.google.com%2F%3Ft%3Dabc%40%20%3A
https://www.google.com/?t=abc@%20:
https://www.google.com/?t=abc@%20:
https://www.google.com/?t=abc@%20:
https://www.google.com/?t=abc@%20:
--- no_error_log
[error]



=== TEST 12: escape type error
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.escape_uri("https://www.google.com/?t=abc@ :", true))
    }
--- stream_response
--- error_log eval
qr/\[error\] \d+#\d+: \*\d+ lua entry thread aborted: runtime error: "type" is not a number/
--- no_error_log
[alert]



=== TEST 13: escape type out of range
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.escape_uri("https://www.google.com/?t=abc@ :", -1))
    }
--- stream_response
--- error_log eval
qr/\[error\] \d+#\d+: \*\d+ lua entry thread aborted: runtime error: "type" -1 out of range/
--- no_error_log
[alert]



=== TEST 14: escape type error
--- stream_server_config
    content_by_lua_block {
        ngx.say(ngx.escape_uri("https://www.google.com/?t=abc@ :", 100))
    }
--- stream_response
--- error_log eval
qr/\[error\] \d+#\d+: \*\d+ lua entry thread aborted: runtime error: "type" 100 out of range/
--- no_error_log
[alert]
