package = "lua-resty-mlcache"
version = "2.6.0-1"
source = {
  url = "git://github.com/thibaultcha/lua-resty-mlcache",
  tag = "2.6.0"
}
description = {
  summary  = "Layered caching library for OpenResty",
  detailed = [[
    This library can be manipulated as a key/value store caching scalar Lua
    types and tables, combining the power of the lua_shared_dict API and
    lua-resty-lrucache, which results in an extremely performant and flexible
    layered caching solution.

    Features:

    - Caching and negative caching with TTLs.
    - Built-in mutex via lua-resty-lock to prevent dog-pile effects to your
      database/backend on cache misses.
    - Built-in inter-worker communication to propagate cache invalidations and
      allow workers to update their L1 (lua-resty-lrucache) caches upon changes
      (`set()`, `delete()`).
    - Support for split hits and misses caching queues.
    - Multiple isolated instances can be created to hold various types of data
      while relying on the *same* `lua_shared_dict` L2 cache.
  ]],
  homepage = "https://github.com/thibaultcha/lua-resty-mlcache",
  license  = "MIT"
}
build = {
  type    = "builtin",
  modules = {
    ["resty.mlcache.ipc"] = "lib/resty/mlcache/ipc.lua",
    ["resty.mlcache"]     = "lib/resty/mlcache.lua"
  }
}
