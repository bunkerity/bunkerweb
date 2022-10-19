--
-- Public domain
--
local socket = require("socket")
local ssl    = require("ssl")

local pkey = require "openssl.pkey"
local ssl_context = require "openssl.ssl.context"
local x509 = require "openssl.x509"
local x509_store = require "openssl.x509.store"

local function read_file(path)
	local file, err, errno = io.open(path, "rb")
	if not file then
		return nil, err, errno
	end
	local contents
	contents, err, errno = file:read "*a"
	file:close()
	return contents, err, errno
end

local ctx = ssl_context.new("TLSv1_2", true)
ctx:setPrivateKey(pkey.new(assert(read_file("../certs/serverAkey.pem"))))
ctx:setCertificate(x509.new(assert(read_file("../certs/serverA.pem"))))
local store = x509_store.new()
store:add("../certs/rootA.pem")
ctx:setStore(store)
ctx:setVerify(ssl_context.VERIFY_FAIL_IF_NO_PEER_CERT)


local server = socket.tcp()
server:setoption('reuseaddr', true)
assert( server:bind("127.0.0.1", 8888) )
server:listen()

local peer = server:accept()

-- [[ SSL wrapper
peer = assert( ssl.wrap(peer, ctx) )

-- Before handshake: nil
print( peer:info() )

assert( peer:dohandshake() )
--]]

print("---")
local info = peer:info()
for k, v in pairs(info) do
  print(k, v)
end

print("---")
print("-> Compression", peer:info("compression"))

peer:send("oneshot test\n")
peer:close()
