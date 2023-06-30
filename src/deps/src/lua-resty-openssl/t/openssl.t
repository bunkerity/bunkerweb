# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua 'no_plan';
use Cwd qw(cwd);


my $pwd = cwd();

my $use_luacov = $ENV{'TEST_NGINX_USE_LUACOV'} // '';
my $fips = $ENV{'TEST_NGINX_FIPS'} // '';

our $HttpConfig = qq{
    lua_package_path "$pwd/lib/?.lua;$pwd/lib/?/init.lua;$pwd/../lua-resty-hmac/lib/?.lua;$pwd/../lua-resty-string/lib/?.lua;;";
    init_by_lua_block {
        if "1" == "$use_luacov" then
            require 'luacov.tick'
            jit.off()
        end

        _G.fips = "$fips" ~= ""
    }
};

run_tests();

__DATA__
=== TEST 1: Load ffi openssl library
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local openssl = require("resty.openssl")
            openssl.load_modules()
            ngx.say(string.format("%x", openssl.version.version_num))
        }
    }
--- request
    GET /t
--- response_body_like
\d{6}[0-9a-f][0f]
--- no_error_log
[error]


=== TEST 2: Luaossl compat pattern
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local openssl = require("resty.openssl")
            openssl.luaossl_compat()
            local pkey = require("resty.openssl.pkey")
            local pok, perr = pcall(pkey.new, "not a key")
            ngx.say(pok)
            ngx.say(perr)
        }
    }
--- request
    GET /t
--- response_body_like
false
.+pkey.new.+
--- no_error_log
[error]


=== TEST 3: List cipher algorithms
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if version.BORINGSSL then
                ngx.say("[\"AES\"]")
                ngx.say("[\"AES-256-GCM @ default\"]")
                ngx.exit(0)
            end
            local openssl = require("resty.openssl")
            ngx.say(require("cjson").encode(openssl.list_cipher_algorithms()))
            if not version.OPENSSL_3X then
                ngx.say("[\"AES-256-GCM @ default\"]")
                ngx.exit(0)
            end
            ngx.say(require("cjson").encode(openssl.list_cipher_algorithms()))
        }
    }
--- request
    GET /t
--- response_body_like
\[.+AES.+\]
\[.+AES-256-GCM @ default.+\]
--- no_error_log
[error]

=== TEST 4: List digest algorithms
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if version.BORINGSSL then
                ngx.say("[\"SHA\"]")
                ngx.say("[\"SHA2-256 @ default\"]")
                ngx.exit(0)
            end
            local openssl = require("resty.openssl")
            ngx.say(require("cjson").encode(openssl.list_digest_algorithms()))
            if not version.OPENSSL_3X then
                ngx.say("[\"SHA2-256 @ default\"]")
                ngx.exit(0)
            end
            ngx.say(require("cjson").encode(openssl.list_digest_algorithms()))
        }
    }
--- request
    GET /t
--- response_body_like
\[.+SHA.+\]
\[.+SHA2-256 @ default.+\]
--- no_error_log
[error]

=== TEST 5: List mac algorithms
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if not version.OPENSSL_3X then
                ngx.say("[\"HMAC @ default\"]")
                ngx.exit(0)
            end
            local openssl = require("resty.openssl")
            ngx.say(require("cjson").encode(openssl.list_mac_algorithms()))
        }
    }
--- request
    GET /t
--- response_body_like
\[.+HMAC @ default.+\]
--- no_error_log
[error]

=== TEST 6: List kdf algorithms
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if not version.OPENSSL_3X then
                ngx.say("[\"HKDF @ default\"]")
                ngx.exit(0)
            end
            local openssl = require("resty.openssl")
            ngx.say(require("cjson").encode(openssl.list_kdf_algorithms()))
        }
    }
--- request
    GET /t
--- response_body_like
\[.+HKDF @ default.+\]
--- no_error_log
[error]

=== TEST 7: List SSL cipher
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if version.OPENSSL_10 or (version.OPENSSL_11 and not version.OPENSSL_111) then
                ngx.say("ECDHE-ECDSA-AES128-SHA:ECDHE-ECDSA-AES128-SHA")
                ngx.say("ECDHE-ECDSA-AES128-SHA:ECDHE-ECDSA-AES128-SHA")
                ngx.say("ECDHE-ECDSA-AES128-SHA:ECDHE-ECDSA-AES128-SHA")
                ngx.say("ECDHE-ECDSA-AES128-SHA:ECDHE-ECDSA-AES128-SHA")
                ngx.exit(0)
            end
            local version = require("resty.openssl.version")
            local openssl = require("resty.openssl")
            ngx.say(openssl.list_ssl_ciphers())
            ngx.say(openssl.list_ssl_ciphers("ECDHE-ECDSA-AES128-SHA"))
            ngx.say(openssl.list_ssl_ciphers("ECDHE-ECDSA-AES128-SHA", nil, "TLSv1.2"))
            ngx.say(openssl.list_ssl_ciphers("ECDHE-ECDSA-AES128-SHA", nil, "TLSv1.3"))
        }
    }
--- request
    GET /t
--- response_body_like
.+:.+
.*ECDHE-ECDSA-AES128-SHA
.*ECDHE-ECDSA-AES128-SHA
.*ECDHE-ECDSA-AES128-SHA
--- no_error_log
[error]
