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
        _G.encode_sorted_json = require("helper").encode_sorted_json
    }
};

no_long_string();

run_tests();

__DATA__
=== TEST 1: Loads a cert
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            ngx.say("ok")
        }
    }
--- request
    GET /t
--- response_body eval
"ok
"
--- no_error_log
[error]

=== TEST 2: Converts and loads PEM format
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local pem = myassert(c:tostring("PEM"))

            for _, typ in ipairs({"PEM", "*", false}) do
              local c2 = myassert(require("resty.openssl.x509").new(pem, typ))
            end
            local c2, err = require("resty.openssl.x509").new(pem, "DER")
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"x509.new.+(nested asn1 error|NESTED_ASN1_ERROR).+"
--- no_error_log
[error]

=== TEST 3: Converts and loads DER format
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local pem = myassert(c:tostring("DER"))

            for _, typ in ipairs({"DER", "*", false}) do
              local c2 = myassert(require("resty.openssl.x509").new(pem, typ))
            end
            local c2, err = require("resty.openssl.x509").new(pem, "PEM")
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"x509.new.+(no start line|NO_START_LINE).+"
--- no_error_log
[error]

=== TEST 4: Rejectes invalid cert
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local x509 = require("resty.openssl.x509")
            local p, err = x509.new(true)
            ngx.say(err)
            p, err = x509.new("222")
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"expect nil or a string at #1
x509.new: .*(not enough data|NOT_ENOUGH_DATA)
"
--- no_error_log
[error]

=== TEST 5: Calculates cert digest
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local dd = myassert(c:digest())

            local h = string.upper(myassert(require("helper").to_hex(dd)))
            ngx.say(h)
        }
    }
--- request
    GET /t
--- response_body eval
"B1BC968BD4F49D622AA89A81F2150152A41D829C
"
--- no_error_log
[error]

=== TEST 6: Calculates pubkey digest
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local dd = myassert(c:pubkey_digest())

            local h, err = string.upper(require("helper").to_hex(dd))
            ngx.say(h)
        }
    }
--- request
    GET /t
--- response_body eval
"607B661A450D97CA89502F7D04CD34A8FFFCFD4B
"
--- no_error_log
[error]

=== TEST 7: Gets extension
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c, err = require("resty.openssl.x509").new(f)
            local ext, pos = c:get_extension("X509v3 Extended Key Usage")

            ngx.say(pos)
            ngx.say(tostring(ext))
        }
    }
--- request
    GET /t
--- response_body eval
"5
TLS Web Server Authentication, TLS Web Client Authentication
"
--- no_error_log
[error]

=== TEST 8: Adds extension
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local c, err = require("resty.openssl.x509").new()
            local ext = myassert(require("resty.openssl.x509.extension").new(
                "extendedKeyUsage", "TLS Web Server Authentication"
            ))

            local ok = myassert(c:add_extension(ext))

            local ext, _ = c:get_extension("X509v3 Extended Key Usage")

            ngx.say(tostring(ext))
        }
    }
--- request
    GET /t
--- response_body eval
"TLS Web Server Authentication
"
--- no_error_log
[error]

=== TEST 9: Set extension
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local ext = myassert(require("resty.openssl.x509.extension").new(
                "keyUsage", "Digital Signature, Key Encipherment"
            ))
            local ok = myassert(c:set_extension(ext))

            local ext, _ = c:get_extension("X509v3 Key Usage")

            ngx.say(tostring(ext))
        }
    }
--- request
    GET /t
--- response_body eval
"Digital Signature, Key Encipherment
"
--- no_error_log
[error]


=== TEST 10: Reads basic constraints
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            ngx.say(c:get_basic_constraints("ca"))
            ngx.say(c:get_basic_constraints("pathlen"))
            collectgarbage("collect")
        }
    }
--- request
    GET /t
--- response_body eval
"true
0
"
--- no_error_log
[error]

=== TEST 11: Set basic constraints
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c, err = require("resty.openssl.x509").new(f)
            local ok = myassert(c:set_basic_constraints({
                CA = false,
                pathLen = 233,
            }))

            ngx.say(c:get_basic_constraints("ca"))
            ngx.say(c:get_basic_constraints("pathlen"))
            collectgarbage("collect")
        }
    }
--- request
    GET /t
