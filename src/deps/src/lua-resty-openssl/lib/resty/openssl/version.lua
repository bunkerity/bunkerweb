-- https://github.com/GUI/lua-openssl-ffi/blob/master/lib/openssl-ffi/version.lua
local ffi = require "ffi"
local C = ffi.C
local ffi_str = ffi.string
local log_debug = require "resty.openssl.auxiliary.compat".log_debug

local libcrypto_name
local lib_patterns = {
  "%s", "%s.so.3", "%s.so.1.1", "%s.so.1.0"
}

local function load_library()
  for _, pattern in ipairs(lib_patterns) do
    -- true: load to global namespae
    local pok, _ = pcall(ffi.load, string.format(pattern, "crypto"), true)
    if pok then
      libcrypto_name = string.format(pattern, "crypto")
      ffi.load(string.format(pattern, "ssl"), true)

      log_debug("loaded crypto library: ", libcrypto_name)
      return libcrypto_name
    end
  end

  return false, "unable to load crypto library"
end

ffi.cdef[[
  // >= 1.1
  unsigned long OpenSSL_version_num();
  const char *OpenSSL_version(int t);
  // >= 3.0
  const char *OPENSSL_info(int t);
]]

local version_func, info_func
local types_table = {
  VERSION = 0,
  CFLAGS = 1,
  BUILT_ON = 2,
  PLATFORM = 3,
  DIR = 4,
  ENGINES_DIR = 5,
  VERSION_STRING = 6,
  FULL_VERSION_STRING = 7,
  MODULES_DIR = 8,
  CPU_INFO = 9,
}

local get_version = function()
  local num = C.OpenSSL_version_num()
  version_func = C.OpenSSL_version
  return num
end

local ok, version_num = pcall(get_version)
if not ok then
  ok, version_num = pcall(load_library)
  if ok then
    -- try again
    ok, version_num = pcall(get_version)
  end
end

if not ok then
  error(string.format("OpenSSL has encountered an error: %s; is OpenSSL library loaded?",
        tostring(version_num)))
elseif type(version_num) == 'number' and version_num < 0x10101000 then
  error(string.format("OpenSSL version %s is not supported", tostring(version_num or 0)))
elseif not version_num then
  error("Can not get OpenSSL version")
end

if version_num >= 0x30000000 then
  local info_table = {
    INFO_CONFIG_DIR = 1001,
    INFO_ENGINES_DIR = 1002,
    INFO_MODULES_DIR = 1003,
    INFO_DSO_EXTENSION = 1004,
    INFO_DIR_FILENAME_SEPARATOR = 1005,
    INFO_LIST_SEPARATOR = 1006,
    INFO_SEED_SOURCE = 1007,
    INFO_CPU_SETTINGS = 1008,
  }

  for k, v in pairs(info_table) do
    types_table[k] = v
  end

  info_func = C.OPENSSL_info
else
  info_func = function(_)
    error(string.format("OPENSSL_info is not supported on %s", ffi_str(version_func(0))))
  end
end

return setmetatable({
    version_num = tonumber(version_num),
    version_text = ffi_str(version_func(0)),
    version = function(t)
      return ffi_str(version_func(t))
    end,
    info = function(t)
      return ffi_str(info_func(t))
    end,
    -- the following has implict upper bound of 4.x
    OPENSSL_3X = version_num >= 0x30000000 and version_num < 0x40000000,
    OPENSSL_111 = version_num >= 0x10101000 and version_num < 0x10200000,
  }, {
    __index = types_table,
})
