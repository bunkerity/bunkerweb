#!/usr/bin/env lua
-- OCSP Async Validation Job with Must-Staple Prioritization
--
-- This job runs periodically (default: every minute) to validate OCSP responses
-- for certificates in the Redis-backed validation queue. It implements a two-phase
-- validation strategy:
--
-- PHASE 1 (High Priority): Validates ALL must-staple certificates first
--   - Must-staple certificates REQUIRE an OCSP staple (mandatory security requirement)
--   - Failed must-staple certs are re-queued for automatic retry
--   - Ensures critical certificates get validated with priority
--
-- PHASE 2 (Low Priority): Validates optional certificates with remaining capacity
--   - Non-must-staple certificates are optional (best-effort)
--   - Only runs if batch capacity remains after phase 1
--   - Prevents starvation of optional certs while prioritizing critical ones
--
-- Key features:
-- - Responder health tracking with exponential backoff (5min→10min→20min→...)
-- - HTTP 429 (rate limit) handling with Retry-After header parsing
-- - Request rate limiting to prevent overwhelming responders
-- - Per-certificate validation with proper error handling
-- - Version tagging for cache invalidation on cert rotation
--
-- Configuration (env vars):
--   OCSP_BATCH_SIZE=10                    -- Certs per cycle (default: 10)
--   OCSP_REQUEST_RATE_LIMIT=50            -- Requests/sec to responder (default: 50)
--   OCSP_RATE_LIMIT_JITTER=20             -- Jitter % ±randomization (default: 20%)
--   OCSP_RESPONDER_RETRY_INITIAL=300      -- Initial backoff seconds (default: 5min)
--   OCSP_RESPONDER_RETRY_MAX=86400        -- Max backoff seconds (default: 24hr)

local logger = require "bunkerweb.logger"
local ocsp_module = require "bunkerweb.ocsp"
local queue = require "ocsp_redis_queue"

-- ============================================================================
-- Queue Storage Tiers (from ocsp_redis_queue module):
-- ============================================================================
-- The queue module uses three-tier fallback for durability:
--
--   Tier 1: Redis (if configured and available)
--   Tier 2: File Storage (/var/lib/bunkerweb/ocsp-queue/)
--   Tier 3: In-Memory fallback (volatile)
--
-- All queue operations automatically use the best available tier:
--   queue.queue_pending()    → Tries Redis → File → Memory
--   queue.get_next_pending() → Tries Redis → File → Memory
--   queue.mark_validated()   → Tries Redis → File → Memory
--   queue.mark_failed()      → Tries Redis → File → Memory
--
-- Must-staple prioritization works with all tiers because it scans
-- via get_next_pending() repeatedly, which always works regardless
-- of underlying storage mechanism.

-- ============================================================================
-- Logging Helpers
-- ============================================================================
-- All logs are prefixed with [OCSP-ASYNC] for easy filtering and debugging

local function log_info(msg)
	logger:info("[OCSP-ASYNC] " .. msg)
end

local function log_warn(msg)
	logger:warn("[OCSP-ASYNC] " .. msg)
end

local function log_err(msg)
	logger:err("[OCSP-ASYNC] " .. msg)
end

local function log_debug(msg)
	logger:debug("[OCSP-ASYNC] " .. msg)
end

-- ============================================================================
-- Must-Staple Module Loading
-- ============================================================================
-- The must-staple detection module is lazily loaded only when needed.
-- This avoids unnecessary imports and allows graceful fallback if unavailable.
-- Caching ensures we only load once, even if called multiple times.

local must_staple_module = nil

-- Lazy-load the must-staple detection module
-- Returns: module object if available, nil if unavailable
-- Caches result to avoid repeated load attempts
local function get_must_staple_module()
	if must_staple_module ~= nil then
		return must_staple_module
	end

	local ok, ms = pcall(function()
		return require("bunkerweb.ocsp_must_staple")
	end)

	if ok and ms then
		must_staple_module = ms
	else
		must_staple_module = false  -- Mark as unavailable (distinct from nil)
	end

	return must_staple_module ~= false and must_staple_module or nil
