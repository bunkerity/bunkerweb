-----------------------------------------------------------------------------
-- Little program that checks links in HTML files, using coroutines and
-- non-blocking I/O via the dispatcher module.
-- LuaSocket sample files
-- Author: Diego Nehab
-----------------------------------------------------------------------------
local url = require("socket.url")
local dispatch = require("dispatch")
local http = require("socket.http")
dispatch.TIMEOUT = 10

-- make sure the user knows how to invoke us
arg = arg or {}
if #arg < 1 then
    print("Usage:\n  luasocket check-links.lua [-n] {<url>}")
    exit()
end

-- '-n' means we are running in non-blocking mode
if arg[1] == "-n" then
    -- if non-blocking I/O was requested, use real dispatcher interface
    table.remove(arg, 1)
    handler = dispatch.newhandler("coroutine")
else
    -- if using blocking I/O, use fake dispatcher interface
    handler = dispatch.newhandler("sequential")
end

local nthreads = 0

-- get the status of a URL using the dispatcher
function getstatus(link)
    local parsed = url.parse(link, {scheme = "file"})
    if parsed.scheme == "http" then
        nthreads = nthreads + 1
        handler:start(function()
            local r, c, h, s = http.request{
                method = "HEAD",
                url = link,
                create = handler.tcp
            }
            if r and c == 200 then io.write('\t', link, '\n')
            else io.write('\t', link, ': ', tostring(c), '\n') end
            nthreads = nthreads - 1
        end)
    end
end

function readfile(path)
    path = url.unescape(path)
    local file, error = io.open(path, "r")
    if file then
        local body = file:read("*a")
        file:close()
        return body
    else return nil, error end
end

function load(u)
    local parsed = url.parse(u, { scheme = "file" })
    local body, headers, code, error
    local base = u
    if parsed.scheme == "http" then
        body, code, headers = http.request(u)
        if code == 200 then
            -- if there was a redirect, update base to reflect it
            base = headers.location or base
        end
        if not body then
            error = code
        end
    elseif parsed.scheme == "file" then
        body, error = readfile(parsed.path)
    else error = string.format("unhandled scheme '%s'", parsed.scheme) end
    return base, body, error
end

function getlinks(body, base)
    -- get rid of comments
    body = string.gsub(body, "%<%!%-%-.-%-%-%>", "")
    local links = {}
    -- extract links
    body = string.gsub(body, '[Hh][Rr][Ee][Ff]%s*=%s*"([^"]*)"', function(href)
        table.insert(links, url.absolute(base, href))
    end)
    body = string.gsub(body, "[Hh][Rr][Ee][Ff]%s*=%s*'([^']*)'", function(href)
        table.insert(links, url.absolute(base, href))
    end)
    string.gsub(body, "[Hh][Rr][Ee][Ff]%s*=%s*(.-)>", function(href)
        table.insert(links, url.absolute(base, href))
    end)
    return links
end

function checklinks(address)
    local base, body, error = load(address)
    if not body then print(error) return end
    print("Checking ", base)
    local links = getlinks(body, base)
    for _, link in ipairs(links) do
        getstatus(link)
    end
end

for _, address in ipairs(arg) do
    checklinks(url.absolute("file:", address))
end

while nthreads > 0 do
    handler:step()
end
