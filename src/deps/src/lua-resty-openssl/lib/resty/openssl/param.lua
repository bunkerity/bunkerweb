local ffi = require "ffi"
local C = ffi.C
local ffi_new = ffi.new
local ffi_str = ffi.string
local ffi_cast = ffi.cast

require "resty.openssl.include.param"
local format_error = require("resty.openssl.err").format_error
local bn_lib = require("resty.openssl.bn")
local null = require("resty.openssl.auxiliary.ctypes").null

local OSSL_PARAM_INTEGER = 1
local OSSL_PARAM_UNSIGNED_INTEGER = 2
local OSSL_PARAM_REAL = 3
local OSSL_PARAM_UTF8_STRING = 4
local OSSL_PARAM_OCTET_STRING = 5
local OSSL_PARAM_UTF8_PTR = 6
local OSSL_PARAM_OCTET_PTR = 7

local alter_type_key = {}
local buf_param_key = {}

local function construct(buf_t, length, types_map, types_size)
  if not length then
    length = 0
    for k, v in pairs(buf_t) do length = length + 1 end
  end

  local params = ffi_new("OSSL_PARAM[?]", length + 1)

  local i = 0
  local buf_param
  for key, value in pairs(buf_t) do
    local typ = types_map[key]
    if not typ then
      return nil, "param:construct: unknown key \"" .. key .. "\""
    end
    local param, buf, size
    if value == null then -- out
      value = nil
      size = types_size and types_size[key] or 100
      if typ == OSSL_PARAM_UTF8_STRING or typ == OSSL_PARAM_OCTET_STRING then
        buf = ffi_new("char[?]", size)
      end
    else
      local numeric = type(value) == "number"
      if (numeric and typ >= OSSL_PARAM_UTF8_STRING) or
        (not numeric and typ <= OSSL_PARAM_UNSIGNED_INTEGER) then
        local alter_typ = types_map[alter_type_key] and types_map[alter_type_key][key]
        if alter_typ and ((numeric and alter_typ <= OSSL_PARAM_UNSIGNED_INTEGER) or
                        (not numeric and alter_typ >= OSSL_PARAM_UTF8_STRING)) then
          typ = alter_typ
        else
          return nil, "param:construct: key \"" .. key .. "\" can't be a " .. type(value)
        end
      end
    end

    if typ == "bn" then -- out only
      buf = ffi_new("char[?]", size)
      param = C.OSSL_PARAM_construct_BN(key, buf, size)
      buf_param = buf_param or {}
      buf_param[key] = param
    elseif typ == OSSL_PARAM_INTEGER then
      buf = value and ffi_new("int[1]", value) or ffi_new("int[1]")
      param = C.OSSL_PARAM_construct_int(key, buf)
    elseif typ == OSSL_PARAM_UNSIGNED_INTEGER then
      buf = value and ffi_new("unsigned int[1]", value) or
                      ffi_new("unsigned int[1]")
      param = C.OSSL_PARAM_construct_uint(key, buf)
    elseif typ == OSSL_PARAM_UTF8_STRING then
      buf = value and ffi_cast("char *", value) or buf
      param = C.OSSL_PARAM_construct_utf8_string(key, buf, value and #value or size)
    elseif typ == OSSL_PARAM_OCTET_STRING then
      buf = value and ffi_cast("char *", value) or buf
      param = C.OSSL_PARAM_construct_octet_string(key, ffi_cast("void*", buf),
                                                  value and #value or size)
    elseif typ == OSSL_PARAM_UTF8_PTR then
      buf = ffi_new("char*[1]")
      param = C.OSSL_PARAM_construct_utf8_ptr(key, buf, 0)
    elseif typ == OSSL_PARAM_OCTET_PTR then
      buf = ffi_new("char*[1]")
      param = C.OSSL_PARAM_construct_octet_ptr(key, ffi_cast("void**", buf), 0)
    else
      error("type " .. typ .. " is not yet implemented")
    end
    if not value then -- out
      buf_t[key] = buf
    end
    params[i] = param
    i = i + 1
  end

  buf_t[buf_param_key] = buf_param
  params[length] = C.OSSL_PARAM_construct_end()

  return params
end

local function parse(buf_t, length, types_map, types_size)
  for key, buf in pairs(buf_t) do
    local typ = types_map[key]
    local sz = types_size and types_size[key]

    if key == buf_param_key then -- luacheck: ignore
      -- ignore
    elseif buf == nil or buf[0] == nil then
      buf_t[key] = nil
    elseif typ == "bn" then
      local bn_t = ffi_new("BIGNUM*[1]")
      local param = buf_t[buf_param_key][key]
      if C.OSSL_PARAM_get_BN(param, bn_t) ~= 1 then
        return nil, format_error("param:parse: OSSL_PARAM_get_BN")
      end
      buf_t[key] = bn_lib.dup(bn_t[0])
    elseif typ == OSSL_PARAM_INTEGER or
        typ == OSSL_PARAM_UNSIGNED_INTEGER then
      buf_t[key] = tonumber(buf[0])
    elseif typ == OSSL_PARAM_UTF8_STRING or
        typ == OSSL_PARAM_OCTET_STRING then
      buf_t[key] = sz and ffi_str(buf, sz) or ffi_str(buf)
    elseif typ == OSSL_PARAM_UTF8_PTR or
          typ == OSSL_PARAM_OCTET_PTR then
      buf_t[key] = sz and ffi_str(buf[0], sz) or ffi_str(buf[0])
    elseif not typ then
        return nil, "param:parse: unknown key type \"" .. key .. "\""
    else
      error("type " .. typ .. " is not yet implemented")
    end
  end
  -- for GC
  buf_t[buf_param_key] = nil

  return buf_t
end

local param_type_readable = {
  [OSSL_PARAM_UNSIGNED_INTEGER] = "unsigned integer",
  [OSSL_PARAM_INTEGER] = "integer",
  [OSSL_PARAM_REAL] = "real number",
  [OSSL_PARAM_UTF8_PTR] = "pointer to a UTF8 encoded string",
  [OSSL_PARAM_UTF8_STRING] = "UTF8 encoded string",
  [OSSL_PARAM_OCTET_PTR] = "pointer to an octet string",
  [OSSL_PARAM_OCTET_STRING] = "octet string",
}

local function readable_data_type(p)
  local typ = p.data_type
  local literal = param_type_readable[typ]
  if not literal then
    literal = string.format("unknown type [%d]", typ)
  end

  local sz = tonumber(p.data_size)
  if sz == 0 then
    literal = literal .. " (arbitrary size)"
  else
    literal = literal .. string.format(" (max %d bytes large)", sz)
  end
  return literal
end

local function parse_params_schema(params, schema, schema_readable)
  if params == nil then
    return nil, format_error("parse_params_schema")
  end

  local i = 0
  while true do
    local p = params[i]
    if p.key == nil then
      break
    end
    local key = ffi_str(p.key)
    if schema then
      -- TODO: don't support same key with different types for now
      -- prefer string type over integer types
      local typ = tonumber(p.data_type)
      if schema[key] then
        schema[alter_type_key] = schema[alter_type_key] or {}
        schema[alter_type_key][key] = typ
      else
        schema[key] = typ
      end
    end
    -- if schema_return_size then -- only non-ptr string types are needed actually
    --   schema_return_size[key] = tonumber(p.return_size)
    -- end
    if schema_readable then
      table.insert(schema_readable, { key, readable_data_type(p) })
    end
    i = i + 1
  end
  return schema
end

local param_maps_set, param_maps_get = {}, {}

local function get_params_func(typ, field)
  local typ_lower = typ:sub(5):lower()
  if typ_lower:sub(-4) == "_ctx" then
    typ_lower = typ_lower:sub(0, -5)
  end
  -- field name for indexing schema, usually the (const) one created by
  -- EVP_TYP_fetch or EVP_get_typebynam,e
  field = field or "algo"

  local cf_settable = C[typ .. "_settable_params"]
  local settable = function(self, raw)
    local k = self[field]
    if raw and param_maps_set[k] then
      return param_maps_set[k]
    end

    local param = cf_settable(self.ctx)
    -- no params, this is fine, shouldn't be regarded as an error
    if param == nil then
      param_maps_set[k] = {}
      return {}
    end
    local schema, schema_reabale = {}, raw and nil or {}
    parse_params_schema(param, schema, schema_reabale)
    param_maps_set[k] = schema

    return raw and schema or schema_reabale
  end

  local cf_set = C[typ .. "_set_params"]
  local set = function(self, params)
    if not param_maps_set[self[field]] then
      local ok, err = self:settable_params()
      if not ok then
        return false, typ_lower .. ":set_params: " .. err
      end
    end

    local oparams, err = construct(params, nil, param_maps_set[self[field]])
    if err then
      return false, typ_lower .. ":set_params: " .. err
    end

    if cf_set(self.ctx, oparams) ~= 1 then
      return false, format_error(typ_lower .. ":set_params: " .. typ .. "_set_params")
    end

    return true
  end

  local cf_gettable = C[typ .. "_gettable_params"]
  local gettable = function(self, raw)
    local k = self[field]
    if raw and param_maps_set[k] then
      return param_maps_set[k]
    end

    local param = cf_gettable(self.ctx)
    -- no params, this is fine, shouldn't be regarded as an error
    if param == nil then
      param_maps_get[k] = {}
      return {}
    end
    local schema, schema_reabale = {}, raw and nil or {}
    parse_params_schema(param, schema, schema_reabale)
    param_maps_set[k] = schema

    return raw and schema or schema_reabale
  end

  local cf_get = C[typ .. "_get_params"]
  local get_buffer, get_size_map = {}, {}
  local get = function(self, key, want_size, want_type)
    if not param_maps_get[self[field]] then
      local ok, err = self:gettable_params()
      if not ok then
        return false, typ_lower .. ":set_params: " .. err
      end
    end
    local schema = param_maps_set[self[field]]
    if schema == nil or not schema[key] then -- nil or null
      return nil, typ_lower .. ":get_param: unknown key \"" .. key .. "\""
    end

    table.clear(get_buffer)
    table.clear(get_size_map)
    get_buffer[key] = null
    get_size_map[key] = want_size
    schema = want_type and { [key] = want_type } or schema

    local req, err = construct(get_buffer, 1, schema, get_size_map)
    if not req then
      return nil, typ_lower .. ":get_param: failed to construct params: " .. err
    end

    if cf_get(self.ctx, req) ~= 1 then
      return nil, format_error(typ_lower .. ":get_param:get")
    end

    get_buffer, err = parse(get_buffer, 1, schema, get_size_map)
    if err then
      return nil, typ_lower .. ":get_param: failed to parse params: " .. err
    end

    return get_buffer[key]
  end

  return settable, set, gettable, get
end

return {
  OSSL_PARAM_INTEGER = OSSL_PARAM_INTEGER,
  OSSL_PARAM_UNSIGNED_INTEGER = OSSL_PARAM_INTEGER,
  OSSL_PARAM_REAL = OSSL_PARAM_REAL,
  OSSL_PARAM_UTF8_STRING = OSSL_PARAM_UTF8_STRING,
  OSSL_PARAM_OCTET_STRING = OSSL_PARAM_OCTET_STRING,
  OSSL_PARAM_UTF8_PTR = OSSL_PARAM_UTF8_PTR,
  OSSL_PARAM_OCTET_PTR = OSSL_PARAM_OCTET_PTR,

  construct = construct,
  parse = parse,
  parse_params_schema = parse_params_schema,
  get_params_func = get_params_func,
}