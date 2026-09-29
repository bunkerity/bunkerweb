#!/usr/bin/env lua
-- OCSP Redis Persistent Queue (Wrapper)
-- Reuses BunkerWeb's shared Redis via common_utils.get_redis_client()
-- Survives scheduler crashes, pod restarts, and node failures
--
-- This is a Lua wrapper that delegates to Python for Redis operations
-- Avoids reinventing connection logic; reuses BunkerWeb's existing infrastructure

local logger = require("bunkerweb.logger")

local _M = {}

-- Redis key prefixes
local REDIS_PREFIX = "ocsp:"
local QUEUE_KEY = REDIS_PREFIX .. "pending"
local VALIDATED_KEY = REDIS_PREFIX .. "validated"
local FAILED_KEY = REDIS_PREFIX .. "failed"
local PROCESSING_KEY = REDIS_PREFIX .. "processing"

-- TTL configuration (seconds)
-- Aligned with 7-day certificate validity:
-- - Validated: 7 days (cert lifetime)
-- - Pending: 1 day (validate quickly before cert expires)
-- - Processing: 1 hour (stale job detection)
local TTL_PENDING = tonumber(os.getenv("OCSP_QUEUE_TTL_PENDING") or "86400") -- 1 day
local TTL_VALIDATED = tonumber(os.getenv("OCSP_QUEUE_TTL_VALIDATED") or "604800") -- 7 days (cert lifetime)
local TTL_PROCESSING = tonumber(os.getenv("OCSP_QUEUE_TTL_PROCESSING") or "3600") -- 1 hour

-- Responder health tracking (exponential backoff)
-- When responder fails, retry with increasing intervals: 5min → 10min → 20min → ... → max
local RESPONDER_INITIAL_RETRY = tonumber(os.getenv("OCSP_RESPONDER_RETRY_INITIAL") or "300") -- 5 minutes
local RESPONDER_MAX_RETRY = tonumber(os.getenv("OCSP_RESPONDER_RETRY_MAX") or "86400") -- 24 hours
local RESPONDER_BACKOFF_MULTIPLIER = 2.0 -- Double interval on each failure
local RESPONDER_HEALTH_KEY = "ocsp:responder_health"  -- Hash: {responder_url: last_failure_time,attempt_count}

-- Request throttling (prevents startup DDOS)
-- Limits how fast we hammer responders on first run with many pending certs
local BATCH_SIZE = tonumber(os.getenv("OCSP_BATCH_SIZE") or "10") -- Process N certs per job cycle
local REQUEST_RATE_LIMIT = tonumber(os.getenv("OCSP_REQUEST_RATE_LIMIT") or "50") -- Max requests/sec to responder
local RATE_LIMIT_JITTER = tonumber(os.getenv("OCSP_RATE_LIMIT_JITTER") or "20") -- Randomize ±20% to avoid thundering herd

-- Fallback: in-memory queue if Redis unavailable
local fallback_queue = {}
local fallback_validated = {}
local redis_client = nil  -- Will be injected from Python or initialized from env

-- Helper: Log with [OCSP-REDIS] prefix
local function log_info(msg)
	logger:info("[OCSP-REDIS] " .. msg)
end

local function log_warn(msg)
	logger:warn("[OCSP-REDIS] " .. msg)
end

-- Initialize Redis client from environment variables (if not injected from Python)
local function initialize_redis_from_env()
	if redis_client then
		return  -- Already initialized or injected
	end

	local use_redis = os.getenv("USE_REDIS") or "no"
	if use_redis:lower() ~= "yes" then
		log_info("USE_REDIS not enabled, using in-memory queue")
		return
	end

	-- Try to load lua-resty-redis (available in OpenResty/nginx context)
	local ok, redis_module = pcall(require, "resty.redis")
	if not ok then
		log_warn("lua-resty-redis not available in scheduler context, using in-memory fallback")
		return
	end

	local redis = redis_module:new()
	local host = os.getenv("REDIS_HOST") or "127.0.0.1"
	local port = tonumber(os.getenv("REDIS_PORT") or "6379")
	local timeout = tonumber(os.getenv("REDIS_TIMEOUT") or "1000")

	-- Set timeout in milliseconds
	redis:set_timeouts(timeout, timeout, timeout)

	local ok, err = redis:connect(host, port)
	if not ok then
		log_warn("Redis connection failed (" .. host .. ":" .. port .. "): " .. (err or "unknown"))
		return
	end

	-- Authenticate if password set
	local password = os.getenv("REDIS_PASSWORD")
	if password then
		local username = os.getenv("REDIS_USERNAME") or "default"
		local auth_ok, auth_err = redis:auth(username, password)
		if not auth_ok then
			log_warn("Redis authentication failed: " .. (auth_err or "unknown"))
			redis:close()
			return
		end
	end

	-- Select database
	local db = tonumber(os.getenv("REDIS_DATABASE") or "0")
	local select_ok, select_err = redis:select(db)
	if not select_ok then
		log_warn("Failed to select Redis DB " .. db .. ": " .. (select_err or "unknown"))
		redis:close()
		return
	end

	-- Verify connection with ping
	local ping_ok, ping_err = redis:ping()
	if not ping_ok then
		log_warn("Redis ping failed: " .. (ping_err or "unknown"))
		redis:close()
		return
	end

	redis_client = redis
	log_info("Redis initialized from environment (host=" .. host .. ", port=" .. port .. ", db=" .. db .. ")")
