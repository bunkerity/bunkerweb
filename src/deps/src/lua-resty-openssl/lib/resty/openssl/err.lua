local ffi = require "ffi"
local C = ffi.C
local ffi_str = ffi.string
local ffi_sizeof = ffi.sizeof

local ctypes = require "resty.openssl.auxiliary.ctypes"
require "resty.openssl.include.err"

local constchar_ptrptr = ffi.typeof("const char*[1]")

local buf = ffi.new('char[256]')

local function format_error(ctx, code, all_errors)
  local errors = {}
  if code then
    table.insert(errors, string.format("code: %d", code or 0))
  end
  -- get the OpenSSL errors
  while C.ERR_peek_error() ~= 0 do
    local line = ctypes.ptr_of_int()
    local path = constchar_ptrptr()
    local code
    if all_errors then
      code = C.ERR_get_error_line(path, line)
    else
      code = C.ERR_peek_last_error_line(path, line)
    end

    local abs_path = ffi_str(path[0])
    -- ../crypto/asn1/a_d2i_fp.c => crypto/asn1/a_d2i_fp.c
    local start = abs_path:find("/")
    if start then
      abs_path = abs_path:sub(start+1)
    end

    C.ERR_error_string_n(code, buf, ffi_sizeof(buf))
    table.insert(errors, string.format("%s:%d:%s",
      abs_path, line[0], ffi_str(buf))
    )

    if not all_errors then
      break
    end
  end

  C.ERR_clear_error()

  if #errors > 0 then
    return string.format("%s%s%s", (ctx or ""), (ctx and ": " or ""), table.concat(errors, " "))
  else
    return string.format("%s failed", ctx)
  end
end

local function format_all_error(ctx, code)
  return format_error(ctx, code, true)
end

return {
  format_error = format_error,
  format_all_error = format_all_error,
}