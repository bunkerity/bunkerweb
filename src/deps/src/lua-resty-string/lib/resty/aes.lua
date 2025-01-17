-- Copyright (C) by Yichun Zhang (agentzh)


--local asn1 = require "resty.asn1"
local ffi = require "ffi"
local ffi_new = ffi.new
local ffi_gc = ffi.gc
local ffi_str = ffi.string
local ffi_copy = ffi.copy
local C = ffi.C
local setmetatable = setmetatable
--local error = error
local type = type


local _M = { _VERSION = '0.16' }

local mt = { __index = _M }

local EVP_CTRL_AEAD_SET_IVLEN = 0x09
local EVP_CTRL_AEAD_GET_TAG = 0x10
local EVP_CTRL_AEAD_SET_TAG = 0x11

ffi.cdef[[
typedef struct engine_st ENGINE;

typedef struct evp_cipher_st EVP_CIPHER;
typedef struct evp_cipher_ctx_st EVP_CIPHER_CTX;

typedef struct env_md_ctx_st EVP_MD_CTX;
typedef struct env_md_st EVP_MD;

const EVP_MD *EVP_md5(void);
const EVP_MD *EVP_sha(void);
const EVP_MD *EVP_sha1(void);
const EVP_MD *EVP_sha224(void);
const EVP_MD *EVP_sha256(void);
const EVP_MD *EVP_sha384(void);
const EVP_MD *EVP_sha512(void);

const EVP_CIPHER *EVP_aes_128_ecb(void);
const EVP_CIPHER *EVP_aes_128_cbc(void);
const EVP_CIPHER *EVP_aes_128_cfb1(void);
const EVP_CIPHER *EVP_aes_128_cfb8(void);
const EVP_CIPHER *EVP_aes_128_cfb128(void);
const EVP_CIPHER *EVP_aes_128_ofb(void);
const EVP_CIPHER *EVP_aes_128_ctr(void);
const EVP_CIPHER *EVP_aes_192_ecb(void);
const EVP_CIPHER *EVP_aes_192_cbc(void);
const EVP_CIPHER *EVP_aes_192_cfb1(void);
const EVP_CIPHER *EVP_aes_192_cfb8(void);
const EVP_CIPHER *EVP_aes_192_cfb128(void);
const EVP_CIPHER *EVP_aes_192_ofb(void);
const EVP_CIPHER *EVP_aes_192_ctr(void);
const EVP_CIPHER *EVP_aes_256_ecb(void);
const EVP_CIPHER *EVP_aes_256_cbc(void);
const EVP_CIPHER *EVP_aes_256_cfb1(void);
const EVP_CIPHER *EVP_aes_256_cfb8(void);
const EVP_CIPHER *EVP_aes_256_cfb128(void);
const EVP_CIPHER *EVP_aes_256_ofb(void);
const EVP_CIPHER *EVP_aes_128_gcm(void);
const EVP_CIPHER *EVP_aes_192_gcm(void);
const EVP_CIPHER *EVP_aes_256_gcm(void);

EVP_CIPHER_CTX *EVP_CIPHER_CTX_new();
void EVP_CIPHER_CTX_free(EVP_CIPHER_CTX *a);
int EVP_CIPHER_CTX_block_size(const EVP_CIPHER_CTX *ctx);

int EVP_CIPHER_CTX_set_padding(EVP_CIPHER_CTX *ctx, int padding);

int EVP_EncryptInit_ex(EVP_CIPHER_CTX *ctx,const EVP_CIPHER *cipher,
        ENGINE *impl, unsigned char *key, const unsigned char *iv);

int EVP_EncryptUpdate(EVP_CIPHER_CTX *ctx, unsigned char *out, int *outl,
        const unsigned char *in, int inl);

int EVP_EncryptFinal_ex(EVP_CIPHER_CTX *ctx, unsigned char *out, int *outl);

int EVP_DecryptInit_ex(EVP_CIPHER_CTX *ctx,const EVP_CIPHER *cipher,
        ENGINE *impl, unsigned char *key, const unsigned char *iv);

int EVP_DecryptUpdate(EVP_CIPHER_CTX *ctx, unsigned char *out, int *outl,
        const unsigned char *in, int inl);

int EVP_DecryptFinal_ex(EVP_CIPHER_CTX *ctx, unsigned char *outm, int *outl);

int EVP_BytesToKey(const EVP_CIPHER *type,const EVP_MD *md,
        const unsigned char *salt, const unsigned char *data, int datal,
        int count, unsigned char *key,unsigned char *iv);

int EVP_CIPHER_CTX_ctrl(EVP_CIPHER_CTX *ctx, int type, int arg, void *ptr);
]]

