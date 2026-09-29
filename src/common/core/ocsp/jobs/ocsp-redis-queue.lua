#!/usr/bin/env lua
-- ============================================================================
-- OCSP Persistent Queue with Three-Tier Fallback
-- ============================================================================
-- Provides durable storage for OCSP validation queue across crashes and restarts.
--
-- ARCHITECTURE:
--   This module implements a three-tier fallback system for queue persistence:
--
--   Tier 1: Redis (Best)
--   ├─ Fastest, distributed, HA-ready
--   ├─ Survives scheduler crashes
--   ├─ Configured via redis plugin (REDIS_HOST, REDIS_PORT, etc)
--   └─ Used if available
--
--   Tier 2: File Storage (Good)
--   ├─ Persistent across restarts
--   ├─ No external dependencies (just filesystem)
--   ├─ Directory structure: /var/lib/bunkerweb/ocsp-queue/{pending,validated,failed,processing}/
--   ├─ Each entry is a JSON file: {fingerprint}.json with metadata
--   └─ Used if Redis unavailable
--
--   Tier 3: In-Memory (Minimal)
--   ├─ Fastest but volatile
--   ├─ Lost on process crash
--   ├─ Can be persisted to disk manually via persist_queue_to_disk()
--   └─ Used as last resort, or only tier if file storage unavailable
--
-- USAGE:
--   queue.queue_pending(fingerprint)  -- Add to queue (auto-chooses best tier)
--   queue.get_next_pending()           -- Get next cert (auto-tries all tiers)
--   queue.mark_validated(fingerprint)  -- Mark done
--   queue.mark_failed(fingerprint)     -- Mark failed
--   queue.persist_queue_to_disk()      -- Backup in-memory to disk
--   queue.restore_queue_from_disk()    -- Recover from disk
--   queue.get_storage_status()         -- Check status of all tiers
--
-- MUST-STAPLE PRIORITIZATION:
--   The job (ocsp-async-validate.lua) scans the queue twice:
--   1. Must-staple phase: Finds and validates all must-staple certs
--   2. Optional phase: Validates remaining optional certs
--
--   This works with all three tiers because the prioritization happens
--   at the JOB level (scanning via get_next_pending), not at queue level.
--   As long as get_next_pending() returns certs, prioritization works.
--
-- PERSISTENCE GUARANTEES:
--   - Redis: Durable by default
--   - File: Durable by default
--   - Memory: Volatile, can be persisted via persist_queue_to_disk()
--
--   Recommended: Use Redis or File tier for production (both offer durability)
--
-- CONFIGURATION:
--   Redis settings from redis plugin (environment variables):
--     USE_REDIS=yes/no (enable/disable)
--     REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_USERNAME
--     REDIS_SSL, REDIS_SSL_VERIFY (TLS support)
--
--   File storage settings:
--     Directory: /var/lib/bunkerweb/ocsp-queue/  (created automatically)
--     Permissions: Scheduler process must have r/w access

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

-- Fallback mechanisms (in priority order):
-- 1. Redis (if configured and available)
-- 2. File-based storage (persistent across restarts)
-- 3. In-memory only (no persistence)
--
-- File-based storage uses directory structure:
--   /var/lib/bunkerweb/ocsp-queue/pending/   - awaiting validation
--   /var/lib/bunkerweb/ocsp-queue/validated/ - successfully validated
--   /var/lib/bunkerweb/ocsp-queue/failed/    - failed validation
--   /var/lib/bunkerweb/ocsp-queue/processing/ - currently validating
--
-- Each entry is a JSON file: {fingerprint}.json with metadata

local fallback_queue = {}
local fallback_validated = {}
local redis_client = nil  -- Will be injected from Python or initialized from env

-- File-based queue configuration
local QUEUE_BASE_DIR = "/var/lib/bunkerweb/ocsp-queue"
local QUEUE_PENDING_DIR = QUEUE_BASE_DIR .. "/pending"
local QUEUE_VALIDATED_DIR = QUEUE_BASE_DIR .. "/validated"
local QUEUE_FAILED_DIR = QUEUE_BASE_DIR .. "/failed"
local QUEUE_PROCESSING_DIR = QUEUE_BASE_DIR .. "/processing"

