--
-- Public domain
--
local socket = require("socket")
local ssl    = require("ssl")

local params = {
   mode = "client",
   protocol = "tlsv1_2",
   key = "../certs/serverBkey.pem",
   certificate = "../certs/serverB.pem",
   cafile = "../certs/rootB.pem",
   verify = {"peer", "fail_if_no_peer_cert"},
   verifyext = {"lsec_continue", "lsec_ignore_purpose"},
   options = "all",
}

local ctx = assert(ssl.newcontext(params))

local peer = socket.tcp()
peer:connect("127.0.0.1", 8888)

peer = assert( ssl.wrap(peer, ctx) )
assert(peer:dohandshake())

local succ, errs = peer:getpeerverification()
print(succ, errs)
for i, err in pairs(errs) do
  for j, msg in ipairs(err) do
    print("depth = " .. i, "error = " .. msg)
  end
end

print(peer:receive("*l"))
peer:close()
