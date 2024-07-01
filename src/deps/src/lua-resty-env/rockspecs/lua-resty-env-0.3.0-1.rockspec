package = "lua-resty-env"
version = "0.3.0-1"
source = {
   url = "https://github.com/3scale/lua-resty-env/archive/v0.3.0.tar.gz",
   md5 = "00c05a22173d0b06927118b85c98e029",
   dir = "lua-resty-env-0.3.0",
}
description = {
   summary = "lua-resty-env - Lua cache for calls to `os.getenv`.",
   detailed = "lua-resty-env - Lua cache for calls to `os.getenv`.",
   homepage = "https://github.com/3scale/lua-resty-env",
   license = "Apache License 2.0"
}
dependencies = {
}
build = {
   type = "builtin",
   modules = {
      ["resty.env"] = "src/resty/env.lua"
   }
}
