package = "lua-resty-ipmatcher"
version = "master-0"
source = {
    url = "git://github.com/iresty/lua-resty-ipmatcher",
    branch = "master",
}

description = {
    summary = "High performance match IP address for Lua(OpenResty).",
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
