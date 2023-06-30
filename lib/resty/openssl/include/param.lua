local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"

ffi.cdef [[
  typedef struct ossl_param_st {
    const char *key;             /* the name of the parameter */
    unsigned int data_type;      /* declare what kind of content is in buffer */
    void *data;                  /* value being passed in or out */
    size_t data_size;            /* data size */
    size_t return_size;          /* returned content size */
  } OSSL_PARAM;

  OSSL_PARAM OSSL_PARAM_construct_int(const char *key, int *buf);
  OSSL_PARAM OSSL_PARAM_construct_uint(const char *key, unsigned int *buf);
  OSSL_PARAM OSSL_PARAM_construct_BN(const char *key, unsigned char *buf,
                                    size_t bsize);
  OSSL_PARAM OSSL_PARAM_construct_double(const char *key, double *buf);
  OSSL_PARAM OSSL_PARAM_construct_utf8_string(const char *key, char *buf,
                                              size_t bsize);
  OSSL_PARAM OSSL_PARAM_construct_octet_string(const char *key, void *buf,
                                                size_t bsize);
  OSSL_PARAM OSSL_PARAM_construct_utf8_ptr(const char *key, char **buf,
                                            size_t bsize);
  OSSL_PARAM OSSL_PARAM_construct_octet_ptr(const char *key, void **buf,
                                            size_t bsize);
  OSSL_PARAM OSSL_PARAM_construct_end(void);

  int OSSL_PARAM_get_int32(const OSSL_PARAM *p, int32_t *val);
  int OSSL_PARAM_get_uint32(const OSSL_PARAM *p, uint32_t *val);
  int OSSL_PARAM_get_int64(const OSSL_PARAM *p, int64_t *val);
  int OSSL_PARAM_get_uint64(const OSSL_PARAM *p, uint64_t *val);
  // int OSSL_PARAM_get_size_t(const OSSL_PARAM *p, size_t *val);
  // int OSSL_PARAM_get_time_t(const OSSL_PARAM *p, time_t *val);

  int OSSL_PARAM_set_int(OSSL_PARAM *p, int val);
  int OSSL_PARAM_set_uint(OSSL_PARAM *p, unsigned int val);
  int OSSL_PARAM_set_long(OSSL_PARAM *p, long int val);
  int OSSL_PARAM_set_ulong(OSSL_PARAM *p, unsigned long int val);
  int OSSL_PARAM_set_int32(OSSL_PARAM *p, int32_t val);
  int OSSL_PARAM_set_uint32(OSSL_PARAM *p, uint32_t val);
  int OSSL_PARAM_set_int64(OSSL_PARAM *p, int64_t val);
  int OSSL_PARAM_set_uint64(OSSL_PARAM *p, uint64_t val);
  // int OSSL_PARAM_set_size_t(OSSL_PARAM *p, size_t val);
  // int OSSL_PARAM_set_time_t(OSSL_PARAM *p, time_t val);

  int OSSL_PARAM_get_double(const OSSL_PARAM *p, double *val);
  int OSSL_PARAM_set_double(OSSL_PARAM *p, double val);

  int OSSL_PARAM_get_BN(const OSSL_PARAM *p, BIGNUM **val);
  int OSSL_PARAM_set_BN(OSSL_PARAM *p, const BIGNUM *val);

  int OSSL_PARAM_get_utf8_string(const OSSL_PARAM *p, char **val, size_t max_len);
  int OSSL_PARAM_set_utf8_string(OSSL_PARAM *p, const char *val);

  int OSSL_PARAM_get_octet_string(const OSSL_PARAM *p, void **val, size_t max_len,
                                  size_t *used_len);
  int OSSL_PARAM_set_octet_string(OSSL_PARAM *p, const void *val, size_t len);

  int OSSL_PARAM_get_utf8_ptr(const OSSL_PARAM *p, const char **val);
  int OSSL_PARAM_set_utf8_ptr(OSSL_PARAM *p, const char *val);

  int OSSL_PARAM_get_octet_ptr(const OSSL_PARAM *p, const void **val,
                              size_t *used_len);
  int OSSL_PARAM_set_octet_ptr(OSSL_PARAM *p, const void *val,
                              size_t used_len);

  int OSSL_PARAM_get_utf8_string_ptr(const OSSL_PARAM *p, const char **val);
  int OSSL_PARAM_get_octet_string_ptr(const OSSL_PARAM *p, const void **val,
                                      size_t *used_len);
]]
