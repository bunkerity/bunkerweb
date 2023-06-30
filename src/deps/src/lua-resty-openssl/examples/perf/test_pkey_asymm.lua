local path = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
package.path = path .. "/?.lua;" .. package.path

local test = require "framework".test
local set_iteration = require "framework".set_iteration
local pkey = require "resty.openssl.pkey"
local version = require("resty.openssl.version")
local data = string.rep("=", 200)

set_iteration(1000)

local rsa = pkey.new({ type = "RSA", bits = 4096 })

for _, op in ipairs({"encrypt", "decrypt"}) do 
    if op == "encrypt" then
        test("encrypt with RSA on " .. #data .. " bytes", function()
            return rsa:encrypt(data)
        end)

    else

        local ciphertext = assert(rsa:encrypt(data))
        test("decrypt with RSA on " .. #ciphertext .. " bytes", function()
            return rsa:decrypt(ciphertext)
        end)
    end
end


for _, t in ipairs({"RSA", "EC", "Ed25519", "Ed448"}) do
    for _, op in ipairs({"sign", "verify"}) do
        -- the fips version of boringssl we used seems don't have ed448
        if (t == "Ed25519" and not version.OPENSSL_111_OR_LATER) or (t == "Ed448" and version.BORINGSSL) then
            goto continue
        end

        local opts = { type = t }
        if t == "EC" then
            opts.curve = "prime256v1"
        elseif t == "RSA" then
            opts.bits = 4096
        end

        local c = assert(pkey.new(opts))
        local md_alg
        if t == "RSA" or t == "EC" then
            md_alg = "SHA256"
        end

        if op == "sign" then
            test("sign with " .. t .. (md_alg and ("-" .. md_alg) or "") .. " on " .. #data .. " bytes", function()
                return c:sign(data, md_alg)
            end)

        else
            local sig = assert(c:sign(data, md_alg)) 

            test("verify with " .. t .. (md_alg and ("-" .. md_alg) or "") .. " on " .. #data .. " bytes", function()
                return c:verify(sig, data, md_alg)
            end)
        end
::continue::
    end
end
