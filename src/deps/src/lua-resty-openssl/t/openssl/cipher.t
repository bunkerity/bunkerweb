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
=== TEST 1: Creates cipher correctly
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local cipher = myassert(require("resty.openssl.cipher").new("aes-256-cbc"))

            myassert(cipher:init(string.rep("0", 32), string.rep("0", 16), {
                is_encrypt = true,
            }))

            ngx.print(ngx.encode_base64(myassert(cipher:final('1'))))
        }
    }
--- request
    GET /t
--- response_body eval
"VhGyRCcMvlAgUjTYrqiWpg=="
--- no_error_log
[error]


=== TEST 2: Rejects unknown cipher
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local cipher, err = require("resty.openssl.cipher").new("aes257")
            ngx.print(err)
        }
    }
--- request
    GET /t
--- response_body_like eval
"cipher.new: invalid cipher type \"aes257\".*"
--- no_error_log
[error]

=== TEST 3: Unintialized ctx throw errors
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local cipher = myassert(require("resty.openssl.cipher").new("aes-256-cbc"))

            local s, err = cipher:update("1")
            ngx.say(err)
            local _, err = cipher:final("1")
            ngx.say(err)
        }
    }
--- request
    GET /t
--- response_body eval
"cipher:update: cipher not initalized, call cipher:init first
cipher:update: cipher not initalized, call cipher:init first
"
--- no_error_log
[error]

=== TEST 4: Encrypt
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local cipher = myassert(require("resty.openssl.cipher").new("aes-256-cbc"))

            local s = myassert(cipher:encrypt(string.rep("0", 32), string.rep("0", 16), '1'))

            ngx.print(ngx.encode_base64(s))
        }
    }
--- request
    GET /t
--- response_body eval
"VhGyRCcMvlAgUjTYrqiWpg=="
--- no_error_log
[error]

=== TEST 5: Encrypt no padding
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local cipher = myassert(require("resty.openssl.cipher").new("aes-256-cbc"))

            local s, err = cipher:encrypt(string.rep("0", 32), string.rep("0", 16), '1', true)
            ngx.say(s)
            -- 1.x: data not multiple of block length
            -- 3.0: wrong final block length
            ngx.say(err)
            local s = myassert(cipher:encrypt(string.rep("0", 32), string.rep("0", 16),
                '1' .. string.rep(string.char(15), 15), true))
            ngx.print(ngx.encode_base64(s))
        }
    }
--- request
    GET /t
--- response_body_like eval
"nil
.+(?:data not multiple of block length|wrong final block length|DATA_NOT_MULTIPLE_OF_BLOCK_LENGTH)
VhGyRCcMvlAgUjTYrqiWpg=="
--- no_error_log
[error]

=== TEST 6: Decrypt
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local cipher = myassert(require("resty.openssl.cipher").new("aes-256-cbc"))

            local s = myassert(cipher:decrypt(string.rep("0", 32), string.rep("0", 16),
                ngx.decode_base64("VhGyRCcMvlAgUjTYrqiWpg==")))

            ngx.print(s)
        }
    }
--- request
    GET /t
--- response_body eval
"1"
--- no_error_log
[error]

=== TEST 7: Decrypt no padding
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local cipher = myassert(require("resty.openssl.cipher").new("aes-256-cbc"))

            local s = myassert(cipher:decrypt(string.rep("0", 32), string.rep("0", 16),
                ngx.decode_base64("VhGyRCcMvlAgUjTYrqiWpg=="), true))

            ngx.print(s)
        }
    }
--- request
    GET /t
--- response_body eval
"1\x{0f}\x{0f}\x{0f}\x{0f}\x{0f}\x{0f}\x{0f}\x{0f}\x{0f}\x{0f}\x{0f}\x{0f}\x{0f}\x{0f}\x{0f}"
--- no_error_log
[error]

=== TEST 8: Encrypt streaming
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local cipher = myassert(require("resty.openssl.cipher").new("aes-256-cbc"))

            local ok = myassert(cipher:init(string.rep("0", 32), string.rep("0", 16), {
                is_encrypt = true,
            }))

            local sample = 'abcdefghi'
            local count = 5
            for i=1,count,1 do
                local s = myassert(cipher:update(sample))

                if s ~= "" then
                    ngx.say(ngx.encode_base64(s))
                else
                    ngx.say("nothing")
                end
            end
            local s = myassert(cipher:final(sample))

            ngx.say("final")
            ngx.say(ngx.encode_base64(s))
        }
    }
