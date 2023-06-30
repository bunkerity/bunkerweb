local ffi = require "ffi"
local ffi_cast = ffi.cast
local C = ffi.C

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.evp.md"
local evp = require("resty.openssl.include.evp")
local ctypes = require "resty.openssl.auxiliary.ctypes"
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X
local BORINGSSL = require("resty.openssl.version").BORINGSSL

local void_ptr = ctypes.void_ptr

local _M = {
  EVP_PKEY_HKDEF_MODE_EXTRACT_AND_EXPAND = 0,
  EVP_PKEY_HKDEF_MODE_EXTRACT_ONLY       = 1,
  EVP_PKEY_HKDEF_MODE_EXPAND_ONLY        = 2,
}

if OPENSSL_3X then
  require "resty.openssl.include.provider"

  ffi.cdef [[
    const OSSL_PROVIDER *EVP_KDF_get0_provider(const EVP_KDF *kdf);

    typedef void* fake_openssl_kdf_provided_list_fn(EVP_KDF *kdf, void *arg);
    void EVP_KDF_do_all_provided(OSSL_LIB_CTX *libctx,
                                fake_openssl_kdf_provided_list_fn*,
                                void *arg);
    int EVP_KDF_up_ref(EVP_KDF *kdf);
    void EVP_KDF_free(EVP_KDF *kdf);

    const char *EVP_KDF_get0_name(const EVP_KDF *kdf);

    EVP_KDF *EVP_KDF_fetch(OSSL_LIB_CTX *libctx, const char *algorithm,
                            const char *properties);
    EVP_KDF_CTX *EVP_KDF_CTX_new(const EVP_KDF *kdf);
    void EVP_KDF_CTX_free(EVP_KDF_CTX *ctx);
    void EVP_KDF_CTX_reset(EVP_KDF_CTX *ctx);

    size_t EVP_KDF_CTX_get_kdf_size(EVP_KDF_CTX *ctx);
    int EVP_KDF_derive(EVP_KDF_CTX *ctx, unsigned char *key, size_t keylen,
                      const OSSL_PARAM params[]);

    int EVP_KDF_CTX_get_params(EVP_KDF_CTX *ctx, OSSL_PARAM params[]);
    int EVP_KDF_CTX_set_params(EVP_KDF_CTX *ctx, const OSSL_PARAM params[]);
    const OSSL_PARAM *EVP_KDF_CTX_gettable_params(const EVP_KDF_CTX *ctx);
    const OSSL_PARAM *EVP_KDF_CTX_settable_params(const EVP_KDF_CTX *ctx);
  ]]
end

