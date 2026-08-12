local cjson = require "cjson"
local class = require "middleclass"
local datastore = require "bunkerweb.datastore"
local internal_api = require "bunkerweb.internal_api"
local lrucache = require "resty.lrucache"
local plugin = require "bunkerweb.plugin"
local resty_lock = require "resty.lock"
local utils = require "bunkerweb.utils"

local metrics = class("metrics", plugin)
local ngx = ngx
local ERR = ngx.ERR
local INFO = ngx.INFO
local WARN = ngx.WARN
local null = ngx.null
local unescape_uri = ngx.unescape_uri

-- Default cap for the per-worker LRU: governs both the slot count (distinct
-- counter/table keys held) and the per-key event-history array length. Overridden
-- per-worker from the MAX_LRU_HISTORY global setting once init_worker() runs and
-- self.variables is populated.
local DEFAULT_MAX_LRU_HISTORY = 1000

local lru, err_lru = lrucache.new(DEFAULT_MAX_LRU_HISTORY)
if not lru then
	require "bunkerweb.logger":new("METRICS"):log(ERR, "failed to instantiate LRU cache : " .. err_lru)
end
-- Security reports have their own bounded queue: they must not compete with metric keys.
local stream_requests = {}

-- Fold one duration sample (seconds) into a running aggregate. Kept pure and module-level
-- so the arithmetic can be exercised on its own.
-- A negative sample is dropped rather than clamped: it means the clock moved backwards, and
-- a bogus 0 would drag the mean down while looking like a real observation.
-- ponytail: count/sum/max yields mean and worst case, not percentiles. Fixed-bucket
-- histograms are the upgrade path if p95 is ever needed.
local function accumulate_timer(acc, sample)
	if type(sample) ~= "number" or sample ~= sample or sample < 0 then
		return acc
	end
	if not acc then
		return { count = 1, sum = sample, max = sample }
	end
	acc.count = acc.count + 1
	acc.sum = acc.sum + sample
	if sample > acc.max then
		acc.max = sample
	end
	return acc
end

-- Longest templated URI kept in a baseline record. Past this the tail carries no signal a
-- model can use and only costs storage.
local MAX_TEMPLATED_URI = 200

-- Decide whether a request joins the sampled baseline. `hash` is a stable hash of the
-- request id and `rate` a percentage.
-- Deterministic on purpose: math.random() has no per-worker seeding here, and a stable
-- decision keeps every subrequest of one request on the same side of the sample.
local function should_sample(hash, rate)
	rate = tonumber(rate) or 0
	-- Full rate short-circuits so a request with no usable id is still sampled. There is no
	-- matching guard for rate <= 0: `hash % 100` is always 0..99, so the comparison below
	-- already rejects everything at 0 or below.
	if rate >= 100 then
		return true
	end
	if type(hash) ~= "number" then
		return false
	end
	return hash % 100 < rate
end

-- Collapse the parts of a path that are unique per user or per object. A raw URI is both a
-- cardinality bomb (one distinct value per request, the problem requests:facet:url already
-- has) and a poor feature: a model should learn that "GET /api/user/<n>" is ordinary, not
-- memorise every id it has ever seen.
local function template_uri(uri)
	if type(uri) ~= "string" then
		return nil
	end
	local out = uri:gsub("%x%x%x%x%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%-%x%x%x%x%x%x%x%x%x%x%x%x", "<uuid>")
	-- Long hex runs (tokens, hashes, object ids) before the digit pass, which would otherwise
	-- only chew the numeric part of them.
	out = out:gsub("%x+", function(token)
		if #token >= 16 then
			return "<hex>"
		end
		return token
	end)
	out = out:gsub("%d+", "<n>")
	if #out > MAX_TEMPLATED_URI then
		out = out:sub(1, MAX_TEMPLATED_URI) .. "..."
	end
	return out
end

-- Combine two {count, sum, max} aggregates coming from different workers. Counts and sums
-- add; max is the larger of the two. Kept separate from accumulate_timer because that one
-- folds a raw duration and this one folds an already-aggregated peer.
local function merge_timer(acc, other)
	if type(other) ~= "table" then
		return acc
	end
	local count, sum, max = tonumber(other.count) or 0, tonumber(other.sum) or 0, tonumber(other.max) or 0
	if not acc then
		return { count = count, sum = sum, max = max }
	end
	acc.count = acc.count + count
	acc.sum = acc.sum + sum
	if max > acc.max then
		acc.max = max
	end
	return acc
end

-- Does a buffered record belong in Reports? Mirrors _report_clause() in
-- db_methods/metrics.py, which filters the same records again once persisted -- keep the two
-- in step.
-- HTTP: blocked (4xx) or merely detected. A stream record is a report by construction, since
-- log() only ever buffers one when a plugin set a reason, and NGINX session statuses do not
-- live in the 4xx range. Records written before `protocol` existed are HTTP.
local function is_report(request)
	local protocol = request.protocol
	if protocol and protocol ~= "http" then
		return true
	end
	return (request.status and request.status >= 400 and request.status < 500) or request.security_mode == "detect"
end

local shared = ngx.shared
local subsystem = ngx.config.subsystem
local HTTP_INTERNAL_SERVER_ERROR = ngx.HTTP_INTERNAL_SERVER_ERROR
local HTTP_OK = ngx.HTTP_OK
local HTTP_BAD_REQUEST = ngx.HTTP_BAD_REQUEST
local HTTP_FORBIDDEN = ngx.HTTP_FORBIDDEN
local HTTP_SERVICE_UNAVAILABLE = ngx.HTTP_SERVICE_UNAVAILABLE
local worker = ngx.worker
local worker_id = worker.id
local worker_pid = worker.pid

local crc32_short = ngx.crc32_short
local get_reason = utils.get_reason
local has_variable = utils.has_variable
local is_connection_error = utils.is_connection_error
local is_oom_error = utils.is_oom_error
local encode = cjson.encode
local decode = cjson.decode

local function stream_requests_key()
	return "stream_requests_" .. tostring(worker_pid())
end

