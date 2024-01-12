local ffi = require "ffi"
local C = ffi.C
local ffi_str = ffi.string
local ffi_sizeof = ffi.sizeof

local ctypes = require "resty.openssl.auxiliary.ctypes"
require "resty.openssl.include.err"
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X

local constchar_ptrptr = ffi.typeof("const char*[1]")

local last_err_code = 0

local function get_last_error_code()
  local code = C.ERR_peek_last_error()
  last_err_code = code == 0 and last_err_code or code
  
  return last_err_code
end

local function get_lib_error_string(code)
  code = code or get_last_error_code()

  local msg = C.ERR_lib_error_string(code)
  if msg == nil then
    return "unknown library"
  end

  return ffi_str(msg)
end

local function get_reason_error_string(code)
  code = code or get_last_error_code()

  local msg = C.ERR_reason_error_string(code)
  if msg == nil then
    return ""
  end

  return ffi_str(msg)
end

local function format_error(ctx, code, all_errors)
  local errors = {}
  if code then
    table.insert(errors, string.format("code: %d", code or 0))
  end

  local line = ctypes.ptr_of_int()
  local path = constchar_ptrptr()
  local func = constchar_ptrptr()

  -- get the OpenSSL errors
  while C.ERR_peek_error() ~= 0 do
    local code
    if all_errors then
      if OPENSSL_3X then
        code = C.ERR_get_error_all(path, line, func, nil, nil)
      else
        code = C.ERR_get_error_line(path, line)
      end
    else
      if OPENSSL_3X then
        code = C.ERR_peek_last_error_all(path, line, func, nil, nil)
      else
        code = C.ERR_peek_last_error_line(path, line)
      end
    end

    last_err_code = code

    local abs_path = ffi_str(path[0])
    -- ../crypto/asn1/a_d2i_fp.c => crypto/asn1/a_d2i_fp.c
    local start = abs_path:find("/")
    if start then
      abs_path = abs_path:sub(start+1)
    end

    local err_line
  
    if OPENSSL_3X then
      local reason_msg = get_reason_error_string(code)
      local lib_msg = get_lib_error_string(code)
      -- error:04800065:PEM routines:PEM_do_header:bad decrypt:crypto/pem/pem_lib.c:467:
      err_line = string.format("error:%X:%s:%s:%s:%s:%d:",
        code, lib_msg, ffi_str(func[0]), reason_msg, abs_path, line[0])
    else
      local buf = ffi.new('char[256]')

      C.ERR_error_string_n(code, buf, ffi_sizeof(buf))
      err_line = string.format("%s:%d:%s",
        abs_path, line[0], ffi_str(buf))
    end

    table.insert(errors, err_line)

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
  get_last_error_code = get_last_error_code,
  get_lib_error_string = get_lib_error_string,
  get_reason_error_string = get_reason_error_string,
}
