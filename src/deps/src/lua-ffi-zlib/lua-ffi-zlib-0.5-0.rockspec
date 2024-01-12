package = "lua-ffi-zlib"
version = "0.5-0"
source = {
  url = "git://github.com/hamishforbes/lua-ffi-zlib",
  tag = "v0.5"
}
description = {
  summary = "A Lua module using LuaJIT's FFI feature to access zlib.",
  homepage = "https://github.com/hamishforbes/lua-ffi-zlib",
  maintainer = "Hamish Forbes"
}
dependencies = {
    "lua >= 5.1",
}
build = {
  type = "builtin",
  modules = {
    ["ffi-zlib"] = "lib/ffi-zlib.lua",
  }
}
