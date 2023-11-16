# vi:ft=

use Test::Nginx::Socket::Lua;

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

=== TEST 1: hello SHA-1
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha1 = require "resty.sha1"
            local str = require "resty.string"
            local sha1 = resty_sha1:new()
            ngx.say(sha1:update("hello"))
            local digest = sha1:final()
            ngx.say(digest == ngx.sha1_bin("hello"))
            ngx.say("sha1: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
true
sha1: aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d
--- no_error_log
[error]



=== TEST 2: SHA-1 incremental
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha1 = require "resty.sha1"
            local str = require "resty.string"
            local sha1 = resty_sha1:new()
            ngx.say(sha1:update("hel"))
            ngx.say(sha1:update("lo"))
            local digest = sha1:final()
            ngx.say("sha1: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
true
sha1: aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d
--- no_error_log
[error]



=== TEST 3: SHA-1 empty string
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha1 = require "resty.sha1"
            local str = require "resty.string"
            local sha1 = resty_sha1:new()
            ngx.say(sha1:update(""))
            local digest = sha1:final()
            ngx.say(digest == ngx.sha1_bin(""))
            ngx.say("sha1: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
true
sha1: da39a3ee5e6b4b0d3255bfef95601890afd80709
--- no_error_log
[error]
