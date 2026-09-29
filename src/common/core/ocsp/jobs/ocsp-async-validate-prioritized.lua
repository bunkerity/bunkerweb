#!/usr/bin/env lua
-- OCSP Async Validation Job with Must-Staple Prioritization
-- Validates must-staple certificates first (high priority)
-- Processes optional certificates second (low priority)
-- Ensures responder gets high-value requests first

local logger = require "bunkerweb.logger"
local ocsp_module = require "bunkerweb.ocsp"
local queue = require "ocsp_redis_queue"

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

local function log_debug(msg)
	logger:debug("[OCSP-ASYNC] " .. msg)
end

-- Load must-staple module for prioritization
local must_staple_module = nil
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
		must_staple_module = false  -- Mark as unavailable
	end
	return must_staple_module ~= false and must_staple_module or nil
end

-- Read files (from original implementation)
local function read_ocsp_response(fingerprint)
	if not fingerprint or fingerprint == "" then
		return nil
	end
	local shard = fingerprint:sub(1, 1)
	local ocsp_path = "/var/cache/bunkerweb/ocsp/" .. shard .. "/" .. fingerprint .. ".der"
	local f = io.open(ocsp_path, "rb")
	if not f then
		return nil
	end
	local ocsp_der = f:read("*a")
	f:close()
	return ocsp_der ~= "" and ocsp_der or nil
end

local function read_leaf_pem(fingerprint)
	if not fingerprint or fingerprint == "" then
		return nil
	end
	local shard = fingerprint:sub(1, 1)
	local metadata_path = "/var/cache/bunkerweb/ocsp/" .. shard .. "/" .. fingerprint .. ".json"
	local f = io.open(metadata_path, "r")
	if not f then
		return nil
	end
	local json_str = f:read("*a")
	f:close()
	local leaf_path = json_str:match('"cert_path"%s*:%s*"([^"]*)"')
	if not leaf_path or leaf_path == "" then
		return nil
	end
	local leaf_f = io.open(leaf_path, "r")
	if not leaf_f then
		return nil
	end
	local leaf_pem = leaf_f:read("*a")
	leaf_f:close()
	return leaf_pem ~= "" and leaf_pem or nil
end

local function read_issuer_chain(fingerprint)
	if not fingerprint or fingerprint == "" then
		return nil
	end
	local shard = fingerprint:sub(1, 1)
	local metadata_path = "/var/cache/bunkerweb/ocsp/" .. shard .. "/" .. fingerprint .. ".json"
	local f = io.open(metadata_path, "r")
	if not f then
		return nil
	end
	local json_str = f:read("*a")
	f:close()
	local issuer_path = json_str:match('"issuer_path"%s*:%s*"([^"]*)"')
	if not issuer_path or issuer_path == "" then
		return nil
	end
	local issuer_f = io.open(issuer_path, "r")
	if not issuer_f then
		return nil
	end
	local chain_pem = issuer_f:read("*a")
	issuer_f:close()
	if not chain_pem or chain_pem == "" then
		return nil
	end
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

-- Detect if certificate has must-staple requirement
local function is_must_staple_cert(fingerprint, leaf_pem)
	if not leaf_pem then
		leaf_pem = read_leaf_pem(fingerprint)
	end

	if not leaf_pem then
		return nil  -- Unknown
	end

	local ms_module = get_must_staple_module()
	if not ms_module then
		return nil  -- Module unavailable
	end

	return ms_module.get_must_staple(leaf_pem, fingerprint) or false
end

-- Validate a single certificate
-- Returns: true if validated, false if failed, nil if skipped
local function validate_single_cert(fingerprint, batch_position)
	-- Read OCSP response from cache
	local ocsp_der = read_ocsp_response(fingerprint)
	if not ocsp_der then
		log_warn("Skipping: could not read OCSP response for " .. fingerprint:sub(1, 16) .. "...")
		queue.mark_failed(fingerprint, "no_ocsp_response")
		return false
	end

	-- Read leaf cert and issuers
	local leaf_pem = read_leaf_pem(fingerprint)
	if not leaf_pem then
		log_warn("Skipping: could not read leaf cert for " .. fingerprint:sub(1, 16) .. "...")
		queue.mark_failed(fingerprint, "no_leaf_cert")
		return false
	end

	local issuers = read_issuer_chain(fingerprint)
	if not issuers or #issuers == 0 then
		log_warn("Skipping: could not read issuer chain for " .. fingerprint:sub(1, 16) .. "...")
		queue.mark_failed(fingerprint, "no_issuer_chain")
		return false
	end

	-- Extract responder URL
	local responder_url = "ocsp:unknown"
	if issuers and #issuers > 0 then
		responder_url = "ocsp:" .. issuers[1]:sub(1, 16) .. "..."
	end

	-- Check responder health
	local is_healthy, wait_seconds = queue.is_responder_healthy(responder_url)
	if not is_healthy then
		log_warn("Responder unhealthy (backoff " .. wait_seconds .. "s): " .. responder_url)
		log_debug("Skipping validation, keeping existing staple for: " .. fingerprint:sub(1, 16) .. "...")
		return nil  -- Skip, don't fail
	end

	-- Apply rate limiting
	if batch_position and batch_position > 1 then
		local request_rate_limit = tonumber(os.getenv("OCSP_REQUEST_RATE_LIMIT") or "50")
		local base_delay_ms = 1000 / request_rate_limit
		if ngx and ngx.sleep then
			ngx.sleep(base_delay_ms / 1000)
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
		return false
	end

	-- Handle HTTP response codes
	if http_code == 429 then
		log_warn("Responder rate limited (429) for: " .. responder_url)
		local retry_after_seconds = queue.parse_retry_after(error_msg)
		queue.mark_responder_failed(responder_url, "rate_limited_429", retry_after_seconds or 300)
		log_info("Keeping existing staple, will retry after " .. (retry_after_seconds or 300) .. "s")
		return nil  -- Skip, keep staple

	elseif http_code and http_code >= 500 then
		log_warn("Responder error (" .. http_code .. ") for: " .. responder_url)
		queue.mark_responder_failed(responder_url, "http_" .. http_code)
		queue.mark_failed(fingerprint, "responder_error_" .. http_code)
		return false

	elseif http_code and http_code >= 400 then
		log_warn("Client error (" .. http_code .. ") for: " .. fingerprint:sub(1, 16) .. "...")
		queue.mark_failed(fingerprint, "http_" .. http_code)
		return false
	end

	if not ok then
		log_warn("✗ OCSP validation failed: " .. fingerprint:sub(1, 16) .. "... (" .. (error_msg or "unknown") .. ")")
		queue.mark_responder_failed(responder_url, "validation_failed")
		queue.mark_failed(fingerprint, "ocsp_invalid")
		return false
	end

	-- Success!
	log_info("✓ OCSP validation succeeded: " .. fingerprint:sub(1, 16) .. "...")
	queue.mark_responder_healthy(responder_url)
	queue.mark_validated(fingerprint)

	-- Tag response with version
	pcall(function()
		if ocsp_module.set_cached_response_version then
			local current_version = ocsp_module.get_ocsp_response_version and ocsp_module.get_ocsp_response_version() or 1
			ocsp_module.set_cached_response_version(fingerprint, current_version)
			log_debug("Tagged response version: " .. fingerprint:sub(1, 16) .. "... = v" .. current_version)
		end
	end)

	return true
