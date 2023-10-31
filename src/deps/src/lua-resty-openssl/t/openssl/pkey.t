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

no_long_string();

run_tests();

__DATA__
=== TEST 1: Generates RSA key by default
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local p = myassert(require("resty.openssl.pkey").new())
            ngx.say(myassert(p:to_PEM('private')))
        }
    }
--- request
    GET /t
--- response_body_like eval
"-----BEGIN PRIVATE KEY-----"
--- no_error_log
[error]

=== TEST 2: Generates and loads RSA key
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local pkey = require("resty.openssl.pkey")
            local p = myassert(pkey.new({
                type = 'RSA',
                bits = 2048,
            }))
            local pem = myassert(p:to_PEM('private'))
            ngx.say(pem)
            ngx.say(pem == pkey.new(pem):to_PEM('private'))
        }
    }
--- request
    GET /t
--- response_body_like eval
"-----BEGIN PRIVATE KEY-----
.+
true"
--- no_error_log
[error]

=== TEST 3: Generates and loads EC key explictly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local pkey = require("resty.openssl.pkey")
            local p = myassert(pkey.new({
                type = "EC",
                curve = 'prime256v1',
            }))
            local pem = myassert(p:to_PEM('private'))
            ngx.say(pem)
            ngx.say(pem == pkey.new(pem):to_PEM('private'))
        }
    }
--- request
    GET /t
--- response_body_like eval
"-----BEGIN PRIVATE KEY-----
.+
true"
--- no_error_log
[error]

=== TEST 4: Generates and loads Ed25519 key explictly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_111_OR_LATER then
                ngx.say("-----BEGIN PRIVATE KEY-----\nyayaa\ntrue"); ngx.exit(0)
            end
            local pkey = require("resty.openssl.pkey")
            local p = myassert(pkey.new({
                type = 'Ed25519',
            }))
            local pem = myassert(p:to_PEM('private'))
            ngx.say(pem)
            ngx.say(pem == pkey.new(pem):to_PEM('private'))
        }
    }
--- request
    GET /t
--- response_body_like eval
"-----BEGIN PRIVATE KEY-----
.+
true"
--- no_error_log
[error]

=== TEST 5: Generates and loads DH key explictly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if version.BORINGSSL or not version.OPENSSL_111_OR_LATER then
                ngx.say("-----BEGIN PRIVATE KEY-----\nsad\ntrue")
                ngx.exit(0)
            end
            local pkey = require("resty.openssl.pkey")
            local p = myassert(pkey.new({
                type = 'DH',
                bits = 512
            }))
            local pem = myassert(p:to_PEM('private'))
            ngx.say(pem)
            ngx.say(pem == pkey.new(pem):to_PEM('private'))
            -- skip for 3.0 since it only allows 2048 bits and is toooo slow
        }
    }
--- request
    GET /t
--- response_body_like eval
"-----BEGIN PRIVATE KEY-----
.+
true"
--- no_error_log
[error]

=== TEST 6: Uses DH predefined groups
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if require("resty.openssl.version").BORINGSSL then
                ngx.say("-----BEGIN PRIVATE KEY-----\nsad\ntrue")
                ngx.exit(0)
            end
            local pkey = require("resty.openssl.pkey")
            local p = myassert(pkey.new({
                type = 'DH',
                group = "dh_1024_160",
            }))
            local pem = myassert(p:to_PEM('private'))
            ngx.say(pem)
            ngx.say(pem == pkey.new(pem):to_PEM('private'))
        }
    }
--- request
    GET /t
--- response_body_like eval
"-----BEGIN PRIVATE KEY-----
.+
true"
--- no_error_log
[error]

=== TEST 7: Rejects invalid arg
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local pkey = require("resty.openssl.pkey")
            local p, err = pkey.new(123)
            ngx.say(err)
            local p, err = pkey.new('PRIVATE KEY')
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"pkey.new: unexpected type.+
pkey.new:load_key: .+
"
--- no_error_log
[error]

=== TEST 8: Loads encrypted PEM pkey with passphrase
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/ec_key_encrypted.pem"):read("*a")
            local privkey, err = require("resty.openssl.pkey").new(f, {
                format = "PEM",
                type = "pr",
                passphrase = "wrongpasswrod",
            })
            ngx.say(err)
            local privkey = myassert(require("resty.openssl.pkey").new(f, {
                format = "PEM",
                type = "pr",
                passphrase = "123456",
            }))

            ngx.say("ok")
        }
    }
