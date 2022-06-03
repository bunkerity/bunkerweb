-- needs Alias from /home/c/diego/tec/luasocket/test to
-- "/luasocket-test" and "/luasocket-test/"
-- needs ScriptAlias from /home/c/diego/tec/luasocket/test/cgi
-- to "/luasocket-test-cgi" and "/luasocket-test-cgi/"
-- needs "AllowOverride AuthConfig" on /home/c/diego/tec/luasocket/test/auth
local socket = require("socket")
local http = require("socket.http")
local url = require("socket.url")

local mime = require("mime")
local ltn12 = require("ltn12")

-- override protection to make sure we see all errors
-- socket.protect = function(s) return s end

dofile("testsupport.lua")

local host, proxy, request, response, index_file
local ignore, expect, index, prefix, cgiprefix, index_crlf

http.TIMEOUT = 10

local t = socket.gettime()

--host = host or "diego.student.princeton.edu"
--host = host or "diego.student.princeton.edu"
host = host or "localhost"
proxy = proxy or "http://localhost:3128"
prefix = prefix or "/luasocket-test"
cgiprefix = cgiprefix or "/luasocket-test-cgi"
index_file = "index.html"

-- read index with CRLF convention
index = readfile(index_file)

local check_result = function(response, expect, ignore)
    for i,v in pairs(response) do
        if not ignore[i] then
            if v ~= expect[i] then
                local f = io.open("err", "w")
                f:write(tostring(v), "\n\n versus\n\n", tostring(expect[i]))
                f:close()
                fail(i .. " differs!")
            end
        end
    end
    for i,v in pairs(expect) do
        if not ignore[i] then
            if v ~= response[i] then
                local f = io.open("err", "w")
                f:write(tostring(response[i]), "\n\n versus\n\n", tostring(v))
                v = string.sub(type(v) == "string" and v or "", 1, 70)
                f:close()
                fail(i .. " differs!")
            end
        end
    end
    print("ok")
end

local check_request = function(request, expect, ignore)
    local t
    if not request.sink then request.sink, t = ltn12.sink.table() end
    request.source = request.source or
        (request.body and ltn12.source.string(request.body))
    local response = {}
    response.code, response.headers, response.status =
        socket.skip(1, http.request(request))
    if t and #t > 0 then response.body = table.concat(t) end
    check_result(response, expect, ignore)
end

------------------------------------------------------------------------
io.write("testing request uri correctness: ")
local forth = cgiprefix .. "/request-uri?" .. "this+is+the+query+string"
local back, c, h = http.request("http://" .. host .. forth)
if not back then fail(c) end
back = url.parse(back)
if similar(back.query, "this+is+the+query+string") then print("ok")
else fail(back.query) end

------------------------------------------------------------------------
io.write("testing query string correctness: ")
forth = "this+is+the+query+string"
back = http.request("http://" .. host .. cgiprefix ..
    "/query-string?" .. forth)
if similar(back, forth) then print("ok")
else fail("failed!") end

------------------------------------------------------------------------
io.write("testing document retrieval: ")
request = {
    url = "http://" .. host .. prefix .. "/index.html"
}
expect = {
    body = index,
    code = 200
}
ignore = {
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)

------------------------------------------------------------------------
io.write("testing redirect loop: ")
request = {
    url = "http://" .. host .. cgiprefix .. "/redirect-loop"
}
expect = {
    code = 302
}
ignore = {
    status = 1,
    headers = 1,
    body = 1
}
check_request(request, expect, ignore)

------------------------------------------------------------------------
io.write("testing invalid url: ")
local r, e = http.request{url = host .. prefix}
assert(r == nil and e == "invalid host ''")
r, re = http.request(host .. prefix)
assert(r == nil and e == re, tostring(r) ..", " .. tostring(re) ..
    " vs " .. tostring(e))
print("ok")

io.write("testing invalid empty port: ")
request = {
    url = "http://" .. host .. ":" .. prefix .. "/index.html"
}
expect = {
    body = index,
    code = 200
}
ignore = {
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)

------------------------------------------------------------------------
io.write("testing post method: ")
-- wanted to test chunked post, but apache doesn't support it...
request = {
    url = "http://" .. host .. cgiprefix .. "/cat",
    method = "POST",
    body = index,
    -- remove content-length header to send chunked body
    headers = { ["content-length"] = string.len(index) }
}
expect = {
    body = index,
    code = 200
}
ignore = {
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)

------------------------------------------------------------------------
--[[
io.write("testing proxy with post method: ")
request = {
    url = "http://" .. host .. cgiprefix .. "/cat",
    method = "POST",
    body = index,
    headers = { ["content-length"] = string.len(index) },
    proxy= proxy
}
expect = {
    body = index,
    code = 200
}
ignore = {
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)
]]

------------------------------------------------------------------------
io.write("testing simple post function: ")
back = http.request("http://" .. host .. cgiprefix .. "/cat", index)
assert(back == index)
print("ok")

