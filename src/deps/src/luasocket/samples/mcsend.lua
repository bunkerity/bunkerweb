local socket = require"socket"
local group = "225.0.0.37"
local port = 12345
local c = assert(socket.udp())
--print(assert(c:setoption("reuseport", true)))
--print(assert(c:setsockname("*", port)))
--print(assert(c:setoption("ip-multicast-loop", false)))
--print(assert(c:setoption("ip-multicast-ttl", 4)))
--print(assert(c:setoption("ip-multicast-if", "10.0.1.3")))
--print(assert(c:setoption("ip-add-membership", {multiaddr = group, interface = "*"})))
local i = 0
while 1 do
    local message = string.format("hello all %d!", i)
    assert(c:sendto(message, group, port))
    print("sent " .. message)
    socket.sleep(1)
    c:settimeout(0.5)
    print(c:receivefrom())
    i = i + 1
end
