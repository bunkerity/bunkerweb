local ffi = require "ffi"
local C = ffi.C
local ffi_str = ffi.string
local ffi_sizeof = ffi.sizeof

require "resty.openssl.include.objects"
require "resty.openssl.include.err"

local buf = ffi.new('char[?]', 100)

local function obj2table(obj)
  local nid = C.OBJ_obj2nid(obj)

  local len = C.OBJ_obj2txt(buf, ffi_sizeof(buf), obj, 1)
  local oid = ffi_str(buf, len)

  return {
    id = oid,
    nid = nid,
    sn = ffi_str(C.OBJ_nid2sn(nid)),
    ln = ffi_str(C.OBJ_nid2ln(nid)),
  }
end

local function nid2table(nid)
  return obj2table(C.OBJ_nid2obj(nid))
end

local function txt2nid(txt)
  if type(txt) ~= "string" then
    return nil, "objects.txt2nid: expect a string at #1"
  end
  local nid = C.OBJ_txt2nid(txt)
  if nid == 0 then
    -- clean up error occurs during OBJ_txt2nid
    C.ERR_clear_error()
    return nil, "objects.txt2nid: invalid NID text " .. txt
  end
  return nid
end

local function txtnid2nid(txt_nid)
  local nid
  if type(txt_nid) == "string" then
    nid = C.OBJ_txt2nid(txt_nid)
    if nid == 0 then
      -- clean up error occurs during OBJ_txt2nid
      C.ERR_clear_error()
      return nil, "objects.txtnid2nid: invalid NID text " .. txt_nid
    end
  elseif type(txt_nid) == "number" then
    nid = txt_nid
  else
    return nil, "objects.txtnid2nid: expect string or number at #1"
  end
  return nid
end

local function find_sigid_algs(nid)
  local out = ffi.new("int[0]")
  if C.OBJ_find_sigid_algs(nid, out, nil) == 0 then
    return 0, "objects.find_sigid_algs: invalid sigid " .. nid
  end
  return tonumber(out[0])
end

return {
  obj2table = obj2table,
  nid2table = nid2table,
  txt2nid = txt2nid,
  txtnid2nid = txtnid2nid,
  find_sigid_algs = find_sigid_algs,
  create = C.OBJ_create,
}