local hash
hash = {
    md5 = C.EVP_md5(),
    sha1 = C.EVP_sha1(),
    sha224 = C.EVP_sha224(),
    sha256 = C.EVP_sha256(),
    sha384 = C.EVP_sha384(),
    sha512 = C.EVP_sha512()
}
_M.hash = hash

local EVP_MAX_BLOCK_LENGTH = 32

local cipher
cipher = function (size, _cipher)
    local _size = size or 128
    local _cipher = _cipher or "cbc"
    local func = "EVP_aes_" .. _size .. "_" .. _cipher
    if C[func] then
        return { size=_size, cipher=_cipher, method=C[func]()}
    else
        return nil
    end
end
_M.cipher = cipher

function _M.new(self, key, salt, _cipher, _hash, hash_rounds, iv_len, enable_padding)
    local encrypt_ctx = C.EVP_CIPHER_CTX_new()
    if encrypt_ctx == nil then
        return nil, "no memory"
    end

    ffi_gc(encrypt_ctx, C.EVP_CIPHER_CTX_free)

    local decrypt_ctx = C.EVP_CIPHER_CTX_new()
    if decrypt_ctx == nil then
        return nil, "no memory"
    end

    ffi_gc(decrypt_ctx, C.EVP_CIPHER_CTX_free)

    local _cipher = _cipher or cipher()
    local _hash = _hash or hash.md5
    local hash_rounds = hash_rounds or 1
    local _cipherLength = _cipher.size/8
    local gen_key = ffi_new("unsigned char[?]",_cipherLength)
    local gen_iv = ffi_new("unsigned char[?]",_cipherLength)
    iv_len = iv_len or _cipherLength
    -- enable padding by default
    local padding = (enable_padding == nil or enable_padding) and 1 or 0

    if type(_hash) == "table" then
        if not _hash.iv then
          return nil, "iv is needed"
        end

        --[[ Depending on the encryption algorithm, the length of iv will be
          different. For detailed, please refer to
          https://www.openssl.org/docs/man1.1.0/man3/EVP_CIPHER_CTX_ctrl.html
        ]]
        iv_len = #_hash.iv
        if iv_len > _cipherLength then
            return nil, "bad iv length"
        end

        if _hash.method then
            local tmp_key = _hash.method(key)

            if #tmp_key ~= _cipherLength then
                return nil, "bad key length"
            end

            ffi_copy(gen_key, tmp_key, _cipherLength)

        elseif #key ~= _cipherLength then
            return nil, "bad key length"

        else
            ffi_copy(gen_key, key, _cipherLength)
        end

        ffi_copy(gen_iv, _hash.iv, iv_len)

    else
        if salt and #salt ~= 8 then
            return nil, "salt must be 8 characters or nil"
        end

        if C.EVP_BytesToKey(_cipher.method, _hash, salt, key, #key,
                            hash_rounds, gen_key, gen_iv)
            ~= _cipherLength
        then
            return nil, "failed to generate key and iv"
        end
    end

    if C.EVP_EncryptInit_ex(encrypt_ctx, _cipher.method, nil,
      nil, nil) == 0 or
      C.EVP_DecryptInit_ex(decrypt_ctx, _cipher.method, nil,
      nil, nil) == 0 then
        return nil, "failed to init ctx"
    end

    local cipher_name = _cipher.cipher
    if cipher_name == "gcm"
      or cipher_name == "ccm"
      or cipher_name == "ocb" then
        if C.EVP_CIPHER_CTX_ctrl(encrypt_ctx, EVP_CTRL_AEAD_SET_IVLEN,
         iv_len, nil) == 0 or
         C.EVP_CIPHER_CTX_ctrl(decrypt_ctx, EVP_CTRL_AEAD_SET_IVLEN,
         iv_len, nil) == 0 then
            return nil, "failed to set IV length"
         end
    end

    if C.EVP_CIPHER_CTX_set_padding(encrypt_ctx, padding) == 0 then
        return nil, "failed to set padding for encrypt context"
    end

    if C.EVP_CIPHER_CTX_set_padding(decrypt_ctx, padding) == 0 then
        return nil, "failed to set padding for decrypt context"
    end

    return setmetatable({
      _encrypt_ctx = encrypt_ctx,
      _decrypt_ctx = decrypt_ctx,
      _cipher = _cipher.cipher,
      _key = gen_key,
      _iv = gen_iv
      }, mt)
