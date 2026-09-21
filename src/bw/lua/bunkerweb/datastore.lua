local ngx = ngx
local class = require "middleclass"
local clogger = require "bunkerweb.logger"
local lrucache = require "resty.lrucache"
local datastore = class("datastore")

local logger = clogger:new("DATASTORE")

local ERR = ngx.ERR
local WARN = ngx.WARN
local subsystem = ngx.config.subsystem
local shared = ngx.shared
local match = string.match

-- Default slot count for the per-worker LRU shared by all datastore instances.
-- Overridden via the DATASTORE_LRU_SIZE global setting on the first worker-LRU
-- read/write once the variables store has been populated (lazy: utils.get_variable
-- depends on this very module so resolution is deferred to first call).
local DEFAULT_DATASTORE_LRU = 1000

-- Setting that sizes each shared dict, so an eviction warning can name the knob to turn: this
-- module serves zones sized by three different settings and "the zone size" names none of them.
-- Built by identity, skipping the dicts the running subsystem does not declare, so an absent one
-- cannot be matched by a nil lookup.
local DICT_SIZE_SETTING = {}
for name, setting in pairs({
	metrics_datastore = "METRICS_MEMORY_SIZE",
	metrics_datastore_stream = "METRICS_MEMORY_SIZE",
	metrics_stream_reports = "METRICS_MEMORY_SIZE",
	metrics_stream_reports_stream = "METRICS_MEMORY_SIZE",
	internalstore = "INTERNALSTORE_MEMORY_SIZE",
	internalstore_stream = "INTERNALSTORE_MEMORY_SIZE",
}) do
	if shared[name] then
		DICT_SIZE_SETTING[shared[name]] = setting
	end
end

local lru, err_lru = lrucache.new(DEFAULT_DATASTORE_LRU)
if not lru then
	logger:log(ERR, "failed to instantiate LRU cache : " .. err_lru)
end

-- Parse a count value with optional SI shorthand suffix: "1000", "1k", "10K", "1m".
-- k/K = x1000, m/M = x1_000_000. Returns the integer count, or nil if value is
-- missing or unparsable.
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

-- Migrate every live entry from the old LRU into a freshly-sized one, preserving
-- per-entry user_flags. The only entries present at resize time are the permanent
-- bootstrap keys (variables/plugins/plugin_*/plugins_order) written during
-- init_by_lua before any request-time TTL cache exists, so re-inserting with
-- ttl=nil keeps them permanent. get_keys/get are direct lrucache calls (no
-- datastore re-entry), so the lru_configuring guard is unaffected.
local function migrate_lru(old_lru, new_lru)
	for _, key in ipairs(old_lru:get_keys(0)) do
		local value, _, flags = old_lru:get(key)
		if value ~= nil then
			new_lru:set(key, value, nil, flags)
		end
	end
	return new_lru
end

-- Keys the init phase writes once and every later read depends on. `plugins_order` used to be
-- rewritable at runtime, so a plugin could recompute the phase order from its own init() and
-- silently override the operator's PLUGINS_ORDER_<PHASE> (PRO acme did exactly that). Once the
-- init phase has stored the key it calls datastore.seal() on it and every later mutation is
-- refused : set, set_with_retries and delete return an error, delete_all skips the key and
-- flush_lru preserves it. A reload builds a fresh Lua VM, so the seal is per-configuration and
-- never outlives the order it protects. The seal is keyed by key NAME, shared by every datastore
-- instance and therefore by every zone -- deliberately, since the key is written and read through
-- the per-worker LRU those instances share.
local sealed_keys = {}

-- A key can only be sealed once it actually holds a value. Plugin chunks run unsandboxed during
-- init_by_lua (they are `require`d before the order is computed), so an unconditional setter would
-- let one seal `plugins_order` ahead of init's own write, make that write fail and leave the
-- instance with no order at all -- fail-open. This is an anti-footgun, not a trust boundary: the
-- same plugin code can already call os.execute in this phase.
datastore.static.seal = function(key)
	if lru and lru:get(key) ~= nil then
		sealed_keys[key] = true
		return true
	end
	return false
end

