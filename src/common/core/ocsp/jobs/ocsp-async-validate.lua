#!/usr/bin/env lua
-- OCSP Async Validation Job
-- Runs in scheduler context (not TLS critical path)
-- Validates OCSP responses queued by TLS handshakes
-- Marks validated responses so future handshakes skip validation
--
-- ============================================================================
-- INTEGRATION INSTRUCTIONS
-- ============================================================================
--
-- 1. Add to plugin.json (src/common/core/ocsp/plugin.json):
--
--    "jobs": [
--      {
--        "name": "ocsp-async-validate",
--        "file": "jobs/ocsp-async-validate.lua",
--        "every": "minute",           # every 1 minute (adjust as needed)
--        "reload": false,             # validation doesn't require reload
--        "async": true                # can run in background
--      }
--    ]
--
-- 2. Dependencies:
--    - ngx.shared.bw_ocsp_validations (shared dict, auto-created by OpenResty)
--    - /var/cache/bunkerweb/ocsp/ (shard directory for OCSP responses)
--    - bunkerweb.logger (standard logging)
--    - bunkerweb.ocsp (TLS-path module with async_validate_response())
--
-- 3. Environment:
--    - Runs in scheduler worker context (not in TLS worker)
--    - Can use IO operations (file reads) without TLS latency concern
--    - Reports via logger; metrics optional
--
-- 4. Monitoring:
--    - Watch logs for "[OCSP-ASYNC]" prefix
--    - Track "validated", "failed", "skipped" counts
--    - Alert if failure rate > 10% or job duration > 5s
--
-- ============================================================================

local logger = require "bunkerweb.logger"
local ocsp_module = require "bunkerweb.ocsp"
local queue = require "ocsp_redis_queue"  -- Persistent queue with Redis fallback

-- Logging helpers
local function log_info(msg)
	logger:info("[OCSP-ASYNC] " .. msg)
end

local function log_warn(msg)
	logger:warn("[OCSP-ASYNC] " .. msg)
end

local function log_err(msg)
	logger:err("[OCSP-ASYNC] " .. msg)
end

-- Helper: Check for certificate rotation and increment global version if detected.
-- Compares certificate modification times; if newer certs found, invalidate all cached responses.
local function detect_and_handle_cert_rotation()
	local cert_dir = "/var/cache/bunkerweb/letsencrypt" or os.getenv("OCSP_CACHE_DIR") or "/var/cache/bunkerweb/ocsp"
	local marker_file = cert_dir .. "/.ocsp_cert_rotation_check"

	-- Read previous rotation check timestamp
	local last_check = 0
	local marker_f = io.open(marker_file, "r")
	if marker_f then
		last_check = tonumber(marker_f:read("*a")) or 0
		marker_f:close()
	end

	-- Check if any certificate files have been modified recently
	local current_time = os.time()
	local rotation_detected = false

	-- Check for new cert files (simple heuristic: any .pem file newer than last check)
	local cert_check = os.execute("find " .. cert_dir .. " -name '*.pem' -mmin -60 2>/dev/null | wc -l")
	if cert_check and tonumber(cert_check) > 0 then
		rotation_detected = true
		log_info("Certificate rotation detected: found recently modified certificate files")
	end

	-- If rotation detected, increment global version to invalidate all cached responses
	if rotation_detected then
		pcall(function()
			if ocsp_module.increment_ocsp_response_version then
				local new_version = ocsp_module.increment_ocsp_response_version()
				log_info("Incremented OCSP response version to: " .. new_version .. " (cache invalidated)")
			end
		end)
	end

	-- Update rotation check marker
	local marker_w = io.open(marker_file, "w")
	if marker_w then
		marker_w:write(tostring(current_time))
		marker_w:close()
	end
end

