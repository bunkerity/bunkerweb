local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X
local BORINGSSL = require("resty.openssl.version").BORINGSSL

if BORINGSSL then
  ffi.cdef [[
    int RAND_bytes(uint8_t *buf, size_t num);
    int RAND_priv_bytes(uint8_t *buf, size_t num);
  ]]
elseif OPENSSL_3X then
  ffi.cdef [[
    int RAND_bytes_ex(OSSL_LIB_CTX *ctx, unsigned char *buf, size_t num,
                      unsigned int strength);
    int RAND_priv_bytes_ex(OSSL_LIB_CTX *ctx, unsigned char *buf, size_t num,
                      unsigned int strength);
  ]]
else
  ffi.cdef [[
    int RAND_bytes(unsigned char *buf, int num);
    int RAND_priv_bytes(unsigned char *buf, int num);
  ]]
end
