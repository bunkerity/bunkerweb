---
-- Common utilities for session library and storage backends
--
-- @module resty.session.utils


local require = require


local buffer = require "string.buffer"
local bit = require "bit"


local select = select
local ceil = math.ceil
local byte = string.byte
local band = bit.band
local bnot = bit.bnot
local bor = bit.bor
local fmt = string.format
local sub = string.sub


local is_fips_mode do
  local IS_FIPS

  local function is_fips_mode_real()
    return IS_FIPS == true
  end

  ---
  -- Returns whether OpenSSL is in FIPS-mode.
  --
  -- @function utils.is_fips_mode
  -- @treturn boolean `true` if OpenSSL is in FIPS-mode, otherwise `false`
  --
  -- @usage
  -- local is_fips = require "resty.session.utils".is_fips_mode()
  is_fips_mode = function()
    IS_FIPS = require("resty.openssl").get_fips_mode()
    is_fips_mode = is_fips_mode_real
    return is_fips_mode()
  end
end


local bpack, bunpack do
  local binpack
  local binunpack

  local SIZE_TO_FORMAT = {
    [1] = "<C",
    [2] = "<S",
    [3] = "<I",
    [4] = "<I",
    [5] = "<L",
    [6] = "<L",
    [7] = "<L",
    [8] = "<L",
  }

  local function bpack_real(size, value)
    local packed = binpack(SIZE_TO_FORMAT[size], value)

    if size == 3 then
      return sub(packed, 1, 3)
    elseif size == 5 then
      return sub(packed, 1, 5)
    elseif size == 6 then
      return sub(packed, 1, 6)
    elseif size == 7 then
      return sub(packed, 1, 7)
    end

    return packed
  end

  local function bunpack_real(size, value)
    if size == 5 then
      value = value .. "\0\0\0"
    elseif size == 6 then
      value = value .. "\0\0"
    elseif size == 3 or size == 7 then
      value = value .. "\0"
    end

    local _, unpacked_value = binunpack(value, SIZE_TO_FORMAT[size])
    return unpacked_value
  end


  ---
  -- Binary pack unsigned integer.
  --
  -- Returns binary packed version of an integer in little endian unsigned format.
  --
  -- Size can be:
  --
  -- * `1`, pack input as a little endian unsigned char (`<C`)
  -- * `2`, pack input as a little endian unsigned short (`<S`)
  -- * `3`, pack input as a little endian unsigned integer (truncated) (`<I`)
  -- * `4`, pack input as a little endian unsigned integer (`<I`)
  -- * `5`, pack input as a little endian unsigned long (truncated) (`<L`)
  -- * `6`, pack input as a little endian unsigned long (truncated) (`<L`)
  -- * `7`, pack input as a little endian unsigned long (truncated) (`<L`)
  -- * `8`, pack input as a little endian unsigned long (`<L`)
  --
  -- @function utils.bpack
  -- @tparam number size size of binary packed output
  -- @tparam number value value to binary pack
  -- @treturn string binary packed value
  --
  -- @usage
  -- local packed_128 = require "resty.session.utils".bpack(1, 128)
  -- local packed_now = require "resty.session.utils".bpack(8, ngx.time())
  bpack = function(size, value)
    if not binpack then
      binpack = require "lua_pack".pack
    end
    bpack = bpack_real
    return bpack(size, value)
  end


  ---
  -- Binary unpack unsigned integer.
  --
  -- Returns number from a little endian unsigned binary packed format.
  --
  -- Size can be:
  --
  -- * `1`, unpack input from little endian unsigned char (`<C`)
  -- * `2`, unpack input from little endian unsigned short (`<S`)
  -- * `3`, unpack input from little endian unsigned integer (truncated) (`<I`)
  -- * `4`, unpack input from little endian unsigned integer (`<I`)
  -- * `5`, unpack input from little endian unsigned integer (truncated) (`<L`)
  -- * `6`, unpack input from little endian unsigned integer (truncated) (`<L`)
  -- * `7`, unpack input from little endian unsigned integer (truncated) (`<L`)
  -- * `8`, unpack input from little endian unsigned long (`<L`)
  --
  -- @function utils.bunpack
  -- @tparam number size size of binary packed output
  -- @tparam number value value to binary pack
  -- @treturn number binary unpacked value
  --
  -- @usage
  -- local utils = require "resty.session.utils"
  -- local value = 128
  -- local packed_value = utils.bpack(1, value)
  -- local unpacked_value = utils.bunpack(1, packed_value)
  -- print(value == unpacked_value) -- true
  bunpack = function(size, value)
    if not binunpack then
      binunpack = require "lua_pack".unpack
    end
    bunpack = bunpack_real
    return bunpack(size, value)
  end
