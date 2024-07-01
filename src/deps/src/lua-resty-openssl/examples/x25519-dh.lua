local pkey = require("resty.openssl.pkey")

-- alice's private key
local alice_priv = assert(pkey.new({
  type = "X25519"
}))
-- alice's public key, shared with bob
local alice_pub = assert(pkey.new(alice_priv:to_PEM("public")))

-- bob's private key
local bob_priv = assert(pkey.new({
  type = "X25519"
}))
-- bobs' public key, shared with alice
local bob_pub = assert(pkey.new(bob_priv:to_PEM("public")))

ngx.say("alice and bob hold ",
  alice_priv:to_PEM() == bob_priv:to_PEM() and "same keys" or "different keys")

ngx.say("")

local k1 = assert(alice_priv:derive(bob_pub))
ngx.say("alice use this key to talk with bob: ", ngx.encode_base64(k1))

local k2 = assert(bob_priv:derive(alice_pub))
ngx.say("bob use this key to talk with alice: ", ngx.encode_base64(k2))

ngx.say("")

ngx.say(k1 == k2 and "key exchange is correct" or "key exchange is not correct")

