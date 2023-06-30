------------
-- Resty ENV
-- OpenResty module for working with ENV variables.
--
-- @module resty.env
-- @author mikz
-- @license Apache License Version 2.0

local _M = {
  _VERSION = '0.4.0'
}

local tostring = tostring
local sub = string.sub
local find = string.find
local pairs = pairs
local getenv = os.getenv

local ffi = require('ffi')
ffi.cdef([=[
int setenv(const char*, const char*, int);
int unsetenv(const char*);
extern char **environ;
]=])

local C = ffi.C

local function ffi_error()
  return C.strerror(ffi.errno())
end

local function unsetenv(name)
  if C.unsetenv(name) == -1 then
    return nil, ffi_error()
  else
    return true
  end
end

local function setenv(name, value, overwrite)
  local overwrite_flag = overwrite and 1 or 0

  if not value then
    return nil, 'missing value'
  end

  if C.setenv(name, value, overwrite_flag) == -1 then
    return nil, C.strerror(ffi.errno())
  else
    return value
  end
end

local function environ() -- return whole environment as table
  local env = C.environ
  if not env then return nil end
  local ret = {}
  local i = 0

  while env[i] ~= nil do
    local e = ffi.string(env[i])
    local eq = find(e, '=')
    if eq then
      ret[sub(e, 1, eq - 1)] = sub(e, eq + 1)
    end
    i = i + 1
  end

  for name, value in pairs(_M.env) do
    ret[name] = value
  end

  return ret
end

local cached = {}

local function fetch(name)
  local value

  if cached[name] then
    value = _M.env[name]
  else
    value = getenv(name)

    ngx.log(ngx.DEBUG, 'env: ', name, ' = ', value)
    _M.env[name] = value

    cached[name] = true
  end

  return value
end

--- Return a table with all environment variables.
function _M.list()
  return environ()
end

--- Return the raw value from ENV. Uses local cache.
-- @tparam string name name of the environment variable
function _M.get(name)
  return _M.env[name] or fetch(name)
end

local value_mapping = {
  [''] = false
}

--- Return value from ENV.
--- Returns false if it is empty. Uses @{get} internally.
-- @tparam string name name of the environment variable
function _M.value(name)
  local value = _M.get(name)
  local mapped = value_mapping[value]

  if mapped == nil then
    return value
  else
    return mapped
  end
end

local env_mapping = {
  ['true'] = true,
  ['false'] = false,
  ['1'] = true,
  ['0'] = false,
  [''] = false
}

--- Returns true/false from ENV variable.
--- Converts 0 to false and 1 to true.
-- @tparam string name name of the environment variable
function _M.enabled(name)
  return env_mapping[_M.get(name)]
end

--- Sets value to the local cache.
-- @tparam string name name of the environment variable
-- @tparam string value value to be cached
-- @see resty.env.get
function _M.set(name, value)
  local env = _M.env

  local val = value and tostring(value)
  local ok, err

  if val then
    ok, err = setenv(name, val, true)
  else
    ok, err = unsetenv(name)
  end

  local previous = env[name]

  if ok then
    env[name] = val
    cached[name] = nil
  end

  return previous, err
end

--- Reset local cache.
function _M.reset()
  _M.env = {}
  cached = {}
  return _M
end

return _M.reset()
