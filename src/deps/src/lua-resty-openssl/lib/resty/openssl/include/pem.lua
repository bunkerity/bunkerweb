
local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"

ffi.cdef [[
  // all pem_password_cb* has been modified to pem_password_cb to avoid a table overflow issue
  typedef int (*pem_password_cb)(char *buf, int size, int rwflag, void *userdata);
  EVP_PKEY *PEM_read_bio_PrivateKey(BIO *bp, EVP_PKEY **x,
  // the following signature has been modified to avoid ffi.cast
    pem_password_cb cb, const char *u);
  //  pem_password_cb *cb, void *u);
  EVP_PKEY *PEM_read_bio_PUBKEY(BIO *bp, EVP_PKEY **x,
  // the following signature has been modified to avoid ffi.cast
    pem_password_cb cb, const char *u);
  //  pem_password_cb *cb, void *u);
  int PEM_write_bio_PrivateKey(BIO *bp, EVP_PKEY *x, const EVP_CIPHER *enc,
    unsigned char *kstr, int klen,
    pem_password_cb *cb, void *u);
  int PEM_write_bio_PUBKEY(BIO *bp, EVP_PKEY *x);

  RSA *PEM_read_bio_RSAPrivateKey(BIO *bp, RSA **x,
  // the following signature has been modified to avoid ffi.cast
    pem_password_cb cb, const char *u);
  //  pem_password_cb *cb, void *u);
  RSA *PEM_read_bio_RSAPublicKey(BIO *bp, RSA **x,
  // the following signature has been modified to avoid ffi.cast
    pem_password_cb cb, const char *u);
  //  pem_password_cb *cb, void *u);
  int PEM_write_bio_RSAPrivateKey(BIO *bp, RSA *x, const EVP_CIPHER *enc,
    unsigned char *kstr, int klen,
    pem_password_cb *cb, void *u);
  int PEM_write_bio_RSAPublicKey(BIO *bp, RSA *x);

  X509_REQ *PEM_read_bio_X509_REQ(BIO *bp, X509_REQ **x, pem_password_cb cb, void *u);
  int PEM_write_bio_X509_REQ(BIO *bp, X509_REQ *x);

  X509_CRL *PEM_read_bio_X509_CRL(BIO *bp, X509_CRL **x, pem_password_cb cb, void *u);
  int PEM_write_bio_X509_CRL(BIO *bp, X509_CRL *x);

  X509 *PEM_read_bio_X509(BIO *bp, X509 **x, pem_password_cb cb, void *u);
  int PEM_write_bio_X509(BIO *bp, X509 *x);

  DH *PEM_read_bio_DHparams(BIO *bp, DH **x, pem_password_cb cb, void *u);
  int PEM_write_bio_DHparams(BIO *bp, DH *x);

  EC_GROUP *PEM_read_bio_ECPKParameters(BIO *bp, EC_GROUP **x, pem_password_cb cb, void *u);
  int PEM_write_bio_ECPKParameters(BIO *bp, const EC_GROUP *x);

]]