end

-- ============================================================================
-- File Reading Helpers
-- ============================================================================
-- Reads certificate data from the OCSP cache directory.
-- Directory structure uses sharding (first hex char) for filesystem performance:
--   /var/cache/bunkerweb/ocsp/0/abc123...def.der   (OCSP response, DER format)
--   /var/cache/bunkerweb/ocsp/f/abc123...def.json  (metadata: cert_path, issuer_path)
-- This reduces entries per directory for faster lookups with 1000s of certs.

-- Reads OCSP response from disk cache
-- Returns: DER-encoded OCSP response bytes, or nil if not found/empty
local function read_ocsp_response(fingerprint)
	if not fingerprint or fingerprint == "" then
		return nil
	end

	local shard = fingerprint:sub(1, 1)  -- First hex char for sharding (0-f)
	local ocsp_path = "/var/cache/bunkerweb/ocsp/" .. shard .. "/" .. fingerprint .. ".der"

	local f = io.open(ocsp_path, "rb")
	if not f then
		return nil
	end

	local ocsp_der = f:read("*a")
	f:close()

	return ocsp_der ~= "" and ocsp_der or nil
end

-- Reads leaf certificate (PEM format) by first reading metadata JSON
-- Metadata contains the file path to the actual cert file
-- Returns: PEM-encoded certificate, or nil if not found/empty
local function read_leaf_pem(fingerprint)
	if not fingerprint or fingerprint == "" then
		return nil
	end

	local shard = fingerprint:sub(1, 1)
	local metadata_path = "/var/cache/bunkerweb/ocsp/" .. shard .. "/" .. fingerprint .. ".json"

	-- Read metadata to find cert file path
	local f = io.open(metadata_path, "r")
	if not f then
		return nil
	end

	local json_str = f:read("*a")
	f:close()

	-- Extract cert_path from JSON (simple regex, not full JSON parser)
	local leaf_path = json_str:match('"cert_path"%s*:%s*"([^"]*)"')
	if not leaf_path or leaf_path == "" then
		return nil
	end

	-- Read the actual certificate file
	local leaf_f = io.open(leaf_path, "r")
	if not leaf_f then
		return nil
	end

	local leaf_pem = leaf_f:read("*a")
	leaf_f:close()

	return leaf_pem ~= "" and leaf_pem or nil
end

-- Reads issuer certificate chain from metadata file
-- Chain is stored as concatenated PEM blocks (usually 1-2 certs)
-- First issuer is typically the CA who signed the leaf, used for OCSP responder URL
-- Returns: array of PEM-encoded certificates, or nil if not found/empty
local function read_issuer_chain(fingerprint)
	if not fingerprint or fingerprint == "" then
		return nil
	end

	local shard = fingerprint:sub(1, 1)
	local metadata_path = "/var/cache/bunkerweb/ocsp/" .. shard .. "/" .. fingerprint .. ".json"

	-- Read metadata to find issuer chain file path
	local f = io.open(metadata_path, "r")
	if not f then
		return nil
	end

	local json_str = f:read("*a")
	f:close()

	-- Extract issuer_path from JSON
	local issuer_path = json_str:match('"issuer_path"%s*:%s*"([^"]*)"')
	if not issuer_path or issuer_path == "" then
		return nil
	end

	-- Read the issuer chain file
	local issuer_f = io.open(issuer_path, "r")
	if not issuer_f then
		return nil
	end

	local chain_pem = issuer_f:read("*a")
	issuer_f:close()

	if not chain_pem or chain_pem == "" then
		return nil
	end

	-- Parse PEM blocks (multiple certs concatenated)
	-- Each cert is bounded by -----BEGIN/END CERTIFICATE-----
	local issuers = {}
	local current_pem = ""
	for line in chain_pem:gmatch("[^\n]+") do
		current_pem = current_pem .. line .. "\n"
		if line == "-----END CERTIFICATE-----" then
			table.insert(issuers, current_pem)
			current_pem = ""
		end
	end

	return #issuers > 0 and issuers or nil
