local aes          = require "resty.aes"

local setmetatable = setmetatable
local tonumber     = tonumber
local ceil         = math.ceil
local var          = ngx.var
local sub          = string.sub
local rep          = string.rep

local HASHES       = aes.hash

local CIPHER_MODES = {
    ecb    = "ecb",
    cbc    = "cbc",
    cfb1   = "cfb1",
    cfb8   = "cfb8",
    cfb128 = "cfb128",
    ofb    = "ofb",
    ctr    = "ctr",
    gcm    = "gcm",
}

local CIPHER_SIZES = {
    [128]   = 128,
    [192]   = 192,
    [256]   = 256,
}

local defaults = {
    size   = CIPHER_SIZES[tonumber(var.session_aes_size, 10)] or 256,
    mode   = CIPHER_MODES[var.session_aes_mode]               or "cbc",
    hash   = HASHES[var.session_aes_hash]                     or HASHES.sha512,
    rounds = tonumber(var.session_aes_rounds,            10)  or 1,
}

local function adjust_salt(salt)
    if not salt then
        return nil
    end

    local z = #salt
    if z < 8 then
        return sub(rep(salt, ceil(8 / z)), 1, 8)
    end
    if z > 8 then
        return sub(salt, 1, 8)
    end

    return salt
end

local function get_cipher(self, key, salt)
    local mode = aes.cipher(self.size, self.mode)
    if not mode then
        return nil, "invalid cipher mode " .. self.mode ..  "(" .. self.size .. ")"
    end

    return aes:new(key, adjust_salt(salt), mode, self.hash, self.rounds)
end

local cipher = {}

cipher.__index = cipher

function cipher.new(session)
    local config = session.aes or defaults
    return setmetatable({
        size   = CIPHER_SIZES[tonumber(config.size, 10)] or defaults.size,
        mode   = CIPHER_MODES[config.mode]               or defaults.mode,
        hash   = HASHES[config.hash]                     or defaults.hash,
        rounds = tonumber(config.rounds,            10)  or defaults.rounds,
    }, cipher)
end

function cipher:encrypt(data, key, salt, _)
    local cip, err = get_cipher(self, key, salt)
    if not cip then
        return nil, err or "unable to aes encrypt data"
    end

    local encrypted_data
    encrypted_data, err = cip:encrypt(data)
    if not encrypted_data then
        return nil, err or "aes encryption failed"
    end

    if self.mode == "gcm" then
        return encrypted_data[1], nil, encrypted_data[2]
    end

    return encrypted_data
end

function cipher:decrypt(data, key, salt, _, tag)
    local cip, err = get_cipher(self, key, salt)
    if not cip then
        return nil, err or "unable to aes decrypt data"
    end

    local decrypted_data
    decrypted_data, err = cip:decrypt(data, tag)
    if not decrypted_data then
        return nil, err or "aes decryption failed"
    end

    if self.mode == "gcm" then
        return decrypted_data, nil, tag
    end

    return decrypted_data
end

return cipher
