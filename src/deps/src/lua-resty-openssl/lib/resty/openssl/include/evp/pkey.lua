local ffi = require "ffi"
local C = ffi.C

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.evp.md"
local evp = require("resty.openssl.include.evp")
local OPENSSL_10 = require("resty.openssl.version").OPENSSL_10
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X
local BORINGSSL = require("resty.openssl.version").BORINGSSL

ffi.cdef [[
  EVP_PKEY *EVP_PKEY_new(void);
  void EVP_PKEY_free(EVP_PKEY *pkey);

  RSA *EVP_PKEY_get0_RSA(EVP_PKEY *pkey);
  EC_KEY *EVP_PKEY_get0_EC_KEY(EVP_PKEY *pkey);
  DH *EVP_PKEY_get0_DH(EVP_PKEY *pkey);

  int EVP_PKEY_assign(EVP_PKEY *pkey, int type, void *key);
  // openssl < 3.0
  int EVP_PKEY_base_id(const EVP_PKEY *pkey);
  int EVP_PKEY_size(const EVP_PKEY *pkey);

  EVP_PKEY_CTX *EVP_PKEY_CTX_new(EVP_PKEY *pkey, ENGINE *e);
  EVP_PKEY_CTX *EVP_PKEY_CTX_new_id(int id, ENGINE *e);
  void EVP_PKEY_CTX_free(EVP_PKEY_CTX *ctx);
  int EVP_PKEY_CTX_ctrl(EVP_PKEY_CTX *ctx, int keytype, int optype,
                      int cmd, int p1, void *p2);
  // TODO replace EVP_PKEY_CTX_ctrl with EVP_PKEY_CTX_ctrl_str to reduce
  // some hardcoded macros
  int EVP_PKEY_CTX_ctrl_str(EVP_PKEY_CTX *ctx, const char *type,
                      const char *value);
  int EVP_PKEY_encrypt_init(EVP_PKEY_CTX *ctx);
  int EVP_PKEY_encrypt(EVP_PKEY_CTX *ctx,
                        unsigned char *out, size_t *outlen,
                        const unsigned char *in, size_t inlen);
  int EVP_PKEY_decrypt_init(EVP_PKEY_CTX *ctx);
  int EVP_PKEY_decrypt(EVP_PKEY_CTX *ctx,
                        unsigned char *out, size_t *outlen,
                        const unsigned char *in, size_t inlen);

  int EVP_PKEY_sign_init(EVP_PKEY_CTX *ctx);
  int EVP_PKEY_sign(EVP_PKEY_CTX *ctx,
                    unsigned char *sig, size_t *siglen,
                    const unsigned char *tbs, size_t tbslen);
  int EVP_PKEY_verify_recover_init(EVP_PKEY_CTX *ctx);
  int EVP_PKEY_verify_recover(EVP_PKEY_CTX *ctx,
                              unsigned char *rout, size_t *routlen,
                              const unsigned char *sig, size_t siglen);

  EVP_PKEY *EVP_PKEY_new_raw_private_key(int type, ENGINE *e,
                        const unsigned char *key, size_t keylen);
  EVP_PKEY *EVP_PKEY_new_raw_public_key(int type, ENGINE *e,
                       const unsigned char *key, size_t keylen);

  int EVP_PKEY_get_raw_private_key(const EVP_PKEY *pkey, unsigned char *priv,
                       size_t *len);
  int EVP_PKEY_get_raw_public_key(const EVP_PKEY *pkey, unsigned char *pub,
                      size_t *len);

  int EVP_SignFinal(EVP_MD_CTX *ctx, unsigned char *md, unsigned int *s,
  EVP_PKEY *pkey);
  int EVP_VerifyFinal(EVP_MD_CTX *ctx, const unsigned char *sigbuf,
                            unsigned int siglen, EVP_PKEY *pkey);

  int EVP_DigestSignInit(EVP_MD_CTX *ctx, EVP_PKEY_CTX **pctx,
                          const EVP_MD *type, ENGINE *e, EVP_PKEY *pkey);
  int EVP_DigestSign(EVP_MD_CTX *ctx, unsigned char *sigret,
                      size_t *siglen, const unsigned char *tbs,
                      size_t tbslen);
  int EVP_DigestVerifyInit(EVP_MD_CTX *ctx, EVP_PKEY_CTX **pctx,
                          const EVP_MD *type, ENGINE *e, EVP_PKEY *pkey);
  int EVP_DigestVerify(EVP_MD_CTX *ctx, const unsigned char *sigret,
                      size_t siglen, const unsigned char *tbs, size_t tbslen);

  int EVP_PKEY_get_default_digest_nid(EVP_PKEY *pkey, int *pnid);

  int EVP_PKEY_derive_init(EVP_PKEY_CTX *ctx);
  int EVP_PKEY_derive_set_peer(EVP_PKEY_CTX *ctx, EVP_PKEY *peer);
  int EVP_PKEY_derive(EVP_PKEY_CTX *ctx, unsigned char *key, size_t *keylen);

  int EVP_PKEY_keygen_init(EVP_PKEY_CTX *ctx);
  int EVP_PKEY_keygen(EVP_PKEY_CTX *ctx, EVP_PKEY **ppkey);
  int EVP_PKEY_paramgen_init(EVP_PKEY_CTX *ctx);
  int EVP_PKEY_paramgen(EVP_PKEY_CTX *ctx, EVP_PKEY **ppkey);
]]

