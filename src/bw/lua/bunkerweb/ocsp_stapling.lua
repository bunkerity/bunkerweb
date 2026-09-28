local _M = {}

-- =====================================================================
-- OCSP Stapling HTTP Wrapper
-- Thin layer for HTTP ssl_certificate phase that delegates to
-- bunkerweb.ocsp (shared module) for all OCSP logic
-- =====================================================================

-- =====================================================================
-- MODULE-LEVEL: Cached modules
-- =====================================================================

local _helpers = require "bunkerweb.helpers" or {}
local _ssl = require "ngx.ssl" or {}
local _resty_openssl_x509 = require "resty.openssl.x509" or {}
local _bw_ocsp = require "bunkerweb.ocsp" or {}

-- =====================================================================
-- HTTP-Specific Helpers
-- =====================================================================

local function is_ocsp_enabled()
	if not _helpers then return false end
	return _helpers.getenv("SSL_USE_OCSP_STAPLING") == "yes"
end

local function get_ocsp_staple_mode()
	if not is_ocsp_enabled() then
		return "open"
	end
	if not _helpers then return "normal" end
	return _helpers.getenv("OCSP_STAPLE_MODE", "normal")
end

local function get_cert_fingerprint(cert_pem)
	-- Calculate SPKI fingerprint for cache lookups
	-- Delegates actual hash to bunkerweb.ocsp if available
	if not cert_pem or not _resty_openssl_x509 then
		return nil
	end

	if _bw_ocsp and _bw_ocsp.get_cert_fingerprint then
		return _bw_ocsp.get_cert_fingerprint(cert_pem)
	end

	-- Fallback: basic calculation
	local cert, _ = _resty_openssl_x509.new(cert_pem, "PEM")
	if not cert then return nil end

	local pubkey, _ = cert:get_pubkey()
	if not pubkey then return nil end

	local spki_der, _ = pubkey:to_DER()
	if not spki_der then return nil end

	local digest = require "resty.openssl.digest"
	if not digest then return nil end

	local d = digest.new("sha256")
	if not d then return nil end

	d:update(spki_der)
	local fingerprint = d:final()

	return string.format("%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x",
		string.byte(fingerprint, 1, 32))
end

local function get_cert_must_staple(cert_pem)
	-- Check if certificate requires Must-Staple
	if not cert_pem or not _resty_openssl_x509 then
		return nil
	end

	if _bw_ocsp and _bw_ocsp.cert_requires_must_staple then
		return _bw_ocsp.cert_requires_must_staple(cert_pem)
	end

	-- Fallback: basic check via TLS Feature extension
	local cert, _ = _resty_openssl_x509.new(cert_pem, "PEM")
	if not cert then return nil end

	local extensions = cert:get_extensions()
	if not extensions then return false end

	for i, ext in ipairs(extensions) do
		local nid = ext:get_nid()
		if nid == 1367 then  -- TLS Feature extension
			return true
		end
	end

	return false
end

-- =====================================================================
-- Main OCSP Stapling Decision
-- HTTP wrapper delegates to bunkerweb.ocsp for actual logic
-- =====================================================================

function _M.staple_certificate(cert_pem, logger)
	-- Input: certificate PEM (from set_cert), logger instance
	-- Output: ok (bool), ocsp_response (DER bytes), must_staple_enforced (bool)

	if not logger then
		logger = {log = function() end}
	end

	local function log_debug(msg)
		if logger then logger:log(ngx.DEBUG, msg) end
	end

	local function log_err(msg)
		if logger then logger:log(ngx.ERR, msg) end
	end

	-- =====================================================================
	-- STEP 1: Check if OCSP enabled globally
	-- =====================================================================

	if not is_ocsp_enabled() then
		log_debug("OCSP stapling disabled globally")
		return true, nil, false
	end

	if not cert_pem or not _ssl or not _bw_ocsp then
		log_debug("OCSP stapling skipped: missing prerequisites")
		return true, nil, false
	end

	-- =====================================================================
	-- STEP 2: Get certificate metadata
	-- =====================================================================

	local fingerprint = get_cert_fingerprint(cert_pem)
	if not fingerprint then
		log_debug("Could not calculate certificate fingerprint")
		return true, nil, false
	end
	log_debug("Certificate fingerprint: " .. fingerprint:sub(1, 16) .. "...")

	local must_staple = get_cert_must_staple(cert_pem)
	log_debug("Certificate Must-Staple: " .. tostring(must_staple))

	local staple_mode = get_ocsp_staple_mode()
	log_debug("OCSP staple mode: " .. staple_mode)

	-- =====================================================================
	-- STEP 3: Delegate to shared OCSP module
	-- =====================================================================

	if not _bw_ocsp.handle_stapling then
		log_debug("bunkerweb.ocsp.handle_stapling not available, serving unstapled")
		return true, nil, false
	end

	local ok_stapling, ocsp_response, must_staple_required, err = _bw_ocsp.handle_stapling(
		cert_pem,
		fingerprint,
		must_staple,
		staple_mode,
		logger
	)

	-- =====================================================================
	-- STEP 4: Return result to conf for attachment/abort decision
	-- =====================================================================

	if not ok_stapling then
		if must_staple_required then
			log_err("Must-Staple certificate failed OCSP validation")
			return false, nil, true  -- Abort handshake
		else
			log_debug("OCSP stapling failed (non-critical): " .. tostring(err))
			return true, nil, false  -- Continue without stapling
		end
	end

	if ocsp_response then
		log_debug("OCSP response available for attachment")
		return true, ocsp_response, false
	end

	if must_staple_required then
		log_err("Must-Staple certificate but no OCSP response available")
		return false, nil, true  -- Abort handshake
	end

	log_debug("No OCSP response but non-critical (non-MS or mode=open)")
	return true, nil, false
end

-- =====================================================================
-- State Coordination (HTTP ↔ Stream)
-- =====================================================================

-- Called by conf to update shared state after OCSP decision
function _M.update_epoch(logger)
	if not _bw_ocsp or not _bw_ocsp.update_epoch then
		return
	end

	_bw_ocsp.update_epoch()
end

return _M