--- response_body eval
"false
233
"
--- no_error_log
[error]

=== TEST 12: Get authority info access
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local aia = myassert(c:get_info_access())

            local ffi = require "ffi"
            for _, v in ipairs(aia) do
                ngx.say(ffi.string(ffi.C.OBJ_nid2ln(v[1])), " - ", v[2], ":", v[3])
            end
            collectgarbage("collect")
        }
    }
--- request
    GET /t
--- response_body eval
"OCSP - URI:http://ocsp.digicert.com
CA Issuers - URI:http://cacerts.digicert.com/DigiCertHighAssuranceTLSHybridECCSHA2562020CA1.crt
"
--- no_error_log
[error]

=== TEST 13: Set authority info access
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local aia = myassert(c:get_info_access())
            myassert(aia:add("OCSP", "URI", "http://somedomain.com"))
        
            myassert(c:set_info_access(aia))

            local aia = myassert(c:get_info_access())
            local ffi = require "ffi"
            for _, v in ipairs(aia) do
                ngx.say(ffi.string(ffi.C.OBJ_nid2ln(v[1])), " - ", v[2], ":", v[3])
            end
            collectgarbage("collect")
        }
    }
--- request
    GET /t
--- response_body eval
"OCSP - URI:http://ocsp.digicert.com
CA Issuers - URI:http://cacerts.digicert.com/DigiCertHighAssuranceTLSHybridECCSHA2562020CA1.crt
OCSP - URI:http://somedomain.com
"
--- no_error_log
[error]

=== TEST 14: Get CRL distribution points
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local cdp = myassert(c:get_crl_distribution_points())

            local ffi = require "ffi"
            for _, altname in pairs(cdp) do
                for k, v in pairs(altname) do
                    ngx.say(k, " ", v)
                end
            end
            collectgarbage("collect")
        }
    }
--- request
    GET /t
--- response_body eval
"URI http://crl3.digicert.com/DigiCertHighAssuranceTLSHybridECCSHA2562020CA1.crl
URI http://crl4.digicert.com/DigiCertHighAssuranceTLSHybridECCSHA2562020CA1.crl
"
--- no_error_log
[error]

=== TEST 15: Set CRL distribution points
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            -- NYI
        }
    }
--- request
    GET /t
--- no_error_log
[error]

=== TEST 16: Get OCSP url
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local ocsp = myassert(c:get_ocsp_url())
            ngx.say(ocsp)

            local ocsp = myassert(c:get_ocsp_url(true))
            ngx.say(encode_sorted_json(ocsp))

            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local ocsp = myassert(c:get_ocsp_url())
            ngx.say(ocsp)
        }
    }
--- request
    GET /t
--- response_body eval
'http://ocsp.digicert.com
["http:\/\/ocsp.digicert.com"]
nil
'
--- no_error_log
[error]

=== TEST 17: Get CRL url
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local crl = myassert(c:get_crl_url())
            ngx.say(crl)

            local crl = myassert(c:get_crl_url(true))
            ngx.say(encode_sorted_json(crl))

            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local crl = myassert(c:get_crl_url())
            ngx.say(crl)
        }
    }
--- request
    GET /t
--- response_body eval
'http://crl3.digicert.com/DigiCertHighAssuranceTLSHybridECCSHA2562020CA1.crl
["http:\/\/crl3.digicert.com\/DigiCertHighAssuranceTLSHybridECCSHA2562020CA1.crl","http:\/\/crl4.digicert.com\/DigiCertHighAssuranceTLSHybridECCSHA2562020CA1.crl"]
nil
'
--- no_error_log
[error]

=== TEST 18: Get non existend extension, return nil, nil
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local get = myassert(c:get_subject_alt_name())
            ngx.say(get)
        }
    }
--- request
    GET /t
--- response_body eval
"nil
"
--- no_error_log
[error]

