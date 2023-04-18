package="lua_pack"
version="2.0.0-0"
source = {
   url = "git://github.com/mashape/lua-pack",
   tag = "2.0.0"
}
description = {
   summary = "This is a simple Lua library for packing and unpacking binary data",
   detailed = [[
      This is a simple Lua library for packing and unpacking binary data.
   ]],
   homepage = "https://github.com/mashape/lua-pack",
   license = "MIT"
}
dependencies = {
   "lua >= 5.1, < 5.3"
}
build = {
   type = "builtin",
   modules = {
      ["lua_pack"] = {
      sources = { "lua_pack.c" },
    }
   }
}