local match = string.match
local math_min = math.min
-- LuaJIT keeps unpack as a global; Lua 5.2+ moved it to table.unpack. Accept either so the
-- module also loads under a plain-Lua test harness. luacheck runs with --std min (5.1),
-- where table.unpack does not exist -- hence the ignore.
local unpack = unpack or table.unpack -- luacheck: ignore 143
local time = os.time
local tonumber = tonumber
local tostring = tostring
local table_insert = table.insert
local table_remove = table.remove

local REQUEST_FACET_FIELDS = { "ip", "country", "method", "url", "status", "reason", "server_name", "security_mode" }

-- Bounded set of nginx $upstream_cache_status values counted per served request
-- (reverseproxy proxy_cache). Distinct axis from the blocked-request facets above;
-- keeps the cache-status counter cardinality fixed and skips nil/unknown statuses.
local CACHE_STATUS_VALUES = {
	HIT = true,
	MISS = true,
	BYPASS = true,
	EXPIRED = true,
	STALE = true,
	UPDATING = true,
	REVALIDATED = true,
}

-- Deduplicate at the Redis sink as well as in HTTP memory: a lost ACK can be retried through
-- another HTTP worker. Any failed write removes the row and ID while the script still owns
-- the tail. Facet OOM invalidates every derived index for a clean rebuild next cycle; unlike
-- HINCRBY rollback, DEL/RPOP/SREM are safe while Redis rejects memory-growing commands.
-- ARGV[1]=json, ARGV[2]=request id, ARGV[3..10]=facet values.
local PUSH_SCRIPT = [==[
  if redis.call('GET', 'requests:facets:initialized') ~= '1' then
    return {err = 'request indexes need rebuild'}
  end
  if redis.call('SISMEMBER', KEYS[2], ARGV[2]) == 1 then
    return 0
  end
  local pushed = redis.pcall('RPUSH', KEYS[1], ARGV[1])
  if type(pushed) == 'table' and pushed.err then
    return pushed
  end
  local indexed = redis.pcall('SADD', KEYS[2], ARGV[2])
  if type(indexed) == 'table' and indexed.err then
    redis.call('RPOP', KEYS[1])
    return indexed
  end
  local fields = {'ip','country','method','url','status','reason','server_name','security_mode'}
  for i = 1, #fields do
    local facet = redis.pcall('HINCRBY', 'requests:facet:' .. fields[i], ARGV[2 + i], 1)
    if type(facet) == 'table' and facet.err then
      redis.call('RPOP', KEYS[1])
      redis.call('SREM', KEYS[2], ARGV[2])
      redis.call('DEL', 'requests:facets:initialized')
      for j = 1, #fields do redis.call('DEL', 'requests:facet:' .. fields[j]) end
      return facet
    end
  end
  return pushed
]==]

-- The OOM probe catches the common failure before mutation. If a later decrement still fails,
-- the absent completion marker forces a rebuild from the unchanged list. ARGV[1]=max_requests.
local TRIM_SCRIPT = [==[
  local max = tonumber(ARGV[1])
  if not max or max < 0 then max = 0 end
  local fields = {'ip','country','method','url','status','reason','server_name','security_mode'}
  local function clear_indexes()
    redis.call('DEL', 'requests:facets:initialized')
    redis.call('DEL', KEYS[2])
    for i = 1, #fields do redis.call('DEL', 'requests:facet:' .. fields[i]) end
  end
  if max == 0 then
    redis.call('DEL', KEYS[1])
    clear_indexes()
    local marked = redis.pcall('SET', 'requests:facets:initialized', '1')
    if type(marked) == 'table' and marked.err then return marked end
    return 0
  end
  local nb = redis.call('LLEN', KEYS[1])
  if nb <= max then return 0 end
  local probe = redis.pcall('SET', 'requests:facets:oomprobe', '1', 'PX', 1)
  if type(probe) == 'table' and probe.err then
    return probe
  end
  redis.call('DEL', 'requests:facets:initialized')
  local to_remove = nb - max
  local items = redis.call('LRANGE', KEYS[1], 0, to_remove - 1)
  for _, raw in ipairs(items) do
    local ok, req = pcall(cjson.decode, raw)
    if not ok or type(req) ~= 'table' then
      clear_indexes()
      local trimmed = redis.pcall('LTRIM', KEYS[1], to_remove, -1)
      if type(trimmed) == 'table' and trimmed.err then return trimmed end
      return {err = 'invalid request payload while trimming'}
    end
    if req.id ~= nil and req.id ~= cjson.null and req.id ~= '' then
      local removed = redis.pcall('SREM', KEYS[2], tostring(req.id))
      if type(removed) == 'table' and removed.err then
        clear_indexes()
        return removed
      end
    end
    for i = 1, #fields do
      local v = req[fields[i]]
      if v == nil or v == cjson.null or v == '' then v = 'N/A' else v = tostring(v) end
      local n = redis.pcall('HINCRBY', 'requests:facet:' .. fields[i], v, -1)
      if type(n) == 'table' and n.err then
        clear_indexes()
        return n
      end
      if n <= 0 then
        local deleted = redis.pcall('HDEL', 'requests:facet:' .. fields[i], v)
        if type(deleted) == 'table' and deleted.err then
          clear_indexes()
          return deleted
        end
      end
    end
  end
  local trimmed = redis.pcall('LTRIM', KEYS[1], to_remove, -1)
  if type(trimmed) == 'table' and trimmed.err then
    clear_indexes()
    return trimmed
  end
  local marked = redis.pcall('SET', 'requests:facets:initialized', '1')
  if type(marked) == 'table' and marked.err then
    clear_indexes()
    return marked
  end
  return to_remove
]==]

