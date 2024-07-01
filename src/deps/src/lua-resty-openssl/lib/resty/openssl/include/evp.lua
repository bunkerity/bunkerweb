local ffi = require "ffi"
local C = ffi.C
local bit = require("bit")

require "resty.openssl.include.ossl_typ"
require "resty.openssl.include.err"
require "resty.openssl.include.objects"
local OPENSSL_3X = require("resty.openssl.version").OPENSSL_3X

ffi.cdef [[
  /* KDF */
  int PKCS5_PBKDF2_HMAC(const char *pass, int passlen,
    const unsigned char *salt, int saltlen, int iter,
    const EVP_MD *digest, int keylen, unsigned char *out);

  int EVP_PBE_scrypt(const char *pass, size_t passlen,
    const unsigned char *salt, size_t saltlen,
    uint64_t N, uint64_t r, uint64_t p, uint64_t maxmem,
    unsigned char *key, size_t keylen);
]]

if OPENSSL_3X then
  require "resty.openssl.include.provider"

  ffi.cdef [[
    int EVP_set_default_properties(OSSL_LIB_CTX *libctx, const char *propq);
    int EVP_default_properties_enable_fips(OSSL_LIB_CTX *libctx, int enable);
    int EVP_default_properties_is_fips_enabled(OSSL_LIB_CTX *libctx);

    // const OSSL_PROVIDER *EVP_RAND_get0_provider(const EVP_RAND *rand);
    // EVP_RAND *EVP_RAND_fetch(OSSL_LIB_CTX *libctx, const char *algorithm,
    //                     const char *properties);
  ]]
end

local EVP_PKEY_ALG_CTRL = 0x1000

