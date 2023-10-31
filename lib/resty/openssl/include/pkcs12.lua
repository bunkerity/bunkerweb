local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.stack"

local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X

ffi.cdef [[
  // hack by changing char* to const char* here
  PKCS12 *PKCS12_create(const char *pass, const char *name, EVP_PKEY *pkey, X509 *cert,
                        OPENSSL_STACK *ca, // STACK_OF(X509)
                        int nid_key, int nid_cert, int iter, int mac_iter, int keytype);

  int PKCS12_parse(PKCS12 *p12, const char *pass, EVP_PKEY **pkey, X509 **cert,
                    OPENSSL_STACK **ca); // STACK_OF(X509) **ca);

  void PKCS12_free(PKCS12 *p12);
  int i2d_PKCS12_bio(BIO *bp, PKCS12 *a);
  PKCS12 *d2i_PKCS12_bio(BIO *bp, PKCS12 **a);
]]

if OPENSSL_3X then
  ffi.cdef [[
    PKCS12 *PKCS12_create_ex(const char *pass, const char *name, EVP_PKEY *pkey,
                              X509 *cert,
                              OPENSSL_STACK *ca, // STACK_OF(X509)
                              int nid_key, int nid_cert,
                              int iter, int mac_iter, int keytype,
                              OSSL_LIB_CTX *ctx, const char *propq);
  ]]
end
