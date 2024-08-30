local pkey = require("resty.openssl.pkey")

-- sign_raw and verify_recover for RSA keys

local priv = assert(pkey.new())
local pub = assert(pkey.new(priv:to_PEM("public")))

local original = "original text"

-- same as nodejs: crypto.privateEncrypt
--            php: openssl_private_encrypt
local signed = assert(priv:sign_raw(original))

print("Signed message: " .. ngx.encode_base64(signed))

-- same as nodejs: crypto.publicDecrypt
--            php: openssl_public_decrypt
local recovered = assert(pub:verify_recover(signed))
print("Recovered message: " .. recovered)


-- sign_raw and verify_raw for non RSA keys

local priv = assert(pkey.new({
    type = "EC",
}))
local pub = assert(pkey.new(priv:to_PEM("public")))
local md_alg = "sha512"

local hashed = require "resty.openssl.digest".new(md_alg):final(original)

local signed = assert(priv:sign_raw(hashed))

print("Signed message: " .. ngx.encode_base64(signed))

local verified = assert(pub:verify_raw(signed, hashed, md_alg))
print("Verification result: ", verified)