--- request
    GET /t
--- response_body_like eval
"pkey.new.+(?:bad decrypt|failed|BAD_DECRYPT)
ok
"
--- no_error_log
[error]

=== TEST 9: Loads encrypted PEM pkey with passphrase callback
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local f = io.open("t/fixtures/ec_key_encrypted.pem"):read("*a")
            local privkey, err = require("resty.openssl.pkey").new(f, {
                format = "PEM",
                type = "pr",
                passphrase_cb = function()
                    return "wrongpassword"
                end,
            })
            ngx.say(err)
            local privkey = myassert(require("resty.openssl.pkey").new(f, {
                format = "PEM",
                type = "pr",
                passphrase_cb = function()
                    return "123456"
                end,
            }))

            ngx.say("ok")
        }
    }
--- request
    GET /t
--- response_body_like eval
"pkey.new.+(?:bad decrypt|failed|BAD_DECRYPT)
ok
"
--- no_error_log
[error]

=== TEST 10: Loads DER format
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local pkey = require("resty.openssl.pkey")
            local p1 = myassert(pkey.new())

            local pem = p1:to_PEM('private')
            local der = myassert(p1:tostring('private', 'DER'))
            local p2 = myassert(pkey.new(der))

            ngx.print(p2 and pem == p2:to_PEM('private'))
        }
    }
--- request
    GET /t
--- response_body eval
"true"
--- no_error_log
[error]

=== TEST 11: Outputs DER and JWK
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local p = myassert(require("resty.openssl.pkey").new({
                type = "EC",
                curve = 'prime256v1',
            }))
            local t = myassert(p:tostring('private', "PEM"))
            ngx.say(t)

            local t = myassert(p:tostring('private', "DER"))
            ngx.say(#t)

            local t = myassert(p:tostring('private', "JWK"))
            ngx.say(t)
        }
    }
--- request
    GET /t
--- response_body_like eval
"-----BEGIN PRIVATE KEY-----
.+
-----END PRIVATE KEY-----

(121|138|364)
.+kid.+"
--- no_error_log
[error]

=== TEST 12: Outputs public key
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local p = myassert(require("resty.openssl.pkey").new())
            ngx.say(p:to_PEM())
        }
    }
--- request
    GET /t
--- response_body_like eval
"-----BEGIN PUBLIC KEY-----"
--- no_error_log
[error]

=== TEST 13: Extracts RSA parameters
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local p = myassert(require("resty.openssl.pkey").new({
                exp = 65537,
            }))

            local params = myassert(p:get_parameters())

            for _, k in ipairs(require("resty.openssl.rsa").params) do
                local b = myassert(params[k]:to_hex():upper())
                ngx.say(b)
            end
            local got = params.dne
            ngx.say(got)
        }
    }
--- request
    GET /t
--- response_body_like eval
"[A-F0-9]+
[A-F0-9]+
[A-F0-9]+
[A-F0-9]+
[A-F0-9]+
[A-F0-9]+
[A-F0-9]+
[A-F0-9]+
nil
"
--- no_error_log
[error]

=== TEST 14: Extracts EC parameters
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local p = myassert(require("resty.openssl.pkey").new({
                type = "EC",
                curve = "prime256v1",
            }))

            local params = myassert(p:get_parameters())

            local group = params["group"]
            ngx.say(group)
            for _, k in ipairs(require("resty.openssl.ec").params) do
                if k ~= "group" then
                    local b = myassert(params[k]:to_hex():upper())

                    ngx.say(b)
                end
            end
            local got = params.dne
            ngx.say(got)
        }
    }
--- request
    GET /t
--- response_body_like eval
"415
[A-F0-9]{1,130}
[A-F0-9]{1,64}
[A-F0-9]{1,64}
[A-F0-9]{1,64}
nil
"
--- no_error_log
[error]

=== TEST 15: Extracts Ed25519 parameters
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if not version.OPENSSL_111_OR_LATER then
                ngx.say("32\n32\nfake")
                ngx.exit(0)
            end
            local p = myassert(require("resty.openssl.pkey").new({
                type = "Ed25519",
            }))

            local params = myassert(p:get_parameters())

            ngx.say(#params.private)
            ngx.say(#params.public)
        }
    }
--- request
    GET /t
--- response_body_like eval
"32
32
"
--- no_error_log
[error]