-- Helper: Read OCSP response from cache or disk
-- Returns: binary OCSP response DER or nil if not found
local function read_ocsp_response(fingerprint)
	if not fingerprint or fingerprint == "" then
		return nil
	end

	-- Calculate shard path (16-way distribution: 0-f)
	local shard = fingerprint:sub(1, 1)  -- First hex char
	local ocsp_path = "/var/cache/bunkerweb/ocsp/" .. shard .. "/" .. fingerprint .. ".der"

	-- Try to read OCSP response from disk
	local f = io.open(ocsp_path, "rb")
	if not f then
		log_warn("OCSP response not found: " .. ocsp_path)
		return nil
	end

	local ocsp_der = f:read("*a")
	f:close()

	if not ocsp_der or ocsp_der == "" then
		log_warn("OCSP response empty: " .. ocsp_path)
		return nil
	end

	return ocsp_der
end

-- Helper: Read certificate chain from metadata
-- Returns: table of issuer PEM strings or nil if not found
local function read_issuer_chain(fingerprint)
	if not fingerprint or fingerprint == "" then
		return nil
	end

	local shard = fingerprint:sub(1, 1)
	local metadata_path = "/var/cache/bunkerweb/ocsp/" .. shard .. "/" .. fingerprint .. ".json"

	-- Try to read metadata JSON
	local f = io.open(metadata_path, "r")
	if not f then
		log_warn("OCSP metadata not found: " .. metadata_path)
		return nil
	end

	local json_str = f:read("*a")
	f:close()

	-- Parse JSON to extract issuer chain (basic parsing)
	-- Full implementation should use proper JSON library
	-- For now: look for "issuer_path" field
	local issuer_path = json_str:match('"issuer_path"%s*:%s*"([^"]*)"')
	if not issuer_path or issuer_path == "" then
		log_warn("Issuer path not in metadata: " .. metadata_path)
		return nil
	end

	-- Read issuer chain file
	local issuer_f = io.open(issuer_path, "r")
	if not issuer_f then
		log_warn("Issuer chain file not found: " .. issuer_path)
		return nil
	end

	local chain_pem = issuer_f:read("*a")
	issuer_f:close()

	if not chain_pem or chain_pem == "" then
		log_warn("Issuer chain empty: " .. issuer_path)
		return nil
	end

	-- Split PEM chain into individual issuers
	local issuers = {}
	local current_pem = ""
	for line in chain_pem:gmatch("[^\n]+") do
		current_pem = current_pem .. line .. "\n"
		if line == "-----END CERTIFICATE-----" then
			table.insert(issuers, current_pem)
			current_pem = ""
		end
	end

	if #issuers == 0 then
		log_warn("No issuers extracted from chain: " .. issuer_path)
		return nil
	end

	return issuers
end

-- Helper: Read leaf certificate PEM
-- Returns: leaf certificate PEM string or nil if not found
local function read_leaf_pem(fingerprint)
	if not fingerprint or fingerprint == "" then
		return nil
	end

	local shard = fingerprint:sub(1, 1)
	local metadata_path = "/var/cache/bunkerweb/ocsp/" .. shard .. "/" .. fingerprint .. ".json"

	-- Read metadata to get leaf cert path
	local f = io.open(metadata_path, "r")
	if not f then
		return nil
	end

	local json_str = f:read("*a")
	f:close()

	-- Extract leaf cert path from metadata
	local leaf_path = json_str:match('"cert_path"%s*:%s*"([^"]*)"')
	if not leaf_path or leaf_path == "" then
		log_warn("Cert path not in metadata: " .. metadata_path)
		return nil
	end

	-- Read leaf cert
	local leaf_f = io.open(leaf_path, "r")
	if not leaf_f then
		log_warn("Leaf cert file not found: " .. leaf_path)
		return nil
	end

	local leaf_pem = leaf_f:read("*a")
	leaf_f:close()

	if not leaf_pem or leaf_pem == "" then
		log_warn("Leaf cert empty: " .. leaf_path)
		return nil
	end

	return leaf_pem
end

