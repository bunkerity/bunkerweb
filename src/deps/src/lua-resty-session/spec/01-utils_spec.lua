local utils = require "resty.session.utils"


local describe = describe
local tostring = tostring
local random = math.random
local assert = assert
local ipairs = ipairs
local match = string.match
local it = it


describe("Testing utils", function()
  describe("pack/unpack data", function()
    local function range_max(bytes)
      if bytes == 8 then
        bytes = bytes - 1
      end
      return 2 ^ (8 * bytes) - 1
    end

    it("bpack and bunpack produce consistent output", function()
      for _, i in ipairs{ 1, 2, 4, 8 } do
        local input    = random(1, range_max(i))
        local packed   = utils.bpack(i, input)
        local unpacked = utils.bunpack(i, packed)

        assert.equals(i, #packed)
        assert.equals(unpacked, input)
      end
    end)
  end)

  describe("trim", function()
    it("characters are trimmed as expected", function()
      local input = "   \t\t\r\n\n\v\f\f\fyay\ntrim!\f\f\v\n\r\t   "
      local expected_output = "yay\ntrim!"
      local output = utils.trim(input)

      assert.equals(output, expected_output)
    end)
  end)

  describe("encode/decode json", function()
    it("produce consistent output", function()
      local input = {
        foo = "bar",
        test = 123
      }
      local encoded = utils.encode_json(input)
      local decoded = utils.decode_json(encoded)

      assert.same(decoded, input)
    end)
  end)

  describe("encode/decode base64url", function()
    it("produce consistent output", function()
      local input   = "<<<!?>>>?!"
      local encoded = utils.encode_base64url(input)

      assert.is_nil(match(encoded, "[/=+]"))
      local decoded = utils.decode_base64url(encoded)
      assert.equals(input, decoded)
    end)
  end)

  describe("deflate/inflate", function()
    it("produce consistent output", function()
      local input    = utils.rand_bytes(1024)
      local deflated = utils.deflate(input)
      local inflated = utils.inflate(deflated)

      assert.equals(input, inflated)
    end)
  end)

  describe("Derive keys, encrypt and decrypt", function()
    local ikm   = "some key material"
    local nonce = "0000000000000000"
    local usage = "encryption"
    local size  = 44

    it("derives key of expected size with derive_hkdf_sha256", function()
      local k_bytes, err = utils.derive_hkdf_sha256(ikm, nonce, usage, size)
      assert.is_not_nil(k_bytes)
      assert.is_nil(err)
      assert.equals(size, #tostring(k_bytes))
    end)

    it("derives key of expected size with derive_pbkdf2_hmac_sha256", function()
      local k_bytes, err = utils.derive_pbkdf2_hmac_sha256(ikm, nonce, usage, size)
      assert.is_not_nil(k_bytes)
      assert.is_nil(err)
      assert.equals(size, #tostring(k_bytes))
    end)

    it("derives a valid key and calculates mac with it", function()
      local key, err, mac
      key, err = utils.derive_hmac_sha256_key(ikm, nonce)
      assert.is_not_nil(key)
      assert.is_nil(err)
      assert.equals(32, #key)

      mac, err = utils.hmac_sha256(key, "some message")
      assert.is_not_nil(mac)
      assert.is_nil(err)
    end)

    it("successfully derives key and iv; encryption and decryption succeeds", function()
      local data = {
        foo = "bar",
        tab = { "val" },
        num = 123,
      }
      local aad = "some_aad"
      local input_data = utils.encode_json(data)

      local key, err, iv, ciphertext, tag, plaintext
      for _, slow in ipairs({ true, false }) do
        key, err, iv = utils.derive_aes_gcm_256_key_and_iv(ikm, nonce, slow)
        assert.is_not_nil(key)
        assert.is_not_nil(iv)
        assert.is_nil(err)

        ciphertext, err, tag = utils.encrypt_aes_256_gcm(key, iv, input_data, aad)
        assert.is_not_nil(ciphertext)
        assert.is_not_nil(tag)
        assert.is_nil(err)

        plaintext, err = utils.decrypt_aes_256_gcm(key, iv, ciphertext, aad, tag)
        assert.is_not_nil(plaintext)
        assert.is_nil(err)

        assert.equals(plaintext, input_data)
      end
    end)
  end)
end)