=== TEST 19: Check private key match
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local cert, key = require("helper").create_self_signed({ type = "EC", curve = "prime256v1" })
            local ok, err = cert:check_private_key(key)
            ngx.say(ok)
            ngx.say(err)

            local f = io.open("t/fixtures/GlobalSign.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local ok, err = c:check_private_key(key)
            ngx.say(ok)
            ngx.say(err)

            local key2 = require("resty.openssl.pkey").new({
                type = 'EC',
                curve = "prime256v1",
            })
            local ok, err = cert:check_private_key(key2)
            ngx.say(ok)
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"true
nil
false
.+(key type mismatch|KEY_TYPE_MISMATCH)
.+(key values mismatch|KEY_VALUES_MISMATCH)
"
--- no_error_log
[error]

# START AUTO GENERATED CODE


=== TEST 20: x509:get_serial_number (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local get = myassert(c:get_serial_number())
            get = get:to_hex():upper()
            ngx.print(get)
        }
    }
--- request
    GET /t
--- response_body eval
"0E8BF3770D92D196F0BB61F93C4166BE"
--- no_error_log
[error]

=== TEST 21: x509:set_serial_number (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local toset = myassert(require("resty.openssl.bn").new(math.random(1, 2333333)))
            local ok = myassert(c:set_serial_number(toset))

            local get = myassert(c:get_serial_number())
            get = get:to_hex():upper()
            toset = toset:to_hex():upper()
            if get ~= toset then
              ngx.say(get)
              ngx.say(toset)
            else
              ngx.print("ok")
            end
        }
    }
--- request
    GET /t
--- response_body eval
"ok"
--- no_error_log
[error]

=== TEST 22: x509:get_not_before (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local get = myassert(c:get_not_before())
            ngx.print(get)
        }
    }
--- request
    GET /t
--- response_body eval
"1616630400"
--- no_error_log
[error]

=== TEST 23: x509:set_not_before (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local toset = ngx.time()
            local ok = myassert(c:set_not_before(toset))

            local get = myassert(c:get_not_before())
            if get ~= toset then
              ngx.say(get)
              ngx.say(toset)
            else
              ngx.print("ok")
            end
        }
    }
--- request
    GET /t
--- response_body eval
"ok"
--- no_error_log
[error]

=== TEST 24: x509:get_not_after (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local get = myassert(c:get_not_after())
            ngx.print(get)
        }
    }
--- request
    GET /t
--- response_body eval
"1648684799"
--- no_error_log
[error]

=== TEST 25: x509:set_not_after (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local toset = ngx.time()
            local ok = myassert(c:set_not_after(toset))

            local get = myassert(c:get_not_after())
            if get ~= toset then
              ngx.say(get)
              ngx.say(toset)
            else
              ngx.print("ok")
            end
        }
    }
--- request
    GET /t
--- response_body eval
"ok"
--- no_error_log
[error]

=== TEST 26: x509:get_pubkey (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local get = myassert(c:get_pubkey())
            get = get:to_PEM()
            ngx.print(get)
        }
    }
--- request
    GET /t
--- response_body eval
"-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErfb3dbHTSVQKXRBxvdwlBksiHKIj
Tp+h/rnQjL05vAwjx8+RppBa2EWrAxO+wSN6ucTInUf2luC5dmtQNmb3DQ==
-----END PUBLIC KEY-----
"
--- no_error_log
[error]

=== TEST 27: x509:set_pubkey (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local toset = myassert(require("resty.openssl.pkey").new())
            local ok = myassert(c:set_pubkey(toset))

            local get = myassert(c:get_pubkey())
            get = get:to_PEM()
            toset = toset:to_PEM()
            if get ~= toset then
              ngx.say(get)
              ngx.say(toset)
            else
              ngx.print("ok")
            end
        }
    }
--- request
    GET /t
--- response_body eval
"ok"
--- no_error_log
[error]

=== TEST 28: x509:get_subject_name (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local get = myassert(c:get_subject_name())
            get = get:tostring()
            ngx.print(get)
        }
    }
--- request
    GET /t
--- response_body eval
"C=US/CN=github.com/L=San Francisco/O=GitHub, Inc./ST=California"
--- no_error_log
[error]

=== TEST 29: x509:set_subject_name (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local toset = myassert(require("resty.openssl.x509.name").new():add('CN', 'earth.galaxy'))
            local ok = myassert(c:set_subject_name(toset))

            local get = myassert(c:get_subject_name())
            get = get:tostring()
            toset = toset:tostring()
            if get ~= toset then
              ngx.say(get)
              ngx.say(toset)
            else
              ngx.print("ok")
            end
        }
    }
--- request
    GET /t
