local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.param"

ffi.cdef [[
  typedef struct ossl_provider_st OSSL_PROVIDER;
  typedef struct ossl_lib_ctx_st OSSL_LIB_CTX;

  void OSSL_PROVIDER_set_default_search_path(OSSL_LIB_CTX *libctx,
                                             const char *path);


  OSSL_PROVIDER *OSSL_PROVIDER_load(OSSL_LIB_CTX *libctx, const char *name);
  OSSL_PROVIDER *OSSL_PROVIDER_try_load(OSSL_LIB_CTX *libctx, const char *name);
  int OSSL_PROVIDER_unload(OSSL_PROVIDER *prov);
  int OSSL_PROVIDER_available(OSSL_LIB_CTX *libctx, const char *name);

  const OSSL_PARAM *OSSL_PROVIDER_gettable_params(OSSL_PROVIDER *prov);
  int OSSL_PROVIDER_get_params(OSSL_PROVIDER *prov, OSSL_PARAM params[]);

  // int OSSL_PROVIDER_add_builtin(OSSL_LIB_CTX *libctx, const char *name,
  //                              ossl_provider_init_fn *init_fn);

  const char *OSSL_PROVIDER_get0_name(const OSSL_PROVIDER *prov);
  int OSSL_PROVIDER_self_test(const OSSL_PROVIDER *prov);
]]
