local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.bio"
require "resty.openssl.include.pem"
require "resty.openssl.include.stack"
local asn1_macro = require "resty.openssl.include.asn1"

local OPENSSL_10 = require("resty.openssl.version").OPENSSL_10
local OPENSSL_11_OR_LATER = require("resty.openssl.version").OPENSSL_11_OR_LATER
local BORINGSSL_110 = require("resty.openssl.version").BORINGSSL_110

asn1_macro.declare_asn1_functions("X509", asn1_macro.has_new_ex)

ffi.cdef [[
  int i2d_X509_bio(BIO *bp, X509 *x509);
  X509 *d2i_X509_bio(BIO *bp, X509 **x509);

  // STACK_OF(X509)
  OPENSSL_STACK *X509_chain_up_ref(OPENSSL_STACK *chain);

  int X509_sign(X509 *x, EVP_PKEY *pkey, const EVP_MD *md);
  int X509_verify(X509 *a, EVP_PKEY *r);

  ASN1_TIME *X509_gmtime_adj(ASN1_TIME *s, long adj);

  int X509_add_ext(X509 *x, X509_EXTENSION *ex, int loc);
  X509_EXTENSION *X509_get_ext(const X509 *x, int loc);
  int X509_get_ext_by_NID(const X509 *x, int nid, int lastpos);
  void *X509_get_ext_d2i(const X509 *x, int nid, int *crit, int *idx);

  int X509_EXTENSION_set_critical(X509_EXTENSION *ex, int crit);
  int X509_EXTENSION_get_critical(const X509_EXTENSION *ex);
  ASN1_OBJECT *X509_EXTENSION_get_object(X509_EXTENSION *ex);
  ASN1_OCTET_STRING *X509_EXTENSION_get_data(X509_EXTENSION *ne);
  X509_EXTENSION *X509V3_EXT_i2d(int ext_nid, int crit, void *ext_struc);
  X509_EXTENSION *X509_EXTENSION_create_by_NID(X509_EXTENSION **ex,
                                             int nid, int crit,
                                             ASN1_OCTET_STRING *data);

  // needed by pkey
  EVP_PKEY *d2i_PrivateKey_bio(BIO *bp, EVP_PKEY **a);
  EVP_PKEY *d2i_PUBKEY_bio(BIO *bp, EVP_PKEY **a);
  int i2d_PrivateKey_bio(BIO *bp, EVP_PKEY *pkey);
  int i2d_PUBKEY_bio(BIO *bp, EVP_PKEY *pkey);

  EVP_PKEY *X509_get_pubkey(X509 *x);
  int X509_set_pubkey(X509 *x, EVP_PKEY *pkey);
  int X509_set_version(X509 *x, long version);
  int X509_set_serialNumber(X509 *x, ASN1_INTEGER *serial);

  X509_NAME *X509_get_subject_name(const X509 *a);
  int X509_set_subject_name(X509 *x, X509_NAME *name);
  X509_NAME *X509_get_issuer_name(const X509 *a);
  int X509_set_issuer_name(X509 *x, X509_NAME *name);

  int X509_pubkey_digest(const X509 *data, const EVP_MD *type,
                       unsigned char *md, unsigned int *len);
  int X509_digest(const X509 *data, const EVP_MD *type,
                unsigned char *md, unsigned int *len);

  const char *X509_verify_cert_error_string(long n);
  int X509_verify_cert(X509_STORE_CTX *ctx);

  int X509_get_signature_nid(const X509 *x);

  unsigned char *X509_alias_get0(X509 *x, int *len);
  unsigned char *X509_keyid_get0(X509 *x, int *len);
  int X509_check_private_key(X509 *x, EVP_PKEY *k);
]]

if OPENSSL_11_OR_LATER then
  ffi.cdef [[
    int X509_up_ref(X509 *a);

    int X509_set1_notBefore(X509 *x, const ASN1_TIME *tm);
    int X509_set1_notAfter(X509 *x, const ASN1_TIME *tm);
    /*const*/ ASN1_TIME *X509_get0_notBefore(const X509 *x);
    /*const*/ ASN1_TIME *X509_get0_notAfter(const X509 *x);
    long X509_get_version(const X509 *x);
    const ASN1_INTEGER *X509_get0_serialNumber(X509 *x);

    X509_EXTENSION *X509_delete_ext(X509 *x, int loc);
  ]]
elseif OPENSSL_10 then
  ffi.cdef [[
    // STACK_OF(X509_EXTENSION)
    X509_EXTENSION *X509v3_delete_ext(OPENSSL_STACK *x, int loc);
  ]]
end

if OPENSSL_10 or BORINGSSL_110 then
  -- in openssl 1.0.x some getters are direct accessor to struct members (defiend by macros)
  ffi.cdef [[
    // crypto/x509/x509.h
    typedef struct X509_val_st {
      ASN1_TIME *notBefore;
      ASN1_TIME *notAfter;
    } X509_VAL;

    typedef struct X509_algor_st {
      ASN1_OBJECT *algorithm;
      ASN1_TYPE *parameter;
    } X509_ALGOR;

    // Note: this struct is trimmed
    typedef struct x509_cinf_st {
      /*ASN1_INTEGER*/ void *version;
      /*ASN1_INTEGER*/ void *serialNumber;
      X509_ALGOR *signature;
      X509_NAME *issuer;
      X509_VAL *validity;
      X509_NAME *subject;
      /*X509_PUBKEY*/ void *key;
      /*ASN1_BIT_STRING*/ void *issuerUID; /* [ 1 ] optional in v2 */
      /*ASN1_BIT_STRING*/ void *subjectUID; /* [ 2 ] optional in v2 */
      /*STACK_OF(X509_EXTENSION)*/ OPENSSL_STACK *extensions; /* [ 3 ] optional in v3 */
      // trimmed
      // ASN1_ENCODING enc;
    } X509_CINF;
    // Note: this struct is trimmed
    struct x509_st {
      X509_CINF *cert_info;
      // trimmed
    } X509;

    int X509_set_notBefore(X509 *x, const ASN1_TIME *tm);
    int X509_set_notAfter(X509 *x, const ASN1_TIME *tm);
    ASN1_INTEGER *X509_get_serialNumber(X509 *x);
  ]]
end

if BORINGSSL_110 then
  ffi.cdef [[
    ASN1_TIME *X509_get_notBefore(const X509 *x);
    ASN1_TIME *X509_get_notAfter(const X509 *x);
  ]]
end
