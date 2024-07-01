-- load our favourite library
local dispatch = require("dispatch")
local handler = dispatch.newhandler()

-- make sure the user knows how to invoke us
if #arg < 1 then
    print("Usage")
    print("    lua forward.lua <iport:ohost:oport> ...")
    os.exit(1)
end

-- function to move data from one socket to the other
local function move(foo, bar)
    local live
    while 1 do
        local data, error, partial = foo:receive(2048)
        live = data or error == "timeout"
        data = data or partial
        local result, error = bar:send(data)
        if not live or not result then
            foo:close()
            bar:close()
            break
        end
    end
end

-- for each tunnel, start a new server
for i, v in ipairs(arg) do
    -- capture forwarding parameters
    local _, _, iport, ohost, oport = string.find(v, "([^:]+):([^:]+):([^:]+)")
    assert(iport, "invalid arguments")
    -- create our server socket
    local server = assert(handler.tcp())
    assert(server:setoption("reuseaddr", true))
    assert(server:bind("*", iport))
    assert(server:listen(32))
    -- handler for the server object loops accepting new connections
    handler:start(function()
        while 1 do
            local client = assert(server:accept())
            assert(client:settimeout(0))
            -- for each new connection, start a new client handler
            handler:start(function()
                -- handler tries to connect to peer
                local peer = assert(handler.tcp())
                assert(peer:settimeout(0))
                assert(peer:connect(ohost, oport))
                -- if sucessful, starts a new handler to send data from
                -- client to peer
                handler:start(function()
                    move(client, peer)
                end)
                -- afte starting new handler, enter in loop sending data from
                -- peer to client
                move(peer, client)
            end)
        end
    end)
end

-- simply loop stepping the server
while 1 do
    handler:step()
end
