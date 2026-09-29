-- Pure certificate / OCSP DER parsing with a per-worker memo (no disk, no shared state).
-- Part of bunkerweb.ocsp; other modules use the .internal table, callers use bunkerweb.ocsp.
local _M = {}

local ngx = ngx

local common = require("bunkerweb.ocsp_common").internal
local is_fp64 = common.is_fp64
local log = common.log
local to_hex = common.to_hex

-- OpenSSL NIDs for TLS 1.3 CertificateVerify EC/Ed schemes
local NID_P256, NID_P384, NID_P521, NID_ED25519, NID_ED448 = 415, 715, 716, 1087, 1088
do
	local ok_obj, objects = pcall(require, "resty.openssl.objects")
	if ok_obj and objects and objects.txtnid2nid then
		local function resolve(name, fallback)
			local n = objects.txtnid2nid(name)
			if type(n) == "number" and n > 0 then
				return n
			end
			return fallback
		end
		NID_P256 = resolve("prime256v1", NID_P256)
		NID_P384 = resolve("secp384r1", NID_P384)
		NID_P521 = resolve("secp521r1", NID_P521)
		NID_ED25519 = resolve("ED25519", NID_ED25519)
		NID_ED448 = resolve("ED448", NID_ED448)
	end
end

local function pem_blocks(cert_pem)
	local blocks = {}
	for block in cert_pem:gmatch("(%-%-%-%-%-BEGIN CERTIFICATE%-%-%-%-%-.-%-%-%-%-%-END CERTIFICATE%-%-%-%-%-)") do
		blocks[#blocks + 1] = block
	end
	if #blocks == 0 then
		blocks[1] = cert_pem
	end
	return blocks
end

-- Per-worker memo of pure PEM-derived facts (SPKI, DNs, Must-Staple bit, serial, key
-- kind). One handshake used to re-parse the same PEM ~20 times. Keyed by the exact
-- PEM bytes, so a rewrapped PEM is only a miss, never a wrong answer.
-- Stores one full profile per PEM (single x509 pass); accessors read fields from it.
-- Eviction: touch-counter LRU — O(1) hits, O(n) only when the cache is full.
-- Main-chunk locals are capped at 200 by LuaJIT, so memo state lives in this block.
local pem_profile_get
local pem_profile_batched
local ocsp_der_memo_fetch
do
	local PEM_MEMO_MAX = 512
	local OCSP_DER_MEMO_MAX = 256
	local MEMO_NIL = {}
	local pem_memo = {}
	local pem_memo_count = 0
	local pem_memo_touch = {} -- pem → monotonic touch for LRU
	local pem_touch_gen = 0
	local ocsp_der_memo = {}
	local ocsp_der_memo_count = 0

	local function touch_pem(pem)
		pem_touch_gen = pem_touch_gen + 1
		pem_memo_touch[pem] = pem_touch_gen
	end

	-- Evict least-recently-touched PEM. Returns true if an entry was removed.
	local function evict_lru()
		local oldest_pem, oldest_touch = nil, nil
		for pem, t in pairs(pem_memo_touch) do
			if oldest_touch == nil or t < oldest_touch then
				oldest_touch = t
				oldest_pem = pem
			end
		end
		if not oldest_pem then
			return false
		end
		pem_memo[oldest_pem] = nil
		pem_memo_touch[oldest_pem] = nil
		pem_memo_count = pem_memo_count - 1
		return true
	end

	-- One batched profile per PEM. Shared table is read-only for callers.
	pem_profile_get = function(pem)
		if type(pem) ~= "string" or pem == "" then
			return pem_profile_batched(pem)
		end
		local profile = pem_memo[pem]
		if profile then
			touch_pem(pem)
			return profile
		end
		if pem_memo_count >= PEM_MEMO_MAX then
			if not evict_lru() then
				-- Invariant broken; wipe rather than grow unbounded.
				pem_memo = {}
				pem_memo_touch = {}
				pem_memo_count = 0
			end
		end
		profile = pem_profile_batched(pem)
		-- Do not memoize empty/incomplete profiles (transient FFI glitch or BN miss).
		-- Missing serial/SPKI would strand CertID / pin paths until LRU.
		if
			type(profile) ~= "table"
			or next(profile) == nil
			or profile.serial == nil
			or not is_fp64(profile.spki_fingerprint)
		then
			return profile or {}
		end
		pem_memo[pem] = profile
		touch_pem(pem)
		pem_memo_count = pem_memo_count + 1
		return profile
	end

	-- SHA256 hex of the full OCSP DER — never a prefix. Same-responder bodies share
	-- structural prefixes; a 32-byte key caused CertID / blacklist wrong answers.
	local function der_body_key(ocsp_der)
		local ok, hex = pcall(function()
			local digest_lib = require("resty.openssl.digest")
			local digest_ctx = digest_lib.new("sha256")
			digest_ctx:update(ocsp_der)
			return to_hex(digest_ctx:final())
		end)
		if ok and type(hex) == "string" and #hex == 64 then
			return hex
		end
		-- Fail closed to correct (if heavy) keying rather than a colliding prefix.
		return ocsp_der
	end

	-- Separate cache for OCSP DER serial walks (binary bodies, not PEM).
	-- Returned tables are always fresh copies so callers cannot poison the memo.
	local function clone_str_list(t)
		if type(t) ~= "table" then
			return t
		end
		local out = {}
		for i = 1, #t do
			out[i] = t[i]
		end
		return out
	end

	ocsp_der_memo_fetch = function(ocsp_der, compute)
		if type(ocsp_der) ~= "string" or #ocsp_der < 2 then
			return compute(ocsp_der)
		end
		local key = der_body_key(ocsp_der)
		local result = ocsp_der_memo[key]
		if result == MEMO_NIL then
			return nil
		end
		if result ~= nil then
			return clone_str_list(result)
		end
		if ocsp_der_memo_count >= OCSP_DER_MEMO_MAX then
			ocsp_der_memo = {}
			ocsp_der_memo_count = 0
		end
		result = compute(ocsp_der)
		if result == nil then
			ocsp_der_memo[key] = MEMO_NIL
			ocsp_der_memo_count = ocsp_der_memo_count + 1
			return nil
		end
		ocsp_der_memo[key] = clone_str_list(result)
		ocsp_der_memo_count = ocsp_der_memo_count + 1
		return clone_str_list(ocsp_der_memo[key])
	end
end

-- True when TLS Feature text asserts status_request (Must-Staple / feature id 5).
-- Named forms first. Digit "5" only when the whole text is a feature-id list
-- ("5", "5, 17") — never gmatch %d+ over OID arcs or openssl dumps.
local function tls_feature_is_must_staple(text)
	if type(text) ~= "string" or text == "" then
		return false
	end
	if text:find("OCSP status request", 1, true) then
		return true
	end
	-- Named forms; exclude status_request_v2 / statusRequestV2
	if text:find("status_request%f[^%w_]") or text:match("status_request%s*$") then
		return true
	end
	if text:find("statusRequest%f[^%w]") or text:match("%.?statusRequest%s*$") then
		return true
	end
	local trimmed = text:match("^%s*(.-)%s*$") or ""
	-- Bare feature-id list only (digits, commas, whitespace) — rejects OID text.
	if trimmed:match("^[%d%s,]+$") then
		for token in trimmed:gmatch("%d+") do
			-- Accept zero-padded forms ("05") — OpenSSL digit dumps occasionally pad.
			if tonumber(token) == 5 then
				return true
			end
		end
	end
	return false
end

-- Canonical uppercase hex serial without leading zeros. Strings are always hex:
-- ocsp-refresh.py writes format(serial, "X"), and an all-digit hex serial such as
-- "1000" (0x1000) must not be reinterpreted as decimal.
local function canonical_serial_hex(serial)
	if serial == nil then
		return nil
	end
	-- resty BN may be userdata or a table with to_hex / to_number.
	local st = type(serial)
	if st == "table" or st == "userdata" then
		if serial.to_hex then
			local ok_hex, hex = pcall(function()
				return serial:to_hex()
			end)
			if ok_hex and type(hex) == "string" and #hex > 0 then
				hex = hex:upper():gsub("[%s:]+", ""):gsub("^0X", "")
				if hex == "" or not hex:match("^[0-9A-F]+$") then
					return nil
				end
				hex = hex:gsub("^0+", "")
				return hex == "" and "0" or hex
			end
		end
		if serial.to_number then
			local ok_n, n = pcall(function()
				return serial:to_number()
			end)
			if ok_n and type(n) == "number" then
				serial = n
			end
		end
	end
	if type(serial) == "number" then
		-- Doubles are exact only below 2^53; larger serials must arrive as hex strings.
		if serial < 0 or serial >= 2 ^ 53 or serial % 1 ~= 0 then
			return nil
		end
		local hex = string.format("%X", serial)
		hex = hex:gsub("^0+", "")
		return hex == "" and "0" or hex
	end
	if type(serial) ~= "string" then
		return nil
	end
	serial = serial:upper():gsub("[%s:]+", ""):gsub("^0X", "")
	if serial == "" or not serial:match("^[0-9A-F]+$") then
		return nil
	end
	serial = serial:gsub("^0+", "")
	return serial == "" and "0" or serial
end

-- SHA256 of SubjectPublicKeyInfo DER, matching ocsp-refresh.py.
-- Never key anything by ngx.md5(cert_pem) as a stand-in for the SPKI: PEM rewrap
-- changes that hash while the SPKI is identical (path skew vs the job).
-- Profile is memoized once per PEM (single x509 pass for all facts).
local function spki_fingerprint(cert_pem)
	local profile = pem_profile_get(cert_pem)
	local fingerprint = profile and profile.spki_fingerprint
	if is_fp64(fingerprint) then
		return fingerprint
	end
	return nil
end

-- Helper: batch extract SPKI for issuers already grouped by DN.
-- Optimized for pre-filtered list (smaller than full issuer list).
local function batch_spki_fingerprints_filtered(dn_grouped_issuers)
	local result = {}
	if type(dn_grouped_issuers) ~= "table" then
		return result
	end
	for iss, _ in pairs(dn_grouped_issuers) do
		if type(iss) == "string" and iss ~= "" then
			result[iss] = spki_fingerprint(iss)
		end
	end
	return result
end

-- Canonical AIA OCSP URI for comparison — must match ocsp-refresh._normalize_ocsp_aia_uri:
-- http(s) only, lowercase scheme/host, drop userinfo, omit default :80/:443, keep path/query/fragment.
local function normalize_ocsp_aia_uri(url)
	if type(url) ~= "string" then
		return nil
	end
	url = url:match("^%s*(.-)%s*$") or ""
	-- Trim trailing punctuation often left by text dumps ("URI:http://x,").
	url = url:gsub("[,;%.]+$", "")
	if url == "" then
		return nil
	end
	local scheme, rest = url:match("^([Hh][Tt][Tt][Pp][Ss]?)://(.+)$")
	if not scheme or not rest then
		return nil
	end
	scheme = scheme:lower()
	local authority, pathquery = rest:match("^([^/?#]*)(.*)$")
	if type(authority) ~= "string" or authority == "" then
		return nil
	end
	-- Drop userinfo (user:pass@host).
	local at = authority:match("^.*@(.-)$")
	if at then
		authority = at
	end
	local host, port
	if authority:sub(1, 1) == "[" then
		-- IPv6 literal [::1] or [::1]:8443
		host, port = authority:match("^(%[[%x:]+%]):(%d+)$")
		if not host then
			host = authority:match("^(%[[%x:]+%])$")
		end
	else
		host, port = authority:match("^([^:]+):(%d+)$")
		if not host then
			host = authority
		end
	end
	if type(host) ~= "string" or host == "" then
		return nil
	end
	host = host:lower()
	local netloc = host
	if port then
		local pnum = tonumber(port)
		local default = (scheme == "http") and 80 or 443
		if pnum and pnum ~= default then
			netloc = host .. ":" .. port
		end
	end
	return scheme .. "://" .. netloc .. (pathquery or "")
end

-- Batch extract all certificate profile facts in single x509 object pass
-- Reuses cert_obj instead of creating 5 separate instances per PEM
-- Saves: 5-8ms per certificate (single FFI call vs 5 separate ones)
-- Set after all helper functions are defined to avoid forward references.
pem_profile_batched = function(pem)
	if type(pem) ~= "string" or pem == "" then
		return {}
	end
	local profile = {}
	local ok = pcall(function()
		local x509 = require("resty.openssl.x509")
		local cert_obj = x509.new(pem)
		if not cert_obj then
			return
		end

		-- Must-Staple: TLS Feature extension. Tri-state for has_must_staple:
		-- true = positive MS, false = proven absent/non-MS, nil = extension present
		-- but text unrecognized (never invent false — that fail-opens vs ocsp.json).
		local tls_feature_ext = cert_obj:get_extension("tlsfeature")
		if tls_feature_ext then
			local text = tls_feature_ext:text() or ""
			if tls_feature_is_must_staple(text) then
				profile.must_staple = true
			else
				local trimmed = text:match("^%s*(.-)%s*$") or ""
				-- Bare feature-id list without 5 → proven not Must-Staple (e.g. "17").
				if trimmed ~= "" and trimmed:match("^[%d%s,]+$") then
					profile.must_staple = false
				else
					-- Empty / ASN.1 dump / unrecognized named form → unknown.
					profile.must_staple = nil
				end
			end
		else
			profile.must_staple = false
		end

		-- Serial: Extract certificate serial number (checked after definition)
		profile.serial = canonical_serial_hex(cert_obj:get_serial_number())

		-- Public key: Extract once, use for both kind and sig_profile
		local pub = cert_obj:get_pubkey()
		if pub then
			local key_type = pub.get_key_type and pub:get_key_type() or nil
			local label = key_type
			local nid = nil
			if type(key_type) == "table" then
				label = key_type.sn or key_type.ln or key_type.nid
				nid = key_type.nid
			elseif type(key_type) == "number" then
				nid = key_type
			end
			label = tostring(label or ""):lower()

			-- Key kind (checked after NIDs defined)
			if label:find("ed25519", 1, true) or nid == NID_ED25519 then
				profile.pubkey_kind = "ed"
				profile.curve_nid = NID_ED25519
			elseif label:find("ed448", 1, true) or nid == NID_ED448 then
				profile.pubkey_kind = "ed"
				profile.curve_nid = NID_ED448
			elseif label:find("rsa", 1, true) then
				profile.pubkey_kind = "rsa"
			elseif label:find("ec", 1, true) or label:find("id-ec", 1, true) then
				profile.pubkey_kind = "ec"
				local params = pub.get_parameters and pub:get_parameters() or nil
				if type(params) == "table" and type(params.group) == "number" and params.group > 0 then
					profile.curve_nid = params.group
				end
			end
		end

		-- Names: Extract subject and issuer DNs
		if cert_obj.get_subject_name and cert_obj.get_issuer_name then
			profile.subject_dn = tostring(cert_obj:get_subject_name() or "")
			profile.issuer_dn = tostring(cert_obj:get_issuer_name() or "")
		end

		-- AIA OCSP URIs: Extract from certificate (checked after definition)
		local aia_ext = cert_obj:get_extension("authorityInfoAccess")
		if aia_ext then
			local aia_text = aia_ext:text() or ""
			local uris = {}
			local seen = {}
			for uri in aia_text:gmatch("1%.3%.6%.1%.5%.5%.7%.48%.1%s*[-=]%s*URI:([%w%p]+)") do
				local n = normalize_ocsp_aia_uri(uri)
				if n and not seen[n] then
					seen[n] = true
					uris[#uris + 1] = n
				end
			end
			if #uris == 0 then
				for uri in aia_text:gmatch("OCSP%s*[-=]?%s*URI:([%w%p]+)") do
					local n = normalize_ocsp_aia_uri(uri)
					if n and not seen[n] then
						seen[n] = true
						uris[#uris + 1] = n
					end
				end
			end
			profile.aia_uris = uris
		else
			profile.aia_uris = {}
		end

		-- SPKI: Extract public key and SHA256
		if pub then
			local spki = pub:tostring("public", "DER")
			if spki then
				local digest_lib = require("resty.openssl.digest")
				local digest_ctx = digest_lib.new("sha256")
				digest_ctx:update(spki)
				profile.spki_fingerprint = to_hex(digest_ctx:final())
			end
		end
	end)
	if not ok then
		log(ngx.DEBUG, "OCSP certificate profile batch extraction failed")
		-- Discard partial facts — caching a half-filled profile fail-opens Must-Staple
		-- (false) or strands serial/AIA until LRU.
		return {}
	end
	return profile
end

-- Handshake path: resty.openssl only — no /tmp + openssl CLI.
-- Returns true | false | nil (unknown). Unknown must stay fail-closed at call sites
-- that decide whether Must-Staple enforcement applies (never invent false on throw).
-- Callers also consult ocsp.json (written by ocsp-refresh) when resty cannot see
-- Must-Staple — see resolve_leaf_must_staple.
-- Profile is memoized once per PEM (single x509 pass for all facts).
local function has_must_staple(cert_pem)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return nil
	end
	local profile = pem_profile_get(cert_pem)
	local must = profile and profile.must_staple
	if must == nil then
		return nil
	end
	return must
end

-- { subject_dn, issuer_dn } strings (either may be nil on parse failure).
-- Profile is memoized once per PEM (single x509 pass for all facts).
local function pem_names(pem)
	local profile = pem_profile_get(pem)
	if type(profile) ~= "table" then
		return nil, nil
	end
	return profile.subject_dn, profile.issuer_dn
end

-- Trust anchor (subject == issuer): never a stapled CertificateEntry.
local function is_self_signed(pem)
	local s, iss = pem_names(pem)
	return s ~= nil and s ~= "" and s == iss
end

-- Minimal DER walk for OCSP CertID serials. lua-resty-openssl has no OCSP module, so
-- the former require("resty.openssl.ocsp") always failed and every CertID check
-- refused. Returns tag, content_start, content_end, next_pos (or nil if malformed).
local function der_read(der, pos, limit)
	if not pos or pos + 1 > limit then
		return nil
	end
	local tag = der:byte(pos)
	local len = der:byte(pos + 1)
	local cs = pos + 2
	if len >= 0x80 then
		local n = len - 0x80
		if n < 1 or n > 4 or cs + n - 1 > limit then
			return nil
		end
		len = 0
		for i = 0, n - 1 do
			len = len * 256 + der:byte(cs + i)
		end
		cs = cs + n
	end
	local ce = cs + len - 1
	if ce > limit then
		return nil
	end
	return tag, cs, ce, ce + 1
end

-- id-pkix-ocsp-basic (1.3.6.1.5.5.7.48.1.1) OID content bytes.
local OID_OCSP_BASIC = "\43\6\1\5\5\7\48\1\1"

-- Canonical uppercase hex serial of every SingleResponse CertID (RFC 6960 4.2.1),
-- in response order. nil when the DER is not a successful basic OCSP response.
-- Memoized by full-body SHA256 (see ocsp_der_memo_fetch).
local function ocsp_der_serials(der)
	if type(der) ~= "string" or #der < 2 then
		return nil
	end
	local n = #der
	local t, s, e, nx
	-- DER sequence tag check
	t, s, e = der_read(der, 1, n)
	if t ~= 0x30 then
		return nil
	end
	local top_end = e
	-- responseStatus ENUMERATED must be successful (0).
	t, s, e, nx = der_read(der, s, top_end)
	if t ~= 0x0A or e ~= s or der:byte(s) ~= 0 then
		return nil
	end
	-- responseBytes [0] EXPLICIT ResponseBytes
	t, s, e = der_read(der, nx, top_end)
	if t ~= 0xA0 then
		return nil
	end
	t, s, e = der_read(der, s, e)
	if t ~= 0x30 then
		return nil
	end
	local rb_end = e
	t, s, e, nx = der_read(der, s, rb_end)
	if t ~= 0x06 or der:sub(s, e) ~= OID_OCSP_BASIC then
		return nil
	end
	-- response OCTET STRING → BasicOCSPResponse → tbsResponseData
	t, s, e = der_read(der, nx, rb_end)
	if t ~= 0x04 then
		return nil
	end
	t, s, e = der_read(der, s, e)
	if t ~= 0x30 then
		return nil
	end
	t, s, e = der_read(der, s, e)
	if t ~= 0x30 then
		return nil
	end
	local rd_end = e
	-- [0] version (optional), responderID [1]|[2], producedAt, responses
	local _
	t, _, _, nx = der_read(der, s, rd_end)
	if t == 0xA0 then
		t, _, _, nx = der_read(der, nx, rd_end)
	end
	if t ~= 0xA1 and t ~= 0xA2 then
		return nil
	end
	t, _, _, nx = der_read(der, nx, rd_end)
	if t ~= 0x18 then
		return nil
	end
	t, s, e = der_read(der, nx, rd_end)
	if t ~= 0x30 then
		return nil
	end
	local serials = {}
	local pos, list_end = s, e
	while pos <= list_end do
		local st, ss, se, snx = der_read(der, pos, list_end)
		if st ~= 0x30 then
			return nil
		end
		-- CertID: hashAlgorithm, issuerNameHash, issuerKeyHash, serialNumber
		local ct, cs, ce = der_read(der, ss, se)
		if ct ~= 0x30 then
			return nil
		end
		local at, _, _, anx = der_read(der, cs, ce)
		local nt, _, _, nnx = der_read(der, anx, ce)
		local kt, _, _, knx = der_read(der, nnx, ce)
		local it, is, ie = der_read(der, knx, ce)
		if at ~= 0x30 or nt ~= 0x04 or kt ~= 0x04 or it ~= 0x02 or ie < is then
			return nil
		end
		-- RFC 5280 serials are positive; a negative INTEGER is not a leaf we issued.
		if der:byte(is) >= 0x80 then
			return nil
		end
		local hex = to_hex(der:sub(is, ie)):upper():gsub("^0+", "")
		serials[#serials + 1] = hex == "" and "0" or hex
		pos = snx
	end
	if #serials == 0 then
		return nil
	end
	return serials
end

-- Memoized wrapper around ocsp_der_serials to cache results per response body hash.
local function ocsp_der_serials_memoized(ocsp_der)
	return ocsp_der_memo_fetch(ocsp_der, ocsp_der_serials)
end

-- Serial of the SingleResponse naming want_hex when present.
-- When want_hex is set and no SingleResponse names it → nil (not serials[1]).
-- When want_hex is nil/omitted → first serial (callers that only need "any").
-- Callers that compare with want_hex must treat nil as miss or unreadable;
-- use a second call without want_hex to distinguish unreadable DER.
local function ocsp_resp_serial_hex(ocsp_der, want_hex)
	local serials = ocsp_der_serials_memoized(ocsp_der)
	if not serials then
		return nil
	end
	if want_hex then
		for _, serial in ipairs(serials) do
			if serial == want_hex then
				return serial
			end
		end
		return nil
	end
	return serials[1]
end

function _M.ocsp_resp_serial_hex(ocsp_der, want_hex)
	return ocsp_resp_serial_hex(ocsp_der, want_hex)
end

local function leaf_serial_hex(cert_pem)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return nil
	end
	local profile = pem_profile_get(cert_pem)
	return profile and profile.serial or nil
end

local function pem_dn_str(cert_pem, which)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return nil
	end
	local subject, issuer = pem_names(cert_pem)
	local out = subject
	if which == "issuer" then
		out = issuer
	end
	if type(out) == "string" and #out > 0 then
		return out
	end
	return nil
end

-- Batch extract SPKI fingerprints for multiple issuer PEMs.
-- Avoids redundant extractions when same PEM appears multiple times in list.
-- Returns: {pem1 → fp1, pem2 → fp2, ...} (only unique PEMs computed once)
-- Saves: 1-3ms per duplicate issuer PEM (via memo hit instead of re-extract).
local function batch_spki_fingerprints(issuer_pems)
	local result = {}
	local seen = {}
	if type(issuer_pems) ~= "table" then
		return result
	end
	-- First pass: identify unique PEMs and extract SPKIs.
	-- Memo cache ensures each unique PEM computed only once per batch.
	for _, iss in ipairs(issuer_pems) do
		if type(iss) == "string" and iss ~= "" and not seen[iss] then
			seen[iss] = true
			result[iss] = spki_fingerprint(iss)
		end
	end
	return result
end

-- Pre-filter issuers by SPKI fingerprint to detect true duplicates early.
-- Groups issuers by (DN, SPKI) pair: if all matching DN have same SPKI, early exit.
-- Returns: distinct_spki_count, spki_map, unreadable_count.
-- unreadable_count > 0 means at least one DN match lacked a readable SPKI.
local function prefilter_issuers_by_spki(issuer_pems, target_dn)
	if type(issuer_pems) ~= "table" or type(target_dn) ~= "string" then
		return 0, {}, 0
	end
	local dn_to_issuers = {}
	local distinct_spki = {}

	-- Group issuers by subject DN first (avoids SPKI extraction for non-matching DNs)
	for _, iss in ipairs(issuer_pems) do
		if type(iss) == "string" and iss ~= "" then
			local subj = pem_dn_str(iss, "subject")
			if subj and subj == target_dn then
				if not dn_to_issuers[iss] then
					dn_to_issuers[iss] = true
				end
			end
		end
	end

	-- Extract SPKI for DN-matching issuers only (pre-filtered list is usually small)
	local spki_map = batch_spki_fingerprints_filtered(dn_to_issuers)

	-- Count distinct readable SPKIs. Any nil fingerprint among DN matches is
	-- reported separately — never treat {A, nil} as a single unambiguous SPKI.
	local seen_spki = {}
	local unreadable = 0
	for iss, _ in pairs(dn_to_issuers) do
		local fp = spki_map[iss]
		if not fp then
			unreadable = unreadable + 1
		elseif not seen_spki[fp] then
			seen_spki[fp] = true
			distinct_spki[#distinct_spki + 1] = fp
		end
	end

	return #distinct_spki, spki_map, unreadable
end

-- CertID must name this handshake leaf: serial match + issuer DN binds to a candidate
-- issuer PEM (subject == leaf.issuer). Fail closed when either side is unreadable.
-- Several PEMs can share one subject DN (cross-signs). Accept that DN only when
-- every match is the same SPKI; distinct keys return issuer_ambiguous (caller
-- maps this to certid_mismatch). This is not a full OCSP CertID issuerNameHash /
-- issuerKeyHash check — ocsp_der_serials reads the serial only, and the SPKI
-- tie-break stops the wrong cross-sign from passing on DN text alone.
-- ngx.ocsp.validate_ocsp_response also binds CertID; this gate covers verified-L1
-- paths that skip re-validate after a same-key renew left a stale body under the SPKI.
local function certid_matches_handshake_leaf(leaf_pem, ocsp_der, issuer_pems)
	if type(leaf_pem) ~= "string" or leaf_pem == "" or type(ocsp_der) ~= "string" or ocsp_der == "" then
		return false, "missing_leaf_or_resp"
	end
	local leaf_serial = leaf_serial_hex(leaf_pem)
	if not leaf_serial then
		return false, "serial_unreadable"
	end
	local resp_serial = ocsp_resp_serial_hex(ocsp_der, leaf_serial)
	if resp_serial ~= leaf_serial then
		if not ocsp_resp_serial_hex(ocsp_der) then
			return false, "serial_unreadable"
		end
		return false, "serial_mismatch"
	end
	local leaf_issuer = pem_dn_str(leaf_pem, "issuer")
	if not leaf_issuer then
		return false, "leaf_issuer_unreadable"
	end
	if type(issuer_pems) ~= "table" or #issuer_pems == 0 then
		return false, "no_issuer_candidates"
	end
	local matches = {}
	for _, iss in ipairs(issuer_pems) do
		if type(iss) == "string" and iss ~= "" then
			local subj = pem_dn_str(iss, "subject")
			if subj and subj == leaf_issuer then
				matches[#matches + 1] = iss
			end
		end
	end
	if #matches == 0 then
		return false, "issuer_mismatch"
	end

	-- Pre-filter issuers by SPKI to detect true duplicates early.
	-- Accept only when every DN match has a readable SPKI and they all agree.
	-- {A, nil} must not collapse to distinct_count==1 (cross-sign fail-open).
	local distinct_spki_count, _, unreadable = prefilter_issuers_by_spki(matches, leaf_issuer)

	if unreadable > 0 then
		return false, "issuer_spki_unreadable"
	end

	-- Optimization: If only 1 distinct SPKI, all issuers are identical, accept immediately.
	if distinct_spki_count == 1 then
		return true, nil
	end

	-- Multiple distinct SPKIs: ambiguous DN (different CAs, cross-signs, etc.)
	if distinct_spki_count > 1 then
		return false, "issuer_ambiguous"
	end

	-- No readable SPKI among DN matches (unreadable already handled above).
	return false, "issuer_spki_unreadable"
end

-- Fingerprint-only path has no handshake leaf PEM: require response CertID serial
-- to match the job-published pin (meta.certid.serial, else meta.serial).
-- When meta.certid is present, those bytes are the SingleResponse the job accepted
-- (exactly one CertID match among possibly several in the DER).
local function certid_consistent_with_meta(meta, ocsp_der)
	if type(meta) ~= "table" then
		return false, "no_meta"
	end
	local pin = meta.certid
	local meta_serial
	if type(pin) == "table" then
		meta_serial = canonical_serial_hex(pin.serial)
		if not meta_serial then
			return false, "certid_serial_unreadable"
		end
	else
		meta_serial = canonical_serial_hex(meta.serial)
	end
	if not meta_serial then
		return false, "serial_unreadable"
	end
	local resp_serial = ocsp_resp_serial_hex(ocsp_der, meta_serial)
	if resp_serial == meta_serial then
		return true, nil
	end
	if not ocsp_resp_serial_hex(ocsp_der) then
		return false, "serial_unreadable"
	end
	return false, "serial_mismatch"
end

-- All OCSP URIs from leaf AIA (authorityInfoAccess), normalized.
-- Profile is memoized once per PEM; returned list is a fresh copy (safe to mutate).
local function leaf_aia_ocsp_uris(cert_pem)
	local profile = pem_profile_get(cert_pem)
	local uris = profile and profile.aia_uris
	if type(uris) ~= "table" then
		return {}
	end
	local out = {}
	for i = 1, #uris do
		out[i] = uris[i]
	end
	return out
end

-- Published staple must name the leaf AIA OCSP URI the job fetched.
-- Returns true, or false, detail for refuse_must_staple / skip.
local function aia_uri_pin_ok(leaf_pem, meta, must_staple)
	if type(meta) ~= "table" then
		if must_staple then
			return false, "aia_uri_unpinned"
		end
		return true, nil
	end
	local pin = normalize_ocsp_aia_uri(meta.aia_ocsp_uri or meta.ocsp_url)
	if not pin then
		if must_staple then
			return false, "aia_uri_unpinned"
		end
		return true, nil
	end
	-- Must-Staple requires a live AIA re-check against the presented leaf.
	-- Fingerprint-only (no PEM) cannot do that — fail closed rather than trust the pin alone.
	if type(leaf_pem) ~= "string" or leaf_pem == "" then
		if must_staple then
			return false, "aia_uri_leaf_unavailable"
		end
		-- Optional staple: pin + ligand still bind the body when PEM is absent.
		return true, nil
	end
	local leaf_uris = leaf_aia_ocsp_uris(leaf_pem)
	if #leaf_uris == 0 then
		log(ngx.ERR, "OCSP leaf has no AIA OCSP URI; refusing staple pinned to " .. pin)
		return false, "aia_uri_missing_on_leaf"
	end
	for _, u in ipairs(leaf_uris) do
		if u == pin then
			return true, nil
		end
	end
	log(ngx.ERR, "OCSP AIA URI pin mismatch pin=" .. pin .. " leaf_aia_count=" .. tostring(#leaf_uris))
	return false, "aia_uri_mismatch"
end

function _M.aia_uri_pin_ok(leaf_pem, meta, must_staple)
	return aia_uri_pin_ok(leaf_pem, meta, must_staple)
end

-- Classify leaf PEM as "ec", "rsa", "ed", or nil (for dual-cert staple selection).
-- Profile is memoized once per PEM (single x509 pass for all facts).
local function cert_pubkey_kind(cert_pem)
	if type(cert_pem) ~= "string" or cert_pem == "" then
		return nil
	end
	local profile = pem_profile_get(cert_pem)
	return profile and profile.pubkey_kind or nil
end

-- kind + curve_nid for matching ClientHello signature_algorithms schemes.
-- Fresh table each call so callers cannot poison the PEM memo via field writes.
-- Profile is memoized once per PEM; this is a thin view of the cache entry.
local function cert_sig_profile(cert_pem)
	local profile = pem_profile_get(cert_pem)
	if type(profile) ~= "table" then
		return { kind = nil, curve_nid = nil }
	end
	return { kind = profile.pubkey_kind, curve_nid = profile.curve_nid }
end

-- True when this leaf can produce a CertificateVerify for the TLS SignatureScheme.
local function leaf_matches_scheme(profile, scheme)
	if type(profile) ~= "table" or type(scheme) ~= "number" then
		return false
	end
	-- ecdsa_secp256r1_sha256 / ecdsa_secp384r1_sha384 / ecdsa_secp521r1_sha512
	if scheme == 0x0403 then
		return profile.kind == "ec" and profile.curve_nid == NID_P256
	end
	if scheme == 0x0503 then
		return profile.kind == "ec" and profile.curve_nid == NID_P384
	end
	if scheme == 0x0603 then
		return profile.kind == "ec" and profile.curve_nid == NID_P521
	end
	-- ed25519 / ed448
	if scheme == 0x0807 then
		return profile.kind == "ed" and profile.curve_nid == NID_ED25519
	end
	if scheme == 0x0808 then
		return profile.kind == "ed" and profile.curve_nid == NID_ED448
	end
	-- rsa_pkcs1_* / rsa_pss_*
	if
		scheme == 0x0401
		or scheme == 0x0501
		or scheme == 0x0601
		or scheme == 0x0804
		or scheme == 0x0805
		or scheme == 0x0806
		or scheme == 0x0809
		or scheme == 0x080a
		or scheme == 0x080b
	then
		return profile.kind == "rsa"
	end
	return false
end

local function parse_pem_keys(pem_data)
	local keys = {}
	if type(pem_data) ~= "string" or pem_data == "" then
		return keys
	end
	local current_key = nil
	local in_key = false
	for line in pem_data:gmatch("[^\n]+") do
		if line:find("-----BEGIN", 1, true) and line:find("PRIVATE KEY", 1, true) then
			in_key = true
			current_key = line
		elseif in_key and current_key then
			current_key = current_key .. "\n" .. line
			if line:find("-----END", 1, true) and line:find("PRIVATE KEY", 1, true) then
				keys[#keys + 1] = current_key
				current_key = nil
				in_key = false
			end
		end
	end
	return keys
end

local function key_spki_fingerprint(key_pem)
	local fingerprint = nil
	pcall(function()
		local pkey = require("resty.openssl.pkey")
		local digest_lib = require("resty.openssl.digest")
		local key_obj = pkey.new(key_pem)
		if not key_obj then
			return
		end
		local pubkey_der = key_obj:tostring(false, "DER")
		if not pubkey_der then
			return
		end
		local digest_ctx = digest_lib.new("sha256")
		digest_ctx:update(pubkey_der)
		fingerprint = to_hex(digest_ctx:final())
	end)
	return fingerprint
end

local function cert_spki_fingerprint(cert_pem)
	return spki_fingerprint(cert_pem)
end

-- Subject / issuer DN strings for issuer-path linking (nil on parse failure).
local function cert_subject_issuer_dns(pem)
	return pem_names(pem)
end

_M.internal = {
	aia_uri_pin_ok = aia_uri_pin_ok,
	batch_spki_fingerprints = batch_spki_fingerprints,
	cert_pubkey_kind = cert_pubkey_kind,
	cert_sig_profile = cert_sig_profile,
	cert_spki_fingerprint = cert_spki_fingerprint,
	cert_subject_issuer_dns = cert_subject_issuer_dns,
	certid_consistent_with_meta = certid_consistent_with_meta,
	certid_matches_handshake_leaf = certid_matches_handshake_leaf,
	has_must_staple = has_must_staple,
	is_self_signed = is_self_signed,
	key_spki_fingerprint = key_spki_fingerprint,
	leaf_matches_scheme = leaf_matches_scheme,
	ocsp_resp_serial_hex = ocsp_resp_serial_hex,
	parse_pem_keys = parse_pem_keys,
	pem_blocks = pem_blocks,
	spki_fingerprint = spki_fingerprint,
	-- Pure helpers exported for unit tests (no disk / no ngx.ocsp).
	tls_feature_is_must_staple = tls_feature_is_must_staple,
	ocsp_der_serials = ocsp_der_serials,
	normalize_ocsp_aia_uri = normalize_ocsp_aia_uri,
	canonical_serial_hex = canonical_serial_hex,
}

return _M