=== TEST 16: Extracts DH parameters
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if require("resty.openssl.version").BORINGSSL then
                ngx.say("B10B8F96A080E01DDE92DE5EAE5D54EC52C99FBCFB06A3C69A6A9DCA52D23B616073E28675A23D189838EF1E2EE652C013ECB4AEA906112324975C3CD49B83BFACCBDD7D90C4BD7098488E9C219A73724EFFD6FAE5644738FAA31A4FF55BCCC0A151AF5F0DC8B4BD45BF37DF365C1A65E68CFDA76D4DA708DF1FB2BC2E4A4371")
                ngx.say("A4D1CBD5C3FD34126765A442EFB99905F8104DD258AC507FD6406CFF14266D31266FEA1E5C41564B777E690F5504F213160217B4B01B886A5E91547F9E2749F4D7FBD7D3B9A92EE1909D0D2263F80A76A6A24C087A091F531DBF0A0169B6A28AD662A4D18E73AFA32D779D5918D08BC8858F4DCEF97C2A24855E6EEB22B3B2E5")
                ngx.say("1\n2")
                ngx.exit(0)
            end
            local p = myassert(require("resty.openssl.pkey").new({
                type = "DH",
                group = "dh_1024_160",
            }))

            local params = myassert(p:get_parameters())

            ngx.say(params.p:to_hex():upper())
            ngx.say(params.g:to_hex():upper())
            ngx.say(params.private:to_hex():upper())
            ngx.say(params.public:to_hex():upper())
        }
    }
--- request
    GET /t
--- response_body_like eval
"B10B8F96A080E01DDE92DE5EAE5D54EC52C99FBCFB06A3C69A6A9DCA52D23B616073E28675A23D189838EF1E2EE652C013ECB4AEA906112324975C3CD49B83BFACCBDD7D90C4BD7098488E9C219A73724EFFD6FAE5644738FAA31A4FF55BCCC0A151AF5F0DC8B4BD45BF37DF365C1A65E68CFDA76D4DA708DF1FB2BC2E4A4371
A4D1CBD5C3FD34126765A442EFB99905F8104DD258AC507FD6406CFF14266D31266FEA1E5C41564B777E690F5504F213160217B4B01B886A5E91547F9E2749F4D7FBD7D3B9A92EE1909D0D2263F80A76A6A24C087A091F531DBF0A0169B6A28AD662A4D18E73AFA32D779D5918D08BC8858F4DCEF97C2A24855E6EEB22B3B2E5
[A-F0-9]+
[A-F0-9]+
"
--- no_error_log
[error]

=== TEST 17: Encrypt and decrypt
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local privkey = myassert(require("resty.openssl.pkey").new())
            if err then
                ngx.log(ngx.ERR, err)
                return
            end
            local pubkey = myassert(require("resty.openssl.pkey").new(assert(privkey:to_PEM("public"))))

            local s = myassert(pubkey:encrypt("23333"))
            ngx.say(#s)

            local decrypted = myassert(privkey:decrypt(s))
            ngx.say(decrypted)
        }
    }
--- request
    GET /t
--- response_body eval
"256
23333
"
--- no_error_log
[error]


=== TEST 18: Sign and verify
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local p = myassert(require("resty.openssl.pkey").new())

            local digest = myassert(require("resty.openssl.digest").new("SHA256"))

            myassert(digest:update("🕶️", "+1s"))

            local s = myassert(p:sign(digest))
            ngx.say(#s)

            local v = myassert(p:verify(s, digest))
            ngx.say(v)
        }
    }
--- request
    GET /t
--- response_body eval
"256
true
"
--- no_error_log
[error]

=== TEST 19: One shot sign and verify
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if not version.OPENSSL_111_OR_LATER and not version.BORINGSSL then
                ngx.say("64\ntrue\n256\ntrue")
                ngx.exit(0)
            end

            -- pureeddsa
            local p = myassert(require("resty.openssl.pkey").new({
                type = "Ed25519"
            }))
            local digest = "23333"
            local s = myassert(p:sign(digest))
            ngx.say(#s)

            local v = myassert(p:verify(s, digest))
            ngx.say(v)

            local md
            if version.BORINGSSL then
                md = "SHA256"
            end

            -- uses default md type
            local p = myassert(require("resty.openssl.pkey").new({
                type = "RSA"
            }))
            local digest = "23333"
            local s = myassert(p:sign(digest, md))
            ngx.say(#s)

            local v = myassert(p:verify(s, digest, md))
            ngx.say(v)
        }
    }
--- request
    GET /t
--- response_body eval
"64
true
256
true
"
--- no_error_log
[error]

