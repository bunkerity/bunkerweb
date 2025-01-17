local socket = require("socket")
local ssl    = require("ssl")

local params01 = {
  mode = "server",
  protocol = "any",
  key = "../certs/serverAkey.pem",
  certificate = "../certs/serverA.pem",
  cafile = "../certs/rootA.pem",
  verify = "none",
  options = "all",
  ciphers = "ALL:!ADH:@STRENGTH",
}

local params02 = {
  mode = "server",
  protocol = "any",
  key = "../certs/serverAAkey.pem",
  certificate = "../certs/serverAA.pem",
  cafile = "../certs/rootA.pem",
  verify = "none",
  options = "all",
  ciphers = "ALL:!ADH:@STRENGTH",
}

--
local ctx01 = ssl.newcontext(params01)
local ctx02 = ssl.newcontext(params02)

--
local server = socket.tcp()
server:setoption('reuseaddr', true)
server:bind("127.0.0.1", 8888)
server:listen()
local conn = server:accept()
--

-- Default context (when client does not send a name) is ctx01
conn = ssl.wrap(conn, ctx01)

-- Configure the name map
local sni_map = {
  ["servera.br"]  = ctx01,
  ["serveraa.br"] = ctx02,
}

conn:sni(sni_map, true)

assert(conn:dohandshake())
--
conn:send("one line\n")
conn:close()