------------------------------------------------------------------------
io.write("testing ltn12.(sink|source).file: ")
request = {
    url = "http://" .. host .. cgiprefix .. "/cat",
    method = "POST",
    source = ltn12.source.file(io.open(index_file, "rb")),
    sink = ltn12.sink.file(io.open(index_file .. "-back", "wb")),
    headers = { ["content-length"] = string.len(index) }
}
expect = {
    code = 200
}
ignore = {
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)
back = readfile(index_file .. "-back")
assert(back == index)
os.remove(index_file .. "-back")

------------------------------------------------------------------------
io.write("testing ltn12.(sink|source).chain and mime.(encode|decode): ")

local function b64length(len)
    local a = math.ceil(len/3)*4
    local l = math.ceil(a/76)
    return a + l*2
end

local source = ltn12.source.chain(
    ltn12.source.file(io.open(index_file, "rb")),
    ltn12.filter.chain(
        mime.encode("base64"),
        mime.wrap("base64")
    )
)

local sink = ltn12.sink.chain(
    mime.decode("base64"),
    ltn12.sink.file(io.open(index_file .. "-back", "wb"))
)

request = {
    url = "http://" .. host .. cgiprefix .. "/cat",
    method = "POST",
    source = source,
    sink = sink,
    headers = { ["content-length"] = b64length(string.len(index)) }
}
expect = {
    code = 200
}
ignore = {
    body_cb = 1,
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)
back = readfile(index_file .. "-back")
assert(back == index)
os.remove(index_file .. "-back")

------------------------------------------------------------------------
io.write("testing http redirection: ")
request = {
    url = "http://" .. host .. prefix
}
expect = {
    body = index,
    code = 200
}
ignore = {
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)

------------------------------------------------------------------------
--[[
io.write("testing proxy with redirection: ")
request = {
    url = "http://" .. host .. prefix,
    proxy = proxy
}
expect = {
    body = index,
    code = 200
}
ignore = {
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)
]]

------------------------------------------------------------------------
io.write("testing automatic auth failure: ")
request = {
    url = "http://really:wrong@" .. host .. prefix .. "/auth/index.html"
}
expect = {
    code = 401
}
ignore = {
    body = 1,
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)

------------------------------------------------------------------------
io.write("testing http redirection failure: ")
request = {
    url = "http://" .. host .. prefix,
    redirect = false
}
expect = {
    code = 301
}
ignore = {
    body = 1,
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)

------------------------------------------------------------------------
io.write("testing document not found: ")
request = {
    url = "http://" .. host .. "/wrongdocument.html"
}
expect = {
    code = 404
}
ignore = {
    body = 1,
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)

------------------------------------------------------------------------
io.write("testing auth failure: ")
request = {
    url = "http://" .. host .. prefix .. "/auth/index.html"
}
expect = {
    code = 401
}
ignore = {
    body = 1,
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)

------------------------------------------------------------------------
io.write("testing manual basic auth: ")
request = {
    url = "http://" .. host .. prefix .. "/auth/index.html",
    headers = {
        authorization = "Basic " .. (mime.b64("luasocket:password"))
    }
}
expect = {
    code = 200,
    body = index
}
ignore = {
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)

------------------------------------------------------------------------
io.write("testing automatic basic auth: ")
request = {
    url = "http://luasocket:password@" .. host .. prefix .. "/auth/index.html"
}
expect = {
    code = 200,
    body = index
}
ignore = {
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)

------------------------------------------------------------------------
io.write("testing auth info overriding: ")
request = {
    url = "http://really:wrong@" .. host .. prefix .. "/auth/index.html",
    user = "luasocket",
    password = "password"
}
expect = {
    code = 200,
    body = index
}
ignore = {
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)

------------------------------------------------------------------------
io.write("testing cgi output retrieval (probably chunked...): ")
request = {
    url = "http://" .. host .. cgiprefix .. "/cat-index-html"
}
expect = {
    body = index,
    code = 200
}
ignore = {
    status = 1,
    headers = 1
}
check_request(request, expect, ignore)

------------------------------------------------------------------------
local body
io.write("testing simple request function: ")
body = http.request("http://" .. host .. prefix .. "/index.html")
assert(body == index)
print("ok")

------------------------------------------------------------------------
io.write("testing HEAD method: ")
local r, c, h = http.request {
  method = "HEAD",
  url = "http://www.tecgraf.puc-rio.br/~diego/"
}
assert(r and h and (c == 200), c)
print("ok")

------------------------------------------------------------------------
io.write("testing host not found: ")
local c, e = socket.connect("example.invalid", 80)
local r, re = http.request{url = "http://example.invalid/does/not/exist"}
assert(r == nil and e == re, tostring(r) .. " " .. tostring(re))
r, re = http.request("http://example.invalid/does/not/exist")
assert(r == nil and e == re)
print("ok")

------------------------------------------------------------------------
print("passed all tests")
os.remove("err")

print(string.format("done in %.2fs", socket.gettime() - t))
