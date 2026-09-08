local cjson = require "cjson"
local class = require "middleclass"
local datastore = require "bunkerweb.datastore"
local lrucache = require "resty.lrucache"
local plugin = require "bunkerweb.plugin"
local utils = require "bunkerweb.utils"

local metrics = class("metrics", plugin)
local ngx = ngx
local ERR = ngx.ERR
local WARN = ngx.WARN
local null = ngx.null
local unescape_uri = ngx.unescape_uri

-- Default cap for the per-worker LRU: governs both the slot count (distinct
-- counter/table keys held) and the per-key event-history array length. Overridden
-- per-worker from the MAX_LRU_HISTORY global setting once init_workers() runs and
-- self.variables is populated.
local DEFAULT_MAX_LRU_HISTORY = 1000

local lru, err_lru = lrucache.new(DEFAULT_MAX_LRU_HISTORY)
if not lru then
	require "bunkerweb.logger":new("METRICS"):log(ERR, "failed to instantiate LRU cache : " .. err_lru)
end

-- Keys this worker wrote to Redis on the previous sync, so the next one can tell which
-- ones the LRU has since evicted. Nothing else ever deletes their Redis counterpart.
local synced_redis_keys = {}

-- A worker-local latch cannot be evicted along with metric data.
local restored_shm = false
local prefilled_redis = false
-- Stripping the TTL is a one-shot migration: in persist mode nothing re-adds one, since
-- every writer uses bare SET/RPUSH/HINCRBY. Later cycles would be pure round trips.
local persisted_redis = false
-- A SCAN/MGET the Redis ACL denies never succeeds: give up after this many ticks
-- instead of spending one wasted round trip per worker every cycle forever.
local MAX_PREFILL_ATTEMPTS = 12
local prefill_attempts = 0

local shared = ngx.shared
local subsystem = ngx.config.subsystem
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local HTTP_OK = ngx.HTTP_OK
local worker = ngx.worker
local worker_id = worker.id

local get_reason = utils.get_reason
local get_country = utils.get_country
local has_variable = utils.has_variable
local is_connection_error = utils.is_connection_error
local is_oom_error = utils.is_oom_error
local encode = cjson.encode
local decode = cjson.decode

local match = string.match
local time = os.time
local tonumber = tonumber
local tostring = tostring
local table_insert = table.insert
local table_remove = table.remove
-- Bound here rather than read as a global at call time, where a missing one would only surface
-- when the branch first runs (the .luacheckrc whitelist hides bare global reads).
local unpack = unpack

local REQUEST_FACET_FIELDS = { "ip", "country", "method", "url", "status", "reason", "server_name", "security_mode" }

-- The list is authoritative. Facet failures invalidate its derived cache without
-- retrying an already inserted report. ARGV[10] marks an uncertain transport retry;
-- only that rare path scans by request ID or exact payload before inserting again.
local PUSH_SCRIPT = [==[
  local decoded, request = pcall(cjson.decode, ARGV[1])
  local id = decoded and type(request) == 'table' and type(request.id) == 'string' and request.id ~= '' and request.id
  if ARGV[10] == '1' then
    for start = 0, redis.call('LLEN', KEYS[1]) - 1, 256 do
      for i, stored in ipairs(redis.call('LRANGE', KEYS[1], start, start + 255)) do
        if stored == ARGV[1] then return {start + i, 1} end
        if id then
          local ok, old = pcall(cjson.decode, stored)
          if ok and type(old) == 'table' and old.id == id then return {start + i, 1} end
        end
      end
    end
  end
  local nb = redis.call('LLEN', KEYS[1])
  local raw = redis.pcall('GET', 'requests:facets:initialized')
  local ok, state = pcall(cjson.decode, type(raw) == 'string' and raw or '')
  local healthy = ok and type(state) == 'table' and state.version == 2 and state.length == nb
      and type(state.valid) == 'number' and type(state.nonfast) == 'number'
  local fields = {'ip','country','method','url','status','reason','server_name','security_mode'}
  for i = 1, #fields do
    local kind = redis.call('TYPE', 'requests:facet:' .. fields[i]).ok
    if kind ~= 'hash' and not (nb == 0 and kind == 'none') then healthy = false end
  end
  local pushed = redis.pcall('RPUSH', KEYS[1], ARGV[1])
  if type(pushed) == 'table' and pushed.err then
    return pushed
  end
  redis.call('DEL', 'requests:facets:initialized')
  if not healthy then return {pushed, 0} end
  -- REBUILD_SCRIPT's own predicate, applied to the row just pushed: a row the rebuild
  -- would reject must not bump valid nor the facets, or the certificate and the facets
  -- drift together and no later check can see it. Duplicate ids are the accepted
  -- ceiling here -- only a full list scan could detect one.
  local object = decoded and type(request) == 'table' and string.match(ARGV[1], '^%s*{')
  local rid = object and request.id
  if rid == cjson.null then rid = nil end
  local date = object and tonumber(request.date)
  local finite = date and date == date and math.abs(date) ~= math.huge
  local counted = object and (finite or request.date == nil or request.date == cjson.null)
      and (rid == nil or type(rid) == 'string' or type(rid) == 'number')
  if counted then
    for i = 1, #fields do
      local result = redis.pcall('HINCRBY', 'requests:facet:' .. fields[i], ARGV[1 + i], 1)
      if type(result) == 'table' and result.err then return {pushed, 0} end
    end
    state.valid = state.valid + 1
    state.tail = type(rid) == 'string' and rid or ''
  end
  -- Counted rather than latched, so paging returns to the bounded path by itself once
  -- the offending rows scroll out of the retained window.
  if not (finite and id) then state.nonfast = state.nonfast + 1 end
  state.length = pushed
  local marked = redis.pcall('SET', 'requests:facets:initialized', cjson.encode(state))
  if type(marked) == 'table' and marked.err then return {pushed, 0} end
  return {pushed, 1}
]==]

