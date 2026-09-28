local cjson = require "cjson"
local hash = require("crowdsec.cache_partition").hash
local M = {}

function M.array()
  return setmetatable({}, cjson.array_mt)
end

function M.duration(value)
  if type(value) ~= "string" then return nil end
  local ttl, offset, previous = 0, 1, 4
  local units = {h = {3600, 3}, m = {60, 2}, s = {1, 1}}
  for start, number, unit, finish in value:gmatch("()(%d+%.?%d*)([hms])()") do
    local spec = units[unit]
    if start ~= offset or spec[2] >= previous then return nil end
    ttl, offset, previous = ttl + tonumber(number) * spec[1], finish, spec[2]
  end
  if offset ~= #value + 1 or ttl <= 0 or ttl == math.huge then return nil end
  return ttl
end

function M.identity(decision)
  local id = decision.id
  if id ~= nil and id ~= cjson.null then
    if type(id) == "string" and #id > 0 and #id <= 128 and not id:find("[%c]") then return id end
    if type(id) == "number" and id >= 0 and id <= 9007199254740991 and id == math.floor(id) then return tostring(id) end
    return nil
  end
  -- Older LAPI responses can omit id; retain distinct provenance when available.
  local parts = {}
  for _, name in ipairs({"origin", "scenario", "type"}) do
    local value = decision[name] or ""
    if type(value) ~= "string" or #value > 512 then return nil end
    parts[#parts + 1] = value
  end
  return "hash:" .. hash(cjson.encode(parts))
end

function M.new(cache, metadata)
  local store = {}
  local function target_key(key, generation)
    return (generation or cache:get("v2_generation") or 0) .. "|" .. key
  end
  local function records(key)
    local raw = cache:get("v2_decisions_" .. key)
    if not raw then return {} end
    local ok, decoded = pcall(cjson.decode, raw)
    if not ok or type(decoded) ~= "table" then return {} end
    local active = {}
    for _, record in ipairs(decoded) do
      if record[2] > ngx.time() then active[#active + 1] = record end
    end
    return active
  end
  local function save(key, active)
    if #active == 0 then cache:delete("v2_decisions_" .. key); return true end
    local expires = 0
    for _, record in ipairs(active) do expires = math.max(expires, record[2]) end
    return cache:safe_set("v2_decisions_" .. key, cjson.encode(active), expires - ngx.time())
  end
  function store.update(key, decision, remediation, ttl, deleted, generation)
    key = target_key(key, generation)
    local id = M.identity(decision)
    if not id then return nil, "Invalid decision identity" end
    local active = records(key)
    for i = #active, 1, -1 do
      if active[i][1] == id then table.remove(active, i) end
    end
    local metadata_key = "v2_evidence_" .. key .. "|" .. id
    if deleted then
      if metadata then metadata:delete(metadata_key) end
    else
      local expires = ngx.time() + ttl
      active[#active + 1] = {id, expires, remediation}
      if metadata then
        local evidence = {expires_at = ngx.time() + M.duration(decision.duration)}
        for _, name in ipairs({"id", "origin", "scenario", "type", "scope", "value"}) do
          local value = decision[name]
          if type(value) == "string" then value = value:sub(1, 512) end
          if type(value) == "string" or type(value) == "number" then evidence[name] = value end
        end
        -- Optional provenance cannot evict decisions, or other provenance entries.
        local ok = metadata:safe_set(metadata_key, cjson.encode(evidence), ttl)
        if not ok then metadata:delete(metadata_key) end
      end
    end
    return save(key, active)
  end
  function store.clear(key)
    cache:delete("v2_decisions_" .. target_key(key))
  end
  function store.get(key)
    key = target_key(key)
    local active = records(key)
    if #active == 0 then return nil end
    local remediation, evidence = active[1][3], {
      source = "lapi", captured_at = ngx.time(), decisions = M.array(), metadata_available = true,
    }
    for _, record in ipairs(active) do
      if record[3] == "ban" then remediation = "ban" end
      local raw = metadata and metadata:get("v2_evidence_" .. key .. "|" .. record[1])
      local ok, decision = false, nil
      if raw then ok, decision = pcall(cjson.decode, raw) end
      if ok and type(decision) == "table" then
        evidence.decisions[#evidence.decisions + 1] = decision
        evidence.matched_target = evidence.matched_target or decision.value
      else
        evidence.metadata_available = false
      end
    end
    return remediation, evidence
  end
  return store
end

return M
