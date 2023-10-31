local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.evp"
local OPENSSL_10 = require("resty.openssl.version").OPENSSL_10
local OPENSSL_11_OR_LATER = require("resty.openssl.version").OPENSSL_11_OR_LATER
local BORINGSSL = require("resty.openssl.version").BORINGSSL

if BORINGSSL then
  ffi.cdef [[
    int HMAC_Init_ex(HMAC_CTX *ctx, const void *key, size_t key_len,
                    const EVP_MD *md, ENGINE *impl);
  ]]
else
  ffi.cdef [[
    int HMAC_Init_ex(HMAC_CTX *ctx, const void *key, int len,
                    const EVP_MD *md, ENGINE *impl);
  ]]
end

ffi.cdef [[
  int HMAC_Update(HMAC_CTX *ctx, const unsigned char *data,
                            size_t len);
  int HMAC_Final(HMAC_CTX *ctx, unsigned char *md,
                            unsigned int *len);
]]

if OPENSSL_11_OR_LATER then
  ffi.cdef [[
    HMAC_CTX *HMAC_CTX_new(void);
    void HMAC_CTX_free(HMAC_CTX *ctx);
  ]]
elseif OPENSSL_10 then
  ffi.cdef [[
    // # define HMAC_MAX_MD_CBLOCK      128/* largest known is SHA512 */
    struct hmac_ctx_st {
      const EVP_MD *md;
      EVP_MD_CTX md_ctx;
      EVP_MD_CTX i_ctx;
      EVP_MD_CTX o_ctx;
      unsigned int key_length;
      unsigned char key[128];
    };

    void HMAC_CTX_init(HMAC_CTX *ctx);
    void HMAC_CTX_cleanup(HMAC_CTX *ctx);
  ]]
end