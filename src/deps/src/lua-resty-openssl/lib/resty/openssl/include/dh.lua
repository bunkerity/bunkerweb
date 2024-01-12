local ffi = require "ffi"
local C = ffi.C

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.objects"

ffi.cdef [[
  void DH_get0_pqg(const DH *dh,
                const BIGNUM **p, const BIGNUM **q, const BIGNUM **g);
  int DH_set0_pqg(DH *dh, BIGNUM *p, BIGNUM *q, BIGNUM *g);
  void DH_get0_key(const DH *dh,
                  const BIGNUM **pub_key, const BIGNUM **priv_key);
  int DH_set0_key(DH *dh, BIGNUM *pub_key, BIGNUM *priv_key);

  DH *DH_get_1024_160(void);
  DH *DH_get_2048_224(void);
  DH *DH_get_2048_256(void);
  DH *DH_new_by_nid(int nid);
]];


local dh_groups = {
  -- per https://tools.ietf.org/html/rfc5114
  dh_1024_160 = function() return C.DH_get_1024_160() end,
  dh_2048_224 = function() return C.DH_get_2048_224() end,
  dh_2048_256 = function() return C.DH_get_2048_256() end,
}

local groups = {
  "ffdhe2048", "ffdhe3072", "ffdhe4096", "ffdhe6144", "ffdhe8192",
  "modp_2048", "modp_3072", "modp_4096", "modp_6144", "modp_8192",
  -- following cannot be used with FIPS provider
  "modp_1536", -- and the RFC5114 ones
}

for _, group in ipairs(groups) do
  local nid = C.OBJ_sn2nid(group)
  if nid ~= 0 then
    dh_groups[group] = function() return C.DH_new_by_nid(nid) end
  end
end

return {
  dh_groups = dh_groups,
}
