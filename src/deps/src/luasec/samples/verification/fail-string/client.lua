--
-- Public domain
--
local socket = require("socket")
local ssl    = require("ssl")

local params = {
   mode = "client",
   protocol = "tlsv1",
   key = "../../certs/clientBkey.pem",
   certificate = "../../certs/clientB.pem",
   cafile = "../../certs/rootB.pem",
   verify = "none",
   options = "all",
}

local peer = socket.tcp()
peer:connect("127.0.0.1", 8888)

-- [[ SSL wrapper
peer = assert( ssl.wrap(peer, params) )
assert(peer:dohandshake())
--]]

local err, msg = peer:getpeerverification()
print(err, msg)

print(peer:receive("*l"))
peer:close()
