function sink.table(t)
  t = t or {}
  local f = function(chunk, err)
    if chunk then table.insert(t, chunk) end
    return 1
  end
  return f, t
end

local function null()
  return 1
end

function sink.null()
  return null
end
