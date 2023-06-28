-----------------------------------------------------------------------------
-- UDP sample: echo protocol client
-- LuaSocket sample files
-- Author: Diego Nehab
-----------------------------------------------------------------------------
local socket = require("socket")
host = host or "localhost"
port = port or 7
if arg then
    host = arg[1] or host
    port = arg[2] or port
end
host = socket.dns.toip(host)
udp = assert(socket.udp())
assert(udp:setpeername(host, port))
print("Using remote host '" ..host.. "' and port " .. port .. "...")
while 1 do
	line = io.read()
	if not line or line == "" then os.exit() end
	assert(udp:send(line))
	dgram = assert(udp:receive())
	print(dgram)
end
