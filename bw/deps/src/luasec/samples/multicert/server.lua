--
-- Public domain
--
local socket = require("socket")
local ssl    = require("ssl")

local params = {
   mode         = "server",
   protocol     = "any",
   certificates = { 
      -- Comment line below and 'client-rsa' stop working
      { certificate = "certs/serverRSA.pem",   key = "certs/serverRSAkey.pem"   },
      -- Comment line below and 'client-ecdsa' stop working
      { certificate = "certs/serverECDSA.pem", key = "certs/serverECDSAkey.pem" }
   },
   verify  = "none",
   options = "all"
}


-- [[ SSL context
local ctx = assert(ssl.newcontext(params))
--]]

local server = socket.tcp()
server:setoption('reuseaddr', true)
assert( server:bind("127.0.0.1", 8888) )
server:listen()

local peer = server:accept()

-- [[ SSL wrapper
peer = assert( ssl.wrap(peer, ctx) )
assert( peer:dohandshake() )
--]]

peer:send("oneshot test\n")
peer:close()
