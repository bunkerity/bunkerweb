local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.provider"

ffi.cdef [[
  typedef struct evp_mac_st EVP_MAC;
  typedef struct evp_mac_ctx_st EVP_MAC_CTX;

  EVP_MAC_CTX *EVP_MAC_CTX_new(EVP_MAC *mac);
  void EVP_MAC_CTX_free(EVP_MAC_CTX *ctx);

  const OSSL_PROVIDER *EVP_MAC_get0_provider(const EVP_MAC *mac);
  EVP_MAC *EVP_MAC_fetch(OSSL_LIB_CTX *libctx, const char *algorithm,
                          const char *properties);

  int EVP_MAC_init(EVP_MAC_CTX *ctx, const unsigned char *key, size_t keylen,
                    const OSSL_PARAM params[]);
  int EVP_MAC_update(EVP_MAC_CTX *ctx, const unsigned char *data, size_t datalen);
  int EVP_MAC_final(EVP_MAC_CTX *ctx,
                    unsigned char *out, size_t *outl, size_t outsize);

  size_t EVP_MAC_CTX_get_mac_size(EVP_MAC_CTX *ctx);

  typedef void* fake_openssl_mac_provided_list_fn(EVP_MAC *mac, void *arg);
  void EVP_MAC_do_all_provided(OSSL_LIB_CTX *libctx,
                              fake_openssl_mac_provided_list_fn*,
                              void *arg);
  int EVP_MAC_up_ref(EVP_MAC *mac);
  void EVP_MAC_free(EVP_MAC *mac);

  const char *EVP_MAC_get0_name(const EVP_MAC *mac);

  int EVP_MAC_CTX_set_params(EVP_MAC_CTX *ctx, const OSSL_PARAM params[]);
  const OSSL_PARAM *EVP_MAC_CTX_settable_params(EVP_MAC_CTX *ctx);
  int EVP_MAC_CTX_get_params(EVP_MAC_CTX *ctx, OSSL_PARAM params[]);
  const OSSL_PARAM *EVP_MAC_CTX_gettable_params(EVP_MAC_CTX *ctx);
]]