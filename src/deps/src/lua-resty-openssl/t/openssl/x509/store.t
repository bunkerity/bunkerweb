# vim:set ft= ts=4 sw=4 et fdm=marker:

use Test::Nginx::Socket::Lua 'no_plan';
use Cwd qw(cwd);


my $pwd = cwd();

my $use_luacov = $ENV{'TEST_NGINX_USE_LUACOV'} // '';

our $HttpConfig = qq{
    lua_package_path "$pwd/t/openssl/?.lua;$pwd/t/openssl/x509/?.lua;$pwd/lib/?.lua;$pwd/lib/?/init.lua;;";
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
=== TEST 1: Creates store properly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local store = require("resty.openssl.x509.store")
            local c = myassert(store.new())
        }
    }
--- request
    GET /t
--- response_body eval
""
--- no_error_log
[error]


=== TEST 2: Loads a x509 object
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local cert, key = require("helper").create_self_signed()
            local store = require("resty.openssl.x509.store")
            local s = myassert(store.new())

            local ok = myassert(s:add(cert))
        }
    }
--- request
    GET /t
--- response_body eval
""
--- no_error_log
[error]

=== TEST 3: Loads default location
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local store = require("resty.openssl.x509.store")
            local s = myassert(store.new())
            myassert(s:use_default())
        }
    }
--- request
    GET /t
--- response_body eval
""
--- no_error_log
[error]

=== TEST 4: Loads file
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local store = require("resty.openssl.x509.store")
            local s = myassert(store.new())

            local ok, err = s:load_file("certnonexistent.pem")
            ngx.say(ok)
            ngx.say(err)
            os.execute("echo > cert4-empty.pem")
            local ok, err = s:load_file("cert4-empty.pem")
            ngx.say(ok)
            -- we only get detailed error for "no certificate found" on >= 1.1.1
            ngx.say(err)
            os.remove("cert4-empty.pem")
            local cert, _ = require("helper").create_self_signed()
            local f = io.open("cert4.pem", "w")
            f:write(cert:tostring())
            f:close()
            local ok = myassert(s:load_file("cert4.pem"))
            os.remove("cert4.pem")
        }
    }
--- request
    GET /t
--- response_body_like eval
"false
x509.store:load_file.+system lib.*
false
x509.store:load_file.+
"
--- no_error_log
[error]


=== TEST 5: Verifies a x509 object
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local cert1, key1 = require("helper").create_self_signed()
            local cert2, key2 = require("helper").create_self_signed()
            local cert3, key3 = require("helper").create_self_signed()
            local store = require("resty.openssl.x509.store")
            local s = myassert(store.new())

            local ok = myassert(s:add(cert1))

            local ok = myassert(s:add(cert2))

            local chain = myassert(s:verify(cert1, nil, true))

            ngx.say(#chain)
            local chain, err = s:verify(cert3, nil, true)
            ngx.say(err)
            ngx.say(chain == nil)
        }
    }
--- request
    GET /t
--- response_body_like eval
"1
(?:self signed|self-signed) certificate
true
"
--- no_error_log
[error]


=== TEST 6: Using default CAs (skip due to hard to setup on custom-built openssl env)
--- SKIP
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local store = require("resty.openssl.x509.store")
            local s = myassert(store.new())

            local ok = myassert(s:use_default())

            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local chain = myassert(s:verify(c, nil, true))

            ngx.say(#chain)
        }
    }
--- request
    GET /t
--- response_body_like eval
"1
"
--- no_error_log
[error]

=== TEST 7: Loads directory
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local store = require("resty.openssl.x509.store")
            local s = myassert(store.new())

            local ok = myassert(s:load_directory("/etc/ssl/certs"))

            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local chain = myassert(s:verify(c, nil, true))
            ngx.say(#chain)
        }
    }
--- request
    GET /t
--- response_body_like eval
"1
"
--- no_error_log
[error]

=== TEST 8: Verifies sub cert
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local helper = require("helper")
            local x509 = require("resty.openssl.x509")
            local store = require("resty.openssl.x509.store")
            local s = myassert(store.new())

            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c = myassert(x509.new(f))
            ngx.say(helper.to_hex(c:digest()))

            local chain = myassert(s:add(c))

            local f = io.open("t/fixtures/GlobalSign_sub.pem"):read("*a")
            local c = myassert(x509.new(f))
            ngx.say(helper.to_hex(c:digest()))

            local chain = myassert(s:verify(c, nil, true))

            for _, c in ipairs(chain) do
                ngx.say(helper.to_hex(c:digest()))
            end
        }
    }
--- request
    GET /t
