--
-- Public domain
--
local socket = require("socket")
local ssl    = require("ssl")

local params = {
   mode        = "client",
   protocol    = "tlsv1_2",
   key         = "certs/clientECDSAkey.pem",
   certificate = "certs/clientECDSA.pem",
   verify      = "none",
   options     = "all",
   ciphers     = "ALL:!aRSA"
}

local peer = socket.tcp()
peer:connect("127.0.0.1", 8888)

-- [[ SSL wrapper
peer = assert( ssl.wrap(peer, params) )
assert(peer:dohandshake())
--]]

local i = peer:info()
for k, v in pairs(i) do print(k, v) end

print(peer:receive("*l"))
peer:close()
