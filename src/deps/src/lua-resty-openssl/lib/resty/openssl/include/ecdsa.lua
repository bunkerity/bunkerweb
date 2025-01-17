local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"

ffi.cdef [[
  ECDSA_SIG *ECDSA_SIG_new(void);
  void ECDSA_SIG_free(ECDSA_SIG *sig);

  void ECDSA_SIG_get0(const ECDSA_SIG *sig, const BIGNUM **pr, const BIGNUM **ps);
  int ECDSA_SIG_set0(ECDSA_SIG *sig, BIGNUM *r, BIGNUM *s);

  int i2d_ECDSA_SIG(const ECDSA_SIG *sig, unsigned char **pp);
  ECDSA_SIG *d2i_ECDSA_SIG(ECDSA_SIG **sig, const unsigned char **pp, long len);

  int EC_GROUP_order_bits(const EC_GROUP *group);
]]
