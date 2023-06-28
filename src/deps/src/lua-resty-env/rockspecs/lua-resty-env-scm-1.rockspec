package = "lua-resty-env"
version = "scm-1"
source = {
   url = "git+https://github.com/3scale/lua-resty-env.git"
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