-- Check if file-based storage is available
local function ensure_queue_dirs()
	local dirs = {
		QUEUE_BASE_DIR,
		QUEUE_PENDING_DIR,
		QUEUE_VALIDATED_DIR,
		QUEUE_FAILED_DIR,
		QUEUE_PROCESSING_DIR
	}

	for _, dir in ipairs(dirs) do
		local ok = os.execute("mkdir -p \"" .. dir .. "\" 2>/dev/null")
		if not ok then
			return false
		end
	end

	return true
end

-- Check if file-based queue is available
local file_storage_available = ensure_queue_dirs()

-- ============================================================================
-- Logging Helpers
-- ============================================================================

local function log_info(msg)
	logger:info("[OCSP-REDIS] " .. msg)
end

local function log_warn(msg)
	logger:warn("[OCSP-REDIS] " .. msg)
end

-- ============================================================================
-- File-Based Queue Operations (Fallback Storage)
-- ============================================================================
-- Persists queue entries to disk for durability across restarts.
-- Directory structure:
--   /var/lib/bunkerweb/ocsp-queue/pending/{fingerprint}.json
--   /var/lib/bunkerweb/ocsp-queue/validated/{fingerprint}.json
--   /var/lib/bunkerweb/ocsp-queue/failed/{fingerprint}.json
--   /var/lib/bunkerweb/ocsp-queue/processing/{fingerprint}.json
--
-- Each file contains JSON metadata: {timestamp, attempt_count, error}

local function write_file(path, content)
	local f = io.open(path, "w")
	if not f then
		return false
	end
	f:write(content)
	f:close()
	return true
end

local function read_file(path)
	local f = io.open(path, "r")
	if not f then
		return nil
	end
	local content = f:read("*a")
	f:close()
	return content ~= "" and content or nil
end

local function file_exists(path)
	local f = io.open(path, "r")
	if f then
		f:close()
		return true
	end
	return false
end

local function delete_file(path)
	return os.remove(path) == 0 or os.remove(path) == nil
end

-- List all files in directory (returns table of filenames)
local function list_dir(dir)
	local files = {}
	local ok = pcall(function()
		local handle = io.popen("find \"" .. dir .. "\" -maxdepth 1 -type f -name '*.json' 2>/dev/null")
		if handle then
			for line in handle:lines() do
				local filename = line:match("([^/]+)$")
				if filename then
					table.insert(files, filename:match("^(.+)%.json$"))
				end
			end
			handle:close()
		end
	end)
	return ok and files or {}
end

-- Queue pending cert to file storage
local function file_queue_pending(fingerprint)
	if not fingerprint or fingerprint == "" then
		return false
	end

	local path = QUEUE_PENDING_DIR .. "/" .. fingerprint .. ".json"
	local metadata = '{"fingerprint":"' .. fingerprint .. '","timestamp":' .. os.time() .. '}'

	if write_file(path, metadata) then
		log_info("File queue: pending " .. fingerprint:sub(1, 16) .. "...")
		return true
	else
		log_warn("Failed to write pending file: " .. path)
		return false
	end
end

-- Get next pending cert from file storage
local function file_get_next_pending()
	local pending_certs = list_dir(QUEUE_PENDING_DIR)

	if #pending_certs == 0 then
		return nil
	end

	-- Get first cert (FIFO order by filename)
	table.sort(pending_certs)
	local fingerprint = pending_certs[1]

	-- Move to processing
	local pending_path = QUEUE_PENDING_DIR .. "/" .. fingerprint .. ".json"
	local processing_path = QUEUE_PROCESSING_DIR .. "/" .. fingerprint .. ".json"

	local content = read_file(pending_path)
	if not content then
		delete_file(pending_path)
		return nil
	end

	if write_file(processing_path, content) then
		delete_file(pending_path)
		log_info("File queue: processing " .. fingerprint:sub(1, 16) .. "...")
		return fingerprint
	end

	return nil
end

-- Mark cert as validated in file storage
local function file_mark_validated(fingerprint)
	if not fingerprint or fingerprint == "" then
		return false
	end

	local processing_path = QUEUE_PROCESSING_DIR .. "/" .. fingerprint .. ".json"
	local validated_path = QUEUE_VALIDATED_DIR .. "/" .. fingerprint .. ".json"

	local content = read_file(processing_path)
	if not content then
		content = '{"fingerprint":"' .. fingerprint .. '","timestamp":' .. os.time() .. '}'
	end

	if write_file(validated_path, content) then
		delete_file(processing_path)
		log_info("File queue: validated " .. fingerprint:sub(1, 16) .. "...")
		return true
	end

	return false
