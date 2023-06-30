-- https://github.com/GUI/lua-openssl-ffi/blob/master/lib/openssl-ffi/version.lua
local ffi = require "ffi"
local C = ffi.C
local ffi_str = ffi.string

ffi.cdef[[
  // 1.0
  unsigned long SSLeay(void);
  const char *SSLeay_version(int t);
  // >= 1.1
  unsigned long OpenSSL_version_num();
  const char *OpenSSL_version(int t);
  // >= 3.0
  const char *OPENSSL_info(int t);
  // BoringSSL
  int BORINGSSL_self_test(void);
]]

local version_func, info_func
local types_table

-- >= 1.1
local ok, version_num = pcall(function()
  local num = C.OpenSSL_version_num()
  version_func = C.OpenSSL_version
  types_table = {
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
  return num
end)


if not ok then
  -- 1.0.x
  ok, version_num = pcall(function()
    local num = C.SSLeay()
    version_func = C.SSLeay_version
    types_table = {
      VERSION = 0,
      CFLAGS = 2,
      BUILT_ON = 3,
      PLATFORM = 4,
      DIR = 5,
    }
    return num
  end)
end


if not ok then
  error(string.format("OpenSSL has encountered an error: %s; is OpenSSL library loaded?",
        tostring(version_num)))
elseif type(version_num) == 'number' and version_num < 0x10000000 then
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

local BORINGSSL = false
pcall(function()
  local _ = C.BORINGSSL_self_test
  BORINGSSL = true
end)

return setmetatable({
    version_num = tonumber(version_num),
    version_text = ffi_str(version_func(0)),
    version = function(t)
      return ffi_str(version_func(t))
    end,
    info = function(t)
      return ffi_str(info_func(t))
    end,
    OPENSSL_3X = version_num >= 0x30000000 and version_num < 0x30200000,
    OPENSSL_30 = version_num >= 0x30000000 and version_num < 0x30100000, -- for backward compat, deprecated
    OPENSSL_11 = version_num >= 0x10100000 and version_num < 0x10200000,
    OPENSSL_111 = version_num >= 0x10101000 and version_num < 0x10200000,
    OPENSSL_11_OR_LATER = version_num >= 0x10100000 and version_num < 0x30200000,
    OPENSSL_111_OR_LATER = version_num >= 0x10101000 and version_num < 0x30200000,
    OPENSSL_10 = version_num < 0x10100000 and version_num > 0x10000000,
    BORINGSSL = BORINGSSL,
    BORINGSSL_110 = BORINGSSL and version_num >= 0x10100000 and version_num < 0x10101000
  }, {
    __index = types_table,
})