--- request
    GET /t
--- response_body eval
"nothing
SEk81GpcHC9KoZfN14RrNg==
nothing
L2dVbLMhEigy917CJBXz7g==
nothing
final
dtpklHxY9IbgmSw84+2XMr0Vy/S1392+rvu0A3GW1Wo=
"
--- no_error_log
[error]

=== TEST 9: Decrypt streaming
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local cipher = myassert(require("resty.openssl.cipher").new("aes-256-cbc"))

            local ok = myassert(cipher:init(string.rep("0", 32), string.rep("0", 16), {
                is_encrypt = false,
            }))

            local input = ngx.decode_base64('SEk81GpcHC9KoZfN14RrNg==') ..
                            ngx.decode_base64('L2dVbLMhEigy917CJBXz7g==') ..
                            ngx.decode_base64('dtpklHxY9IbgmSw84+2XMr0Vy/S1392+rvu0A3GW1Wo=')
            local count = 5 + 1
            local len = (#input - #input % count) / count
            for i=0,#input-len,len do
                local s = myassert(cipher:update(string.sub(input, i+1, i+len)))

                if s ~= "" then
                    ngx.say(s)
                else
                    ngx.say("nothing")
                end
            end
            -- this should throw error since we end in the middle
            local s, err = cipher:final()
            ngx.say(err)
            ngx.say(s)
            -- feed the last chunk of input
            local s = myassert(cipher:final(string.sub(input, #input -#input % count + 1, #input)))
            ngx.say("final")
            ngx.say(s)
        }
    }
--- request
    GET /t
--- response_body_like eval
"nothing
abcdefghiabcdefg
nothing
hiabcdefghiabcde
fghiabcdefghiabc
nothing
.+(wrong final block length|WRONG_FINAL_BLOCK_LENGTH)
nil
final
defghi
"
--- no_error_log
[error]


=== TEST 10: Derive key and iv
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            function string.tohex(str)
                return (str:gsub('.', function (c)
                    return string.format('%02X', string.byte(c))
                end))
            end

            local cipher = myassert(require("resty.openssl.cipher").new("aes-256-cbc"))

            -- openssl enc -aes-256-cbc -pass pass:xxx -S 797979 -P -md md5
            local key, iv = cipher:derive("xxx", "yyy", 1, "md5")

            ngx.say(key:tohex())
            ngx.say(iv:tohex())

            local cipher = myassert(require("resty.openssl.cipher").new("aes-256-ecb"))

            -- openssl enc -aes-256-ecb -pass pass:xxx -S 797979 -P -md md5
            local key, iv = cipher:derive("xxx", "yyy", 1, "md5")
            ngx.say(key:tohex())
            ngx.say(iv:tohex() == "" and "no iv")
        }
    }
--- request
    GET /t
--- response_body eval
"1F94CD004791ECFD50955451ACDA89D2CF1B4BCC6A378E4FC5C5861BDED17F61
FE91AF7782EDB48F32775BB2B72DD5ED
1F94CD004791ECFD50955451ACDA89D2CF1B4BCC6A378E4FC5C5861BDED17F61
no iv
"
--- no_error_log
[error]

=== TEST 11: Derive key and iv: salt, count and md is optional
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            function string.tohex(str)
                return (str:gsub('.', function (c)
                    return string.format('%02X', string.byte(c))
                end))
            end

            local cipher = myassert(require("resty.openssl.cipher").new("aes-256-cbc"))

            -- openssl enc -aes-256-cbc -pass pass:xxx -nosalt -P -md sha1
            local key, iv = cipher:derive("xxx")

            ngx.say(key:tohex())
            ngx.say(iv:tohex())
        }
    }
--- request
    GET /t
--- response_body eval
"B60D121B438A380C343D5EC3C2037564B82FFEF3542808AB5694FA93C3179140
20578C4FEF1AEE907B1DC95C776F8160
"
--- no_error_log
[error]

=== TEST 12: AEAD modes
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            local myassert = require("helper").myassert
            local key = string.rep("0", 32)
            local iv = string.rep("0", 12)
            local aad = "an aad"
            local cipher = require("resty.openssl.cipher")

            local enc = myassert(cipher.new("aes-256-gcm"))
            local d = myassert(enc:encrypt(key, iv, "secret", false, aad))
            local tag = myassert(enc:get_aead_tag())

            local dec = myassert(cipher.new("aes-256-gcm"))
            local s = myassert(dec:decrypt(key, iv, d, false, aad, tag))
            ngx.say(s)

            local dec = myassert(cipher.new("aes-256-gcm"))
            local r, err = dec:decrypt(key, iv, d, false, nil, tag)
            ngx.say(r)

            local dec = myassert(cipher.new("aes-256-gcm"))
            local r, err = dec:decrypt(key, iv, d, false, aad, nil)
            ngx.say(r)

        }
    }
