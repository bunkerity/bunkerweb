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

local ctx = ssl_context.new("TLSv1_2", false)
ctx:setPrivateKey(pkey.new(assert(read_file("../certs/clientAkey.pem"))))
ctx:setCertificate(x509.new(assert(read_file("../certs/clientA.pem"))))
local store = x509_store.new()
store:add("../certs/rootA.pem")
ctx:setStore(store)
ctx:setVerify(ssl_context.VERIFY_FAIL_IF_NO_PEER_CERT)

local peer = socket.tcp()
peer:connect("127.0.0.1", 8888)

-- [[ SSL wrapper
peer = assert( ssl.wrap(peer, ctx) )
assert(peer:dohandshake())
--]]

print(peer:receive("*l"))
peer:close()
