local pkey = require("resty.openssl.pkey")

local priv = assert(pkey.new())
local pub = assert(pkey.new(priv:to_PEM("public")))

local original = "original text"

-- same as nodejs: crypto.privateEncrypt
--            php: openssl_private_encrypt
local digested = assert(priv:sign_raw(original))

print("Digested message: " .. ngx.encode_base64(digested))

-- same as nodejs: crypto.publicDecrypt
--            php: openssl_public_decrypt
local recovered = assert(pub:verify_recover(digested))
print("Recovered message: " .. recovered)
