# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua 'no_plan';
use Cwd qw(cwd);


my $pwd = cwd();

my $use_luacov = $ENV{'TEST_NGINX_USE_LUACOV'} // '';

our $HttpConfig = qq{
    lua_package_path "$pwd/lib/?.lua;$pwd/lib/?/init.lua;;";
    init_by_lua_block {
        if "1" == "$use_luacov" then
            require 'luacov.tick'
            jit.off()
        end
    }
};

run_tests();

__DATA__
=== TEST 1: asn1_to_unix utctime
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local ffi = require("ffi")
            local asn1 = require("resty.openssl.asn1")
            local a = ffi.C.ASN1_STRING_type_new(23) -- V_ASN1_UTCTIME
            ffi.gc(a, ffi.C.ASN1_STRING_free)
            local s = "200115123456Z"
            ffi.C.ASN1_STRING_set(a, s, #s)

            ngx.print(assert(asn1.asn1_to_unix(a)))
        }
    }
--- request
    GET /t
--- response_body eval
"1579091696"
--- no_error_log
[error]

=== TEST 2: asn1_to_unix utctime, offset
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local ffi = require("ffi")
            local asn1 = require("resty.openssl.asn1")
            local a = ffi.C.ASN1_STRING_type_new(23) -- V_ASN1_UTCTIME
            ffi.gc(a, ffi.C.ASN1_STRING_free)
            local s = "200115123456+0102"
            ffi.C.ASN1_STRING_set(a, s, #s)

            ngx.print(assert(asn1.asn1_to_unix(a)))
        }
    }
--- request
    GET /t
--- response_body eval
"1579095416"
--- no_error_log
[error]

=== TEST 3: asn1_to_unix generalized time
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local ffi = require("ffi")
            local asn1 = require("resty.openssl.asn1")
            local a = ffi.C.ASN1_STRING_type_new(24) -- V_ASN1_GENERALIZEDTIME
            ffi.gc(a, ffi.C.ASN1_STRING_free)
            local s = "22200115123456Z"
            ffi.C.ASN1_STRING_set(a, s, #s)

            ngx.print(assert(asn1.asn1_to_unix(a)))
        }
    }
--- request
    GET /t
--- response_body eval
"7890438896"
--- no_error_log
[error]

=== TEST 4: asn1_to_unix generalized time, offset
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local ffi = require("ffi")
            local asn1 = require("resty.openssl.asn1")
            local a = ffi.C.ASN1_STRING_type_new(24) -- V_ASN1_GENERALIZEDTIME
            ffi.gc(a, ffi.C.ASN1_STRING_free)
            local s = "22200115123456-0123"
            ffi.C.ASN1_STRING_set(a, s, #s)

            ngx.print(assert(asn1.asn1_to_unix(a)))
        }
    }
--- request
    GET /t
--- response_body eval
"7890433916"
--- no_error_log
[error]

=== TEST 5: asn1_to_unix error on bad format
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local ffi = require("ffi")
            local asn1 = require("resty.openssl.asn1")
            local a = ffi.C.ASN1_STRING_type_new(24) -- V_ASN1_UTCTIME
            ffi.gc(a, ffi.C.ASN1_STRING_free)
            for _, s in pairs({
                "201315123456Z",
                "200132123456Z",
                "200115243456Z",
                "200115123461Z",
            }) do
                ffi.C.ASN1_STRING_set(a, s, #s)

                local _, err = asn1.asn1_to_unix(a)
                if err == nil then
                    ngx.say(s, " should fail but didn't")
                end
            end
        }
    }
--- request
    GET /t
--- response_body eval
""
--- no_error_log
[error]
