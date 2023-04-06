---
-- Session library.
--
-- Session library provides HTTP session management capabilities for OpenResty based
-- applications, libraries and proxies.
--
-- @module resty.session


local require = require


local table_new = require "table.new"
local isempty = require "table.isempty"
local buffer = require "string.buffer"
local utils = require "resty.session.utils"


local clear_request_header = ngx.req.clear_header
local set_request_header = ngx.req.set_header
local setmetatable = setmetatable
local http_time = ngx.http_time
local tonumber = tonumber
local select = select
local assert = assert
local remove = table.remove
local header = ngx.header
local error = error
local floor = math.ceil
local time = ngx.time
local byte = string.byte
local type = type
local sub = string.sub
local fmt = string.format
local var = ngx.var
local log = ngx.log
local max = math.max
local min = math.min


local derive_aes_gcm_256_key_and_iv = utils.derive_aes_gcm_256_key_and_iv
local derive_hmac_sha256_key = utils.derive_hmac_sha256_key
local encrypt_aes_256_gcm = utils.encrypt_aes_256_gcm
local decrypt_aes_256_gcm = utils.decrypt_aes_256_gcm
local encode_base64url = utils.encode_base64url
local decode_base64url = utils.decode_base64url
local load_storage = utils.load_storage
local encode_json = utils.encode_json
local decode_json = utils.decode_json
local base64_size = utils.base64_size
local hmac_sha256 = utils.hmac_sha256
local rand_bytes = utils.rand_bytes
local unset_flag = utils.unset_flag
local set_flag = utils.set_flag
local has_flag = utils.has_flag
local inflate = utils.inflate
local deflate = utils.deflate
local bunpack = utils.bunpack
local errmsg = utils.errmsg
local sha256 = utils.sha256
local bpack = utils.bpack
local trim = utils.trim


local NOTICE = ngx.NOTICE
local WARN   = ngx.WARN


local KEY_SIZE = 32


--[ HEADER ----------------------------------------------------------------------------------------------------] || [ PAYLOAD --]
--[ Type || Flags || Session ID || Creation Time || Rolling Offset || Data Size || Tag || Idling Offset || Mac ] || [ Data      ]
--[ 1B   || 2B    || 32B        || 5B            || 4B             || 3B        || 16B || 3B            || 16B ] || [ *B        ]


local COOKIE_TYPE_SIZE    = 1  --  1
local FLAGS_SIZE          = 2  --  3
local SID_SIZE            = 32 -- 35
local CREATION_TIME_SIZE  = 5  -- 40
local ROLLING_OFFSET_SIZE = 4  -- 44
local DATA_SIZE           = 3  -- 47
local TAG_SIZE            = 16 -- 63
local IDLING_OFFSET_SIZE  = 3  -- 66
local MAC_SIZE            = 16 -- 82


local HEADER_TAG_SIZE = COOKIE_TYPE_SIZE + FLAGS_SIZE + SID_SIZE + CREATION_TIME_SIZE + ROLLING_OFFSET_SIZE + DATA_SIZE
local HEADER_TOUCH_SIZE = HEADER_TAG_SIZE + TAG_SIZE
local HEADER_MAC_SIZE = HEADER_TOUCH_SIZE + IDLING_OFFSET_SIZE
local HEADER_SIZE = HEADER_MAC_SIZE + MAC_SIZE
local HEADER_ENCODED_SIZE = base64_size(HEADER_SIZE)


local COOKIE_TYPE = bpack(COOKIE_TYPE_SIZE, 1)


local MAX_COOKIE_SIZE    = 4096
local MAX_COOKIES        = 9
local MAX_COOKIES_SIZE   = MAX_COOKIES * MAX_COOKIE_SIZE     --    36864 bytes
local MAX_CREATION_TIME  = 2 ^ (CREATION_TIME_SIZE  * 8) - 1 --   ~34789 years
local MAX_ROLLING_OFFSET = 2 ^ (ROLLING_OFFSET_SIZE * 8) - 1 --     ~136 years
local MAX_IDLING_OFFSET  = 2 ^ (IDLING_OFFSET_SIZE  * 8) - 1 --     ~194 days
local MAX_DATA_SIZE      = 2 ^ (DATA_SIZE           * 8) - 1 -- 16777215 bytes
local MAX_TTL            = 34560000                          --      400 days
-- see: https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-rfc6265bis-11#section-4.1.2.1


local FLAGS_NONE   = 0x0000
local FLAG_STORAGE = 0x0001
local FLAG_FORGET  = 0x0002
local FLAG_DEFLATE = 0x0010


local DEFAULT_AUDIENCE = "default"
local DEFAULT_SUBJECT
local DEFAULT_ENFORCE_SAME_SUBJECT = false
local DEFAULT_META = {}
local DEFAULT_IKM
local DEFAULT_IKM_FALLBACKS
local DEFAULT_HASH_STORAGE_KEY = false
local DEFAULT_HASH_SUBJECT = false
local DEFAULT_STORE_METADATA = false
local DEFAULT_TOUCH_THRESHOLD = 60 -- 1 minute
local DEFAULT_COMPRESSION_THRESHOLD = 1024 -- 1 kB
local DEFAULT_REQUEST_HEADERS
local DEFAULT_RESPONSE_HEADERS


local DEFAULT_COOKIE_NAME = "session"
local DEFAULT_COOKIE_PATH = "/"
local DEFAULT_COOKIE_SAME_SITE = "Lax"
local DEFAULT_COOKIE_SAME_PARTY
local DEFAULT_COOKIE_PRIORITY
local DEFAULT_COOKIE_PARTITIONED
local DEFAULT_COOKIE_HTTP_ONLY = true
local DEFAULT_COOKIE_PREFIX
local DEFAULT_COOKIE_DOMAIN
local DEFAULT_COOKIE_SECURE


local DEFAULT_REMEMBER_COOKIE_NAME = "remember"
local DEFAULT_REMEMBER_SAFETY = "Medium"
local DEFAULT_REMEMBER_META = false
local DEFAULT_REMEMBER = false


local DEFAULT_STALE_TTL                 = 10      -- 10 seconds
local DEFAULT_IDLING_TIMEOUT            = 900     -- 15 minutes
local DEFAULT_ROLLING_TIMEOUT           = 3600    --  1 hour
local DEFAULT_ABSOLUTE_TIMEOUT          = 86400   --  1 day
local DEFAULT_REMEMBER_ROLLING_TIMEOUT  = 604800  --  1 week
local DEFAULT_REMEMBER_ABSOLUTE_TIMEOUT = 2592000 -- 30 days


local DEFAULT_STORAGE


local STATE_NEW    = "new"
local STATE_OPEN   = "open"
local STATE_CLOSED = "closed"


local AT_BYTE        = byte("@")
local EQUALS_BYTE    = byte("=")
local SEMICOLON_BYTE = byte(";")


local COOKIE_EXPIRE_FLAGS = "; Expires=Thu, 01 Jan 1970 00:00:01 GMT; Max-Age=0"


local HEADER_BUFFER = buffer.new(HEADER_SIZE)
local FLAGS_BUFFER  = buffer.new(128)
local DATA_BUFFER   = buffer.new(MAX_COOKIES_SIZE)
local HIDE_BUFFER   = buffer.new(256)


local DATA = table_new(2, 0)


local HEADERS = {
  id                   = "Session-Id",
  audience             = "Session-Audience",
  subject              = "Session-Subject",
  timeout              = "Session-Timeout",
  idling_timeout       = "Session-Idling-Timeout",
  ["idling-timeout"]   = "Session-Idling-Timeout",
  rolling_timeout      = "Session-Rolling-Timeout",
  ["rolling-timeout"]  = "Session-Rolling-Timeout",
  absolute_timeout     = "Session-Absolute-Timeout",
  ["absolute-timeout"] = "Session-Absolute-Timeout",
}


local function set_response_header(name, value)
  header[name] = value
end


local function sha256_storage_key(sid)
  local key, err = sha256(sid)
  if not key then
    return nil, errmsg(err, "unable to sha256 hash session id")
  end

  if SID_SIZE ~= 32 then
    key = sub(key, 1, SID_SIZE)
  end

  key, err = encode_base64url(key)
  if not key then
    return nil, errmsg(err, "unable to base64url encode session id")
  end

  return key
end


local function sha256_subject(subject)
  local hashed_subject, err = sha256(subject)
  if not hashed_subject then
    return nil, errmsg(err, "unable to sha256 hash subject")
  end

  hashed_subject, err = encode_base64url(sub(hashed_subject, 1, 16))
  if not hashed_subject then
    return nil, errmsg(err, "unable to base64url encode subject")
  end

  return hashed_subject
end


local function calculate_mac(ikm, nonce, msg)
  local mac_key, err = derive_hmac_sha256_key(ikm, nonce)
  if not mac_key then
    return nil, errmsg(err, "unable to derive session message authentication key")
  end

  local mac, err = hmac_sha256(mac_key, msg)
  if not mac then
    return nil, errmsg(err, "unable to calculate session message authentication code")
  end

  if MAC_SIZE ~= 32 then
    return sub(mac, 1, MAC_SIZE)
  end

  return mac
end


local function calculate_cookie_chunks(cookie_name_size, data_size)
  local space_needed = cookie_name_size + 1 + HEADER_ENCODED_SIZE + data_size
  if space_needed > MAX_COOKIES_SIZE then
    return nil, "cookie size limit exceeded"
  end

  if space_needed <= MAX_COOKIE_SIZE then
    return 1
  end

  for i = 2, MAX_COOKIES do
    space_needed = space_needed + cookie_name_size + 2
    if space_needed > MAX_COOKIES_SIZE then
      return nil, "cookie size limit exceeded"
    elseif space_needed <= (MAX_COOKIE_SIZE * i) then
      return i
    end
  end

  return nil, "cookie size limit exceeded"
end


local function merge_cookies(cookies, cookie_name_size, cookie_name, cookie_data)
  if not cookies then
    return cookie_data
  end

  if type(cookies) == "string" then
    if byte(cookies, cookie_name_size + 1) == EQUALS_BYTE and
       sub(cookies, 1, cookie_name_size) == cookie_name
    then
      return cookie_data
    end

    return { cookies, cookie_data }
  end

  if type(cookies) ~= "table" then
    return nil, "unable to merge session cookies with response cookies"
  end

  local count = #cookies
  for i = 1, count do
    if byte(cookies[i], cookie_name_size + 1) == EQUALS_BYTE and
       sub(cookies[i], 1, cookie_name_size) == cookie_name
    then
      cookies[i] = cookie_data
      return cookies
    end

    if i == count then
      cookies[i+1] = cookie_data
      return cookies
    end
  end
