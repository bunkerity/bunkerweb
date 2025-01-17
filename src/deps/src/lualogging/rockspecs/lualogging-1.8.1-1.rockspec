local package_name = "lualogging"
local package_version = "1.8.1"
local rockspec_revision = "1"
local github_account_name = "lunarmodules"
local github_repo_name = package_name


package = package_name
version = package_version.."-"..rockspec_revision
source = {
  url = "git://github.com/"..github_account_name.."/"..github_repo_name..".git",
  branch = (package_version == "dev") and "master" or nil,
  tag = (package_version ~= "dev") and ("v"..package_version) or nil,
}
description = {
  summary = "A simple API to use logging features",
  detailed = [[
    LuaLogging provides a simple API to use logging features in Lua. Its design was
    based on log4j. LuaLogging currently supports, through the use of appenders,
    console, file, rolling file, email, socket and SQL outputs.
  ]],
  homepage = "https://github.com/"..github_account_name.."/"..github_repo_name,
  license = "MIT/X11",
}
dependencies = {
  "luasocket"
}
build = {
  type = "none",
  install = {
    lua = {
      ['logging']              = "src/logging.lua",
      ['logging.console']      = "src/logging/console.lua",
      ['logging.file']         = "src/logging/file.lua",
      ['logging.rolling_file'] = "src/logging/rolling_file.lua",
      ['logging.email']        = "src/logging/email.lua",
      ['logging.sql']          = "src/logging/sql.lua",
      ['logging.socket']       = "src/logging/socket.lua",
      ['logging.nginx']        = "src/logging/nginx.lua",
      ['logging.rsyslog']      = "src/logging/rsyslog.lua",
      ['logging.envconfig']    = "src/logging/envconfig.lua",
    }
  },
  copy_directories = {
    "docs",
  },
}