end


local trim do
  local SPACE_BYTE = byte(" ")
  local TAB_BYTE   = byte("\t")
  local CR_BYTE    = byte("\r")
  local LF_BYTE    = byte("\n")
  local VTAB_BYTE  = byte("\v")
  local FF_BYTE    = byte("\f")

  ---
  -- Trim whitespace from the start and from the end of string.
  --
  -- Characters that are trimmed:
  --
  -- * space `" "`
  -- * tab `"\t"`
  -- * carriage return `"\r"`
  -- * line feed `"\n"`
  -- * vertical tab `"\v"`
  -- * form feed `"\f"`
  --
  -- @function utils.trim
  -- @tparam string value string to trim
  -- @treturn string a whitespace trimmed string
  --
  -- @usage
  -- local trimmed = require "resty.session.utils".trim("  hello world  ")
  trim = function(value)
    if value == nil or value == "" then
      return ""
    end

    local len = #value

    local s = 1
    for i = 1, len do
      local b = byte(value, i)
      if b == SPACE_BYTE
      or b == TAB_BYTE
      or b == CR_BYTE
      or b == LF_BYTE
      or b == VTAB_BYTE
      or b == FF_BYTE
      then
        s = s + 1
      else
        break
      end
    end

    local e = len
    for i = len, 1, -1 do
      local b = byte(value, i)
      if b == SPACE_BYTE
      or b == TAB_BYTE
      or b == CR_BYTE
      or b == LF_BYTE
      or b == VTAB_BYTE
      or b == FF_BYTE
      then
        e = e - 1
      else
        break
      end
    end

    if s ~= 1 or e ~= len then
      return sub(value, s, e)
    end

    return value
  end
end


local encode_json, decode_json do
  local cjson

  ---
  -- JSON encode value.
  --
  -- @function utils.encode_json
  -- @tparam any value value to json encode
  -- @treturn string json encoded value
  --
  -- @usage
  -- local json = require "resty.session.utils".encode_json({ hello = "world" })
  encode_json = function(value)
    if not cjson then
      cjson = require "cjson.safe".new()
    end
    encode_json = cjson.encode
    return encode_json(value)
  end

  ---
  -- JSON decode value.
  --
  -- @function utils.decode_json
  -- @tparam string value string to json decode
  -- @treturn any json decoded value
  --
  -- @usage
  -- local tbl = require "resty.session.utils".decode_json('{ "hello": "world" }')
  decode_json = function(value)
    if not cjson then
      cjson = require "cjson.safe".new()
    end
    decode_json = cjson.decode
    return decode_json(value)
  end
end


