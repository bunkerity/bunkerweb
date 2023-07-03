local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.evp"
require "resty.openssl.include.objects"
require "resty.openssl.include.x509"
require "resty.openssl.include.stack"

local asn1_macro = require "resty.openssl.include.asn1"

local OPENSSL_10 = require("resty.openssl.version").OPENSSL_10
local OPENSSL_11_OR_LATER = require("resty.openssl.version").OPENSSL_11_OR_LATER
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X
local BORINGSSL_110 = require("resty.openssl.version").BORINGSSL_110

asn1_macro.declare_asn1_functions("X509_REQ", asn1_macro.has_new_ex)

ffi.cdef [[
  int X509_REQ_set_subject_name(X509_REQ *req, X509_NAME *name);

  EVP_PKEY *X509_REQ_get_pubkey(X509_REQ *req);
  int X509_REQ_set_pubkey(X509_REQ *x, EVP_PKEY *pkey);

  int X509_REQ_set_version(X509_REQ *x, long version);

  int X509_REQ_get_attr_count(const X509_REQ *req);

  int X509_CRL_add_ext(X509_CRL *x, X509_EXTENSION *ex, int loc);
  X509_EXTENSION *X509_CRL_get_ext(const X509_CRL *x, int loc);
  int X509_CRL_get_ext_by_NID(const X509_CRL *x, int nid, int lastpos);

  int i2d_re_X509_REQ_tbs(X509_REQ *req, unsigned char **pp);
  void X509_ATTRIBUTE_free(X509_ATTRIBUTE *a);
  int X509_REQ_get_attr_by_NID(const X509_REQ *req, int nid, int lastpos);
  X509_ATTRIBUTE *X509_REQ_delete_attr(X509_REQ *req, int loc);

  int *X509_REQ_get_extension_nids(void);

  int X509_REQ_sign(X509_REQ *x, EVP_PKEY *pkey, const EVP_MD *md);
  int X509_REQ_verify(X509_REQ *a, EVP_PKEY *r);

  int i2d_X509_REQ_bio(BIO *bp, X509_REQ *req);
  X509_REQ *d2i_X509_REQ_bio(BIO *bp, X509_REQ **req);

  // STACK_OF(X509_EXTENSION)
  OPENSSL_STACK *X509_REQ_get_extensions(X509_REQ *req);
  // STACK_OF(X509_EXTENSION)
  int X509_REQ_add_extensions(X509_REQ *req, OPENSSL_STACK *exts);

  int X509_REQ_check_private_key(X509_REQ *x, EVP_PKEY *k);
]]

if OPENSSL_11_OR_LATER then
  ffi.cdef [[
    X509_NAME *X509_REQ_get_subject_name(const X509_REQ *req);
    long X509_REQ_get_version(const X509_REQ *req);

    int X509_REQ_get_signature_nid(const X509_REQ *crl);
  ]]
end
if OPENSSL_10 or BORINGSSL_110 then
  ffi.cdef [[
    typedef struct X509_req_info_st {
      ASN1_ENCODING enc;
      ASN1_INTEGER *version;
      X509_NAME *subject;
      /*X509_PUBKEY*/ void *pubkey;
      /*  d=2 hl=2 l=  0 cons: cont: 00 */
      /*STACK_OF(X509_ATTRIBUTE)*/ OPENSSL_STACK *attributes; /* [ 0 ] */
    } X509_REQ_INFO;

    // Note: this struct is trimmed
    typedef struct X509_req_st {
      X509_REQ_INFO *req_info;
      X509_ALGOR *sig_alg;
      // trimmed
      //ASN1_BIT_STRING *signature;
      //int references;
    } X509_REQ;
  ]]
end

if OPENSSL_3X then
  ffi.cdef [[
    int X509_REQ_verify_ex(X509_REQ *a, EVP_PKEY *pkey, OSSL_LIB_CTX *libctx,
                          const char *propq);
  ]]
end
