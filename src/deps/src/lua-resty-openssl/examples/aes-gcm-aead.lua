local key = string.rep("0", 32)
local iv = string.rep("0", 12)

local to_be_encrypted = "secret"

local aad = "aead aad"

local mode = "aes-256-gcm"
-- local mode = "chacha20-poly1305"
ngx.say("use cipher ", mode)

-- using one shot interface
local cipher = assert(require("resty.openssl.cipher").new(mode))
local encrypted = assert(cipher:encrypt(key, iv, to_be_encrypted, false, aad))
-- OR using streaming interface
assert(cipher:init(key, iv, {
  is_encrypt = true,
}))
assert(cipher:update_aead_aad(aad))
encrypted = assert(cipher:final(to_be_encrypted))

ngx.say("encryption result: ", ngx.encode_base64(encrypted))

local tag = assert(cipher:get_aead_tag())

ngx.say("tag is: ", ngx.encode_base64(tag), " ", #tag)

local _, err = cipher:decrypt(key, iv, encrypted, false, nil, tag)
if err then
  ngx.say("no AAD, decryption failed")
end

local _, err = cipher:decrypt(key, iv, encrypted, false, "wrong", tag)
if err then
  ngx.say("wrong AAD, decryption failed")
end

-- this seems not working for chacha20-poly1305
local _, err = cipher:decrypt(key, iv, encrypted, false, aad, nil)
if err then
  ngx.say("no tag, decryption failed")
end

local _, err = cipher:decrypt(key, iv, encrypted, false, aad, "wrong")
if err then
  ngx.say("wrong tag, decryption failed")
end

-- using one shot interface
local decrypted = assert(cipher:decrypt(key, iv, encrypted, false, aad, tag))
-- OR using streaming interface
assert(cipher:init(key, iv, {
  is_encrypt = false,
}))
assert(cipher:update_aead_aad(aad))
assert(cipher:set_aead_tag(tag))
decrypted = assert(cipher:final(encrypted))

ngx.say("decryption result: ", decrypted)

--[[
Note in some implementations like `libsodium` or Java, AEAD ciphers append the `tag` (or `MAC`)
at the end of encrypted ciphertext. In such case, user will need to manually cut off the `tag`
with correct size(usually 16 bytes) and pass in the ciphertext and `tag` seperately.

-- encrypt with libsodium and decrypt in lua-resty-openssl

<? php
$encrypted_with_tag = sodium_crypto_aead_aes256gcm_encrypt(
    $to_be_encrypted,
    $aad,
    $iv,
    $key
);
?>

local tag = string.sub(encrypted_with_tag, #encrypted_with_tag-16, #encrypted_with_tag)
local encrypted = string.sub(encrypted_with_tag, 1, #encrypted_with_tag-16)
local decrypted = assert(cipher:decrypt(key, iv, encrypted, false, aad, tag))


-- encrypt with lua-resty-openssl and decrypt in libsodium

local encrypted = assert(cipher:encrypt(key, iv, to_be_encrypted, false, aad))
local tag = assert(cipher:get_aead_tag())

<? php
$decrypted = sodium_crypto_aead_aes256gcm_decrypt(
    $encrypted . $tag,
    $aad,
    $iv,
    $key
);
?>

]]--

--[[
  If the encryption is not done properly, it's possible that no tag is provided after all.
  In such case, use the streaming interface and call update() instead of final()
]]

assert(cipher:init(key, iv, {
  is_encrypt = false,
}))
assert(cipher:update_aead_aad(aad))
decrypted = assert(cipher:update(encrypted))

ngx.say("decryption result (without checking MAC): ", decrypted)