=== TEST 20: Error on bad digest or verify parameters
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local p = myassert(require("resty.openssl.pkey").new({
                type = "EC",
                curve = "prime256v1",
            }))
            local s, err = p:sign(false)
            ngx.say(err)
            local v, err = p:verify("", false)
            ngx.say(err)
            local v, err = p:verify(false, "1")
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body eval
"pkey:sign: expect a digest instance or a string at #1
pkey:verify: expect a digest instance or a string at #2
pkey:verify: expect a string at #1
"
--- no_error_log
[error]

=== TEST 21: Key derivation for EC, X448 and X25519
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version_num = require("resty.openssl.version").version_num
            local BORINGSSL = require("resty.openssl.version").BORINGSSL
            local expected = { 32, 32, 56 }
            for i, t in ipairs({"EC", "X25519", "X448"}) do
                if (version_num < 0x10101000 and i == 3) or
                   (version_num < 0x10100000 and i == 2) or
                   (BORINGSSL and i > 2) then
                    ngx.say(expected[i])
                    goto next
                end
                local p = myassert(require("resty.openssl.pkey").new({
                    type = t,
                    curve = t == "EC" and "prime256v1" or nil,
                }))

                -- usually the peer key is the pubkey from other key pair
                -- we use the same key here just for simplicity
                local k = myassert(p:derive(p))
                ngx.say(#k)
            ::next::
            end
        }
    }
--- request
    GET /t
--- response_body_like eval
"32
32
56"
--- no_error_log
[error]

=== TEST 22: get key type
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local p, err = myassert(require("resty.openssl.pkey").new({
                type = 'RSA',
            }))
            ngx.say(encode_sorted_json(p:get_key_type()))
        }
    }
--- request
    GET /t
--- response_body_like eval
'{"id":"1.2.840.113549.1.1.1","ln":"rsaEncryption","nid":6,"sn":"rsaEncryption"}'
--- no_error_log
[error]

=== TEST 23: Raw sign and recover
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local p = myassert(require("resty.openssl.pkey").new())

            local s = myassert(p:sign_raw("🕶️"))
            ngx.say(#s)

            local v = myassert(p:verify_recover(s))
            ngx.say(v == "🕶️")
        }
    }
--- request
    GET /t
--- response_body eval
"256
true
"
--- no_error_log
[error]

=== TEST 24: Streaming sign and one shot sign can cross verify
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if not version.OPENSSL_111_OR_LATER or version.BORINGSSL then
                ngx.say("true\ntrue\ntrue\ntrue")
                ngx.exit(0)
            end

            local p = myassert(require("resty.openssl.pkey").new())
            local pec = myassert(require("resty.openssl.pkey").new({
                type = "EC",
                curve = "prime256v1",
            }))

            -- one shot sign RSA, verify with digest instance
            local s = myassert(p:sign("🕶️+1s"))

            local digest = myassert(require("resty.openssl.digest").new("SHA256"))
            digest:update("🕶️+1s")
            local v, err = p:verify(s, digest)
            ngx.say(v)

            -- sign with digest RSA, one shot verify
            local digest = myassert(require("resty.openssl.digest").new("SHA256"))
            digest:update("🕶️+1s")
            local s = myassert(p:sign(digest))

            local v, err = p:verify(s, "🕶️+1s")
            ngx.say(v)

            -- one shot sign EC, verify with digest instance
            local s = myassert(pec:sign("🕶️+1s"))

            local digest = myassert(require("resty.openssl.digest").new("SHA256"))
            digest:update("🕶️+1s")
            local v, err = pec:verify(s, digest)
            ngx.say(v)

            -- sign with digest EC, one shot verify
            local digest = myassert(require("resty.openssl.digest").new("SHA256"))
            digest:update("🕶️+1s")
            local s = myassert(pec:sign(digest))

            local v, err = pec:verify(s, "🕶️+1s")
            ngx.say(v)
        }
    }
--- request
    GET /t
--- response_body eval
"true
true
true
true
"
--- no_error_log
[error]

=== TEST 25: Outpus DH and EC params
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if require("resty.openssl.version").BORINGSSL then
                ngx.say("-----BEGIN DH PARAMETERS-----\nsad\n-----BEGIN EC PARAMETERS-----")
                ngx.exit(0)
            end

            local pkey = require("resty.openssl.pkey")
            ngx.say(myassert(pkey.paramgen({
                type = 'DH',
                group = "dh_1024_160",
            })))
            ngx.say(myassert(pkey.paramgen({
                type = "EC",
                curve = "prime256v1",
            })))
            collectgarbage()
        }
    }
