socket=require("socket");
os.remove("/tmp/luasocket")
socket.unix = require("socket.unix");
host = host or "luasocket";
server = assert(socket.unix())
assert(server:bind(host))
assert(server:listen(5))
ack = "\n";
while 1 do
    print("server: waiting for client connection...");
    control = assert(server:accept());
    while 1 do 
        command = assert(control:receive());
        assert(control:send(ack));
        ((loadstring or load)(command))();
    end
end
