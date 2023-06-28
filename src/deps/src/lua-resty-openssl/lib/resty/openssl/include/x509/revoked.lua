local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.asn1"
require "resty.openssl.include.objects"
local asn1_macro = require "resty.openssl.include.asn1"

asn1_macro.declare_asn1_functions("X509_REVOKED")

ffi.cdef [[
  int X509_REVOKED_set_serialNumber(X509_REVOKED *x, ASN1_INTEGER *serial);
  int X509_REVOKED_set_revocationDate(X509_REVOKED *r, ASN1_TIME *tm);
  int X509_REVOKED_add_ext(X509_REVOKED *x, X509_EXTENSION *ex, int loc);

  const ASN1_INTEGER *X509_REVOKED_get0_serialNumber(const X509_REVOKED *r);
  const ASN1_TIME *X509_REVOKED_get0_revocationDate(const X509_REVOKED *r);
]]