if OPENSSL_3X or BORINGSSL then
  ffi.cdef [[
    int EVP_PKEY_CTX_set_tls1_prf_md(EVP_PKEY_CTX *ctx, const EVP_MD *md);
    int EVP_PKEY_CTX_set1_tls1_prf_secret(EVP_PKEY_CTX *pctx,
                                          const unsigned char *sec, int seclen);
    int EVP_PKEY_CTX_add1_tls1_prf_seed(EVP_PKEY_CTX *pctx,
                                        const unsigned char *seed, int seedlen);

    int EVP_PKEY_CTX_set_hkdf_md(EVP_PKEY_CTX *ctx, const EVP_MD *md);
    int EVP_PKEY_CTX_set1_hkdf_salt(EVP_PKEY_CTX *ctx,
                                    const unsigned char *salt, int saltlen);
    int EVP_PKEY_CTX_set1_hkdf_key(EVP_PKEY_CTX *ctx,
                                    const unsigned char *key, int keylen);
    int EVP_PKEY_CTX_set_hkdf_mode(EVP_PKEY_CTX *ctx, int mode);
    int EVP_PKEY_CTX_add1_hkdf_info(EVP_PKEY_CTX *ctx,
                                    const unsigned char *info, int infolen);
  ]]

  _M.EVP_PKEY_CTX_set_tls1_prf_md = function(pctx, md)
    return C.EVP_PKEY_CTX_set_tls1_prf_md(pctx, md)
  end
  _M.EVP_PKEY_CTX_set1_tls1_prf_secret = function(pctx, sec)
    return C.EVP_PKEY_CTX_set1_tls1_prf_secret(pctx, sec, #sec)
  end
  _M.EVP_PKEY_CTX_add1_tls1_prf_seed = function(pctx, seed)
    return C.EVP_PKEY_CTX_add1_tls1_prf_seed(pctx, seed, #seed)
  end

  _M.EVP_PKEY_CTX_set_hkdf_md = function(pctx, md)
    return C.EVP_PKEY_CTX_set_hkdf_md(pctx, md)
  end
  _M.EVP_PKEY_CTX_set1_hkdf_salt = function(pctx, salt)
    return C.EVP_PKEY_CTX_set1_hkdf_salt(pctx, salt, #salt)
  end
  _M.EVP_PKEY_CTX_set1_hkdf_key = function(pctx, key)
    return C.EVP_PKEY_CTX_set1_hkdf_key(pctx, key, #key)
  end
  _M.EVP_PKEY_CTX_set_hkdf_mode = function(pctx, mode)
    return C.EVP_PKEY_CTX_set_hkdf_mode(pctx, mode)
  end
  _M.EVP_PKEY_CTX_add1_hkdf_info = function(pctx, info)
    return C.EVP_PKEY_CTX_add1_hkdf_info(pctx, info, #info)
  end

else
  _M.EVP_PKEY_CTX_set_tls1_prf_md = function(pctx, md)
    return C.EVP_PKEY_CTX_ctrl(pctx, -1,
                                evp.EVP_PKEY_OP_DERIVE,
                                evp.EVP_PKEY_CTRL_TLS_MD,
                                0, ffi_cast(void_ptr, md))
  end
  _M.EVP_PKEY_CTX_set1_tls1_prf_secret = function(pctx, sec)
    return C.EVP_PKEY_CTX_ctrl(pctx, -1,
                                evp.EVP_PKEY_OP_DERIVE,
                                evp.EVP_PKEY_CTRL_TLS_SECRET,
                                #sec, ffi_cast(void_ptr, sec))
  end
  _M.EVP_PKEY_CTX_add1_tls1_prf_seed = function(pctx, seed)
    return C.EVP_PKEY_CTX_ctrl(pctx, -1,
                                evp.EVP_PKEY_OP_DERIVE,
                                evp.EVP_PKEY_CTRL_TLS_SEED,
                                #seed, ffi_cast(void_ptr, seed))
  end

  _M.EVP_PKEY_CTX_set_hkdf_md = function(pctx, md)
    return C.EVP_PKEY_CTX_ctrl(pctx, -1,
                                evp.EVP_PKEY_OP_DERIVE,
                                evp.EVP_PKEY_CTRL_HKDF_MD,
                                0, ffi_cast(void_ptr, md))
  end
  _M.EVP_PKEY_CTX_set1_hkdf_salt = function(pctx, salt)
    return C.EVP_PKEY_CTX_ctrl(pctx, -1,
                              evp.EVP_PKEY_OP_DERIVE,
                              evp.EVP_PKEY_CTRL_HKDF_SALT,
                              #salt, ffi_cast(void_ptr, salt))
  end
  _M.EVP_PKEY_CTX_set1_hkdf_key = function(pctx, key)
    return C.EVP_PKEY_CTX_ctrl(pctx, -1,
                              evp.EVP_PKEY_OP_DERIVE,
                              evp.EVP_PKEY_CTRL_HKDF_KEY,
                              #key, ffi_cast(void_ptr, key))
  end
  _M.EVP_PKEY_CTX_set_hkdf_mode = function(pctx, mode)
    return C.EVP_PKEY_CTX_ctrl(pctx, -1,
                              evp.EVP_PKEY_OP_DERIVE,
                              evp.EVP_PKEY_CTRL_HKDF_MODE,
                              mode, nil)
  end
  _M.EVP_PKEY_CTX_add1_hkdf_info = function(pctx, info)
    return C.EVP_PKEY_CTX_ctrl(pctx, -1,
                              evp.EVP_PKEY_OP_DERIVE,
                              evp.EVP_PKEY_CTRL_HKDF_INFO,
                              #info, ffi_cast(void_ptr, info))
  end
end

return _M