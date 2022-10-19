--
-- Public domain
--
local socket = require("socket")
local ssl    = require("ssl")
local util   = require("util") 

local params = {
   mode = "client",
   protocol = "tlsv1_2",
   key = "../certs/clientAkey.pem",
   certificate = "../certs/clientA.pem",
   cafile = "../certs/rootA.pem",
   verify = {"peer", "fail_if_no_peer_cert"},
   options = "all",
}

local conn = socket.tcp()
conn:connect("127.0.0.1", 8888)

conn = assert( ssl.wrap(conn, params) )
assert(conn:dohandshake())

util.show( conn:getpeercertificate() )

print("----------------------------------------------------------------------")

for k, cert in ipairs( conn:getpeerchain() ) do
  util.show(cert)
end

local cert = conn:getpeercertificate()
print( cert )
print( cert:pem() )

conn:close()
