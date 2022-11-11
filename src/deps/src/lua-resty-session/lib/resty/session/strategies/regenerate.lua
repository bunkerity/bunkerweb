local default = require "resty.session.strategies.default"

local concat  = table.concat

local strategy = {
  regenerate = true,
  start      = default.start,
  destroy    = default.destroy,
  close      = default.close,
}

local function key(source)
  if source.usebefore then
    return concat{ source.id, source.usebefore }
  end

  return source.id
end

function strategy.open(session, cookie, keep_lock)
  return default.load(session, cookie, key(cookie), keep_lock)
end

function strategy.touch(session, close)
  return default.modify(session, "touch", close, key(session))
end

function strategy.save(session, close)
  if session.present then
    local storage = session.storage
    if storage.ttl then
      storage:ttl(session.encoder.encode(session.id), session.cookie.discard, true)
    elseif storage.close then
      storage:close(session.encoder.encode(session.id))
    end

    session.id = session:identifier()
  end

  return default.modify(session, "save", close, key(session))
end

return strategy
