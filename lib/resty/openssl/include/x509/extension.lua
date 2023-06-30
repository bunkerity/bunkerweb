local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.x509v3"
require "resty.openssl.include.x509"
local asn1_macro = require "resty.openssl.include.asn1"
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X

asn1_macro.declare_asn1_functions("X509_EXTENSION")

if OPENSSL_3X then
  ffi.cdef [[
    struct v3_ext_ctx {
      int flags;
      X509 *issuer_cert;
      X509 *subject_cert;
      X509_REQ *subject_req;
      X509_CRL *crl;
      /*X509V3_CONF_METHOD*/ void *db_meth;
      void *db;
      EVP_PKEY *issuer_pkey;
    };

    int X509V3_set_issuer_pkey(X509V3_CTX *ctx, EVP_PKEY *pkey);
  ]]

else
  ffi.cdef [[
    struct v3_ext_ctx {
      int flags;
      X509 *issuer_cert;
      X509 *subject_cert;
      X509_REQ *subject_req;
      X509_CRL *crl;
      /*X509V3_CONF_METHOD*/ void *db_meth;
      void *db;
    };
  ]]
end

ffi.cdef [[
  int X509_EXTENSION_set_data(X509_EXTENSION *ex, ASN1_OCTET_STRING *data);
  int X509_EXTENSION_set_object(X509_EXTENSION *ex, const ASN1_OBJECT *obj);
]]