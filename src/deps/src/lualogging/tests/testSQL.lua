local log_sql = require "logging.sql"
local _, luasql = pcall(require, "luasql")
local has_module = pcall(require, "luasql.sqlite3")
if not has_module then
  print("SQLite 3 Logging SKIP (missing luasql.sqlite3)")
else
  if not luasql or not luasql.sqlite3 then
    print("Missing LuaSQL SQLite 3 driver!")
  else
    local env = luasql.sqlite3()

    local logger = log_sql{
      connectionfactory = function()
        return assert(env:connect("test.db"))
      end,
      keepalive = true,
    }

    logger:info("logging.sql test")
    logger:debug("debugging...")
    logger:error("error!")
    print("SQLite 3 Logging OK")
  end
end

