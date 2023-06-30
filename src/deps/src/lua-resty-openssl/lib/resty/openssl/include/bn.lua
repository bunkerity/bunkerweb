local ffi = require "ffi"

require "resty.openssl.include.ossl_typ"
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X

local BN_ULONG
if ffi.abi('64bit') then
  BN_ULONG = 'unsigned long long'
else -- 32bit
  BN_ULONG = 'unsigned int'
end

ffi.cdef(
[[
  BIGNUM *BN_new(void);
  void BN_free(BIGNUM *a);

  BN_CTX *BN_CTX_new(void);
  void BN_CTX_init(BN_CTX *c);
  void BN_CTX_free(BN_CTX *c);

  BIGNUM *BN_dup(const BIGNUM *a);
  int BN_add_word(BIGNUM *a, ]] .. BN_ULONG ..[[ w);
  int BN_set_word(BIGNUM *a, ]] .. BN_ULONG ..[[ w);
  ]] .. BN_ULONG ..[[ BN_get_word(BIGNUM *a);
  int BN_num_bits(const BIGNUM *a);
  BIGNUM *BN_bin2bn(const unsigned char *s, int len, BIGNUM *ret);
  int BN_bn2binpad(const BIGNUM *a, unsigned char *to, int tolen);

  int BN_hex2bn(BIGNUM **a, const char *str);
  int BN_dec2bn(BIGNUM **a, const char *str);
  int BN_bn2bin(const BIGNUM *a, unsigned char *to);
  char *BN_bn2hex(const BIGNUM *a);
  char *BN_bn2dec(const BIGNUM *a);

  void BN_set_negative(BIGNUM *a, int n);
  int  BN_is_negative(const BIGNUM *a);

  int BN_add(BIGNUM *r, const BIGNUM *a, const BIGNUM *b);
  int BN_sub(BIGNUM *r, const BIGNUM *a, const BIGNUM *b);
  int BN_mul(BIGNUM *r, BIGNUM *a, BIGNUM *b, BN_CTX *ctx);
  int BN_sqr(BIGNUM *r, BIGNUM *a, BN_CTX *ctx);
  int BN_div(BIGNUM *dv, BIGNUM *rem, const BIGNUM *a, const BIGNUM *d,
             BN_CTX *ctx);
  int BN_mod_add(BIGNUM *ret, BIGNUM *a, BIGNUM *b, const BIGNUM *m,
    BN_CTX *ctx);
  int BN_mod_sub(BIGNUM *ret, BIGNUM *a, BIGNUM *b, const BIGNUM *m,
    BN_CTX *ctx);
  int BN_mod_mul(BIGNUM *ret, BIGNUM *a, BIGNUM *b, const BIGNUM *m,
    BN_CTX *ctx);
  int BN_mod_sqr(BIGNUM *ret, BIGNUM *a, const BIGNUM *m, BN_CTX *ctx);
  int BN_exp(BIGNUM *r, BIGNUM *a, BIGNUM *p, BN_CTX *ctx);
  int BN_mod_exp(BIGNUM *r, BIGNUM *a, const BIGNUM *p,
    const BIGNUM *m, BN_CTX *ctx);
  int BN_gcd(BIGNUM *r, BIGNUM *a, BIGNUM *b, BN_CTX *ctx);

  int BN_lshift(BIGNUM *r, const BIGNUM *a, int n);
  int BN_rshift(BIGNUM *r, BIGNUM *a, int n);

  int BN_cmp(BIGNUM *a, BIGNUM *b);
  int BN_ucmp(BIGNUM *a, BIGNUM *b);

  // openssl >= 1.1 only
  int BN_is_zero(BIGNUM *a);
  int BN_is_one(BIGNUM *a);
  int BN_is_word(BIGNUM *a, ]] .. BN_ULONG ..[[ w);
  int BN_is_odd(BIGNUM *a);

  int BN_is_prime_ex(const BIGNUM *p,int nchecks, BN_CTX *ctx, BN_GENCB *cb);
  int BN_generate_prime_ex(BIGNUM *ret,int bits,int safe, const BIGNUM *add,
                            const BIGNUM *rem, BN_GENCB *cb);
]]
)

if OPENSSL_3X then
  ffi.cdef [[
    int BN_check_prime(const BIGNUM *p, BN_CTX *ctx, BN_GENCB *cb);
  ]]
end