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
        _G.encode_sorted_json = require("helper").encode_sorted_json
    }
};

run_tests();

__DATA__
=== TEST 1: Loads password protected pkcs12
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if require("resty.openssl.version").OPENSSL_3X then
                local pro = require "resty.openssl.provider"
                myassert(pro.load("legacy"))
            end

            local pkcs12 = require "resty.openssl.pkcs12"

            local pp = io.open("t/fixtures/badssl.com-client.p12"):read("*a")

            local r = myassert(pkcs12.decode(pp, "badssl.com"))

            ngx.say(r.key:get_parameters().d:to_hex():upper())
            ngx.say(r.cert:get_serial_number():to_hex():upper())
        }
    }
--- request
    GET /t
--- response_body
55107FB7D6FD8A099E4E5CF24291CF20CBD4BB7B93A66EF8D89996A5C49EEB51405E6843CC89CD74B9C87DB9DBDE9E38923E02A32E4F6F32A59B4D6C6CDC40E0192204F135C9E9F527FD9E53F2C9E90B8D8D18E8F5DAC57D1EF95163D0DF1BBDB89850636AE870B20B5E6BF2EBD1651BE79B4E187C48F6D332D35A4C531BE3B027A64D85AD6F7EAF33ECC1B9253B196CFD20EDEFCBAC46F7C08EC966EF721D0533AB6DC785F86998B37FD25F3D60BB4E692F1636AE10BCA62065AA70FF41B5C16A165B8636FD4A40C59F6B72A4C1592A424820A0C968E23613DB48959F7BFF49D9B71A9C84CB72F08B94F586007CB5C29A3D8811F9EF2ED2FBB612DF28BB9601
2B936CE32D82CE8B01FD9A0595AC6366AA014C82
--- no_error_log
[error]

=== TEST 2: Errors on bad password
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if require("resty.openssl.version").OPENSSL_3X then
                local pro = require "resty.openssl.provider"
                myassert(pro.load("legacy"))
            end

            local pkcs12 = require "resty.openssl.pkcs12"

            local pp = io.open("t/fixtures/badssl.com-client.p12"):read("*a")

            local r, err = pkcs12.decode(pp, "wrong password")
            ngx.say(r == nil)
            ngx.say(err)

            local r, err = pkcs12.decode(pp)
            ngx.say(r == nil)
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
'true
pkcs12.decode.+(mac verify failure|INCORRECT_PASSWORD)
true
pkcs12.decode.+(mac verify failure|INCORRECT_PASSWORD)
'
--- no_error_log
[error]

=== TEST 3: Creates pkcs12
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if require("resty.openssl.version").OPENSSL_3X then
                local pro = require "resty.openssl.provider"
                myassert(pro.load("legacy"))
            end

            local pkcs12 = require "resty.openssl.pkcs12"
            local cert, key = require("helper").create_self_signed({ type = 'EC', curve = "prime256v1" })
            local x509 = require("resty.openssl.x509")
            local ca1 = myassert(x509.new(io.open("t/fixtures/GlobalSign.pem"):read("*a")))
            local ca2 = myassert(x509.new(io.open("t/fixtures/GlobalSign_sub.pem"):read("*a")))
            
            -- full house
            local r = myassert(pkcs12.encode({
                friendly_name = "myname",
                key = key,
                cert = cert,
                cacerts = { ca1, ca2 }
            }, "test-pkcs12"))
            ngx.say(#r)
            -- no name
            local r = myassert(pkcs12.encode({
                key = key,
                cert = cert,
                cacerts = { ca1, ca2 }
            }, "test-pkcs12"))
            ngx.say(#r)
            -- no CA
            local r = myassert(pkcs12.encode({
                key = key,
                cert = cert,
            }, "test-pkcs12"))
            ngx.say(#r)
            -- empty password
            local r = myassert(pkcs12.encode({
                key = key,
                cert = cert,
            }))
            ngx.say(#r)
        }
    }
--- request
    GET /t
--- response_body_like eval
'\d{3,4}
\d{3,4}
\d{3,4}
\d{3,4}
'
--- no_error_log
[error]

=== TEST 4: Uses empty string password when omitted
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if require("resty.openssl.version").OPENSSL_3X then
                local pro = require "resty.openssl.provider"
                myassert(pro.load("legacy"))
            end
    
            local pkcs12 = require "resty.openssl.pkcs12"
            local cert, key = require("helper").create_self_signed({ type = 'EC', curve = "prime256v1" })
            local x509 = require("resty.openssl.x509")
            local ca1 = myassert(x509.new(io.open("t/fixtures/GlobalSign.pem"):read("*a")))
            local ca2 = myassert(x509.new(io.open("t/fixtures/GlobalSign_sub.pem"):read("*a")))
            
            local p12 = myassert(pkcs12.encode({
                friendly_name = "myname",
                key = key,
                cert = cert,
                cacerts = { ca1, ca2 },
            }))

            local r = myassert(pkcs12.decode(p12, nil))
            ngx.say(#r.key:get_parameters().x:to_hex():upper())
            ngx.say(r.cert:get_serial_number():to_hex():upper())
            ngx.say(#r.cacerts)
            ngx.say(r.friendly_name)
            -- same as empty string
            local r = myassert(pkcs12.decode(p12, ""))

            -- password mismatch
            local r, err = pkcs12.decode(p12, "extrapassword")
            ngx.say(r == nil)
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
'6\d
0
2
myname
true
pkcs12.decode.+(mac verify failure|INCORRECT_PASSWORD)
'
--- no_error_log
[error]

=== TEST 5: Check cert and key mismatch
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if require("resty.openssl.version").OPENSSL_3X then
                local pro = require "resty.openssl.provider"
                myassert(pro.load("legacy"))
            end

            local pkcs12 = require "resty.openssl.pkcs12"
            local cert, key = require("helper").create_self_signed({ type = 'EC', curve = "prime256v1" })
            local key2 = require("resty.openssl.pkey").new({ type = 'EC', curve = "prime256v1" })
            
            local r, err = pkcs12.encode({
                friendly_name = "myname",
                key = key2,
                cert = cert,
                cacerts = { ca1, ca2 }
            }, "test-pkcs12")
            ngx.say(r == nil, err)
        }
    }
--- request
    GET /t
--- response_body_like eval
'true.+(key values mismatch|KEY_VALUES_MISMATCH)
'
--- no_error_log
[error]

=== TEST 6: Creates pkcs12 with newer algorithm
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if require("resty.openssl.version").BORINGSSL then
                ngx.say("2333")
                ngx.exit(0)
            end

            -- don't load the legacy provider for this test
            -- by default nid_key is RC2 and is moved to legacy provider in 3.0

            local pkcs12 = require "resty.openssl.pkcs12"
            local cert, key = require("helper").create_self_signed({ type = 'EC', curve = "prime256v1" })
            local x509 = require("resty.openssl.x509")
            local ca1 = myassert(x509.new(io.open("t/fixtures/GlobalSign.pem"):read("*a")))
            local ca2 = myassert(x509.new(io.open("t/fixtures/GlobalSign_sub.pem"):read("*a")))
            
            local r = myassert(pkcs12.encode({
                friendly_name = "myname",
                key = key,
                cert = cert,
                cacerts = { ca1, ca2 },
                nid_key = "aes-128-cbc",
                nid_cert = "aes-128-cbc",
                mac_iter = 2000,
            }, "test-pkcs12"))
            ngx.say(#r)
        }
    }
--- request
    GET /t
--- response_body_like eval
'\d{3,4}
'
--- no_error_log
[error]
