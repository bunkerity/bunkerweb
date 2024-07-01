local logging
local logenv
local env

local old_getenv = os.getenv
function os.getenv(key)  -- luacheck: ignore
  assert(type(key) == "string", "expected env variable name to be a string")
  return env[key]
end

local function reset()
  env = {}
  package.loaded["logging"] = nil
  package.loaded["logging.envconfig"] = nil
  logging = require "logging"
  logenv = require "logging.envconfig"
end


local tests = {}

tests.returns_defaults = function()
  local name, opts = logenv.get_default_settings()
  -- print("title: ", require("pl.pretty").write(opts))
  assert(name == "console", "expected 'console' to be the default logger")
  assert(type(opts) == "table", "expected 'opts' to be a table")
  assert(opts.destination == "stderr", "expected 'destination' to be 'stderr'")
  assert(opts.logLevel == "DEBUG", "expected 'logLevel' to be 'DEBUG'")
  assert(opts.logPatterns.DEBUG == "%date %level %message\n")
  assert(opts.logPatterns.INFO == "%date %level %message\n")
  assert(opts.logPatterns.WARN == "%date %level %message\n")
  assert(opts.logPatterns.ERROR == "%date %level %message\n")
  assert(opts.logPatterns.FATAL == "%date %level %message\n")
end

tests.returns_defaults_if_prefix_not_found = function()
  assert(logenv.set_default_settings("not_a_real_prefix"))
  local name, opts = logenv.get_default_settings()
  -- print("title: ", require("pl.pretty").write(opts))
  assert(name == "console", "expected 'console' to be the default logger")
  assert(type(opts) == "table", "expected 'opts' to be a table")
  assert(opts.destination == "stderr", "expected 'destination' to be 'stderr'")
  assert(opts.logLevel == "DEBUG", "expected 'logLevel' to be 'DEBUG'")
  assert(opts.logPatterns.DEBUG == "%date %level %message\n")
  assert(opts.logPatterns.INFO == "%date %level %message\n")
  assert(opts.logPatterns.WARN == "%date %level %message\n")
  assert(opts.logPatterns.ERROR == "%date %level %message\n")
  assert(opts.logPatterns.FATAL == "%date %level %message\n")
end

tests.fails_if_default_already_set = function()
  assert(logenv.set_default_settings("prefix"))
  local ok, err = logenv.set_default_settings("prefix")
  assert(err == "already set a default")
  assert(ok == nil)
end

tests.prefix_defaults_to_LL = function()
  env.LL_LOGLEVEL = assert(logging.ERROR)
  local _, opts = logenv.get_default_settings()
  -- print("title: ", require("pl.pretty").write(opts))
  assert(opts.logLevel == "ERROR", "expected 'logLevel' to be 'ERROR'")
end

tests.loads_patterns_object = function()
  env.LL_LOGPATTERN = "not used"
  env.LL_LOGPATTERNS_DEBUG = "debug"
  env.LL_LOGPATTERNS_INFO = "info"
  env.LL_LOGPATTERNS_WARN = "warn"
  env.LL_LOGPATTERNS_ERROR = "error"
  env.LL_LOGPATTERNS_FATAL = "fatal"
  local _, opts = logenv.get_default_settings()
  -- print("title: ", require("pl.pretty").write(opts))
  assert(opts.logPattern == "not used")
  assert(opts.logPatterns.DEBUG == "debug")
  assert(opts.logPatterns.INFO == "info")
  assert(opts.logPatterns.WARN == "warn")
  assert(opts.logPatterns.ERROR == "error")
  assert(opts.logPatterns.FATAL == "fatal")
end

tests.fills_patterns_object_from_logpattern = function()
  env.LL_LOGPATTERN = "this one"
  local _, opts = logenv.get_default_settings()
  -- print("title: ", require("pl.pretty").write(opts))
  assert(opts.logPattern == "this one")
  assert(opts.logPatterns.DEBUG == "this one")
  assert(opts.logPatterns.INFO == "this one")
  assert(opts.logPatterns.WARN == "this one")
  assert(opts.logPatterns.ERROR == "this one")
  assert(opts.logPatterns.FATAL == "this one")
end

tests.bad_loglevel_not_accepted = function()
  env.LL_LOGLEVEL = "something bad"
  local ok, loggername, opts = pcall(logenv.get_default_settings)
  -- print("title: ", require("pl.pretty").write(opts))
  assert(not ok)
  assert(opts == nil)
  assert(type(loggername) == "string")
end

tests.does_dynamic_lookups_of_vars = function()
  local _, opts = logenv.get_default_settings() -- "LL" is now prefix
  -- print("title: ", require("pl.pretty").write(opts))
  env.LL_SOME_VALUE = "hello"
  assert(opts.some_value == "hello")
end

tests.converts_booleans = function()
  local _, opts = logenv.get_default_settings() -- "LL" is now prefix
  -- print("title: ", require("pl.pretty").write(opts))
  env.LL_ONE = "TRUE"
  env.LL_TWO = "true"
  env.LL_THREE = "false"
  env.LL_FOUR = "FALSE"
  assert(opts.one == true)
  assert(opts.two == true)
  assert(opts.three == false)
  assert(opts.four == false)
end

tests.converts_numbers = function()
  local _, opts = logenv.get_default_settings() -- "LL" is now prefix
  env.LL_ONE = "1"
  env.LL_TWO = "-2"
  env.LL_THREE = ".2"
  env.LL_FOUR = "1.2"
  assert(opts.one == 1, "got: "..tostring(opts.one).." ("..type(opts.one)..")")
  assert(opts.two == -2, "got: "..tostring(opts.two).." ("..type(opts.two)..")")
  assert(opts.three == .2, "got: "..tostring(opts.three).." ("..type(opts.three)..")")
  assert(opts.four == 1.2, "got: "..tostring(opts.four).." ("..type(opts.four)..")")
end




for name, func in pairs(tests) do
  reset()
  print("env-config test: " .. name)
  func()
end

print("[v] all env-config tests succesful")
os.getenv = old_getenv  -- luacheck: ignore
