package = "lua-resty-ipmatcher"
version = "0.3-0"
source = {
    url = "git://github.com/iresty/lua-resty-ipmatcher",
    tag = "v0.3",
}

description = {
    summary = "High performance match IP address for OpenResty Lua.",
    homepage = "https://github.com/iresty/lua-resty-ipmatcher",
    license = "Apache License 2.0",
    maintainer = "Yuansheng Wang <membphis@gmail.com>"
}

build = {
    type = "builtin",
    modules = {
        ["resty.ipmatcher"] = "resty/ipmatcher.lua"
    }
}
