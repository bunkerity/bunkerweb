-----------------------------------------------------------------------------
-- Select sample: simple text line server
-- LuaSocket sample files.
-- Author: Diego Nehab
-----------------------------------------------------------------------------
local socket = require("socket")
host = host or "*"
port1 = port1 or 8080
port2 = port2 or 8181
if arg then
    host = arg[1] or host
    port1 = arg[2] or port1
    port2 = arg[3] or port2
end

server1 = assert(socket.bind(host, port1))
server2 = assert(socket.bind(host, port2))
server1:settimeout(1) -- make sure we don't block in accept
server2:settimeout(1)

io.write("Servers bound\n")

-- simple set implementation
-- the select function doesn't care about what is passed to it as long as
-- it behaves like a table
-- creates a new set data structure
function newset()
    local reverse = {}
    local set = {}
    return setmetatable(set, {__index = {
        insert = function(set, value)
            if not reverse[value] then
                table.insert(set, value)
                reverse[value] = #set
            end
        end,
        remove = function(set, value)
            local index = reverse[value]
            if index then
                reverse[value] = nil
                local top = table.remove(set)
                if top ~= value then
                    reverse[top] = index
                    set[index] = top
                end
            end
        end
    }})
end

set = newset()

io.write("Inserting servers in set\n")
set:insert(server1)
set:insert(server2)

while 1 do
    local readable, _, error = socket.select(set, nil)
    for _, input in ipairs(readable) do
        -- is it a server socket?
        if input == server1 or input == server2 then
            io.write("Waiting for clients\n")
            local new = input:accept()
            if new then
                new:settimeout(1)
                io.write("Inserting client in set\n")
                set:insert(new)
            end
        -- it is a client socket
        else
            local line, error = input:receive()
            if error then
                input:close()
                io.write("Removing client from set\n")
                set:remove(input)
            else
            	io.write("Broadcasting line '", line, "'\n")
            	writable, error = socket.skip(1, socket.select(nil, set, 1))
            	if not error then
                	for __, output in ipairs(writable) do
                    	if output ~= input then
                            output:send(line .. "\n")
                        end
                	end
            	else io.write("No client ready to receive!!!\n") end
			end
        end
    end
end
