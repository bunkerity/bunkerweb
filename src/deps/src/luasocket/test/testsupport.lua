function readfile(name)
    local f = io.open(name, "rb")
    if not f then return nil end
    local s = f:read("*a")
    f:close()
    return s
end

function similar(s1, s2)
    return string.lower(string.gsub(s1 or "", "%s", "")) ==
        string.lower(string.gsub(s2 or "", "%s", ""))
end

function fail(msg)
    msg = msg or "failed"
    error(msg, 2)
end

function compare(input, output)
    local original = readfile(input)
    local recovered = readfile(output)
    if original ~= recovered then fail("comparison failed")
    else print("ok") end
end

local G = _G
local set = rawset
local warn = print

local setglobal = function(table, key, value)
    warn("changed " .. key)
    set(table, key, value)
end

setmetatable(G, {
    __newindex = setglobal
})