-- OOM probe bails before any destructive op so a popped entry never loses its
-- facet decrement. ARGV[1]=max_requests.
local TRIM_SCRIPT = [==[
  local max = tonumber(ARGV[1])
  if not max or max < 0 then max = 0 end
  local fields = {'ip','country','method','url','status','reason','server_name','security_mode'}
  if max == 0 then
    redis.call('DEL', KEYS[1])
    for i = 1, #fields do redis.call('DEL', 'requests:facet:' .. fields[i]) end
    redis.call('SET', 'requests:facets:initialized', cjson.encode({version=2,length=0,valid=0,nonfast=0,tail=''}))
    return 0
  end
  local nb = redis.call('LLEN', KEYS[1])
  if nb <= max then return 0 end
  local probe = redis.pcall('SET', 'requests:facets:oomprobe', '1', 'PX', 1)
  if type(probe) == 'table' and probe.err then
    return probe
  end
  local to_remove = nb - max
  local certificate = redis.pcall('GET', 'requests:facets:initialized')
  local ok, state = pcall(cjson.decode, type(certificate) == 'string' and certificate or '')
  -- A complete population can be decremented even when paging needs a fallback and even
  -- when the rebuild rejected some rows: only the list length has to match. Requiring
  -- valid == length made one rejected row invalidate the certificate on every tick.
  local healthy = ok and type(state) == 'table' and state.version == 2 and state.length == nb
      and type(state.valid) == 'number' and type(state.nonfast) == 'number'
  redis.call('DEL', 'requests:facets:initialized')
  local items = redis.call('LRANGE', KEYS[1], 0, to_remove - 1)
  local seen = {}
  local removed_valid = 0
  local removed_nonfast = 0
  for _, raw in ipairs(items) do
    -- Same predicate as REBUILD_SCRIPT, over the same prefix it counted first.
    local decoded, req = pcall(cjson.decode, raw)
    local object = decoded and type(req) == 'table' and string.match(raw, '^%s*{')
    local id = object and req.id
    if id == cjson.null then id = nil end
    local date = object and tonumber(req.date)
    local finite = date and date == date and math.abs(date) ~= math.huge
    local counted = object and (finite or req.date == nil or req.date == cjson.null)
        and (id == nil or (type(id) == 'string' or type(id) == 'number') and not seen[id])
    -- Same fast-pageable predicate as REBUILD_SCRIPT, evaluated before this row joins seen.
    local pageable = finite and type(id) == 'string' and id ~= '' and not seen[id]
    if healthy and not pageable then removed_nonfast = removed_nonfast + 1 end
    if healthy and counted then
      if id ~= nil then seen[id] = true end
      removed_valid = removed_valid + 1
      for i = 1, #fields do
        local v = req[fields[i]]
        if v == nil or v == cjson.null or v == '' then v = 'N/A' else v = tostring(v) end
        local n = redis.pcall('HINCRBY', 'requests:facet:' .. fields[i], v, -1)
        if type(n) ~= 'number' or n < 0 then healthy = false; break end
        if n == 0 then redis.call('HDEL', 'requests:facet:' .. fields[i], v) end
      end
    end
  end
  redis.call('LTRIM', KEYS[1], to_remove, -1)
  if healthy and state.valid >= removed_valid and state.nonfast >= removed_nonfast then
    state.length = max
    state.valid = state.valid - removed_valid
    state.nonfast = state.nonfast - removed_nonfast
    redis.pcall('SET', 'requests:facets:initialized', cjson.encode(state))
  end
  return to_remove
]==]

