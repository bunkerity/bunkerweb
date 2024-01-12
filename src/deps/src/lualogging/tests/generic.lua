local logging = require "logging"
local call_count
local last_msg
local msgs

function logging.test(params)
  local logPatterns = logging.buildLogPatterns(params.logPatterns, params.logPattern)
  local timestampPattern = params.timestampPattern or logging.defaultTimestampPattern()
  return logging.new( function(self, level, message)
    last_msg = logging.prepareLogMsg(logPatterns[level], os.date(timestampPattern), level, message)
    msgs = msgs or {}
    table.insert(msgs, last_msg)
    --print("----->",last_msg)
    call_count = call_count + 1
    return true
  end)
end

local function reset()
  call_count = 0
  last_msg = nil
  msgs = nil
end

local tests = {}




tests.constants_for_lualogging = function()
  local DEFAULT_LEVELS = { "DEBUG", "INFO", "WARN", "ERROR", "FATAL", "OFF" }
  for _, level in ipairs(DEFAULT_LEVELS) do
    assert(logging[level], "constant logging."..level.." is not defined")
  end
end


tests.deprecated_parameter_handling = function()
  local list = { "param1", "next_one", "hello_world" }
  local params = logging.getDeprecatedParams(list, {
    param1 = 1,
    next_one = nil,
    hello_world = 3,
  })
  assert(params.param1 == 1)
  assert(params.next_one == nil)
  assert(params.hello_world == 3)

  params = logging.getDeprecatedParams(list, 1, nil, 3)
  assert(params.param1 == 1)
  assert(params.next_one == nil)
  assert(params.hello_world == 3)
end

tests.buildLogPatterns = function()
  local check_patterns = function(t)
    assert(type(t) == "table")
    assert(t.DEBUG and t.INFO and t.WARN and t.ERROR and t.FATAL)
    local i = 0
    for k,v in pairs(t) do i = i + 1 end
    assert(i == 5)
  end
  local t = logging.buildLogPatterns()
  check_patterns(t)
  local t = logging.buildLogPatterns(nil, "hello")
  check_patterns(t)
  assert(t.DEBUG == "hello")
  assert(t.FATAL == "hello")
  local t = logging.buildLogPatterns({}, "hello")
  check_patterns(t)
  assert(t.DEBUG == "hello")
  assert(t.FATAL == "hello")
  local t = logging.buildLogPatterns({
    DEBUG = "bye"
  }, "hello")
  check_patterns(t)
  assert(t.DEBUG == "bye")
  assert(t.INFO == "hello")
  assert(t.FATAL == "hello")
end

tests.log_levels = function()
  local logger = logging.test { logPattern = "%message", timestampPattern = nil }
  logger:setLevel(logger.DEBUG)
  -- debug gets logged
  logger:debug("message 1")
  assert(last_msg == "message 1", "got: " .. tostring(last_msg))
  assert(call_count == 1, "Got: " ..  tostring(call_count))
  -- fatal also gets logged at 'debug' setting
  logger:fatal("message 2")
  assert(last_msg == "message 2", "got: " .. tostring(last_msg))
  assert(call_count == 2, "Got: " ..  tostring(call_count))

  logger:setLevel(logger.FATAL)
  -- debug gets logged
  logger:debug("message 3")  -- should not change the last message
  assert(last_msg == "message 2", "got: " .. tostring(last_msg))
  assert(call_count == 2, "Got: " ..  tostring(call_count))
  -- fatal also gets logged at 'debug' setting
  logger:fatal("message 4") -- should be logged as 3rd message
  assert(last_msg == "message 4", "got: " .. tostring(last_msg))
  assert(call_count == 3, "Got: " ..  tostring(call_count))

  logger:setLevel(logger.OFF)
  -- debug gets logged
  logger:debug("message 5")  -- should not change the last message
  assert(last_msg == "message 4", "got: " .. tostring(last_msg))
  assert(call_count == 3, "Got: " ..  tostring(call_count))
  -- fatal also gets logged at 'debug' setting
  logger:fatal("message 6")  -- should not change the last message
  assert(last_msg == "message 4", "got: " .. tostring(last_msg))
  assert(call_count == 3, "Got: " ..  tostring(call_count))
  -- should never log "OFF", even if its set
  logger:fatal("message 7")  -- should not change the last message
  assert(last_msg == "message 4", "got: " .. tostring(last_msg))
  assert(call_count == 3, "Got: " ..  tostring(call_count))
end


