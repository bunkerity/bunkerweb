local socket = require("socket")
local ssl    = require("ssl")

local params = {
  mode = "client",
  protocol = "tlsv1_2",
  key = "../certs/clientAkey.pem",
  certificate = "../certs/clientA.pem",
  cafile = "../certs/rootA.pem",
  verify = "peer",
  options = "all",
}

local conn = socket.tcp()
conn:connect("127.0.0.1", 8888)

-- TLS/SSL initialization
conn = ssl.wrap(conn, params)

-- Comment the lines to not send a name
--conn:sni("servera.br")
--conn:sni("serveraa.br")
conn:sni("serverb.br")

assert(conn:dohandshake())
--
local cert = conn:getpeercertificate()
for k, v in pairs(cert:subject()) do
  for i, j in pairs(v) do
    print(i, j)
  end
end
--
print(conn:receive("*l"))
conn:close()
