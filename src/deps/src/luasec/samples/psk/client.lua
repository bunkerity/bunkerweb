--
-- Public domain
--
local socket = require("socket")
local ssl    = require("ssl")

if not ssl.config.capabilities.psk then
   print("[ERRO] PSK not available")
   os.exit(1)
end

-- @param hint (nil | string)
-- @param max_identity_len (number)
-- @param max_psk_len (number)
-- @return identity (string)
-- @return PSK (string)
local function pskcb(hint, max_identity_len, max_psk_len)
   print(string.format("PSK Callback: hint=%q, max_identity_len=%d, max_psk_len=%d", hint, max_identity_len, max_psk_len))
   return "abcd", "1234"
end

local params = {
   mode = "client",
   protocol = "tlsv1_2",
   psk = pskcb,
}

local peer = socket.tcp()
peer:connect("127.0.0.1", 8888)

peer = assert( ssl.wrap(peer, params) )
assert(peer:dohandshake())

print("--- INFO ---")
local info = peer:info()
for k, v in pairs(info) do
   print(k, v)
end
print("---")

peer:close()
