local socket = require("socket")
local ftp = require("socket.ftp")
local url = require("socket.url")
local ltn12 = require("ltn12")

-- use dscl to create user "luasocket" with password "password"
-- with home in /Users/diego/luasocket/test/ftp
-- with group com.apple.access_ftp
-- with shell set to /sbin/nologin
-- set /etc/ftpchroot to chroot luasocket
-- must set group com.apple.access_ftp on user _ftp (for anonymous access)
-- copy index.html to /var/empty/pub (home of user ftp)
-- start ftp server with
-- sudo -s launchctl load -w /System/Library/LaunchDaemons/ftp.plist
-- copy index.html to /Users/diego/luasocket/test/ftp
-- stop with
-- sudo -s launchctl unload -w /System/Library/LaunchDaemons/ftp.plist

-- override protection to make sure we see all errors
--socket.protect = function(s) return s end

dofile("testsupport.lua")

local host = host or "localhost"
local port, index_file, index, back, err, ret

local t = socket.gettime()

index_file = "index.html"

-- a function that returns a directory listing
local function nlst(u)
    local t = {}
    local p = url.parse(u)
    p.command = "nlst"
    p.sink = ltn12.sink.table(t)
    local r, e = ftp.get(p)
    return r and table.concat(t), e
end

-- function that removes a remote file
local function dele(u)
    local p = url.parse(u)
    p.command = "dele"
    p.argument = string.gsub(p.path, "^/", "")
    if p.argumet == "" then p.argument = nil end
    p.check = 250
    return ftp.command(p)
end

-- read index with CRLF convention
index = readfile(index_file)

io.write("testing wrong scheme: ")
back, err = ftp.get("wrong://banana.com/lixo")
assert(not back and err == "wrong scheme 'wrong'", err)
print("ok")

io.write("testing invalid url: ")
back, err = ftp.get("localhost/dir1/index.html;type=i")
assert(not back and err)
print("ok")

io.write("testing anonymous file download: ")
back, err = socket.ftp.get("ftp://" .. host .. "/pub/index.html;type=i")
assert(not err and back == index, err)
print("ok")

io.write("erasing before upload: ")
ret, err = dele("ftp://luasocket:password@" .. host .. "/index.up.html")
if not ret then print(err)
else print("ok") end

io.write("testing upload: ")
ret, err = ftp.put("ftp://luasocket:password@" .. host .. "/index.up.html;type=i", index)
assert(ret and not err, err)
print("ok")

io.write("downloading uploaded file: ")
back, err = ftp.get("ftp://luasocket:password@" .. host .. "/index.up.html;type=i")
assert(ret and not err and index == back, err)
print("ok")

io.write("erasing after upload/download: ")
ret, err = dele("ftp://luasocket:password@" .. host .. "/index.up.html")
assert(ret and not err, err)
print("ok")

io.write("testing weird-character translation: ")
back, err = ftp.get("ftp://luasocket:password@" .. host .. "/%23%3f;type=i")
assert(not err and back == index, err)
print("ok")

io.write("testing parameter overriding: ")
local back = {}
ret, err = ftp.get{
    url = "//stupid:mistake@" .. host .. "/index.html",
    user = "luasocket",
    password = "password",
    type = "i",
    sink = ltn12.sink.table(back)
}
assert(ret and not err and table.concat(back) == index, err)
print("ok")

io.write("testing upload denial: ")
ret, err = ftp.put("ftp://" .. host .. "/index.up.html;type=a", index)
assert(not ret and err, "should have failed")
print(err)

io.write("testing authentication failure: ")
ret, err = ftp.get("ftp://luasocket:wrong@".. host .. "/index.html;type=a")
assert(not ret and err, "should have failed")
print(err)

io.write("testing wrong file: ")
back, err = ftp.get("ftp://".. host .. "/index.wrong.html;type=a")
assert(not back and err, "should have failed")
print(err)

print("passed all tests")
print(string.format("done in %.2fs", socket.gettime() - t))
