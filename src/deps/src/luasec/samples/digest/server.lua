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
assert( peer:dohandshake() )
--]]

local cert = peer:getpeercertificate()
local sha1   = cert:digest("sha1")
local sha256 = cert:digest("sha256")
local sha512 = cert:digest("sha512")

print("SHA1",   sha1)
print("SHA256", sha256)
print("SHA512", sha512)

peer:send("oneshot test\n")
peer:close()
