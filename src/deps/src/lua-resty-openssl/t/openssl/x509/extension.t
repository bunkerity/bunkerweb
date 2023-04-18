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
=== TEST 1: Creates extension by nconf
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local extension = require("resty.openssl.x509.extension")
            local c = myassert(extension.new("extendedKeyUsage",
                                        "serverAuth,clientAuth"))
        }
    }
--- request
    GET /t
--- no_error_log
[error]

=== TEST 2: Gets extension object
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local extension = require("resty.openssl.x509.extension")
            local c = myassert(extension.new("extendedKeyUsage",
                                        "serverAuth,clientAuth"))

            ngx.say(encode_sorted_json(myassert(c:get_object())))
        }
    }
--- request
    GET /t
--- response_body_like eval
'{"id":"2.5.29.37","ln":"X509v3 Extended Key Usage","nid":126,"sn":"extendedKeyUsage"}
'
--- no_error_log
[error]

=== TEST 3: Gets extension critical
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local extension, _, err = c:get_extension("X509v3 Key Usage")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(extension:get_critical())
    
            local extension, _, err = c:get_extension("X509v3 Extended Key Usage")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(extension:get_critical())
        }
    }
--- request
    GET /t
--- response_body_like eval
"true
false
"
--- no_error_log
[error]

=== TEST 4: Set extension critical
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local extension = require("resty.openssl.x509.extension")
            local c = myassert(extension.new("extendedKeyUsage",
                                        "serverAuth,clientAuth"))
            myassert(c:set_critical())
            ngx.say(c:get_critical())

            myassert(c:set_critical(true))
            ngx.say(c:get_critical())
        }
    }
--- request
    GET /t
--- response_body_like eval
"false
true
"
--- no_error_log
[error]

=== TEST 5: Prints human readable txt of extension
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local extension, _, err = c:get_extension("subjectKeyIdentifier")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(extension:text())

            local extension, _, err = c:get_extension("Authority Information Access")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(tostring(extension))

            -- unknown extension
            local objects = require("resty.openssl.objects")
            local id_pe_acmeIdentifier = "1.3.6.1.5.5.7.1.31"
            local nid = objects.txt2nid(id_pe_acmeIdentifier)
            if not nid or nid == 0 then
                nid = objects.create(
                    id_pe_acmeIdentifier, -- nid
                    "pe-acmeIdentifier",  -- sn
                    "ACME Identifier"     -- ln
                )
            end
            local ext = myassert(require("resty.openssl.x509.extension").from_der("valuevalue", nid, true))
            ngx.say("ACME Identifier: ", tostring(ext))
        }
    }
--- request
    GET /t
--- response_body_like eval
"27:B1:7E:9F:BB:26:99:50:D8:F3:C3:53:5B:FE:31:16:B0:BB:1E:72
OCSP - URI:http://ocsp.digicert.com
CA Issuers - URI:http://cacerts.digicert.com/DigiCertHighAssuranceTLSHybridECCSHA2562020CA1.crt
.?ACME Identifier: valuevalue
"
--- no_error_log
[error]

=== TEST 6: Creates extension by X509V3_CTX
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local x509 = myassert(require("resty.openssl.x509").new(f))
            f = io.open("t/fixtures/test.crt"):read("*a")
            local ic = myassert(require("resty.openssl.x509").new(f))
            f = io.open("t/fixtures/test.key"):read("*a")
            local ik = myassert(require("resty.openssl.pkey").new(f))

            local extension = require("resty.openssl.x509.extension")
            local c = myassert(extension.new("subjectKeyIdentifier", "hash",
                            {
                                subject = x509,
                            }))

            ngx.say(tostring(c))

            if require("resty.openssl.version").OPENSSL_3X then
                c = myassert(extension.new("authorityKeyIdentifier", "keyid",
                                {
                                    subject = x509,
                                    issuer = x509,
                                }))

                if tostring(c) ~= "0." then
                    ngx.log(ngx.ERR, "authorityKeyIdentifier should be empty but got " .. tostring(c))
                end

                c = myassert(extension.new("authorityKeyIdentifier", "keyid",
                                {
                                    subject = x509,
                                    issuer = x509,
                                    issuer_pkey = ik,
                                }))
                -- when set with issuer_pkey, the X509V3_print doesn't include "keyid:" prefix
                ngx.print("keyid:")
            else
                c = myassert(extension.new("authorityKeyIdentifier", "keyid",
                                {
                                    subject = x509,
                                    issuer = ic,
                                }))
            end

            ngx.say(tostring(c))
        }
    }
--- request
    GET /t
