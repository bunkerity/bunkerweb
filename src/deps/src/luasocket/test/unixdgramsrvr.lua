    socket = require"socket"
    socket.unix = require"socket.unix"
    u = assert(socket.unix.dgram())
    assert(u:bind("/tmp/foo"))
    while 1 do
		x, r = assert(u:receivefrom())
		print(x, r)
		assert(u:sendto(">" .. x, r))
    end
