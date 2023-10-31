# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua 'no_plan';
use Cwd qw(cwd);


my $pwd = cwd();

my $use_luacov = $ENV{'TEST_NGINX_USE_LUACOV'} // '';
my $fips = $ENV{'TEST_NGINX_FIPS'} // '';

our $HttpConfig = qq{
    lua_package_path "$pwd/t/openssl/?.lua;$pwd/t/openssl/x509/?.lua;$pwd/lib/?.lua;$pwd/lib/?/init.lua;;";
    init_by_lua_block {
        if "1" == "$use_luacov" then
            require 'luacov.tick'
            jit.off()
        end

        _G.myassert = require("helper").myassert
        _G.fips = "$fips" ~= ""
    }
};

run_tests();

__DATA__
=== TEST 1: FIPS mode can be turned on and off
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not _G.fips then
                ngx.say("false\ntrue\nfalse")
                ngx.exit(200)
            end
            local openssl = require("resty.openssl")
            if require("resty.openssl.version").BORINGSSL then
                if openssl.get_fips_mode() then
                    ngx.say("false\ntrue\nfalse")
                else
                    ngx.say("BORINGSSL should have fips turned on but actually not")
                end
                ngx.exit(200)
            end
            ngx.say(openssl.get_fips_mode())
            myassert(openssl.set_fips_mode(true))
            ngx.say(openssl.get_fips_mode())
            myassert(openssl.set_fips_mode(false))
            ngx.say(openssl.get_fips_mode())
        }
    }
--- request
    GET /t
--- response_body
false
true
false
--- no_error_log
[error]

=== TEST 2: CIPHER, MD and PKEY provider is directed to fips
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not _G.fips or not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("fips\nfips\nfips")
                ngx.exit(200)
            end
            local openssl = require("resty.openssl")
            myassert(openssl.set_fips_mode(true))

            ngx.say(myassert(require("resty.openssl.cipher").new("aes256")):get_provider_name())
            ngx.say(myassert(require("resty.openssl.digest").new("sha256")):get_provider_name())
            ngx.say(myassert(require("resty.openssl.pkey").new({ type = "EC" })):get_provider_name())
        }
    }
--- request
    GET /t
--- response_body
fips
fips
fips
--- no_error_log
[error]

=== TEST 3: Non-FIPS compliant algorithms are not allowed
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            -- BORINGSSL doesn't seem to remove non-fips compliant algorithms?
            if not _G.fips or require("resty.openssl.version").BORINGSSL then
                ngx.say("true\ntrue")
                ngx.say("invalid cipher type \"chacha20\": unsupported")
                ngx.say("invalid digest type \"md5\": unsupported")
                ngx.exit(200)
            end

            local ok, err
            if require("resty.openssl.version").OPENSSL_3X then
                ok, err = require("resty.openssl.cipher").new("chacha20")
            else
                ok, err = require("resty.openssl.cipher").new("seed")
            end
            ngx.say(not not ok)
            local ok, err = require("resty.openssl.digest").new("md5")
            ngx.say(not not ok)

            local openssl = require("resty.openssl")
            myassert(openssl.set_fips_mode(true))

            if require("resty.openssl.version").OPENSSL_3X then
                ok, err = require("resty.openssl.cipher").new("chacha20")
            else
                ok, err = require("resty.openssl.cipher").new("seed")
            end
            ngx.say(err)
            local ok, err = require("resty.openssl.digest").new("md5")
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body_like
true
true
.*invalid cipher type.+(?:unsupported|disabled for fips).*
.*invalid digest type "md5".+(?:unsupported|disabled for fips).*
--- no_error_log
[error]
