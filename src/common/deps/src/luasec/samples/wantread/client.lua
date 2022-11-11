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
}


local function wait(peer, err)
   if err == "timeout" or err == "wantread" then
      socket.select({peer}, nil)
   elseif err == "wantwrite" then
      socket.select(nil, {peer})
   else
      peer:close()
      os.exit(1)
   end
end


local peer = socket.tcp()
assert( peer:connect("127.0.0.1", 8888) )

-- [[ SSL wrapper
peer = assert( ssl.wrap(peer, params) )
peer:settimeout(0.3)
local succ, err = peer:dohandshake()
while not succ do
   print("handshake", err)
   wait(peer, err)
   succ, err = peer:dohandshake()
end
print("** Handshake done")
--]]

-- If the section above is commented, the timeout is not set.
-- We set it again for safetiness.
peer:settimeout(0.3)  

local str, err, part = peer:receive("*l")
while not str do
   print(part, err)
   wait(peer, err)
   str, err, part = peer:receive("*l")
end
peer:close()