if OPENSSL_3X then
  require "resty.openssl.include.provider"

  ffi.cdef [[
    int EVP_PKEY_CTX_set_rsa_padding(EVP_PKEY_CTX *ctx, int pad_mode);

    int EVP_PKEY_get_base_id(const EVP_PKEY *pkey);
    int EVP_PKEY_get_size(const EVP_PKEY *pkey);

    const OSSL_PROVIDER *EVP_PKEY_get0_provider(const EVP_PKEY *key);
    const OSSL_PROVIDER *EVP_PKEY_CTX_get0_provider(const EVP_PKEY_CTX *ctx);

    const OSSL_PARAM *EVP_PKEY_settable_params(const EVP_PKEY *pkey);
    int EVP_PKEY_set_params(EVP_PKEY *pkey, OSSL_PARAM params[]);
    int EVP_PKEY_get_params(EVP_PKEY *ctx, OSSL_PARAM params[]);
    const OSSL_PARAM *EVP_PKEY_gettable_params(EVP_PKEY *ctx);
  ]]
end

if OPENSSL_10 then
  ffi.cdef [[
    // crypto/evp/evp.h
    // only needed for openssl 1.0.x where getters are not available
    // needed to get key to extract parameters
    // Note: this struct is trimmed
    struct evp_pkey_st {
      int type;
      int save_type;
      const EVP_PKEY_ASN1_METHOD *ameth;
      ENGINE *engine;
      ENGINE *pmeth_engine;
      union {
          void *ptr;
          struct rsa_st *rsa;
          struct dsa_st *dsa;
          struct dh_st *dh;
          struct ec_key_st *ec;
      } pkey;
      // trimmed

      // CRYPTO_REF_COUNT references;
      // CRYPTO_RWLOCK *lock;
      // STACK_OF(X509_ATTRIBUTE) *attributes;
      // int save_parameters;

      // struct {
      //     EVP_KEYMGMT *keymgmt;
      //     void *provkey;
      // } pkeys[10];
      // size_t dirty_cnt_copy;
    };
  ]]
end

local _M = {}

