-----------------------------------------------------------------------------
-- UDP sample: daytime protocol client
-- LuaSocket sample files
-- Author: Diego Nehab
-----------------------------------------------------------------------------
local socket = require"socket"
host = host or "127.0.0.1"
port = port or 13
if arg then
    host = arg[1] or host
    port = arg[2] or port
end
host = socket.dns.toip(host)
udp = socket.udp()
print("Using host '" ..host.. "' and port " ..port.. "...")
udp:setpeername(host, port)
udp:settimeout(3)
sent, err = udp:send("anything")
if err then print(err) os.exit() end
dgram, err = udp:receive()
if not dgram then print(err) os.exit() end
io.write(dgram)
