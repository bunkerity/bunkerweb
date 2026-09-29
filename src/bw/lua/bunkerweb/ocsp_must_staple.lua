-- OCSP Must-Staple Module
-- Detects, caches, and enforces must-staple requirements.
-- Tri-state from resolve_leaf_must_staple: true | false | nil (unknown).
-- Fail-closed gate everywhere: unknown ~= false → enforce / do not skip validate.

local _M = {}

local common = require("bunkerweb.ocsp_common").internal
local store = require("bunkerweb.ocsp_store").internal

local is_fp64 = common.is_fp64
local resp_binding = common.resp_binding
local resolve_leaf_must_staple = store.resolve_leaf_must_staple

-- Stable request-cache key. Never use a PEM prefix: "-----BEGIN CERTIFICATE-----"
-- is ~27 bytes, so sub(1, 32) collides across every leaf in a dual-cert handshake.
-- When both fp and PEM are present, bind them together so an early fp-only miss
-- cannot sticky-cache false across a later real MS PEM (HTTP leaf_ms_cache parity).
local function ms_cache_key(cert_pem, cert_fp)
	local fp_part = nil
	if is_fp64(cert_fp) then
		fp_part = cert_fp:lower()
	end
	local pem_part = nil
	if type(cert_pem) == "string" and cert_pem ~= "" then
		local dig = resp_binding(cert_pem)
		if dig then
			pem_part = dig
		end
	end
	if fp_part and pem_part then
		return "fp:" .. fp_part .. ":pem:" .. pem_part
	end
	if fp_part then
		return "fp:" .. fp_part
	end
	if pem_part then
		return "pem:" .. pem_part
	end
	return nil
end

-- Request-scoped memoization via ngx.ctx (staple / probe / decision share one answer).
local function resolve_leaf_must_staple_with_cache(cert_pem, cert_fp)
	local ctx = ngx.ctx
	if not ctx then
		return resolve_leaf_must_staple(cert_pem, cert_fp)
	end

	local key = ms_cache_key(cert_pem, cert_fp)
	if not key then
		return resolve_leaf_must_staple(cert_pem, cert_fp)
	end

	if not ctx.bw_ocsp_ms_cache then
		ctx.bw_ocsp_ms_cache = {}
	end

	local cached = ctx.bw_ocsp_ms_cache[key]
	-- Box every result (incl. nil): raw t[k]=nil would delete the entry.
	if type(cached) == "table" and cached._boxed then
		return cached._ms
	end

	local result = resolve_leaf_must_staple(cert_pem, cert_fp)
	ctx.bw_ocsp_ms_cache[key] = { _boxed = true, _ms = result }
	return result
end

-- True when Must-Staple enforcement applies for this mode.
-- Never call ocsp_staple_mode() without internalstore+SNI (that always yields "open").
-- Omitted mode → assume enforcement on (fail closed).
function _M.check_enabled(mode)
	if mode == nil or mode == "" then
		return true
	end
	return tostring(mode):lower() ~= "open"
end

-- Tri-state Must-Staple for this leaf (true / false / nil), request-cached.
function _M.get_must_staple(cert_pem, cert_fp)
	return resolve_leaf_must_staple_with_cache(cert_pem, cert_fp)
end

-- Annotate leaves in-place with tri-state must_staple (fail-closed callers use ~= false).
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

-- Whether ngx.ocsp.validate may be skipped for this leaf.
-- mode == "open" → always skip (optional stapling).
-- Otherwise skip only when Must-Staple is proven false.
-- Omitted mode → do not open-skip (callers that lack mode still fail closed).
-- Unknown (nil) → do not skip.
function _M.should_skip_validation(leaf_pem, fingerprint, mode)
	if mode ~= nil and tostring(mode):lower() == "open" then
		return true
	end
	return resolve_leaf_must_staple_with_cache(leaf_pem, fingerprint) == false
end

return _M
