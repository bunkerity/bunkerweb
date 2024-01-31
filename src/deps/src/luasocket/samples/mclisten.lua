local socket = require"socket"
local group = "225.0.0.37"
local port = 12345
local c = assert(socket.udp())
print(assert(c:setoption("reuseport", true)))
print(assert(c:setsockname("*", port)))
--print("loop:", c:getoption("ip-multicast-loop"))
--print(assert(c:setoption("ip-multicast-loop", false)))
--print("loop:", c:getoption("ip-multicast-loop"))
--print("if:", c:getoption("ip-multicast-if"))
--print(assert(c:setoption("ip-multicast-if", "127.0.0.1")))
--print("if:", c:getoption("ip-multicast-if"))
--print(assert(c:setoption("ip-multicast-if", "10.0.1.4")))
--print("if:", c:getoption("ip-multicast-if"))
print(assert(c:setoption("ip-add-membership", {multiaddr = group, interface = "*"})))
while 1 do
    print(c:receivefrom())
end
