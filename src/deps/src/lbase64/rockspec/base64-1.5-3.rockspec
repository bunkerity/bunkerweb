package = "base64"
version = "1.5-3"
source = {
   url = "git://github.com/iskolbin/lbase64",
	 tag = "v1.5.3",
}
description = {
   summary = "Pure Lua base64 encoder/decoder",
   detailed = [[
Pure Lua base64 encoder/decoder. Works with Lua 5.1+ and LuaJIT. Fallbacks to pure Lua bit operations if bit/bit32/native bit operators are not available.]],
   homepage = "https://github.com/iskolbin/lbase64",
   license = "MIT/Public Domain"
}
dependencies = {}
build = {
   type = "builtin",
   modules = {
      base64 = "base64.lua",
   }
}
