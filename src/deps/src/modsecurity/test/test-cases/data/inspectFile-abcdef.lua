#!/usr/bin/lua

function main(filename)
    local file = io.open(filename, 'r')
    local chunk = file:read(1024)
    local ret = string.match(chunk, 'abcdef')
    io.close(file)

    return ret
end
