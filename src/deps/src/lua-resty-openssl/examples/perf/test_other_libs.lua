local path = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
package.path = path .. "/?.lua;" .. package.path

local test = require "framework".test
local set_iteration = require "framework".set_iteration
local write_seperator = require "framework".write_seperator
local cipher = require "resty.openssl.cipher"
local digest = require "resty.openssl.digest"
local hmac = require "resty.openssl.hmac"
local pkey = require "resty.openssl.pkey"
local version = require "resty.openssl.version"
local rand = require "resty.openssl.rand"
local kdf = require "resty.openssl.kdf"
local aes = require "resty.aes"
local resty_rsa = require "resty.rsa"
local to_hex = require "resty.string".to_hex

-- ensure best performance
require "framework".set_no_count_iter(true)

local luaossl
do
    local pok, perr, err = pcall(require, "_openssl")
    if pok then
        luaossl = perr
    end
end

local lua_openssl
do
    -- move openssl.so to lua-openssl.so to avoid conflict with luaossl
    local pok, perr, err = pcall(require, "lua-openssl")
    if pok then
        lua_openssl = perr
    end
end

local lua_pack
do
    local pok, perr, err = pcall(require, "lua_pack")
    if pok then
        lua_pack = perr
    end
end

local v = require "jit.dump"
v.on(nil, "/tmp/a.out")

------------- bn
do
    set_iteration(1000000)

    local binary_input = rand.bytes(24)
    local bn = require "resty.openssl.bn"
    local hex_input = assert(bn.from_binary(binary_input)):to_hex()

    test("lua-resty-openssl bn unpack parse binary", function()
        return bn.new(hex_input, 16)
    end)

    local bni = bn.new()
    test("lua-resty-openssl bn unpack parse binary reused struct", function()
        return bni:set(hex_input, 16)
    end)

    if luaossl then
        local luaossl_bn = require "_openssl.bignum"
        local hex_input = "0X" .. hex_input

        test("luaossl bn unpack parse binary", function()
            return luaossl_bn.new(hex_input)
        end)
    end

    if lua_openssl then
        local hex_input = "X" .. hex_input
        test("lua-openssl bn unpack parse binary", function()
            return lua_openssl.bn.number(hex_input)
        end)
    end

    if lua_pack then
        test("lua_pack bn unpack 6 int", function()
            return lua_pack.unpack(binary_input, ">6I")
        end)
    end
end

