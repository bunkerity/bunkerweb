local type   = type
local concat = table.concat

local strategy = {}

function strategy.load(session, cookie, key, keep_lock)
  local storage    = session.storage
  local id         = cookie.id
  local id_encoded = session.encoder.encode(id)

  local data, err, tag
  if storage.open then
    data, err = storage:open(id_encoded, keep_lock)
    if not data then
      return nil, err or "cookie data was not found"
    end

  else
    data = cookie.data
  end

  local expires   = cookie.expires
  local usebefore = cookie.usebefore
  local hash      = cookie.hash

  if not key then
    key = concat{ id, expires, usebefore }
  end

  local hkey = session.hmac(session.secret, key)

  data, err, tag = session.cipher:decrypt(data, hkey, id, session.key, hash)
  if not data then
    if storage.close then
      storage:close(id_encoded)
    end

    return nil, err or "unable to decrypt data"
  end

  if tag then
    if tag ~= hash then
      if storage.close then
        storage:close(id_encoded)
      end

      return nil, "cookie has invalid tag"
    end

  else
    local input = concat{ key, data, session.key }
    if session.hmac(hkey, input) ~= hash then
      if storage.close then
        storage:close(id_encoded)
      end

      return nil, "cookie has invalid signature"
    end
  end

  data, err = session.compressor:decompress(data)
  if not data then
    if storage.close then
      storage:close(id_encoded)
    end

    return nil, err or "unable to decompress data"
  end

  data, err = session.serializer.deserialize(data)
  if not data then
    if storage.close then
      storage:close(id_encoded)
    end

    return nil, err or "unable to deserialize data"
  end

  session.id        = id
  session.expires   = expires
  session.usebefore = usebefore
  session.data      = type(data) == "table" and data or {}
  session.present   = true

  return true
end

function strategy.open(session, cookie, keep_lock)
  return strategy.load(session, cookie, nil, keep_lock)
end

function strategy.start(session)
  local storage = session.storage
  if not storage.start then
    return true
  end

  local id_encoded = session.encoder.encode(session.id)

  local ok, err = storage:start(id_encoded)
  if not ok then
    return nil, err or "unable to start session"
  end

  return true
end

function strategy.modify(session, action, close, key)
  local id         = session.id
  local id_encoded = session.encoder.encode(id)
  local storage    = session.storage
  local expires    = session.expires
  local usebefore  = session.usebefore
  local ttl        = expires - session.now

  if ttl <= 0 then
    if storage.close then
      storage:close(id_encoded)
    end

    return nil, "session is already expired"
  end

  if not key then
    key = concat{ id, expires, usebefore }
  end

  local data, err = session.serializer.serialize(session.data)
  if not data then
    if close and storage.close then
      storage:close(id_encoded)
    end

    return nil, err or "unable to serialize data"
  end

  data, err = session.compressor:compress(data)
  if not data then
    if close and storage.close then
      storage:close(id_encoded)
    end

    return nil, err or "unable to compress data"
  end

  local hkey = session.hmac(session.secret, key)

  local encrypted_data, tag
  encrypted_data, err, tag = session.cipher:encrypt(data, hkey, id, session.key)
  if not encrypted_data then
    if close and storage.close then
      storage:close(id_encoded)
    end

    return nil, err
  end

  local hash
  if tag then
    hash = tag
  else
    -- it would be better to calculate signature from encrypted_data,
    -- but this is kept for backward compatibility
    hash = session.hmac(hkey, concat{ key, data, session.key })
  end

  if action == "save" and storage.save then
    local ok
    ok, err = storage:save(id_encoded, ttl, encrypted_data, close)
    if not ok then
      return nil, err
    end
  elseif close and storage.close then
    local ok
    ok, err = storage:close(id_encoded)
    if not ok then
      return nil, err
    end
  end

  if usebefore then
    expires = expires .. ":" .. usebefore
  end

  hash = session.encoder.encode(hash)

  local cookie
  if storage.save then
    cookie = concat({ id_encoded, expires, hash }, "|")
  else
    local encoded_data = session.encoder.encode(encrypted_data)
    cookie = concat({ id_encoded, expires, encoded_data, hash }, "|")
  end

  return cookie
end

function strategy.touch(session, close)
  return strategy.modify(session, "touch", close)
end

function strategy.save(session, close)
  return strategy.modify(session, "save", close)
end

function strategy.destroy(session)
  local id = session.id
  if id then
    local storage = session.storage
    if storage.destroy then
      return storage:destroy(session.encoder.encode(id))
    elseif storage.close then
      return storage:close(session.encoder.encode(id))
    end
  end

  return true
end

function strategy.close(session)
  local id = session.id
  if id then
    local storage = session.storage
    if storage.close then
      return storage:close(session.encoder.encode(id))
    end
  end

  return true
end

return strategy
