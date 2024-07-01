socket = require"socket"
socket.unix = require"socket.unix"
c = assert(socket.unix.dgram())
print(c:bind("/tmp/bar"))
while 1 do
    local l = io.read("*l")
    assert(c:sendto(l, "/tmp/foo"))
	print(assert(c:receivefrom()))
end
