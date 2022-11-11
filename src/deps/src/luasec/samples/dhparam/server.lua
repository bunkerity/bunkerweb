--
-- Public domain
--
local socket = require("socket")
local ssl    = require("ssl")

local function readfile(filename)
  local fd = assert(io.open(filename))
  local dh = fd:read("*a")
  fd:close()
  return dh
end

local function dhparam_cb(export, keylength)
  print("---")
  print("DH Callback")
  print("Export", export)
  print("Key length", keylength)
  print("---")
  local filename
  if keylength == 512 then
    filename = "dh-512.pem"
  elseif keylength == 1024 then
    filename = "dh-1024.pem"
  else
    -- No key
    return nil
  end
  return readfile(filename)
end

local params = {
   mode = "server",
   protocol = "any",
   key = "../certs/serverAkey.pem",
   certificate = "../certs/serverA.pem",
   cafile = "../certs/rootA.pem",
   verify = {"peer", "fail_if_no_peer_cert"},
   options = "all",
   dhparam = dhparam_cb,
   ciphers = "EDH+AESGCM"
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

peer:send("oneshot test\n")
peer:close()