--- request
    GET /t
--- response_body_like eval
"-----BEGIN DH PARAMETERS-----
.+
-----BEGIN EC PARAMETERS-----"
--- no_error_log
[error]


=== TEST 26: Set DH parameters
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if require("resty.openssl.version").BORINGSSL then
                ngx.say("B10B8F96A080E01DDE92DE5EAE5D54EC52C99FBCFB06A3C69A6A9DCA52D23B616073E28675A23D189838EF1E2EE652C013ECB4AEA906112324975C3CD49B83BFACCBDD7D90C4BD7098488E9C219A73724EFFD6FAE5644738FAA31A4FF55BCCC0A151AF5F0DC8B4BD45BF37DF365C1A65E68CFDA76D4DA708DF1FB2BC2E4A4371")
                ngx.say("A4D1CBD5C3FD34126765A442EFB99905F8104DD258AC507FD6406CFF14266D31266FEA1E5C41564B777E690F5504F213160217B4B01B886A5E91547F9E2749F4D7FBD7D3B9A92EE1909D0D2263F80A76A6A24C087A091F531DBF0A0169B6A28AD662A4D18E73AFA32D779D5918D08BC8858F4DCEF97C2A24855E6EEB22B3B2E5")
                ngx.say(string.rep("1", 256))
                ngx.say(string.rep("1", 256))
                ngx.exit(0)
            end

            local p = myassert(require("resty.openssl.pkey").new({
                type = "DH",
                group = "dh_1024_160",
            }))

            local params1 = myassert(p:get_parameters())

            local p = myassert(require("resty.openssl.pkey").new({
                type = "DH",
                group = "dh_2048_224",
            }))

            myassert(p:set_parameters({
                p = params1.p,
                g = params1.g,
                private = params1.private,
                public = params1.public,
            }))

            local params = myassert(p:get_parameters())

            ngx.say(params.p:to_hex():upper())
            ngx.say(params.g:to_hex():upper())
            ngx.say(params.private:to_hex():upper())
            ngx.say(params.public:to_hex():upper())

            collectgarbage()
        }
    }
--- request
    GET /t
--- response_body_like eval
"B10B8F96A080E01DDE92DE5EAE5D54EC52C99FBCFB06A3C69A6A9DCA52D23B616073E28675A23D189838EF1E2EE652C013ECB4AEA906112324975C3CD49B83BFACCBDD7D90C4BD7098488E9C219A73724EFFD6FAE5644738FAA31A4FF55BCCC0A151AF5F0DC8B4BD45BF37DF365C1A65E68CFDA76D4DA708DF1FB2BC2E4A4371
A4D1CBD5C3FD34126765A442EFB99905F8104DD258AC507FD6406CFF14266D31266FEA1E5C41564B777E690F5504F213160217B4B01B886A5E91547F9E2749F4D7FBD7D3B9A92EE1909D0D2263F80A76A6A24C087A091F531DBF0A0169B6A28AD662A4D18E73AFA32D779D5918D08BC8858F4DCEF97C2A24855E6EEB22B3B2E5
[A-F0-9]{1,256}
[A-F0-9]{1,256}
"
--- no_error_log
[error]

=== TEST 27: Load parameters for keygen
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if require("resty.openssl.version").BORINGSSL then
                ngx.say("B10B8F96A080E01DDE92DE5EAE5D54EC52C99FBCFB06A3C69A6A9DCA52D23B616073E28675A23D189838EF1E2EE652C013ECB4AEA906112324975C3CD49B83BFACCBDD7D90C4BD7098488E9C219A73724EFFD6FAE5644738FAA31A4FF55BCCC0A151AF5F0DC8B4BD45BF37DF365C1A65E68CFDA76D4DA708DF1FB2BC2E4A4371")
                ngx.say("415")
                ngx.exit(0)
            end

            local pem = myassert(require("resty.openssl.pkey").paramgen({
                type = "DH",
                group = "dh_1024_160",
            }))

            local p = myassert(require("resty.openssl.pkey").new({
                type = "DH",
                param = pem,
            }))

            ngx.say(myassert(p:get_parameters().p:to_hex():upper()))

            local pem = myassert(require("resty.openssl.pkey").paramgen({
                type = "EC",
                curve = "prime256v1",
            }))

            local p = myassert(require("resty.openssl.pkey").new({
                type = "EC",
                param = pem,
            }))

            ngx.say(myassert(p:get_parameters().group))

            collectgarbage()
        }
    }
