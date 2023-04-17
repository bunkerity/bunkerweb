local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.stack"
local asn1_macro = require "resty.openssl.include.asn1"

ffi.cdef [[
  // STACK_OF(OPENSSL_STRING)
  OPENSSL_STACK *X509_get1_ocsp(X509 *x);
  void X509_email_free(OPENSSL_STACK *sk);
  void X509V3_set_nconf(X509V3_CTX *ctx, CONF *conf);

  typedef struct EDIPartyName_st EDIPARTYNAME;

  typedef struct otherName_st OTHERNAME;

  typedef struct GENERAL_NAME_st {
      int type;
      union {
        char *ptr;
        OTHERNAME *otherName;   /* otherName */
        ASN1_IA5STRING *rfc822Name;
        ASN1_IA5STRING *dNSName;
        ASN1_TYPE *x400Address;
        X509_NAME *directoryName;
        EDIPARTYNAME *ediPartyName;
        ASN1_IA5STRING *uniformResourceIdentifier;
        ASN1_OCTET_STRING *iPAddress;
        ASN1_OBJECT *registeredID;
        /* Old names */
        ASN1_OCTET_STRING *ip;  /* iPAddress */
        X509_NAME *dirn;        /* dirn */
        ASN1_IA5STRING *ia5;    /* rfc822Name, dNSName,
                                    * uniformResourceIdentifier */
        ASN1_OBJECT *rid;       /* registeredID */
        ASN1_TYPE *other;       /* x400Address */
      } d;
    } GENERAL_NAME;

  // STACK_OF(GENERAL_NAME)
  typedef struct stack_st GENERAL_NAMES;

  // STACK_OF(X509_EXTENSION)
  int X509V3_add1_i2d(OPENSSL_STACK **x, int nid, void *value,
                    int crit, unsigned long flags);
  void *X509V3_EXT_d2i(X509_EXTENSION *ext);
  X509_EXTENSION *X509V3_EXT_i2d(int ext_nid, int crit, void *ext_struc);
  int X509V3_EXT_print(BIO *out, X509_EXTENSION *ext, unsigned long flag,
                     int indent);

  int X509_add1_ext_i2d(X509 *x, int nid, void *value, int crit,
                    unsigned long flags);
  // although the struct has plural form, it's not a stack
  typedef struct BASIC_CONSTRAINTS_st {
    int ca;
    ASN1_INTEGER *pathlen;
  } BASIC_CONSTRAINTS;

  void X509V3_set_ctx(X509V3_CTX *ctx, X509 *issuer, X509 *subject,
    X509_REQ *req, X509_CRL *crl, int flags);

  X509_EXTENSION *X509V3_EXT_nconf_nid(CONF *conf, X509V3_CTX *ctx, int ext_nid,
                                     const char *value);
  X509_EXTENSION *X509V3_EXT_nconf(CONF *conf, X509V3_CTX *ctx, const char *name,
                                 const char *value);
  int X509V3_EXT_print(BIO *out, X509_EXTENSION *ext, unsigned long flag,
    int indent);

  void *X509V3_get_d2i(const OPENSSL_STACK *x, int nid, int *crit, int *idx);

  int X509v3_get_ext_by_NID(const OPENSSL_STACK *x,
                           int nid, int lastpos);

   X509_EXTENSION *X509v3_get_ext(const OPENSSL_STACK *x, int loc);

  // STACK_OF(ACCESS_DESCRIPTION)
  typedef struct stack_st AUTHORITY_INFO_ACCESS;

  typedef struct ACCESS_DESCRIPTION_st {
    ASN1_OBJECT *method;
    GENERAL_NAME *location;
  } ACCESS_DESCRIPTION;

  typedef struct DIST_POINT_NAME_st {
    int type;
    union {
        GENERAL_NAMES *fullname;
        // STACK_OF(X509_NAME_ENTRY)
        OPENSSL_STACK *relativename;
    } name;
  /* If relativename then this contains the full distribution point name */
      X509_NAME *dpname;
  } DIST_POINT_NAME;

  typedef struct DIST_POINT_st {
    DIST_POINT_NAME *distpoint;
    ASN1_BIT_STRING *reasons;
    GENERAL_NAMES *CRLissuer;
    int dp_reasons;
  } DIST_POINT;

]]

asn1_macro.declare_asn1_functions("GENERAL_NAME")
asn1_macro.declare_asn1_functions("BASIC_CONSTRAINTS")
asn1_macro.declare_asn1_functions("AUTHORITY_INFO_ACCESS") -- OCSP responder and CA
asn1_macro.declare_asn1_functions("ACCESS_DESCRIPTION")
asn1_macro.declare_asn1_functions("DIST_POINT") -- CRL distribution points
