--
-- Public domain
--
local socket = require("socket")
local ssl    = require("ssl")

local params = {
   mode = "client",
   protocol = "tlsv1_2",
   key = "../certs/clientAkey.pem",
   certificate = "../certs/clientA.pem",
   cafile = "../certs/rootA.pem",
   verify = {"peer", "fail_if_no_peer_cert"},
   options = "all",
   --
   curve = "secp384r1",
}

--------------------------------------------------------------------------------
local peer = socket.tcp()
peer:connect("127.0.0.1", 8888)

peer = assert( ssl.wrap(peer, params) )
assert(peer:dohandshake())

print("--- INFO  ---")
local info = peer:info()
for k, v in pairs(info) do
  print(k, v)
end
print("---")

peer:close()