-- The caller's plugin id, when the stack reaches a plugin's Lua half : those are required as
-- `<id>/<id>.lua` (helpers.require_plugin), which is what the back-reference matches. Core code
-- and anonymous chunks yield nil and the key is named instead.
local function caller_plugin_id()
	for level = 2, 12 do
		-- Guarded : this is the only debug.getinfo in src/bw/lua, and it sits on the refusal path.
		-- A stripped or sandboxed `debug` must not turn a refusal into a raised error.
		local info = debug and debug.getinfo(level, "S")
		if not info then
			return nil
		end
		local id = info.source and info.source:match("/([%w_-]+)/%1%.lua$")
		if id then
			return id
		end
	end
	return nil
end

local function refuse_if_sealed(key, action)
	if not sealed_keys[key] then
		return false
	end
	local who = caller_plugin_id()
	logger:log(
		ERR,
		"refused post-init "
			.. action
			.. " of "
			.. key
			.. " by "
			.. (who and ("plugin " .. who) or "an unidentified caller")
			.. " : the key is sealed once the init phase has computed it"
	)
	return true
end

local lru_configured = false
local lru_configuring = false
local function ensure_lru_sized()
	if lru_configured or lru_configuring then
		return
	end
	lru_configuring = true
	-- Lazy require to avoid circular load (utils requires this module at the top).
	local ok_utils, utils = pcall(require, "bunkerweb.utils")
	if not ok_utils or type(utils.get_variable) ~= "function" then
		lru_configuring = false
		return
	end
	-- utils.get_variable reads internalstore via the worker LRU, which re-enters
	-- this module; the lru_configuring guard short-circuits the recursion.
	local value = utils.get_variable("DATASTORE_LRU_SIZE", false)
	lru_configuring = false
	if value == nil then
		-- Variables not yet populated; retry on next call.
		return
	end
	lru_configured = true
	local size = parse_count(value)
	-- Only ever grow the shared bootstrap LRU. A size at or below the default could
	-- LRU-evict the init-time bootstrap entries (variables/plugins/...) and deadlock
	-- startup (bug #3618), so sizes <= default keep the safe default-sized cache.
	if not size or size <= DEFAULT_DATASTORE_LRU then
		return
	end
	local new_lru, err = lrucache.new(size)
	if not new_lru then
		logger:log(ERR, "failed to resize datastore LRU to " .. size .. " : " .. err)
		return
	end
	-- Carry existing entries over before swapping so init-time bootstrap data
	-- (written into the old LRU during init_by_lua) survives the resize.
	lru = lru and migrate_lru(lru, new_lru) or new_lru
end

function datastore:initialize(dict)
	if dict then
		self.dict = dict
	elseif subsystem == "http" then
		self.dict = shared.datastore
	else
		self.dict = shared.datastore_stream
	end
	self.size_setting = (self.dict and DICT_SIZE_SETTING[self.dict]) or "DATASTORE_MEMORY_SIZE"
end

function datastore:get(key, worker)
	-- luacheck: ignore 431
	local value, err
	if worker then
		ensure_lru_sized()
		if not lru then
			return nil, "lru is not instantiated"
		end
		-- lru:get returns value, stale_value, flags : an expired entry is a miss, and its
		-- stale value must not be returned as the error (callers concatenate it).
		value = lru:get(key)
		if value == nil then
			return nil, "not found"
		end
		return value, "success"
	end
	value, err = self.dict:get(key)
	if not value and not err then
		err = "not found"
	end
	return value, err
end

function datastore:set(key, value, exptime, worker)
	if refuse_if_sealed(key, "write") then
		return false, "key " .. key .. " is sealed after init"
	end
	if worker then
		ensure_lru_sized()
		if not lru then
			return false, "lru is not instantiated"
		end
		-- Same convention as the shared dict below : no exptime, zero or a negative one means no
		-- expiry. Zero has to be normalised too : the shared dict reads it as no expiry, while
		-- lrucache reads it as already expired, so passing it through would make the very next
		-- get() a miss.
		if exptime and exptime <= 0 then
			exptime = nil
		end
		lru:set(key, value, exptime)
		return true, "success"
	end
	if exptime == nil or exptime < 0 then
		return self.dict:safe_set(key, value)
	else
		return self.dict:safe_set(key, value, exptime)
	end
end

-- Last time an eviction warning was emitted, per zone. A zone that has reached capacity
-- force-evicts on every single write, and the metrics zone is written for every live key on
-- every timer tick, so anything finer than per-zone turns a saturated zone into a permanent
-- log stream. The zone size is the only fix, so the zone is also the only useful granularity.
local forcible_warned = {}
local FORCIBLE_WARN_INTERVAL = 60

local function warn_forcible(setting, key)
	local now = ngx.time()
	local last = forcible_warned[setting]
	if last and now - last < FORCIBLE_WARN_INTERVAL then
		return
	end
	forcible_warned[setting] = now
	logger:log(WARN, "shared dict is full : writing " .. key .. " evicted an unexpired entry, raise " .. setting)
end

function datastore:set_with_retries(key, value, exptime, max_retries)
	if refuse_if_sealed(key, "write") then
		return false, "key " .. key .. " is sealed after init"
	end
	max_retries = max_retries or 5
	local success, err, forcible
	-- Try multiple times if we need to make room for the new value
	for _ = 1, max_retries do
		if exptime == nil or exptime < 0 then
			success, err, forcible = self.dict:set(key, value)
		else
			success, err, forcible = self.dict:set(key, value, exptime)
		end
		-- Ok case
		if success then
			-- The write succeeded by evicting an unexpired entry. This zone also holds active
			-- bans, so a silent eviction can drop one; the caller only ever sees success, hence
			-- the warning here. Throttled per zone: a zone at capacity force-evicts on every
			-- write, and its size is the only thing the operator can act on.
			if forcible then
				warn_forcible(self.size_setting, key)
			end
			return true, "success"
		end
		-- Unknown error, can't do nothing
		if err ~= "no memory" then
			return false, err
		end
	end
	return false, err or "max retries reached"
end

function datastore:delete(key, worker)
	if refuse_if_sealed(key, "delete") then
		return false, "key " .. key .. " is sealed after init"
	end
	if worker then
		if not lru then
			return false, "lru is not instantiated"
		end
		lru:delete(key)
		return true, "success"
	end
	self.dict:delete(key)
	return true, "success"
end

function datastore:keys(worker)
	if worker then
		if not lru then
			return false, "lru is not instantiated"
		end
		return lru:get_keys(0)
	end
	return self.dict:get_keys(0)
end

function datastore:ttl(key, worker)
	if worker then
		return false, "not supported by LRU"
	end
	-- luacheck: ignore 431
	local ttl, err = self.dict:ttl(key)
	if err then
		return false, err
	end
	if not ttl then
		return true, 0
	end
	return true, ttl
end

function datastore:delete_all(pattern, worker)
	local keys
	if worker then
		if not lru then
			return false, "lru is not instantiated"
		end
		keys = lru:get_keys(0)
	else
		keys = self.dict:get_keys(0)
	end
	for _, key in ipairs(keys) do
		-- A sealed key is skipped rather than refused : delete_all is a pattern sweep, so a
		-- caller that matches one by accident must not lose the whole sweep over it.
		if key:match(pattern) and not sealed_keys[key] then
			if worker then
				lru:delete(key)
			else
				self.dict:delete(key)
			end
		end
	end
	return true, "success"
end

-- luacheck: ignore 212
function datastore:flush_lru()
	if not lru then
		return false, "lru is not instantiated"
	end
	-- Sealed keys survive the flush. `plugins_order` lives only in this LRU, and every phase
	-- runner bails out of its whole phase when the read misses (server-http/access-lua.conf:110),
	-- so losing it fails OPEN -- a flush would be a wider hole than the write the seal refuses.
	-- The init confs call this before anything is sealed, so it is a no-op there.
	-- Re-inserted with ttl = nil, i.e. permanent. Inert today : the only sealed key is
	-- plugins_order and it is written without an expiry (init-lua.conf), like every bootstrap key.
	local kept = {}
	for key in pairs(sealed_keys) do
		local value, _, flags = lru:get(key)
		if value ~= nil then
			kept[key] = { value = value, flags = flags }
		end
	end
	lru:flush_all()
	for key, entry in pairs(kept) do
		lru:set(key, entry.value, nil, entry.flags)
	end
	return true, "success"
end

function datastore:safe_rpush(key, value)
	local length, err = self.dict:rpush(key, value)
	-- Dict is full : evict this key's oldest entries one by one and retry, up to 5 times.
	local i = 0
	while not length and err == "no memory" and i < 5 do
		local val
		val, err = self.dict:lpop(key)
		if not val then
			-- lpop returns nil, nil on an empty or absent list
			return nil, err or "no memory (dict is full and key has nothing to evict)"
		end
		length, err = self.dict:rpush(key, value)
		i = i + 1
	end
	return length, err
end

function datastore:lpop(key)
	return self.dict:lpop(key)
end

function datastore:llen(key)
	return self.dict:llen(key)
end

return datastore