--- request
    GET /t
--- response_body_like eval
"B10B8F96A080E01DDE92DE5EAE5D54EC52C99FBCFB06A3C69A6A9DCA52D23B616073E28675A23D189838EF1E2EE652C013ECB4AEA906112324975C3CD49B83BFACCBDD7D90C4BD7098488E9C219A73724EFFD6FAE5644738FAA31A4FF55BCCC0A151AF5F0DC8B4BD45BF37DF365C1A65E68CFDA76D4DA708DF1FB2BC2E4A4371
415
"
--- no_error_log
[error]

=== TEST 28: Checks if it's private key
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local opts = {
                { type = 'RSA', bits = 1024 },
                { type = "EC", curve = "prime256v1" },
                { type = 'DH', group = "dh_1024_160",},
            }
            for _, opt in ipairs(opts) do
                if require("resty.openssl.version").BORINGSSL and opt.type == "DH" then
                    goto next_loop
                end

                local priv = myassert(require("resty.openssl.pkey").new(opt))

                local ok, err = priv:is_private()
                if not ok then
                    ngx.say(opt.type .. ": should be a private key, but returns false: ".. (err or "nil"))
                end

                local pem = myassert(priv:to_PEM("public"))

                local pub = myassert(require("resty.openssl.pkey").new(pem))

                local ok, err = pub:is_private()
                if ok then
                    ngx.say(opt.type .. ": should not be a private key, but returns true: ".. (err or "nil"))
                end
                ::next_loop::
            end
        }
    }
--- request
    GET /t
--- response_body eval
""
--- no_error_log
[error]

=== TEST 29: Checks if it's private key: ecx
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if not version.OPENSSL_111_OR_LATER then
                ngx.exit(0)
            end
            local opts = {
                { type = 'Ed25519'},
            }
            for _, opt in ipairs(opts) do
                local priv = myassert(require("resty.openssl.pkey").new(opt))

                local ok, err = priv:is_private()
                if not ok then
                    ngx.say(opt.type .. ": should be a private key, but returns false: ".. (err or "nil"))
                end

                local pem = myassert(priv:to_PEM("public"))

                local pub = myassert(require("resty.openssl.pkey").new(pem))

                local ok, err = pub:is_private()
                if ok then
                    ngx.say(opt.type .. ": should not be a private key, but returns true: ".. (err or "nil"))
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

=== TEST 30: Sign/verify with md_alg
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if not version.OPENSSL_111_OR_LATER then
                ngx.say("256\ntrue\nfalse\nfalse")
                ngx.exit(0)
            end
            -- uses default md type
            local p = myassert(require("resty.openssl.pkey").new({
                type = "RSA"
            }))
            local digest = "23333"
            local s = myassert(p:sign(digest, "sha512"))
            ngx.say(#s)

            local ok = myassert(p:verify(s, digest, "sha512"))
            ngx.say(ok)

            -- use wrong md type, should not pass
            local md = version.BORINGSSL and "sha256" or nil
            local ok, e = p:verify(s, digest, "sha256")
            ngx.say(ok)
            local ok, e = p:verify(s, digest, "md5")
            ngx.say(ok)
        }
    }
--- request
    GET /t
--- response_body eval
"256
true
false
false
"
--- no_error_log
[error]

=== TEST 31: Sign/verify with paddings
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if not version.OPENSSL_111_OR_LATER then
                ngx.say("256\ntrue\nfalse\nfalse")
                ngx.exit(0)
            end
            -- uses default md type, boringssl must have md_alg
            local md = version.BORINGSSL and "sha256" or nil
            local p = myassert(require("resty.openssl.pkey").new({
                type = "RSA"
            }))
            local digest = "23333"
            local s = myassert(p:sign(digest, md, p.PADDINGS.RSA_PKCS1_PSS_PADDING))
            ngx.say(#s)

            local ok = myassert(p:verify(s, digest, md, p.PADDINGS.RSA_PKCS1_PSS_PADDING))
            ngx.say(ok)

            -- use wrong padding scheme, should not pass
            local ok, e = p:verify(s, digest, md)
            if ok ~= false then ngx.say(e) else ngx.say(ok) end
            local ok, e = p:verify(s, digest, md, p.PADDINGS.RSA_PKCS1_PADDING)
            if ok ~= false then ngx.say(e) else ngx.say(ok) end
        }
    }
--- request
    GET /t
