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

=== TEST 1: hello SHA-256
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha256 = require "resty.sha256"
            local str = require "resty.string"
            local sha256 = resty_sha256:new()
            ngx.say(sha256:update("hello"))
            local digest = sha256:final()
            ngx.say("sha256: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
sha256: 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
--- no_error_log
[error]



=== TEST 2: SHA-256 incremental
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha256 = require "resty.sha256"
            local str = require "resty.string"
            local sha256 = resty_sha256:new()
            ngx.say(sha256:update("hel"))
            ngx.say(sha256:update("lo"))
            local digest = sha256:final()
            ngx.say("sha256: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
true
sha256: 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
--- no_error_log
[error]



=== TEST 3: SHA-256 empty string
--- http_config eval: $::HttpConfig
--- config
    location /t {
        content_by_lua '
            local resty_sha256 = require "resty.sha256"
            local str = require "resty.string"
            local sha256 = resty_sha256:new()
            ngx.say(sha256:update(""))
            local digest = sha256:final()
            ngx.say("sha256: ", str.to_hex(digest))
        ';
    }
--- request
GET /t
--- response_body
true
sha256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
--- no_error_log
[error]
