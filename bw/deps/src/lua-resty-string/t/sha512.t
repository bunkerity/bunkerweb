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

=== TEST 1: hello SHA-512
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha512 = require "resty.sha512"
            local str = require "resty.string"
            local sha512 = resty_sha512:new()
            ngx.say(sha512:update("hello"))
            local digest = sha512:final()
            ngx.say("sha512: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
sha512: 9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca72323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043
--- no_error_log
[error]



=== TEST 2: SHA-512 incremental
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha512 = require "resty.sha512"
            local str = require "resty.string"
            local sha512 = resty_sha512:new()
            ngx.say(sha512:update("hel"))
            ngx.say(sha512:update("lo"))
            local digest = sha512:final()
            ngx.say("sha512: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
true
sha512: 9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca72323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043
--- no_error_log
[error]



=== TEST 3: SHA-512 empty string
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha512 = require "resty.sha512"
            local str = require "resty.string"
            local sha512 = resty_sha512:new()
            ngx.say(sha512:update(""))
            local digest = sha512:final()
            ngx.say("sha512: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
sha512: cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e
--- no_error_log
[error]
