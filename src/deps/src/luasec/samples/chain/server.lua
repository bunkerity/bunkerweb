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

local expectedpeerchain = { "../certs/clientAcert.pem", "../certs/rootA.pem" }

local peerchain = conn:getpeerchain()
assert(#peerchain == #expectedpeerchain)
for k, cert in ipairs( peerchain ) do
  util.show(cert)
  local expectedpem = assert(io.open(expectedpeerchain[k])):read("*a")
  assert(cert:pem() == expectedpem, "peer chain mismatch @ "..tostring(k))
end

local expectedlocalchain = { "../certs/serverAcert.pem" }

local localchain = assert(conn:getlocalchain())
assert(#localchain == #expectedlocalchain)
for k, cert in ipairs( localchain ) do
  util.show(cert)
  local expectedpem = assert(io.open(expectedlocalchain[k])):read("*a")
  assert(cert:pem() == expectedpem, "local chain mismatch @ "..tostring(k))
  if k == 1 then
    assert(cert:pem() == conn:getlocalcertificate():pem())
  end
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
