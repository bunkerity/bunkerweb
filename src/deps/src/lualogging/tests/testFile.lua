local GLOBAL_OS_DATE = os.date
local GLOBAL_IO_OPEN = io.open

local buffer_mode do
  local dir_separator = _G.package.config:sub(1,1)
  local is_windows = dir_separator == '\\'
  if is_windows then
    -- Windows does not support "line" buffered mode, see
    -- https://github.com/lunarmodules/lualogging/pull/9
    buffer_mode = "no"
  else
    buffer_mode = "line"
  end
end

local mock = {
  date = nil,
  handle = {}
}

io.open = function (file, mode)  --luacheck: ignore
  if (not string.find(file, "^__TEST*")) then
    return GLOBAL_IO_OPEN(file, mode)
  end

  mock.handle[file] = {}
  mock.handle[file].lines = {}
  mock.handle[file].mode = mode
  return {
    setvbuf = function (_, s)
      mock.handle[file].setvbuf = s
    end,
    write = function (_, s)
      table.insert(mock.handle[file].lines, s)
    end,
  }
end

os.date = function (...)  --luacheck: ignore
  return mock.date
end

local log_file = require "logging.file"

mock.date = "2008-01-01"
local logger = log_file("__TEST%s.log", "%Y-%m-%d")

assert(mock.handle["__TEST"..mock.date..".log"] == nil)

logger:info("logging.file test")

assert(mock.handle["__TEST"..mock.date..".log"].mode == "a")
assert(#mock.handle["__TEST"..mock.date..".log"].lines == 1)
assert(mock.handle["__TEST"..mock.date..".log"].setvbuf == buffer_mode)
assert(mock.handle["__TEST"..mock.date..".log"].lines[1] == "2008-01-01 INFO logging.file test\n")

mock.date = "2008-01-02"

logger:debug("debugging...")
logger:error("error!")

assert(mock.handle["__TEST"..mock.date..".log"].mode == "a")
assert(#mock.handle["__TEST"..mock.date..".log"].lines == 2)
assert(mock.handle["__TEST"..mock.date..".log"].setvbuf == buffer_mode)
assert(mock.handle["__TEST"..mock.date..".log"].lines[1] == "2008-01-02 DEBUG debugging...\n")
assert(mock.handle["__TEST"..mock.date..".log"].lines[2] == "2008-01-02 ERROR error!\n")

mock.date = "2008-01-03"

logger:info({id = "1"})

assert(mock.handle["__TEST"..mock.date..".log"].mode == "a")
assert(#mock.handle["__TEST"..mock.date..".log"].lines == 1)
assert(mock.handle["__TEST"..mock.date..".log"].setvbuf == buffer_mode)
assert(mock.handle["__TEST"..mock.date..".log"].lines[1] == '2008-01-03 INFO {id = "1"}\n')

os.date = GLOBAL_OS_DATE  --luacheck: ignore
io.open = GLOBAL_IO_OPEN  --luacheck: ignore

print("File Logging OK")

