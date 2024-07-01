# vi:ft=

use Test::Nginx::Socket::Lua;

repeat_each(2);

plan tests => repeat_each() * (3 * blocks());

our $HttpConfig = <<'_EOC_';
    lua_package_path 'lib/?.lua;;';
    lua_package_cpath 'lib/?.so;;';
_EOC_

no_long_string();

run_tests();

__DATA__

=== TEST 1: pseudo random bytes
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local rand = require "resty.random"
            local str = require "resty.string"
            local s = rand.bytes(5)
            ngx.say("res: ", str.to_hex(s))
        ';
    }
--- request
GET /t
--- response_body_like
^res: [a-f0-9]{10}$
--- no_error_log
[error]



=== TEST 2: strong random bytes
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local rand = require "resty.random"
            local str = require "resty.string"
            local s = rand.bytes(5, true)
            ngx.say("res: ", str.to_hex(s))
        ';
    }
--- request
GET /t
--- response_body_like
^res: [a-f0-9]{10}$
--- no_error_log
[error]