--- response_body eval
"B1BC968BD4F49D622AA89A81F2150152A41D829C
C187B85714202A2941E8EAFB846C39EB1F9C609A
C187B85714202A2941E8EAFB846C39EB1F9C609A
B1BC968BD4F49D622AA89A81F2150152A41D829C
"
--- no_error_log
[error]

=== TEST 9: Set purpose
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local helper = require("helper")
            local x509 = require("resty.openssl.x509")
            local store = require("resty.openssl.x509.store")
            local s = myassert(store.new())

            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c = myassert(x509.new(f))

            local chain = myassert(s:add(c))

            local f = io.open("t/fixtures/GlobalSign_sub.pem"):read("*a")
            local c = myassert(x509.new(f))

            myassert(s:set_purpose("sslclient"))

            local ok, err = s:verify(c, nil, false)
            ngx.say(ok, err)

            myassert(s:set_purpose("crlsign"))

            local ok, err = s:verify(c, nil, false)
            ngx.say(ok, err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"nil(?:unsupported|unsuitable) certificate purpose
truenil
"
--- no_error_log
[error]

=== TEST 10: Set depth
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local helper = require "t.openssl.helper"
            local store = require("resty.openssl.x509.store")
            local chain = require("resty.openssl.x509.chain")

            local certs, keys = helper.create_cert_chain(5, { type = 'EC', curve = "prime256v1" })
            local s = myassert(store.new())
            myassert(s:add(certs[1]))
            local ch = chain.new()
            for i=2, #certs-1 do
                myassert(ch:add(certs[i]))
            end
            -- should be ok
            ngx.say(s:verify(certs[#certs], ch))

            -- in openssl < 1.1.0, depth are counted 1 more than later versions
            -- we set it to be one less than enough to be prune to that case
            myassert(s:set_depth(1))
            -- openssl 1.0.2 will emit "unable to get local issuer certificate"
            -- instead of "certificate chain too long"
            ngx.say(s:verify(certs[#certs], ch))
        }
    }
--- request
    GET /t
--- response_body_like eval
"truenil
nil(?:certificate chain too long|unable to get local issuer certificate)
"
--- no_error_log
[error]

=== TEST 11: Verify with verify_method
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local helper = require("helper")
            local x509 = require("resty.openssl.x509")
            local store = require("resty.openssl.x509.store")
            local s = myassert(store.new())

            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c = myassert(x509.new(f))

            local chain = myassert(s:add(c))

            local f = io.open("t/fixtures/GlobalSign_sub.pem"):read("*a")
            local c = myassert(x509.new(f))

            local ok, err = s:verify(c, nil, false, nil, "ssl_client")
            ngx.say(ok, err)

            local ok, err = s:verify(c, nil, false, nil, "default")
            ngx.say(ok, err)

            myassert(s:set_purpose("sslclient"))
            local ok, err = s:verify(c, nil, false, nil, "default")
            ngx.say(ok, err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"nil(?:unsupported|unsuitable) certificate purpose
truenil
nil(?:unsupported|unsuitable) certificate purpose
"
--- no_error_log
[error]

=== TEST 12: Set flags
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local helper = require "t.openssl.helper"
            local store = require("resty.openssl.x509.store")
            local chain = require("resty.openssl.x509.chain")

            local certs, keys = helper.create_cert_chain(5, { type = 'EC', curve = "prime256v1" })
            local s = myassert(store.new())
            myassert(s:add(certs[2]))
            local ch = chain.new()
            for i=3, #certs-1 do
                myassert(ch:add(certs[i]))
            end
            -- should not be ok, need root CA
            ngx.say(s:verify(certs[#certs], ch))

            myassert(s:set_flags(s.verify_flags.X509_V_FLAG_PARTIAL_CHAIN))
            ngx.say(s:verify(certs[#certs], ch))
        }
    }
--- request
    GET /t
--- response_body_like eval
"nilunable to get issuer certificate
truenil
"
--- no_error_log
[error]

=== TEST 13: Set verify time flags
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local helper = require "t.openssl.helper"
            local store = require("resty.openssl.x509.store")
            local chain = require("resty.openssl.x509.chain")

            local certs, keys = helper.create_cert_chain(5, { type = 'EC', curve = "prime256v1" })
            local s = myassert(store.new())
            myassert(s:add(certs[2]))
            local ch = chain.new()
            for i=3, #certs-1 do
                myassert(ch:add(certs[i]))
            end
            -- should not be ok, need root CA
            ngx.say(s:verify(certs[#certs], ch))

            ngx.say(s:verify(certs[#certs], ch, false, nil, nil, s.verify_flags.X509_V_FLAG_PARTIAL_CHAIN))
        }
    }
--- request
    GET /t
--- response_body_like eval
"nilunable to get issuer certificate
truenil
"
--- no_error_log
[error]
