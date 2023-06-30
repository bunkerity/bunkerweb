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
=== TEST 1: Calculate hmac correctly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local hmac = myassert(require("resty.openssl.hmac").new("goose", "sha256"))

            myassert(hmac:update("🦢🦢🦢🦢🦢🦢"))
            ngx.print(ngx.encode_base64(myassert(hmac:final())))
        }
    }
--- request
    GET /t
--- response_body eval
"kwUMjYrP0BSJb8cIJvWYoiM1Kc4mQxZOTwSiTTLRhDM="
--- no_error_log
[error]

=== TEST 2: Update accepts vardiac args
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local hmac = myassert(require("resty.openssl.hmac").new("goose", "sha256"))

            hmac:update("🦢", "🦢🦢", "🦢🦢", "🦢")
            ngx.print(ngx.encode_base64(hmac:final()))
        }
    }
--- request
    GET /t
--- response_body eval
"kwUMjYrP0BSJb8cIJvWYoiM1Kc4mQxZOTwSiTTLRhDM="
--- no_error_log
[error]

=== TEST 3: Final accepts optional arg
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local hmac = myassert(require("resty.openssl.hmac").new("goose", "sha256"))

            myassert(hmac:update("🦢", "🦢🦢", "🦢🦢"))
            ngx.print(ngx.encode_base64(myassert(hmac:final("🦢"))))
        }
    }
--- request
    GET /t
--- response_body eval
"kwUMjYrP0BSJb8cIJvWYoiM1Kc4mQxZOTwSiTTLRhDM="
--- no_error_log
[error]

=== TEST 4: Rejects unknown hash
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local hmac, err = require("resty.openssl.hmac").new("goose", "sha257")
            ngx.print(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"hmac.new:.+(?:invalid|unsupported).*"
--- no_error_log
[error]


=== TEST 5: Can be reused
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local hmac = myassert(require("resty.openssl.hmac").new("goose", "sha256"))
            myassert(hmac:update("🦢🦢🦢🦢🦢🦢"))
            ngx.say(ngx.encode_base64(myassert(hmac:final())))

            myassert(hmac:reset())

            myassert(hmac:update("🦢🦢🦢🦢🦢🦢"))
            ngx.say(ngx.encode_base64(myassert(hmac:final())))
        }
    }
--- request
    GET /t
--- response_body eval
"kwUMjYrP0BSJb8cIJvWYoiM1Kc4mQxZOTwSiTTLRhDM=
kwUMjYrP0BSJb8cIJvWYoiM1Kc4mQxZOTwSiTTLRhDM=
"
--- no_error_log
[error]