end

-- Mark cert as failed in file storage
local function file_mark_failed(fingerprint, reason)
	if not fingerprint or fingerprint == "" then
		return false
	end

	local processing_path = QUEUE_PROCESSING_DIR .. "/" .. fingerprint .. ".json"
	local failed_path = QUEUE_FAILED_DIR .. "/" .. fingerprint .. ".json"

	local content = read_file(processing_path)
	if not content then
		content = '{"fingerprint":"' .. fingerprint .. '","timestamp":' .. os.time() .. '}'
	end

	-- Add error reason to metadata
	local metadata = content:gsub("}", ',"error":"' .. (reason or "unknown") .. '"}')

	if write_file(failed_path, metadata) then
		delete_file(processing_path)
		log_info("File queue: failed " .. fingerprint:sub(1, 16) .. "... (" .. (reason or "unknown") .. ")")
		return true
	end

	return false
end

-- Check if cert is validated in file storage
local function file_is_validated(fingerprint)
	if not fingerprint or fingerprint == "" then
		return false
	end

	local validated_path = QUEUE_VALIDATED_DIR .. "/" .. fingerprint .. ".json"
	return file_exists(validated_path)
end

-- Load and restore in-memory queue from file storage at startup
local function file_restore_queue()
	local pending = list_dir(QUEUE_PENDING_DIR)
	for _, fingerprint in ipairs(pending) do
		table.insert(fallback_queue, fingerprint)
	end

	if #pending > 0 then
		log_info("Restored " .. #pending .. " pending certs from file storage")
	end
end

-- Persist in-memory queue to file storage
local function file_persist_queue()
	for _, fingerprint in ipairs(fallback_queue) do
		file_queue_pending(fingerprint)
	end
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

-- Load file-based queue from disk at startup (persistence recovery)
-- This restores any pending validations that were interrupted
if not redis_client and file_storage_available then
	file_restore_queue()
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
-- ============================================================================
-- Queue Management Functions (with multi-tier fallback)
-- ============================================================================
-- Fallback order: Redis → File Storage → In-Memory
-- This ensures durability even if Redis unavailable.

function _M.queue_pending(fingerprint)
	if not fingerprint or fingerprint == "" then
		return false
	end

	-- Try Redis first
	if redis_client then
		local ok = pcall(function()
			if not redis_client:hexists(VALIDATED_KEY, fingerprint) and
			   not redis_client:hexists(FAILED_KEY, fingerprint) then
				redis_client:lpush(QUEUE_KEY, fingerprint)
				redis_client:expire(QUEUE_KEY, TTL_PENDING)
				log_info("Queued: " .. fingerprint:sub(1, 16) .. "... (Redis)")
			end
		end)

		if ok then
			return true
		else
			log_warn("Redis queue failed, using file storage fallback")
		end
	end

	-- Fall back to file storage
	if file_storage_available and file_queue_pending(fingerprint) then
		return true
	end

	-- Final fallback: in-memory queue
	if not fallback_validated[fingerprint] then
		table.insert(fallback_queue, fingerprint)
		log_info("Queued: " .. fingerprint:sub(1, 16) .. "... (Memory)")
	end

	return true
end

-- Get next pending validation
-- Returns: fingerprint string, or nil if queue empty
-- Fallback order: Redis → File Storage → In-Memory
function _M.get_next_pending()
	-- Try Redis first
	if redis_client then
		local fingerprint
		local ok = pcall(function()
			fingerprint = redis_client:rpop(QUEUE_KEY)
			if fingerprint then
				redis_client:hset(PROCESSING_KEY, fingerprint, os.time())
				redis_client:expire(PROCESSING_KEY, TTL_PROCESSING)
				log_info("Processing: " .. fingerprint:sub(1, 16) .. "... (Redis)")
			end
		end)

		if ok and fingerprint then
			return fingerprint
		elseif not ok then
			log_warn("Redis get_next failed, trying file storage")
		end
	end

	-- Fall back to file storage
	if file_storage_available then
		local fingerprint = file_get_next_pending()
		if fingerprint then
			return fingerprint
		end
	end

	-- Final fallback: in-memory queue
	if #fallback_queue > 0 then
		local fingerprint = table.remove(fallback_queue)
		log_info("Processing: " .. fingerprint:sub(1, 16) .. "... (Memory)")
		return fingerprint
	end

	return nil
end

-- Mark validation as complete
-- Removes from processing, stores in validated
-- Fallback order: Redis → File Storage → In-Memory
function _M.mark_validated(fingerprint)
	if not fingerprint or fingerprint == "" then
		return false
	end

	-- Try Redis first
	if redis_client then
		local ok = pcall(function()
			redis_client:hset(VALIDATED_KEY, fingerprint, os.time())
			redis_client:expire(VALIDATED_KEY, TTL_VALIDATED)
			redis_client:hdel(PROCESSING_KEY, fingerprint)
			redis_client:hdel(FAILED_KEY, fingerprint)
			log_info("Validated: " .. fingerprint:sub(1, 16) .. "... (Redis)")
		end)

		if ok then
			return true
		else
			log_warn("Redis mark_validated failed, trying file storage")
		end
	end

	-- Fall back to file storage
	if file_storage_available and file_mark_validated(fingerprint) then
		return true
	end

	-- Final fallback: in-memory
	fallback_validated[fingerprint] = os.time()
	log_info("Validated: " .. fingerprint:sub(1, 16) .. "... (Memory)")
	return true
end

-- Mark validation as failed
-- Removes from processing, stores error reason
-- Fallback order: Redis → File Storage → In-Memory
function _M.mark_failed(fingerprint, error)
	if not fingerprint or fingerprint == "" then
		return false
	end

	local error_msg = error or "unknown error"

	-- Try Redis first
	if redis_client then
		local ok = pcall(function()
			redis_client:hset(FAILED_KEY, fingerprint, error_msg)
			redis_client:expire(FAILED_KEY, TTL_FAILED)
			redis_client:hdel(PROCESSING_KEY, fingerprint)
			log_info("Failed: " .. fingerprint:sub(1, 16) .. "... (" .. error_msg .. ") (Redis)")
		end)

		if ok then
			return true
		else
			log_warn("Redis mark_failed failed, trying file storage")
		end
	end

	-- Fall back to file storage
	if file_storage_available and file_mark_failed(fingerprint, error_msg) then
		return true
	end

	-- Final fallback: in-memory
	log_info("Failed: " .. fingerprint:sub(1, 16) .. "... (" .. error_msg .. ") (Memory)")
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

-- ============================================================================
-- Persistence Functions (Disk Durability)
-- ============================================================================
-- These functions manage persistence of the in-memory queue to disk.
-- Use these to ensure in-memory queue survives process crashes.

-- Persist in-memory queue to file storage (backup)
-- Call this periodically or before shutdown to save queue state
function _M.persist_queue_to_disk()
	if not file_storage_available then
		return 0
	end

	if #fallback_queue == 0 then
		return 0
	end

	local saved = 0
	for _, fingerprint in ipairs(fallback_queue) do
		if file_queue_pending(fingerprint) then
			saved = saved + 1
		end
	end

	if saved > 0 then
		log_info("Persisted " .. saved .. " in-memory queue entries to disk")
	end

	return saved
end

-- Restore in-memory queue from file storage (recovery)
-- Called at module load time, or manually if needed
function _M.restore_queue_from_disk()
	if not file_storage_available then
		return 0
	end

	local restored = 0
	local pending = list_dir(QUEUE_PENDING_DIR)
	for _, fingerprint in ipairs(pending) do
		if not fallback_queue[fingerprint] then  -- Avoid duplicates
			table.insert(fallback_queue, fingerprint)
			restored = restored + 1
		end
	end

	if restored > 0 then
		log_info("Restored " .. restored .. " queue entries from disk")
	end

	return restored
end

-- Get file storage status
-- Returns: table with storage info (available, pending_count, validated_count)
function _M.get_storage_status()
	local status = {
		file_storage = file_storage_available,
		redis = redis_client ~= nil,
		fallback_queue_size = #fallback_queue,
		fallback_validated_size = 0
	}

	for _ in pairs(fallback_validated) do
		status.fallback_validated_size = status.fallback_validated_size + 1
	end

	if file_storage_available then
		status.file_pending = #list_dir(QUEUE_PENDING_DIR)
		status.file_validated = #list_dir(QUEUE_VALIDATED_DIR)
		status.file_failed = #list_dir(QUEUE_FAILED_DIR)
		status.file_processing = #list_dir(QUEUE_PROCESSING_DIR)
	end

	return status
end

return _M
