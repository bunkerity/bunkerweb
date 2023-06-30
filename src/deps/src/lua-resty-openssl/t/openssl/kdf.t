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
=== TEST 1: kdf: invalid args are checked
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local kdf = require("resty.openssl.kdf")
            local key, err = kdf.derive({
            })
            ngx.say(err)
            local key, err = kdf.derive({
                type = "no",
            })
            ngx.say(err)
            local key, err = kdf.derive({
                type = kdf.PBKDF2,
            })
            ngx.say(err)
            local key, err = kdf.derive({
                type = kdf.PBKDF2,
                outlen = 16,
                pass = 123,
            })
            ngx.say(err)
            local key, err = kdf.derive({
                type = 19823718236128631,
                outlen = 16,
                pass = "123",
            })
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"kdf.derive: \"type\" must be set
kdf.derive: expect a number as \"type\"
kdf.derive: \"outlen\" must be set
kdf.derive: except a string as \"pass\"
kdf.derive: unknown type 19823718236128632
"
--- no_error_log
[error]


=== TEST 2: PBKDF2
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {

            local kdf = require("resty.openssl.kdf")
            local key = myassert(kdf.derive({
                type = kdf.PBKDF2,
                outlen = 16,
                pass = "1234567",
                pbkdf2_iter = 1000,
                md = "md5",
            }))

            ngx.print(ngx.encode_base64(key))
        }
    }
--- request
    GET /t
--- response_body_like eval
"cDRFLQ7NWt\\+AP4i0TdBzog=="
--- no_error_log
[error]


=== TEST 3: PBKDF2, optional args
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local kdf = require("resty.openssl.kdf")
            local key = myassert(kdf.derive({
                type = kdf.PBKDF2,
                outlen = 16,
            }))

            ngx.print(ngx.encode_base64(key))
        }
    }
--- request
    GET /t
--- response_body_like eval
"HkN6HHnXW\\+YekRQdriCv/A=="
--- no_error_log
[error]


=== TEST 4: HKDF
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if version.BORINGSSL or not version.OPENSSL_11_OR_LATER then
                ngx.print("aqRd+gO5Ok3YneDEormTcg==")
                ngx.exit(0)
            end
            local kdf = require("resty.openssl.kdf")
            local key = myassert(kdf.derive({
                type = kdf.HKDF,
                outlen = 16,
                md = "md5",
                salt = "salt",
                hkdf_key = "secret",
                hkdf_info = "some info",
                hkdf_mode = kdf.HKDEF_MODE_EXTRACT_AND_EXPAND,
            }))

            ngx.print(ngx.encode_base64(key))
        }
    }
--- request
    GET /t
--- response_body eval
"aqRd+gO5Ok3YneDEormTcg=="
--- no_error_log
[error]


=== TEST 5: HKDF, optional arg
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if version.BORINGSSL or not version.OPENSSL_11_OR_LATER then
                ngx.say("aggdq4eoqRiP0Z3GbpxCjg==")
                ngx.say("W/tSxFnNsHIYwXa13eybYhW9W3Y=")
                ngx.exit(0)
            end
            local version_num = version.version_num
            local kdf = require("resty.openssl.kdf")
            local key = myassert(kdf.derive({
                type = kdf.HKDF,
                outlen = 16,
                salt = "salt",
                hkdf_key = "secret",
                hkdf_info = "info",
            }))

            ngx.say(ngx.encode_base64(key))

            if not version.OPENSSL_111_or_LATER then
                ngx.say("W/tSxFnNsHIYwXa13eybYhW9W3Y=")
                ngx.exit(0)
            end
            local key = myassert(kdf.derive({
                type = kdf.HKDF,
                outlen = 16,
                salt = "salt",
                hkdf_key = "secret",
                hkdf_mode = kdf.HKDEF_MODE_EXTRACT_ONLY,
            }))

            ngx.say(ngx.encode_base64(key))
        }
    }
--- request
    GET /t
--- response_body_like eval
"aggdq4eoqRiP0Z3GbpxCjg==
W/tSxFnNsHIYwXa13eybYhW9W3Y=
"
--- no_error_log
[error]


=== TEST 6: TLS1-PRF
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if version.BORINGSSL or not version.OPENSSL_11_OR_LATER then
                ngx.print("0xr8qthU+ypv2xRC90la8g==")
                ngx.exit(0)
            end
            local kdf = require("resty.openssl.kdf")
            local key = myassert(kdf.derive({
                type = kdf.TLS1_PRF,
                outlen = 16,
                md = "md5",
                tls1_prf_secret = "secret",
                tls1_prf_seed = "seed",
            }))

            ngx.print(ngx.encode_base64(key))
        }
    }
--- request
    GET /t
--- response_body_like eval
"0xr8qthU\\+ypv2xRC90la8g=="
--- no_error_log
[error]


