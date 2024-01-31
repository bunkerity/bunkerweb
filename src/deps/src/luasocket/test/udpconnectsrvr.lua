local socket = require"socket"
local udp = socket.udp
local localhost = "127.0.0.1"
local s = assert(udp())
assert(tostring(s):find("udp{unconnected}"))
print("setpeername", s:setpeername(localhost, 5061))
print("getsockname", s:getsockname())
assert(tostring(s):find("udp{connected}"))
print(s:receive())
print("setpeername", s:setpeername("*"))
print("getsockname", s:getsockname())
s:sendto("a", localhost, 12345)
print("getsockname", s:getsockname())
assert(tostring(s):find("udp{unconnected}"))
print(s:receivefrom())
s:close()