--- response_body eval
"ok"
--- no_error_log
[error]

=== TEST 30: x509:get_issuer_name (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local get = myassert(c:get_issuer_name())
            get = get:tostring()
            ngx.print(get)
        }
    }
--- request
    GET /t
--- response_body eval
"C=US/CN=DigiCert High Assurance TLS Hybrid ECC SHA256 2020 CA1/O=DigiCert, Inc."
--- no_error_log
[error]

=== TEST 31: x509:set_issuer_name (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local toset = myassert(require("resty.openssl.x509.name").new():add('CN', 'earth.galaxy'))
            local ok = myassert(c:set_issuer_name(toset))

            local get = myassert(c:get_issuer_name())
            get = get:tostring()
            toset = toset:tostring()
            if get ~= toset then
              ngx.say(get)
              ngx.say(toset)
            else
              ngx.print("ok")
            end
        }
    }
--- request
    GET /t
--- response_body eval
"ok"
--- no_error_log
[error]

=== TEST 32: x509:get_version (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local get = myassert(c:get_version())
            ngx.print(get)
        }
    }
--- request
    GET /t
--- response_body eval
"3"
--- no_error_log
[error]

=== TEST 33: x509:set_version (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local toset = ngx.time()
            local ok = myassert(c:set_version(toset))

            local get = myassert(c:get_version())
            if get ~= toset then
              ngx.say(get)
              ngx.say(toset)
            else
              ngx.print("ok")
            end
        }
    }
--- request
    GET /t
--- response_body eval
"ok"
--- no_error_log
[error]

=== TEST 34: x509:get_subject_alt_name (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local get = myassert(c:get_subject_alt_name())
            get = get:tostring()
            ngx.print(get)
        }
    }
--- request
    GET /t
--- response_body eval
"DNS=github.com/DNS=www.github.com"
--- no_error_log
[error]

=== TEST 35: x509:set_subject_alt_name (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))
            local toset = myassert(require("resty.openssl.x509.altname").new():add('DNS', 'earth.galaxy'))
            local ok = myassert(c:set_subject_alt_name(toset))

            local get = myassert(c:get_subject_alt_name())
            get = get:tostring()
            toset = toset:tostring()
            if get ~= toset then
              ngx.say(get)
              ngx.say(toset)
            else
              ngx.print("ok")
            end
        }
    }
--- request
    GET /t
--- response_body eval
"ok"
--- no_error_log
[error]

=== TEST 37: x509:get/set_subject_alt_name_critical (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local crit = myassert(c:get_subject_alt_name_critical())

            local ok, err = myassert(c:set_subject_alt_name_critical(not crit))

            ngx.say(c:get_subject_alt_name_critical() == not crit)
        }
    }
--- request
    GET /t
--- response_body
true
--- no_error_log
[error]

=== TEST 38: x509:get/set_basic_constraints_critical (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local crit = myassert(c:get_basic_constraints_critical())

            local ok, err = myassert(c:set_basic_constraints_critical(not crit))

            ngx.say(c:get_basic_constraints_critical() == not crit)
        }
    }
--- request
    GET /t
--- response_body
true
--- no_error_log
[error]

=== TEST 39: x509:get/set_info_access_critical (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local crit = myassert(c:get_info_access_critical())

            local ok, err = myassert(c:set_info_access_critical(not crit))

            ngx.say(c:get_info_access_critical() == not crit)
        }
    }
--- request
    GET /t
--- response_body
true
--- no_error_log
[error]

=== TEST 40: x509:get/set_crl_distribution_points_critical (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local crit = myassert(c:get_crl_distribution_points_critical())

            local ok, err = myassert(c:set_crl_distribution_points_critical(not crit))

            ngx.say(c:get_crl_distribution_points_critical() == not crit)
        }
    }
--- request
    GET /t
--- response_body
true
--- no_error_log
[error]

=== TEST 41: x509:get_get_signature_name (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local nid = myassert(c:get_signature_nid())

            ngx.say(nid)

            local name = myassert(c:get_signature_name())

            ngx.say(name)

            local name = myassert(c:get_signature_digest_name())

            ngx.say(name)
        }
    }
--- request
    GET /t
--- response_body
794
ecdsa-with-SHA256
SHA256
--- no_error_log
[error]
# END AUTO GENERATED CODE