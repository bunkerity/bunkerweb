# vim:set ft= ts=4 sw=4 et fdm=marker:
use Test::Nginx::Socket::Lua::Stream;

#worker_connections(1014);
#master_process_enabled(1);
log_level('warn');

repeat_each(2);

plan tests => repeat_each() * (blocks() * 2 + 1);

#no_diff();
#no_long_string();
run_tests();

__DATA__

=== TEST 1: set sha1 hello
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.encode_base64(ngx.sha1_bin("hello"))) }
--- stream_response
qvTGHdzF6KLavt4PO0gs2a6pQ00=



=== TEST 2: set sha1 ""
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.encode_base64(ngx.sha1_bin(""))) }
--- stream_response
2jmj7l5rSw0yVb/vlWAYkK/YBwk=



=== TEST 3: set sha1 nil
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.encode_base64(ngx.sha1_bin(nil))) }
--- stream_response
2jmj7l5rSw0yVb/vlWAYkK/YBwk=



=== TEST 4: set sha1 number
--- stream_server_config
    content_by_lua_block { ngx.say(ngx.encode_base64(ngx.sha1_bin(512))) }
--- stream_response
zgmxJ9SPg4aKRWReJG07UvS97L4=
--- no_error_log
[error]
