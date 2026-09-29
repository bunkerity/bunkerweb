-- OCSP Must-Staple Module
-- Detects, caches, and enforces must-staple requirements
-- Only loaded when needed (normal or staple_only mode)

local _M = {}

local common = require("bunkerweb.ocsp_common").internal
local store = require("bunkerweb.ocsp_store").internal

local resolve_leaf_must_staple = store.resolve_leaf_must_staple

-- Internal: Request-scoped memoization of must-staple resolution via ngx.ctx
-- Avoids re-resolving the same cert during staple(), probe(), and decision paths
local function resolve_leaf_must_staple_with_cache(cert_pem, cert_fp)
	local ctx = ngx.ctx
	if not ctx then
		-- No context (should not happen in TLS handshake); resolve directly
		return resolve_leaf_must_staple(cert_pem, cert_fp)
	end

	-- Initialize cache on first use
	if not ctx.bw_ocsp_ms_cache then
		ctx.bw_ocsp_ms_cache = {}
	end

	-- Generate cache key from fingerprint or PEM hash
	local key = cert_fp or ("pem_" .. (cert_pem and cert_pem:sub(1, 32) or "unknown"))

	-- Return cached result if available
	if ctx.bw_ocsp_ms_cache[key] ~= nil then
		return ctx.bw_ocsp_ms_cache[key]
	end

	-- Resolve and cache for this request
	local result = resolve_leaf_must_staple(cert_pem, cert_fp)
	ctx.bw_ocsp_ms_cache[key] = result
	return result
end

-- Check if must-staple enforcement is enabled in current config
-- Returns: true if mode is "normal" or "staple_only", false if "open"
function _M.check_enabled(mode)
	mode = mode or common.ocsp_staple_mode()
	return mode ~= "open"
end

-- Get must-staple requirement for cert with request-scoped caching
-- Returns: true if cert has must-staple extension, false otherwise
function _M.get_must_staple(cert_pem, cert_fp)
	return resolve_leaf_must_staple_with_cache(cert_pem, cert_fp)
end

-- Annotate cert list with must-staple requirement
-- Modifies leaves table in-place, adding must_staple field to each leaf
function _M.annotate_leaves(leaves)
	if type(leaves) ~= "table" then
		return
	end
	for _, leaf in ipairs(leaves) do
		if type(leaf) == "table" then
			local pem = leaf.pem or leaf.ocsp_cert or leaf.cert_pem
			local fp = leaf.fp or leaf.ocsp_fp_hint
			if pem or fp then
				leaf.must_staple = resolve_leaf_must_staple_with_cache(pem, fp)
			end
		end
	end
end

-- Decide if we can skip OCSP validation for this cert
-- In open mode: skip all validation (optional stapling)
-- In normal/staple_only mode: skip only non-must-staple certs
-- Returns: true if validation can be skipped, false if required
function _M.should_skip_validation(leaf_pem, fingerprint, mode)
	mode = mode or common.ocsp_staple_mode()

	-- Open mode: skip validation for all (optional stapling)
	if mode == "open" then
		return true
	end

	-- Normal/staple_only mode: check if must-staple
	local is_must_staple = resolve_leaf_must_staple_with_cache(leaf_pem, fingerprint)
	if is_must_staple then
		-- Must-staple: cannot skip validation
		return false
	end

	-- Optional stapling: can skip, but async validation will queue for security
	return true
end

return _M
