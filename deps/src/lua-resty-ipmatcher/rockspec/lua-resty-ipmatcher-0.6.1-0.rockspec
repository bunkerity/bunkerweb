package = "lua-resty-ipmatcher"
version = "0.6.1-0"
source = {
    url = "git://github.com/api7/lua-resty-ipmatcher",
    tag = "v0.6.1",
}

description = {
    summary = "High performance match IP address for Lua(OpenResty).",
    homepage = "https://github.com/api7/lua-resty-ipmatcher",
    license = "Apache License 2.0",
    maintainer = "Yuansheng Wang <membphis@gmail.com>"
}

build = {
    type = "builtin",
    modules = {
        ["resty.ipmatcher"] = "resty/ipmatcher.lua"
    }
}
