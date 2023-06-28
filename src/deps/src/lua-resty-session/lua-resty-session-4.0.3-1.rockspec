package = "lua-resty-session"
version = "4.0.3-1"
source = {
  url = "git+https://github.com/bungle/lua-resty-session.git",
  tag = "v4.0.3",
}
description = {
  summary = "Session Library for OpenResty - Flexible and Secure",
  detailed = "lua-resty-session is a secure, and flexible session library for OpenResty.",
  homepage = "https://github.com/bungle/lua-resty-session",
  maintainer = "Aapo Talvensaari <aapo.talvensaari@gmail.com>, Samuele Illuminati <samuele@konghq.com>",
  license = "BSD",
}
dependencies = {
  "lua >= 5.1",
  "lua_pack >= 2.0.0",
  "lua-ffi-zlib >= 0.5",
  "lua-resty-openssl >= 0.8.0",
}
build = {
  type = "builtin",
  modules = {
    ["resty.session"] = "lib/resty/session.lua",
    ["resty.session.dshm"] = "lib/resty/session/dshm.lua",
    ["resty.session.file"] = "lib/resty/session/file.lua",
    ["resty.session.file.thread"] = "lib/resty/session/file/thread.lua",
    ["resty.session.file.utils"] = "lib/resty/session/file/utils.lua",
    ["resty.session.memcached"] = "lib/resty/session/memcached.lua",
    ["resty.session.mysql"] = "lib/resty/session/mysql.lua",
    ["resty.session.postgres"] = "lib/resty/session/postgres.lua",
    ["resty.session.redis"] = "lib/resty/session/redis.lua",
    ["resty.session.redis.cluster"] = "lib/resty/session/redis/cluster.lua",
    ["resty.session.redis.sentinel"] = "lib/resty/session/redis/sentinel.lua",
    ["resty.session.redis.common"] = "lib/resty/session/redis/common.lua",
    ["resty.session.shm"] = "lib/resty/session/shm.lua",
    ["resty.session.utils"] = "lib/resty/session/utils.lua",
  },
}