--- response_body_like eval
"27:B1:7E:9F:BB:26:99:50:D8:F3:C3:53:5B:FE:31:16:B0:BB:1E:72
keyid:CF:03:F5:09:EB:83:D2:4F:10:DE:65:92:90:E9:93:3E:38:4C:E8:7C
"
--- no_error_log
[error]

=== TEST 7: Creates extension by data
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local altname = require("resty.openssl.x509.altname").new()
            myassert(altname:add("DNS", "test.com"))
            myassert(altname:add("DNS", "test2.com"))
            local extension = require("resty.openssl.x509.extension")
            local c = myassert(extension.from_data(altname, 85, false))

            ngx.say(encode_sorted_json(c:get_object()))
            ngx.say(tostring(c))
        }
    }
--- request
    GET /t
--- response_body_like eval
'{"id":"2.5.29.17","ln":"X509v3 Subject Alternative Name","nid":85,"sn":"subjectAltName"}
DNS:test.com, DNS:test2.com
'
--- no_error_log
[error]

=== TEST 8: Convert extension to data
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local altname = require("resty.openssl.x509.altname").new()
            myassert(altname:add("DNS", "test.com"))
            myassert(altname:add("DNS", "test2.com"))
            local extension = require("resty.openssl.x509.extension")
            local c = myassert(extension.from_data(altname, 85, false))

            local alt2 = myassert(extension.to_data(c, 85))
            ngx.say(alt2:tostring())
        }
    }
--- request
    GET /t
--- response_body_like eval
'DNS=test.com/DNS=test2.com
'
--- no_error_log
[error]

=== TEST 9: Creates extension by der
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local extension = require("resty.openssl.x509.extension")
            local c = myassert(extension.from_der("\x00\x01\x02\x03", "basicConstraints"))

            ngx.say(encode_sorted_json(c:get_object()))
        }
    }
--- request
    GET /t
--- response_body_like eval
'{"id":"2.5.29.19","ln":"X509v3 Basic Constraints","nid":87,"sn":"basicConstraints"}
'
--- no_error_log
[error]

=== TEST 10: Creates extension by nconf
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if require("resty.openssl.version").BORINGSSL then
                ngx.say([[
{"id":"2.5.29.32","ln":"X509v3 Certificate Policies","nid":89,"sn":"certificatePolicies"}
Policy: 1.2.3.4
Policy: 1.5.6.7.8
Policy: 1.3.5.8
  CPS: http://my.host.name/
  CPS: http://my.your.name/
  User Notice:
    Organization: Organisation Name
    Numbers: 1, 2, 3, 4
    Explicit Text: Explicit Text Here
            ]])
                ngx.exit(0)
            end

            local extension = require("resty.openssl.x509.extension")
            local c = myassert(extension.new("certificatePolicies", "ia5org,1.2.3.4,1.5.6.7.8,@polsect",
                [[
                [polsect]
                policyIdentifier = 1.3.5.8
                CPS.1="http://my.host.name/"
                CPS.2="http://my.your.name/"
                userNotice.1=@notice

                [notice]
                explicitText="Explicit Text Here"
                organization="Organisation Name"
                noticeNumbers=1,2,3,4
                ]]
            ))

            ngx.say(encode_sorted_json(c:get_object()))
            ngx.say(tostring(c))
        }
    }
--- request
    GET /t
--- response_body_like eval
'{"id":"2.5.29.32","ln":"X509v3 Certificate Policies","nid":89,"sn":"certificatePolicies"}
Policy: 1.2.3.4
Policy: 1.5.6.7.8
Policy: 1.3.5.8
  CPS: http://my.host.name/
  CPS: http://my.your.name/
  User Notice:
    Organization: Organisation Name
    Numbers: 1, 2, 3, 4
    Explicit Text: Explicit Text Here
'
--- no_error_log
[error]

=== TEST 11: Returns DER encoded data
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/Github.pem"):read("*a")
            local c = myassert(require("resty.openssl.x509").new(f))

            local extension, _, err = c:get_extension("subjectKeyIdentifier")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(require("helper").to_hex(extension:to_der()))

            local extension, _, err = c:get_extension("Authority Information Access")
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            ngx.say(require("helper").to_hex(extension:to_der()))
        }
    }
--- request
    GET /t
--- response_body_like eval
"041427B17E9FBB269950D8F3C3535BFE3116B0BB1E72
308182302406082B060105050730018618687474703A2F2F6F6373702E64696769636572742E636F6D305A06082B06010505073002864E687474703A2F2F636163657274732E64696769636572742E636F6D2F4469676943657274486967684173737572616E6365544C53487962726964454343534841323536323032304341312E637274
"
--- no_error_log
[error]