if OPENSSL_3X or BORINGSSL then
  ffi.cdef [[
    int EVP_PKEY_CTX_set_ec_paramgen_curve_nid(EVP_PKEY_CTX *ctx, int nid);
    int EVP_PKEY_CTX_set_ec_param_enc(EVP_PKEY_CTX *ctx, int param_enc);

    int EVP_PKEY_CTX_set_rsa_keygen_bits(EVP_PKEY_CTX *ctx, int mbits);
    int EVP_PKEY_CTX_set_rsa_keygen_pubexp(EVP_PKEY_CTX *ctx, BIGNUM *pubexp);

    int EVP_PKEY_CTX_set_rsa_padding(EVP_PKEY_CTX *ctx, int pad);
    int EVP_PKEY_CTX_set_rsa_pss_saltlen(EVP_PKEY_CTX *ctx, int len);

    int EVP_PKEY_CTX_set_dh_paramgen_prime_len(EVP_PKEY_CTX *ctx, int pbits);
  ]]
  _M.EVP_PKEY_CTX_set_ec_paramgen_curve_nid = function(pctx, nid)
    return C.EVP_PKEY_CTX_set_ec_paramgen_curve_nid(pctx, nid)
  end
  _M.EVP_PKEY_CTX_set_ec_param_enc = function(pctx, param_enc)
    return C.EVP_PKEY_CTX_set_ec_param_enc(pctx, param_enc)
  end

  _M.EVP_PKEY_CTX_set_rsa_keygen_bits = function(pctx, mbits)
    return C.EVP_PKEY_CTX_set_rsa_keygen_bits(pctx, mbits)
  end
  _M.EVP_PKEY_CTX_set_rsa_keygen_pubexp = function(pctx, pubexp)
    return C.EVP_PKEY_CTX_set_rsa_keygen_pubexp(pctx, pubexp)
  end

  _M.EVP_PKEY_CTX_set_rsa_padding = function(pctx, pad)
    return C.EVP_PKEY_CTX_set_rsa_padding(pctx, pad)
  end
  _M.EVP_PKEY_CTX_set_rsa_pss_saltlen = function(pctx, len)
    return C.EVP_PKEY_CTX_set_rsa_pss_saltlen(pctx, len)
  end
  _M.EVP_PKEY_CTX_set_dh_paramgen_prime_len = function(pctx, pbits)
    return C.EVP_PKEY_CTX_set_dh_paramgen_prime_len(pctx, pbits)
  end

else
  _M.EVP_PKEY_CTX_set_ec_paramgen_curve_nid = function(pctx, nid)
    return C.EVP_PKEY_CTX_ctrl(pctx,
                                evp.EVP_PKEY_EC,
                                evp.EVP_PKEY_OP_PARAMGEN + evp.EVP_PKEY_OP_KEYGEN,
                                evp.EVP_PKEY_CTRL_EC_PARAMGEN_CURVE_NID,
                                nid, nil)
  end
  _M.EVP_PKEY_CTX_set_ec_param_enc = function(pctx, param_enc)
    return C.EVP_PKEY_CTX_ctrl(pctx,
                                evp.EVP_PKEY_EC,
                                evp.EVP_PKEY_OP_PARAMGEN + evp.EVP_PKEY_OP_KEYGEN,
                                evp.EVP_PKEY_CTRL_EC_PARAM_ENC,
                                param_enc, nil)
  end

  _M.EVP_PKEY_CTX_set_rsa_keygen_bits = function(pctx, mbits)
    return C.EVP_PKEY_CTX_ctrl(pctx,
                                evp.EVP_PKEY_RSA,
                                evp.EVP_PKEY_OP_KEYGEN,
                                evp.EVP_PKEY_CTRL_RSA_KEYGEN_BITS,
                                mbits, nil)
  end
  _M.EVP_PKEY_CTX_set_rsa_keygen_pubexp = function(pctx, pubexp)
    return C.EVP_PKEY_CTX_ctrl(pctx,
                                evp.EVP_PKEY_RSA, evp.EVP_PKEY_OP_KEYGEN,
                                evp.EVP_PKEY_CTRL_RSA_KEYGEN_PUBEXP,
                                0, pubexp)
  end

  _M.EVP_PKEY_CTX_set_rsa_padding = function(pctx, pad)
    return C.EVP_PKEY_CTX_ctrl(pctx,
                                evp.EVP_PKEY_RSA,
                                -1,
                                evp.EVP_PKEY_CTRL_RSA_PADDING,
                                pad, nil)
  end
  _M.EVP_PKEY_CTX_set_rsa_pss_saltlen = function(pctx, len)
    return C.EVP_PKEY_CTX_ctrl(pctx,
                                evp.EVP_PKEY_RSA,
                                evp.EVP_PKEY_OP_SIGN + evp.EVP_PKEY_OP_VERIFY,
                                evp.EVP_PKEY_CTRL_RSA_PSS_SALTLEN,
                                len, nil)
  end

  _M.EVP_PKEY_CTX_set_dh_paramgen_prime_len = function(pctx, pbits)
    return C.EVP_PKEY_CTX_ctrl(pctx,
            evp.EVP_PKEY_DH, evp.EVP_PKEY_OP_PARAMGEN,
            evp.EVP_PKEY_CTRL_DH_PARAMGEN_PRIME_LEN,
            pbits, nil)
  end
end

return _M