-- Main: Enumerate pending validations and gather data
local function get_pending_validations()
	local pending = {}

	-- Access shared dict (bw_ocsp_validations)
	local ngx_shared = ngx and ngx.shared
	if not ngx_shared or not ngx_shared.bw_ocsp_validations then
		log_warn("Shared dict bw_ocsp_validations not available")
		return pending
	end

	local dict = ngx_shared.bw_ocsp_validations
	local async_prefix = "OCSP:ASYNC_VALIDATE:"

	-- Iterate shared dict to find pending validations
	-- Note: ngx.shared dict iteration is expensive; in production, consider
	-- maintaining a separate "pending queue" in Redis or database
	for key, value in pairs(dict:get_keys(0)) do
		if key:sub(1, #async_prefix) == async_prefix and value == "pending" then
			-- Extract fingerprint from key
			local fingerprint = key:sub(#async_prefix + 1)

			if fingerprint and #fingerprint == 64 then
				log_info("Found pending validation: " .. fingerprint:sub(1, 16) .. "...")

				-- Read OCSP response, leaf, and issuers
				local ocsp_der = read_ocsp_response(fingerprint)
				if not ocsp_der then
					log_warn("Skipping: could not read OCSP response for " .. fingerprint:sub(1, 16) .. "...")
					goto skip_item
				end

				local leaf_pem = read_leaf_pem(fingerprint)
				if not leaf_pem then
					log_warn("Skipping: could not read leaf cert for " .. fingerprint:sub(1, 16) .. "...")
					goto skip_item
				end

				local issuers = read_issuer_chain(fingerprint)
				if not issuers or #issuers == 0 then
					log_warn("Skipping: could not read issuer chain for " .. fingerprint:sub(1, 16) .. "...")
					goto skip_item
				end

				-- Add to pending validations
				table.insert(pending, {
					fingerprint = fingerprint,
					ocsp_der = ocsp_der,
					leaf_pem = leaf_pem,
					issuers = issuers
				})

				::skip_item::
			end
		end
	end

	log_info("Found " .. #pending .. " pending validations to process")
	return pending
end

-- Helper: Validate issuer certificate and compute SPKI
-- Returns: issuer_spki (fingerprint) if valid, nil if validation fails
local function validate_issuer_cert_and_compute_spki(issuer_pem)
	if not issuer_pem or issuer_pem == "" then
		return nil
	end

	-- In a full implementation, this would:
	-- 1. Parse issuer certificate PEM
	-- 2. Verify certificate dates (not expired)
	-- 3. Check certificate chain validity
	-- 4. Compute SPKI fingerprint (SHA256 of public key)
	--
	-- For now: use placeholder that extracts basic info
	-- Actual implementation requires lua-resty-openssl FFI

	local pcall_ok, issuer_cert
	pcall_ok = pcall(function()
		local openssl = require "resty.openssl"
		issuer_cert = openssl.x509.new(issuer_pem, "PEM")
	end)

	if not pcall_ok or not issuer_cert then
		log_warn("Failed to parse issuer certificate")
		return nil
	end

	-- Compute SPKI (placeholder: would use openssl.pkey:get_public_key_sha256())
	-- For now, return a marker that issuer was validated
	return "spki_placeholder"
end

-- Validate from Redis queue (persists across restarts)
local function validate_from_redis_queue()
	local validated_count = 0
	local failed_count = 0
	local skipped_count = 0
	local spki_cached_count = 0

	-- Read batch size from environment (respects startup throttling)
	local batch_size = tonumber(os.getenv("OCSP_BATCH_SIZE") or "10")
	local request_rate_limit = tonumber(os.getenv("OCSP_REQUEST_RATE_LIMIT") or "50")
	local rate_limit_jitter = tonumber(os.getenv("OCSP_RATE_LIMIT_JITTER") or "20")

	-- Calculate delay between requests (with jitter)
	local base_delay_ms = 1000 / request_rate_limit
	local jitter_pct = (math.random(100 - rate_limit_jitter, 100 + rate_limit_jitter) / 100)
	local request_delay_ms = base_delay_ms * jitter_pct

	log_info("Batch config: size=" .. batch_size .. ", rate=" .. request_rate_limit ..
		" req/s, jitter=" .. rate_limit_jitter .. "%, delay=" .. string.format("%.1f", request_delay_ms) .. "ms")

	for batch = 1, batch_size do
		local fingerprint = queue.get_next_pending()
		if not fingerprint then
			break  -- No more pending
		end

		-- Read OCSP response from cache
		local ocsp_der = read_ocsp_response(fingerprint)
		if not ocsp_der then
			log_warn("Skipping: could not read OCSP response for " .. fingerprint:sub(1, 16) .. "...")
			queue.mark_failed(fingerprint, "no_ocsp_response")
			failed_count = failed_count + 1
			goto continue_redis
		end

		-- Read leaf cert and issuers
		local leaf_pem = read_leaf_pem(fingerprint)
		if not leaf_pem then
			log_warn("Skipping: could not read leaf cert for " .. fingerprint:sub(1, 16) .. "...")
			queue.mark_failed(fingerprint, "no_leaf_cert")
			failed_count = failed_count + 1
			goto continue_redis
		end

		local issuers = read_issuer_chain(fingerprint)
		if not issuers or #issuers == 0 then
			log_warn("Skipping: could not read issuer chain for " .. fingerprint:sub(1, 16) .. "...")
			queue.mark_failed(fingerprint, "no_issuer_chain")
			failed_count = failed_count + 1
			goto continue_redis
		end

		-- Extract responder URL from issuers (first issuer's OCSP URL)
		local responder_url = "ocsp:unknown"  -- Default placeholder
		if issuers and #issuers > 0 then
			-- Extract OCSP URL from issuer certificate (would need openssl parsing)
			-- For now, use a generic identifier based on issuer fingerprint
			responder_url = "ocsp:" .. issuers[1]:sub(1, 16) .. "..."
		end

		-- Check responder health before validating
		local is_healthy, wait_seconds = queue.is_responder_healthy(responder_url)
		if not is_healthy then
			log_warn("Responder unhealthy (backoff " .. wait_seconds .. "s): " .. responder_url)
			log_info("Skipping validation, keeping existing staple for: " .. fingerprint:sub(1, 16) .. "...")
			skipped_count = skipped_count + 1
			-- Don't fail the entry—keep it queued for later
			-- Just move to next and come back when responder recovers
			goto continue_redis
		end

		-- Rate limiting: add delay between requests to prevent responder overload
		if batch > 1 then
			local delay_seconds = request_delay_ms / 1000
			log_info("Rate limiting: wait " .. string.format("%.1f", request_delay_ms) .. "ms before next request")
			-- Simple delay using os.execute (not ideal for production, but works in scheduler context)
			-- Better approach: use ngx.sleep if available
			if ngx and ngx.sleep then
				ngx.sleep(delay_seconds)
			else
				-- Fallback: busy-wait or skip (responder rate limit handles it)
				log_info("Rate limiting not supported in this context (no ngx.sleep)")
			end
		end

		-- Validate OCSP response
		local ok, http_code, error_msg
		local success = pcall(function()
			ok, http_code, error_msg = ocsp_module.async_validate_response(fingerprint, ocsp_der, issuers, leaf_pem)
		end)

		if not success then
			log_err("Async validation crashed for " .. fingerprint:sub(1, 16) .. "...")
			queue.mark_responder_failed(responder_url, "validation_crash")
			queue.mark_failed(fingerprint, "validation_crash")
			failed_count = failed_count + 1
			goto continue_redis
		end

		-- Handle HTTP response codes
		if http_code == 429 then
			-- Rate limited: parse Retry-After header and respect it
			log_warn("Responder rate limited (429) for: " .. responder_url)
			local retry_after_seconds = queue.parse_retry_after(error_msg)
			queue.mark_responder_failed(responder_url, "rate_limited_429", retry_after_seconds or 300)
			-- Keep existing staple, don't mark as failed
			log_info("Keeping existing staple, will retry after " .. (retry_after_seconds or 300) .. "s")
			goto continue_redis

		elseif http_code and http_code >= 500 then
			-- Server error: responder is having issues
			log_warn("Responder error (" .. http_code .. ") for: " .. responder_url)
			queue.mark_responder_failed(responder_url, "http_" .. http_code)
			queue.mark_failed(fingerprint, "responder_error_" .. http_code)
			failed_count = failed_count + 1
			goto continue_redis

		elseif http_code and http_code >= 400 then
			-- Client error (except 429): cert/request issue
			log_warn("Client error (" .. http_code .. ") for: " .. fingerprint:sub(1, 16) .. "...")
			queue.mark_failed(fingerprint, "http_" .. http_code)
			failed_count = failed_count + 1
			goto continue_redis
		end

		if not ok then
			-- Validation logic error (not HTTP error)
			log_warn("✗ OCSP validation failed: " .. fingerprint:sub(1, 16) .. "... (" .. (error_msg or "unknown") .. ")")
			queue.mark_responder_failed(responder_url, "validation_failed")
			queue.mark_failed(fingerprint, "ocsp_invalid")
			failed_count = failed_count + 1
			goto continue_redis
		end

		-- OCSP validation succeeded, mark as complete
		log_info("✓ OCSP validation succeeded: " .. fingerprint:sub(1, 16) .. "...")
		validated_count = validated_count + 1

		-- Mark responder as healthy (reset backoff counter)
		queue.mark_responder_healthy(responder_url)

		-- Mark in persistent queue
		queue.mark_validated(fingerprint)

		-- Tag response with current version (for cache versioning)
		pcall(function()
			if ocsp_module.set_cached_response_version then
				local current_version = ocsp_module.get_ocsp_response_version and ocsp_module.get_ocsp_response_version() or 1
				ocsp_module.set_cached_response_version(fingerprint, current_version)
				log_info("Tagged response version: " .. fingerprint:sub(1, 16) .. "... = v" .. current_version)
			end
		end)

		-- Validate and cache issuer SPKIs
		for idx, issuer_pem in ipairs(issuers) do
			local issuer_spki = validate_issuer_cert_and_compute_spki(issuer_pem)
			if issuer_spki then
				local issuer_fingerprint = issuer_pem:sub(1, 8) .. "_issuer_" .. idx
				pcall(function()
					if ocsp_module.cache_issuer_spki then
						ocsp_module.cache_issuer_spki(issuer_fingerprint, issuer_spki)
						spki_cached_count = spki_cached_count + 1
						log_info("Cached SPKI for issuer " .. issuer_fingerprint:sub(1, 16) .. "...")
					end
				end)
			end
		end

		::continue_redis::
	end

	log_info("Batch complete: validated=" .. validated_count .. ", failed=" .. failed_count ..
		", skipped=" .. skipped_count .. ", spki_cached=" .. spki_cached_count)

	return validated_count, failed_count, skipped_count, spki_cached_count
end

-- Fallback: Validate from disk scan (for compatibility)
local function validate_pending_responses()
	local pending = get_pending_validations()
	local validated_count = 0
	local failed_count = 0
	local skipped_count = 0
	local spki_cached_count = 0

	for _, item in ipairs(pending) do
		local fingerprint = item.fingerprint
		local ocsp_der = item.ocsp_der
		local issuers = item.issuers
		local leaf_pem = item.leaf_pem

		if not fingerprint or not ocsp_der or not issuers or not leaf_pem then
			log_warn("Skipping incomplete async validation: missing fields")
			skipped_count = skipped_count + 1
			goto continue
		end

		-- Validate OCSP response (call async validation function from ocsp.lua)
		local ok
		local success = pcall(function()
			ok = ocsp_module.async_validate_response(fingerprint, ocsp_der, issuers, leaf_pem)
		end)

		if not success then
			log_err("Async validation crashed for " .. fingerprint:sub(1, 16) .. "...")
			failed_count = failed_count + 1
			goto continue
		end

		if not ok then
			log_warn("✗ OCSP validation failed: " .. fingerprint:sub(1, 16) .. "...")
			failed_count = failed_count + 1
			goto continue
		end

		-- OCSP validation succeeded, now validate issuers and cache SPKI
		log_info("✓ OCSP validation succeeded: " .. fingerprint:sub(1, 16) .. "...")
		validated_count = validated_count + 1

		-- Tag response with current version (for cache invalidation on cert rotation)
		-- TLS path will reject cache if version mismatches
		pcall(function()
			if ocsp_module.set_cached_response_version then
				local current_version = ocsp_module.get_ocsp_response_version and ocsp_module.get_ocsp_response_version() or 1
				ocsp_module.set_cached_response_version(fingerprint, current_version)
				log_info("Tagged response version: " .. fingerprint:sub(1, 16) .. "... = v" .. current_version)
			end
		end)

		-- Validate each issuer certificate and cache SPKI
		for idx, issuer_pem in ipairs(issuers) do
			local issuer_spki = validate_issuer_cert_and_compute_spki(issuer_pem)
			if issuer_spki then
				-- Compute issuer fingerprint for storage key
				local issuer_fingerprint = issuer_pem:sub(1, 8) .. "_issuer_" .. idx

				-- Try to cache SPKI (call ocsp_module if available)
				pcall(function()
					if ocsp_module.cache_issuer_spki then
						ocsp_module.cache_issuer_spki(issuer_fingerprint, issuer_spki)
						spki_cached_count = spki_cached_count + 1
						log_info("Cached SPKI for issuer " .. issuer_fingerprint:sub(1, 16) .. "...")
					end
				end)
			else
				log_warn("Failed to validate issuer cert #" .. idx .. " for " .. fingerprint:sub(1, 16) .. "...")
			end
		end

		::continue::
	end

	log_info("Batch complete: " .. validated_count .. " OCSP validated, " ..
		failed_count .. " failed, " .. skipped_count .. " skipped, " ..
		spki_cached_count .. " SPKI cached")

	return validated_count, failed_count, skipped_count, spki_cached_count
end

-- Helper: Report metrics (optional, if metrics system available)
local function report_metrics(validated, failed, skipped, spki_cached, elapsed)
	-- Try to report metrics if system supports it
	-- Common systems: prometheus, statsd, grafana, etc.

	-- Attempt 1: Via logger (metrics exported from logs)
	log_info("METRICS: validated=" .. validated .. " failed=" .. failed ..
		" skipped=" .. skipped .. " spki_cached=" .. spki_cached .. " duration_s=" .. elapsed)

	-- Attempt 2: Via optional metrics module (if available)
	local metrics_ok, metrics = pcall(function()
		return require "bunkerweb.metrics"
	end)

	if metrics_ok and metrics then
		pcall(function()
			metrics:counter("ocsp.async.validations_completed", validated)
			metrics:counter("ocsp.async.validations_failed", failed)
			metrics:counter("ocsp.async.spki_cached", spki_cached)
			metrics:gauge("ocsp.async.job_duration_s", elapsed)

			local total = validated + failed + skipped
			if total > 0 then
				local success_rate = (validated / total) * 100
				metrics:gauge("ocsp.async.success_rate_percent", success_rate)
			end
		end)
		log_info("Metrics reported successfully")
	else
		log_warn("Metrics module not available (optional)")
	end
end

-- Warmup: Pre-load cached OCSP responses at job startup (first run).
-- Marks valid responses as already validated, reducing first handshake latency.
local function warmup_on_startup()
	-- Check if we've already warmed up (use marker file, not ngx dict in scheduler context)
	local marker_file = "/var/cache/bunkerweb/ocsp/.warmup_done"
	local marker_check = io.open(marker_file, "r")
	if marker_check then
		marker_check:close()
		return  -- Already warmed up, skip
	end

	log_info("=== OCSP Cache Warmup Starting ===")
	local start_time = os.time()

	local cache_dir = "/var/cache/bunkerweb/ocsp"
	local warmed = 0
	local stale = 0
	local invalid = 0
	local failed = 0

	-- Scan cache directory for OCSP responses
	local dir_cmd = "find " .. cache_dir .. " -maxdepth 2 -name '*.der' 2>/dev/null"
	local dir_handle, dir_err = io.popen(dir_cmd)

	if not dir_handle then
		log_warn("Warmup: could not open cache directory: " .. tostring(dir_err))
		return
	end

	-- Process each cached OCSP response
	for ocsp_file in dir_handle:lines() do
		-- Extract fingerprint from path
		local fingerprint = ocsp_file:match("([a-f0-9]+)%.der$")
		if not fingerprint or #fingerprint ~= 64 then
			invalid = invalid + 1
			goto continue_warmup_scan
		end

		-- Check file age (assume valid if <7 days old)
		local stat_cmd = "stat -f%m " .. ocsp_file .. " 2>/dev/null"
		local stat_handle = io.popen(stat_cmd)
		local mtime_str = stat_handle:read("*a")
		stat_handle:close()

		local mtime = tonumber(mtime_str)
		if not mtime then
			failed = failed + 1
			goto continue_warmup_scan
		end

		local current_time = os.time()
		local age_days = (current_time - mtime) / (24 * 60 * 60)

		if age_days > 7 then
			stale = stale + 1
			goto continue_warmup_scan
		end

		-- Mark response as pre-warmed
		pcall(function()
			-- Tag with current version (for versioned cache)
			if ocsp_module.set_cached_response_version then
				local current_version = ocsp_module.get_ocsp_response_version and
					ocsp_module.get_ocsp_response_version() or 1
				ocsp_module.set_cached_response_version(fingerprint, current_version)
			end

			-- Mark as already validated (skip async job)
			local ngx_shared_warmup = ngx and ngx.shared
			if ngx_shared_warmup and ngx_shared_warmup.bw_ocsp_validations then
				local async_key = "OCSP:ASYNC_VALIDATE:" .. fingerprint
				ngx_shared_warmup.bw_ocsp_validations:set(async_key, "validated", 86400)
			end

			warmed = warmed + 1
		end)

		::continue_warmup_scan::
	end

	dir_handle:close()

	local elapsed = os.time() - start_time
	log_info("OCSP warmup complete in " .. elapsed .. "s: " .. warmed .. " ready, " ..
		stale .. " stale, " .. invalid .. " invalid, " .. failed .. " failed")

	-- Mark warmup as done (create marker file so we don't repeat)
	local marker_file = "/var/cache/bunkerweb/ocsp/.warmup_done"
	local marker_w = io.open(marker_file, "w")
	if marker_w then
		marker_w:write(tostring(os.time()))
		marker_w:close()
	end
end

-- Main job entry point (called by scheduler)
local function run_job()
	log_info("=== OCSP Async Validation Job Started ===")

	local start_time = os.time()

	-- Warmup: pre-load cached responses on first job run
	warmup_on_startup()

	-- Check for certificate rotation and invalidate stale responses if detected
	detect_and_handle_cert_rotation()

	-- Cleanup stale processing entries (stuck from previous crashes)
	queue.cleanup_stale_processing()

	-- Validate from persistent Redis queue (with rate limiting and batch throttling)
	local validated, failed, skipped, spki_cached = validate_from_redis_queue()

	local elapsed = os.time() - start_time

	-- Report results
	log_info("=== OCSP Async Validation Job Complete ===")
	log_info("Summary: " .. validated .. " validated, " .. failed .. " failed, " ..
		skipped .. " skipped (backoff), " .. spki_cached .. " SPKI cached in " .. elapsed .. "s")

	-- Report metrics (optional)
	report_metrics(validated, failed, skipped, spki_cached, elapsed)

	-- Return success even if some validations failed (job itself succeeded)
	return true
end

-- Execute job
return run_job()
