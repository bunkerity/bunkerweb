local ffi = require "ffi"
local C = ffi.C
local ffi_gc = ffi.gc
local ffi_new = ffi.new
local ffi_str = ffi.string

require "resty.openssl.include.bio"
local format_error = require("resty.openssl.err").format_error

local function read_wrap(f, ...)
  if type(f) ~= "cdata" then -- should be explictly a function
    return nil, "bio_util.read_wrap: expect a function at #1"
  end

  local bio_method = C.BIO_s_mem()
  if bio_method == nil then
      return nil, "bio_util.read_wrap: BIO_s_mem() failed"
  end
  local bio = C.BIO_new(bio_method)
  ffi_gc(bio, C.BIO_free)

  -- BIO_reset; #define BIO_CTRL_RESET 1
  local code = C.BIO_ctrl(bio, 1, 0, nil)
  if code ~= 1 then
      return nil, "bio_util.read_wrap: BIO_ctrl() failed: " .. code
  end

  local code = f(bio, ...)
  if code ~= 1 then
      return nil, format_error(f, code)
  end

  local buf = ffi_new("char *[1]")

  -- BIO_get_mem_data; #define BIO_CTRL_INFO 3
  local length = C.BIO_ctrl(bio, 3, 0, buf)

  return ffi_str(buf[0], length)
end

return {
  read_wrap = read_wrap,
}