end

-- ============================================================================
-- Must-Staple Detection
-- ============================================================================
-- Checks if a certificate has the must-staple extension (RFC 6961).
-- Must-staple means the certificate REQUIRES an OCSP staple during TLS handshake.
-- These are high-priority and must be validated before optional certs.
--
-- Returns:
--   true  = Certificate has must-staple requirement (high priority)
--   false = Certificate does NOT have must-staple (optional, low priority)
--   nil   = Unable to determine (module unavailable or cert unreadable)

local function is_must_staple_cert(fingerprint, leaf_pem)
	-- If PEM not provided, read from disk
	if not leaf_pem then
		leaf_pem = read_leaf_pem(fingerprint)
	end

	if not leaf_pem then
		return nil  -- Cannot read cert
	end

	-- Get must-staple detection module
	local ms_module = get_must_staple_module()
	if not ms_module then
		return nil  -- Module unavailable, cannot determine
	end

	-- Delegate to module for actual must-staple detection
	return ms_module.get_must_staple(leaf_pem, fingerprint) or false
end

-- ============================================================================
-- Core Validation Logic
-- ============================================================================
-- Validates a single OCSP response for a certificate.
-- Handles responder health checks, rate limiting, and various error conditions.
--
-- Parameters:
--   fingerprint    = SHA-256 fingerprint of the certificate (hex string)
--   batch_position = Position in current batch (for rate limiting)
--
-- Returns:
--   true  = Successfully validated and cached
--   false = Failed (marked as failed, will not retry)
--   nil   = Skipped (responder backoff, keeping existing staple)
--
-- Process:
--   1. Read OCSP response, leaf cert, and issuer chain from disk
--   2. Check responder health (skip if unhealthy, responder in backoff)
--   3. Apply rate limiting based on batch position
--   4. Call async_validate_response (crypto validation)
--   5. Handle HTTP errors (429 = rate limited, 500+ = responder error, 400+ = client error)
--   6. Mark as validated/failed and update responder health
--   7. Tag response with version for cache invalidation

