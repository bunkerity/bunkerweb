local path = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
package.path = path .. "/?.lua;" .. package.path

local test = require "framework".test
local set_iteration = require "framework".set_iteration
local write_seperator = require "framework".write_seperator
local cipher = require "resty.openssl.cipher"
local version = require("resty.openssl.version")

local key = string.rep("0", 32)
local iv = string.rep("0", 16)
local data = string.rep("1", 4096)
local aad = string.rep("2", 10)

set_iteration(100000)

for _, t in ipairs({"aes-256-cbc", "aes-256-gcm", "chacha20-poly1305"}) do
    for _, op in ipairs({"encrypt", "decrypt"}) do 
        -- the fips version of boringssl we used seems don't have chacha20
        if t == "chacha20-poly1305" and (not version.OPENSSL_111_OR_LATER or version.BORINGSSL) then
            goto continue
        end

        local c = assert(cipher.new(t))
        local _iv = iv
        local _aad
        if t == "aes-256-gcm" or t == "chacha20-poly1305" then
            _iv = string.rep("0", 12)
            _aad = aad
        end

        if op == "encrypt" then
            test("encrypt with " .. t .. " on " .. #data .. " bytes", function()
                return c:encrypt(key, _iv, data, false, _aad)
            end)

        else
            local ciphertext = assert(c:encrypt(key, _iv, data, false, _aad))

            local tag
            if t == "aes-256-gcm" or t == "chacha20-poly1305" then
                tag = assert(c:get_aead_tag())
            end
            test("decrypt with " .. t .. " on " .. #ciphertext .. " bytes", function()
                return c:decrypt(key, _iv, ciphertext, false, _aad, tag)
            end)
        end
::continue::
    end

    write_seperator()
end
