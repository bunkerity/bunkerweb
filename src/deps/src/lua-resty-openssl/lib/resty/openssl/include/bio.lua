local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"

ffi.cdef [[
  typedef struct bio_method_st BIO_METHOD;
  long BIO_ctrl(BIO *bp, int cmd, long larg, void *parg);
  BIO *BIO_new_mem_buf(const void *buf, int len);
  BIO *BIO_new(const BIO_METHOD *type);
  int BIO_free(BIO *a);
  const BIO_METHOD *BIO_s_mem(void);
  int BIO_read(BIO *b, void *data, int dlen);
]]