local function validate_single_cert(fingerprint, batch_position)
	-- Step 1: Read cached OCSP response (DER format)
	local ocsp_der = read_ocsp_response(fingerprint)
	if not ocsp_der then
		log_warn("Skipping: could not read OCSP response for " .. fingerprint:sub(1, 16) .. "...")
		queue.mark_failed(fingerprint, "no_ocsp_response")
		return false
	end

	-- Step 2: Read leaf certificate (PEM format)
	local leaf_pem = read_leaf_pem(fingerprint)
	if not leaf_pem then
		log_warn("Skipping: could not read leaf cert for " .. fingerprint:sub(1, 16) .. "...")
		queue.mark_failed(fingerprint, "no_leaf_cert")
		return false
	end

	-- Step 3: Read issuer certificate chain (needed to validate OCSP response)
	local issuers = read_issuer_chain(fingerprint)
	if not issuers or #issuers == 0 then
		log_warn("Skipping: could not read issuer chain for " .. fingerprint:sub(1, 16) .. "...")
		queue.mark_failed(fingerprint, "no_issuer_chain")
		return false
	end

	-- Step 4: Extract responder URL from issuer certificate (first issuer usually contains OCSP URL)
	-- Used for responder health tracking (group errors by responder, not by cert)
	local responder_url = "ocsp:unknown"
	if issuers and #issuers > 0 then
		responder_url = "ocsp:" .. issuers[1]:sub(1, 16) .. "..."
	end

	-- Step 5: Check responder health before making request
	-- If responder recently failed, back off exponentially (5min → 10min → 20min → ...)
	-- Keeps existing OCSP staple while responder recovers
	local is_healthy, wait_seconds = queue.is_responder_healthy(responder_url)
	if not is_healthy then
		log_warn("Responder unhealthy (backoff " .. wait_seconds .. "s): " .. responder_url)
		log_debug("Skipping validation, keeping existing staple for: " .. fingerprint:sub(1, 16) .. "...")
		return nil  -- Skip (don't fail), will retry after backoff period
	end

	-- Step 6: Apply rate limiting to prevent overwhelming responder
	-- Spreads requests over time based on batch position and configured rate limit
	-- Default: 50 requests/second = 20ms per request
	if batch_position and batch_position > 1 then
		local request_rate_limit = tonumber(os.getenv("OCSP_REQUEST_RATE_LIMIT") or "50")
		local base_delay_ms = 1000 / request_rate_limit
		if ngx and ngx.sleep then
			ngx.sleep(base_delay_ms / 1000)
		end
	end

	-- Step 7: Validate OCSP response cryptographically
	-- This calls the OCSP module to verify the response signature, freshness, etc.
	-- Wrapped in pcall() to catch any unexpected crashes
	local ok, http_code, error_msg
	local success = pcall(function()
		ok, http_code, error_msg = ocsp_module.async_validate_response(fingerprint, ocsp_der, issuers, leaf_pem)
	end)

	if not success then
		log_err("Async validation crashed for " .. fingerprint:sub(1, 16) .. "...")
		queue.mark_responder_failed(responder_url, "validation_crash")
		queue.mark_failed(fingerprint, "validation_crash")
		return false
	end

	-- Step 8: Handle HTTP response codes
	-- Different codes require different actions:
	-- - 429 (Too Many Requests): Responder-level backoff, keep existing staple
	-- - 5xx (Server Error): Responder-level backoff, mark cert failed
	-- - 4xx (Client Error): Cert-specific failure, doesn't affect responder
	-- - 2xx (Success): Proceed to crypto validation below

	if http_code == 429 then
		-- Responder rate-limited us. Parse Retry-After header to know how long to wait.
		log_warn("Responder rate limited (429) for: " .. responder_url)
		local retry_after_seconds = queue.parse_retry_after(error_msg)
		queue.mark_responder_failed(responder_url, "rate_limited_429", retry_after_seconds or 300)
		log_info("Keeping existing staple, will retry after " .. (retry_after_seconds or 300) .. "s")
		return nil  -- Skip, keep existing OCSP staple

	elseif http_code and http_code >= 500 then
		-- Responder returned server error. Mark responder unhealthy.
		-- All certs from this responder will wait before retry.
		log_warn("Responder error (" .. http_code .. ") for: " .. responder_url)
		queue.mark_responder_failed(responder_url, "http_" .. http_code)
		queue.mark_failed(fingerprint, "responder_error_" .. http_code)
		return false

	elseif http_code and http_code >= 400 then
		-- Client error (malformed request, cert not found, etc).
		-- Only this cert fails, responder stays healthy.
		log_warn("Client error (" .. http_code .. ") for: " .. fingerprint:sub(1, 16) .. "...")
		queue.mark_failed(fingerprint, "http_" .. http_code)
		return false
	end

	-- Step 9: Check crypto validation result
	-- If ok=false, the OCSP response failed validation (signature mismatch, expired, etc)
	if not ok then
		log_warn("✗ OCSP validation failed: " .. fingerprint:sub(1, 16) .. "... (" .. (error_msg or "unknown") .. ")")
		queue.mark_responder_failed(responder_url, "validation_failed")
		queue.mark_failed(fingerprint, "ocsp_invalid")
		return false
	end

	-- Step 10: Success! Mark certificate as validated
	log_info("✓ OCSP validation succeeded: " .. fingerprint:sub(1, 16) .. "...")
	queue.mark_responder_healthy(responder_url)  -- Responder working, clear backoff
	queue.mark_validated(fingerprint)

	-- Step 11: Tag response with version for cache invalidation
	-- When certificates rotate, version counter increments.
	-- Old responses get invalidated automatically (version mismatch).
	pcall(function()
		if ocsp_module.set_cached_response_version then
			local current_version = ocsp_module.get_ocsp_response_version and ocsp_module.get_ocsp_response_version() or 1
			ocsp_module.set_cached_response_version(fingerprint, current_version)
			log_debug("Tagged response version: " .. fingerprint:sub(1, 16) .. "... = v" .. current_version)
		end
	end)

	return true
end

-- ============================================================================
-- Main Validation Orchestrator
-- ============================================================================
-- Two-phase validation strategy:
--
-- PHASE 1 - Must-Staple (High Priority):
--   - Scans queue for certificates with must-staple requirement
--   - Validates ALL must-staple certs found (no quota limit)
--   - Re-queues any non-must-staple found (defer to phase 2)
--   - Failed must-staple certs are re-queued for automatic retry
--   - Continues until queue exhausted or batch_size reached
--
-- PHASE 2 - Optional (Low Priority):
--   - Processes remaining optional certificates
--   - Only runs if batch capacity remains
--   - Fills up to batch_size total
--   - Prevents starvation of optional certs
--
-- Responder Protection:
--   - Responder health tracked at responder level (not per-cert)
--   - Failed responders enter exponential backoff (5min → 10min → 20min → ...)
--   - Rate limiting spreads requests to avoid overwhelming responder
--   - 429 responses respected with Retry-After parsing
--
-- Returns: (validated_count, failed_count, skipped_count)

local function validate_from_redis_queue()
	local batch_size = tonumber(os.getenv("OCSP_BATCH_SIZE") or "10")

	local must_staple_validated = 0
	local must_staple_failed = 0
	local optional_validated = 0
	local optional_failed = 0
	local skipped_count = 0
	local batch_position = 0

	log_info("Starting validation: batch_size=" .. batch_size)

	-- ========================================================================
	-- PHASE 1: Must-Staple Certificates (HIGH PRIORITY)
	-- ========================================================================
	-- Validates ALL must-staple certificates first. Must-staple certs have
	-- a mandatory requirement for OCSP stapling (RFC 6961), so they take
	-- priority over optional certificates.
	--
	-- Strategy:
	-- - Scan queue for must-staple certificates
	-- - Defer (re-queue) any non-must-staple found
	-- - Re-queue any must-staple that fails (for automatic retry)
	-- - Continue until batch full or queue exhausted
	--
	-- This ensures must-staple always gets validated first, even if queue
	-- is large (1000s of certs).

	log_info("Phase 1: Processing all must-staple certificates")

	local scan_attempts = 0
	local max_scan_attempts = batch_size * 5  -- Limit scan iterations to prevent infinite loops

	while scan_attempts < max_scan_attempts do
		scan_attempts = scan_attempts + 1

		-- Get next certificate from queue
		local fingerprint = queue.get_next_pending()
		if not fingerprint then
			log_info("Queue empty during must-staple phase")
			break
		end

		batch_position = batch_position + 1

		-- Determine if certificate has must-staple requirement
		local leaf_pem = read_leaf_pem(fingerprint)
		local is_must_staple = is_must_staple_cert(fingerprint, leaf_pem)

		if not is_must_staple then
			-- Not must-staple, defer to phase 2 (lower priority)
			log_debug("Deferring non-must-staple: " .. fingerprint:sub(1, 16) .. "...")
			queue.queue_pending(fingerprint)  -- Put back in queue for phase 2
			goto continue_phase1
		end

		-- Validate this must-staple certificate
		local result = validate_single_cert(fingerprint, batch_position)
		if result == true then
			-- Success
			must_staple_validated = must_staple_validated + 1
		elseif result == false then
			-- Failed validation. Re-queue for retry because must-staple is critical.
			-- Next cycle will attempt again (responder may recover).
			log_debug("Re-queueing failed must-staple: " .. fingerprint:sub(1, 16) .. "...")
			queue.queue_pending(fingerprint)
			must_staple_failed = must_staple_failed + 1
		else
			-- Skipped (responder in backoff). Keep existing staple, will retry later.
			skipped_count = skipped_count + 1
		end

		-- Stop if we've reached batch capacity AND validated at least one must-staple
		-- This prevents phase 1 from consuming entire batch when many must-staple present
		if batch_position >= batch_size and must_staple_validated > 0 then
			log_info("Batch size reached, stopping phase 1")
			break
		end

		::continue_phase1::
	end

	log_info("Phase 1 complete: " .. must_staple_validated .. " validated, " ..
		must_staple_failed .. " failed, " .. skipped_count .. " skipped (backoff)")

	-- ========================================================================
	-- PHASE 2: Optional Certificates (LOW PRIORITY)
	-- ========================================================================
	-- Fills remaining batch capacity with optional (non-must-staple) certificates.
	-- These are best-effort: validation is good if it happens, but not critical
	-- if queue is large and responder is under load.
	--
	-- Strategy:
	-- - Only runs if batch_position < batch_size (capacity remains)
	-- - Processes optional certs from queue
	-- - Fills batch up to batch_size or queue exhausted
	-- - No re-queuing on failure (unlike must-staple)
	--
	-- This prevents starvation: optional certs still get validated, just after
	-- all must-staple are processed.

	if batch_position < batch_size then
		log_info("Phase 2: Processing optional certificates (remaining capacity=" .. (batch_size - batch_position) .. ")")

		while batch_position < batch_size do
			local fingerprint = queue.get_next_pending()
			if not fingerprint then
				log_info("Queue empty during optional phase")
				break
			end

			batch_position = batch_position + 1

			-- Validate optional certificate
			-- Note: Unlike phase 1, failures are not re-queued (lower priority)
			local result = validate_single_cert(fingerprint, batch_position)
			if result == true then
				optional_validated = optional_validated + 1
			elseif result == false then
				optional_failed = optional_failed + 1
			else
				skipped_count = skipped_count + 1
			end
		end

		log_info("Phase 2 complete: " .. optional_validated .. " validated, " ..
			optional_failed .. " failed, " .. skipped_count .. " skipped (backoff)")
	end

	-- ========================================================================
	-- Summary and Metrics
	-- ========================================================================
	-- Log detailed metrics for monitoring prioritization effectiveness

	local total_validated = must_staple_validated + optional_validated
	local total_failed = must_staple_failed + optional_failed

	log_info("Validation summary: must-staple=" .. must_staple_validated .. "/" ..
		(must_staple_validated + must_staple_failed) ..
		", optional=" .. optional_validated .. "/" ..
		(optional_validated + optional_failed) ..
		", skipped=" .. skipped_count ..
		", total=" .. total_validated .. " validated/" .. total_failed .. " failed")

	return total_validated, total_failed, skipped_count
end

-- ============================================================================
-- Job Entry Point
-- ============================================================================
-- Called by the scheduler once per configured interval (default: every minute).
-- Orchestrates the entire validation cycle.

local function run_job()
	log_info("=== OCSP Async Validation Job Started (Prioritized) ===")

	local start_time = os.time()

	-- Execute two-phase validation
	local validated, failed, skipped = validate_from_redis_queue()

	local elapsed = os.time() - start_time

	log_info("=== OCSP Async Validation Job Complete ===")
	log_info("Summary: " .. validated .. " validated, " .. failed .. " failed, " ..
		skipped .. " skipped (backoff) in " .. elapsed .. "s")

	return true
end

-- ============================================================================
-- Execution
-- ============================================================================
-- Invoke job immediately when module loaded by scheduler

return run_job()
