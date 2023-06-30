package = "lua-resty-http"
version = "0.17.1-0"
source = {
    url = "git://github.com/ledgetech/lua-resty-http",
    tag = "v0.17.1"
}
description = {
    summary = "Lua HTTP client cosocket driver for OpenResty / ngx_lua.",
    homepage = "https://github.com/ledgetech/lua-resty-http",
    license = "2-clause BSD",
    maintainer = "James Hurst <james@pintsized.co.uk>"
}
dependencies = {
    "lua >= 5.1"
}
build = {
    type = "builtin",
    modules = {
        ["resty.http"] = "lib/resty/http.lua",
        ["resty.http_headers"] = "lib/resty/http_headers.lua",
        ["resty.http_connect"] = "lib/resty/http_connect.lua"
    }
}
