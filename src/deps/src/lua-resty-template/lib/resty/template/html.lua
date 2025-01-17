local template = require "resty.template"
local setmetatable = setmetatable
local escape = template.escape
local concat = table.concat
local pairs = pairs
local type = type

local function tag(name, content, attr)
    local r, a = {}, {}
    content = content or attr
    r[#r + 1] = "<"
    r[#r + 1] = name
    if attr then
        for k, v in pairs(attr) do
            if type(k) == "number" then
                a[#a + 1] = escape(v)
            else
                a[#a + 1] = k .. '="' .. escape(v) .. '"'
            end
        end
        if #a > 0 then
            r[#r + 1] = " "
            r[#r + 1] = concat(a, " ")
        end
    end
    if type(content) == "string" then
        r[#r + 1] = ">"
        r[#r + 1] = escape(content)
        r[#r + 1] = "</"
        r[#r + 1] = name
        r[#r + 1] = ">"
    else
        r[#r + 1] = " />"
    end
    return concat(r)
end

local html = { __index = function(_, name)
    return function(attr)
        if type(attr) == "table" then
            return function(content)
                return tag(name, content, attr)
            end
        else
            return tag(name, attr)
        end
    end
end }

template.html = setmetatable(html, html)

return template.html