end


function _M.encrypt(self, s, aad)
    local typ = type(self)
    if typ ~= "table" then
        error("bad argument #1 self: table expected, got " .. typ, 2)
    end

    local s_len = #s
    local max_len = s_len + 2 * EVP_MAX_BLOCK_LENGTH
    local buf = ffi_new("unsigned char[?]", max_len)
    local out_len = ffi_new("int[1]")
    local tmp_len = ffi_new("int[1]")
    local ctx = self._encrypt_ctx

    if C.EVP_EncryptInit_ex(ctx, nil, nil, self._key, self._iv) == 0 then
        return nil, "EVP_EncryptInit_ex failed"
    end

    if self._cipher == "gcm" and aad ~= nil then
        if C.EVP_EncryptUpdate(ctx, nil, tmp_len, aad, #aad) == 0 then
            return nil, "C.EVP_EncryptUpdate failed"
        end
    end

    if C.EVP_EncryptUpdate(ctx, buf, out_len, s, s_len) == 0 then
        return nil, "EVP_EncryptUpdate failed"
    end

    if self._cipher == "gcm" then
        local encrypt_data = ffi_str(buf, out_len[0])
        if C.EVP_EncryptFinal_ex(ctx, buf, out_len) == 0 then
            return nil, "EVP_DecryptFinal_ex failed"
        end

        -- FIXME: For OCB mode the taglen must either be 16
        -- or the value previously set via EVP_CTRL_OCB_SET_TAGLEN.
        -- so we should extend this api in the future
        C.EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_GET_TAG, 16, buf);
        local tag = ffi_str(buf, 16)
        return {encrypt_data, tag}
    end

    if C.EVP_EncryptFinal_ex(ctx, buf + out_len[0], tmp_len) == 0 then
        return nil, "EVP_EncryptFinal_ex failed"
    end

    return ffi_str(buf, out_len[0] + tmp_len[0])
end


function _M.decrypt(self, s, tag, aad)
    local typ = type(self)
    if typ ~= "table" then
        error("bad argument #1 self: table expected, got " .. typ, 2)
    end

    local s_len = #s
    local max_len = s_len + 2 * EVP_MAX_BLOCK_LENGTH
    local buf = ffi_new("unsigned char[?]", max_len)
    local out_len = ffi_new("int[1]")
    local tmp_len = ffi_new("int[1]")
    local ctx = self._decrypt_ctx

    if C.EVP_DecryptInit_ex(ctx, nil, nil, self._key, self._iv) == 0 then
      return nil, "EVP_DecryptInit_ex failed"
    end

    if self._cipher == "gcm" and aad ~= nil then
        if C.EVP_DecryptUpdate(ctx, nil, tmp_len, aad, #aad) == 0 then
            return nil, "C.EVP_DecryptUpdate failed"
        end
    end

    if C.EVP_DecryptUpdate(ctx, buf, out_len, s, s_len) == 0 then
      return nil, "EVP_DecryptUpdate failed"
    end

    if self._cipher == "gcm" then
        local plain_txt = ffi_str(buf, out_len[0])
        if tag ~= nil then
            local tag_buf = ffi_new("unsigned char[?]", 16)
            ffi.copy(tag_buf, tag, 16)
            C.EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_AEAD_SET_TAG, 16, tag_buf);
        end

        if C.EVP_DecryptFinal_ex(ctx, buf + out_len[0], tmp_len) == 0 then
            return nil, "EVP_DecryptFinal_ex failed"
        end

        return plain_txt
    end

    if C.EVP_DecryptFinal_ex(ctx, buf + out_len[0], tmp_len) == 0 then
        return nil, "EVP_DecryptFinal_ex failed"
    end

    return ffi_str(buf, out_len[0] + tmp_len[0])
end


return _M

