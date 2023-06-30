local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
local OPENSSL_10 = require("resty.openssl.version").OPENSSL_10
local OPENSSL_11_OR_LATER = require("resty.openssl.version").OPENSSL_11_OR_LATER

ffi.cdef [[
  RSA *RSA_new(void);
  void RSA_free(RSA *r);
]]

if OPENSSL_11_OR_LATER then
  ffi.cdef [[
    void RSA_get0_key(const RSA *r,
              const BIGNUM **n, const BIGNUM **e, const BIGNUM **d);
    void RSA_get0_factors(const RSA *r, const BIGNUM **p, const BIGNUM **q);
    void RSA_get0_crt_params(const RSA *r,
              const BIGNUM **dmp1, const BIGNUM **dmq1,
              const BIGNUM **iqmp);

    int RSA_set0_key(RSA *r, BIGNUM *n, BIGNUM *e, BIGNUM *d);
    int RSA_set0_factors(RSA *r, BIGNUM *p, BIGNUM *q);
    int RSA_set0_crt_params(RSA *r,BIGNUM *dmp1, BIGNUM *dmq1, BIGNUM *iqmp);
    struct rsa_st;
  ]]
elseif OPENSSL_10 then
  ffi.cdef [[
    // crypto/rsa/rsa_locl.h
    // needed to extract parameters
    // Note: this struct is trimmed
    struct rsa_st {
      int pad;
      // the following has been changed in OpenSSL 1.1.x to int32_t
      long version;
      const RSA_METHOD *meth;
      ENGINE *engine;
      BIGNUM *n;
      BIGNUM *e;
      BIGNUM *d;
      BIGNUM *p;
      BIGNUM *q;
      BIGNUM *dmp1;
      BIGNUM *dmq1;
      BIGNUM *iqmp;
      // trimmed

      // CRYPTO_EX_DATA ex_data;
      // int references;
      // int flags;
      // BN_MONT_CTX *_method_mod_n;
      // BN_MONT_CTX *_method_mod_p;
      // BN_MONT_CTX *_method_mod_q;

      // char *bignum_data;
      // BN_BLINDING *blinding;
      // BN_BLINDING *mt_blinding;
    };
  ]]
end

return {
  paddings = {
    RSA_PKCS1_PADDING       = 1,
    RSA_SSLV23_PADDING      = 2,
    RSA_NO_PADDING          = 3,
    RSA_PKCS1_OAEP_PADDING  = 4,
    RSA_X931_PADDING        = 5,
    RSA_PKCS1_PSS_PADDING   = 6,
  },
}