tests.logPatterns = function()
  local logger = logging.test { logPattern = "%date", timestampPattern = nil }
  logger:debug("hello")
  assert(last_msg ~= "%date", "expected '%date' placeholder to be replaced, got: " .. tostring(last_msg))
  assert(last_msg ~= "", "expected '%date' placeholder to be replaced by a value, got an empty string")

  local logger = logging.test { logPattern = "%level", timestampPattern = nil }
  logger:fatal("hello")
  assert(last_msg ~= "%level", "expected '%level' placeholder to be replaced, got: " .. tostring(last_msg))
  assert(last_msg == "FATAL", "expected '%level' placeholder to be replaced by 'FATAL', got: " .. tostring(last_msg))

  local logger = logging.test { logPattern = "%message", timestampPattern = nil }
  logger:debug("hello")
  assert(last_msg ~= "%message", "expected '%message' placeholder to be replaced, got: " .. tostring(last_msg))
  assert(last_msg == "hello", "expected '%message' placeholder to be replaced by 'hello', got: " .. tostring(last_msg))

  local logger = logging.test { logPattern = "%source", timestampPattern = nil }
  local function test_func()
    logger:debug("hello")
  end
  test_func()
  assert(last_msg ~= "%source", "expected '%source' placeholder to be replaced, got: " .. tostring(last_msg))
  if debug then
    assert(last_msg:find("'test_func'", 1, true), "expected function name in output, got: " .. tostring(last_msg))
    assert(last_msg:find(":138 ", 1, true), "expected line number in output, got: " .. tostring(last_msg)) -- update hardcoded linenumber when this fails!
    assert(last_msg:find("generic.lua:", 1, true), "expected filename in output, got: " .. tostring(last_msg))
  else
    -- debug library disabled
    assert(last_msg:find("'unknown function'", 1, true), "expected 'unknwon function' in output, got: " .. tostring(last_msg))
    assert(last_msg:find(":-1 ", 1, true), "expected line number (-1) in output, got: " .. tostring(last_msg)) -- update hardcoded linenumber when this fails!
    assert(last_msg:find("?:", 1, true), "expected filename ('?') in output, got: " .. tostring(last_msg))
  end
  -- mutiple separate patterns
  local logger = logging.test {
    logPattern = "%message",
    logPatterns = {
      [logging.DEBUG] = "hello %message"
    },
    timestampPattern = nil,
  }
  logger:debug("world")
  assert(last_msg == "hello world", "expected 'hello world', got: " .. tostring(last_msg))
  logger:error("world")
  assert(last_msg == "world", "expected 'world', got: " .. tostring(last_msg))
end


tests.table_serialization = function()
  local logger = logging.test { logPattern = "%message", timestampPattern = nil }

  logger:debug({1,2,3,4,5,6,7,8,9,10})
  assert(last_msg == "{1, 10, 2, 3, 4, 5, 6, 7, 8, 9}", "got: " .. tostring(last_msg))

  logger:debug({abc = "cde", "hello", "world", xyz = true, 1, 2, 3})
  assert(last_msg == '{"hello", "world", 1, 2, 3, abc = "cde", xyz = true}', "got: " .. tostring(last_msg))
end


tests.print_function = function()
  local logger = logging.test { logPattern = "%level %message" }
  local print = logger:getPrint(logger.DEBUG)
  print("hey", "there", "dude")
  assert(msgs[1] == "DEBUG hey there dude")
  print()
  assert(msgs[2] == "DEBUG ")
  print("hello\nthere")
  assert(msgs[3] == "DEBUG hello")
  assert(msgs[4] == "DEBUG there")
  print({}, true, nil, 0)
  assert(msgs[5]:find("table"))
  assert(msgs[5]:find(" true nil 0$"))
end


tests.format_error_stacktrace = function()
  local count = 0
  local logger = logging.test { logPattern = "%level %message" }

  logger:debug("%s-%s", 'abc', '007')
  assert(last_msg == 'DEBUG abc-007')

  logger:debug("%s=%s", nil)
  assert(last_msg:find("bad argument #%d to '(.-)'"), "msg:'"..last_msg.."'")
  if debug then
    assert(last_msg:find("in main chunk"), "msg:'"..last_msg.."'")
    assert(last_msg:find("in %w+ 'func'"), "msg:'"..last_msg.."'")
    local _, levels = last_msg:gsub("(|)", function() count = count + 1 end)
    assert(levels == 3, "got : " .. tostring(levels))
  end
end


tests.defaultLogger = function()
  -- returns a logger
  assert(logging.defaultLogger(), "expected a logger object to be returned)")
  local logger = logging.test {}
  -- setting a default one
  assert(logging.defaultLogger(logger), "expected a logger object to be returned)")
  assert(logger == logging.defaultLogger(), "expected my previously set logger to be returned)")
end


tests.defaultLevel = function()
  -- default level is 'debug'
  local old_level = logging.defaultLevel()
  assert(old_level == logging.DEBUG, "expected default to be 'debug'")
  -- setting level
  assert(logging.defaultLevel(logging.FATAL) == logging.FATAL, "expected updated log-level")
  -- new logger uses new default level
  local logger = logging.test {}
  logger:error("less than 'fatal', should not be logged")
  assert(call_count == 0)
  logger:fatal("should be logged")
  assert(call_count == 1)

  -- errors on unknown level
  assert(not pcall(logging.defaultLevel, "unknown level"), "expected an error to be thrown")

  -- restore old default
  logging.defaultLevel(old_level)
end


for name, func in pairs(tests) do
  reset()
  print("generic test: " .. name)
  func()
end

print("[v] all generic tests succesful")
