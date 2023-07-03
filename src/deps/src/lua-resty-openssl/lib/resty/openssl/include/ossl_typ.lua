local ffi = require "ffi"

ffi.cdef(
[[
  typedef struct rsa_st RSA;
  typedef struct evp_pkey_st EVP_PKEY;
  typedef struct bignum_st BIGNUM;
  typedef struct bn_gencb_st BN_GENCB;
  typedef struct bignum_ctx BN_CTX;
  typedef struct bio_st BIO;
  typedef struct evp_cipher_st EVP_CIPHER;
  typedef struct evp_md_ctx_st EVP_MD_CTX;
  typedef struct evp_pkey_ctx_st EVP_PKEY_CTX;
  typedef struct evp_md_st EVP_MD;
  typedef struct evp_pkey_asn1_method_st EVP_PKEY_ASN1_METHOD;
  typedef struct evp_cipher_ctx_st EVP_CIPHER_CTX;
  typedef struct engine_st ENGINE;
  typedef struct x509_st X509;
  typedef struct x509_attributes_st X509_ATTRIBUTE;
  typedef struct X509_extension_st X509_EXTENSION;
  typedef struct X509_name_st X509_NAME;
  typedef struct X509_name_entry_st X509_NAME_ENTRY;
  typedef struct X509_req_st X509_REQ;
  typedef struct X509_crl_st X509_CRL;
  typedef struct x509_store_st X509_STORE;
  typedef struct x509_store_ctx_st X509_STORE_CTX;
  typedef struct x509_purpose_st X509_PURPOSE;
  typedef struct v3_ext_ctx X509V3_CTX;
  typedef struct asn1_string_st ASN1_INTEGER;
  typedef struct asn1_string_st ASN1_ENUMERATED;
  typedef struct asn1_string_st ASN1_BIT_STRING;
  typedef struct asn1_string_st ASN1_OCTET_STRING;
  typedef struct asn1_string_st ASN1_PRINTABLESTRING;
  typedef struct asn1_string_st ASN1_T61STRING;
  typedef struct asn1_string_st ASN1_IA5STRING;
  typedef struct asn1_string_st ASN1_GENERALSTRING;
  typedef struct asn1_string_st ASN1_UNIVERSALSTRING;
  typedef struct asn1_string_st ASN1_BMPSTRING;
  typedef struct asn1_string_st ASN1_UTCTIME;
  typedef struct asn1_string_st ASN1_TIME;
  typedef struct asn1_string_st ASN1_GENERALIZEDTIME;
  typedef struct asn1_string_st ASN1_VISIBLESTRING;
  typedef struct asn1_string_st ASN1_UTF8STRING;
  typedef struct asn1_string_st ASN1_STRING;
  typedef struct asn1_object_st ASN1_OBJECT;
  typedef struct conf_st CONF;
  typedef struct conf_method_st CONF_METHOD;
  typedef int ASN1_BOOLEAN;
  typedef int ASN1_NULL;
  typedef struct ec_key_st EC_KEY;
  typedef struct ec_method_st EC_METHOD;
  typedef struct ec_point_st EC_POINT;
  typedef struct ec_group_st EC_GROUP;
  typedef struct rsa_meth_st RSA_METHOD;
  // typedef struct evp_keymgmt_st EVP_KEYMGMT;
  // typedef struct crypto_ex_data_st CRYPTO_EX_DATA;
  // typedef struct bn_mont_ctx_st BN_MONT_CTX;
  // typedef struct bn_blinding_st BN_BLINDING;
  // crypto.h
  // typedef void CRYPTO_RWLOCK;
  typedef struct hmac_ctx_st HMAC_CTX;
  typedef struct x509_revoked_st X509_REVOKED;
  typedef struct dh_st DH;
  typedef struct PKCS12_st PKCS12;
  typedef struct ssl_st SSL;
  typedef struct ssl_ctx_st SSL_CTX;
  typedef struct evp_kdf_st EVP_KDF;
  typedef struct evp_kdf_ctx_st EVP_KDF_CTX;
  typedef struct ossl_lib_ctx_st OSSL_LIB_CTX;
  typedef struct ECDSA_SIG_st ECDSA_SIG;
]])