local _M = {
  EVP_PKEY_RSA = C.OBJ_txt2nid("rsaEncryption"),
  EVP_PKEY_DH = C.OBJ_txt2nid("dhKeyAgreement"),
  EVP_PKEY_EC = C.OBJ_txt2nid("id-ecPublicKey"),
  EVP_PKEY_X25519 = C.OBJ_txt2nid("X25519"),
  EVP_PKEY_ED25519 = C.OBJ_txt2nid("ED25519"),
  EVP_PKEY_X448 = C.OBJ_txt2nid("X448"),
  EVP_PKEY_ED448 = C.OBJ_txt2nid("ED448"),

  EVP_CTRL_AEAD_SET_IVLEN = 0x9,
  EVP_CTRL_AEAD_GET_TAG = 0x10,
  EVP_CTRL_AEAD_SET_TAG = 0x11,

  -- remove EVP_PKEY_OP_* and EVP_PKEY_CTRL_* after openssl 1.1.1 support is dropped
  EVP_PKEY_OP_PARAMGEN =  not OPENSSL_3X      and bit.lshift(1, 1)  or nil,
  EVP_PKEY_OP_KEYGEN =  not OPENSSL_3X        and bit.lshift(1, 2)  or nil,
  EVP_PKEY_OP_SIGN = not OPENSSL_3X           and bit.lshift(1, 3)  or nil,
  EVP_PKEY_OP_VERIFY = not OPENSSL_3X         and bit.lshift(1, 4)  or nil,
  EVP_PKEY_OP_VERIFYRECOVER = not OPENSSL_3X  and bit.lshift(1, 5)  or nil,
  EVP_PKEY_OP_SIGNCTX = not OPENSSL_3X        and bit.lshift(1, 6)  or nil,
  EVP_PKEY_OP_VERIFYCTX = not OPENSSL_3X      and bit.lshift(1, 7)  or nil,
  EVP_PKEY_OP_ENCRYPT = not OPENSSL_3X        and bit.lshift(1, 8)  or nil,
  EVP_PKEY_OP_DECRYPT = not OPENSSL_3X        and bit.lshift(1, 9)  or nil,
  EVP_PKEY_OP_DERIVE = not OPENSSL_3X         and bit.lshift(1, 10) or nil,

  EVP_PKEY_ALG_CTRL = EVP_PKEY_ALG_CTRL,

  EVP_PKEY_CTRL_DH_PARAMGEN_PRIME_LEN = EVP_PKEY_ALG_CTRL + 1,
  EVP_PKEY_CTRL_EC_PARAMGEN_CURVE_NID = EVP_PKEY_ALG_CTRL + 1,
  EVP_PKEY_CTRL_EC_PARAM_ENC          = EVP_PKEY_ALG_CTRL + 2,
  EVP_PKEY_CTRL_RSA_KEYGEN_BITS       = EVP_PKEY_ALG_CTRL + 3,
  EVP_PKEY_CTRL_RSA_KEYGEN_PUBEXP     = EVP_PKEY_ALG_CTRL + 4,
  EVP_PKEY_CTRL_RSA_PADDING           = EVP_PKEY_ALG_CTRL + 1,
  EVP_PKEY_CTRL_RSA_PSS_SALTLEN       = EVP_PKEY_ALG_CTRL + 2,
  EVP_PKEY_CTRL_RSA_MGF1_MD           = EVP_PKEY_ALG_CTRL + 5,
  EVP_PKEY_CTRL_RSA_OAEP_MD           = EVP_PKEY_ALG_CTRL + 9,

  EVP_PKEY_CTRL_TLS_MD              = EVP_PKEY_ALG_CTRL,
  EVP_PKEY_CTRL_TLS_SECRET          = EVP_PKEY_ALG_CTRL + 1,
  EVP_PKEY_CTRL_TLS_SEED            = EVP_PKEY_ALG_CTRL + 2,
  EVP_PKEY_CTRL_HKDF_MD             = EVP_PKEY_ALG_CTRL + 3,
  EVP_PKEY_CTRL_HKDF_SALT           = EVP_PKEY_ALG_CTRL + 4,
  EVP_PKEY_CTRL_HKDF_KEY            = EVP_PKEY_ALG_CTRL + 5,
  EVP_PKEY_CTRL_HKDF_INFO           = EVP_PKEY_ALG_CTRL + 6,
  EVP_PKEY_CTRL_HKDF_MODE           = EVP_PKEY_ALG_CTRL + 7,
  EVP_PKEY_CTRL_PASS                = EVP_PKEY_ALG_CTRL + 8,
  EVP_PKEY_CTRL_SCRYPT_SALT         = EVP_PKEY_ALG_CTRL + 9,
  EVP_PKEY_CTRL_SCRYPT_N            = EVP_PKEY_ALG_CTRL + 10,
  EVP_PKEY_CTRL_SCRYPT_R            = EVP_PKEY_ALG_CTRL + 11,
  EVP_PKEY_CTRL_SCRYPT_P            = EVP_PKEY_ALG_CTRL + 12,
  EVP_PKEY_CTRL_SCRYPT_MAXMEM_BYTES = EVP_PKEY_ALG_CTRL + 13,
}

if not OPENSSL_3X then
  _M.EVP_PKEY_OP_CRYPT = _M.EVP_PKEY_OP_ENCRYPT + _M.EVP_PKEY_OP_DECRYPT
  _M.EVP_PKEY_OP_SIG = _M.EVP_PKEY_OP_SIGN + _M.EVP_PKEY_OP_VERIFY + _M.EVP_PKEY_OP_VERIFYRECOVER +
                      _M.EVP_PKEY_OP_SIGNCTX + _M.EVP_PKEY_OP_VERIFYCTX
end

-- clean up error occurs during OBJ_txt2*
C.ERR_clear_error()

_M.ecx_curves = {
  Ed25519 = _M.EVP_PKEY_ED25519,
  X25519 = _M.EVP_PKEY_X25519,
  Ed448 = _M.EVP_PKEY_ED448,
  X448 = _M.EVP_PKEY_X448,
}

return _M