--- response_body eval
"256
true
false
false
"
--- no_error_log
[error]

=== TEST 32: Sign/verify with PSS custom salt_len
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local version = require("resty.openssl.version")
            if not version.OPENSSL_111_OR_LATER then
                ngx.say("256\ntrue")
                ngx.exit(0)
            end
            -- uses default md type, boringssl must have md_alg
            local md = version.BORINGSSL and "sha256" or nil
            local p = myassert(require("resty.openssl.pkey").new({
                type = "RSA"
            }))
            local digest = "23333"
            local s = myassert(p:sign(digest, md, p.PADDINGS.RSA_PKCS1_PSS_PADDING, {
                pss_saltlen = 64,
            }))
            ngx.say(#s)

            local ok = myassert(p:verify(s, digest, md, p.PADDINGS.RSA_PKCS1_PSS_PADDING, {
                pss_saltlen = 64,
            }))
            ngx.say(ok)
        }
    }
--- request
    GET /t
--- response_body eval
"256
true
"
--- no_error_log
[error]

=== TEST 33: PEM passphrase_cb won't overflow
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local pkey = require("resty.openssl.pkey")
            local ffi = require("ffi")
            local f = function() end
            local pok, perr, last_ff
            while true do
                pok, pret = pcall(ffi.cast, "pem_password_cb", f)
                if not pok then
                    last_ff:free()
                    break
                end
                last_ff = pret
            end
            ngx.say("errored out with ", pret)

            local f = io.open("t/fixtures/ec_key_encrypted.pem"):read("*a")
            local privkey, err
            for i=1, 5 do
                privkey, err = pkey.new(f, {
                    format = "PEM",
                    passphrase_cb = function()
                        return "wrongpassword"
                    end,
                })
            end
            -- with random order in lua tables, this could be loaded
            -- by PEM_read_bio_PUBKEY, in such case, error will be
            -- PEM routines:get_name:no start line
            ngx.say(err)

            for i=1, 5 do
                local privkey = myassert(pkey.new(f, {
                    format = "PEM",
                    passphrase_cb = function()
                        return "123456"
                    end,
                }))
            end
            ngx.say("ok")

            local p = myassert(pkey.new({
                type = "EC",
                curve = 'prime256v1',
            }))
            local pem = myassert(p:to_PEM('private'))

            for i=1, 5 do
                local privkey = myassert(pkey.new(p, {
                        format = "PEM",
                        passphrase_cb = function()
                            error("should not reach here")
                        end,
                    }))
                end
            ngx.say("ok")
        }
    }
--- request
    GET /t
--- response_body_like eval
"errored out with too many callbacks
pkey.new.+(?:bad decrypt|failed|BAD_DECRYPT|no start line|NO_START_LINE|DECODER routines::unsupported)
ok
ok
"
--- no_error_log
[error]

=== TEST 34: Returns provider
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("default")
                ngx.exit(0)
            end

            local pkey = require("resty.openssl.pkey")
            local p = myassert(pkey.new({ type = "EC" }))
            ngx.say(myassert(p:get_provider_name()))
        }
    }
--- request
    GET /t
--- response_body
default
--- no_error_log
[error]

=== TEST 35: Returns gettable, settable params
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("-bits-\n-encoding-")
                ngx.exit(0)
            end

            local pkey = require("resty.openssl.pkey")
            local p = myassert(pkey.new({ type = "EC" }))
            ngx.say(require("cjson").encode(myassert(p:gettable_params())))
            ngx.say(require("cjson").encode(myassert(p:settable_params())))
        }
    }
--- request
    GET /t
--- response_body_like
.+bits.+
.+encoding.+
--- no_error_log
[error]

=== TEST 36: Get params, set params
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("true")
                ngx.exit(0)
            end

            local pkey = require("resty.openssl.pkey")
            local p = myassert(pkey.new({ type = "EC" }))
            local priv = myassert(p:get_param("priv", nil, "bn"))
            local priv2 = p:get_parameters().private
            ngx.say(priv == priv2)

            myassert(p:set_params({["point-format"] = "UNCOMPRESSED"}))
        }
    }
--- request
    GET /t
--- response_body eval
"true
"
--- no_error_log
[error]

=== TEST 37: Get default digest type
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if require("resty.openssl.version").BORINGSSL then
                ngx.say('BROKEN sha256 BROKEN')
                ngx.exit(0)
            end

            local pkey = require("resty.openssl.pkey")
            local p = myassert(pkey.new({ type = "EC" }))
            local algo = myassert(p:get_default_digest_type())
            ngx.say(require("cjson").encode(algo))
        }
    }