-- Marker invalidated up-front so an OOM-aborted rebuild retries next cycle instead
-- of latching a partial result.
-- ponytail: one atomic LRANGE + 8xN HINCRBY blocks Redis; fine as it only fires on
-- rare facet desync, and chunking would break atomicity.
local REBUILD_SCRIPT = [==[
  local fields = {'ip','country','method','url','status','reason','server_name','security_mode'}
  -- Every worker checks health then rebuilds in two separate EVALs, so on a restart or an
  -- upgrade they all queue a rebuild at once. Re-checking here makes all but the first a
  -- no-op: Redis serialises EVALs, so the later ones see the certificate the first wrote.
  local current = redis.pcall('GET', 'requests:facets:initialized')
  local valid, published = pcall(cjson.decode, type(current) == 'string' and current or '')
  if valid and type(published) == 'table' and published.version == 2
      and type(published.valid) == 'number' and published.valid >= 0
      and type(published.nonfast) == 'number' and published.nonfast >= 0
      and published.length == redis.call('LLEN', KEYS[1]) then
    local healthy = true
    for i = 1, #fields do
      local kind = redis.call('TYPE', 'requests:facet:' .. fields[i]).ok
      if (published.valid > 0 and kind ~= 'hash') or (published.valid == 0 and kind ~= 'none') then healthy = false end
    end
    if healthy then return 0 end
  end
  -- One rebuild per window for the whole deployment. A peer that writes this Redis
  -- without maintaining the certificate (a 1.6.14 instance during a rolling upgrade)
  -- leaves it stale on every tick, which would otherwise make every worker of every
  -- instance rebuild the entire list every 5 s. The TTL is what releases the lease.
  local lease = redis.pcall('SET', 'requests:facets:rebuilding', ARGV[1] or '1', 'NX', 'PX', 30000)
  if type(lease) == 'table' and lease.err then return lease end
  if not lease then return 0 end
  local probe = redis.pcall('SET', 'requests:facets:oomprobe', '1', 'PX', 1)
  if type(probe) == 'table' and probe.err then return probe end
  redis.call('DEL', 'requests:facets:initialized')
  for i = 1, #fields do redis.call('DEL', 'requests:facet:' .. fields[i]) end
  local items = redis.call('LRANGE', KEYS[1], 0, -1)
  local seen = {}
  local state = {version=2,length=#items,valid=0,nonfast=0,tail=''}
  for _, raw in ipairs(items) do
    local ok, req = pcall(cjson.decode, raw)
    local object = ok and type(req) == 'table' and string.match(raw, '^%s*{')
    local id = object and req.id
    if id == cjson.null then id = nil end
    local date = object and tonumber(req.date)
    local finite = date and date == date and math.abs(date) ~= math.huge
    if not date or date ~= date or math.abs(date) == math.huge
        or type(id) ~= 'string' or id == '' or seen[id] then state.nonfast = state.nonfast + 1 end
    if object and (finite or req.date == nil or req.date == cjson.null)
        and (id == nil or (type(id) == 'string' or type(id) == 'number') and not seen[id]) then
      if id ~= nil then seen[id] = true end
      state.tail = type(id) == 'string' and id or ''
      state.valid = state.valid + 1
      for i = 1, #fields do
        local v = req[fields[i]]
        if v == nil or v == cjson.null or v == '' then v = 'N/A' else v = tostring(v) end
        local r = redis.pcall('HINCRBY', 'requests:facet:' .. fields[i], v, 1)
        if type(r) == 'table' and r.err then return r end
      end
    end
  end
  redis.call('SET', 'requests:facets:initialized', cjson.encode(state))
  return #items
]==]

-- O(8) on every worker tick, independent of retained history/cardinality. Writers
-- invalidate on errors; UI pane scans check deeper sums and request a rebuild.
local HEALTH_SCRIPT = [==[
  local raw = redis.pcall('GET', 'requests:facets:initialized')
  local ok, state = pcall(cjson.decode, type(raw) == 'string' and raw or '')
  if not ok or type(state) ~= 'table' or state.version ~= 2
      or type(state.valid) ~= 'number' or state.valid < 0
      or type(state.nonfast) ~= 'number' or state.nonfast < 0
      or state.length ~= redis.call('LLEN', KEYS[1]) then return 0 end
  local fields = {'ip','country','method','url','status','reason','server_name','security_mode'}
  for i = 1, #fields do
    local kind = redis.call('TYPE', 'requests:facet:' .. fields[i]).ok
    if (state.valid > 0 and kind ~= 'hash') or (state.valid == 0 and kind ~= 'none') then return 0 end
  end
  return 1
]==]

-- Parse a count value with optional SI shorthand suffix: "100", "1k", "10K", "1m", "5M".
-- k/K = x1000, m/M = x1_000_000. Returns the integer count, or nil if value is missing
-- or unparsable.
local function parse_count(value)
	if value == nil or value == "" then
		return nil
	end
	local num_str, suffix = match(tostring(value), "^(%d+)([kKmM]?)$")
	if not num_str then
		return nil
	end
	local num = tonumber(num_str)
	if not num then
		return nil
	end
	if suffix == "k" or suffix == "K" then
		return num * 1000
	elseif suffix == "m" or suffix == "M" then
		return num * 1000000
	end
	return num
end

local function get_request_facet_value(request, field)
	local value = request[field]
	if value == nil or value == "" or value == null then
		return "N/A"
	end
	return tostring(value)
end

local function enforce_redis_requests_cap(self)
	local max_requests = parse_count(self.variables["METRICS_MAX_BLOCKED_REQUESTS_REDIS"])
	if not max_requests then
		-- Unparsable cap must not become 0: cap 0 wipes the list and facets.
		return
	end
	local _, err = self:redis_call("eval", TRIM_SCRIPT, 1, "requests", tostring(max_requests))
	if err then
		self:log_throttled(ERR, "cap_enforce", "Can't enforce Redis requests cap: " .. err)
	end
end

-- Rebuild on an invalid certificate or missing/wrong-typed facet keys.
local function self_heal_request_facets(self)
	local healthy, health_err = self:redis_call("eval", HEALTH_SCRIPT, 1, "requests")
	if health_err then
		self:log_throttled(ERR, "facet_check", "Can't check request facets: " .. health_err)
		return
	end
	if healthy ~= 1 then
		local _, err = self:redis_call("eval", REBUILD_SCRIPT, 1, "requests", tostring(worker_id()))
		if err then
			self:log_throttled(ERR, "facet_rebuild", "Can't rebuild request facets: " .. err)
		end
	end
end

local function reap_evicted_redis_keys(self, wid, live_keys)
	for key in pairs(synced_redis_keys) do
		-- Numeric totals remain authoritative in Redis after local LRU eviction.
		-- Their existing TTL bounds dormant retention; TTL=0 intentionally retains them.
		if not live_keys[key] and not key:find("_counter_", 1, true) then
			local ok, err = self:redis_call("del", "metrics:" .. key .. ":" .. wid)
			if not ok then
				self:log_throttled(ERR, "reap_evicted", "Can't delete evicted metric " .. key .. " from Redis: " .. err)
			end
		end
	end
	synced_redis_keys = live_keys
end

-- Baseline and increments share the counter's existing LRU slot. A cache miss
-- reads shared memory only; Redis is resolved lazily in the timer, never in log().
local function new_counter(self, key)
	local stored = self.metrics_datastore:get(key .. "_" .. tostring(worker_id()))
	local baseline = tonumber(stored) or 0
	return { value = baseline, baseline = baseline, increments = 0, restored = not self.use_redis }
end

local function restore_counter(self, key, counter, wid)
	if counter.restored then
		return true
	end
	local stored, err = self:redis_call("get", "metrics:" .. key .. ":" .. wid)
	if stored == false or stored == nil then
		self:log_throttled(
			ERR,
			"counter_restore",
			"Can't restore metric counter " .. key .. ": " .. (err or "unexpected reply")
		)
		return false
	end
	local baseline = stored == null and 0 or tonumber(stored)
	if not baseline then
		self:log_throttled(ERR, "counter_restore", "Invalid Redis metric counter " .. key)
		return false
	end
	-- log() can increment or evict this record while GET yields. Never reinsert a
	-- stale record, and merge the live increments only after the reply arrives.
	if lru:get(key) ~= counter then
		return false
	end
	counter.value = math.max(counter.baseline, baseline) + counter.increments
	counter.restored = true
	return true
end

-- Preserve passive counter exposure in the local API when slots are available.
-- This optional prefill never establishes correctness for a later cache miss;
-- restore_counter still protects every newly active counter independently.
local function prefill_counters(self, wid)
	local cursor, scanned = "0", 0
	local budget = lru:capacity() - #lru:get_keys()
	while budget > 0 do
		local page =
			self:redis_call("scan", cursor, "MATCH", "metrics:*_counter_*:" .. wid, "COUNT", math.min(budget, 100))
		if type(page) ~= "table" or type(page[1]) ~= "string" or type(page[2]) ~= "table" then
			return false
		end
		cursor = page[1]
		-- Empty MATCH pages still consume work: bound cursor steps as well as slots.
		scanned = scanned + math.max(100, #page[2])
		if #page[2] > 0 then
			local values = self:redis_call("mget", unpack(page[2]))
			if type(values) ~= "table" then
				return false
			end
			budget = lru:capacity() - #lru:get_keys()
			for i, redis_key in ipairs(page[2]) do
				if budget <= 0 then
					break
				end
				local key = redis_key:sub(9, -(#wid + 2))
				local value = values[i] ~= null and tonumber(values[i])
				-- A log() during SCAN/MGET owns its live record; lazy restore will merge it.
				if value and lru:get(key) == nil then
					lru:set(key, { value = value, baseline = value, increments = 0, restored = true })
					budget = budget - 1
				end
			end
		end
		if cursor == "0" or scanned >= lru:capacity() then
			break
		end
	end
	return true
end

-- METRICS_REDIS_TTL=0 is documented as keeping the keys permanent. Only refreshing the
-- TTL when it is set leaves a key that already carries one expiring for another full
-- period, and under volatile-lru it stays evictable for exactly that long, which is how
-- an operator who set 0 to pin the reports list still loses it. PERSIST makes the
-- documented behaviour true on an instance that ran with a TTL before.
local function refresh_request_ttls(self, ttl, wid)
	local persist = ttl <= 0
	if persist then
		if persisted_redis then
			return
		end
		persisted_redis = true
	end
	local function touch(key)
		if persist then
			self.clusterstore:call("persist", key)
		else
			self.clusterstore:call("expire", key, ttl)
		end
	end
	touch("requests")
	for _, field in ipairs(REQUEST_FACET_FIELDS) do
		touch("requests:facet:" .. field)
	end
	touch("requests:facets:initialized")
	if self.variables["METRICS_SAVE_TO_REDIS"] == "yes" then
		for _, key in ipairs(lru:get_keys()) do
			if key ~= "setup" and key ~= "requests" then
				touch("metrics:" .. key .. ":" .. wid)
			end
		end
	end
end

function metrics:initialize(ctx)
	-- Call parent initialize
	plugin.initialize(self, "metrics", ctx)
	local dict
	if subsystem == "http" then
		dict = shared.metrics_datastore
	else
		dict = shared.metrics_datastore_stream
	end
	self.metrics_datastore = datastore:new(dict)
end

-- init_workers(), not init_worker(): the latter is gated behind a shared "misc_ready" flag
-- and runs once per instance, so it would resize a single worker's LRU and leave every other
-- one on the default. This is per-worker VM state, so it needs the per-worker phase.
function metrics:init_workers()
	-- Resize the per-worker LRU using the configured MAX_LRU_HISTORY (global setting).
	-- Until this runs, the module-level default LRU sized at DEFAULT_MAX_LRU_HISTORY is
	-- used. The resize is skipped when the configured value matches the default to avoid
	-- dropping any entries collected between module load and here.
	local max_lru_history = parse_count(self.variables["MAX_LRU_HISTORY"]) or DEFAULT_MAX_LRU_HISTORY
	if max_lru_history < 1 then
		max_lru_history = DEFAULT_MAX_LRU_HISTORY
	end
	if max_lru_history == DEFAULT_MAX_LRU_HISTORY then
		return self:ret(true, "metrics LRU using default size (MAX_LRU_HISTORY=" .. max_lru_history .. ")")
	end
	local new_lru, err = lrucache.new(max_lru_history)
	if not new_lru then
		self.logger:log(ERR, "failed to resize metrics LRU to " .. max_lru_history .. " slots : " .. err)
		return self:ret(true, "kept default LRU size")
	end
	lru = new_lru
	return self:ret(true, "metrics LRU sized to " .. max_lru_history .. " slots")
end

-- Call Redis with one automatic reconnect attempt on connection error.
-- Must be called after self.clusterstore:connect() has succeeded.
-- Acts as a circuit-breaker: once self.redis_ok is false, all calls
-- are short-circuited for the rest of the timer cycle.
function metrics:redis_call(method, ...)
	if self.redis_ok == false then
		return false, "Redis unavailable for this cycle"
	end
	local res, call_err = self.clusterstore:call(method, ...)
	if not res and call_err and is_oom_error(call_err) then
		self.redis_ok = false
		return false, call_err -- no reconnect: the connection is healthy under OOM
	end
	if not res and call_err and is_connection_error(call_err) then
		self.clusterstore:close()
		local ok, reconnect_err = self.clusterstore:connect()
		if not ok then
			self:log_throttled(
				ERR,
				"redis_reconnect",
				"Can't reconnect to Redis: " .. (reconnect_err or "unknown error")
			)
			self.redis_ok = false
			return false, call_err
		end
		local args = { ... }
		if method == "eval" and args[1] == PUSH_SCRIPT then
			args[13] = "1" -- uncertain RPUSH reply: look up the original JSON before replay
		end
		local res2, err2 = self.clusterstore:call(method, unpack(args))
		if not res2 and err2 then
			self.redis_ok = false
		end
		return res2, err2
	end
	return res, call_err
end

function metrics:log(bypass_checks)
	-- Don't go further if metrics is not enabled
	if not bypass_checks and self.variables["USE_METRICS"] == "no" then
		return self:ret(true, "metrics are disabled")
	end
	-- Store blocked requests
	local reason, data, security_mode = get_reason(self.ctx)
	if reason then
		local country = "local"
		local err
		if self.ctx.bw.ip_is_global then
			country, err = get_country(self.ctx.bw.remote_addr)
			if not country then
				country = "unknown"
				self.logger:log(ERR, "can't get country code " .. err)
			end
		end
		local request = {
			id = self.ctx.bw.request_id,
			date = self.ctx.bw.start_time or time(),
			ip = self.ctx.bw.remote_addr,
			country = country,
			method = self.ctx.bw.request_method,
			url = self.ctx.bw.request_uri,
			status = ngx.status,
			user_agent = self.ctx.bw.http_user_agent or "",
			reason = reason,
			server_name = self.ctx.bw.server_name,
			data = data,
			security_mode = security_mode,
			synced = not self.use_redis,
		}
		-- Get requests from LRU
		local requests = lru:get("requests") or {}

		-- Add to LRU
		table_insert(requests, request)

		-- Remove old requests if needed
		local max_requests = parse_count(self.variables["METRICS_MAX_BLOCKED_REQUESTS"]) or 1000
		while #requests > max_requests do
			local dropped = table_remove(requests, 1)
			if dropped and not dropped.synced then
				self:log_throttled(
					WARN,
					"buffer_drop",
					"Blocked-request buffer full, dropping unsynced report (Redis down or OOM?)"
				)
			end
		end

		-- Update worker cache
		lru:set("requests", requests)
	end
	-- Get metrics from plugins
	local all_metrics = self.ctx.bw.metrics
	if all_metrics then
		-- Loop on plugins
		for plugin_id, plugin_metrics in pairs(all_metrics) do
			-- Loop on kinds
			for kind, kind_metrics in pairs(plugin_metrics) do
				-- Increment counters
				if kind == "counters" then
					for metric_key, metric_value in pairs(kind_metrics) do
						local lru_key = plugin_id .. "_counter_" .. metric_key
						local metric_counter = lru:get(lru_key)
						if not metric_counter then
							metric_counter = new_counter(self, lru_key)
						end
						metric_counter.value = metric_counter.value + metric_value
						metric_counter.increments = metric_counter.increments + metric_value
						lru:set(lru_key, metric_counter)
					end
				-- Add table entries
				elseif kind == "tables" then
					local max_lru_history = parse_count(self.variables["MAX_LRU_HISTORY"]) or DEFAULT_MAX_LRU_HISTORY
					for metric_key, metric_value in pairs(kind_metrics) do
						local lru_key = plugin_id .. "_table_" .. metric_key
						local metric_table = lru:get(lru_key) or {}
						-- Cap event history per (plugin, key) — drop oldest first
						while #metric_table >= max_lru_history do
							table_remove(metric_table, 1)
						end
						-- Add value to table
						table_insert(metric_table, metric_value)
						-- Update LRU cache
						lru:set(lru_key, metric_table)
					end
				end
			end
		end
	end
	return self:ret(true, "success")
end

function metrics:log_default()
	local is_needed, err = has_variable("USE_METRICS", "yes")
	if is_needed == nil then
		return self:ret(false, "can't check USE_METRICS variable : " .. err)
	end
	if is_needed then
		return self:log(true)
	end
	return self:ret(true, "metrics not used")
end

function metrics:timer()
	-- Check if metrics is used
	local is_needed, err = has_variable("USE_METRICS", "yes")
	if is_needed == nil then
		return self:ret(false, "can't check USE_METRICS variable : " .. err)
	end
	if not is_needed then
		return self:ret(true, "metrics not used")
	end

	local ret = true
	local ret_err = "metrics updated"
	local wid = tostring(worker_id())

	-- Restore SHM once, leaving counters/requests already touched by log() intact.
	-- Do not evict live slots just to prefill a cache: later misses recover lazily.
	if not restored_shm then
		local budget = lru:capacity() - #lru:get_keys()
		for _, key in ipairs(self.metrics_datastore:keys()) do
			if budget <= 0 then
				break
			end
			if key:match("_" .. wid .. "$") then
				local name = key:gsub("_" .. wid .. "$", "")
				if name ~= "setup" and lru:get(name) == nil then
					local value = self.metrics_datastore:get(key)
					if value then
						local ok, decoded = pcall(decode, value)
						if ok then
							value = decoded
						end
						if name:find("_counter_", 1, true) then
							value = new_counter(self, name)
						elseif name == "requests" and type(value) == "table" then
							-- Redis may have accepted a report before the old worker died
							-- without rewriting SHM. Every restored unsynced row is uncertain.
							for _, request in ipairs(value) do
								if type(request) == "table" and not request.synced then
									request.redis_retry_json = request.redis_retry_json or encode(request)
								end
							end
						end
						lru:set(name, value)
						budget = budget - 1
					end
				end
			end
		end
		restored_shm = true
	end

	self.redis_ok = nil
	local ttl = parse_count(self.variables["METRICS_REDIS_TTL"])
	local redis_connected = false
	if self.use_redis then
		self.redis_ok, err = self.clusterstore:connect()
		if not self.redis_ok then
			self:log_throttled(
				ERR,
				"redis_connect",
				"Can't connect to Redis server: "
					.. (err or "unknown error")
					.. " - requests will be stored in datastore"
			)
		else
			redis_connected = true
			if not prefilled_redis and self.variables["METRICS_SAVE_TO_REDIS"] == "yes" then
				prefill_attempts = prefill_attempts + 1
				prefilled_redis = prefill_counters(self, wid) or prefill_attempts >= MAX_PREFILL_ATTEMPTS
			end
			self_heal_request_facets(self)
		end
	end

	local lru_keys = lru:get_keys()
	-- Built from the snapshot rather than from the writes below, so a key skipped because
	-- the OOM breaker tripped or because it was raced out mid-loop is not taken for evicted.
	local live_keys = {}
	for _, key in ipairs(lru_keys) do
		if key ~= "setup" and key ~= "requests" then
			live_keys[key] = true
		end
	end

	-- Loop on all keys, coldest first. get_keys() hands them back hottest first and lru:get()
	-- promotes what it reads, so walking forward reverses the whole queue on every cycle and
	-- the next insertion evicts the hottest key instead of the coldest. Walking backwards
	-- promotes them in the order they already had, leaving it unchanged.
	for idx = #lru_keys, 1, -1 do
		local key = lru_keys[idx]
		-- Get LRU data
		local value = lru:get(key)
		local counter = type(value) == "table" and value.value ~= nil and key:find("_counter_", 1, true) and value
		if counter then
			if self.redis_ok and self.variables["METRICS_SAVE_TO_REDIS"] == "yes" then
				restore_counter(self, key, counter, wid)
			end
			value = lru:get(key) == counter and counter.value or nil
		end
		-- get_keys() returns a snapshot and every redis_call below yields, so a
		-- concurrent log() can evict this key from the (full) LRU in between. A miss
		-- must never be written out: tostring(nil) stores the literal string "nil" in
		-- Redis, and a nil datastore value deletes the entry. Skip it and let the next
		-- cycle resync whatever is still live.
		if value ~= nil then
			if self.redis_ok then
				if key == "requests" then
					for _, request in ipairs(value) do
						if not request.synced then
							local v = {}
							for i, field in ipairs(REQUEST_FACET_FIELDS) do
								v[i] = get_request_facet_value(request, field)
							end
							local ok
							local payload = request.redis_retry_json or encode(request)
							ok, err = self:redis_call(
								"eval",
								PUSH_SCRIPT,
								1,
								"requests",
								payload,
								v[1],
								v[2],
								v[3],
								v[4],
								v[5],
								v[6],
								v[7],
								v[8],
								request.redis_retry_json and "1" or "0"
							)
							if not ok then
								request.redis_retry_json = payload
								self:log_throttled(
									ERR,
									"sync_request",
									"Can't sync request to Redis: " .. (err or "unknown error")
								)
								break
							end
							request.redis_retry_json = nil
							request.synced = true
							if type(ok) == "table" and ok[2] == 0 then
								self:log_throttled(
									WARN,
									"facet_invalid",
									"Report saved; request facets require rebuilding"
								)
							end
						end
					end

					-- Update LRU cache
					lru:set("requests", value)
				elseif key ~= "setup" and self.variables["METRICS_SAVE_TO_REDIS"] == "yes" then
					-- Sync other metrics (counters and tables) to Redis with optimized data structures
					local redis_key = "metrics:" .. key .. ":" .. wid
					local ok
					if type(value) == "table" then
						-- Use Redis list for table values
						ok, err = self:redis_call("del", redis_key)
						if ok then
							for _, item in ipairs(value) do
								local item_value = type(item) == "table" and encode(item) or tostring(item)
								ok, err = self:redis_call("rpush", redis_key, item_value)
								if not ok then
									self:log_throttled(
										ERR,
										"sync_table_item",
										"Can't push metric table item " .. key .. " to Redis: " .. err
									)
									break
								end
							end
						else
							self:log_throttled(
								ERR,
								"sync_table_clear",
								"Can't clear metric table " .. key .. " in Redis: " .. err
							)
						end
					elseif type(value) == "number" then
						-- Use Redis string for numeric counters
						-- ponytail: increments survive yields only while the LRU record remains;
						-- eviction during SET can drop newer deltas. Durable queues are separate work.
						if not counter or counter.restored then
							-- Scoped here: the outer err still holds the previous key's failure,
							-- which would be reported as this counter's own.
							local set_ok, set_err = self:redis_call("set", redis_key, value)
							if not set_ok then
								self:log_throttled(
									ERR,
									"sync_counter",
									"Can't sync metric counter " .. key .. " to Redis: " .. (set_err or "unknown error")
								)
							end
						else
							self:log_throttled(
								WARN,
								"counter_unrestored",
								"Metric counter " .. key .. " not restored from Redis yet: not synced this cycle"
							)
						end
					else
						-- Use Redis string for other types
						ok, err = self:redis_call("set", redis_key, tostring(value))
						if not ok then
							self:log_throttled(ERR, "sync_other", "Can't sync metric " .. key .. " to Redis: " .. err)
						end
					end
				end
			end
			if type(value) == "table" then
				value = encode(value)
			end
			-- Push to dict (with LRU eviction if needed)
			local ok
			ok, err = self.metrics_datastore:set_with_retries(key .. "_" .. wid, value)
			-- Shed the oldest half rather than the whole history: set_with_retries already
			-- force-evicted, so "no memory" means the dict is undersized, and dropping every
			-- stored entry to make one write fit loses far more than needed. The halving is
			-- kept in the LRU, so later cycles start from the reduced size.
			while not ok and err == "no memory" do
				local live = lru:get(key)
				if type(live) ~= "table" or #live < 2 then
					break
				end
				for _ = 1, math.floor(#live / 2) do
					table_remove(live, 1)
				end
				lru:set(key, live)
				self:log_throttled(
					WARN,
					"datastore_shed_" .. key,
					"not enough memory in the metrics datastore, halved LRU key "
						.. key
						.. " to "
						.. #live
						.. " entries : raise METRICS_MEMORY_SIZE"
				)
				ok, err = self.metrics_datastore:set_with_retries(key .. "_" .. wid, encode(live))
			end
			if not ok then
				-- Nothing left to shed : drop the key so the next cycle starts clean
				if err == "no memory" then
					self:log_throttled(
						WARN,
						"datastore_purge_" .. key,
						"not enough memory in the metrics datastore, purging LRU key " .. key
					)
					lru:delete(key)
				else
					ret = false
					ret_err = err
					self:log_throttled(ERR, "datastore_set", "can't set " .. key .. "_" .. wid .. " : " .. err)
				end
			end
		end
	end

	if self.redis_ok then
		enforce_redis_requests_cap(self)
		if self.variables["METRICS_SAVE_TO_REDIS"] == "yes" then
			reap_evicted_redis_keys(self, wid, live_keys)
		end
	end
	if redis_connected and ttl then
		refresh_request_ttls(self, ttl, wid)
	end
	-- Always attempt cleanup when Redis was used, even if connection dropped mid-cycle.
	-- clusterstore:close() handles the "client is not instantiated" case gracefully.
	if self.use_redis then
		self.clusterstore:close()
	end

	-- Flush any end-of-window recaps for errors that stopped repeating.
	self:flush_log_recaps()

	-- Done
	return self:ret(ret, ret_err)
end

function metrics:api()
	-- Match request
	if not match(self.ctx.bw.uri, "^/metrics/.+$") or self.ctx.bw.request_method ~= "GET" then
		return self:ret(false, "success")
	end
	-- Extract filter parameter
	local filter = self.ctx.bw.uri:gsub("^/metrics/", "")

	-- Handle special /metrics/requests/query endpoint for optimized queries
	if filter == "requests/query" then
		return self:api_requests_query()
	end

	-- Loop on keys
	local metrics_data = {}
	for _, key in ipairs(self.metrics_datastore:keys()) do
		-- Check if key starts with our filter
		if key:match("^" .. filter .. "_") then
			-- Get the value
			local data, err = self.metrics_datastore:get(key)
			if not data then
				return self:ret(true, "error while fetching metric : " .. err, HTTP_INTERNAL_SERVER_ERROR)
			end
			local metric_key = key:gsub("_[0-9]+$", ""):gsub("^" .. filter .. "_", "")
			if metric_key == "" then
				metric_key = filter
			end
			-- Table case
			local ok, decoded = pcall(decode, data)
			if ok then
				data = decoded
			end
			if type(data) == "table" then
				if not metrics_data[metric_key] then
					metrics_data[metric_key] = {}
				end
				for _, metric_value in ipairs(data) do
					table_insert(metrics_data[metric_key], metric_value)
				end
			else
				-- Counter case
				if not metrics_data[metric_key] then
					metrics_data[metric_key] = 0
				end
				metrics_data[metric_key] = metrics_data[metric_key] + data
			end
		end
	end
	return self:ret(true, metrics_data, HTTP_OK)
end

function metrics:api_requests_query()
	-- Parse query parameters from request args
	local args = ngx.req.get_uri_args()
	local start_idx = tonumber(args.start) or 0
	local length = tonumber(args.length) or 10
	local search = unescape_uri(args.search or "")
	local order_column = args.order_column or "date"
	local order_dir = args.order_dir or "desc"
	local count_only = args.count_only == "true"

	-- Parse search panes filters (format: field1:value1,value2;field2:value3)
	local search_panes = {}
	local search_panes_raw = unescape_uri(args.search_panes or "")
	if search_panes_raw and search_panes_raw ~= "" then
		for field_filter in search_panes_raw:gmatch("[^;]+") do
			local field, values = field_filter:match("^([^:]+):(.+)$")
			if field and values then
				search_panes[field] = {}
				for value in values:gmatch("[^,]+") do
					table_insert(search_panes[field], value)
				end
			end
		end
	end

	-- Collect all requests from all workers
	local all_requests = {}
	for _, key in ipairs(self.metrics_datastore:keys()) do
		if key:match("^requests_[0-9]+$") then
			local data, _ = self.metrics_datastore:get(key)
			if data then
				local ok, decoded = pcall(decode, data)
				if ok and type(decoded) == "table" then
					for _, request in ipairs(decoded) do
						table_insert(all_requests, request)
					end
				end
			end
		end
	end

	-- Filter requests
	local filtered_requests = {}
	for _, request in ipairs(all_requests) do
		-- Filter: status 400-499 or detect mode
		if (request.status and request.status >= 400 and request.status < 500) or request.security_mode == "detect" then
			local matches = true

			-- Apply search filter
			if search ~= "" then
				local search_lower = search:lower()
				matches = false
				for _, value in pairs(request) do
					if type(value) == "string" and value:lower():find(search_lower, 1, true) then
						matches = true
						break
					elseif type(value) == "number" and tostring(value):find(search_lower, 1, true) then
						matches = true
						break
					end
				end
			end

			-- Apply search panes filters
			if matches then
				for field, allowed_values in pairs(search_panes) do
					local field_value = tostring(request[field] or "N/A")
					local field_matches = false
					for _, allowed in ipairs(allowed_values) do
						if field_value == allowed then
							field_matches = true
							break
						end
					end
					if not field_matches then
						matches = false
						break
					end
				end
			end

			if matches then
				table_insert(filtered_requests, request)
			end
		end
	end

	-- If only count is requested, return early
	if count_only then
		return self:ret(true, { total = #all_requests, filtered = #filtered_requests }, HTTP_OK)
	end

	-- Sort filtered requests
	if order_column == "date" then
		table.sort(filtered_requests, function(a, b)
			local a_val = tonumber(a.date) or 0
			local b_val = tonumber(b.date) or 0
			if order_dir == "desc" then
				return a_val > b_val
			else
				return a_val < b_val
			end
		end)
	else
		table.sort(filtered_requests, function(a, b)
			local a_val = a[order_column] or ""
			local b_val = b[order_column] or ""
			if order_dir == "desc" then
				return a_val > b_val
			else
				return a_val < b_val
			end
		end)
	end

	-- Paginate
	local paginated = {}
	local end_idx = start_idx + length
	if length == -1 then
		end_idx = #filtered_requests
	end

	for i = start_idx + 1, math.min(end_idx, #filtered_requests) do
		table_insert(paginated, filtered_requests[i])
	end

	-- Calculate search panes options
	local pane_counts = {}
	local filtered_ids = {}
	for _, req in ipairs(filtered_requests) do
		filtered_ids[req.id] = true
	end

	local pane_fields = { "ip", "country", "method", "url", "status", "reason", "server_name", "security_mode" }
	for _, field in ipairs(pane_fields) do
		pane_counts[field] = {}
	end

	for _, request in ipairs(all_requests) do
		if (request.status and request.status >= 400 and request.status < 500) or request.security_mode == "detect" then
			for _, field in ipairs(pane_fields) do
				local value = tostring(request[field] or "N/A")
				if not pane_counts[field][value] then
					pane_counts[field][value] = { total = 0, count = 0 }
				end
				pane_counts[field][value].total = pane_counts[field][value].total + 1
				if filtered_ids[request.id] then
					pane_counts[field][value].count = pane_counts[field][value].count + 1
				end
			end
		end
	end

	return self:ret(true, {
		total = #all_requests,
		filtered = #filtered_requests,
		data = paginated,
		pane_counts = pane_counts,
	}, HTTP_OK)
end

return metrics
