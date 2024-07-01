package = "LuaSocket"
version = "3.0rc1-2"
source = {
   url = "https://github.com/diegonehab/luasocket/archive/v3.0-rc1.zip",
   dir = "luasocket-3.0-rc1",
}
description = {
   summary = "Network support for the Lua language",
   detailed = [[
      LuaSocket is a Lua extension library that is composed by two parts: a C core
      that provides support for the TCP and UDP transport layers, and a set of Lua
      modules that add support for functionality commonly needed by applications
      that deal with the Internet.
   ]],
   homepage = "http://luaforge.net/projects/luasocket/",
   license = "MIT"
}
dependencies = {
   "lua >= 5.1"
}

local function make_plat(plat)
   local defines = {
      unix = {
         "LUA_COMPAT_APIINTCASTS",
         "LUASOCKET_DEBUG",
         "LUASOCKET_API=__attribute__((visibility(\"default\")))",
         "UNIX_API=__attribute__((visibility(\"default\")))",
         "MIME_API=__attribute__((visibility(\"default\")))"
      },
      macosx = {
         "LUA_COMPAT_APIINTCASTS",
         "LUASOCKET_DEBUG",
         "UNIX_HAS_SUN_LEN",
         "LUASOCKET_API=__attribute__((visibility(\"default\")))",
         "UNIX_API=__attribute__((visibility(\"default\")))",
         "MIME_API=__attribute__((visibility(\"default\")))"
      },
      win32 = {
         "LUA_COMPAT_APIINTCASTS",
         "LUASOCKET_DEBUG",
         "NDEBUG",
         "LUASOCKET_API=__declspec(dllexport)",
         "MIME_API=__declspec(dllexport)"
      },
      mingw32 = {
         "LUA_COMPAT_APIINTCASTS",
         "LUASOCKET_DEBUG",
         "LUASOCKET_INET_PTON",
         "WINVER=0x0501",
         "LUASOCKET_API=__declspec(dllexport)",
         "MIME_API=__declspec(dllexport)"
      }
   }
   local modules = {
      ["socket.core"] = {
         sources = { "src/luasocket.c", "src/timeout.c", "src/buffer.c", "src/io.c", "src/auxiliar.c",
                     "src/options.c", "src/inet.c", "src/except.c", "src/select.c", "src/tcp.c", "src/udp.c" },
         defines = defines[plat],
         incdir = "src"
      },
      ["mime.core"] = {
         sources = { "src/mime.c" },
         defines = defines[plat],
         incdir = "src"
      },
      ["socket.http"] = "src/http.lua",
      ["socket.url"] = "src/url.lua",
      ["socket.tp"] = "src/tp.lua",
      ["socket.ftp"] = "src/ftp.lua",
      ["socket.headers"] = "src/headers.lua",
      ["socket.smtp"] = "src/smtp.lua",
      ltn12 = "src/ltn12.lua",
      socket = "src/socket.lua",
      mime = "src/mime.lua"
   }
   if plat == "unix" or plat == "macosx" then
      modules["socket.core"].sources[#modules["socket.core"].sources+1] = "src/usocket.c"
      modules["socket.unix"] = {
         sources = { "src/buffer.c", "src/auxiliar.c", "src/options.c", "src/timeout.c", "src/io.c",
                     "src/usocket.c", "src/unix.c" },
         defines = defines[plat],
         incdir = "/src"
      }
      modules["socket.serial"] = {
         sources = { "src/buffer.c", "src/auxiliar.c", "src/options.c", "src/timeout.c",
                     "src/io.c", "src/usocket.c", "src/serial.c" },
         defines = defines[plat],
         incdir = "/src"
      }
   end
   if plat == "win32" or plat == "mingw32" then
      modules["socket.core"].sources[#modules["socket.core"].sources+1] = "src/wsocket.c"
      modules["socket.core"].libraries = { "ws2_32" }
   end
   return { modules = modules }
end

build = {
   type = "builtin",
   platforms = {
      unix = make_plat("unix"),
      macosx = make_plat("macosx"),
      win32 = make_plat("win32"),
      mingw32 = make_plat("mingw32")
   },
   copy_directories = { "doc", "samples", "etc", "test" }
}
