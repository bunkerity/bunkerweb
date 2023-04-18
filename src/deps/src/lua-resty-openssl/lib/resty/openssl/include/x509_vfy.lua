local ffi = require "ffi"
local C = ffi.C

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.stack"
local OPENSSL_10 = require("resty.openssl.version").OPENSSL_10
local OPENSSL_11_OR_LATER = require("resty.openssl.version").OPENSSL_11_OR_LATER
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X
local BORINGSSL_110 = require("resty.openssl.version").BORINGSSL_110

ffi.cdef [[
  X509_STORE *X509_STORE_new(void);
  void X509_STORE_free(X509_STORE *v);
 /* int X509_STORE_lock(X509_STORE *ctx);
  int X509_STORE_unlock(X509_STORE *ctx);
  int X509_STORE_up_ref(X509_STORE *v);
  // STACK_OF(X509_OBJECT)
  OPENSSL_STACK *X509_STORE_get0_objects(X509_STORE *v);*/

  int X509_STORE_add_cert(X509_STORE *ctx, X509 *x);
  int X509_STORE_add_crl(X509_STORE *ctx, X509_CRL *x);
  int X509_STORE_load_locations(X509_STORE *ctx,
                              const char *file, const char *dir);
  int X509_STORE_set_default_paths(X509_STORE *ctx);
  int X509_STORE_set_flags(X509_STORE *ctx, unsigned long flags);
  int X509_STORE_set_depth(X509_STORE *store, int depth);
  int X509_STORE_set_purpose(X509_STORE *ctx, int purpose);

  X509_STORE_CTX *X509_STORE_CTX_new(void);
  void X509_STORE_CTX_free(X509_STORE_CTX *ctx);
  // STACK_OF(X509)
  int X509_STORE_CTX_init(X509_STORE_CTX *ctx, X509_STORE *store,
                        X509 *x509, OPENSSL_STACK *chain);

  int X509_STORE_CTX_get_error(X509_STORE_CTX *ctx);

  int X509_STORE_CTX_set_default(X509_STORE_CTX *ctx, const char *name);

  void X509_STORE_CTX_set_flags(X509_STORE_CTX *ctx, unsigned long flags);

  int X509_PURPOSE_get_by_sname(char *sname);
  X509_PURPOSE *X509_PURPOSE_get0(int idx);
  int X509_PURPOSE_get_id(const X509_PURPOSE *xp);
]]

local _M = {
  verify_flags = {
    X509_V_FLAG_CB_ISSUER_CHECK              = 0x0,   -- Deprecated
    X509_V_FLAG_USE_CHECK_TIME               = 0x2,
    X509_V_FLAG_CRL_CHECK                    = 0x4,
    X509_V_FLAG_CRL_CHECK_ALL                = 0x8,
    X509_V_FLAG_IGNORE_CRITICAL              = 0x10,
    X509_V_FLAG_X509_STRICT                  = 0x20,
    X509_V_FLAG_ALLOW_PROXY_CERTS            = 0x40,
    X509_V_FLAG_POLICY_CHECK                 = 0x80,
    X509_V_FLAG_EXPLICIT_POLICY              = 0x100,
    X509_V_FLAG_INHIBIT_ANY                  = 0x200,
    X509_V_FLAG_INHIBIT_MAP                  = 0x400,
    X509_V_FLAG_NOTIFY_POLICY                = 0x800,
    X509_V_FLAG_EXTENDED_CRL_SUPPORT         = 0x1000,
    X509_V_FLAG_USE_DELTAS                   = 0x2000,
    X509_V_FLAG_CHECK_SS_SIGNATURE           = 0x4000,
    X509_V_FLAG_TRUSTED_FIRST                = 0x8000,
    X509_V_FLAG_SUITEB_128_LOS_ONLY          = 0x10000,
    X509_V_FLAG_SUITEB_192_LOS               = 0x20000,
    X509_V_FLAG_SUITEB_128_LOS               = 0x30000,
    X509_V_FLAG_PARTIAL_CHAIN                = 0x80000,
    X509_V_FLAG_NO_ALT_CHAINS                = 0x100000,
    X509_V_FLAG_NO_CHECK_TIME                = 0x200000,
  },
}

if OPENSSL_10 or BORINGSSL_110 then
  ffi.cdef [[
    // STACK_OF(X509)
    OPENSSL_STACK *X509_STORE_CTX_get_chain(X509_STORE_CTX *ctx);
  ]];
  _M.X509_STORE_CTX_get0_chain = C.X509_STORE_CTX_get_chain
elseif OPENSSL_11_OR_LATER then
  ffi.cdef [[
    // STACK_OF(X509)
    OPENSSL_STACK *X509_STORE_CTX_get0_chain(X509_STORE_CTX *ctx);
  ]];
  _M.X509_STORE_CTX_get0_chain = C.X509_STORE_CTX_get0_chain
end

if OPENSSL_3X then
  ffi.cdef [[
    X509_STORE_CTX *X509_STORE_CTX_new_ex(OSSL_LIB_CTX *libctx, const char *propq);

    int X509_STORE_set_default_paths_ex(X509_STORE *ctx, OSSL_LIB_CTX *libctx,
                                        const char *propq);
    /* int X509_STORE_load_file_ex(X509_STORE *ctx, const char *file,
                                OSSL_LIB_CTX *libctx, const char *propq);
    int X509_STORE_load_store_ex(X509_STORE *ctx, const char *uri,
                                OSSL_LIB_CTX *libctx, const char *propq); */
    int X509_STORE_load_locations_ex(X509_STORE *ctx, const char *file,
                                    const char *dir, OSSL_LIB_CTX *libctx,
                                    const char *propq);
  ]]
  _M.X509_STORE_set_default_paths = function(...) return C.X509_STORE_set_default_paths_ex(...) end
  _M.X509_STORE_load_locations = function(...) return C.X509_STORE_load_locations_ex(...) end
else
  _M.X509_STORE_set_default_paths = function(s) return C.X509_STORE_set_default_paths(s) end
  _M.X509_STORE_load_locations = function(s, file, dir) return C.X509_STORE_load_locations(s, file, dir) end
end


return _M

