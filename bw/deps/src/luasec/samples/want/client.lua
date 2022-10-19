--
-- Test the conn:want() function
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

-- Wait until socket is ready (for reading or writing)
local function wait(peer)
   -- What event blocked us?
   local err
   if peer.want then  -- Is it an SSL connection?
     err = peer:want()
     print("Want? ", err)
   else
     -- No, it's a normal TCP connection...
     err = "timeout"
   end

   if err == "read" or err == "timeout" then
      socket.select({peer}, nil)
   elseif err == "write" then
      socket.select(nil, {peer})
   else
      peer:close()
      os.exit(1)
   end
end

-- Start the TCP connection
local peer = socket.tcp()
assert( peer:connect("127.0.0.1", 8888) )

-- [[ SSL wrapper
peer = assert( ssl.wrap(peer, params) )
peer:settimeout(0.3)
local succ = peer:dohandshake()
while not succ do
   wait(peer)
   succ = peer:dohandshake()
end
print("** Handshake done")
--]]

-- If the section above is commented, the timeout is not set.
-- We set it again for safetiness.
peer:settimeout(0.3)

-- Try to receive a line
local str = peer:receive("*l")
while not str do
   wait(peer)
   str = peer:receive("*l")
end
peer:close()