end


local function get_store_metadata(self)
  if not self.store_metadata then
    return
  end

  local data = self.data
  local count = #data
  if count == 1 then
    local audience = data[1][2]
    local subject = data[1][3]
    if audience and subject then
      audience = encode_base64url(audience)
      subject = self.hash_subject(subject)
      return {
        audiences = { audience },
        subjects = { subject },
      }
    end

    return
  end

  local audiences
  local subjects
  local index = 0
  for i = 1, count do
    local audience = data[i][2]
    local subject = data[i][3]
    if audience and subject then
      audience = encode_base64url(audience)
      self.hash_subject(subject)
      if not audiences then
        audiences = table_new(count, 0)
        subjects = table_new(count, 0)
      end

      index = index + 1
      audiences[index] = audience
      subjects[index] = subject
    end
  end

  if not audiences then
    return
  end

  return {
    audiences = audiences,
    subjects = subjects,
  }
end


local function get_property(self, name)
  if name == "id" then
    local sid = self.meta.sid
    if not sid then
      return
    end

    return encode_base64url(sid)

  elseif name == "nonce" then
    return self.meta.sid

  elseif name == "audience" then
    return self.data[self.data_index][2]

  elseif name == "subject" then
    return self.data[self.data_index][3]

  elseif name == "timeout" then
    local timeout
    local meta = self.meta

    if self.idling_timeout > 0 then
      timeout = self.idling_timeout - (meta.timestamp - meta.creation_time - meta.rolling_offset - meta.idling_offset)
    end

    if self.rolling_timeout > 0 then
      local t = self.rolling_timeout - (meta.timestamp - meta.creation_time - meta.rolling_offset)
      timeout = timeout and min(t, timeout) or t
    end

    if self.absolute_timeout > 0 then
      local t = self.absolute_timeout - (meta.timestamp - meta.creation_time)
      timeout = timeout and min(t, timeout) or t
    end

    return timeout

  elseif name == "idling-timeout" or name == "idling_timeout" then
    local idling_timeout = self.idling_timeout
    if idling_timeout == 0 then
      return
    end

    local meta = self.meta
    return idling_timeout - (meta.timestamp - meta.creation_time - meta.rolling_offset - meta.idling_offset)

  elseif name == "rolling-timeout" or name == "rolling_timeout" then
    local rolling_timeout = self.rolling_timeout
    if rolling_timeout == 0 then
      return
    end

    local meta = self.meta
    return rolling_timeout - (meta.timestamp - meta.creation_time - meta.rolling_offset)

  elseif name == "absolute-timeout" or name == "absolute_timeout" then
    local absolute_timeout = self.absolute_timeout
    if absolute_timeout == 0 then
      return
    end

    local meta = self.meta
    return absolute_timeout - (meta.timestamp - meta.creation_time)

  else
    return self.meta[name]
  end
end


