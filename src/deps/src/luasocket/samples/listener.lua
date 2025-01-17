-----------------------------------------------------------------------------
-- TCP sample: Little program to dump lines received at a given port
-- LuaSocket sample files
-- Author: Diego Nehab
-----------------------------------------------------------------------------
local socket = require("socket")
host = host or "*"
port = port or 8080
if arg then
	host = arg[1] or host
	port = arg[2] or port
end
print("Binding to host '" ..host.. "' and port " ..port.. "...")
s = assert(socket.bind(host, port))
i, p   = s:getsockname()
assert(i, p)
print("Waiting connection from talker on " .. i .. ":" .. p .. "...")
c = assert(s:accept())
print("Connected. Here is the stuff:")
l, e = c:receive()
while not e do
	print(l)
	l, e = c:receive()
end
print(e)
