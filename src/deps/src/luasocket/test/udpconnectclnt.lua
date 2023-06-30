local socket = require"socket"
local udp = socket.udp
local localhost = "127.0.0.1"
local port = assert(arg[1], "missing port argument")

se = udp(); se:setoption("reuseaddr", true)
se:setsockname(localhost, 5062)
print("se", se:getsockname())
sc = udp(); sc:setoption("reuseaddr", true)
sc:setsockname(localhost, 5061)
print("sc", sc:getsockname())

se:sendto("this is a test from se", localhost, port)
socket.sleep(1)
sc:sendto("this is a test from sc", localhost, port)
socket.sleep(1)
se:sendto("this is a test from se", localhost, port)
socket.sleep(1)
sc:sendto("this is a test from sc", localhost, port)