end

-- Main validation with must-staple prioritization
local function validate_from_redis_queue()
	local batch_size = tonumber(os.getenv("OCSP_BATCH_SIZE") or "10")
	local prioritize = os.getenv("OCSP_PRIORITIZE_MUST_STAPLE") ~= "no"
	local must_staple_ratio = tonumber(os.getenv("OCSP_MUST_STAPLE_BATCH_RATIO") or "0.7")

	-- Calculate batch allocation
	local must_staple_quota = prioritize and math.ceil(batch_size * must_staple_ratio) or 0
	local optional_quota = batch_size - must_staple_quota

	local must_staple_validated = 0
	local must_staple_failed = 0
	local optional_validated = 0
	local optional_failed = 0
	local skipped_count = 0

	log_info("Starting validation: batch_size=" .. batch_size ..
		", must_staple_quota=" .. must_staple_quota .. ", optional_quota=" .. optional_quota)

	-- PHASE 1: Must-staple certificates (high priority)
	if prioritize and must_staple_quota > 0 then
		log_info("Phase 1: Processing must-staple certificates (up to " .. must_staple_quota .. ")")

		local scan_attempts = 0
		local max_scan_attempts = batch_size * 3

		while must_staple_validated + must_staple_failed < must_staple_quota and scan_attempts < max_scan_attempts do
			scan_attempts = scan_attempts + 1

			local fingerprint = queue.get_next_pending()
			if not fingerprint then
				log_info("Queue empty during must-staple phase")
				break
			end

			-- Check if must-staple
			local leaf_pem = read_leaf_pem(fingerprint)
			local is_must_staple = is_must_staple_cert(fingerprint, leaf_pem)

			if not is_must_staple then
				-- Re-queue for phase 2
				log_debug("Deferring non-must-staple: " .. fingerprint:sub(1, 16) .. "...")
				queue.queue_pending(fingerprint)
				goto continue_phase1
			end

			-- Validate must-staple
			local result = validate_single_cert(fingerprint, must_staple_validated + must_staple_failed + 1)
			if result == true then
				must_staple_validated = must_staple_validated + 1
			elseif result == false then
				must_staple_failed = must_staple_failed + 1
			else
				skipped_count = skipped_count + 1
			end

			::continue_phase1::
		end

		log_info("Phase 1 complete: " .. must_staple_validated .. " validated, " ..
			must_staple_failed .. " failed, " .. skipped_count .. " skipped (backoff)")
	end

	-- PHASE 2: Optional certificates (low priority)
	if must_staple_validated + must_staple_failed < batch_size and optional_quota > 0 then
		log_info("Phase 2: Processing optional certificates (up to " .. optional_quota .. ")")

		for phase2_batch = 1, optional_quota do
			local fingerprint = queue.get_next_pending()
			if not fingerprint then
				log_info("Queue empty during optional phase")
				break
			end

			-- Validate optional cert
			local result = validate_single_cert(fingerprint, must_staple_validated + must_staple_failed + phase2_batch)
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

	-- Summary
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

-- Main entry point
local function run_job()
	log_info("=== OCSP Async Validation Job Started (Prioritized) ===")

	local start_time = os.time()

	-- Validate from queue with must-staple prioritization
	local validated, failed, skipped = validate_from_redis_queue()

	local elapsed = os.time() - start_time

	log_info("=== OCSP Async Validation Job Complete ===")
	log_info("Summary: " .. validated .. " validated, " .. failed .. " failed, " ..
		skipped .. " skipped (backoff) in " .. elapsed .. "s")

	return true
end

-- Execute job
return run_job()
