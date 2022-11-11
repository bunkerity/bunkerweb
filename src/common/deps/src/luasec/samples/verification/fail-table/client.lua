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
   verify = {"peer", "fail_if_no_peer_cert"},
   options = "all",
   verifyext = "lsec_continue",
}

-- [[ SSL context
local ctx = assert(ssl.newcontext(params))
--]]

local peer = socket.tcp()
peer:connect("127.0.0.1", 8888)

-- [[ SSL wrapper
peer = assert( ssl.wrap(peer, ctx) )
assert(peer:dohandshake())
--]]

local succ, errs = peer:getpeerverification()
print(succ, errs)
for i, err in pairs(errs) do
  for j, msg in ipairs(err) do
    print("depth = " .. i, "error = " .. msg)
  end
end

print(peer:receive("*l"))
peer:close()
