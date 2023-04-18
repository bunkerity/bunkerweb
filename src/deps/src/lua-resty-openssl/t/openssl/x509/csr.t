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

no_long_string();

run_tests();

__DATA__
=== TEST 1: Loads a csr
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))

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
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))

            local pem = myassert(c:tostring("PEM"))

            for _, typ in ipairs({"PEM", "*", false}) do
              local c2 = myassert(require("resty.openssl.x509.csr").new(pem, typ))
            end
            local c2, err = require("resty.openssl.x509.csr").new(pem, "DER")
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"x509.csr.new.+(nested asn1 error|NESTED_ASN1_ERROR).+"
--- no_error_log
[error]

=== TEST 3: Converts and loads DER format
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))

            local pem = myassert(c:tostring("DER"))

            for _, typ in ipairs({"DER", "*", false}) do
              local c2 = myassert(require("resty.openssl.x509.csr").new(pem, typ))
            end
            local c2, err = require("resty.openssl.x509.csr").new(pem, "PEM")
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"x509.csr.new.+(no start line|NO_START_LINE).+"
--- no_error_log
[error]

=== TEST 4: Generates CSR with RSA pkey correctly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local util = require("csr")
            local pkey = require("resty.openssl.pkey").new()
            local der = myassert(util.create_csr(pkey, "dns1.com", "dns2.com", "dns3.com"))

            ngx.update_time()
            local fname = "ci_" .. math.floor(ngx.now() * 1000)
            local f = io.open(fname, "wb")
            f:write(der)
            f:close()
            ngx.say(io.popen("openssl req -inform der -in " .. fname .. " -noout -text", 'r'):read("*a"))
            os.remove(fname)
        }
    }
--- request
    GET /t
--- response_body_like eval
".+CN\\s*=\\s*dns1.com.+rsaEncryption.+2048 bit.+DNS:dns1.com.+DNS:dns2.com.+DNS:dns3.com"
--- no_error_log
[error]

=== TEST 5: Rejects invalid arguments
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local csr = require("resty.openssl.x509.csr").new()
            ok, err = csr:set_subject_name("not a subject")
            ngx.say(err)
            ok, err = csr:set_subject_alt_name("not an alt")
            ngx.say(err)
            ok, err = csr:set_pubkey("not a pkey")
            ngx.say(err)
            ok, err = csr:sign("not a pkey")
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body eval
"x509.csr:set_subject_name: expect a x509.name instance at #1
x509.csr:set_subject_alt_name: expect a x509.altname instance at #1
x509.csr:set_pubkey: expect a pkey instance at #1
x509.csr:sign: expect a pkey instance at #1
"
--- no_error_log
[error]


=== TEST 6: x509.csr:get_extensions of csr
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))
            local exts = c:get_extensions()
            if #exts == 0 then
              ngx.print("0")
            else
              ngx.print("4")
            end
        }
    }
--- request
    GET /t
--- response_body eval
"4"
--- no_error_log
[error]


=== TEST 7: x509.csr:get_extension by nid
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))
            local ext, pos = c:get_extension(83)
            if not ext then
              ngx.say("nil")
            else
              ngx.say(pos)
            end

            local ext = c:get_extension(83, pos)
            if not ext then
              ngx.say("nil")
            else
              ngx.say(pos)
            end
        }
    }
--- request
    GET /t
--- response_body eval
"2
nil
"
--- no_error_log
[error]

=== TEST 8: x509.csr:get_extension by nid name
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))
            local ext = c:get_extension('basicConstraints')
            if not ext then
              ngx.print("nil")
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

=== TEST 9: x509.csr:get_extension should return nil if wrong nid name is given
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))
            local ext, err = c:get_extension('test')
            if not ext then
              ngx.print("ok")
            else
              ngx.print(err)
            end
        }
    }
--- request
    GET /t
--- response_body eval
"ok"
--- no_error_log
[error]

=== TEST 10: Adds extension
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))
            local altname = require("resty.openssl.x509.altname").new()
            myassert(altname:add("DNS", "test.com"))
            myassert(altname:add("DNS", "test2.com"))
            local extension = require("resty.openssl.x509.extension")
            local ext = myassert(extension.from_data(altname, 85, false))

            local ok = myassert(c:add_extension(ext))

            local ext, _ = c:get_extension("subjectAltName")

            ngx.update_time()
            local fname = "ci_" .. math.floor(ngx.now() * 1000)
            local f = io.open(fname, "wb")
            f:write(c:tostring())
            f:close()
            ngx.say(io.popen("openssl req -in " .. fname .. " -noout -text", 'r'):read("*a"))
            os.remove(fname)
        }
    }