local function open(self, remember, meta_only)
  local storage = self.storage
  local current_time = time()
  local cookie_name
  if remember then
    cookie_name = self.remember_cookie_name
  else
    cookie_name = self.cookie_name
  end

  local cookie = var["cookie_" .. cookie_name]
  if not cookie then
    return nil, "missing session cookie"
  end

  local header_decoded do
    header_decoded = sub(cookie, 1, HEADER_ENCODED_SIZE)
    if #header_decoded ~= HEADER_ENCODED_SIZE then
      return nil, "invalid session header"
    end
    local err
    header_decoded, err = decode_base64url(header_decoded)
    if not header_decoded then
      return nil, errmsg(err, "unable to base64url decode session header")
    end
  end

  HEADER_BUFFER:set(header_decoded)

  local cookie_type do
    cookie_type = HEADER_BUFFER:get(COOKIE_TYPE_SIZE)
    if #cookie_type ~= COOKIE_TYPE_SIZE then
      return nil, "invalid session cookie type"
    end
    if cookie_type ~= COOKIE_TYPE then
      return nil, "invalid session cookie type"
    end
  end

  local flags do
    flags = HEADER_BUFFER:get(FLAGS_SIZE)
    if #flags ~= FLAGS_SIZE then
      return nil, "invalid session flags"
    end

    flags = bunpack(FLAGS_SIZE, flags)

    if storage then
      if not has_flag(flags, FLAG_STORAGE) then
        return nil, "invalid session flags"
      end
    elseif has_flag(flags, FLAG_STORAGE) then
      return nil, "invalid session flags"
    end
  end

  local sid do
    sid = HEADER_BUFFER:get(SID_SIZE)
    if #sid ~= SID_SIZE then
      return nil, "invalid session id"
    end
  end

  local creation_time do
    creation_time = HEADER_BUFFER:get(CREATION_TIME_SIZE)
    if #creation_time ~= CREATION_TIME_SIZE then
      return nil, "invalid session creation time"
    end

    creation_time = bunpack(CREATION_TIME_SIZE, creation_time)
    if not creation_time or creation_time < 0 or creation_time > MAX_CREATION_TIME then
      return nil, "invalid session creation time"
    end

    local absolute_elapsed = current_time - creation_time
    if absolute_elapsed > MAX_ROLLING_OFFSET then
      return nil, "session lifetime exceeded"
    end

    if remember then
      local remember_absolute_timeout = self.remember_absolute_timeout
      if remember_absolute_timeout ~= 0 then
        if absolute_elapsed > remember_absolute_timeout then
          return nil, "session remember absolute timeout exceeded"
        end
      end

    else
      local absolute_timeout = self.absolute_timeout
      if absolute_timeout ~= 0 then
        if absolute_elapsed > absolute_timeout then
          return nil, "session absolute timeout exceeded"
        end
      end
    end
  end

  local rolling_offset do
    rolling_offset = HEADER_BUFFER:get(ROLLING_OFFSET_SIZE)
    if #rolling_offset ~= ROLLING_OFFSET_SIZE then
      return nil, "invalid session rolling offset"
    end

    rolling_offset = bunpack(ROLLING_OFFSET_SIZE, rolling_offset)
    if not rolling_offset or rolling_offset < 0 or rolling_offset > MAX_ROLLING_OFFSET then
      return nil, "invalid session rolling offset"
    end

    local rolling_elapsed = current_time - creation_time - rolling_offset

    if remember then
      local remember_rolling_timeout = self.remember_rolling_timeout
      if remember_rolling_timeout ~= 0 then
        if rolling_elapsed > remember_rolling_timeout then
          return nil, "session remember rolling timeout exceeded"
        end
      end

    else
      local rolling_timeout = self.rolling_timeout
      if rolling_timeout ~= 0 then
        if rolling_elapsed > rolling_timeout then
          return nil, "session rolling timeout exceeded"
        end
      end
    end
  end

  local data_size do
    data_size = HEADER_BUFFER:get(DATA_SIZE)
    if #data_size ~= DATA_SIZE then
      return nil, "invalid session data size"
    end

    data_size = bunpack(DATA_SIZE, data_size)
    if not data_size or data_size < 0 or data_size > MAX_DATA_SIZE then
      return nil, "invalid session data size"
    end
  end

  local tag do
    tag = HEADER_BUFFER:get(TAG_SIZE)
    if #tag ~= TAG_SIZE then
      return nil, "invalid session tag"
    end
  end

  local idling_offset do
    idling_offset = HEADER_BUFFER:get(IDLING_OFFSET_SIZE)
    if #idling_offset ~= IDLING_OFFSET_SIZE then
      return nil, "invalid session idling offset"
    end

    idling_offset = bunpack(IDLING_OFFSET_SIZE, idling_offset)
    if not idling_offset or idling_offset < 0 or idling_offset > MAX_IDLING_OFFSET then
      return nil, "invalid session idling offset"
    end

    if remember then
      if idling_offset ~= 0 then
        return nil, "invalid session idling offset"
      end

    else
      local idling_timeout = self.idling_timeout
      if idling_timeout ~= 0 then
        local idling_elapsed = current_time - creation_time - rolling_offset - idling_offset
        if idling_elapsed > idling_timeout then
          return nil, "session idling timeout exceeded"
        end
      end
    end
  end

  local ikm do
    ikm = self.ikm
    local mac = HEADER_BUFFER:get(MAC_SIZE)
    if #mac ~= MAC_SIZE then
      return nil, "invalid session message authentication code"
    end

    local msg = sub(header_decoded, 1, HEADER_MAC_SIZE)
    local expected_mac, err = calculate_mac(ikm, sid, msg)
    if mac ~= expected_mac then
      local fallback_keys = self.ikm_fallbacks
      if fallback_keys then
        local count = #fallback_keys
        if count > 0 then
          for i = 1, count do
            ikm = fallback_keys[i]
            expected_mac, err = calculate_mac(ikm, sid, msg)
            if mac == expected_mac then
              break
            end

            if i == count then
              return nil, errmsg(err, "invalid session message authentication code")
            end
          end

        else
          return nil, errmsg(err, "invalid session message authentication code")
        end

      else
        return nil, errmsg(err, "invalid session message authentication code")
      end
    end
  end

  local data_index = self.data_index
  local audience = self.data[data_index][2]
  local initial_chunk, ciphertext, ciphertext_encoded, info_data do
    if storage then
      local key, err = self.hash_storage_key(sid)
      if not key then
        return nil, err
      end

      local data, err = storage:get(cookie_name, key, current_time)
      if not data then
        return nil, errmsg(err, "unable to load session")
      end

      data, err = decode_json(data)
      if not data then
        return nil, errmsg(err, "unable to json decode session")
      end

      ciphertext = data[1]
      ciphertext_encoded = ciphertext
      info_data = data[2]
      if info_data then
        info_data, err = decode_base64url(info_data)
        if not info_data then
          return nil, errmsg(err, "unable to base64url decode session info")
        end

        info_data, err = decode_json(info_data)
        if not info_data then
          return nil, errmsg(err, "unable to json decode session info")
        end

        if not info_data[audience] then
          info_data[audience] = self.info.data and self.info.data[audience] or nil
        end
      end

    else
      local cookie_chunks, err = calculate_cookie_chunks(#cookie_name, data_size)
      if not cookie_chunks then
        return nil, err
      end

      if cookie_chunks == 1 then
        initial_chunk = sub(cookie, -data_size)
        ciphertext = initial_chunk

      else
        initial_chunk = sub(cookie, HEADER_ENCODED_SIZE + 1)
        DATA_BUFFER:reset():put(initial_chunk)
        for i = 2, cookie_chunks do
          local chunk = var["cookie_" .. cookie_name .. i]
          if not chunk then
            return nil, errmsg(err, "missing session cookie chunk")
          end

          DATA_BUFFER:put(chunk)
        end

        ciphertext = DATA_BUFFER:get()
      end
    end

    if #ciphertext ~= data_size then
      return nil, "invalid session payload"
    end

    local err
    ciphertext, err = decode_base64url(ciphertext)
    if not ciphertext then
      return nil, errmsg(err, "unable to base64url decode session data")
    end
  end

  if remember then
    self.remember_meta = {
      timestamp      = current_time,
      flags          = flags,
      sid            = sid,
      creation_time  = creation_time,
      rolling_offset = rolling_offset,
      data_size      = data_size,
      idling_offset  = idling_offset,
      ikm            = ikm,
      header         = header_decoded,
      initial_chunk  = initial_chunk,
      ciphertext     = ciphertext_encoded,
    }

  else
    self.meta = {
      timestamp      = current_time,
      flags          = flags,
      sid            = sid,
      creation_time  = creation_time,
      rolling_offset = rolling_offset,
      data_size      = data_size,
      idling_offset  = idling_offset,
      ikm            = ikm,
      header         = header_decoded,
      initial_chunk  = initial_chunk,
      ciphertext     = ciphertext_encoded,
    }
  end

  if meta_only then
    return true
  end

  local aes_key, err, iv
  if remember then
    aes_key, err, iv = derive_aes_gcm_256_key_and_iv(ikm, sid, self.remember_safety)
  else
    aes_key, err, iv = derive_aes_gcm_256_key_and_iv(ikm, sid)
  end

  if not aes_key then
    return nil, errmsg(err, "unable to derive session decryption key")
  end

  local aad = sub(header_decoded, 1, HEADER_TAG_SIZE)
  local plaintext, err = decrypt_aes_256_gcm(aes_key, iv, ciphertext, aad, tag)
  if not plaintext then
    return nil, errmsg(err, "unable to decrypt session data")
  end

  local data do
    if has_flag(flags, FLAG_DEFLATE) then
      plaintext, err = inflate(plaintext)
      if not plaintext then
        return nil, errmsg(err, "unable to inflate session data")
      end
    end

    data, err = decode_json(plaintext)
    if not data then
      return nil, errmsg(err, "unable to json decode session data")
    end
  end

  if storage then
    self.info.data = info_data
  end

  local audience_index
  local count = #data
  for i = 1, count do
    if data[i][2] == audience then
      audience_index = i
      break
    end
  end

  if not audience_index then
    data[count + 1] = self.data[data_index]
    self.state = STATE_NEW
    self.data = data
    self.data_index = count + 1
    return nil, "missing session audience", true
  end

  self.state = STATE_OPEN
  self.data = data
  self.data_index = audience_index

  return true
end


local function save(self, state, remember)
  local cookie_name
  local meta
  if remember then
    cookie_name = self.remember_cookie_name
    meta = self.remember_meta or {}
  else
    cookie_name = self.cookie_name
    meta = self.meta
  end

  local cookie_name_size = #cookie_name
  local storage = self.storage
  local flags = self.flags

  if storage then
    flags = set_flag(flags, FLAG_STORAGE)
  else
    flags = unset_flag(flags, FLAG_STORAGE)
  end

  local sid, err = rand_bytes(SID_SIZE)
  if not sid then
    return nil, errmsg(err, "unable to generate session id")
  end

  local current_time = time()
  local rolling_offset

  local creation_time = meta.creation_time
  if creation_time then
    rolling_offset = current_time - creation_time
    if rolling_offset > MAX_ROLLING_OFFSET then
      return nil, "session maximum rolling offset exceeded"
    end

  else
    creation_time = current_time
    rolling_offset = 0
  end

  if creation_time > MAX_CREATION_TIME then
    -- this should only happen at around year 36759 (most likely a clock problem)
    return nil, "session maximum creation time exceeded"
  end

  do
    local meta_flags = meta.flags
    if meta_flags and has_flag(meta_flags, FLAG_FORGET) then
      flags = set_flag(flags, FLAG_FORGET)
    end
  end

  local data, data_size, cookie_chunks do
    data = self.data
    if self.enforce_same_subject then
      local count = #data
      if count > 1 then
        local subject = data[self.data_index][3]
        for i = count, 1, -1 do
          if data[i][3] ~= subject then
            remove(data, i)
          end
        end
      end
    end

    data, err = encode_json(data)
    if not data then
      return nil, errmsg(err, "unable to json encode session data")
    end

    data_size = #data

    local compression_threshold = self.compression_threshold
    if compression_threshold ~= 0 and data_size > compression_threshold then
      local deflated_data, err = deflate(data)
      if not deflated_data then
        log(NOTICE, "[session] unable to deflate session data (", err , ")")

      else
        if deflated_data then
          local deflated_size = #deflated_data
          if deflated_size < data_size then
            flags = set_flag(flags, FLAG_DEFLATE)
            data = deflated_data
            data_size = deflated_size
          end
        end
      end
    end

    data_size = base64_size(data_size)

    if storage then
      if data_size > MAX_DATA_SIZE then
        return nil, "session maximum data size exceeded"
      end

      cookie_chunks = 1
    else
      cookie_chunks, err = calculate_cookie_chunks(cookie_name_size, data_size)
      if not cookie_chunks then
        return nil, err
      end
    end
  end

  local idling_offset = 0

  local packed_flags          = bpack(FLAGS_SIZE, flags)
  local packed_data_size      = bpack(DATA_SIZE, data_size)
  local packed_creation_time  = bpack(CREATION_TIME_SIZE, creation_time)
  local packed_rolling_offset = bpack(ROLLING_OFFSET_SIZE, rolling_offset)
  local packed_idling_offset  = bpack(IDLING_OFFSET_SIZE, idling_offset)

  HEADER_BUFFER:reset()
  HEADER_BUFFER:put(COOKIE_TYPE, packed_flags, sid, packed_creation_time, packed_rolling_offset, packed_data_size)

  local ikm = self.ikm
  local aes_key, iv
  if remember then
    aes_key, err, iv = derive_aes_gcm_256_key_and_iv(ikm, sid, self.remember_safety)
  else
    aes_key, err, iv = derive_aes_gcm_256_key_and_iv(ikm, sid)
  end

  if not aes_key then
    return nil, errmsg(err, "unable to derive session encryption key")
  end

  local ciphertext, err, tag = encrypt_aes_256_gcm(aes_key, iv, data, HEADER_BUFFER:tostring())
  if not ciphertext then
    return nil, errmsg(err, "unable to encrypt session data")
  end

  HEADER_BUFFER:put(tag, packed_idling_offset)

  local mac, err = calculate_mac(ikm, sid, HEADER_BUFFER:tostring())
  if not mac then
    return nil, err
  end

  local header_decoded = HEADER_BUFFER:put(mac):get()
  local header_encoded, err = encode_base64url(header_decoded)
  if not header_encoded then
    return nil, errmsg(err, "unable to base64url encode session header")
  end

  local payload, err = encode_base64url(ciphertext)
  if not payload then
    return nil, errmsg(err, "unable to base64url encode session data")
  end

  local cookies = header["Set-Cookie"]
  local cookie_flags = self.cookie_flags

  local initial_chunk
  local ciphertext_encoded

  local remember_flags
  if remember then
    local max_age = self.remember_rolling_timeout
    if max_age == 0 or max_age > MAX_TTL then
      max_age = MAX_TTL
    end

    local expires = http_time(creation_time + max_age)
    remember_flags = fmt("; Expires=%s; Max-Age=%d", expires, max_age)
  end

  if cookie_chunks == 1 then
    local cookie_data
    if storage then
      ciphertext_encoded = payload
      if remember then
        cookie_data = fmt("%s=%s%s%s", cookie_name, header_encoded, cookie_flags, remember_flags)
      else
        cookie_data = fmt("%s=%s%s", cookie_name, header_encoded, cookie_flags)
      end

    else
      initial_chunk = payload
      if remember then
        cookie_data = fmt("%s=%s%s%s%s", cookie_name, header_encoded, payload, cookie_flags, remember_flags)
      else
        cookie_data = fmt("%s=%s%s%s", cookie_name, header_encoded, payload, cookie_flags)
      end
    end

    cookies, err = merge_cookies(cookies, cookie_name_size, cookie_name, cookie_data)
    if not cookies then
      return nil, err
    end

  else
    DATA_BUFFER:set(payload)

    initial_chunk = DATA_BUFFER:get(MAX_COOKIE_SIZE - HEADER_ENCODED_SIZE - cookie_name_size - 1)

    local cookie_data
    if remember then
      cookie_data = fmt("%s=%s%s%s%s", cookie_name, header_encoded, initial_chunk, cookie_flags, remember_flags)
    else
      cookie_data = fmt("%s=%s%s%s", cookie_name, header_encoded, initial_chunk, cookie_flags)
    end

    cookies, err = merge_cookies(cookies, cookie_name_size, cookie_name, cookie_data)
    if not cookies then
      return nil, err
    end

    for i = 2, cookie_chunks do
      local name = fmt("%s%d", cookie_name, i)
      cookie_data = DATA_BUFFER:get(MAX_COOKIE_SIZE - cookie_name_size - 2)
      if remember then
        cookie_data = fmt("%s=%s%s%s", name, cookie_data, cookie_flags, remember_flags)
      else
        cookie_data = fmt("%s=%s%s", name, cookie_data, cookie_flags)
      end
      cookies, err = merge_cookies(cookies, cookie_name_size + 1, name, cookie_data)
      if not cookies then
        return nil, err
      end
    end
  end

  if storage then
    local key, err = self.hash_storage_key(sid)
    if not key then
      return nil, err
    end

    DATA[1] = payload

    local info_data = self.info.data
    if info_data then
      info_data, err = encode_json(info_data)
      if not info_data then
        return nil, errmsg(err, "unable to json encode session info")
      end

      info_data, err = encode_base64url(info_data)
      if not info_data then
        return nil, errmsg(err, "unable to base64url encode session info")
      end

      DATA[2] = info_data

    else
      DATA[2] = nil
    end

    data, err = encode_json(DATA)
    if not data then
      return nil, errmsg(err, "unable to json encode session data")
    end

    local old_sid = meta.sid
    local old_key
    if old_sid then
      old_key, err = self.hash_storage_key(old_sid)
      if not old_key then
        log(WARN, "[session] ", err)
      end
    end

    local ttl = remember and self.remember_rolling_timeout or self.rolling_timeout
    if ttl == 0 or ttl > MAX_TTL then
      ttl = MAX_TTL
    end

    local store_metadata = get_store_metadata(self)

    local ok, err = storage:set(cookie_name, key, data, ttl, current_time, old_key, self.stale_ttl, store_metadata, remember)
    if not ok then
      return nil, errmsg(err, "unable to store session data")
    end

  else
    local old_data_size = meta.data_size
    if old_data_size then
      local old_cookie_chunks = calculate_cookie_chunks(cookie_name_size, old_data_size)
      if old_cookie_chunks and old_cookie_chunks > cookie_chunks then
        for i = cookie_chunks + 1, old_cookie_chunks do
          local name = fmt("%s%d", cookie_name, i)
          local cookie_data = fmt("%s=%s%s", name, cookie_flags, COOKIE_EXPIRE_FLAGS)
          cookies, err = merge_cookies(cookies, cookie_name_size + 1, name, cookie_data)
          if not cookies then
            return nil, err
          end
        end
      end
    end
  end

  header["Set-Cookie"] = cookies

  if remember then
    self.remember_meta = {
      timestamp      = current_time,
      flags          = flags,
      sid            = sid,
      creation_time  = creation_time,
      rolling_offset = rolling_offset,
      data_size      = data_size,
      idling_offset  = idling_offset,
      ikm            = ikm,
      header         = header_decoded,
      initial_chunk  = initial_chunk,
      ciphertext     = ciphertext_encoded,
    }

  else
    self.state = state or STATE_OPEN
    self.meta = {
      timestamp      = current_time,
      flags          = flags,
      sid            = sid,
      creation_time  = creation_time,
      rolling_offset = rolling_offset,
      data_size      = data_size,
      idling_offset  = idling_offset,
      ikm            = ikm,
      header         = header_decoded,
      initial_chunk  = initial_chunk,
      ciphertext     = ciphertext_encoded,
    }
  end

  return true
end


local function save_info(self, data, remember)
  local cookie_name
  local meta
  if remember then
    cookie_name = self.remember_cookie_name
    meta = self.remember_meta or {}
  else
    cookie_name = self.cookie_name
    meta = self.meta
  end

  local key, err = self.hash_storage_key(meta.sid)
  if not key then
    return nil, err
  end

  DATA[1] = meta.ciphertext
  DATA[2] = data

  data, err = encode_json(DATA)
  if not data then
    return nil, errmsg(err, "unable to json encode session data")
  end

  local current_time = time()

  local ttl = self.rolling_timeout
  if ttl == 0 or ttl > MAX_TTL then
    ttl = MAX_TTL
  end
  ttl = max(ttl - (current_time - meta.creation_time - meta.rolling_offset), 1)
  local ok, err = self.storage:set(cookie_name, key, data, ttl, current_time)
  if not ok then
    return nil, errmsg(err, "unable to store session info")
  end
end


local function destroy(self, remember)
  local cookie_name
  local meta
  if remember then
    cookie_name = self.remember_cookie_name
    meta = self.remember_meta or {}
  else
    cookie_name = self.cookie_name
    meta = self.meta
  end

  local cookie_name_size = #cookie_name
  local storage = self.storage

  local cookie_chunks = 1
  local data_size = meta.data_size
  if not storage and data_size then
    local err
    cookie_chunks, err = calculate_cookie_chunks(cookie_name_size, data_size)
    if not cookie_chunks then
      return nil, err
    end
  end

  local cookie_flags = self.cookie_flags
  local cookie_data = fmt("%s=%s%s", cookie_name, cookie_flags, COOKIE_EXPIRE_FLAGS)
  local cookies, err = merge_cookies(header["Set-Cookie"], cookie_name_size, cookie_name, cookie_data)
  if not cookies then
    return nil, err
  end

  if cookie_chunks > 1 then
    for i = 2, cookie_chunks do
      local name = fmt("%s%d", cookie_name, i)
      cookie_data = fmt("%s=%s%s", name, cookie_flags, COOKIE_EXPIRE_FLAGS)
      cookies, err = merge_cookies(cookies, cookie_name_size + 1, name, cookie_data)
      if not cookies then
        return nil, err
      end
    end
  end

  if storage then
    local sid = meta.sid
    if sid then
      local key, err = self.hash_storage_key(sid)
      if not key then
        return nil, err
      end

      local ok, err = storage:delete(cookie_name, key, meta.timestamp, get_store_metadata(self))
      if not ok then
        return nil, errmsg(err, "unable to destroy session")
      end
    end
  end

  header["Set-Cookie"] = cookies

  self.state = STATE_CLOSED

  return true
end


local function clear_request_cookie(self, remember)
  local cookies = var.http_cookie
  if not cookies or cookies == "" then
    return
  end

  local cookie_name
  if remember then
    cookie_name = self.remember_cookie_name
  else
    cookie_name = self.cookie_name
  end

  local cookie_name_size = #cookie_name

  local cookie_chunks
  if self.storage then
    cookie_chunks = 1
  else
    local data_size = remember                     and
                      self.remember_meta           and
                      self.remember_meta.data_size or
                      self.meta.data_size
    cookie_chunks = calculate_cookie_chunks(cookie_name_size, data_size) or 1
  end

  HIDE_BUFFER:reset()

  local size = #cookies
  local name
  local skip = false
  local start = 1
  for i = 1, size do
    local b = byte(cookies, i)
    if name then
      if b == SEMICOLON_BYTE or i == size then
        if not skip then
          local value
          if b == SEMICOLON_BYTE then
            value = trim(sub(cookies, start, i - 1))
          else
            value = trim(sub(cookies, start))
          end

          if value ~= "" then
            HIDE_BUFFER:put(value)
          end

          if i ~= size then
            HIDE_BUFFER:put("; ")
          end
        end

        if i == size then
          break
        end

        name = nil
        start = i + 1
        skip = false
      end

    else
      if b == EQUALS_BYTE or b == SEMICOLON_BYTE then
        name = sub(cookies, start, i - 1)
      elseif i == size then
        name = sub(cookies, start, i)
      end

      if name then
        name = trim(name)
        if b == SEMICOLON_BYTE or i == size then
          if name ~= "" then
            HIDE_BUFFER:put(name)
            if i ~= size then
              HIDE_BUFFER:put(";")
            end

          elseif i == size then
            break
          end

          name = nil

        else
          if name == cookie_name then
            skip = true

          elseif cookie_chunks > 1 then
            local chunk_number = tonumber(sub(name, -1), 10)
            if chunk_number and chunk_number > 1 and chunk_number <= cookie_chunks
                            and sub(name, 1, -2) == cookie_name
            then
              skip = true
            end
          end

          if not skip then
            if name ~= "" then
              HIDE_BUFFER:put(name)
            end

            if b == EQUALS_BYTE then
              HIDE_BUFFER:put("=")
            end
          end
        end

        start = i + 1
      end
    end
  end

  if #HIDE_BUFFER == 0 then
    clear_request_header("Cookie")
  else
    set_request_header("Cookie", HIDE_BUFFER:get())
  end

  return true
end



local function get_remember(self)
  local flags = self.meta.flags
  if flags and has_flag(flags, FLAG_FORGET) then
    return false
  end

  if has_flag(self.flags, FLAG_FORGET) then
    return false
  end

  return self.remember
end


local function set_property_header(self, property_header, set_header)
  local name = HEADERS[property_header]
  if not name then
    return
  end

  local value = get_property(self, property_header)
  if not value then
    return
  end

  set_header(name, value)
end


local function set_property_headers(self, headers, set_header)
  if not headers then
    return
  end

  local count = #headers
  if count == 0 then
    return
  end

  for i = 1, count do
    set_property_header(self, headers[i], set_header)
  end
end


local function set_property_headers_vararg(self, set_header, count, ...)
  if count == 1 then
    local header_or_headers = select(1, ...)
    if type(header_or_headers) == "table" then
      return set_property_headers(self, header_or_headers, set_header)
    end

    return set_property_header(self, header_or_headers, set_header)
  end

  for i = 1, count do
    local property_header = select(i, ...)
    set_property_header(self, property_header, set_header)
  end
end


---
-- Session
-- @section instance


local fake_info_mt = {}


function fake_info_mt:set(key, value)
  local session = self.session
  assert(session.state ~= STATE_CLOSED, "unable to set session info on closed session")
  session.data[session.data_index][1]["@" .. key] = value
end


function fake_info_mt:get(key)
  local session = self.session
  assert(session.state ~= STATE_CLOSED, "unable to get session info on closed session")
  return session.data[session.data_index][1]["@" .. key]
end


function fake_info_mt:save()
  local session = self.session
  assert(session.state == STATE_OPEN, "unable to save session info on nonexistent or closed session")
  return session:save()
end


fake_info_mt.__index = fake_info_mt


local fake_info = {}


function fake_info.new(session)
  return setmetatable({
    session = session,
    data = false,
  }, fake_info_mt)
end


local info_mt = {}


info_mt.__index = info_mt


---
-- Set a value in session information store.
--
-- @function instance.info:set
-- @tparam string key key
-- @param value value
function info_mt:set(key, value)
  local session = self.session
  assert(session.state ~= STATE_CLOSED, "unable to set session info on closed session")
  local audience = session.data[session.data_index][2]
  local data = self.data
  if data then
    if data[audience] then
      data[audience][key] = value

    else
      data[audience] = {
        [key] = value,
      }
    end

  else
    self.data = {
      [audience] = {
        [key] = value,
      },
    }
  end
end


---
-- Get a value from session information store.
--
-- @function instance.info:get
-- @tparam string key key
-- @return value
function info_mt:get(key)
  local session = self.session
  assert(session.state ~= STATE_CLOSED, "unable to get session info on closed session")
  local data = self.data
  if not data then
    return
  end

  local audience = session.data[session.data_index][2]
  data = self.data[audience]
  if not data then
    return
  end

  return data[key]
end


---
-- Save information.
--
-- Only updates backend storage. Does not send a new cookie.
--
-- @function instance.info:save
-- @treturn true|nil ok
-- @treturn string error message
function info_mt:save()
  local session = self.session
  assert(session.state == STATE_OPEN, "unable to save session info on nonexistent or closed session")
  local data = self.data
  if not data then
    return true
  end

  local err
  data, err = encode_json(data)
  if not data then
    return nil, errmsg(err, "unable to json encode session info")
  end

  data, err = encode_base64url(data)
  if not data then
    return nil, errmsg(err, "unable to base64url encode session info")
  end

  local ok, err = save_info(session, data)
  if not ok then
    return nil, err
  end

  if get_remember(session) then
    if not session.remember_meta then
      local remembered = open(self, true, true)
      if not remembered then
        return save(session, nil, true)
      end
    end

    return save_info(session, data, true)
  end

  return true
end


local info = {}


function info.new(session)
  return setmetatable({
    session = session,
    data = false,
  }, info_mt)
end


local metatable = {}


metatable.__index = metatable


function metatable.__newindex()
  error("attempt to update a read-only table", 2)
end


---
-- Set session data.
--
-- @function instance:set_data
-- @tparam table data data
--
-- @usage
-- local session, err, exists = require "resty.session".open()
-- if not exists then
--   session:set_data({
--     cart = {},
--   })
--   session:save()
-- end
function metatable:set_data(data)
  assert(self.state ~= STATE_CLOSED, "unable to set session data on closed session")
  assert(type(data) == "table", "invalid session data")
  self.data[self.data_index][1] = data
end


---
-- Get session data.
--
-- @function instance:get_data
-- @treturn table value
--
-- @usage
-- local session, err, exists = require "resty.session".open()
-- if exists then
--   local data = session:get_data()
--   ngx.req.set_header("Authorization", "Bearer " .. data.access_token)
-- end
function metatable:get_data()
  assert(self.state ~= STATE_CLOSED, "unable to set session data on closed session")
  return self.data[self.data_index][1]
end


---
-- Set a value in session.
--
-- @function instance:set
-- @tparam string key key
-- @param value value
--
-- local session, err, exists = require "resty.session".open()
-- if not exists then
--   session:set("access-token", "eyJ...")
--   session:save()
-- end
function metatable:set(key, value)
  assert(self.state ~= STATE_CLOSED, "unable to set session data value on closed session")
  if self.storage or byte(key, 1) ~= AT_BYTE then
    self.data[self.data_index][1][key] = value
  else
    self.data[self.data_index][1]["$" .. key] = value
  end
end


---
-- Get a value from session.
--
-- @function instance:get
-- @tparam string key key
-- @return value
--
-- @usage
-- local session, err, exists = require "resty.session".open()
-- if exists then
--   local access_token = session:get("access-token")
--   ngx.req.set_header("Authorization", "Bearer " .. access_token)
-- end
function metatable:get(key)
  assert(self.state ~= STATE_CLOSED, "unable to get session data value on closed session")
  if self.storage or byte(key, 1) ~= AT_BYTE then
    return self.data[self.data_index][1][key]
  else
    return self.data[self.data_index][1]["$" .. key]
  end
end


---
-- Set session audience.
--
-- @function instance:set_audience
-- @tparam string audience audience
--
-- @usage
-- local session = require "resty.session".new()
-- session.set_audience("my-service")
function metatable:set_audience(audience)
  assert(self.state ~= STATE_CLOSED, "unable to set audience on closed session")

  local data = self.data
  local data_index = self.data_index
  local current_audience = data[data_index][2]
  if audience == current_audience then
    return
  end

  local info_data = self.info.data
  if info_data then
    info_data[audience] = info_data[current_audience]
    info_data[current_audience] = nil
  end

  local count = #data
  if count == 1 then
    data[1][2] = audience
    return
  end

  local previous_index
  for i = 1, count do
    if data[i][2] == audience then
      previous_index = i
      break
    end
  end

  data[data_index][2] = audience

  if not previous_index or previous_index == data_index then
    return
  end

  remove(data, previous_index)

  if previous_index < data_index then
    self.data_index = data_index - 1
  end
end


---
-- Get session audience.
--
-- @function instance:get_audience
-- @treturn string audience
function metatable:get_audience()
  assert(self.state ~= STATE_CLOSED, "unable to get audience on closed session")
  return self.data[self.data_index][2]
end


---
-- Set session subject.
--
-- @function instance:set_subject
-- @tparam string subject subject
--
-- @usage
-- local session = require "resty.session".new()
-- session.set_subject("john@doe.com")
function metatable:set_subject(subject)
  assert(self.state ~= STATE_CLOSED, "unable to set subject on closed session")
  self.data[self.data_index][3] = subject
end


---
-- Get session subject.
--
-- @function instance:get_subject
-- @treturn string subject
--
-- @usage
-- local session, err, exists = require "resty.session".open()
-- if exists then
--   local subject = session.get_subject()
-- end
function metatable:get_subject()
  assert(self.state ~= STATE_CLOSED, "unable to get subject on closed session")
  return self.data[self.data_index][3]
end


---
-- Get session property.
--
-- Possible property names:
-- * `"id"`: 43 bytes session id (same as nonce, but base64 url-encoded)
-- * `"nonce"`: 32 bytes nonce (same as session id but in raw bytes)
-- * `"audience"`: Current session audience
-- * `"subject"`: Current session subject
-- * `"timeout"`: Closest timeout (in seconds) (what's left of it)
-- * `"idling-timeout`"`: Session idling timeout (in seconds) (what's left of it)
-- * `"rolling-timeout`"`: Session rolling timeout (in seconds) (what's left of it)
-- * `"absolute-timeout`"`: Session absolute timeout (in seconds) (what's left of it)
--
-- @function instance:get_property
-- @treturn string|number metadata
--
-- @usage
-- local session, err, exists = require "resty.session".open()
-- if exists then
--   local timeout = session.get_property("timeout")
-- end
function metatable:get_property(name)
  assert(self.state ~= STATE_CLOSED, "unable to get session property on closed session")
  return get_property(self, name)
end


---
-- Set persistent sessions on/off.
--
-- In many login forms user is given an option for "remember me".
-- You can call this function based on what user selected.
--
-- @function instance:set_remember
-- @tparam boolean value `true` to enable persistent session, `false` to disable them
function metatable:set_remember(value)
  assert(self.state ~= STATE_CLOSED, "unable to set remember on closed session")
  assert(type(value) == "boolean", "invalid remember value")
  if value == false then
    set_flag(self.flags, FLAG_FORGET)
  else
    unset_flag(self.flags, FLAG_FORGET)
  end

  self.remember = value
end


---
-- Get state of persistent sessions.
--
-- @function instance:get_remember
-- @treturn boolean `true` when persistent sessions are enabled, otherwise `false`
function metatable:get_remember()
  assert(self.state ~= STATE_CLOSED, "unable to get remember on closed session")
  return get_remember(self)
end


---
-- Open a session.
--
-- This can be used to open a session.
--
-- @function instance:open
-- @treturn true|nil ok
-- @treturn string error message
function metatable:open()
  local exists, err, audience_error = open(self)
  if exists then
    return true
  end

  if audience_error then
    return nil, err
  end

  if not self.remember then
    return nil, err
  end

  local remembered = open(self, true)
  if not remembered then
    return nil, err
  end

  local ok, err = save(self, nil, true)
  if not ok then
    return nil, err
  end

  self.state = STATE_NEW
  self.meta = DEFAULT_META

  local ok, err = save(self, STATE_OPEN)
  if not ok then
    return nil, err
  end

  return true
end


---
-- Save the session.
--
-- Saves the session data and issues a new session cookie with a new session id.
-- When `remember` is enabled, it will also issue a new persistent cookie and
-- possibly save the data in backend store.
--
-- @function instance:save
-- @treturn true|nil ok
-- @treturn string error message
function metatable:save()
  assert(self.state ~= STATE_CLOSED, "unable to save closed session")

  local ok, err = save(self)
  if not ok then
    return nil, err
  end

  if get_remember(self) then
    if not self.remember_meta then
      open(self, true, true)
    end

    local ok, err = save(self, nil, true)
    if not ok then
      log(WARN, "[session] ", err)
    end
  end

  return true
end


---
-- Touch the session.
--
-- Updates idling offset of the session by sending an updated session cookie.
-- It only sends the client cookie and never calls any backend session store
-- APIs. Normally the `session:refresh` is used to call this indirectly.
--
-- @function instance:touch
-- @treturn true|nil ok
-- @treturn string error message
function metatable:touch()
  assert(self.state == STATE_OPEN, "unable to touch nonexistent or closed session")

  local meta = self.meta
  local idling_offset = min(time() - meta.creation_time - meta.rolling_offset, MAX_IDLING_OFFSET)

  HEADER_BUFFER:reset():put(sub(meta.header, 1, HEADER_TOUCH_SIZE),
                            bpack(IDLING_OFFSET_SIZE, idling_offset))

  local mac, err = calculate_mac(meta.ikm, meta.sid, HEADER_BUFFER:tostring())
  if not mac then
    return nil, err
  end

  local payload_header = HEADER_BUFFER:put(mac):get()

  meta.idling_offset = idling_offset
  meta.header        = payload_header

  payload_header, err = encode_base64url(payload_header)
  if not payload_header then
    return nil, errmsg(err, "unable to base64url encode session header")
  end

  local cookie_flags = self.cookie_flags
  local cookie_name = self.cookie_name
  local cookie_data
  if self.storage then
    cookie_data = fmt("%s=%s%s", cookie_name, payload_header, cookie_flags)
  else
    cookie_data = fmt("%s=%s%s%s", cookie_name, payload_header, meta.initial_chunk, cookie_flags)
  end

  header["Set-Cookie"] = merge_cookies(header["Set-Cookie"], #cookie_name, cookie_name, cookie_data)

  return true
end


---
-- Refresh the session.
--
-- Either saves the session (creating a new session id) or touches the session
-- depending on whether the rolling timeout is getting closer, which means
-- by default when 3/4 of rolling timeout is spent - 45 minutes with default
-- rolling timeout of an hour. The touch has a threshold, by default one minute,
-- so it may be skipped in some cases (you can call `session:touch()` to force it).
--
-- @function instance:refresh
-- @treturn true|nil ok
-- @treturn string error message
function metatable:refresh()
  assert(self.state == STATE_OPEN, "unable to refresh nonexistent or closed session")

  local rolling_timeout = self.rolling_timeout
  local idling_timeout = self.idling_timeout
  if rolling_timeout == 0 and idling_timeout == 0 then
    return true
  end

  local meta = self.meta
  local rolling_elapsed = meta.timestamp - meta.creation_time - meta.rolling_offset

  if rolling_timeout > 0 then
    if rolling_elapsed > floor(rolling_timeout * 0.75) then
      -- TODO: in case session was modified before calling this function, the possible remember me cookie needs to be saved too?
      return save(self)
    end
  end

  if idling_timeout > 0 then
    local idling_elapsed = rolling_elapsed - meta.idling_offset
    if idling_elapsed > self.touch_threshold then
      return self:touch()
    end
  end

  return true
end


---
-- Logout the session.
--
-- Logout either destroys the session or just clears the data for the current audience,
-- and saves it (logging out from the current audience).
--
-- @function instance:logout
-- @treturn true|nil ok
-- @treturn string error message
function metatable:logout()
  assert(self.state == STATE_OPEN, "unable to logout nonexistent or closed session")

  local data = self.data
  if #data == 1 then
    return self:destroy()
  end

  local data_index = self.data_index
  local info_store = self.info
  local info_data = info_store and info_store.data
  if info_data then
    local audience = data[data_index][2]
    info_data[audience] = nil
    if isempty(info_data) then
      info_store.data = false
    end
  end

  remove(data, data_index)

  local ok, err = save(self, STATE_CLOSED)
  if not ok then
    return nil, err
  end

  if get_remember(self) then
    if not self.remember_meta then
      open(self, true, true)
    end
    local ok, err = save(self, nil, true)
    if not ok then
      log(WARN, "[session] ", err)
    end
  end

  return true
end


---
-- Destroy the session.
--
-- Destroy the session and clear the cookies.
--
-- @function instance:destroy
-- @treturn true|nil ok
-- @treturn string error message
function metatable:destroy()
  assert(self.state == STATE_OPEN, "unable to destroy nonexistent or closed session")

  local ok, err = destroy(self)
  if not ok then
    return nil, err
  end

  if get_remember(self) then
    if not self.remember_meta then
      local remembered = open(self, true, true)
      if not remembered then
        return true
      end
    end

    ok, err = destroy(self, true)
    if not ok then
      return nil, err
    end
  end

  return true
end


---
-- Close the session.
--
-- Just closes the session instance so that it cannot be used anymore.
--
-- @function instance:close
function metatable:close()
  self.state = STATE_CLOSED
end


---
-- Clear the request session cookie.
--
-- Modifies the request headers by removing the session related
-- cookies. This is useful when you use the session library on
-- a proxy server and don't want the session cookies to be forwarded
-- to the upstream service.
--
-- @function instance:clear_request_cookie
function metatable:clear_request_cookie()
  assert(self.state == STATE_OPEN, "unable to hide nonexistent or closed session")

  local ok = clear_request_cookie(self)
  if not ok then
    log(NOTICE, "[session] unable to clear session request cookie")
  end

  if get_remember(self) then
    ok = clear_request_cookie(self, true)
    if not ok then
      log(NOTICE, "[session] unable to clear persistent session request cookie")
    end
  end
end


---
-- Sets request and response headers.
--
-- @function instance:set_headers
-- @tparam[opt] string ...
function metatable:set_headers(...)
  assert(self.state == STATE_OPEN, "unable to set request/response headers of nonexistent or closed session")

  local count = select("#", ...)
  if count == 0 then
    set_property_headers(self, self.request_headers, set_request_header)
    set_property_headers(self, self.response_headers, set_response_header)
    return
  end

  set_property_headers_vararg(self, set_request_header, count, ...)
  set_property_headers_vararg(self, set_response_header, count, ...)
end


---
-- Set request headers.
--
-- @function instance:set_request_headers
-- @tparam[opt] string ...
function metatable:set_request_headers(...)
  assert(self.state == STATE_OPEN, "unable to set request headers of nonexistent or closed session")

  local count = select("#", ...)
  if count == 0 then
    set_property_headers(self, self.request_headers, set_request_header)
    return
  end

  set_property_headers_vararg(self, set_request_header, count, ...)
end


---
-- Set response headers.
--
-- @function instance:set_response_headers
-- @tparam[opt] string ...
function metatable:set_response_headers(...)
  assert(self.state == STATE_OPEN, "unable to set response headers of nonexistent or closed session")

  local count = select("#", ...)
  if count == 0 then
    set_property_headers(self, self.response_headers, set_response_header)
    return
  end

  set_property_headers_vararg(self, set_response_header, count, ...)
end



local session = {
  _VERSION = "4.0.3",
  metatable = metatable,
}


---
-- Configuration
-- @section configuration


---
-- Session configuration.
-- @field secret Secret used for the key derivation. The secret is hashed with SHA-256 before using it. E.g. `"RaJKp8UQW1"`.
-- @field secret_fallbacks Array of secrets that can be used as alternative secrets (when doing key rotation), E.g. `{ "6RfrAYYzYq", "MkbTkkyF9C" }`.
-- @field ikm Initial key material (or ikm) can be specified directly (without using a secret) with exactly 32 bytes of data. E.g. `"5ixIW4QVMk0dPtoIhn41Eh1I9enP2060"`
-- @field ikm_fallbacks Array of initial key materials that can be used as alternative keys (when doing key rotation), E.g. `{ "QvPtlPKxOKdP5MCu1oI3lOEXIVuDckp7" }`.
-- @field cookie_prefix Cookie prefix, use `nil`, `"__Host-"` or `"__Secure-"` (defaults to `nil`)
-- @field cookie_name Session cookie name, e.g. `"session"` (defaults to `"session"`)
-- @field cookie_path Cookie path, e.g. `"/"` (defaults to `"/"`)
-- @field cookie_domain Cookie domain, e.g. `"example.com"` (defaults to `nil`)
-- @field cookie_http_only Mark cookie HTTP only, use `true` or `false` (defaults to `true`)
-- @field cookie_secure Mark cookie secure, use `nil`, `true` or `false` (defaults to `nil`)
-- @field cookie_priority Cookie priority, use `nil`, `"Low"`, `"Medium"`, or `"High"` (defaults to `nil`)
-- @field cookie_same_site Cookie same-site policy, use `nil`, `"Lax"`, `"Strict"`, `"None"`, or `"Default"` (defaults to `"Lax"`)
-- @field cookie_same_party Mark cookie with same party flag, use `nil`, `true`, or `false` (default: `nil`)
-- @field cookie_partitioned Mark cookie with partitioned flag, use `nil`, `true`, or `false` (default: `nil`)
-- @field remember Enable or disable persistent sessions, use `nil`, `true`, or `false` (defaults to `false`)
-- @field remember_safety Remember cookie key derivation complexity, use `nil`, `"None"` (fast), `"Low"`, `"Medium"`, `"High"` or `"Very High"` (slow) (defaults to `"Medium"`)
-- @field remember_cookie_name Persistent session cookie name, e.g. `"remember"` (defaults to `"remember"`)
-- @field audience Session audience, e.g. `"my-application"` (defaults to `"default"`)
-- @field subject Session subject, e.g. `"john.doe@example.com"` (defaults to `nil`)
-- @field enforce_same_subject When set to `true`, audiences need to share the same subject. The library removes non-subject matching audience data on save.
-- @field stale_ttl When session is saved a new session is created, stale ttl specifies how long the old one can still be used, e.g. `10` (defaults to `10`) (in seconds)
-- @field idling_timeout Idling timeout specifies how long the session can be inactive until it is considered invalid, e.g. `900` (defaults to `900`, or 15 minutes) (in seconds)
-- @field rolling_timeout Rolling timeout specifies how long the session can be used until it needs to be renewed, e.g. `3600` (defaults to `3600`, or an hour) (in seconds)
-- @field absolute_timeout Absolute timeout limits how long the session can be renewed, until re-authentication is required, e.g. `86400` (defaults to `86400`, or a day) (in seconds)
-- @field remember_rolling_timeout Remember timeout specifies how long the persistent session is considered valid, e.g. `604800` (defaults to `604800`, or a week) (in seconds)
-- @field remember_absolute_timeout Remember absolute timeout limits how long the persistent session can be renewed, until re-authentication is required, e.g. `2592000` (defaults to `2592000`, or 30 days) (in seconds)
-- @field hash_storage_key Whether to hash or not the storage key. With storage key hashed it is impossible to decrypt data on server side without having a cookie too (defaults to `false`).
-- @field hash_subject Whether to hash or not the subject when `store_metadata` is enabled, e.g. for PII reasons (defaults to `false`).
-- @field store_metadata Whether to also store metadata of sessions, such as collecting data of sessions for a specific audience belonging to a specific subject (defaults to `false`).
-- @field touch_threshold Touch threshold controls how frequently or infrequently the `session:refresh` touches the cookie, e.g. `60` (defaults to `60`, or a minute) (in seconds)
-- @field compression_threshold Compression threshold controls when the data is deflated, e.g. `1024` (defaults to `1024`, or a kilobyte) (in bytes)
-- @field request_headers Set of headers to send to upstream, use `id`, `audience`, `subject`, `timeout`, `idling-timeout`, `rolling-timeout`, `absolute-timeout`. E.g. `{ "id", "timeout" }` will set `Session-Id` and `Session-Timeout` request headers when `set_headers` is called.
-- @field response_headers Set of headers to send to downstream, use `id`, `audience`, `subject`, `timeout`, `idling-timeout`, `rolling-timeout`, `absolute-timeout`. E.g. `{ "id", "timeout" }` will set `Session-Id` and `Session-Timeout` response headers when `set_headers` is called.
-- @field storage Storage is responsible of storing session data, use `nil` or `"cookie"` (data is stored in cookie), `"dshm"`, `"file"`, `"memcached"`, `"mysql"`, `"postgres"`, `"redis"`, or `"shm"`, or give a name of custom module (`"custom-storage"`), or a `table` that implements session storage interface (defaults to `nil`)
-- @field dshm Configuration for dshm storage, e.g. `{ prefix = "sessions" }`
-- @field file Configuration for file storage, e.g. `{ path = "/tmp", suffix = "session" }`
-- @field memcached Configuration for memcached storage, e.g. `{ prefix = "sessions" }`
-- @field mysql Configuration for MySQL / MariaDB storage, e.g. `{ database = "sessions" }`
-- @field postgres Configuration for Postgres storage, e.g. `{ database = "sessions" }`
-- @field redis Configuration for Redis / Redis Sentinel / Redis Cluster storages, e.g. `{ prefix = "sessions" }`
-- @field shm Configuration for shared memory storage, e.g. `{ zone = "sessions" }`
-- @field ["custom-storage"] Custom storage (loaded with `require "custom-storage"`) configuration
-- @table configuration


---
-- Initialization
-- @section initialization


---
-- Initialize the session library.
--
-- This function can be called on `init` or `init_worker` phases on OpenResty
-- to set global default configuration to all session instances created by this
-- library.
--
-- @function module.init
-- @tparam[opt] table configuration session @{configuration} overrides
--
-- @usage
-- require "resty.session".init({
--   audience = "my-application",
--   storage = "redis",
--   redis = {
--     username = "session",
--     password = "storage",
--   },
-- })
function session.init(configuration)
  if configuration then
    local ikm = configuration.ikm
    if ikm then
      assert(#ikm == KEY_SIZE, "invalid ikm size")
      DEFAULT_IKM = ikm

    else
      local secret = configuration.secret
      if secret then
        DEFAULT_IKM = assert(sha256(secret))
      end
    end

    local ikm_fallbacks = configuration.ikm_fallbacks
    if ikm_fallbacks then
      local count = #ikm_fallbacks
      for i = 1, count do
        assert(#ikm_fallbacks[i] == KEY_SIZE, "invalid ikm size in ikm_fallbacks")
      end

      DEFAULT_IKM_FALLBACKS = ikm_fallbacks

    else
      local secret_fallbacks = configuration.secret_fallbacks
      if secret_fallbacks then
        local count = #secret_fallbacks
        if count > 0 then
          DEFAULT_IKM_FALLBACKS = table_new(count, 0)
          for i = 1, count do
            DEFAULT_IKM_FALLBACKS[i] = assert(sha256(secret_fallbacks[i]))
          end

        else
          DEFAULT_IKM_FALLBACKS = nil
        end
      end
    end

    local request_headers = configuration.request_headers
    if request_headers then
      local count = #request_headers
      for i = 1, count do
        assert(HEADERS[request_headers[i]], "invalid request header")
      end

      DEFAULT_REQUEST_HEADERS = request_headers
    end

    local response_headers = configuration.response_headers
    if response_headers then
      local count = #response_headers
      for i = 1, count do
        assert(HEADERS[response_headers[i]], "invalid response header")
      end

      DEFAULT_RESPONSE_HEADERS = response_headers
    end

    DEFAULT_COOKIE_NAME               = configuration.cookie_name               or DEFAULT_COOKIE_NAME
    DEFAULT_COOKIE_PATH               = configuration.cookie_path               or DEFAULT_COOKIE_PATH
    DEFAULT_COOKIE_DOMAIN             = configuration.cookie_domain             or DEFAULT_COOKIE_DOMAIN
    DEFAULT_COOKIE_SAME_SITE          = configuration.cookie_same_site          or DEFAULT_COOKIE_SAME_SITE
    DEFAULT_COOKIE_PRIORITY           = configuration.cookie_priority           or DEFAULT_COOKIE_PRIORITY
    DEFAULT_COOKIE_PREFIX             = configuration.cookie_prefix             or DEFAULT_COOKIE_PREFIX
    DEFAULT_REMEMBER_SAFETY           = configuration.remember_safety           or DEFAULT_REMEMBER_SAFETY
    DEFAULT_REMEMBER_COOKIE_NAME      = configuration.remember_cookie_name      or DEFAULT_REMEMBER_COOKIE_NAME
    DEFAULT_AUDIENCE                  = configuration.audience                  or DEFAULT_AUDIENCE
    DEFAULT_SUBJECT                   = configuration.subject                   or DEFAULT_SUBJECT
    DEFAULT_STALE_TTL                 = configuration.stale_ttl                 or DEFAULT_STALE_TTL
    DEFAULT_IDLING_TIMEOUT            = configuration.idling_timeout            or DEFAULT_IDLING_TIMEOUT
    DEFAULT_ROLLING_TIMEOUT           = configuration.rolling_timeout           or DEFAULT_ROLLING_TIMEOUT
    DEFAULT_ABSOLUTE_TIMEOUT          = configuration.absolute_timeout          or DEFAULT_ABSOLUTE_TIMEOUT
    DEFAULT_REMEMBER_ROLLING_TIMEOUT  = configuration.remember_rolling_timeout  or DEFAULT_REMEMBER_ROLLING_TIMEOUT
    DEFAULT_REMEMBER_ABSOLUTE_TIMEOUT = configuration.remember_absolute_timeout or DEFAULT_REMEMBER_ABSOLUTE_TIMEOUT
    DEFAULT_TOUCH_THRESHOLD           = configuration.touch_threshold           or DEFAULT_TOUCH_THRESHOLD
    DEFAULT_COMPRESSION_THRESHOLD     = configuration.compression_threshold     or DEFAULT_COMPRESSION_THRESHOLD
    DEFAULT_STORAGE                   = configuration.storage                   or DEFAULT_STORAGE

    local cookie_http_only = configuration.cookie_http_only
    if cookie_http_only ~= nil then
      DEFAULT_COOKIE_HTTP_ONLY = cookie_http_only
    end

    local cookie_same_party = configuration.cookie_same_party
    if cookie_same_party ~= nil then
      DEFAULT_COOKIE_SAME_PARTY = cookie_same_party
    end

    local cookie_partitioned = configuration.cookie_partitioned
    if cookie_partitioned ~= nil then
      DEFAULT_COOKIE_PARTITIONED = cookie_partitioned
    end

    local cookie_secure = configuration.cookie_secure
    if cookie_secure ~= nil then
      DEFAULT_COOKIE_SECURE = cookie_secure
    end

    local remember = configuration.remember
    if remember ~= nil then
      DEFAULT_REMEMBER = remember
    end

    local hash_storage_key = configuration.hash_storage_key
    if hash_storage_key ~= nil then
      DEFAULT_HASH_STORAGE_KEY = hash_storage_key
    end

    local hash_subject = configuration.hash_subject
    if hash_subject ~= nil then
      DEFAULT_HASH_SUBJECT = hash_subject
    end

    local store_metadate = configuration.store_metadata
    if store_metadate ~= nil then
      DEFAULT_STORE_METADATA = store_metadate
    end

    local enforce_same_subject = configuration.enforce_same_subject
    if enforce_same_subject ~= nil then
      DEFAULT_ENFORCE_SAME_SUBJECT = enforce_same_subject
    end
  end

  if not DEFAULT_IKM then
    DEFAULT_IKM = assert(sha256(assert(rand_bytes(KEY_SIZE))))
  end

  if type(DEFAULT_STORAGE) == "string" then
    DEFAULT_STORAGE = load_storage(DEFAULT_STORAGE, configuration)
  end
end


---
-- Constructors
-- @section constructors


---
-- Create a new session.
--
-- This creates a new session instance.
--
-- @function module.new
-- @tparam[opt] table configuration session @{configuration} overrides
-- @treturn table session instance
--
-- @usage
-- local session = require "resty.session".new()
-- -- OR
-- local session = require "resty.session".new({
--   audience = "my-application",
-- })
function session.new(configuration)
  local cookie_name               = configuration and configuration.cookie_name               or DEFAULT_COOKIE_NAME
  local cookie_path               = configuration and configuration.cookie_path               or DEFAULT_COOKIE_PATH
  local cookie_domain             = configuration and configuration.cookie_domain             or DEFAULT_COOKIE_DOMAIN
  local cookie_same_site          = configuration and configuration.cookie_same_site          or DEFAULT_COOKIE_SAME_SITE
  local cookie_priority           = configuration and configuration.cookie_priority           or DEFAULT_COOKIE_PRIORITY
  local cookie_prefix             = configuration and configuration.cookie_prefix             or DEFAULT_COOKIE_PREFIX
  local remember_safety           = configuration and configuration.remember_safety           or DEFAULT_REMEMBER_SAFETY
  local remember_cookie_name      = configuration and configuration.remember_cookie_name      or DEFAULT_REMEMBER_COOKIE_NAME
  local audience                  = configuration and configuration.audience                  or DEFAULT_AUDIENCE
  local subject                   = configuration and configuration.subject                   or DEFAULT_SUBJECT
  local stale_ttl                 = configuration and configuration.stale_ttl                 or DEFAULT_STALE_TTL
  local idling_timeout            = configuration and configuration.idling_timeout            or DEFAULT_IDLING_TIMEOUT
  local rolling_timeout           = configuration and configuration.rolling_timeout           or DEFAULT_ROLLING_TIMEOUT
  local absolute_timeout          = configuration and configuration.absolute_timeout          or DEFAULT_ABSOLUTE_TIMEOUT
  local remember_rolling_timeout  = configuration and configuration.remember_rolling_timeout  or DEFAULT_REMEMBER_ROLLING_TIMEOUT
  local remember_absolute_timeout = configuration and configuration.remember_absolute_timeout or DEFAULT_REMEMBER_ABSOLUTE_TIMEOUT
  local touch_threshold           = configuration and configuration.touch_threshold           or DEFAULT_TOUCH_THRESHOLD
  local compression_threshold     = configuration and configuration.compression_threshold     or DEFAULT_COMPRESSION_THRESHOLD
  local storage                   = configuration and configuration.storage                   or DEFAULT_STORAGE
  local ikm                       = configuration and configuration.ikm
  local ikm_fallbacks             = configuration and configuration.ikm_fallbacks
  local request_headers           = configuration and configuration.request_headers
  local response_headers          = configuration and configuration.response_headers

  local cookie_http_only = configuration and configuration.cookie_http_only
  if cookie_http_only == nil then
    cookie_http_only = DEFAULT_COOKIE_HTTP_ONLY
  end

  local cookie_secure = configuration and configuration.cookie_secure
  if cookie_secure == nil then
    cookie_secure = DEFAULT_COOKIE_SECURE
  end

  local cookie_same_party = configuration and configuration.cookie_same_party
  if cookie_same_party == nil then
    cookie_same_party = DEFAULT_COOKIE_SAME_PARTY
  end

  local cookie_partitioned = configuration and configuration.cookie_partitioned
  if cookie_partitioned == nil then
    cookie_partitioned = DEFAULT_COOKIE_PARTITIONED
  end

  local remember = configuration and configuration.remember
  if remember == nil then
    remember = DEFAULT_REMEMBER
  end

  local hash_storage_key = configuration and configuration.hash_storage_key
  if hash_storage_key == nil then
    hash_storage_key = DEFAULT_HASH_STORAGE_KEY
  end

  local hash_subject = configuration and configuration.hash_subject
  if hash_subject == nil then
    hash_subject = DEFAULT_HASH_SUBJECT
  end

  local store_metadata = configuration and configuration.store_metadata
  if store_metadata == nil then
    store_metadata = DEFAULT_STORE_METADATA
  end

  local enforce_same_subject = configuration and configuration.enforce_same_subject
  if enforce_same_subject == nil then
    enforce_same_subject = DEFAULT_ENFORCE_SAME_SUBJECT
  end

  if cookie_prefix == "__Host-" then
    cookie_name          = cookie_prefix .. cookie_name
    remember_cookie_name = cookie_prefix .. remember_cookie_name
    cookie_path          = DEFAULT_COOKIE_PATH
    cookie_domain        = nil
    cookie_secure        = true

  elseif cookie_prefix == "__Secure-" then
    cookie_name          = cookie_prefix .. cookie_name
    remember_cookie_name = cookie_prefix .. remember_cookie_name
    cookie_secure        = true

  elseif cookie_same_site == "None" then
    cookie_secure = true
  end

  if cookie_same_party then
    assert(cookie_same_site ~= "Strict", "SameParty session cookies cannot use SameSite=Strict")
    cookie_secure = true
  end

  FLAGS_BUFFER:reset()

  if cookie_domain and cookie_domain ~= "localhost" and cookie_domain ~= "" then
    FLAGS_BUFFER:put("; Domain=", cookie_domain)
  end

  FLAGS_BUFFER:put("; Path=", cookie_path, "; SameSite=", cookie_same_site)

  if cookie_priority then
    FLAGS_BUFFER:put("; Priority=", cookie_priority)
  end

  if cookie_same_party then
    FLAGS_BUFFER:put("; SameParty")
  end

  if cookie_partitioned then
    FLAGS_BUFFER:put("; Partitioned")
  end

  if cookie_secure then
    FLAGS_BUFFER:put("; Secure")
  end

  if cookie_http_only then
    FLAGS_BUFFER:put("; HttpOnly")
  end

  local cookie_flags = FLAGS_BUFFER:get()

  if ikm then
    assert(#ikm == KEY_SIZE, "invalid ikm size")

  else
    local secret = configuration and configuration.secret
    if secret then
      ikm = assert(sha256(secret))

    else
      if not DEFAULT_IKM then
        DEFAULT_IKM = assert(sha256(assert(rand_bytes(KEY_SIZE))))
      end

      ikm = DEFAULT_IKM
    end
  end

  if ikm_fallbacks then
    local count = #ikm_fallbacks
    for i = 1, count do
      assert(#ikm_fallbacks[i] == KEY_SIZE, "invalid ikm size in ikm_fallbacks")
    end

  else
    local secret_fallbacks = configuration and configuration.secret_fallbacks
    if secret_fallbacks then
      local count = #secret_fallbacks
      if count > 0 then
        ikm_fallbacks = table_new(count, 0)
        for i = 1, count do
          ikm_fallbacks[i] = assert(sha256(secret_fallbacks[i]))
        end
      end

    else
      ikm_fallbacks = DEFAULT_IKM_FALLBACKS
    end
  end

  if request_headers then
    local count = #request_headers
    for i = 1, count do
      assert(HEADERS[request_headers[i]], "invalid request header")
    end

  else
    request_headers = DEFAULT_REQUEST_HEADERS
  end

  if response_headers then
    local count = #response_headers
    for i = 1, count do
      assert(HEADERS[response_headers[i]], "invalid response header")
    end

  else
    response_headers = DEFAULT_RESPONSE_HEADERS
  end

  local t = type(storage)
  if t == "string" then
    storage = load_storage(storage, configuration)

  elseif t ~= "table" then
    assert(storage == nil, "invalid session storage")
  end

  local self = setmetatable({
    stale_ttl                 = stale_ttl,
    idling_timeout            = idling_timeout,
    rolling_timeout           = rolling_timeout,
    absolute_timeout          = absolute_timeout,
    remember_rolling_timeout  = remember_rolling_timeout,
    remember_absolute_timeout = remember_absolute_timeout,
    touch_threshold           = touch_threshold,
    compression_threshold     = compression_threshold,
    hash_storage_key          = hash_storage_key and sha256_storage_key or encode_base64url,
    hash_subject              = hash_subject and sha256_subject or encode_base64url,
    store_metadata            = store_metadata,
    enforce_same_subject      = enforce_same_subject,
    cookie_name               = cookie_name,
    cookie_flags              = cookie_flags,
    remember_cookie_name      = remember_cookie_name,
    remember_safety           = remember_safety,
    remember                  = remember,
    flags                     = FLAGS_NONE,
    storage                   = storage,
    ikm                       = ikm,
    ikm_fallbacks             = ikm_fallbacks,
    request_headers           = request_headers,
    response_headers          = response_headers,
    state                     = STATE_NEW,
    meta                      = DEFAULT_META,
    remember_meta             = DEFAULT_REMEMBER_META,
    info                      = info,
    data_index                = 1,
    data                      = {
      {
        {},
        audience,
        subject,
      },
    },
  }, metatable)

  if storage then
    self.info = info.new(self)
  else
    self.info = fake_info.new(self)
  end

  return self
end


---
-- Helpers
-- @section helpers


---
-- Open a session.
--
-- This can be used to open a session, and it will either return an existing
-- session or a new session.
--
-- @function module.open
-- @tparam[opt] table configuration session @{configuration} overrides
-- @treturn table session instance
-- @treturn string error message
-- @treturn boolean `true`, if session existed, otherwise `false`
--
-- @usage
-- local session = require "resty.session".open()
-- -- OR
-- local session, err, exists = require "resty.session".open({
--   audience = "my-application",
-- })
function session.open(configuration)
  local self = session.new(configuration)
  local exists, err = self:open()
  if not exists then
    return self, err, false
  end

  return self, err, true
end


---
-- Start a session and refresh it as needed.
--
-- This can be used to start a session, and it will either return an existing
-- session or a new session. In case there is an existing session, the
-- session will be refreshed as well (as needed).
--
-- @function module.start
-- @tparam[opt] table configuration session @{configuration} overrides
-- @treturn table session instance
-- @treturn string error message
-- @treturn boolean `true`, if session existed, otherwise `false`
-- @treturn boolean `true`, if session was refreshed, otherwise `false`
--
-- @usage
-- local session = require "resty.session".start()
-- -- OR
-- local session, err, exists, refreshed = require "resty.session".start({
--   audience = "my-application",
-- })
function session.start(configuration)
  local self, err, exists = session.open(configuration)
  if not exists then
    return self, err, false, false
  end

  local refreshed, err = self:refresh()
  if not refreshed then
    return self, err, true, false
  end

  return self, nil, true, true
end


---
-- Logout a session.
--
-- It logouts from a specific audience.
--
-- A single session cookie may be shared between multiple audiences
-- (or applications), thus there is a need to be able to logout from
-- just a single audience while keeping the session for the other
-- audiences.
--
-- When there is only a single audience, then this can be considered
-- equal to `session.destroy`.
--
-- When the last audience is logged out, the cookie will be destroyed
-- as well and invalidated on a client.
--
-- @function module.logout
-- @tparam[opt] table configuration session @{configuration} overrides
-- @treturn boolean `true` session exists for an audience and was logged out successfully, otherwise `false`
-- @treturn string error message
-- @treturn boolean `true` if session existed, otherwise `false`
-- @treturn boolean `true` if session was logged out, otherwise `false`
--
-- @usage
-- require "resty.session".logout()
-- -- OR
-- local ok, err, exists, logged_out = require "resty.session".logout({
--   audience = "my-application",
-- })
function session.logout(configuration)
  local self, err, exists = session.open(configuration)
  if not exists then
    return nil, err, false, false
  end

  local ok, err = self:logout()
  if not ok then
    return nil, err, true, false
  end

  return true, nil, true, true
end

---
-- Destroy a session.
--
-- It destroys the whole session and clears the cookies.
--
-- @function module.destroy
-- @tparam[opt] table configuration session @{configuration} overrides
-- @treturn boolean `true` session exists and was destroyed successfully, otherwise `nil`
-- @treturn string error message
-- @treturn boolean `true` if session existed, otherwise `false`
-- @treturn boolean `true` if session was destroyed, otherwise `false`
--
-- @usage
-- require "resty.session".destroy()
-- -- OR
-- local ok, err, exists, destroyed = require "resty.session".destroy({
--   cookie_name = "auth",
-- })
function session.destroy(configuration)
  local self, err, exists = session.open(configuration)
  if not exists then
    return nil, err, false, false
  end

  local ok, err = self:destroy()
  if not ok then
    return nil, err, true, false
  end

  return true, nil, true, true
end


function session.__set_ngx_log(ngx_log)
  log = ngx_log
end


function session.__set_ngx_var(ngx_var)
  var = ngx_var
end


function session.__set_ngx_header(ngx_header)
  header = ngx_header
end


function session.__set_ngx_req_clear_header(clear_header)
  clear_request_header = clear_header
end


function session.__set_ngx_req_set_header(set_header)
  set_request_header = set_header
end


return session