end

-- Set Redis client (called from Python with BunkerWeb's shared Redis)
function _M.set_redis_client(client)
	redis_client = client
	if client then
		log_info("Using Redis client injected from Python")
	else
		log_warn("No Redis client injected, initializing from environment")
		initialize_redis_from_env()
		if not redis_client then
			log_warn("Failed to initialize Redis, using in-memory fallback")
		end
	end
end

-- Try to initialize Redis at module load time (before any queue operations)
-- This ensures both Python-injected and environment-initialized paths work
if not redis_client then
	initialize_redis_from_env()
end

-- Check if responder is healthy (not in backoff window)
-- Returns: healthy (bool), next_retry_seconds (number)
function _M.is_responder_healthy(responder_url)
	if not responder_url or responder_url == "" then
		return true, 0  -- Unknown responder treated as healthy
	end

	if not redis_client then
		return true, 0  -- No Redis, assume healthy
	end

	local health_ok = pcall(function()
		local health_data = redis_client:hget(RESPONDER_HEALTH_KEY, responder_url)
		if not health_data then
			return true, 0  -- No failure recorded, responder healthy
		end

		-- Parse: "last_failure_time:attempt_count"
		local parts = {}
		for part in health_data:gmatch("[^:]+") do
			table.insert(parts, part)
		end

		if #parts < 2 then
			return true, 0  -- Malformed, treat as healthy
		end

		local last_failure = tonumber(parts[1]) or 0
		local attempt_count = tonumber(parts[2]) or 0
		local current_time = os.time()

		-- Calculate next retry: 5min * 2^(attempts-1), capped at max
		local retry_interval = RESPONDER_INITIAL_RETRY * math.pow(RESPONDER_BACKOFF_MULTIPLIER, attempt_count - 1)
		retry_interval = math.min(retry_interval, RESPONDER_MAX_RETRY)

		local next_retry_time = last_failure + retry_interval
		local wait_seconds = next_retry_time - current_time

		if wait_seconds > 0 then
			-- Still in backoff window
			return false, wait_seconds
		else
			-- Backoff window expired, retry now
			return true, 0
		end
	end)

	if health_ok then
		return true, 0
	else
		log_warn("Redis health check failed, treating responder as healthy")
		return true, 0
	end
end

-- Mark responder as failed (with exponential backoff)
-- Keeps existing staples, prevents retry spam at responder level
-- retry_after_seconds: if provided (from 429 Retry-After), uses that instead of exponential backoff
function _M.mark_responder_failed(responder_url, error, retry_after_seconds)
	if not responder_url or responder_url == "" then
		return false
	end

	if not redis_client then
		return false
	end

	local ok = pcall(function()
		-- Get current attempt count
		local health_data = redis_client:hget(RESPONDER_HEALTH_KEY, responder_url)
		local attempt_count = 0
		if health_data then
			local parts = {}
			for part in health_data:gmatch("[^:]+") do
				table.insert(parts, part)
			end
			attempt_count = tonumber(parts[2]) or 0
		end

		local current_time = os.time()
		local retry_interval

		-- Handle 429 (Too Many Requests) with Retry-After header
		if retry_after_seconds and retry_after_seconds > 0 then
			-- Respect Retry-After, don't increment aggressively
			retry_interval = retry_after_seconds
			-- Still increment attempt but don't backoff as hard
			attempt_count = attempt_count + 1
			log_warn("Responder rate limited: " .. responder_url .. " (429 Retry-After: " .. retry_after_seconds .. "s)")
		else
			-- Regular failure: use exponential backoff
			attempt_count = attempt_count + 1
			retry_interval = RESPONDER_INITIAL_RETRY * math.pow(RESPONDER_BACKOFF_MULTIPLIER, attempt_count - 1)
			retry_interval = math.min(retry_interval, RESPONDER_MAX_RETRY)
			log_warn("Responder failed: " .. responder_url .. " (" .. error .. ")")
		end

		-- Store: "last_failure_time:attempt_count"
		redis_client:hset(RESPONDER_HEALTH_KEY, responder_url, current_time .. ":" .. attempt_count)

		log_info("Responder backoff: retry after " .. retry_interval .. "s (attempt #" .. attempt_count .. ")")
	end)

	return ok ~= nil
end

-- Parse Retry-After header (RFC 7231)
-- Supports both delay-seconds (e.g., "120") and HTTP-date (e.g., "Wed, 21 Oct 2026 07:28:00 GMT")
function _M.parse_retry_after(retry_after_header)
	if not retry_after_header or retry_after_header == "" then
		return nil
	end

	-- Try parsing as seconds (most common)
	local seconds = tonumber(retry_after_header)
	if seconds and seconds > 0 then
		return seconds
	end

	-- Try parsing as HTTP-date (would need date parsing library)
	-- For now, default to minimum backoff if we can't parse
	if retry_after_header:find("GMT") or retry_after_header:find("UTC") then
		-- Rough estimate: assume "soon", use minimum backoff
		log_warn("Retry-After in HTTP-date format (not fully supported), using minimum backoff")
		return RESPONDER_INITIAL_RETRY
	end

	log_warn("Could not parse Retry-After header: " .. retry_after_header)
	return nil
end

-- Mark responder as healthy (reset backoff counter)
function _M.mark_responder_healthy(responder_url)
	if not responder_url or responder_url == "" then
		return false
	end

	if not redis_client then
		return false
	end

	local ok = pcall(function()
		redis_client:hdel(RESPONDER_HEALTH_KEY, responder_url)
		log_info("Responder recovered: " .. responder_url .. " (backoff reset)")
	end)

	return ok ~= nil
end

-- Queue a pending validation
function _M.queue_pending(fingerprint)
	if not fingerprint or fingerprint == "" then
		return false
	end

	if redis_client then
		local ok = pcall(function()
			if not redis_client:hexists(VALIDATED_KEY, fingerprint) and
			   not redis_client:hexists(FAILED_KEY, fingerprint) then
				redis_client:lpush(QUEUE_KEY, fingerprint)
				redis_client:expire(QUEUE_KEY, TTL_PENDING)
				log_info("Queued: " .. fingerprint:sub(1, 16) .. "... (TTL " .. TTL_PENDING .. "s)")
			end
		end)

		if not ok then
			log_warn("Redis queue failed, using fallback")
			table.insert(fallback_queue, fingerprint)
		end
	else
		if not fallback_validated[fingerprint] then
			table.insert(fallback_queue, fingerprint)
			log_info("Queued (fallback): " .. fingerprint:sub(1, 16) .. "...")
		end
	end

	return true
end

-- Get next pending validation
function _M.get_next_pending()
	if redis_client then
		local fingerprint
		local ok = pcall(function()
			fingerprint = redis_client:rpop(QUEUE_KEY)
			if fingerprint then
				redis_client:hset(PROCESSING_KEY, fingerprint, os.time())
				redis_client:expire(PROCESSING_KEY, TTL_PROCESSING)
				log_info("Processing: " .. fingerprint:sub(1, 16) .. "... (TTL " .. TTL_PROCESSING .. "s)")
			end
		end)

		if ok and fingerprint then
			return fingerprint
		elseif not ok then
			log_warn("Redis get_next failed, using fallback")
		end
	end

	if #fallback_queue > 0 then
		local fingerprint = table.remove(fallback_queue)
		log_info("Processing (fallback): " .. fingerprint:sub(1, 16) .. "...")
		return fingerprint
	end

	return nil
end

-- Mark validation as complete
function _M.mark_validated(fingerprint)
	if not fingerprint or fingerprint == "" then
		return false
	end

	if redis_client then
		local ok = pcall(function()
			redis_client:hset(VALIDATED_KEY, fingerprint, os.time())
			redis_client:expire(VALIDATED_KEY, TTL_VALIDATED)
			redis_client:hdel(PROCESSING_KEY, fingerprint)
			redis_client:hdel(FAILED_KEY, fingerprint)
			log_info("Validated: " .. fingerprint:sub(1, 16) .. "... (TTL " .. TTL_VALIDATED .. "s)")
		end)

		if not ok then
			log_warn("Redis mark_validated failed, using fallback")
			fallback_validated[fingerprint] = os.time()
		end
	else
		fallback_validated[fingerprint] = os.time()
		log_info("Validated (fallback): " .. fingerprint:sub(1, 16) .. "...")
	end

	return true
end

-- Mark validation as failed
function _M.mark_failed(fingerprint, error)
	if not fingerprint or fingerprint == "" then
		return false
	end

	local error_msg = error or "unknown error"

	if redis_client then
		local ok = pcall(function()
			redis_client:hset(FAILED_KEY, fingerprint, error_msg)
			redis_client:expire(FAILED_KEY, TTL_FAILED)
			redis_client:hdel(PROCESSING_KEY, fingerprint)
			log_info("Failed: " .. fingerprint:sub(1, 16) .. "... (" .. error_msg .. ") (TTL " .. TTL_FAILED .. "s)")
		end)

		if not ok then
			log_warn("Redis mark_failed failed")
		end
	else
		log_info("Failed (fallback): " .. fingerprint:sub(1, 16) .. "... (" .. error_msg .. ")")
	end

	return true
end

-- Check if validation is complete
function _M.is_validation_complete(fingerprint)
	if not fingerprint or fingerprint == "" then
		return false
	end

	if redis_client then
		local is_complete = false
		local ok = pcall(function()
			is_complete = redis_client:hexists(VALIDATED_KEY, fingerprint) or
						  redis_client:hexists(FAILED_KEY, fingerprint)
		end)

		if ok then
			return is_complete
		else
			log_warn("Redis check failed, using fallback")
		end
	end

	return fallback_validated[fingerprint] ~= nil
end

-- Check if validated (not failed)
function _M.is_validated(fingerprint)
	if not fingerprint or fingerprint == "" then
		return false
	end

	if redis_client then
		local is_valid = false
		local ok = pcall(function()
			is_valid = redis_client:hexists(VALIDATED_KEY, fingerprint)
		end)

		if ok then
			return is_valid
		else
			log_warn("Redis check failed, using fallback")
		end
	end

	return fallback_validated[fingerprint] ~= nil
end

-- Get queue stats
function _M.get_stats()
	local stats = {
		pending = 0,
		processing = 0,
		validated = 0,
		unhealthy_responders = 0,
		using_redis = redis_client ~= nil
	}

	if redis_client then
		local ok = pcall(function()
			stats.pending = redis_client:llen(QUEUE_KEY) or 0
			stats.processing = redis_client:hlen(PROCESSING_KEY) or 0
			stats.validated = redis_client:hlen(VALIDATED_KEY) or 0
			stats.unhealthy_responders = redis_client:hlen(RESPONDER_HEALTH_KEY) or 0
		end)

		if not ok then
			log_warn("Redis stats failed")
		end
	end

	if not stats.using_redis then
		stats.pending = #fallback_queue
		stats.validated = 0
		for _ in pairs(fallback_validated) do
			stats.validated = stats.validated + 1
		end
	end

	return stats
end

-- Cleanup stale processing entries
function _M.cleanup_stale_processing()
	if not redis_client then
		return 0
	end

	local cleaned = 0
	local ok = pcall(function()
		local processing = redis_client:hgetall(PROCESSING_KEY) or {}
		local current_time = os.time()
		local stale_threshold = 3600  -- 1 hour

		for i = 1, #processing, 2 do
			local fingerprint = processing[i]
			local started_at = tonumber(processing[i + 1]) or 0
			local elapsed = current_time - started_at

			if elapsed > stale_threshold then
				log_warn("Cleaning stale: " .. fingerprint:sub(1, 16) .. "...")
				redis_client:hdel(PROCESSING_KEY, fingerprint)
				redis_client:lpush(QUEUE_KEY, fingerprint)
				cleaned = cleaned + 1
			end
		end
	end)

	if ok then
		log_info("Cleanup: moved " .. cleaned .. " stale entries back to queue")
	else
		log_warn("Cleanup failed")
	end

	return cleaned
end

return _M
