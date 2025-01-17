package = "lua-resty-template"
version = "dev-1"
source = {
    url = "git://github.com/bungle/lua-resty-template.git"
}
description = {
    summary = "Templating Engine (HTML) for Lua and OpenResty",
    detailed = "lua-resty-template is a compiling (HTML) templating engine for Lua and OpenResty.",
    homepage = "https://github.com/bungle/lua-resty-template",
    maintainer = "Aapo Talvensaari <aapo.talvensaari@gmail.com>",
    license = "BSD"
}
dependencies = {
    "lua >= 5.1"
}
build = {
    type = "builtin",
    modules = {
        ["resty.template"]                = "lib/resty/template.lua",
        ["resty.template.safe"]           = "lib/resty/template/safe.lua",
        ["resty.template.html"]           = "lib/resty/template/html.lua",
        ["resty.template.microbenchmark"] = "lib/resty/template/microbenchmark.lua"
    }
}
