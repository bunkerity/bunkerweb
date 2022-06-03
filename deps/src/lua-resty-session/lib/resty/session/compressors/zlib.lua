local zlib   = require "ffi-zlib"
local sio    = require "pl.stringio"

local concat = table.concat

local function gzip(func, input)
    local stream = sio.open(input)
    local output = {}
    local n = 0

    local ok, err = func(function(size)
        return stream:read(size)
    end, function(data)
        n = n + 1
        output[n] = data
    end, 8192)

    if not ok then
        return nil, err
    end

    if n == 0 then
        return ""
    end

    return concat(output, nil, 1, n)
end

local compressor = {}

function compressor.new()
    return compressor
end

function compressor.compress(_, data)
    return gzip(zlib.deflateGzip, data)
end

function compressor.decompress(_, data)
    return gzip(zlib.inflateGzip, data)
end

return compressor
