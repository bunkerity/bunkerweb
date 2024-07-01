local log_file = require "logging.rolling_file"

local max_size       = 1024 * 10 --10kb
local max_index      = 5
local total_log_size = max_size * max_index --more than needed because of the log pattern
local log_filename   = "test.log"
local logger         = log_file(log_filename, max_size, max_index)


-- it will generate the log + max_index backup files
local size = 0
while size < total_log_size do
  local data = string.format("Test actual size[%d]", size)
  logger:debug(data)
  size = size + #data
end

-- lets test if all files where created
for i = 1, max_index do
  local file = assert(io.open(log_filename.."."..tostring(i), "r"))
  -- since there is an exact precision on the rolling
  -- (it can be a little less or a little more than the max_size)
  -- lets just test if the file is empty.

  assert(file:seek("end", 0) > 0)
  file:close()
end

print("RollingFile Logging OK")

