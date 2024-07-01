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

=== TEST 1: hello SHA-224
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha224 = require "resty.sha224"
            local str = require "resty.string"
            local sha224 = resty_sha224:new()
            ngx.say(sha224:update("hello"))
            local digest = sha224:final()
            ngx.say("sha224: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
sha224: ea09ae9cc6768c50fcee903ed054556e5bfc8347907f12598aa24193
--- no_error_log
[error]



=== TEST 2: SHA-224 incremental
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha224 = require "resty.sha224"
            local str = require "resty.string"
            local sha224 = resty_sha224:new()
            ngx.say(sha224:update("hel"))
            ngx.say(sha224:update("lo"))
            local digest = sha224:final()
            ngx.say("sha224: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
true
sha224: ea09ae9cc6768c50fcee903ed054556e5bfc8347907f12598aa24193
--- no_error_log
[error]



=== TEST 3: SHA-224 empty string
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha224 = require "resty.sha224"
            local str = require "resty.string"
            local sha224 = resty_sha224:new()
            ngx.say(sha224:update(""))
            local digest = sha224:final()
            ngx.say("sha224: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
sha224: d14a028c2a3a2bc9476102bb288234c415a2b01f828ea62ac5b3e42f
--- no_error_log
[error]



=== TEST 4: hello (SHA-1 + SHA-224 + SHA-256 + SHA-512 at the same time)
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha224 = require "resty.sha224"
            local resty_sha256 = require "resty.sha256"
            local resty_sha1 = require "resty.sha1"
            local resty_sha512 = require "resty.sha512"

            local str = require "resty.string"

            local sha224 = resty_sha224:new()
            local sha256 = resty_sha256:new()
            local sha1 = resty_sha1:new()
            local sha512 = resty_sha512:new()

            ngx.say(sha224:update("hello"))
            ngx.say(sha256:update("hello"))
            ngx.say(sha1:update("hello"))
            ngx.say(sha512:update("hello"))


            local digest = sha224:final()
            ngx.say("sha224: ", str.to_hex(digest))

            digest = sha256:final()
            ngx.say("sha256: ", str.to_hex(digest))

            digest = sha1:final()
            ngx.say("sha1: ", str.to_hex(digest))

            digest = sha512:final()
            ngx.say("sha512: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
true
true
true
sha224: ea09ae9cc6768c50fcee903ed054556e5bfc8347907f12598aa24193
sha256: 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
sha1: aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d
sha512: 9b71d224bd62f3785d96d46ad3ea3d73319bfbc2890caadae2dff72519673ca72323c3d99ba5c11d7c7acc6e14b8c5da0c4663475c2e5c3adef46f73bcdec043
--- no_error_log
[error]
