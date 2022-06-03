package = "luajit-geoip"
version = "dev-1"

source = {
  url = "git://github.com/leafo/luajit-geoip.git",
}

description = {
  summary = "LuaJIT bindings to MaxMind GeoIP library",
  license = "MIT",
  maintainer = "Leaf Corcoran <leafot@gmail.com>",
}

dependencies = {
  "lua ~> 5.1",
}

build = {
  type = "builtin",
  modules = {
		["geoip"] = "geoip/init.lua",
		["geoip.mmdb"] = "geoip/mmdb.lua",
		["geoip.version"] = "geoip/version.lua",
  }
}
