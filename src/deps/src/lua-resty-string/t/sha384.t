# vi:ft=

use Test::Nginx::Socket;

repeat_each(2);

plan tests => repeat_each() * (3 * blocks());

our $HttpConfig = <<'_EOC_';
    #lua_code_cache off;
    lua_package_path 'lib/?.lua;;';
    lua_package_cpath 'lib/?.so;;';
_EOC_

no_long_string();

run_tests();

__DATA__

=== TEST 1: hello SHA-384
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha384 = require "resty.sha384"
            local str = require "resty.string"
            local sha384 = resty_sha384:new()
            ngx.say(sha384:update("hello"))
            local digest = sha384:final()
            ngx.say("sha384: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
sha384: 59e1748777448c69de6b800d7a33bbfb9ff1b463e44354c3553bcdb9c666fa90125a3c79f90397bdf5f6a13de828684f
--- no_error_log
[error]



=== TEST 2: SHA-384 incremental
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha384 = require "resty.sha384"
            local str = require "resty.string"
            local sha384 = resty_sha384:new()
            ngx.say(sha384:update("hel"))
            ngx.say(sha384:update("lo"))
            local digest = sha384:final()
            ngx.say("sha384: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
true
sha384: 59e1748777448c69de6b800d7a33bbfb9ff1b463e44354c3553bcdb9c666fa90125a3c79f90397bdf5f6a13de828684f
--- no_error_log
[error]



=== TEST 3: SHA-384 empty string
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha384 = require "resty.sha384"
            local str = require "resty.string"
            local sha384 = resty_sha384:new()
            ngx.say(sha384:update(""))
            local digest = sha384:final()
            ngx.say("sha384: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
sha384: 38b060a751ac96384cd9327eb1b1e36a21fdb71114be07434c0cc7bf63f6e1da274edebfe76f65fbd51ad2f14898b95b
--- no_error_log
[error]