local encode_base64url, decode_base64url, base64_size do
  local base64
  ---
  -- Base64 URL encode value.
  --
  -- @function utils.encode_base64url
  -- @tparam string value string to base64 url encode
  -- @treturn string base64 url encoded value
  --
  -- @usage
  -- local encoded = require "resty.session.utils".encode_base64url("test")
  encode_base64url = function(value)
    if not base64 then
      base64 = require "ngx.base64"
    end
    encode_base64url = base64.encode_base64url
    return encode_base64url(value)
  end

  ---
  -- Base64 URL decode value
  --
  -- @function utils.decode_base64url
  -- @tparam string value string to base64 url decode
  -- @treturn string base64 url decoded value
  --
  -- @usage
  -- local utils = require "resty.session.utils"
  -- local encoded = utils.encode_base64url("test")
  -- local decoded = utils.decode_base64url(encoded)
  decode_base64url = function(value)
    if not base64 then
      base64 = require "ngx.base64"
    end
    decode_base64url = base64.decode_base64url
    return decode_base64url(value)
  end

  ---
  -- Base64 size from original size (without padding).
  --
  -- @function utils.base64_size
  -- @tparam number size original size
  -- @treturn number base64 url encoded size without padding
  --
  -- @usage
  -- local test = "test"
  -- local b64len = require "resty.session.utils".base64_size(#test)
  base64_size = function(size)
    return ceil(4 * size / 3)
  end
end


local deflate, inflate do
  local DEFLATE_WINDOW_BITS = -15
  local DEFLATE_CHUNK_SIZE = 8192
  local DEFLATE_OPTIONS = {
    windowBits = DEFLATE_WINDOW_BITS,
  }

  local zlib
  local input_buffer = buffer.new()
  local output_buffer = buffer.new()

  local function prepare_buffers(input)
    input_buffer:set(input)
    output_buffer:reset()
  end

  local function read_input_buffer(size)
    local data = input_buffer:get(size)
    return data ~= "" and data or nil
  end

  local function write_output_buffer(data)
    return output_buffer:put(data)
  end

  local function gzip(inflate_or_deflate, input, chunk_size, window_bits_or_options)
    prepare_buffers(input)
    local ok, err = inflate_or_deflate(read_input_buffer, write_output_buffer,
                                       chunk_size, window_bits_or_options)
    if not ok then
      return nil, err
    end

    return output_buffer:get()
  end

  local function deflate_real(data)
    return gzip(zlib.deflateGzip, data, DEFLATE_CHUNK_SIZE, DEFLATE_OPTIONS)
  end

  local function inflate_real(data)
    return gzip(zlib.inflateGzip, data, DEFLATE_CHUNK_SIZE, DEFLATE_WINDOW_BITS)
  end


  ---
  -- Compress the data with deflate algorithm.
  --
  -- @function utils.deflate
  -- @tparam string data data to deflate
  -- @treturn string deflated data
  --
  -- @usage
  -- local test = "test"
  -- local deflated = require "resty.session.utils".deflate(("a"):rep(100))
  deflate = function(data)
    if not zlib then
      zlib = require "ffi-zlib"
    end
    deflate = deflate_real
    return deflate(data)
  end

  ---
  -- Decompress the data compressed with deflate algorithm.
  --
  -- @function utils.inflate
  -- @tparam string data data to inflate
  -- @treturn string inflated data
  --
  -- @usage
  -- local utils = require "resty.session.utils"
  -- local deflated = utils.deflate(("a"):rep(100))
  -- local inflated = utils.inflate(deflated)
  inflate = function(data)
    if not zlib then
      zlib = require "ffi-zlib"
    end
    inflate = inflate_real
    return inflate(data)
  end
end


local rand_bytes do
  local rand

  ---
  -- Generate crypto random bytes.
  --
  -- @function utils.rand_bytes
  -- @tparam number length how many bytes of random data to generate
  -- @treturn string|nil random bytes
  -- @treturn string|nil error message
  --
  -- @usage
  -- local bytes = require "resty.session.utils".rand_bytes(32)
  rand_bytes = function(length)
    if not rand then
      rand = require "resty.openssl.rand"
    end
    rand_bytes = rand.bytes
    return rand_bytes(length)
  end
end


local sha256 do
  local digest
  local sha256_digest

  local function sha256_real(value)
    local _, err, output
    if not sha256_digest then
      sha256_digest, err = digest.new("sha256")
      if err then
        return nil, err
      end
    end

    output, err = sha256_digest:final(value)
    if err then
      sha256_digest = nil
      return nil, err
    end

    _, err = sha256_digest:reset()
    if err then
      sha256_digest = nil
    end

    return output
  end

  ---
  -- Calculates SHA-256 hash of the value.
  --
  -- @function utils.sha256
  -- @tparam string value value from which to calculate hash
  -- @treturn string|nil sha-256 hash (32 bytes)
  -- @treturn string|nil error message
  --
  -- @usage
  -- local hash, err = require "resty.session.utils".sha256("hello world")
  sha256 = function(value)
    if not digest then
      digest = require "resty.openssl.digest"
    end
    sha256 = sha256_real
    return sha256(value)
  end
end


local derive_hkdf_sha256 do
  local kdf_derive

  local EXTRACTED_KEYS = {}

  local HKDF_SHA256_EXTRACT_OPTS
  local HKDF_SHA256_EXPAND_OPTS

  local function derive_hkdf_sha256_real(ikm, nonce, usage, size)
    local err
    local key = EXTRACTED_KEYS[ikm]
    if not key then
      HKDF_SHA256_EXTRACT_OPTS.hkdf_key = ikm
      key, err = kdf_derive(HKDF_SHA256_EXTRACT_OPTS)
      HKDF_SHA256_EXTRACT_OPTS.hkdf_key = ""
      if not key then
        return nil, err
      end
      EXTRACTED_KEYS[ikm] = key
    end

    HKDF_SHA256_EXPAND_OPTS.hkdf_key = key
    HKDF_SHA256_EXPAND_OPTS.hkdf_info = usage .. ":" .. nonce
    HKDF_SHA256_EXPAND_OPTS.outlen = size
    key, err = kdf_derive(HKDF_SHA256_EXPAND_OPTS)
    if not key then
      return nil, err
    end

    return key
  end

  ---
  -- Derive a new key using HKDF with SHA-256.
  --
  -- @function utils.derive_hkdf_sha256
  -- @tparam string ikm initial key material
  -- @tparam string nonce nonce
  -- @tparam string usage e.g. `"encryption"` or `"authentication"`
  -- @tparam number size how many bytes to return
  -- @treturn string|nil key material
  -- @treturn string|nil error message
  --
  -- @usage
  -- local utils = require "resty.session.utils"
  -- local ikm = utils.rand_bytes(32)
  -- local nonce = utils.rand_bytes(32)
  -- local key, err = utils.derive_hkdf_sha256(ikm, nonce, "encryption", 32)
  derive_hkdf_sha256 = function(ikm, nonce, usage, size)
    if not kdf_derive then
      local kdf = require "resty.openssl.kdf"
      HKDF_SHA256_EXTRACT_OPTS = {
        type = kdf.HKDF,
        outlen = 32,
        md = "sha256",
        salt = "",
        hkdf_key = "",
        hkdf_mode = kdf.HKDEF_MODE_EXTRACT_ONLY,
        hkdf_info = "",
      }
      HKDF_SHA256_EXPAND_OPTS = {
        type = kdf.HKDF,
        outlen = 44,
        md = "sha256",
        salt = "",
        hkdf_key = "",
        hkdf_mode = kdf.HKDEF_MODE_EXPAND_ONLY,
        hkdf_info = "",
      }
      kdf_derive = kdf.derive
    end
    derive_hkdf_sha256 = derive_hkdf_sha256_real
    return derive_hkdf_sha256(ikm, nonce, usage, size)
  end
end


local derive_pbkdf2_hmac_sha256 do
  local kdf_derive

  local PBKDF2_SHA256_OPTS

  local function derive_pbkdf2_hmac_sha256_real(pass, salt, usage, size, iterations)
    PBKDF2_SHA256_OPTS.pass = pass
    PBKDF2_SHA256_OPTS.salt = usage .. ":" .. salt
    PBKDF2_SHA256_OPTS.outlen = size
    PBKDF2_SHA256_OPTS.pbkdf2_iter = iterations
    local key, err = kdf_derive(PBKDF2_SHA256_OPTS)
    if not key then
      return nil, err
    end

    return key
  end

  ---
  -- Derive a new key using PBKDF2 with SHA-256.
  --
  -- @function utils.derive_pbkdf2_hmac_sha256
  -- @tparam string pass password
  -- @tparam string salt salt
  -- @tparam string usage e.g. `"encryption"` or `"authentication"`
  -- @tparam number size how many bytes to return
  -- @tparam number iterations how many iterations to run, e.g. `10000`
  -- @treturn string|nil key material
  -- @treturn string|nil error message
  --
  -- @usage
  -- local utils = require "resty.session.utils"
  -- local pass = "my-super-secret-password"
  -- local salt = utils.rand_bytes(32)
  -- local key, err = utils.derive_pbkdf2_hmac_sha256(pass, salt, "encryption", 32, 10000)
  derive_pbkdf2_hmac_sha256 = function(pass, salt, usage, size, iterations)
    if not kdf_derive then
      local kdf = require "resty.openssl.kdf"
      PBKDF2_SHA256_OPTS = {
        type = kdf.PBKDF2,
        outlen = 44,
        md = "sha256",
        pass = "",
        salt = "",
        pbkdf2_iter = 10000,
      }
      kdf_derive = kdf.derive
    end
    derive_pbkdf2_hmac_sha256 = derive_pbkdf2_hmac_sha256_real
    return derive_pbkdf2_hmac_sha256(pass, salt, usage, size, iterations)
  end
end


---
-- Derive a new AES-256 GCM-mode key and initialization vector.
--
-- Safety can be:
-- * `nil` or `"None"`: key and iv will be derived using HKDF with SHA-256, except on FIPS-mode uses PBKDF2 with SHA-256 (single iteration)
-- * `Low`: key and iv will be derived using PBKDF2 with SHA-256 (1.000 iterations)
-- * `Medium`: key and iv will be derived using PBKDF2 with SHA-256 (10.000 iterations)
-- * `High`: key and iv will be derived using PBKDF2 with SHA-256 (100.000 iterations)
-- * `Very High`: key and iv will be derived using PBKDF2 with SHA-256 (1.000.000 iterations)
--
-- @function utils.derive_aes_gcm_256_key_and_iv
-- @tparam string ikm initial key material
-- @tparam string nonce nonce
-- @tparam[opt] string safety safety of key generation
-- @treturn string|nil key
-- @treturn string|nil error message
-- @treturn string|nil initialization vector
--
-- @usage
-- local utils = require "resty.session.utils"
-- local ikm = utils.rand_bytes(32)
-- local nonce = utils.rand_bytes(32)
-- local key, err, iv = utils.derive_aes_gcm_256_key_and_iv(ikm, nonce, "Medium")
local function derive_aes_gcm_256_key_and_iv(ikm, nonce, safety)
  local bytes, err
  if safety and safety ~= "None" then
    if safety == "Very High" then
      bytes, err = derive_pbkdf2_hmac_sha256(ikm, nonce, "encryption", 44, 1000000)
    elseif safety == "High" then
      bytes, err = derive_pbkdf2_hmac_sha256(ikm, nonce, "encryption", 44, 100000)
    elseif safety == "Low" then
      bytes, err = derive_pbkdf2_hmac_sha256(ikm, nonce, "encryption", 44, 1000)
    else
      bytes, err = derive_pbkdf2_hmac_sha256(ikm, nonce, "encryption", 44, 10000)
    end

  else
    if is_fips_mode() then
      bytes, err = derive_pbkdf2_hmac_sha256(ikm, nonce, "encryption", 44, 1)
    else
      bytes, err = derive_hkdf_sha256(ikm, nonce, "encryption", 44)
    end
  end

  if not bytes then
    return nil, err
  end

  local key = sub(bytes, 1, 32)  -- 32 bytes
  local iv  = sub(bytes, 33, 44) -- 12 bytes

  return key, nil, iv
end


---
-- Derive HMAC SHA-256 key for message authentication using HDKF with SHA-256,
-- except on FIPS-mode it uses PBKDF2 with SHA-256 (single iteration).
--
-- @function utils.derive_hmac_sha256_key
-- @tparam string ikm initial key material
-- @tparam string nonce nonce
-- @treturn string|nil key
-- @treturn string|nil error message
--
-- @usage
-- local utils = require "resty.session.utils"
-- local ikm = utils.rand_bytes(32)
-- local nonce = utils.rand_bytes(32)
-- local key, err = utils.derive_hmac_sha256_key(ikm, nonce)
local function derive_hmac_sha256_key(ikm, nonce)
  if is_fips_mode() then
    return derive_pbkdf2_hmac_sha256(ikm, nonce, "authentication", 32, 1)
  end

  return derive_hkdf_sha256(ikm, nonce, "authentication", 32)
end


local encrypt_aes_256_gcm, decrypt_aes_256_gcm do
  local AES_256_GCP_CIPHER = "aes-256-gcm"
  local AES_256_GCM_TAG_SIZE = 16

  local cipher_aes_256_gcm
  local function encrypt_aes_256_gcm_real(key, iv, plaintext, aad)
    local ciphertext, err = cipher_aes_256_gcm:encrypt(key, iv, plaintext, false, aad)
    if not ciphertext then
      return nil, err
    end

    local tag, err = cipher_aes_256_gcm:get_aead_tag(AES_256_GCM_TAG_SIZE)
    if not tag then
      return nil, err
    end

    return ciphertext, nil, tag
  end

  local function decrypt_aes_256_gcm_real(key, iv, ciphertext, aad, tag)
    return cipher_aes_256_gcm:decrypt(key, iv, ciphertext, false, aad, tag)
  end

  ---
  -- Encrypt plain text using AES-256 in GCM-mode.
  --
  -- @function utils.encrypt_aes_256_gcm
  -- @tparam string key encryption key
  -- @tparam string iv initialization vector
  -- @tparam string plaintext plain text
  -- @tparam string aad additional authenticated data
  -- @treturn string|nil ciphertext
  -- @treturn string|nil error message
  -- @treturn string|nil authentication tag
  --
  -- @usage
  -- local utils = require "resty.session.utils"
  -- local ikm = utils.rand_bytes(32)
  -- local nonce = utils.rand_bytes(32)
  -- local key, err, iv = utils.derive_aes_gcm_256_key_and_iv(ikm, nonce)
  -- local enc, err, tag = utils.encrypt_aes_256_gcm(key, iv, "hello", "john@doe.com")
  encrypt_aes_256_gcm = function(key, iv, plaintext, aad)
    if not cipher_aes_256_gcm then
      cipher_aes_256_gcm = require("resty.openssl.cipher").new(AES_256_GCP_CIPHER)
    end
    encrypt_aes_256_gcm = encrypt_aes_256_gcm_real
    return encrypt_aes_256_gcm(key, iv, plaintext, aad)
  end

  ---
  -- Decrypt ciphertext using AES-256 in GCM-mode.
  --
  -- @function utils.decrypt_aes_256_gcm
  -- @tparam string key encryption key
  -- @tparam string iv initialization vector
  -- @tparam string plaintext plain text
  -- @tparam string aad additional authenticated data
  -- @tparam string tag authentication tag
  -- @treturn string|nil ciphertext
  -- @treturn string|nil error message
  --
  -- @usage
  -- local utils = require "resty.session.utils"
  -- local ikm = utils.rand_bytes(32)
  -- local nonce = utils.rand_bytes(32)
  -- local key, err, iv = utils.derive_aes_gcm_256_key_and_iv(ikm, nonce)
  -- local enc, err, tag = utils.encrypt_aes_256_gcm(key, iv, "hello", "john@doe.com")
  -- local out, err = utils.decrypt_aes_256_gcm(key, iv, ciphertext, "john@doe.com", tag)
  decrypt_aes_256_gcm = function(key, iv, ciphertext, aad, tag)
    if not cipher_aes_256_gcm then
      cipher_aes_256_gcm = require("resty.openssl.cipher").new(AES_256_GCP_CIPHER)
    end
    decrypt_aes_256_gcm = decrypt_aes_256_gcm_real
    return decrypt_aes_256_gcm(key, iv, ciphertext, aad, tag)
  end
end


local hmac_sha256 do
  local hmac
  local HMAC_SHA256_DIGEST = "sha256"

  local function hmac_sha256_real(key, value)
    local mac, err = hmac.new(key, HMAC_SHA256_DIGEST)
    if not mac then
      return nil, err
    end

    local digest, err = mac:final(value)
    if not digest then
      return nil, err
    end

    return digest
  end

  ---
  -- Calculate message authentication code with HMAC with SHA-256.
  --
  -- @function utils.hmac_sha256
  -- @tparam string key key
  -- @tparam string value value
  -- @treturn string|nil message authentication code (32 bytes)
  -- @treturn string|nil error message
  --
  -- @usage
  -- local utils = require "resty.session.utils"
  -- local ikm = utils.rand_bytes(32)
  -- local nonce = utils.rand_bytes(32)
  -- local key, err = utils.derive_hmac_sha256_key(ikm, nonce)
  -- local mac, err = utils.hmac_sha256(key, "hello")
  hmac_sha256 = function(key, value)
    if not hmac then
      hmac = require "resty.openssl.hmac"
    end
    hmac_sha256 = hmac_sha256_real
    return hmac_sha256(key, value)
  end
end



local load_storage do
  local DSHM
  local FILE
  local MEMCACHED
  local MYSQL
  local POSTGRES
  local REDIS
  local REDIS_SENTINEL
  local REDIS_CLUSTER
  local SHM
  local CUSTOM = {}

  ---
  -- Loads session storage and creates a new instance using session configuration.
  --
  -- @function utils.load_storage
  -- @tparam string storage name of the storage to load
  -- @tparam[opt] table configuration session configuration
  -- @treturn table|nil instance of session storage
  -- @treturn string|nil error message
  --
  -- @usage
  -- local postgres = require "resty.session.utils".load_storage("postgres", {
  --   postgres = {
  --     host = "127.0.0.1",
  --   }
  -- })
  load_storage = function(storage, configuration)
    if storage == "cookie" then
      return nil

    elseif storage == "dshm" then
      if not DSHM then
        DSHM = require("resty.session.dshm")
      end
      return DSHM.new(configuration and configuration.dshm)

    elseif storage == "file" then
      if not FILE then
        FILE = require("resty.session.file")
      end
      return FILE.new(configuration and configuration.file)

    elseif storage == "memcached" or storage == "memcache" then
      if not MEMCACHED then
        MEMCACHED = require("resty.session.memcached")
      end
      return MEMCACHED.new(configuration and configuration.memcached or configuration.memcache)

    elseif storage == "mysql" or storage == "mariadb" then
      if not MYSQL then
        MYSQL = require("resty.session.mysql")
      end
      return MYSQL.new(configuration and configuration.mysql or configuration.mariadb)

    elseif storage == "postgres" or storage == "postgresql" then
      if not POSTGRES then
        POSTGRES = require("resty.session.postgres")
      end
      return POSTGRES.new(configuration and configuration.postgres or configuration.postgresql)

    elseif storage == "redis" then
      local cfg = configuration and configuration.redis
      if cfg then
        if cfg.nodes then
          if not REDIS_CLUSTER then
            REDIS_CLUSTER = require("resty.session.redis.cluster")
          end
          return REDIS_CLUSTER.new(cfg)

        elseif cfg.sentinels then
          if not REDIS_SENTINEL then
            REDIS_SENTINEL = require("resty.session.redis.sentinel")
          end
          return REDIS_SENTINEL.new(cfg)
        end
      end

      if not REDIS then
        REDIS = require("resty.session.redis")
      end
      return REDIS.new(cfg)

    elseif storage == "shm" then
      if not SHM then
        SHM = require("resty.session.shm")
      end

      return SHM.new(configuration and configuration.shm)

    else
      if not CUSTOM[storage] then
        CUSTOM[storage] = require(storage)
      end
      return CUSTOM[storage].new(configuration and configuration[storage])
    end
  end
end


---
-- Helper to format error messages.
--
-- @function utils.errmsg
-- @tparam[opt] string|nil err a possible error coming from underlying library
-- @tparam string|nil msg error message
-- @tparam any ... arguments for formatting the msg
-- @treturn string formatted error message
--
-- @usage
-- local utils = require "resty.session.utils"
-- local test = "aaaa"
-- local data, err = utils.deflate(test)
-- if not data then
--   print(utils.errmsg(err, "unable to deflate data '%s'", test)
-- end
local function errmsg(err, msg, ...)
  if not msg then
    if err then
      return err
    end

    return "unknown error"
  end

  if select("#", ...) > 0 then
    msg = fmt(msg, ...)
  end

  if err then
    return fmt("%s (%s)", msg, err)
  end

  return msg
end


---
-- Helper to create a delimited key.
--
-- @function utils.get_name
-- @tparam table storage a storage implementation
-- @tparam string name name
-- @tparam string key key
-- @tparam string subject subject
-- @treturn string formatted and delimited name
local function get_name(storage, name, key, subject)
  local prefix = storage.prefix
  local suffix = storage.suffix
  if prefix and suffix and subject then
    return fmt("%s:%s:%s:%s:%s", prefix, name, key, subject, suffix)
  elseif prefix and suffix then
    return fmt("%s:%s:%s:%s", prefix, name, key, suffix)
  elseif prefix and subject then
    return fmt("%s:%s:%s:%s", prefix, name, key, subject)
  elseif suffix and subject then
    return fmt("%s:%s:%s:%s", name, key, subject, suffix)
  elseif prefix then
    return fmt("%s:%s:%s", prefix, name, key)
  elseif suffix then
    return fmt("%s:%s:%s", name, key, suffix)
  elseif subject then
    return fmt("%s:%s:%s", name, key, subject)
  else
    return fmt("%s:%s", name, key)
  end
end


---
-- Helper to turn on a flag.
--
-- @function utils.set_flag
-- @tparam number flags flags on which the flag is applied
-- @tparam number flag flag that is applied
-- @treturn number flags with the flag applied
--
-- @usage
-- local flags = 0x0000
-- local FLAG_DOG = 0x001
-- flags = utils.set_flag(flags, FLAG_DOG)
local function set_flag(options, flag)
  return bor(options, flag)
end


---
-- Helper to turn off a flag.
--
-- @function utils.unset_flag
-- @tparam number flags flags on which the flag is removed
-- @tparam number flag flag that is removed
-- @treturn number flags with the flag removed
--
-- @usage
-- local options = 0x0000
-- local FLAG_DOG = 0x001
-- flags = utils.set_flag(options, FLAG_DOG)
-- flags = utils.unset_flag(options, FLAG_DOG)
local function unset_flag(flags, flag)
  return band(flags, bnot(flag))
end


---
-- Helper to check if flag is enabled.
--
-- @function utils.has_flag
-- @tparam number flags flags on which the flag is checked
-- @tparam number flag flag that is checked
-- @treturn boolean true if flag has is present, otherwise false
--
-- @usage
-- local flags = 0x0000
-- local FLAG_DOG = 0x001
-- local FLAG_BONE = 0x010
-- flags = utils.set_flag(flags, FLAG_DOG)
-- flags = utils.set_flag(flags, FLAG_BONE)
-- print(utils.has_flag(flags, FLAG_BONE)
local function has_flag(flags, flag)
  return band(flags, flag) ~= 0
end


---
-- Helper to get the value used to store metadata for a certain aud and sub
-- Empty exp means the session id has been invalidated
--
-- @function utils.meta_get_value
-- @tparam string key storage key
-- @tparam string exp expiration
-- @treturn string the value to store in the metadata collection
local function meta_get_value(key, exp)
  if not exp or exp == 0 then
    return fmt("%s;", key)
  end
  return fmt("%s:%s;", key, encode_base64url(bpack(5, exp)))
end


local meta_get_next do
  local KEY_OFFSET = 43
  local DEL_OFFSET = 1
  local EXP_OFFSET = 7

  local COLON = byte(":")

  ---
  -- Function to extract the next key and exp from a serialized
  -- metadata list, starting from index
  --
  -- @function utils.meta_get_next
  -- @tparam string val list of key:exp;
  -- @tparam number index start index
  -- @treturn key string session id
  -- @treturn err string error
  -- @treturn exp number expiration
  -- @treturn index number|nil index of the cursor
  meta_get_next = function(val, index)
    local key = sub(val, index, index + KEY_OFFSET - 1)
    index = index + KEY_OFFSET
    local del = byte(val, index + DEL_OFFSET - 1)
    index = index + DEL_OFFSET

    if del ~= COLON then
      return key, nil, nil, index
    end

    local exp = sub(val, index, index + EXP_OFFSET - 1)
    index = index + EXP_OFFSET + DEL_OFFSET
    local exp, err = decode_base64url(exp)
    if err then
      return nil, err
    end

    exp = bunpack(5, exp)
    return key, nil, exp, index
  end
end


---
-- Function to filter out the latest valid key:exp from a
-- serialized list, used to store session metadata
--
-- @function utils.meta_get_latest
-- @tparam string sessions list of key:exp;
-- @treturn table valid sessions and their exp
local function meta_get_latest(sessions, current_time)
  current_time = current_time

  local latest = {}
  local index = 1
  local length = #sessions
  while index < length do
    local key, err, exp
    key, err, exp, index = meta_get_next(sessions, index)
    if err then
      return nil, err
    end

    if exp and exp > current_time then
      latest[key] = exp
    else
      latest[key] = nil
    end
  end

  return latest
end


return {
  is_fips_mode = is_fips_mode,
  bpack = bpack,
  bunpack = bunpack,
  trim = trim,
  encode_json = encode_json,
  decode_json = decode_json,
  encode_base64url = encode_base64url,
  decode_base64url = decode_base64url,
  base64_size = base64_size,
  inflate = inflate,
  deflate = deflate,
  rand_bytes = rand_bytes,
  sha256 = sha256,
  derive_hkdf_sha256 = derive_hkdf_sha256,
  derive_pbkdf2_hmac_sha256 = derive_pbkdf2_hmac_sha256,
  derive_aes_gcm_256_key_and_iv = derive_aes_gcm_256_key_and_iv,
  derive_hmac_sha256_key = derive_hmac_sha256_key,
  encrypt_aes_256_gcm = encrypt_aes_256_gcm,
  decrypt_aes_256_gcm = decrypt_aes_256_gcm,
  hmac_sha256 = hmac_sha256,
  load_storage = load_storage,
  errmsg = errmsg,
  get_name = get_name,
  set_flag = set_flag,
  unset_flag = unset_flag,
  has_flag = has_flag,
  meta_get_value = meta_get_value,
  meta_get_next = meta_get_next,
  meta_get_latest = meta_get_latest,
}
