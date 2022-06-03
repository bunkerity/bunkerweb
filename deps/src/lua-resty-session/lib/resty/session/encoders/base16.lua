local to_hex   = require "resty.string".to_hex

local tonumber = tonumber
local gsub     = string.gsub
local char     = string.char

local function chr(c)
    return char(tonumber(c, 16) or 0)
end

local encoder = {}

function encoder.encode(value)
    if not value then
        return nil, "unable to base16 encode value"
    end

    return to_hex(value)
end

function encoder.decode(value)
    if not value then
        return nil, "unable to base16 decode value"
    end

    return (gsub(value, "..", chr))
end

return encoder
