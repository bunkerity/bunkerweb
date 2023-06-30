# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua 'no_plan';
use Cwd qw(cwd);


my $pwd = cwd();

my $use_luacov = $ENV{'TEST_NGINX_USE_LUACOV'} // '';

our $HttpConfig = qq{
    lua_package_path "$pwd/t/openssl/?.lua;$pwd/lib/?.lua;$pwd/lib/?/init.lua;;";
    init_by_lua_block {
        if "1" == "$use_luacov" then
            require 'luacov.tick'
            jit.off()
        end
        _G.myassert = require("helper").myassert
    }
};

run_tests();

__DATA__
=== TEST 1: Calculate mac correctly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("kwUMjYrP0BSJb8cIJvWYoiM1Kc4mQxZOTwSiTTLRhDM=")
                ngx.exit(0)
            end

            local mac = myassert(require("resty.openssl.mac").new("goose", "HMAC", nil, "sha256"))

            myassert(mac:update("🦢🦢🦢🦢🦢🦢"))
            ngx.print(ngx.encode_base64(myassert(mac:final())))
        }
    }
--- request
    GET /t
--- response_body_like eval
"kwUMjYrP0BSJb8cIJvWYoiM1Kc4mQxZOTwSiTTLRhDM="
--- no_error_log
[error]

=== TEST 2: Update accepts vardiac args
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("kwUMjYrP0BSJb8cIJvWYoiM1Kc4mQxZOTwSiTTLRhDM=")
                ngx.exit(0)
            end

            local mac = myassert(require("resty.openssl.mac").new("goose", "HMAC", nil, "sha256"))

            mac:update("🦢", "🦢🦢", "🦢🦢", "🦢")
            ngx.print(ngx.encode_base64(mac:final()))
        }
    }
--- request
    GET /t
--- response_body_like eval
"kwUMjYrP0BSJb8cIJvWYoiM1Kc4mQxZOTwSiTTLRhDM="
--- no_error_log
[error]

=== TEST 3: Final accepts optional arg
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("kwUMjYrP0BSJb8cIJvWYoiM1Kc4mQxZOTwSiTTLRhDM=")
                ngx.exit(0)
            end

            local mac = myassert(require("resty.openssl.mac").new("goose", "HMAC", nil, "sha256"))

            myassert(mac:update("🦢", "🦢🦢", "🦢🦢"))
            ngx.print(ngx.encode_base64(myassert(mac:final("🦢"))))
        }
    }
--- request
    GET /t
--- response_body_like eval
"kwUMjYrP0BSJb8cIJvWYoiM1Kc4mQxZOTwSiTTLRhDM="
--- no_error_log
[error]

=== TEST 4: Rejects unknown hash
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("mac.new: invalid cipher or digest type")
                ngx.exit(0)
            end
            local mac, err = require("resty.openssl.mac").new("goose", "HMAC", nil, "sha257")
            ngx.print(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"mac.new: invalid cipher or digest type.*"
--- no_error_log
[error]

=== TEST 5: Returns provider
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("default")
                ngx.exit(0)
            end

            local mac = require("resty.openssl.mac")
            local m = myassert(mac.new("goose", "HMAC", nil, "sha256"))
            ngx.say(myassert(m:get_provider_name()))
        }
    }
--- request
    GET /t
--- response_body
default
--- no_error_log
[error]

=== TEST 6: Returns gettable, settable params
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("-size-\n-digest-")
                ngx.exit(0)
            end

            local mac = require("resty.openssl.mac")
            local m = myassert(mac.new("goose", "HMAC", nil, "sha256"))
            ngx.say(require("cjson").encode(myassert(m:gettable_params())))
            ngx.say(require("cjson").encode(myassert(m:settable_params())))
        }
    }
--- request
    GET /t
--- response_body_like
.+size.+
.+digest.+
--- no_error_log
[error]

=== TEST 7: Get params, set params
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("true\n32")
                ngx.exit(0)
            end

            local mac = myassert(require("resty.openssl.mac").new("goose", "HMAC", nil, "sha256"))
            local s1 = myassert(mac:final("🦢"))

            local mac = myassert(require("resty.openssl.mac").new("notthiskey", "HMAC", nil, "sha256"))
            myassert(mac:set_params({key = "goose"}))
            local s2 = myassert(mac:final("🦢"))

            ngx.say(s1 == s2)
            ngx.say(myassert(mac:get_param("size")))
        }
    }
--- request
    GET /t
--- response_body eval
"true
32
"
--- no_error_log
[error]