--- request
    GET /t
--- response_body eval
"secret
nil
nil
"
--- no_error_log
[error]

=== TEST 13: Returns provider
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("default")
                ngx.exit(0)
            end

            local cipher = require("resty.openssl.cipher")
            local c = myassert(cipher.new("aes256"))
            ngx.say(myassert(c:get_provider_name()))
        }
    }
--- request
    GET /t
--- response_body
default
--- no_error_log
[error]

=== TEST 14: Returns gettable, settable params
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("-ivlen-\n-padding-")
                ngx.exit(0)
            end

            local cipher = require("resty.openssl.cipher")
            local c = myassert(cipher.new("aes256"))
            ngx.say(require("cjson").encode(myassert(c:gettable_params())))
            ngx.say(require("cjson").encode(myassert(c:settable_params())))
        }
    }
--- request
    GET /t
--- response_body_like
.+ivlen.+
.+padding.+
--- no_error_log
[error]

=== TEST 15: Get params, set params
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {
            if not require("resty.openssl.version").OPENSSL_3X then
                ngx.say("secret\nsecret\nnil")
                ngx.exit(0)
            end

            local myassert = require("helper").myassert
            local key = string.rep("0", 32)
            local iv = string.rep("0", 12)
            local aad = "an aad"
            local cipher = require("resty.openssl.cipher")

            local enc = myassert(cipher.new("aes-256-gcm"))
            local d = myassert(enc:encrypt(key, iv, "secret", false, aad))
            local tag = myassert(enc:get_param("tag", 16))

            local dec = myassert(cipher.new("aes-256-gcm"))
            local s = myassert(dec:decrypt(key, iv, d, false, aad, tag))
            ngx.say(s)

            local dec = myassert(cipher.new("aes-256-gcm"))
            myassert(dec:init(key, iv))
            myassert(dec:set_params({tag = tag}))
            myassert(dec:update_aead_aad(aad))
            local r, err = dec:final(d)
            ngx.say(r)

            local dec = myassert(cipher.new("aes-256-gcm"))
            myassert(dec:init(key, iv))
            myassert(dec:set_params({tag = "wrong tag"}))
            myassert(dec:update_aead_aad(aad))
            local r, err = dec:final(d)
            ngx.say(r)
        }
    }
--- request
    GET /t
--- response_body eval
"secret
secret
nil
"
--- no_error_log
[error]


=== TEST 16: Update with segements larger than 1024
--- http_config eval: $::HttpConfig
--- config
    location =/t {
        content_by_lua_block {

            local cipher = myassert(require("resty.openssl.cipher").new("aes-256-cbc"))

            local ok = myassert(cipher:init(string.rep("0", 32), string.rep("0", 16), {
                is_encrypt = true,
            }))

            local count = 3
            for i=1,count,1 do
                local s = myassert(cipher:update(string.rep(tostring(i), 1024)))

                if s ~= "" then
                    ngx.say(ngx.encode_base64(string.sub(s, -16)))
                else
                    ngx.say("nothing")
                end
            end
            local s = myassert(cipher:final(string.rep("a", 1024)))

            ngx.say("final")
            ngx.say(ngx.encode_base64(string.sub(s, -16)))

            local ok = myassert(cipher:init(string.rep("0", 32), string.rep("0", 16), {
                is_encrypt = true,
            }))
            local s = myassert(cipher:final(string.rep("1", 1024) ..
                                            string.rep("2", 1024) ..
                                            string.rep("3", 1024) ..
                                            string.rep("a", 1024)))

            ngx.say(ngx.encode_base64(string.sub(s, -16))) -- should be same as above

        }
    }
--- request
    GET /t
--- response_body eval
"XZElJKMyKzuvbYNf4Y0hAw==
59Cw1+C6hHpfqsOn7PZ2Gw==
t6oGLYvnjihoi+7tPfyK/A==
final
QcpC0TXDxiOln2ENZ0aGDA==
QcpC0TXDxiOln2ENZ0aGDA==
"
--- no_error_log
[error]
