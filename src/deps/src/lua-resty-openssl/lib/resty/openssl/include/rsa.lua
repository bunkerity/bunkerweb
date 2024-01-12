local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"

ffi.cdef [[
  RSA *RSA_new(void);
  void RSA_free(RSA *r);

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
