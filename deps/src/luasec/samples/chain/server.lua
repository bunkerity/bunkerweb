--
-- Public domain
--
local socket = require("socket")
local ssl    = require("ssl")
local util   = require("util")

local params = {
   mode = "server",
   protocol = "any",
   key = "../certs/serverAkey.pem",
   certificate = "../certs/serverA.pem",
   cafile = "../certs/rootA.pem",
   verify = {"peer", "fail_if_no_peer_cert"},
   options = "all",
}

local ctx = assert(ssl.newcontext(params))

local server = socket.tcp()
server:setoption('reuseaddr', true)
assert( server:bind("127.0.0.1", 8888) )
server:listen()

local conn = server:accept()

conn = assert( ssl.wrap(conn, ctx) )
assert( conn:dohandshake() )

util.show( conn:getpeercertificate() )

print("----------------------------------------------------------------------")

for k, cert in ipairs( conn:getpeerchain() ) do
  util.show(cert)
end

local f = io.open(params.certificate)
local str = f:read("*a")
f:close()

util.show( ssl.loadcertificate(str) )

print("----------------------------------------------------------------------")
local cert = conn:getpeercertificate()
print( cert )
print( cert:digest() )
print( cert:digest("sha1") )
print( cert:digest("sha256") )
print( cert:digest("sha512") )

conn:close()
server:close()