--- request
    GET /t
--- response_body_like
.+sha256.+
--- no_error_log
[error]

=== TEST 38: Reads and write pkcs1 rsa key
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local pkey = require("resty.openssl.pkey")

            local f = io.open("t/fixtures/test.key"):read("*a") -- pkcs8
            local key = myassert(pkey.new(f))

            -- read
            for _, fp in ipairs({"rsa-pkcs1-priv.key", "rsa-pkcs1-pub.key"}) do
                local f = io.open("t/fixtures/" .. fp):read("*a") -- pkcs8
                myassert(pkey.new(f))
            end

            local p = myassert(pkey.new({ type = "EC", curve = 'prime256v1' }))
            ngx.say(p:to_PEM(nil, true))
            ngx.say(key:tostring(nil, "DER", true))

            if require("resty.openssl.version").OPENSSL_3X then
                ngx.say('BEGIN RSA PUBLIC KEY\ntrue')
                ngx.say('BEGIN RSA PRIVATE KEY\ntrue')
                ngx.exit(0)
            end

            -- write (and read back)
            for _, kt in ipairs({"public", "private"}) do
                local pkcs1_pem = key:to_PEM(kt, true)
                ngx.say(pkcs1_pem:match("BEGIN RSA " .. kt:upper() .. " KEY"))

                local key2 = myassert(pkey.new(pkcs1_pem))
                ngx.say(key2:to_PEM(kt) == key:to_PEM(kt))
            end
        }
    }
--- request
    GET /t
--- response_body
nilPKCS#1 format is only supported to encode RSA key in "PEM" format
nilPKCS#1 format is only supported to encode RSA key in "PEM" format
BEGIN RSA PUBLIC KEY
true
BEGIN RSA PRIVATE KEY
true
--- no_error_log
[error]

=== TEST 39: Sign/verify with binary ecdsa sig
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_11_OR_LATER then
                ngx.say("64\ntrue\ntrue\ntruenil\nfalsenil")
                ngx.say("nilpkey:sign: ecdsa.sig_raw2der: invalid signature length, expect 64 but got 72")
                ngx.exit(0)
            end

            local opts = { ecdsa_use_raw = true }
            local p = myassert(require("resty.openssl.pkey").new({
                type = "EC",
                curve = "prime256v1",
            }))

            local digest = myassert(require("resty.openssl.digest").new("SHA256"))

            myassert(digest:update("🕶️", "+1s"))

            local s = myassert(p:sign(digest, nil, nil, opts))
            ngx.say(#s)

            local s2 = myassert(p:sign(digest))
            ngx.say(#s2 > 64) -- normally 72

            local v = myassert(p:verify(s, digest, nil, nil, opts))
            ngx.say(v)

            ngx.say(p:verify(s2, digest)) -- this is ok
            ngx.say(p:verify(s, digest)) -- this should fail
            ngx.say(p:verify(s2, digest, nil, nil, opts)) -- this should also fail
        }
    }
--- request
    GET /t
--- response_body_like eval
"64
true
true
truenil
false.+
nilpkey:sign: ecdsa.sig_raw2der: invalid signature length, expect 64 but got \\d+
"
--- no_error_log
[error]

=== TEST 40: Sign/verify with binary ecdsa sig length
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_11_OR_LATER then
                ngx.say("132\n96\ntrue\ntrue")
                ngx.exit(0)
            end
            local opts = { ecdsa_use_raw = true }
            local p_521 = myassert(require("resty.openssl.pkey").new({
                type = "EC",
                curve = "secp521r1",
            }))

            local p_384 = myassert(require("resty.openssl.pkey").new({
                type = "EC",
                curve = "secp384r1",
            }))
            local digest = myassert(require("resty.openssl.digest").new("SHA256"))

            myassert(digest:update("🕶️", "+1s"))

            local s_512 = myassert(p_521:sign(digest, nil, nil, opts))
            ngx.say(#s_512)
            local s_384 = myassert(p_384:sign(digest, nil, nil, opts))
            ngx.say(#s_384)

            local v_512 = myassert(p_521:verify(s_512, digest, nil, nil, opts))
            ngx.say(v_512)
            local v_384 = myassert(p_384:verify(s_384, digest, nil, nil, opts))
            ngx.say(v_384)
        }
    }
--- request
    GET /t
--- response_body
132
96
true
true
--- no_error_log
[error]
