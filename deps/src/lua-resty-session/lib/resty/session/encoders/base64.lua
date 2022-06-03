local encode_base64 = ngx.encode_base64
local decode_base64 = ngx.decode_base64

local gsub = string.gsub

local ENCODE_CHARS = {
    ["+"] = "-",
    ["/"] = "_",
}

local DECODE_CHARS = {
    ["-"] = "+",
    ["_"] = "/",
}

local encoder = {}

function encoder.encode(value)
    if not value then
        return nil, "unable to base64 encode value"
    end

    local encoded = encode_base64(value, true)
    if not encoded then
        return nil, "unable to base64 encode value"
    end

    return gsub(encoded, "[+/]", ENCODE_CHARS)
end

function encoder.decode(value)
    if not value then
        return nil, "unable to base64 decode value"
    end

    return decode_base64((gsub(value, "[-_]", DECODE_CHARS)))
end

return encoder
