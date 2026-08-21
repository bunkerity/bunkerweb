local ffi = require "ffi"
local C = ffi.C
local ffi_str = ffi.string

local ctypes = require "resty.openssl.auxiliary.ctypes"
local ctx_lib = require "resty.openssl.ctx"
local format_error = require("resty.openssl.err").format_error

local _M = {}

-- OpenSSL 3 provider-native keys share the type-name and OSSL parameter APIs
-- regardless of algorithm family, and may not have an ASN.1 NID. Keep that
-- access path here; ecx.lua is only the pre-OpenSSL 3 compatibility path.
local function get_type_name(evp_pkey_st)
  local p = C.EVP_PKEY_get0_type_name(evp_pkey_st)
  if p == nil then
    return nil, "provider_key: cannot get key type name"
  end
  return ffi_str(p)
end

function _M.get_parameters(evp_pkey_st)
  return setmetatable({}, {
    __index = function(_, k)
      local param_name
      if k == "public" or k == "pub_key" then
        param_name = "pub"
      elseif k == "private" or k == "priv_key" then
        param_name = "priv"
      else
        return nil, "provider_key.get_parameters: unknown raw key parameter \"" .. k .. "\""
      end

      local length = ctypes.ptr_of_size_t()
      local code = C.EVP_PKEY_get_octet_string_param(evp_pkey_st,
                                                     param_name,
                                                     nil, 0, length)
      if code ~= 1 and param_name == "pub" then
        C.ERR_clear_error()
        param_name = "encoded-pub-key"
        code = C.EVP_PKEY_get_octet_string_param(evp_pkey_st,
                                                 param_name,
                                                 nil, 0, length)
      end
      if code ~= 1 then
        C.ERR_clear_error()
        return nil
      end

      local buf = ctypes.uchar_array(length[0])
      if C.EVP_PKEY_get_octet_string_param(evp_pkey_st, param_name,
                                           buf, length[0], length) ~= 1 then
        return nil, format_error("provider_key.get_parameters: EVP_PKEY_get_octet_string_param")
      end
      return ffi_str(buf, length[0])
    end
  }), nil
end

function _M.set_parameters(_, evp_pkey_st, opts, type_name, properties)
  if type_name == nil then
    type_name = get_type_name(evp_pkey_st)
    if type_name == nil then
      return nil, "provider_key.set_parameters: cannot get key type name"
    end
  end

  local key
  if opts.private ~= nil then
    local private = opts.private
    key = C.EVP_PKEY_new_raw_private_key_ex(ctx_lib.get_libctx(),
                                            type_name, properties,
                                            private, #private)
  elseif opts.public ~= nil then
    local public = opts.public
    key = C.EVP_PKEY_new_raw_public_key_ex(ctx_lib.get_libctx(),
                                           type_name, properties,
                                           public, #public)
  else
    return nil, "provider_key.set_parameters: no parameter is specified"
  end

  if key == nil then
    return nil, format_error("provider_key.set_parameters: EVP_PKEY_new_raw_*_key_ex")
  end
  return key
end

function _M.is_private(evp_pkey_st)
  local length = ctypes.ptr_of_size_t()
  local code = C.EVP_PKEY_get_octet_string_param(evp_pkey_st, "priv",
                                                 nil, 0, length)
  C.ERR_clear_error()
  return code == 1
end

return _M
