local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"

ffi.cdef [[
  /** Enum for the point conversion form as defined in X9.62 (ECDSA)
  *  for the encoding of a elliptic curve point (x,y) */
  typedef enum {
    /** the point is encoded as z||x, where the octet z specifies
    *  which solution of the quadratic equation y is  */
    POINT_CONVERSION_COMPRESSED = 2,
    /** the point is encoded as z||x||y, where z is the octet 0x04  */
    POINT_CONVERSION_UNCOMPRESSED = 4,
    /** the point is encoded as z||x||y, where the octet z specifies
    *  which solution of the quadratic equation y is  */
    POINT_CONVERSION_HYBRID = 6
  } point_conversion_form_t;

  EC_KEY *EC_KEY_new(void);
  void EC_KEY_free(EC_KEY *key);

  EC_GROUP *EC_GROUP_new_by_curve_name(int nid);
  void EC_GROUP_set_asn1_flag(EC_GROUP *group, int flag);
  void EC_GROUP_set_point_conversion_form(EC_GROUP *group,
    point_conversion_form_t form);
  void EC_GROUP_set_curve_name(EC_GROUP *group, int nid);
  int EC_GROUP_get_curve_name(const EC_GROUP *group);


  void EC_GROUP_free(EC_GROUP *group);

  BIGNUM *EC_POINT_point2bn(const EC_GROUP *, const EC_POINT *,
    point_conversion_form_t form, BIGNUM *, BN_CTX *);
  // for BoringSSL
  size_t EC_POINT_point2oct(const EC_GROUP *group, const EC_POINT *p,
        point_conversion_form_t form,
        unsigned char *buf, size_t len, BN_CTX *ctx);
  // OpenSSL < 1.1.1
  int EC_POINT_get_affine_coordinates_GFp(const EC_GROUP *group,
    const EC_POINT *p,
    BIGNUM *x, BIGNUM *y, BN_CTX *ctx);
  // OpenSSL >= 1.1.1
  int EC_POINT_get_affine_coordinates(const EC_GROUP *group, const EC_POINT *p,
    BIGNUM *x, BIGNUM *y, BN_CTX *ctx);
  EC_POINT *EC_POINT_bn2point(const EC_GROUP *group, const BIGNUM *bn,
    EC_POINT *p, BN_CTX *ctx);

  point_conversion_form_t EC_KEY_get_conv_form(const EC_KEY *key);

  const BIGNUM *EC_KEY_get0_private_key(const EC_KEY *key);
  int EC_KEY_set_private_key(EC_KEY *key, const BIGNUM *prv);

  const EC_POINT *EC_KEY_get0_public_key(const EC_KEY *key);
  int EC_KEY_set_public_key(EC_KEY *key, const EC_POINT *pub);
  int EC_KEY_set_public_key_affine_coordinates(EC_KEY *key, BIGNUM *x, BIGNUM *y);

  const EC_GROUP *EC_KEY_get0_group(const EC_KEY *key);
  int EC_KEY_set_group(EC_KEY *key, const EC_GROUP *group);
]]
