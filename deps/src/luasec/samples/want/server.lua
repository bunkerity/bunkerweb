--
-- Public domain
--
local socket = require("socket")
local ssl    = require("ssl")

local params = {
   mode = "server",
   protocol = "any",
   key = "../certs/serverAkey.pem",
   certificate = "../certs/serverA.pem",
   cafile = "../certs/rootA.pem",
   verify = {"peer", "fail_if_no_peer_cert"},
   options = "all",
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
socket.sleep(2) -- force the timeout in the client dohandshake()
assert( peer:dohandshake() )
--]]

for i = 1, 10 do
   local v = tostring(i)
   io.write(v)
   io.flush()
   peer:send(v)
   socket.sleep(1) -- force the timeout in the client receive()
end
io.write("\n")
peer:send("\n")
peer:close()