-- Marker invalidated up-front so an OOM-aborted rebuild retries next cycle instead
-- of latching a partial result.
-- ponytail: one atomic LRANGE + 8xN HINCRBY blocks Redis; fine as it only fires on
-- rare facet desync, and chunking would break atomicity.
local REBUILD_SCRIPT = [==[
  local fields = {'ip','country','method','url','status','reason','server_name','security_mode'}
  local function clear_indexes()
    redis.call('DEL', KEYS[2])
    for i = 1, #fields do redis.call('DEL', 'requests:facet:' .. fields[i]) end
  end
  local probe = redis.pcall('SET', 'requests:facets:oomprobe', '1', 'PX', 1)
  if type(probe) == 'table' and probe.err then return probe end
  redis.call('DEL', 'requests:facets:initialized')
  clear_indexes()
  local items = redis.call('LRANGE', KEYS[1], 0, -1)
  local kept = 0
  for _, raw in ipairs(items) do
    local ok, req = pcall(cjson.decode, raw)
    local id
    if ok and type(req) == 'table' then id = req.id end
    if type(id) ~= 'string' or id == '' then
      redis.call('LREM', KEYS[1], 1, raw)
    else
      local r = redis.pcall('SADD', KEYS[2], tostring(id))
      if type(r) == 'table' and r.err then
        clear_indexes()
        return r
      end
      if r == 0 then
        redis.call('LREM', KEYS[1], 1, raw)
      else
        kept = kept + 1
        for i = 1, #fields do
          local v = req[fields[i]]
          if v == nil or v == cjson.null or v == '' then v = 'N/A' else v = tostring(v) end
          local r = redis.pcall('HINCRBY', 'requests:facet:' .. fields[i], v, 1)
          if type(r) == 'table' and r.err then
            clear_indexes()
            return r
          end
        end
      end
    end
  end
  redis.call('SET', 'requests:facets:initialized', '1')
  return kept
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
	local _, err = self:redis_call("eval", TRIM_SCRIPT, 2, "requests", "requests:ids", tostring(max_requests))
	if err then
		self:log_throttled(ERR, "cap_enforce", "Can't enforce Redis requests cap: " .. err)
	end
end

-- Read-only probes (never denyoom), so they run even under OOM. Every stored request contributes
-- all eight facets (using N/A when absent) and one ID; any missing index triggers a full rebuild.
local function self_heal_request_facets(self)
	local nb_raw = self:redis_call("llen", "requests")
	local nb = tonumber(nb_raw) or 0
	local marker = self:redis_call("get", "requests:facets:initialized")
	local marked = marker ~= nil and marker ~= false and marker ~= null and tostring(marker) == "1"
	local facets_present = false
	local facets_complete = true
	for _, field in ipairs(REQUEST_FACET_FIELDS) do
		local facet_len_raw = self:redis_call("hlen", "requests:facet:" .. field)
		local facet_len = tonumber(facet_len_raw) or 0
		if facet_len > 0 then
			facets_present = true
		else
			facets_complete = false
		end
	end
	local ids_len_raw = self:redis_call("scard", "requests:ids")
	local ids_len = tonumber(ids_len_raw) or 0
	if nb == 0 then
		if not marked then
			local _, clear_err = self:redis_call("eval", TRIM_SCRIPT, 2, "requests", "requests:ids", "0")
			if clear_err then
				self:log_throttled(ERR, "facet_clear", "Can't clear request facets: " .. clear_err)
			end
		else
			if facets_present or ids_len > 0 then
				local _, clear_err = self:redis_call("eval", TRIM_SCRIPT, 2, "requests", "requests:ids", "0")
				if clear_err then
					self:log_throttled(ERR, "facet_clear", "Can't clear request facets: " .. clear_err)
				end
			end
		end
		return
	end
	if not facets_complete or ids_len ~= nb or not marked then
		local _, err = self:redis_call("eval", REBUILD_SCRIPT, 2, "requests", "requests:ids")
		if err then
			self:log_throttled(ERR, "facet_rebuild", "Can't rebuild request facets: " .. err)
		end
	end
end

-- EXPIRE is denyoom-safe, so it must run under OOM to make these pinning keys
-- and this worker's metrics keys evictable; it bypasses the redis_ok breaker
-- (dead socket returns an ignored error).
-- Pipelined : these EXPIREs are independent, order-insensitive and their results are
-- all discarded, so buffering them collapses 11+N round-trips into one. Keep this
-- function free of early returns after init_pipeline -- escaping it would leave the
-- client buffering for the rest of the cycle.
local function refresh_request_ttls(self, ttl, wid)
	if not ttl or ttl <= 0 then
		return
	end
	-- While buffering, every call returns nil with no error, so `healthy` cannot be
	-- falsely poisoned; only commit_pipeline reports a real socket failure.
	self.clusterstore:call("init_pipeline")
	self.clusterstore:call("expire", "requests:ids", ttl)
	self.clusterstore:call("expire", "requests", ttl)
	for _, field in ipairs(REQUEST_FACET_FIELDS) do
		self.clusterstore:call("expire", "requests:facet:" .. field, ttl)
	end
	self.clusterstore:call("expire", "requests:facets:initialized", ttl)
	if self.variables["METRICS_SAVE_TO_REDIS"] == "yes" then
		for _, key in ipairs(lru:get_keys()) do
			if key ~= "setup" and key ~= "requests" and key ~= "baseline" then
				if key ~= "stream_requests" then
					self.clusterstore:call("expire", "metrics:" .. key .. ":" .. wid, ttl)
				end
			end
		end
	end
	self.clusterstore:call("commit_pipeline")
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
	self.stream_reports_datastore =
		datastore:new(subsystem == "http" and shared.metrics_stream_reports or shared.metrics_stream_reports_stream)
end

function metrics:init_worker()
	-- Resize the per-worker LRU using the configured MAX_LRU_HISTORY (global setting).
	-- Until this runs, the module-level default LRU sized at DEFAULT_MAX_LRU_HISTORY is
	-- used. The resize is skipped when the configured value matches the default to avoid
	-- dropping any entries collected between module load and init_worker.
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
		local res2, err2 = self.clusterstore:call(method, ...)
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
		-- Geo data is resolved once per request by fill_ctx()
		local country = self.ctx.bw.country or "local"
		local asn_number, asn_org = self.ctx.bw.asn_number, self.ctx.bw.asn_org
		-- ngx.status is HTTP-only; stream carries the session status in $status (200/400/403/
		-- 500/502/503). Both are stored raw and read against `protocol`, which says which
		-- vocabulary the number belongs to. Stream denies used to be pinned to 403 so that the
		-- 4xx-or-detect report filter would keep them -- an HTTP code invented for a session
		-- that never had one. The filter carries a protocol arm now instead, here and in the
		-- two query paths below, so the real session status survives.
		local status
		if subsystem == "http" then
			status = ngx.status
		else
			status = tonumber(ngx.var.status) or 0
		end
		local request = {
			id = self.ctx.bw.request_id,
			date = self.ctx.bw.start_time or time(),
			-- "http" covers https too: this column discriminates request from session, and the
			-- TLS detail is already carried by the baseline's own `scheme`/`ssl_protocol`.
			protocol = subsystem == "http" and "http" or (self.ctx.bw.protocol or "tcp"),
			ip = self.ctx.bw.remote_addr,
			country = country,
			status = status,
			reason = reason,
			server_name = self.ctx.bw.server_name,
			data = data,
			security_mode = security_mode,
			synced = not self.use_redis,
			asn_number = asn_number,
			asn_org = asn_org,
		}
		if subsystem == "http" then
			request.method = self.ctx.bw.request_method
			request.url = self.ctx.bw.request_uri
			request.user_agent = self.ctx.bw.http_user_agent or ""
		else
			-- L4 dimensions, every one of them a free log-phase variable. method/url/user_agent
			-- are deliberately left unset: fill_ctx() still synthesizes them because plugins
			-- branch on them in stream, but nothing fabricated is persisted.
			request.listen_port = tonumber(ngx.var.server_port)
			request.client_port = tonumber(ngx.var.remote_port)
			request.bytes_sent = tonumber(ngx.var.bytes_sent)
			request.bytes_received = tonumber(ngx.var.bytes_received)
			request.session_time = tonumber(ngx.var.session_time)
		end
		local requests = subsystem == "stream" and stream_requests or lru:get("requests") or {}

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

		if subsystem ~= "stream" then
			lru:set("requests", requests)
		end
	end
	-- Count proxy_cache hit/miss for served requests. Distinct axis from the
	-- blocked-request facets above (never touches the `requests` list): reads the
	-- reverseproxy plugin's $upstream_cache_status (also emitted as the
	-- X-Proxy-Cache header) and increments a bounded per-status counter. nil status
	-- (non-cached requests) is skipped. Exposed via GET /metrics/reverseproxy.
	local cache_status = ngx.var.upstream_cache_status
	if cache_status and CACHE_STATUS_VALUES[cache_status] then
		local lru_key = "reverseproxy_counter_cache_status_" .. cache_status
		local counter = lru:get(lru_key)
		lru:set(lru_key, (counter or 0) + 1)
	end
	-- Sampled baseline of NORMAL traffic. The record above only ever exists when a plugin set
	-- a reason, so the table describes exclusively what was blocked and an anomaly model has
	-- no notion of what ordinary traffic looks like. Every field here is already resolved by
	-- fill_ctx or is a free log-phase NGINX variable, so collection costs no new work on the
	-- request path -- the cost is storage, which is why the sample rate defaults to 0.
	--
	-- The client IP is deliberately NOT stored: this is a model of traffic *shape*, not of
	-- who sent it, and recording every ordinary visitor's address is a far larger privacy
	-- commitment than recording the ones that got blocked.
	-- HTTP only: nearly every field below is an HTTP notion ($request_time, $body_bytes_sent,
	-- scheme, content-type...) and none of them exist for a raw L4 session.
	if not reason and subsystem == "http" then
		local rate = self.variables["METRICS_BASELINE_SAMPLE_RATE"]
		local request_id = self.ctx.bw.request_id
		if request_id and should_sample(crc32_short(request_id), rate) then
			local baseline = lru:get("baseline") or {}
			table_insert(baseline, {
				-- Dedup key for the scrape, exactly like the blocked buffer: the job re-reads
				-- the whole buffer every minute, so without it an overlapping scrape would
				-- insert the same request twice. NGINX-generated, carries no client identity.
				id = request_id,
				date = self.ctx.bw.start_time or time(),
				server_name = self.ctx.bw.server_name,
				method = self.ctx.bw.request_method,
				uri = template_uri(self.ctx.bw.uri),
				status = ngx.status,
				request_time = tonumber(ngx.var.request_time),
				request_length = tonumber(ngx.var.request_length),
				body_bytes_sent = tonumber(ngx.var.body_bytes_sent),
				upstream_time = tonumber(ngx.var.upstream_response_time),
				connection_requests = tonumber(ngx.var.connection_requests),
				http_version = self.ctx.bw.http_version,
				scheme = self.ctx.bw.scheme,
				content_type = self.ctx.bw.http_content_type,
				content_length = tonumber(self.ctx.bw.http_content_length),
				ssl_protocol = ngx.var.ssl_protocol,
				ssl_cipher = ngx.var.ssl_cipher,
				country = self.ctx.bw.country,
				asn_number = self.ctx.bw.asn_number,
				ip_version = self.ctx.bw.ip_version,
				user_agent = self.ctx.bw.http_user_agent,
			})
			-- Drop oldest first, like the blocked buffer. A burst silently biases the sample
			-- rather than growing memory; lowering the rate is the fix, not a bigger cap.
			local max_baseline = parse_count(self.variables["METRICS_MAX_BASELINE_REQUESTS"]) or 1000
			while #baseline > max_baseline do
				table_remove(baseline, 1)
			end
			lru:set("baseline", baseline)
		end
	end
	-- Whole-request duration, taken from NGINX's own accounting rather than measured in Lua:
	-- $request_time costs nothing here, needs no update_time(), and is the single most useful
	-- feature for the anomaly baseline. Unlike the per-plugin timers it is always collected.
	-- HTTP-only: the stream equivalent is $session_time, which measures a different thing
	-- (whole connection lifetime, not request latency) and would skew the aggregate.
	local request_time = tonumber(ngx.var.request_time)
	if request_time then
		lru:set("metrics_timer_request", accumulate_timer(lru:get("metrics_timer_request"), request_time))
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
							metric_counter = metric_value
						else
							metric_counter = metric_counter + metric_value
						end
						lru:set(lru_key, metric_counter)
					end
				-- Fold duration samples into a {count, sum, max} aggregate. One slot per
				-- (plugin, phase) instead of one per observation, so the timing axis costs a
				-- bounded number of LRU slots however much traffic flows through it.
				elseif kind == "timers" then
					for metric_key, metric_value in pairs(kind_metrics) do
						local lru_key = plugin_id .. "_timer_" .. metric_key
						lru:set(lru_key, accumulate_timer(lru:get(lru_key), metric_value))
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

-- Stream counterpart of log(). Same report path : the subsystem-specific bits (status source,
-- baseline sampling, $request_time, $upstream_cache_status) are already branched inside log(),
-- so there is nothing to duplicate here. Blocked TCP/UDP sessions used to reach no persistent
-- store at all -- they only produced an INFO line in the NGINX log.
function metrics:log_stream()
	return self:log()
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

-- Stream half of the handover documented on api_ingest_stream_reports(): drain this worker's
-- buffered reports and POST them to the instance's own API over loopback. Runs from the timer
-- phase, never from log_stream -- cosockets are forbidden in the log phase, which is the same
-- reason badbehavior queues its increments instead of banning inline.
--
-- The batch is only dropped once the API has acknowledged it. On failure it stays in memory
-- and the next tick retries, bounded by METRICS_MAX_BLOCKED_REQUESTS like every other buffer
-- here, so an API that is down costs bounded memory rather than an unbounded backlog.
local function push_stream_reports(max_requests)
	local requests = stream_requests
	if not requests or #requests == 0 then
		return true, "no stream reports to push"
	end

	-- Encode before detaching the queue so even an unexpected cjson failure leaves it intact.
	local encoded, payload = pcall(encode, { requests = requests })
	if not encoded then
		return false, "can't encode stream reports : " .. tostring(payload)
	end

	-- Take the batch and hand the buffer a fresh table right away. log_stream() keeps appending
	-- to it while the cosocket below yields --
	-- so anything logged mid-flight would be appended to the very table being sent, then
	-- counted as acknowledged and dropped without ever having been transmitted.
	local batch = requests
	local count = #batch
	stream_requests = {}

	local function keep_for_next_tick()
		local pending = stream_requests
		for index = count, 1, -1 do
			table_insert(pending, 1, batch[index])
		end
		-- Same bound as everywhere else here: an API that stays down costs bounded memory.
		while #pending > (max_requests or 1000) do
			table_remove(pending, 1)
		end
	end

	local call_ok, res, err = pcall(internal_api.request, "/metrics/stream-reports", {
		method = "POST",
		headers = { ["Content-Type"] = "application/json" },
		body = payload,
	})
	if not call_ok then
		keep_for_next_tick()
		return false, "can't push stream reports to the API : " .. tostring(res)
	end
	if not res then
		keep_for_next_tick()
		return false, "can't push stream reports to the API : " .. tostring(err)
	end
	if res.status ~= HTTP_OK then
		keep_for_next_tick()
		return false, "API refused stream reports with status " .. tostring(res.status)
	end
	local ack_ok, ack = pcall(decode, res.body or "")
	if
		not ack_ok
		or type(ack) ~= "table"
		or ack.status ~= "success"
		or type(ack.msg) ~= "table"
		or tonumber(ack.msg.accepted) ~= count
	then
		keep_for_next_tick()
		return false, "API returned an invalid stream reports acknowledgement"
	end

	return true, "pushed " .. count .. " stream reports"
end

local function persist_stream_reports(self)
	local key = stream_requests_key()
	local encoded, reports = pcall(encode, stream_requests)
	if not encoded then
		return false, reports, key
	end
	local ok, err = self.stream_reports_datastore:set(key, reports)
	if ok then
		self.metrics_datastore:delete(key)
	end
	return ok, err, key
end

local function sync_request_buffer(self, value)
	local index = 1
	while index <= #value do
		local request = value[index]
		if type(request.id) ~= "string" or request.id == "" then
			self:log_throttled(ERR, "sync_request", "Can't sync request without a stable id")
			table_remove(value, index)
		else
			if not request.synced then
				local facets = {}
				for i, field in ipairs(REQUEST_FACET_FIELDS) do
					facets[i] = get_request_facet_value(request, field)
				end
				local ok, err = self:redis_call(
					"eval",
					PUSH_SCRIPT,
					2,
					"requests",
					"requests:ids",
					encode(request),
					request.id,
					facets[1],
					facets[2],
					facets[3],
					facets[4],
					facets[5],
					facets[6],
					facets[7],
					facets[8]
				)
				if not ok then
					self:log_throttled(ERR, "sync_request", "Can't sync request to Redis: " .. (err or "unknown error"))
					break
				end
				request.synced = true
			end
			index = index + 1
		end
	end
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

	-- Purpose of following code is to populate the LRU cache.
	-- In case of a reload, everything in LRU cache is removed
	-- so we need to copy it from SHM cache if it exists.
	local setup = lru:get("setup")
	if not setup then
		for _, key in ipairs(self.metrics_datastore:keys()) do
			if key:match("_" .. wid .. "$") and key ~= "stream_requests_" .. wid then
				local value
				value, err = self.metrics_datastore:get(key)
				if not value and err ~= "not found" then
					ret = false
					ret_err = err
					self.logger:log(ERR, "error while checking " .. key .. " : " .. err)
				end
				if value then
					local ok, decoded = pcall(decode, value)
					if ok then
						value = decoded
					end
					lru:set(key:gsub("_" .. wid .. "$", ""), value)
				end
			end
		end
		local restored_stream_requests = {}
		local seen = {}
		local function remember_stream_requests(requests)
			if type(requests) ~= "table" then
				return
			end
			for _, request in ipairs(requests) do
				if type(request) == "table" and type(request.id) == "string" and not seen[request.id] then
					seen[request.id] = true
					table_insert(restored_stream_requests, request)
				end
			end
		end
		for _, store in ipairs({ self.metrics_datastore, self.stream_reports_datastore }) do
			for _, key in ipairs(store:keys()) do
				if key:match("^stream_requests_[0-9]+$") then
					local persisted = store:get(key)
					if persisted then
						local ok, decoded = pcall(decode, persisted)
						if ok and type(decoded) == "table" then
							remember_stream_requests(decoded)
						end
					end
				end
			end
		end
		remember_stream_requests(stream_requests)
		for index = #stream_requests, 1, -1 do
			stream_requests[index] = nil
		end
		for index, request in ipairs(restored_stream_requests) do
			stream_requests[index] = request
		end
		lru:set("setup", true)
	end

	self.redis_ok = nil
	local ttl = parse_count(self.variables["METRICS_REDIS_TTL"]) or 0
	-- Stays true after the OOM breaker trips redis_ok, so the TTL refresh still runs.
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
			self_heal_request_facets(self)
		end
	end

	-- Loop on all keys
	for _, key in ipairs(lru:get_keys()) do
		-- Get LRU data
		local value = lru:get(key)
		if self.redis_ok then
			if key == "requests" then
				-- Stream workers only hand reports over. The HTTP worker that installs the
				-- batch is the sole Redis owner, preventing the same report being pushed once
				-- before handover and again after it.
				if subsystem == "http" then
					sync_request_buffer(self, value)
					-- Update LRU cache
					lru:set(key, value)
				end
			-- Timer aggregates are a {count, sum, max} hash. The list sync below iterates
			-- table values with ipairs, so it would DEL the key and push nothing, leaving an
			-- empty Redis key and burning a DEL per timer per tick. They are read from the
			-- shm through GET /metrics/<plugin>, which needs no Redis, so skip them here.
			-- ponytail: no cross-instance timer aggregation. Sync them as a Redis hash if a
			-- consumer ever needs it.
			elseif key == "baseline" or key:match("_timer_") then -- luacheck: ignore 542
			elseif key ~= "setup" and self.variables["METRICS_SAVE_TO_REDIS"] == "yes" then
				-- Sync other metrics (counters and tables) to Redis with optimized data structures
				local redis_key = "metrics:" .. key .. ":" .. wid
				local ok
				if type(value) == "table" then
					-- Use Redis list for table values
					ok, err = self:redis_call("del", redis_key)
					if ok then
						-- One RPUSH per chunk instead of one per item. Per-item error
						-- attribution is lost, but the only actionable failure was the
						-- socket one and the chunk result still reports that.
						-- ponytail: 512 items per call -- LuaJIT's unpack() argument
						-- ceiling is ~8000 and MAX_LRU_HISTORY accepts values like "1m".
						local items = {}
						for _, item in ipairs(value) do
							items[#items + 1] = type(item) == "table" and encode(item) or tostring(item)
						end
						local total = #items
						local first = 1
						while first <= total do
							local last = math_min(first + 511, total)
							ok, err = self:redis_call("rpush", redis_key, unpack(items, first, last))
							if not ok then
								self:log_throttled(
									ERR,
									"sync_table_items",
									"Can't push metric table items " .. key .. " to Redis: " .. err
								)
								break
							end
							first = last + 1
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
					ok, err = self:redis_call("set", redis_key, value)
					if not ok then
						self:log_throttled(
							ERR,
							"sync_counter",
							"Can't sync metric counter " .. key .. " to Redis: " .. err
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
		if key == "baseline" then
			-- Baseline is best-effort model input. safe_set refuses to evict security reports
			-- from the shared dict when the sampled buffer does not fit.
			ok, err = self.metrics_datastore:set(key .. "_" .. wid, value)
		else
			ok, err = self.metrics_datastore:set_with_retries(
				key .. "_" .. wid,
				value,
				nil,
				tonumber(self.variables["METRICS_MEMORY_MAX_RETRIES"]) or 5
			)
		end
		if not ok then
			-- If there isn't enough memory : we fallback to delete everything
			if err == "no memory" then
				self.logger:log(INFO, "not enough memory in the metrics datastore, purging LRU key " .. key)
				lru:delete(key)
			else
				ret = false
				ret_err = err
				self:log_throttled(ERR, "datastore_set", "can't set " .. key .. "_" .. wid .. " : " .. err)
			end
		end
	end

	-- Keep Stream reports outside the capacity-limited metrics LRU, but persist the same
	-- bounded table before handing it to HTTP so a reload cannot lose it.
	if self.redis_ok and subsystem == "http" then
		sync_request_buffer(self, stream_requests)
	end
	local stream_ok, stream_err, stream_key = persist_stream_reports(self)
	if not stream_ok then
		ret = false
		ret_err = stream_err
		self:log_throttled(ERR, "stream_reports_store", "can't set " .. stream_key .. " : " .. tostring(stream_err))
	end

	if self.redis_ok then
		enforce_redis_requests_cap(self)
	end
	if redis_connected and ttl > 0 then
		refresh_request_ttls(self, ttl, wid)
	end
	-- Always attempt cleanup when Redis was used, even if connection dropped mid-cycle.
	-- clusterstore:close() handles the "client is not instantiated" case gracefully.
	if self.use_redis then
		self.clusterstore:close()
	end

	-- Hand this stream worker's reports over to the HTTP subsystem, which owns the only shm the
	-- scrape job can read. Done after the flush above so the shm copy survives a worker restart.
	if subsystem == "stream" then
		local pushed, push_msg =
			push_stream_reports(parse_count(self.variables["METRICS_MAX_BLOCKED_REQUESTS"]) or 1000)
		if not pushed then
			self:log_throttled(ERR, "stream_reports_push", push_msg)
		else
			self.logger:log(INFO, push_msg)
		end
		-- push_stream_reports() yields: persist the replacement queue so reports logged while
		-- the POST was in flight survive a reload before the next timer tick.
		stream_ok, stream_err, stream_key = persist_stream_reports(self)
		if not stream_ok then
			ret = false
			ret_err = stream_err
			self:log_throttled(ERR, "stream_reports_store", "can't set " .. stream_key .. " : " .. tostring(stream_err))
		end
	end

	-- Flush any end-of-window recaps for errors that stopped repeating.
	self:flush_log_recaps()

	-- Done
	return self:ret(ret, ret_err)
end

-- Receives the reports a stream worker buffered and installs them in an independent HTTP-side
-- queue. The shared-memory write happens before the 200 response, making an acknowledged batch
-- visible across workers and durable across a reload; the sender can safely replay a lost ACK.
function metrics:api_ingest_stream_reports()
	if self.ctx.bw.remote_addr ~= "unix:" then
		return self:ret(true, "stream reports ingestion is internal only", HTTP_FORBIDDEN)
	end
	ngx.req.read_body()
	local body = ngx.req.get_body_data()
	if not body then
		local body_file = ngx.req.get_body_file()
		if body_file then
			local file, file_err = io.open(body_file, "rb")
			if not file then
				return self:ret(true, "can't read stream reports body : " .. tostring(file_err), HTTP_BAD_REQUEST)
			end
			body, file_err = file:read("*a")
			file:close()
			if not body then
				return self:ret(true, "can't read stream reports body : " .. tostring(file_err), HTTP_BAD_REQUEST)
			end
		end
	end
	if not body then
		return self:ret(true, "no body", HTTP_BAD_REQUEST)
	end
	local ok, decoded = pcall(decode, body)
	if not ok or type(decoded) ~= "table" or type(decoded.requests) ~= "table" then
		return self:ret(true, "malformed stream reports payload", HTTP_BAD_REQUEST)
	end

	-- Validate the complete dense array before touching either LRU or shared memory. The query
	-- path compares status numerically and may sort every report-facing scalar directly.
	local string_fields = {
		"ip",
		"country",
		"method",
		"url",
		"user_agent",
		"reason",
		"server_name",
		"security_mode",
	}
	local function is_finite_number(value)
		return type(value) == "number" and value == value and value ~= math.huge and value ~= -math.huge
	end
	local request_count = 0
	local highest_index = 0
	for index, request in pairs(decoded.requests) do
		local valid = not (
			type(index) ~= "number"
			or index < 1
			or index % 1 ~= 0
			or type(request) ~= "table"
			or type(request.id) ~= "string"
			or request.id == ""
			or not is_finite_number(request.date)
			or not is_finite_number(request.status)
			or type(request.synced) ~= "boolean"
			or (request.asn_number ~= nil and not is_finite_number(request.asn_number))
			or (request.asn_org ~= nil and type(request.asn_org) ~= "string")
		)
		if valid then
			for _, field in ipairs(string_fields) do
				if type(request[field]) ~= "string" then
					valid = false
					break
				end
			end
		end
		if not valid then
			return self:ret(true, "malformed stream reports payload", HTTP_BAD_REQUEST)
		end
		request_count = request_count + 1
		if index > highest_index then
			highest_index = index
		end
	end
	if request_count ~= highest_index then
		return self:ret(true, "malformed stream reports payload", HTTP_BAD_REQUEST)
	end

	local max_requests = parse_count(self.variables["METRICS_MAX_BLOCKED_REQUESTS"]) or 1000
	if request_count > max_requests then
		return self:ret(true, "stream reports payload exceeds the queue limit", HTTP_BAD_REQUEST)
	end

	-- Serialize the cross-worker scan and install in the dedicated lock zone. Keeping this out
	-- of metrics_datastore lets an existing queue be replaced even when that SHM is otherwise full.
	local lock, lock_err = resty_lock:new("worker_lock", { timeout = 0, exptime = 5 })
	if not lock then
		return self:ret(
			true,
			"can't create stream reports ingest lock : " .. tostring(lock_err),
			HTTP_SERVICE_UNAVAILABLE
		)
	end
	local elapsed
	elapsed, lock_err = lock:lock("metrics_stream_reports_ingest")
	if elapsed == nil then
		return self:ret(true, "stream reports ingest is busy : " .. tostring(lock_err), HTTP_SERVICE_UNAVAILABLE)
	end

	local function install_reports()
		local live_requests = stream_requests
		local requests = {}
		local seen = {}
		local function remember(items, install)
			if type(items) ~= "table" then
				return
			end
			for _, request in ipairs(items) do
				if
					type(request) == "table"
					and type(request.id) == "string"
					and request.id ~= ""
					and not seen[request.id]
				then
					seen[request.id] = true
					if install then
						table_insert(requests, request)
					end
				end
			end
		end

		-- Reports already in the regular HTTP queue are not reinstalled, but every Stream
		-- generation is merged into this PID-scoped queue before stale generations are removed.
		remember(lru:get("requests"), false)
		local current_key = stream_requests_key()
		local stale_keys = {}
		local function scan_store(store)
			for _, key in ipairs(store:keys()) do
				if key:match("^requests_[0-9]+$") or key:match("^stream_requests_[0-9]+$") then
					local persisted = store:get(key)
					if persisted then
						local decoded_ok, items = pcall(decode, persisted)
						if decoded_ok then
							if key:match("^stream_requests_[0-9]+$") then
								remember(items, true)
								local pid = tonumber(key:match("^stream_requests_([0-9]+)$"))
								if key ~= current_key and pid and pid < worker_pid() then
									table_insert(stale_keys, { store = store, key = key })
								end
							else
								remember(items, false)
							end
						end
					end
				end
			end
		end
		scan_store(self.metrics_datastore)
		scan_store(self.stream_reports_datastore)

		-- The API can run before timer() has restored this worker's SHM after a reload.
		remember(live_requests, true)

		while #requests > max_requests do
			table_remove(requests, 1)
		end
		local added = 0
		for _, request in ipairs(decoded.requests) do
			if not seen[request.id] then
				seen[request.id] = true
				request.synced = not self.use_redis
				table_insert(requests, request)
				added = added + 1
			end
		end

		-- The incoming batch is at most max_requests, so trimming removes only older Stream rows.
		while #requests > max_requests do
			table_remove(requests, 1)
		end

		local encoded, encoded_requests = pcall(encode, requests)
		if not encoded then
			return self:ret(
				true,
				"can't encode stream reports : " .. tostring(encoded_requests),
				HTTP_INTERNAL_SERVER_ERROR
			)
		end
		local installed, install_err = self.stream_reports_datastore:set(current_key, encoded_requests)
		if not installed then
			return self:ret(
				true,
				"can't install stream reports : " .. tostring(install_err),
				HTTP_INTERNAL_SERVER_ERROR
			)
		end
		self.metrics_datastore:delete(current_key)
		for _, stale in ipairs(stale_keys) do
			stale.store:delete(stale.key)
		end
		-- A timer may be paused in Redis while holding this table. Update that same reference so
		-- it cannot resume after the ACK and overwrite SHM with the pre-install queue.
		for index = #live_requests, 1, -1 do
			live_requests[index] = nil
		end
		for index, request in ipairs(requests) do
			live_requests[index] = request
		end

		return self:ret(true, { accepted = request_count, installed = added }, HTTP_OK)
	end

	local installed, response = pcall(install_reports)
	local unlocked, unlock_err = lock:unlock()
	if not unlocked then
		return self:ret(
			true,
			"can't release stream reports ingest lock : " .. tostring(unlock_err),
			HTTP_INTERNAL_SERVER_ERROR
		)
	end
	if not installed then
		return self:ret(true, "can't install stream reports : " .. tostring(response), HTTP_INTERNAL_SERVER_ERROR)
	end
	return response
end

local function collect_buffered_requests(metrics_datastore, stream_reports_datastore)
	local requests = {}
	local ids = {}
	local function collect(store)
		if not store then
			return
		end
		for _, key in ipairs(store:keys()) do
			if key:match("^requests_[0-9]+$") or key:match("^stream_requests_[0-9]+$") then
				local data = store:get(key)
				if data then
					local ok, decoded = pcall(decode, data)
					if ok and type(decoded) == "table" then
						for _, request in ipairs(decoded) do
							if
								type(request) == "table"
								and type(request.id) == "string"
								and request.id ~= ""
								and not ids[request.id]
							then
								ids[request.id] = true
								table_insert(requests, request)
							end
						end
					end
				end
			end
		end
	end
	collect(metrics_datastore)
	collect(stream_reports_datastore)
	return requests
end

function metrics:api()
	-- Match request
	if not match(self.ctx.bw.uri, "^/metrics/.+$") then
		return self:ret(false, "success")
	end
	-- Extract filter parameter
	local filter = self.ctx.bw.uri:gsub("^/metrics/", "")

	-- The only write on this plugin's API, and the only one that is not client-facing: the
	-- stream subsystem hands over its buffered reports here. ngx.shared is built per
	-- subsystem, so the stream workers' metrics_datastore_stream is unreachable from this
	-- HTTP server -- without this handover a blocked TCP/UDP session could never reach the
	-- scrape job, whatever the storage backend.
	if self.ctx.bw.request_method == "POST" then
		if filter == "stream-reports" then
			return self:api_ingest_stream_reports()
		end
		return self:ret(false, "success")
	end

	if self.ctx.bw.request_method ~= "GET" then
		return self:ret(false, "success")
	end

	-- Handle special /metrics/requests/query endpoint for optimized queries
	if filter == "requests/query" then
		return self:api_requests_query()
	end

	-- Timing aggregates are keyed <plugin>_timer_<phase>, so the prefix filter below can only
	-- reach one plugin at a time. An operator wants the whole picture at once, hence a
	-- dedicated endpoint returning them nested by plugin and phase.
	if filter == "timings" then
		return self:api_timings()
	end
	if filter == "requests" then
		return self:ret(
			true,
			{ requests = collect_buffered_requests(self.metrics_datastore, self.stream_reports_datastore) },
			HTTP_OK
		)
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
			-- Timer aggregates are a {count, sum, max} hash, not an array: the ipairs merge
			-- below iterates nothing on them and would hand back an empty table for every
			-- timing key. Merge them on their own terms instead.
			if key:match("_timer_") and type(data) == "table" then
				metrics_data[metric_key] = merge_timer(metrics_data[metric_key], data)
			elseif type(data) == "table" then
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

-- Split a shm timing key into its plugin and phase. Keys are `<plugin>_timer_<phase>_<wid>`
-- and a phase name may itself contain an underscore (`header_filter`), so the worker suffix
-- is anchored to the end rather than split on the last underscore.
local function parse_timer_key(key)
	if type(key) ~= "string" then
		return nil
	end
	return key:match("^(.-)_timer_(.-)_%d+$")
end

function metrics:api_timings()
	-- One entry per (plugin, phase), summed across this instance's workers. Whole-request
	-- duration shows up here too, as plugin "metrics" / phase "request".
	local timings = {}
	for _, key in ipairs(self.metrics_datastore:keys()) do
		local plugin_id, phase = parse_timer_key(key)
		if plugin_id and phase then
			local data = self.metrics_datastore:get(key)
			if data then
				local ok, decoded = pcall(decode, data)
				if ok and type(decoded) == "table" then
					timings[plugin_id] = timings[plugin_id] or {}
					timings[plugin_id][phase] = merge_timer(timings[plugin_id][phase], decoded)
				end
			end
		end
	end
	return self:ret(true, timings, HTTP_OK)
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
	local all_requests = collect_buffered_requests(self.metrics_datastore, self.stream_reports_datastore)

	-- Filter requests
	local filtered_requests = {}
	for _, request in ipairs(all_requests) do
		-- Filter: HTTP 4xx / detect, or any stream session (see is_report)
		if is_report(request) then
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

	local pane_fields =
		{ "protocol", "ip", "country", "method", "url", "status", "reason", "server_name", "security_mode" }
	for _, field in ipairs(pane_fields) do
		pane_counts[field] = {}
	end

	for _, request in ipairs(all_requests) do
		if is_report(request) then
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