------------- cipher
do
    write_seperator()

    local key = rand.bytes(32)
    local iv = rand.bytes(16)
    local data = string.rep("1", 4096)

    set_iteration(100000)

    for _, t in ipairs({"aes-256-cbc", "aes-256-gcm"}) do
        for _, op in ipairs({"encrypt", "decrypt"}) do

            local c = assert(cipher.new(t))
            cipher.set_buffer_size(#data + 64) -- add room for decrypt

            local _iv = iv
            if t == "aes-256-gcm" then
                _iv = string.rep("0", 12)
            end

            local aes_default
            if t == "aes-256-cbc" then
                aes_default = aes:new(key, nil, aes.cipher(256, "cbc"), {iv = _iv})
            else
                aes_default = aes:new(key, nil, aes.cipher(256, "gcm"), {iv = _iv})
            end

            local luaossl_aes
            if luaossl then
                local luaossl_cipher = require "_openssl.cipher"
                luaossl_aes = luaossl_cipher.new(t)
            end

            local ciphertext = assert(c:encrypt(key, _iv, data, false))

            if op == "encrypt" then
                -- assert(c:init(key, _iv, {is_encrypt = true }))
                -- assert(c:encrypt(key, _iv, data, false))
                test("lua-resty-openssl encrypt with " .. t .. " on " .. #data .. " bytes", function()
                    return c:encrypt(key, _iv, data, false)
                    -- return c:final(data)
                end, nil, ciphertext)

                test("lua-resty-strings encrypt with " .. t .. " on " .. #data .. " bytes", function()
                    local r = aes_default:encrypt(data)
                    if t == "aes-256-gcm" then
                        return r[1]
                    end
                    return r
                end, nil, ciphertext)

                if luaossl then
                    test("luaossl encrypt with " .. t .. " on " .. #data .. " bytes", function()
                        return luaossl_aes:encrypt(key, _iv):final(data)
                    end, nil, ciphertext)
                end

                if lua_openssl then
                    local evp_cipher = lua_openssl.cipher.get(t)
                    test("lua_openssl encrypt with " .. t .. " on " .. #data .. " bytes", function()
                        return evp_cipher:encrypt(data, key, _iv)
                    end, nil, ciphertext)
                end


            else

                local tag
                if t == "aes-256-gcm" then
                    tag = assert(c:get_aead_tag())
                end
                -- assert(c:init(key, _iv))
                test("lua-resty-openssl decrypt with " .. t .. " on " .. #ciphertext .. " bytes", function()
                    -- if tag then
                    --    c:set_aead_tag(tag)
                    --end
                    --return c:final(ciphertext)
                    return c:decrypt(key, _iv, ciphertext, false, nil, tag)
                end, nil, data)


                test("lua-resty-strings decrypt with " .. t .. " on " .. #ciphertext .. " bytes", function()
                    return aes_default:decrypt(ciphertext, tag)
                end, nil, data)

                if luaossl then
                    --local luaossl_cipher = require "openssl.cipher"
                    --local luaossl_aes2 = luaossl_cipher.new(t)

                    test("luaossl decrypt with " .. t .. " on " .. #ciphertext .. " bytes", function()
                        luaossl_aes:decrypt(key, _iv)
                        if t == "aes-256-gcm" then
                            luaossl_aes:setTag(tag)
                        end
                        return luaossl_aes:final(ciphertext)
                    end, nil, data)
                end


                if lua_openssl then
                    local evp = lua_openssl.cipher.get(t)

                    local d = evp:decrypt_new(key, _iv)
                    test("lua_openssl decrypt with " .. t .. " on " .. #ciphertext .. " bytes", function()
                        d:ctrl(lua_openssl.cipher.EVP_CTRL_GCM_SET_IVLEN, #_iv)
                        d:init(key, _iv)
                        d:padding(false)

                        local r = d:update(ciphertext)
                        if t == "aes-256-gcm" then
                            assert(d:ctrl(lua_openssl.cipher.EVP_CTRL_GCM_SET_TAG, tag))
                        end
                        return r .. d:final()
                    end) -- has extra padding: , nil, data)
                end
            end
    ::continue::
        end

        write_seperator()
    end
end

------------- digest
do
    write_seperator()

    local data = string.rep("1", 4096)

    for _, t in ipairs({"sha256", "md5"}) do

        local d = digest.new(t)

        local expected = d:final(data)

        test("lua-resty-openssl " .. t .. " on " .. #data .. " bytes", function()
            d:reset()
            return d:final(data)
        end, nil, expected)

        local h = require ("resty." .. t)
        local hh = h:new()

        test("lua-resty-strings " .. t .. " on " .. #data .. " bytes", function()
            hh:reset()
            hh:update(data)
            return hh:final()
        end, nil, expected)

        if luaossl then
            local _digest = require "_openssl.digest"
            test("luaossl " .. t .. " on " .. #data .. " bytes", function()
                local hh = _digest.new(t)
                return hh:final(data)
            end, nil, expected)
        end

        if lua_openssl then
            local hh = lua_openssl.digest.get(t)
            test("lua_openssl " .. t .. " on " .. #data .. " bytes", function()
                return hh:digest(data)
            end, nil, expected)
        end

        if t == "md5" then
            test("ngx.md5_bin on " .. #data .. " bytes", function()
                return ngx.md5_bin(data)
            end, nil, expected)
        end
    end

end

------------- hmac
do
    write_seperator()

    local data = string.rep("1", 4096)
    local key = rand.bytes(32)

    local d = hmac.new(key, "sha256")

    local expected = d:final(data)

    test("lua-resty-openssl hmac sha256 on " .. #data .. " bytes", function()
        d:reset()
        return d:final(data)
    end, nil, expected)

    if version.OPENSSL_3X then
        local mac = require "resty.openssl.mac"
        local m = mac.new(key, "HMAC", nil, "sha256")
        test("lua-resty-openssl hmac sha256 new API on " .. #data .. " bytes", function()
            m:reset()
            return m:final(data)
        end, nil, expected)
    end

    if luaossl then
        local _hmac = require "_openssl.hmac"
        test("luaossl hmac sha256 " .. #data .. " bytes", function()
            local hh = _hmac.new(key, "sha256")
            return hh:final(data)
        end, nil, expected)
    end

    if lua_openssl then
        local hh = lua_openssl.hmac
        test("lua_openssl hmac sha256 on " .. #data .. " bytes", function()
            return hh.hmac("sha256", data, key)
        end, nil, to_hex(expected))

        if version.OPENSSL_3X then
            local mm = lua_openssl.mac
            test("lua_openssl hmac sha256 new API on " .. #data .. " bytes", function()
                return mm.mac("sha256", data, key)
            end, nil, to_hex(expected))
        end
    end
end

------------- pkey
do
    write_seperator()

    local key = pkey.new({ type = "RSA", bits = 4096 })
    local data = string.rep("1", 200)
    local rsa_encrypted = assert(key:encrypt(data, pkey.PADDINGS.RSA_PKCS1_PADDING))

    set_iteration(1000)

    for _, op in ipairs({"encrypt", "decrypt"}) do
        local _data = data
        if op == "decrypt" then
            _data = rsa_encrypted
        end

        local f = key[op]
        test("lua-resty-openssl RSA " .. op .. " on " .. #data .. " bytes", function()
            return f(key, _data)
        end)

        if not version.OPENSSL_3X then
            local pub = resty_rsa:new({ public_key = key:to_PEM("public"), padding = resty_rsa.PADDING.RSA_PKCS1_PADDING })
            local priv = resty_rsa:new({ private_key = key:to_PEM("private"), padding = resty_rsa.PADDING.RSA_PKCS1_PADDING })

            local _key = pub
            if op == "decrypt" then
                _key = priv
            end

            local f = _key[op]
            test("lua-resty-rsa RSA " .. op .." on " .. #data .. " bytes", function()
                return f(_key, _data)
            end)
        end

        if luaossl then
            local _key = require "_openssl.pkey".new(key:to_PEM("private"))
            local f = _key[op]
            test("luaossl RSA " .. op .." on " .. #data .. " bytes", function()
                return f(_key, _data)
            end)
        end


        if lua_openssl then
            local _key = lua_openssl.pkey.read(key:to_PEM("private"), true)
            local f = _key[op]
            test("lua_openssl RSA " .. op .." on " .. #data .. " bytes", function()
                return f(_key, _data)
            end)
        end
    end

end

------------- kdf
do
    write_seperator()

    local kdf_out_size = 64
    local kdf_pass = "1234567"
    local kdf_md = "md5"
    local kdf_salt = rand.bytes(16)

    set_iteration(500)

    local kdf_opts = {
        type = kdf.PBKDF2,
        outlen = kdf_out_size,
        pass = kdf_pass,
        md = kdf_md,
        salt = kdf_salt,
        pbkdf2_iter = 1000,
    }
    local expected = assert(kdf.derive(kdf_opts))

    test("lua-resty-openssl kdf pbkdf2 outputs " .. kdf_out_size .. " bytes", function()
        return kdf.derive(kdf_opts)
    end)

    if version.OPENSSL_3X then
        local kdfi = kdf.new("pbkdf2")
        kdf_opts = {
            pass = kdf_pass,
            iter = 1000,
            digest = kdf_md,
            salt = kdf_salt,
        }
        test("lua-resty-openssl kdf new API pbkdf2 outputs " .. kdf_out_size .. " bytes", function()
            return kdfi:derive(kdf_out_size, kdf_opts)
        end, nil, expected)
    end

    if luaossl then
        local _kdf = require "_openssl.kdf"
        local kdf_opts = {
            type = "PBKDF2",
            outlen = kdf_out_size,
            pass = kdf_pass,
            md = kdf_md,
            salt = kdf_salt,
            iter = 1000,
        }
        test("luaossl kdf pbkf2 outputs " .. kdf_out_size .. " bytes", function()
            return _kdf.derive(kdf_opts)
        end, nil, expected)
    end


    if lua_openssl and version.OPENSSL_3X then
        local _kdf = lua_openssl.kdf.fetch('PBKDF2')
        local kdf_opts = {
            { name = "pass", data = kdf_pass },
            { name = "iter", data = 1000 },
            { name = "digest", data = kdf_md },
            { name = "salt", data = kdf_salt },
        }
        test("lua_openssl kdf pbkf2 outputs " .. kdf_out_size .. " bytes", function()
            return _kdf:derive(kdf_opts, kdf_out_size)
        end, nil, expected)
    end
end
