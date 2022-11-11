--
-- Public domain
--
local socket = require("socket")
local ssl    = require("ssl")

local params = {
   mode = "client",
   protocol = "any",
   key = "../certs/clientAkey.pem",
   certificate = "../certs/clientA.pem",
   cafile = "../certs/rootA.pem",
   verify = {"peer", "fail_if_no_peer_cert"},
   options = "all",
   ciphers = "EDH+AESGCM"
}

local peer = socket.tcp()
peer:connect("127.0.0.1", 8888)

-- [[ SSL wrapper
peer = assert( ssl.wrap(peer, params) )
assert(peer:dohandshake())
--]]

print(peer:receive("*l"))
peer:close()
