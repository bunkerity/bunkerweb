local rawget, rawset, setmetatable =
    rawget, rawset, setmetatable

local str_lower = string.lower

local _M = {
    _VERSION = '0.16.1',
}


-- Returns an empty headers table with internalised case normalisation.
function _M.new()
    local mt = {
        normalised = {},
    }

    mt.__index = function(t, k)
        return rawget(t, mt.normalised[str_lower(k)])
    end

    mt.__newindex = function(t, k, v)
        local k_normalised = str_lower(k)

        -- First time seeing this header field?
        if not mt.normalised[k_normalised] then
            -- Create a lowercased entry in the metatable proxy, with the value
            -- of the given field case
            mt.normalised[k_normalised] = k

            -- Set the header using the given field case
            rawset(t, k, v)
        else
            -- We're being updated just with a different field case. Use the
            -- normalised metatable proxy to give us the original key case, and
            -- perorm a rawset() to update the value.
            rawset(t, mt.normalised[k_normalised], v)
        end
    end

    return setmetatable({}, mt)
end


return _M