--- request
    GET /t
--- response_body_like eval
"DNS:example.com.+DNS:test.com, DNS:test2.com
"
--- no_error_log
[error]

=== TEST 11: Set extension
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))
            local altname = require("resty.openssl.x509.altname").new()
            myassert(altname:add("DNS", "test.com"))
            myassert(altname:add("DNS", "test2.com"))
            local extension = require("resty.openssl.x509.extension")
            local ext = myassert(extension.from_data(altname, 85, false))

            local ok = myassert(c:set_extension(ext))

            local ext, _ = c:get_extension("subjectAltName")

            ngx.say(tostring(ext))
        }
    }
--- request
    GET /t
--- response_body eval
"DNS:test.com, DNS:test2.com
"
--- no_error_log
[error]

=== TEST 12: x509.csr:sign should succeed
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))
            local d = myassert(require("resty.openssl.digest").new("SHA256"))
            local p = myassert(require("resty.openssl.pkey").new())
            local ok = myassert(c:sign(p, d))
            if ok == false then
                ngx.say("false")
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

=== TEST 14: Check private key match
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local util = require("csr")
            local pkey = require("resty.openssl.pkey").new({ type = "EC", curve = "prime256v1" })
            local der = myassert(util.create_csr(pkey, "dns1.com", "dns2.com", "dns3.com"))
            local csr = myassert(require("resty.openssl.x509.csr").new(der))
            local ok, err = csr:check_private_key(pkey)
            ngx.say(ok)
            ngx.say(err)

            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))
            local ok, err = c:check_private_key(pkey)
            ngx.say(ok)
            ngx.say(err)

            local key2 = require("resty.openssl.pkey").new({
                type = 'EC',
                curve = "prime256v1",
            })
            local ok, err = csr:check_private_key(key2)
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


=== TEST 15: x509.csr:get_subject_name (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))

            local get = myassert(c:get_subject_name())
            get = get:tostring()
            ngx.print(get)
        }
    }
--- request
    GET /t
--- response_body eval
"C=US/CN=example.com/L=Los Angeles/O=SSL Support/OU=SSL Support/ST=California"
--- no_error_log
[error]

=== TEST 16: x509.csr:set_subject_name (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))
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

=== TEST 17: x509.csr:get_pubkey (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))

            local get = myassert(c:get_pubkey())
            get = get:to_PEM()
            ngx.print(get)
        }
    }
--- request
    GET /t
--- response_body eval
"-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwPOIBIoblSLFv/ifj8GD
CNL5NhDX2JVUQKcWC19KtWYQg1HPnaGIy+Dj9tYSBw8T8xc9hbJ1TYGbBIMKfBUz
KoTt5yLdVIM/HJm3m9ImvAbK7TYcx1U9TJEMxN6686whAUMBr4B7ql4VTXqu6TgD
cdbcQ5wsPVOiFHJTTwgVwt7eVCBMFAkZn+qQz+WigM5HEp8KFrzwAK142H2ucuyf
gGS4+XQSsUdwNWh9GPRZgRt3R2h5ymYkQB/cbg596alCquoizI6QCfwQx3or9Dg1
f3rlwf8H5HIVH3hATGIr7GpbKka/JH2PYNGfi5KqsJssVQfu84m+5WXDB+90KHJE
cwIDAQAB
-----END PUBLIC KEY-----
"
--- no_error_log
[error]

=== TEST 18: x509.csr:set_pubkey (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))
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

=== TEST 19: x509.csr:get_version (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))

            local get = myassert(c:get_version())
            ngx.print(get)
        }
    }
--- request
    GET /t
--- response_body eval
"1"
--- no_error_log
[error]

=== TEST 20: x509.csr:set_version (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))
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

=== TEST 21: x509.csr:get_subject_alt_name (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))

            local get = myassert(c:get_subject_alt_name())
            get = get:tostring()
            ngx.print(get)
        }
    }
--- request
    GET /t
--- response_body eval
"DNS=example.com"
--- no_error_log
[error]

=== TEST 22: x509.csr:set_subject_alt_name (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))
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

=== TEST 24: x509.csr:get/set_subject_alt_name_critical (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))

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

=== TEST 25: x509.csr:get_get_signature_name (AUTOGEN)
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/test.csr"):read("*a")
            local c = myassert(require("resty.openssl.x509.csr").new(f))

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
65
RSA-SHA1
SHA1
--- no_error_log
[error]
# END AUTO GENERATED CODE
