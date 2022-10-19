local socket = require("socket")
socket.url = require("socket.url")
dofile("testsupport.lua")

local check_build_url = function(parsed)
    local built = socket.url.build(parsed)
    if built ~= parsed.url then
        print("built is different from expected")
        print(built)
        print(expected)
        os.exit()
    end
end

local check_protect = function(parsed, path, unsafe)
    local built = socket.url.build_path(parsed, unsafe)
    if built ~= path then
        print(built, path)
        print("path composition failed.")
        os.exit()
    end
end

local check_invert = function(url)
    local parsed = socket.url.parse(url)
    parsed.path = socket.url.build_path(socket.url.parse_path(parsed.path))
    local rebuilt = socket.url.build(parsed)
    if rebuilt ~= url then
        print(url, rebuilt)
        print("original and rebuilt are different")
        os.exit()
    end
end

local check_parse_path = function(path, expect)
    local parsed = socket.url.parse_path(path)
    for i = 1, math.max(#parsed, #expect) do
        if parsed[i] ~= expect[i] then
            print(path)
            os.exit()
        end
    end
    if expect.is_directory ~= parsed.is_directory then
        print(path)
        print("is_directory mismatch")
        os.exit()
    end
    if expect.is_absolute ~= parsed.is_absolute then
        print(path)
        print("is_absolute mismatch")
        os.exit()
    end
    local built = socket.url.build_path(expect)
    if built ~= path then
        print(built, path)
        print("path composition failed.")
        os.exit()
    end
end

local check_absolute_url = function(base, relative, absolute)
    local res = socket.url.absolute(base, relative)
    if res ~= absolute then 
        io.write("absolute: In test for base='", base, "', rel='", relative, "' expected '", 
            absolute, "' but got '", res, "'\n")
        os.exit()
    end
end

local check_parse_url = function(gaba)
    local url = gaba.url
    gaba.url = nil
    local parsed = socket.url.parse(url)
    for i, v in pairs(gaba) do
        if v ~= parsed[i] then
            io.write("parse: In test for '", url, "' expected ", i, " = '", 
                   v, "' but got '", tostring(parsed[i]), "'\n")
            for i,v in pairs(parsed) do print(i,v) end
            os.exit()
        end
    end
    for i, v in pairs(parsed) do
        if v ~= gaba[i] then
            io.write("parse: In test for '", url, "' expected ", i, " = '", 
                   tostring(gaba[i]), "' but got '", v, "'\n")
            for i,v in pairs(parsed) do print(i,v) end
            os.exit()
        end
    end
end

print("testing URL parsing")
check_parse_url{
    url = "scheme://user:pass$%?#wd@host:port/path;params?query#fragment",
    scheme = "scheme", 
    authority = "user:pass$%?#wd@host:port", 
    host = "host",
    port = "port",
    userinfo = "user:pass$%?#wd",
    password = "pass$%?#wd",
    user = "user",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}
check_parse_url{
    url = "scheme://user:pass?#wd@host:port/path;params?query#fragment",
    scheme = "scheme", 
    authority = "user:pass?#wd@host:port", 
    host = "host",
    port = "port",
    userinfo = "user:pass?#wd",
    password = "pass?#wd",
    user = "user",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}
check_parse_url{
    url = "scheme://user:pass-wd@host:port/path;params?query#fragment",
    scheme = "scheme", 
    authority = "user:pass-wd@host:port", 
    host = "host",
    port = "port",
    userinfo = "user:pass-wd",
    password = "pass-wd",
    user = "user",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}
check_parse_url{
    url = "scheme://user:pass#wd@host:port/path;params?query#fragment",
    scheme = "scheme", 
    authority = "user:pass#wd@host:port", 
    host = "host",
    port = "port",
    userinfo = "user:pass#wd",
    password = "pass#wd",
    user = "user",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}
check_parse_url{
    url = "scheme://user:pass#wd@host:port/path;params?query",
    scheme = "scheme", 
    authority = "user:pass#wd@host:port", 
    host = "host",
    port = "port",
    userinfo = "user:pass#wd",
    password = "pass#wd",
    user = "user",
    path = "/path",
    params = "params",
    query = "query",
}
check_parse_url{
    url = "scheme://userinfo@host:port/path;params?query#fragment",
    scheme = "scheme", 
    authority = "userinfo@host:port", 
    host = "host",
    port = "port",
    userinfo = "userinfo",
    user = "userinfo",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

check_parse_url{
    url = "scheme://user:password@host:port/path;params?query#fragment",
    scheme = "scheme", 
    authority = "user:password@host:port", 
    host = "host",
    port = "port",
    userinfo = "user:password",
    user = "user",
    password = "password",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment",
}

check_parse_url{
    url = "scheme://userinfo@host:port/path;params?query#",
    scheme = "scheme", 
    authority = "userinfo@host:port", 
    host = "host",
    port = "port",
    userinfo = "userinfo",
    user = "userinfo",
    path = "/path",
    params = "params",
    query = "query",
    fragment = ""
}

check_parse_url{
    url = "scheme://userinfo@host:port/path;params?#fragment",
    scheme = "scheme", 
    authority = "userinfo@host:port", 
    host = "host",
    port = "port",
    userinfo = "userinfo",
    user = "userinfo",
    path = "/path",
    params = "params",
    query = "",
    fragment = "fragment"
}

check_parse_url{
    url = "scheme://userinfo@host:port/path;params#fragment",
    scheme = "scheme", 
    authority = "userinfo@host:port", 
    host = "host",
    port = "port",
    userinfo = "userinfo",
    user = "userinfo",
    path = "/path",
    params = "params",
    fragment = "fragment"
}

check_parse_url{
    url = "scheme://userinfo@host:port/path;?query#fragment",
    scheme = "scheme", 
    authority = "userinfo@host:port", 
    host = "host",
    port = "port",
    userinfo = "userinfo",
    user = "userinfo",
    path = "/path",
    params = "",
    query = "query",
    fragment = "fragment"
}

check_parse_url{
    url = "scheme://userinfo@host:port/path?query#fragment",
    scheme = "scheme", 
    authority = "userinfo@host:port", 
    host = "host",
    port = "port",
    userinfo = "userinfo",
    user = "userinfo",
    path = "/path",
    query = "query",
    fragment = "fragment"
}

check_parse_url{
    url = "scheme://userinfo@host:port/;params?query#fragment",
    scheme = "scheme", 
    authority = "userinfo@host:port", 
    host = "host",
    port = "port",
    userinfo = "userinfo",
    user = "userinfo",
    path = "/",
    params = "params",
    query = "query",
    fragment = "fragment"
}

check_parse_url{
    url = "scheme://userinfo@host:port",
    scheme = "scheme", 
    authority = "userinfo@host:port", 
    host = "host",
    port = "port",
    userinfo = "userinfo",
    user = "userinfo",
}

check_parse_url{
    url = "//userinfo@host:port/path;params?query#fragment",
    authority = "userinfo@host:port", 
    host = "host",
    port = "port",
    userinfo = "userinfo",
    user = "userinfo",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

check_parse_url{
    url = "//userinfo@host:port/path",
    authority = "userinfo@host:port", 
    host = "host",
    port = "port",
    userinfo = "userinfo",
    user = "userinfo",
    path = "/path",
}

check_parse_url{
    url = "//userinfo@host/path",
    authority = "userinfo@host", 
    host = "host",
    userinfo = "userinfo",
    user = "userinfo",
    path = "/path",
}

check_parse_url{
    url = "//user:password@host/path",
    authority = "user:password@host", 
    host = "host",
    userinfo = "user:password",
    password = "password",
    user = "user",
    path = "/path",
}

check_parse_url{
    url = "//user:@host/path",
    authority = "user:@host", 
    host = "host",
    userinfo = "user:",
    password = "",
    user = "user",
    path = "/path",
}

check_parse_url{
    url = "//user@host:port/path",
    authority = "user@host:port", 
    host = "host",
    userinfo = "user",
    user = "user",
    port = "port",
    path = "/path",
}

check_parse_url{
    url = "//host:port/path",
    authority = "host:port", 
    port = "port",
    host = "host",
    path = "/path",
}

check_parse_url{
    url = "//host/path",
    authority = "host", 
    host = "host",
    path = "/path",
}

check_parse_url{
    url = "//host",
    authority = "host", 
    host = "host",
}

check_parse_url{
    url = "/path",
    path = "/path",
}

check_parse_url{
    url = "path",
    path = "path",
}

-- IPv6 tests

check_parse_url{
    url = "http://[FEDC:BA98:7654:3210:FEDC:BA98:7654:3210]:80/index.html",
    scheme = "http",
    host = "FEDC:BA98:7654:3210:FEDC:BA98:7654:3210",
    authority = "[FEDC:BA98:7654:3210:FEDC:BA98:7654:3210]:80",
    port = "80",
    path = "/index.html"
}

check_parse_url{
    url = "http://[1080:0:0:0:8:800:200C:417A]/index.html",
    scheme = "http",
    host = "1080:0:0:0:8:800:200C:417A",
    authority = "[1080:0:0:0:8:800:200C:417A]",
    path = "/index.html"
}

check_parse_url{
    url = "http://[3ffe:2a00:100:7031::1]",
    scheme = "http",
    host = "3ffe:2a00:100:7031::1",
    authority = "[3ffe:2a00:100:7031::1]",
}

check_parse_url{
    url = "http://[1080::8:800:200C:417A]/foo",
    scheme = "http",
    host = "1080::8:800:200C:417A",
    authority = "[1080::8:800:200C:417A]",
    path = "/foo"
}

check_parse_url{
    url = "http://[::192.9.5.5]/ipng",
    scheme = "http",
    host = "::192.9.5.5",
    authority = "[::192.9.5.5]",
    path = "/ipng"
}

check_parse_url{
    url = "http://[::FFFF:129.144.52.38]:80/index.html",
    scheme = "http",
    host = "::FFFF:129.144.52.38",
    port = "80",
    authority = "[::FFFF:129.144.52.38]:80",
    path = "/index.html"
}

check_parse_url{
    url = "http://[2010:836B:4179::836B:4179]",
    scheme = "http",
    host = "2010:836B:4179::836B:4179",
    authority = "[2010:836B:4179::836B:4179]",
}

check_parse_url{
    url = "//userinfo@[::FFFF:129.144.52.38]:port/path;params?query#fragment",
    authority = "userinfo@[::FFFF:129.144.52.38]:port", 
    host = "::FFFF:129.144.52.38",
    port = "port",
    userinfo = "userinfo",
    user = "userinfo",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

check_parse_url{
    url = "scheme://user:password@[::192.9.5.5]:port/path;params?query#fragment",
    scheme = "scheme",
    authority = "user:password@[::192.9.5.5]:port", 
    host = "::192.9.5.5",
    port = "port",
    userinfo = "user:password",
    user = "user",
    password = "password",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

print("testing URL building")
check_build_url {
    url = "scheme://user:password@host:port/path;params?query#fragment",
    scheme = "scheme", 
    host = "host",
    port = "port",
    user = "user",
    password = "password",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

check_build_url{
    url = "//userinfo@[::FFFF:129.144.52.38]:port/path;params?query#fragment",
    host = "::FFFF:129.144.52.38",
    port = "port",
    user = "userinfo",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

check_build_url{
    url = "scheme://user:password@[::192.9.5.5]:port/path;params?query#fragment",
    scheme = "scheme",
    host = "::192.9.5.5",
    port = "port",
    user = "user",
    password = "password",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

check_build_url {
    url = "scheme://user:password@host/path;params?query#fragment",
    scheme = "scheme", 
    host = "host",
    user = "user",
    password = "password",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

check_build_url {
    url = "scheme://user@host/path;params?query#fragment",
    scheme = "scheme", 
    host = "host",
    user = "user",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

check_build_url {
    url = "scheme://host/path;params?query#fragment",
    scheme = "scheme", 
    host = "host",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

check_build_url {
    url = "scheme://host/path;params#fragment",
    scheme = "scheme", 
    host = "host",
    path = "/path",
    params = "params",
    fragment = "fragment"
}

check_build_url {
    url = "scheme://host/path#fragment",
    scheme = "scheme", 
    host = "host",
    path = "/path",
    fragment = "fragment"
}

check_build_url {
    url = "scheme://host/path",
    scheme = "scheme", 
    host = "host",
    path = "/path",
}

check_build_url {
    url = "//host/path",
    host = "host",
    path = "/path",
}

check_build_url {
    url = "/path",
    path = "/path",
}

check_build_url {
    url = "scheme://user:password@host:port/path;params?query#fragment",
    scheme = "scheme", 
    host = "host",
    port = "port",
    user = "user",
    userinfo = "not used",
    password = "password",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

check_build_url {
    url = "scheme://user:password@host:port/path;params?query#fragment",
    scheme = "scheme", 
    host = "host",
    port = "port",
    user = "user",
    userinfo = "not used",
    authority = "not used",
    password = "password",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

check_build_url {
    url = "scheme://user:password@host:port/path;params?query#fragment",
    scheme = "scheme", 
    host = "host",
    port = "port",
    userinfo = "user:password",
    authority = "not used",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

check_build_url {
    url = "scheme://user:password@host:port/path;params?query#fragment",
    scheme = "scheme", 
    authority = "user:password@host:port",
    path = "/path",
    params = "params",
    query = "query",
    fragment = "fragment"
}

-- standard RFC tests
print("testing absolute resolution")
check_absolute_url("http://a/b/c/d;p?q#f", "g:h", "g:h")
check_absolute_url("http://a/b/c/d;p?q#f", "g", "http://a/b/c/g")
check_absolute_url("http://a/b/c/d;p?q#f", "./g", "http://a/b/c/g")
check_absolute_url("http://a/b/c/d;p?q#f", "g/", "http://a/b/c/g/")
check_absolute_url("http://a/b/c/d;p?q#f", "/g", "http://a/g")
check_absolute_url("http://a/b/c/d;p?q#f", "//g", "http://g")
check_absolute_url("http://a/b/c/d;p?q#f", "?y", "http://a/b/c/d;p?y")
check_absolute_url("http://a/b/c/d;p?q#f", "g?y", "http://a/b/c/g?y")
check_absolute_url("http://a/b/c/d;p?q#f", "g?y/./x", "http://a/b/c/g?y/x")
check_absolute_url("http://a/b/c/d;p?q#f", "#s", "http://a/b/c/d;p?q#s")
check_absolute_url("http://a/b/c/d;p?q#f", "g#s", "http://a/b/c/g#s")
check_absolute_url("http://a/b/c/d;p?q#f", "g#s/./x", "http://a/b/c/g#s/x")
check_absolute_url("http://a/b/c/d;p?q#f", "g?y#s", "http://a/b/c/g?y#s")
check_absolute_url("http://a/b/c/d;p?q#f", ";x", "http://a/b/c/d;x")
check_absolute_url("http://a/b/c/d;p?q#f", "g;x", "http://a/b/c/g;x")
check_absolute_url("http://a/b/c/d;p?q#f", "g;x?y#s", "http://a/b/c/g;x?y#s")
check_absolute_url("http://a/b/c/d;p?q#f", ".", "http://a/b/c/")
check_absolute_url("http://a/b/c/d;p?q#f", "./", "http://a/b/c/")
check_absolute_url("http://a/b/c/d;p?q#f", "./g", "http://a/b/c/g")
check_absolute_url("http://a/b/c/d;p?q#f", "./g/", "http://a/b/c/g/")
check_absolute_url("http://a/b/c/d;p?q#f", "././g", "http://a/b/c/g")
check_absolute_url("http://a/b/c/d;p?q#f", "././g/", "http://a/b/c/g/")
check_absolute_url("http://a/b/c/d;p?q#f", "g/.", "http://a/b/c/g/")
check_absolute_url("http://a/b/c/d;p?q#f", "g/./", "http://a/b/c/g/")
check_absolute_url("http://a/b/c/d;p?q#f", "g/./.", "http://a/b/c/g/")
check_absolute_url("http://a/b/c/d;p?q#f", "g/././", "http://a/b/c/g/")
check_absolute_url("http://a/b/c/d;p?q#f", "./.", "http://a/b/c/")
check_absolute_url("http://a/b/c/d;p?q#f", "././.", "http://a/b/c/")
check_absolute_url("http://a/b/c/d;p?q#f", "././g/./.", "http://a/b/c/g/")
check_absolute_url("http://a/b/c/d;p?q#f", "..", "http://a/b/")
check_absolute_url("http://a/b/c/d;p?q#f", "../", "http://a/b/")
check_absolute_url("http://a/b/c/d;p?q#f", "../g", "http://a/b/g")
check_absolute_url("http://a/b/c/d;p?q#f", "../..", "http://a/")
check_absolute_url("http://a/b/c/d;p?q#f", "../../", "http://a/")
check_absolute_url("http://a/b/c/d;p?q#f", "../../g", "http://a/g")
check_absolute_url("http://a/b/c/d;p?q#f", "../../../g", "http://a/g")
check_absolute_url("http://a/b/c/d;p?q#f", "", "http://a/b/c/d;p?q#f")
check_absolute_url("http://a/b/c/d;p?q#f", "/./g", "http://a/g")
check_absolute_url("http://a/b/c/d;p?q#f", "/../g", "http://a/g")
check_absolute_url("http://a/b/c/d;p?q#f", "g.", "http://a/b/c/g.")
check_absolute_url("http://a/b/c/d;p?q#f", ".g", "http://a/b/c/.g")
check_absolute_url("http://a/b/c/d;p?q#f", "g..", "http://a/b/c/g..")
check_absolute_url("http://a/b/c/d;p?q#f", "..g", "http://a/b/c/..g")
check_absolute_url("http://a/b/c/d;p?q#f", "./../g", "http://a/b/g")
check_absolute_url("http://a/b/c/d;p?q#f", "./g/.", "http://a/b/c/g/")
check_absolute_url("http://a/b/c/d;p?q#f", "g/./h", "http://a/b/c/g/h")
check_absolute_url("http://a/b/c/d;p?q#f", "g/../h", "http://a/b/c/h")

check_absolute_url("http://a/b/c/d:p?q#f/", "../g/", "http://a/b/g/")
check_absolute_url("http://a/b/c/d:p?q#f/", "../g", "http://a/b/g")
check_absolute_url("http://a/b/c/d:p?q#f/", "../.g/", "http://a/b/.g/")
check_absolute_url("http://a/b/c/d:p?q#f/", "../.g", "http://a/b/.g")
check_absolute_url("http://a/b/c/d:p?q#f/", "../.g.h/", "http://a/b/.g.h/")
check_absolute_url("http://a/b/c/d:p?q#f/", "../.g.h", "http://a/b/.g.h")

check_absolute_url("http://a/b/c/d:p?q#f/", "g.h/", "http://a/b/c/g.h/")
check_absolute_url("http://a/b/c/d:p?q#f/", "../g.h/", "http://a/b/g.h/")
check_absolute_url("http://a/", "../g.h/", "http://a/g.h/")

-- extra tests
check_absolute_url("//a/b/c/d;p?q#f", "d/e/f", "//a/b/c/d/e/f")
check_absolute_url("/a/b/c/d;p?q#f", "d/e/f", "/a/b/c/d/e/f")
check_absolute_url("a/b/c/d", "d/e/f", "a/b/c/d/e/f")
check_absolute_url("a/b/c/d/../", "d/e/f", "a/b/c/d/e/f")
check_absolute_url("http://velox.telemar.com.br", "/dashboard/index.html", 
   "http://velox.telemar.com.br/dashboard/index.html")
check_absolute_url("http://example.com/", "../.badhost.com/", "http://example.com/.badhost.com/")
check_absolute_url("http://example.com/", "...badhost.com/", "http://example.com/...badhost.com/")
check_absolute_url("http://example.com/a/b/c/d/", "../q", "http://example.com/a/b/c/q")
check_absolute_url("http://example.com/a/b/c/d/", "../../q", "http://example.com/a/b/q")
check_absolute_url("http://example.com/a/b/c/d/", "../../../q", "http://example.com/a/q")
check_absolute_url("http://example.com", ".badhost.com", "http://example.com/.badhost.com")
check_absolute_url("http://example.com/a/b/c/d/", "..//../../../q", "http://example.com/a/q")
check_absolute_url("http://example.com/a/b/c/d/", "..//a/../../../../q", "http://example.com/a/q")
check_absolute_url("http://example.com/a/b/c/d/", "..//a/..//../../../q", "http://example.com/a/b/q")
check_absolute_url("http://example.com/a/b/c/d/", "..//a/..///../../../../q", "http://example.com/a/b/q")
check_absolute_url("http://example.com/a/b/c/d/", "../x/a/../y/z/../../../../q", "http://example.com/a/b/q")

print("testing path parsing and composition")
check_parse_path("/eu/tu/ele", { "eu", "tu", "ele"; is_absolute = 1 })
check_parse_path("/eu/", { "eu"; is_absolute = 1, is_directory = 1 })
check_parse_path("eu/tu/ele/nos/vos/eles/", 
    { "eu", "tu", "ele", "nos", "vos", "eles"; is_directory = 1})
check_parse_path("/", { is_absolute = 1, is_directory = 1})
check_parse_path("", { })
check_parse_path("eu%01/%02tu/e%03l%04e/nos/vos%05/e%12les/", 
    { "eu\1", "\2tu", "e\3l\4e", "nos", "vos\5", "e\18les"; is_directory = 1})
check_parse_path("eu/tu", { "eu", "tu" })

print("testing path protection")
check_protect({ "eu", "-_.!~*'():@&=+$,", "tu" }, "eu/-_.!~*'():@&=+$,/tu")
check_protect({ "eu ", "~diego" }, "eu%20/~diego")
check_protect({ "/eu>", "<diego?" }, "%2Feu%3E/%3Cdiego%3F")
check_protect({ "\\eu]", "[diego`" }, "%5Ceu%5D/%5Bdiego%60")
check_protect({ "{eu}", "|diego\127" }, "%7Beu%7D/%7Cdiego%7F")
check_protect({ "eu ", "~diego" }, "eu /~diego", 1)
check_protect({ "/eu>", "<diego?" }, "/eu>/<diego?", 1)
check_protect({ "\\eu]", "[diego`" }, "\\eu]/[diego`", 1)
check_protect({ "{eu}", "|diego\127" }, "{eu}/|diego\127", 1)

print("testing inversion")
check_invert("http:")
check_invert("a/b/c/d.html")
check_invert("//net_loc")
check_invert("http:a/b/d/c.html")
check_invert("//net_loc/a/b/d/c.html")
check_invert("http://net_loc/a/b/d/c.html")
check_invert("//who:isit@net_loc")
check_invert("http://he:man@boo.bar/a/b/c/i.html;type=moo?this=that#mark")
check_invert("/b/c/d#fragment")
check_invert("/b/c/d;param#fragment")
check_invert("/b/c/d;param?query#fragment")
check_invert("/b/c/d?query")
check_invert("/b/c/d;param?query")
check_invert("http://he:man@[::192.168.1.1]/a/b/c/i.html;type=moo?this=that#mark")

print("the library passed all tests")
