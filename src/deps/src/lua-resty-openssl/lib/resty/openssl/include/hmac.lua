local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.evp"

ffi.cdef [[
  int HMAC_Init_ex(HMAC_CTX *ctx, const void *key, int len,
                  const EVP_MD *md, ENGINE *impl);

  int HMAC_Update(HMAC_CTX *ctx, const unsigned char *data,
                            size_t len);
  int HMAC_Final(HMAC_CTX *ctx, unsigned char *md,
                            unsigned int *len);

  HMAC_CTX *HMAC_CTX_new(void);
  void HMAC_CTX_free(HMAC_CTX *ctx);
]]