=== TEST 7: TLS1-PRF, optional arg
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if version.BORINGSSL or not version.OPENSSL_11_OR_LATER then
                ngx.print("XVVDK9/puTqBOsyTKt8PKQ==")
                ngx.exit(0)
            end
            local kdf = require("resty.openssl.kdf")
            local key = myassert(kdf.derive({
                type = kdf.TLS1_PRF,
                outlen = 16,
                tls1_prf_secret = "secret",
                tls1_prf_seed = "seed",
            }))

            ngx.print(ngx.encode_base64(key))
        }
    }
--- request
    GET /t
--- response_body_like eval
"XVVDK9/puTqBOsyTKt8PKQ=="
--- no_error_log
[error]


=== TEST 8: scrypt
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if version.BORINGSSL or not version.OPENSSL_11_OR_LATER then
                ngx.print("9giFtxace5sESmRb8qxuOw==")
                ngx.exit(0)
            end
            local kdf = require("resty.openssl.kdf")
            local key = myassert(kdf.derive({
                type = kdf.SCRYPT,
                outlen = 16,
                pass = "1234567",
                scrypt_N = 1024,
                scrypt_r = 8,
                scrypt_p = 16,
            }))

            ngx.print(ngx.encode_base64(key))
        }
    }
--- request
    GET /t
--- response_body_like eval
"9giFtxace5sESmRb8qxuOw=="
--- no_error_log
[error]

=== TEST 9: EVP_KDF API: new
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say('mac.new: invalid mac type "UNKNOWNKDF": blah')
                ngx.exit(0)
            end
            local kdf = require("resty.openssl.kdf")
            myassert(kdf.new("PBKDF2"))
            local ok, err = kdf.new("UNKNOWNKDF")

            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
".+invalid mac type \"UNKNOWNKDF\".+
"
--- no_error_log
[error]

=== TEST 10: EVP_KDF API: Returns provider
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("default")
                ngx.exit(0)
            end

            local cipher = require("resty.openssl.kdf")
            local c = myassert(cipher.new("hkdf"))
            ngx.say(myassert(c:get_provider_name()))
        }
    }
--- request
    GET /t
--- response_body
default
--- no_error_log
[error]


=== TEST 11: EVP_KDF API: derive
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("cDRFLQ7NWt+AP4i0TdBzog==")
                ngx.exit(0)
            end
            local kdf = require("resty.openssl.kdf")
            local k = myassert(kdf.new("PBKDF2"))
            local key = myassert(k:derive(16, {
                pass = "1234567",
                iter = 1000,
                digest = "md5",
                salt = "",
            }))
            ngx.say(ngx.encode_base64(key))
        }
    }
--- request
    GET /t
--- response_body
cDRFLQ7NWt+AP4i0TdBzog==
--- no_error_log
[error]

=== TEST 12: EVP_KDF API: Returns gettable, settable params
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("-size-\n-digest-")
                ngx.exit(0)
            end

            local kdf = require("resty.openssl.kdf")
            local k = myassert(kdf.new("PBKDF2"))
            ngx.say(require("cjson").encode(myassert(k:gettable_params())))
            ngx.say(require("cjson").encode(myassert(k:settable_params())))
        }
    }
--- request
    GET /t
--- response_body_like
.+size.+
.+digest.+
--- no_error_log
[error]

=== TEST 13: EVP_KDF API: Get params, set params
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("cDRFLQ7NWt+AP4i0TdBzog==\n18446744073709551615")
                ngx.exit(0)
            end
            local kdf = require("resty.openssl.kdf")
            local k = myassert(kdf.new("PBKDF2"))
            myassert(k:set_params({
                iter = 1000,
                digest = "md5",
                salt = "",

            }))
            local key = myassert(k:derive(16, {
                pass = "1234567",
            }))
            ngx.say(ngx.encode_base64(key))
            -- output SIZE_MAX since it's not fixed size, need to find a better test case
            ngx.say(tostring(k:get_param("size", nil, "bn")))
        }
    }
--- request
    GET /t
--- response_body
cDRFLQ7NWt+AP4i0TdBzog==
18446744073709551615
--- no_error_log
[error]

=== TEST 14: EVP_KDF API: reset
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("-missing salt\ncDRFLQ7NWt+AP4i0TdBzog==")
                ngx.exit(0)
            end
            local kdf = require("resty.openssl.kdf")
            local k = myassert(kdf.new("PBKDF2"))
            myassert(k:set_params({
                iter = 1000,
                digest = "md5",
                salt = "",
            }))
            myassert(k:reset())
            local ok, err = k:derive(16, {
                pass = "1234567",
            })
            ngx.say(err)

            myassert(k:set_params({
                iter = 100,
                digest = "md5",
                salt = "",
            }))
            local key = myassert(k:derive(16, {
                iter = 1000,
                pass = "1234567",
            }))
             ngx.say(ngx.encode_base64(key))
        }
    }
--- request
    GET /t
--- response_body_like
.+missing salt
cDRFLQ7NWt\+AP4i0TdBzog==
--- no_error_log
[error]
