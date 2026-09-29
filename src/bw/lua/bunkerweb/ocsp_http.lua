local _M = {}
_M.__index = _M

-- Log levels used throughout ssl_certificate. Without these they were nil globals and
-- the first safe_log(DEBUG, ...) threw inside the conf's pcall (ngx.log needs a number).
local DEBUG, INFO, NOTICE, ERR = ngx.DEBUG, ngx.INFO, ngx.NOTICE, ngx.ERR

-- =====================================================================
-- MODULE-LEVEL: Load and cache all modules once at require time
-- =====================================================================

local _clogger
local ok_logger, err_logger = pcall(function()
	return require "bunkerweb.logger"
end)

if ok_logger then
	_clogger = err_logger
else
	ngx.log(
		ngx.ERR,
		"SSL-CERTIFICATE critical error: failed to load bunkerweb.logger: " .. tostring(err_logger):sub(1, 1024)
	)
	_clogger = nil
end

-- Logger factory for per-handshake instances
local function get_logger()
	if not _clogger then
		return nil
	end
	return _clogger:new("SSL-CERTIFICATE")
end

-- Safe require wrapper for modules
local function safe_require(name)
	local ok_mod, mod = pcall(require, name)
	return ok_mod and mod or nil
end

-- Cache all critical and optional modules at load time
local _class = safe_require "middleclass"
local _helpers = safe_require "bunkerweb.helpers"
local _utils = safe_require "bunkerweb.utils"
local _cdatastore = safe_require "bunkerweb.datastore"
local _cjson = safe_require "cjson"
local _ssl = safe_require "ngx.ssl"
local _ocsp = safe_require "ngx.ocsp"
local _resty_openssl_x509 = safe_require "resty.openssl.x509"
local _cwd = safe_require "bunkerweb.ocsp"

-- Allow-pin / ligand / epoch paths live in bunkerweb.ocsp
-- (/var/cache/bunkerweb/ssl/ocsp-allow|ocsp-ligand|...). Do not reintroduce
-- a parallel /data/bw/ocsp tree here — handshake gates go through _cwd.

-- =====================================================================
-- HANDSHAKE FUNCTION: ssl_certificate(state)
-- Uses module-level cached modules and helpers
-- =====================================================================

function _M.ssl_certificate(state)
	-- OCSP stapling logic for HTTP ssl_certificate phase.
	--
	-- Input: state table with install flags:
	--   state.abort_must_staple (bool|nil)
	--   state.abort_must_staple_detail (string|nil)
	--   state.certs_cleared (bool)
	--   state.leaf_installed (bool)
	--   state.leaf_complete (bool)
	--   state.leaf_must_staple (bool|nil)
	--
	-- State is modified in-place with results and error details.
	-- Uses module-level cached modules via local aliases for compatibility

	-- Conf passes this table; write flags here so the outer abort / cleared_no_leaf
	-- net (ssl-certificate-by-lua.conf) can see clear_certs / Must-Staple decisions.
	-- Bare locals were extraction leftovers and became worker globals instead.
	if type(state) ~= "table" then
		state = {}
	end
	if state.abort_must_staple == nil then
		state.abort_must_staple = false
	end
	if state.certs_cleared == nil then
		state.certs_cleared = false
	end
	if state.leaf_installed == nil then
		state.leaf_installed = false
	end
	if state.leaf_complete == nil then
		state.leaf_complete = false
	end
	-- state.abort_must_staple_detail and state.leaf_must_staple stay nil until set.

	-- Per-handshake logger instance
	local logger = get_logger()

	local function safe_log(level, msg)
		if logger and msg then
			logger:log(level, tostring(msg):sub(1, 2048))
		end
	end

	-- Validate critical modules
	if not _ssl then
		safe_log(ngx.ERR, "Critical module ngx.ssl not available")
		return
	end

	if not _helpers then
		safe_log(ngx.ERR, "Critical module bunkerweb.helpers not available")
		return
	end

	if not _cdatastore then
		safe_log(ngx.ERR, "Critical module bunkerweb.datastore not available")
		return
	end

	-- Create local aliases to module-level cached modules (for compatibility with business logic)
	local class = _class
	local helpers = _helpers
	local utils = _utils
	local cdatastore = _cdatastore
	local cjson = _cjson
	local ssl = _ssl
	local ocsp = _ocsp
	local resty_openssl_x509 = _resty_openssl_x509
	local cwd = _cwd

	safe_log(ngx.DEBUG, "bunkerweb.logger loaded successfully")
	safe_log(ngx.DEBUG, "All critical modules available")

	-- 4. Debug toggle (set DEBUG_SSL_CERTIFICATE=yes environment variable to enable)
	local debug_ssl = os.getenv("DEBUG_SSL_CERTIFICATE") == "yes"
	if debug_ssl then
		safe_log(ngx.NOTICE, "DEBUG_SSL_CERTIFICATE enabled - verbose logging active")
	end

	-- =====================================================================
	-- SECTION: Per-handshake variable initialization
	-- Initialize variables needed by business logic
	-- =====================================================================

	-- Optional modules and flags
	local disable_resty_openssl = os.getenv("BW_DISABLE_RESTY_OPENSSL") == "yes"
	local resty_x509 = nil
	if not disable_resty_openssl then
		resty_x509 = resty_openssl_x509
	else
		safe_log(ngx.DEBUG, "RESTY.OPENSSL DISABLED: resty.openssl.x509 is disabled")
	end
	local has_resty_ssl = (resty_x509 ~= nil) and not disable_resty_openssl

	-- SSL methods
	local clear_certs = ssl and ssl.clear_certs
	local set_cert = ssl and ssl.set_cert
	local set_priv_key = ssl and ssl.set_priv_key
	local require_plugin = helpers and helpers.require_plugin
	local new_plugin = helpers and helpers.new_plugin
	local call_plugin = helpers and helpers.call_plugin

	-- Datastore and phase order initialization
	local internalstore = cdatastore and cdatastore:new(ngx.shared.internalstore)
	if not internalstore then
		safe_log(ngx.ERR, "Failed to initialize internalstore")
		return
	end

	-- Get plugins order
	local order, order_err = internalstore:get("plugins_order", true)
	if not order then
		safe_log(ngx.ERR, "cannot get plugins order from internalstore : " .. (order_err or "unknown"))
		return
	end

	-- Resolve per-site plugin order
	local function get_phase_order(ord, phase, sni)
		if ord.per_site and sni and ord.per_site[sni] and ord.per_site[sni][phase] then
			return ord.per_site[sni][phase]
		elseif ord.global and ord.global[phase] then
			return ord.global[phase]
		end
		return ord[phase]
	end

	local server_name = ssl and ssl.server_name()
	local phase_order = get_phase_order(order, "ssl_certificate", server_name)

	safe_log(ngx.DEBUG, "ssl_certificate phase started for server_name=" .. (server_name or "nil"))

	-- =====================================================================
	-- SECTION: Business logic begins here (from original extracted body)
	-- =====================================================================

	-- SECTION: stapling-off fast path (SSL_USE_OCSP_STAPLING=no, the default)
	-- Upstream plugin loop: the first plugin returning parsed ngx.ssl objects
	-- installs cert + key. Runs before the OCSP helpers below are built, so
	-- sites without stapling pay no OCSP cost and never hit Must-Staple aborts.
	-- Plugins returning PEM strings need cert/key pairing from the full path;
	-- they fall through to it (earlier plugins are then called a second time).
	-- If bunkerweb.ocsp cannot load, stapling_on stays true and the full path's
	-- degraded-module handling decides.
	-- =====================================================================
	local stapling_on = true
	pcall(function()
		local ocsp_mod = require "bunkerweb.ocsp"
		if ocsp_mod.stapling_enabled then
			stapling_on = ocsp_mod.stapling_enabled(internalstore, server_name) == true
		end
	end)
	if not stapling_on then
		local needs_full_path = false
		for _, plugin_id in ipairs(phase_order) do
			local plugin_lua, plugin_err = require_plugin(plugin_id)
			if plugin_lua == false then
				safe_log(ngx.ERR, plugin_err)
			elseif plugin_lua == nil then
				safe_log(ngx.DEBUG, plugin_err)
			elseif plugin_lua.ssl_certificate ~= nil then
				local ok_p, plugin_obj = new_plugin(plugin_lua)
				if not ok_p then
					safe_log(ngx.ERR, plugin_obj)
				else
					local ok_c, ret = call_plugin(plugin_obj, "ssl_certificate")
					if not ok_c then
						safe_log(ngx.ERR, ret)
					elseif not ret.ret then
						safe_log(ngx.ERR, plugin_id .. ":ssl_certificate() call failed : " .. tostring(ret.msg))
					elseif ret.status then
						if type(ret.status[1]) == "string" or type(ret.status[2]) == "string" then
							needs_full_path = true
							break
						end
						local ok_clear, clear_err = clear_certs()
						if not ok_clear then
							safe_log(ngx.ERR, "error while clearing certificates : " .. tostring(clear_err))
						else
							-- Stapling-off still clears the SSL ctx; update state so a
							-- failed set_cert cannot fall through to nginx's static leaf.
							-- leaf_must_staple stays nil until install succeeds so
							-- cleared_no_leaf (~= false) aborts a wipe without a leaf.
							state.certs_cleared = true
							state.leaf_installed = false
							state.leaf_complete = false
							state.leaf_must_staple = nil
						end
						local ok_cert, cert_err = set_cert(ret.status[1])
						if not ok_cert then
							safe_log(ngx.ERR, "error while setting certificate : " .. tostring(cert_err))
						else
							local ok_key, key_err = set_priv_key(ret.status[2])
							if not ok_key then
								safe_log(ngx.ERR, "error while setting private key : " .. tostring(key_err))
							else
								state.leaf_installed = true
								state.leaf_complete = true
								state.leaf_must_staple = false
								safe_log(ngx.DEBUG, "certificate set by " .. plugin_id .. " (OCSP stapling off)")
								return true
							end
						end
					end
				end
			end
		end
		if not needs_full_path then
			return true
		end
	end

	-- =====================================================================
	-- OPTIMIZATION: Per-worker OCSP validation result cache (Priority 1)
	-- Cache validation results by (cert_fp, ocsp_resp_binding) with TTL
	-- Prevents redundant crypto operations (FFI RSA/ECDSA verify) per handshake
	-- Estimated savings: 1-3ms per cached validation
	-- =====================================================================
	local ocsp_validation_cache = {}
	local ocsp_validation_cache_max_entries = 256
	local ocsp_validation_cache_ttl = 60
	local ocsp_validation_cache_access_order = {}

	local function ocsp_validation_cache_key(cert_fp, resp_binding)
		if not cert_fp or not resp_binding then
			return nil
		end
		return cert_fp .. "|" .. resp_binding
	end

	local function ocsp_validation_cache_get(cert_fp, resp_binding)
		local key = ocsp_validation_cache_key(cert_fp, resp_binding)
		if not key then
			return nil
		end
		local cached = ocsp_validation_cache[key]
		if cached and cached.expires and cached.expires > ngx.time() then
			table.insert(ocsp_validation_cache_access_order, key)
			return cached.result
		end
		if cached then
			ocsp_validation_cache[key] = nil
		end
		return nil
	end

	local function ocsp_validation_cache_set(cert_fp, resp_binding, result)
		local key = ocsp_validation_cache_key(cert_fp, resp_binding)
		if not key then
			return
		end
		local expires = ngx.time() + ocsp_validation_cache_ttl
		ocsp_validation_cache[key] = { result = result, expires = expires }
		table.insert(ocsp_validation_cache_access_order, key)

		if #ocsp_validation_cache > ocsp_validation_cache_max_entries then
			local evict_key = table.remove(ocsp_validation_cache_access_order, 1)
			if evict_key then
				ocsp_validation_cache[evict_key] = nil
			end
		end
	end

	-- =====================================================================
	-- OPTIMIZATION: Per-worker certificate metadata cache (Priority 2)
	-- Cache fingerprint, serial number, and key kind by certificate PEM
	-- Prevents redundant FFI parsing on cert reuse (same cert across handshakes)
	-- Estimated savings: 1-2ms per cached cert metadata
	-- =====================================================================
	local cert_metadata_cache = {}
	local cert_metadata_cache_max_entries = 512
	local cert_metadata_cache_ttl = 300
	local cert_metadata_cache_access_order = {}

	local function cert_metadata_cache_key(cert_pem)
		if not cert_pem or type(cert_pem) ~= "string" or #cert_pem == 0 then
			return nil
		end
		local ok, digest = pcall(function()
			local digest_lib = require("resty.openssl.digest")
			local ctx = digest_lib.new("sha256")
			ctx:update(cert_pem)
			return ocsp_to_hex(ctx:final())
		end)
		if ok and type(digest) == "string" and #digest == 64 then
			return digest
		end
		return nil
	end

	local function cert_metadata_cache_get(cert_pem)
		local key = cert_metadata_cache_key(cert_pem)
		if not key then
			return nil
		end
		local cached = cert_metadata_cache[key]
		if cached and cached.expires and cached.expires > ngx.time() then
			table.insert(cert_metadata_cache_access_order, key)
			return cached
		end
		if cached then
			cert_metadata_cache[key] = nil
		end
		return nil
	end

	local function cert_metadata_cache_set(cert_pem, metadata)
		local key = cert_metadata_cache_key(cert_pem)
		if not key or not metadata then
			return
		end
		local expires = ngx.time() + cert_metadata_cache_ttl
		cert_metadata_cache[key] = {
			fingerprint = metadata.fingerprint,
			serial = metadata.serial,
			kind = metadata.kind,
			issuer_name = metadata.issuer_name,  -- OPTIMIZATION: Cache issuer DN (Priority 10)
			expires = expires,
		}
		table.insert(cert_metadata_cache_access_order, key)

		if #cert_metadata_cache > cert_metadata_cache_max_entries then
			local evict_key = table.remove(cert_metadata_cache_access_order, 1)
			if evict_key then
				cert_metadata_cache[evict_key] = nil
			end
		end
	end

	-- =====================================================================
	-- OPTIMIZATION: Per-worker Must-Staple detection cache (Priority 3)
	-- Cache Must-Staple flag by certificate fingerprint
	-- Prevents repeated ocsp.json reads and TLS Feature parsing
	-- Estimated savings: 1-2ms per cached Must-Staple detection
	-- =====================================================================
	local must_staple_cache = {}
	local must_staple_cache_max_entries = 256
	local must_staple_cache_ttl = 300
	local must_staple_cache_access_order = {}

	local function must_staple_cache_key(cert_fp)
		if not cert_fp or type(cert_fp) ~= "string" or #cert_fp ~= 64 then
			return nil
		end
		return cert_fp:lower()
	end

	local function must_staple_cache_get(cert_fp)
		local key = must_staple_cache_key(cert_fp)
		if not key then
			return nil
		end
		local cached = must_staple_cache[key]
		if cached and cached.expires and cached.expires > ngx.time() then
			table.insert(must_staple_cache_access_order, key)
			return cached.result
		end
		if cached then
			must_staple_cache[key] = nil
		end
		return nil
	end

	local function must_staple_cache_set(cert_fp, result)
		local key = must_staple_cache_key(cert_fp)
		if not key then
			return
		end
		local expires = ngx.time() + must_staple_cache_ttl
		must_staple_cache[key] = { result = result, expires = expires }
		table.insert(must_staple_cache_access_order, key)

		if #must_staple_cache > must_staple_cache_max_entries then
			local evict_key = table.remove(must_staple_cache_access_order, 1)
			if evict_key then
				must_staple_cache[evict_key] = nil
			end
		end
	end

	-- =====================================================================
	-- OPTIMIZATION: Per-worker stored issuer PEM cache (Priority 8)
	-- Cache issuer.pem files read from disk by certificate fingerprint
	-- Prevents repeated file I/O on identical cert validations
	-- Estimated savings: 0.2-1.0ms per validation (30-40% of handshakes)
	-- =====================================================================
	local stored_issuer_cache = {}
	local stored_issuer_cache_max_entries = 256
	local stored_issuer_cache_ttl = 600
	local stored_issuer_cache_access_order = {}

	local function stored_issuer_cache_key(cert_fp)
		if not cert_fp or type(cert_fp) ~= "string" or #cert_fp ~= 64 then
			return nil
		end
		return "issuer:" .. cert_fp:lower()
	end

	local function stored_issuer_cache_get(cert_fp)
		local key = stored_issuer_cache_key(cert_fp)
		if not key then
			return nil
		end
		local cached = stored_issuer_cache[key]
		if cached and cached.expires and cached.expires > ngx.time() then
			table.insert(stored_issuer_cache_access_order, key)
			-- Return cached value: nil means file didn't exist, string means PEM data
			return cached.pem
		end
		if cached then
			stored_issuer_cache[key] = nil
		end
		return nil
	end

	local function stored_issuer_cache_set(cert_fp, pem_or_nil)
		local key = stored_issuer_cache_key(cert_fp)
		if not key then
			return
		end
		local expires = ngx.time() + stored_issuer_cache_ttl
		-- Cache both successful reads (PEM) and misses (nil)
		stored_issuer_cache[key] = {
			pem = pem_or_nil,
			expires = expires,
		}
		table.insert(stored_issuer_cache_access_order, key)

		if #stored_issuer_cache > stored_issuer_cache_max_entries then
			local evict_key = table.remove(stored_issuer_cache_access_order, 1)
			if evict_key then
				stored_issuer_cache[evict_key] = nil
			end
		end
	end

-- =====================================================================
	-- OPTIMIZATION: Per-worker chain mapping cache (Priority 7)
	-- Cache chain subject-to-PEM maps and issuer subjects by chain hash
	-- Prevents repeated FFI x509 parsing on identical cert chains
	-- Estimated savings: 0.5-1.0ms per static chain (50-70% of handshakes)
	-- =====================================================================
	local chain_mapping_cache = {}
	local chain_mapping_cache_max_entries = 128
	local chain_mapping_cache_ttl = 600
	local chain_mapping_cache_access_order = {}

	local function chain_mapping_cache_key(chain_certs)
		if not chain_certs or type(chain_certs) ~= "table" or #chain_certs == 0 then
			return nil
		end
		-- Hash the concatenated PEM blocks to detect identical chains
		local chain_str = table.concat(chain_certs, "\n---\n")
		local ok, digest = pcall(function()
			local digest_lib = require("resty.openssl.digest")
			local ctx = digest_lib.new("sha256")
			ctx:update(chain_str)
			return ocsp_to_hex(ctx:final())
		end)
		if ok and type(digest) == "string" and #digest == 64 then
			return digest
		end
		return nil
	end

	local function chain_mapping_cache_get(chain_certs)
		local key = chain_mapping_cache_key(chain_certs)
		if not key then
			return nil
		end
		local cached = chain_mapping_cache[key]
		if cached and cached.expires and cached.expires > ngx.time() then
			table.insert(chain_mapping_cache_access_order, key)
			return cached.subject_to_pem, cached.issuer_subjects
		end
		if cached then
			chain_mapping_cache[key] = nil
		end
		return nil
	end

	local function chain_mapping_cache_set(chain_certs, subject_to_pem, issuer_subjects)
		local key = chain_mapping_cache_key(chain_certs)
		if not key then
			return
		end
		local expires = ngx.time() + chain_mapping_cache_ttl
		chain_mapping_cache[key] = {
			subject_to_pem = subject_to_pem,
			issuer_subjects = issuer_subjects,
			expires = expires,
		}
		table.insert(chain_mapping_cache_access_order, key)

		if #chain_mapping_cache > chain_mapping_cache_max_entries then
			local evict_key = table.remove(chain_mapping_cache_access_order, 1)
			if evict_key then
				chain_mapping_cache[evict_key] = nil
			end
		end
	end

local tostring = tostring
	local insert = table.insert
	local lower = string.lower
	-- Convert binary data to lowercase hex (replacement for ngx.encode_base16)
	local function to_hex(bin)
		if not bin then
			return nil
		end
		local t = {}
		for i = 1, #bin do
			t[i] = string.format("%02x", string.byte(bin, i))
		end
		return table.concat(t)
	end
	local match = string.match
	local concat = table.concat

	-- Lua pattern note: `string.match()` uses Lua patterns, not regex.
	-- So we validate fingerprints with length + allowed-characters checks.
	local function is_fp64_lower_hex(fp)
		return type(fp) == "string" and #fp == 64 and fp:match("^[0-9a-f]+$") ~= nil
	end

	-- Bind "already verified" to the OCSP DER bytes, not only the SPKI fingerprint.
	-- Same-key renewals keep the fingerprint; a bare true would skip re-validation of a new serial.
	local function ocsp_to_hex(bin)
		if type(bin) ~= "string" then
			return nil
		end
		local hex = {}
		for i = 1, #bin do
			hex[i] = string.format("%02x", string.byte(bin, i))
		end
		return table.concat(hex)
	end

	-- =====================================================================
	-- SECTION: OCSP L1 (HTTP internalstore) — bw2 blob mirrors stream ocsp.lua
	-- Key: TLS:SSL:ocsp:{fp64}. Pack: magic|epoch|der_sha256|expires|DER.
	-- Epoch file couples HTTP↔stream when shm zones cannot cross-delete.
	-- =====================================================================
	-- Bind verified L1 flag to sha256(OCSP DER), not SPKI alone (same-key renewals).
	local function ocsp_resp_binding(resp)
		if type(resp) ~= "string" or #resp == 0 then
			return nil
		end
		local ok, digest = pcall(function()
			local digest_lib = require("resty.openssl.digest")
			local ctx = digest_lib.new("sha256")
			ctx:update(resp)
			return ocsp_to_hex(ctx:final())
		end)
		if ok and type(digest) == "string" and #digest == 64 then
			return digest
		end
		return nil
	end

	-- True when stored L1 binding still equals sha256(resp) AND soft_recall_gen matches.
	-- Missing gen (legacy bw2) or gen mismatch after soft-recall → not crypto-trusted.
	local function ocsp_verified_for_resp(stored, resp, stored_gen, live_gen)
		local binding = ocsp_resp_binding(resp)
		if binding == nil or stored ~= binding then
			return false
		end
		if type(stored_gen) ~= "number" or type(live_gen) ~= "number" then
			return false
		end
		return stored_gen == live_gen
	end

	-- Live soft_recall_gen from outside ligand (upgrade-grace 0 when key absent).
	local function ocsp_live_soft_recall_gen(cert_fp)
		if type(cert_fp) ~= "string" or #cert_fp ~= 64 then
			return nil
		end
		local gen = nil
		pcall(function()
			local f = io.open("/var/cache/bunkerweb/ssl/ocsp-ligand/" .. cert_fp, "r")
			if not f then
				gen = 0
				return
			end
			local raw = f:read("*a")
			f:close()
			local ok, obj = pcall(require("cjson").decode, raw)
			if not ok or type(obj) ~= "table" then
				return
			end
			local raw_g = obj.soft_recall_gen
			if raw_g == nil then
				gen = 0
			elseif type(raw_g) == "number" and raw_g == raw_g and raw_g >= 0 and raw_g ~= math.huge then
				gen = math.floor(raw_g)
			elseif type(raw_g) == "string" and raw_g:match("^%d+$") then
				gen = tonumber(raw_g)
			end
		end)
		return gen
	end

	-- Composite L1: epoch + verified binding + soft_recall_gen + expires + DER.
	-- Layout matches store bw3 (legacy bw2 still unpacks with gen=nil).
	-- Epoch file is the coherence bus with stream (separate lua_shared_dict; no cross-delete).
	-- Always re-read: a mid-handshake bump must not be masked by an ngx.ctx pin.
	local OCSP_EPOCH_PATH = "/var/cache/bunkerweb/ssl/.ocsp_epoch"
	local function ocsp_l1_cache_key(fingerprint)
		return "TLS:SSL:ocsp:" .. tostring(fingerprint)
	end
	-- Read .ocsp_epoch — shared coherence bus with stream L1 (separate shm zones).
	-- Prefer bunkerweb.ocsp.current_ocsp_epoch (single tokenizer). Fallback below
	-- matches that same first-line ^%S+ rule if require fails mid-handshake.
	local function ocsp_current_epoch()
		local ok_mod, ocsp_mod = pcall(require, "bunkerweb.ocsp")
		if ok_mod and ocsp_mod and ocsp_mod.current_ocsp_epoch then
			return ocsp_mod.current_ocsp_epoch() or "0"
		end
		local epoch = "0"
		pcall(function()
			local f = io.open(OCSP_EPOCH_PATH, "r")
			if not f then
				return
			end
			local raw = f:read("*l")
			f:close()
			if type(raw) == "string" and #raw > 0 then
				epoch = raw:match("^%S+") or "0"
			end
		end)
		return epoch
	end
	-- Pack bw3 L1: epoch | verified binding | soft_recall_gen | expires | DER (matches store).
	-- Legacy bw2 still unpacks (gen=nil → verified trust fails closed).
	local OCSP_L1_MAGIC = "bw3\0"
	local OCSP_L1_MAGIC_V2 = "bw2\0"
	local function ocsp_l1_pack(epoch, verified_binding, der, expires_unix, soft_recall_gen)
		local exp = ""
		if type(expires_unix) == "number" and expires_unix > 0 then
			exp = tostring(math.floor(expires_unix))
		elseif type(expires_unix) == "string" and expires_unix:match("^%d+$") then
			exp = expires_unix
		end
		local gen = ""
		if type(soft_recall_gen) == "number" and soft_recall_gen >= 0 then
			gen = tostring(math.floor(soft_recall_gen))
		end
		return OCSP_L1_MAGIC
			.. (epoch or "0")
			.. "\0"
			.. (verified_binding or "")
			.. "\0"
			.. gen
			.. "\0"
			.. exp
			.. "\0"
			.. der
	end
	-- Declared clock-skew budget. Must match ocsp-refresh.py / ocsp.lua.
	-- Death time = expires_unix/max_age minus skew.
	local OCSP_CLOCK_SKEW_SECONDS = 300
	-- Signed-window policy; must match ocsp-refresh.py / ocsp.lua.
	local OCSP_MAX_INTRINSIC_LIFETIME_SECONDS = 7 * 24 * 3600
	local OCSP_MAX_THIS_UPDATE_AGE_SECONDS = 7 * 24 * 3600
	-- Cap DRAM residence; never longer than remaining OCSP life when known.
	-- Returns TTL seconds, or nil when the body is already past death (do not park).
	local L1_MAX_TTL = 300
	local function ocsp_l1_shm_ttl(expires_unix)
		-- Never park an undated body in L1 (would outlive stripped meta).
		if type(expires_unix) ~= "number" or expires_unix <= 0 then
			return nil
		end
		local remaining = expires_unix - OCSP_CLOCK_SKEW_SECONDS - ngx.time()
		if remaining <= 0 then
			return nil
		end
		if remaining > L1_MAX_TTL then
			return L1_MAX_TTL
		end
		return remaining
	end
	-- Unpack bw3 (preferred) or legacy bw2 → epoch, binding, der, expires, gen.
	local function ocsp_l1_unpack(blob)
		if type(blob) ~= "string" or #blob < 4 then
			return nil, nil, nil, nil, nil
		end
		local magic = blob:sub(1, 4)
		if magic == OCSP_L1_MAGIC then
			local epoch, binding, gen_s, exp, der = blob:sub(5):match("^([^\0]*)\0([^\0]*)\0([^\0]*)\0([^\0]*)\0(.*)$")
			if type(der) ~= "string" or #der == 0 then
				return nil, nil, nil, nil, nil
			end
			if binding == "" then
				binding = nil
			end
			local expires_unix = nil
			if type(exp) == "string" and exp:match("^%d+$") then
				expires_unix = tonumber(exp)
			end
			local gen = nil
			if type(gen_s) == "string" and gen_s:match("^%d+$") then
				gen = tonumber(gen_s)
			end
			return epoch or "0", binding, der, expires_unix, gen
		end
		if magic == OCSP_L1_MAGIC_V2 then
			local epoch, binding, exp, der = blob:sub(5):match("^([^\0]*)\0([^\0]*)\0([^\0]*)\0(.*)$")
			if type(der) ~= "string" or #der == 0 then
				return nil, nil, nil, nil, nil
			end
			if binding == "" then
				binding = nil
			end
			local expires_unix = nil
			if type(exp) == "string" and exp:match("^%d+$") then
				expires_unix = tonumber(exp)
			end
			return epoch or "0", binding, der, expires_unix, nil
		end
		return nil, nil, nil, nil, nil
	end
	-- Returns der, verified_binding, epoch, expires_unix, soft_recall_gen from HTTP L1.
	local function ocsp_l1_get(fingerprint)
		if not internalstore or not fingerprint then
			return nil
		end
		local ok, blob = pcall(function()
			return internalstore:get(ocsp_l1_cache_key(fingerprint))
		end)
		if not ok or type(blob) ~= "string" or #blob == 0 then
			return nil
		end
		local epoch, verified, der, expires_unix, gen = ocsp_l1_unpack(blob)
		if der then
			return der, verified, epoch, expires_unix, gen
		end
		return nil
	end
	-- Write DER into HTTP L1 (bw3 composite).
	-- packed_epoch: when re-parking a body that already passed l1_matches_disk,
	-- pass the epoch from that get — never stamp "now's" epoch over an old body
	-- (that would make a stale DER look current until the next ligand check).
	-- Callers in probe_only should skip this entirely (losing leaves must not warm L1).
	-- verified_binding nil = cache for reuse but do not skip crypto on later hits.
	-- soft_recall_gen parks generation identity (required for verified trust).
	local function ocsp_l1_put(fingerprint, der, verified_binding, expires_unix, packed_epoch, soft_recall_gen)
		if not internalstore or not fingerprint or type(der) ~= "string" or #der == 0 then
			return false
		end
		local ttl = ocsp_l1_shm_ttl(expires_unix)
		if not ttl then
			-- Already past nextUpdate; do not park an expired body in L1.
			return false
		end
		local epoch = packed_epoch
		if type(epoch) ~= "string" or #epoch == 0 then
			epoch = ocsp_current_epoch()
		end
		-- Verified without a concrete gen cannot survive soft-recall — demote.
		if verified_binding and type(soft_recall_gen) ~= "number" then
			verified_binding = nil
		end
		local ok = false
		pcall(function()
			ok = internalstore:set(
				ocsp_l1_cache_key(fingerprint),
				ocsp_l1_pack(epoch, verified_binding, der, expires_unix, soft_recall_gen),
				ttl
			)
			internalstore:delete(ocsp_l1_cache_key(fingerprint), true)
		end)
		return ok == true
	end
	-- Drop HTTP L1 + validate-failed poison for this SPKI (epoch mismatch / refuse).
	local function ocsp_l1_drop(fingerprint, ocsp_path)
		pcall(function()
			if fingerprint then
				internalstore:delete(ocsp_l1_cache_key(fingerprint))
				internalstore:delete("TLS:SSL:ocsp_validate_failed:" .. fingerprint)
				internalstore:delete(ocsp_l1_cache_key(fingerprint), true)
				internalstore:delete("TLS:SSL:ocsp_validate_failed:" .. fingerprint, true)
			end
		end)
	end

	-- True when this L1 body still matches disk ligand/meta der_sha256 + .ocsp_epoch.
	-- Delegates to bunkerweb.ocsp.l1_body_matches_disk (same rules as stream) so HTTP
	-- cannot keep a body stream would refuse after a ligand swap / publish gap.
	local function ocsp_l1_matches_disk(fingerprint, ocsp_dir, ocsp_path, resp, stored_epoch)
		local ok_mod, ocsp_mod = pcall(require, "bunkerweb.ocsp")
		if not ok_mod or not ocsp_mod or not ocsp_mod.l1_body_matches_disk then
			return false
		end
		return ocsp_mod.l1_body_matches_disk(fingerprint, resp, stored_epoch)
	end

	-- =====================================================================
	-- SECTION: PEM parse / SPKI fingerprint / cert↔key pairing
	-- Handshake path is resty.openssl only (never shell out). SPKI fp names
	-- the shard directory. Do not pass ngx.ssl cdata into resty (segfault).
	-- =====================================================================
	-- Helper: parse multiple PEM certificates from a single string
	-- Returns array of individual PEM certificate strings
	local function parse_pem_certificates(pem_data)
		if not pem_data or #pem_data == 0 then
			return {}
		end

		local certs = {}
		local current_cert = nil

		for line in pem_data:gmatch("[^\n]+") do
			if current_cert then
				current_cert = current_cert .. "\n" .. line
			end

			if line:find("-----BEGIN CERTIFICATE-----", 1, true) then
				current_cert = line
			elseif line:find("-----END CERTIFICATE-----", 1, true) then
				if current_cert then
					insert(certs, current_cert)
					current_cert = nil
				end
			end
		end

		return certs
	end

	-- Helper: parse multiple PEM private keys from a single string
	-- Returns array of individual PEM key strings
	-- Matches RSA, EC, EdDSA, and other key types
	local function parse_pem_keys(pem_data)
		if not pem_data or #pem_data == 0 then
			return {}
		end

		local keys = {}
		local current_key = nil
		local in_key = false

		for line in pem_data:gmatch("[^\n]+") do
			if line:find("-----BEGIN", 1, true) and line:find("PRIVATE KEY", 1, true) then
				in_key = true
				current_key = line
			elseif in_key and current_key then
				current_key = current_key .. "\n" .. line
				if line:find("-----END", 1, true) and line:find("PRIVATE KEY", 1, true) then
					insert(keys, current_key)
					current_key = nil
					in_key = false
				end
			end
		end

		return keys
	end

	-- Helper: extract certificate serial number for identification (normalized to uppercase)
	-- Handshake path: resty.openssl only — never write PEM to /tmp or shell out to openssl.
	local function get_cert_identifier(cert_pem)
		if not cert_pem or #cert_pem == 0 then
			return nil
		end

		-- OPTIMIZATION: Check metadata cache for serial number
		local cached = cert_metadata_cache_get(cert_pem)
		if cached and cached.serial then
			safe_log(DEBUG, "OCSP cert serial cache hit")
			return cached.serial
		end

		if not has_resty_ssl then
			safe_log(
				DEBUG,
				"OCSP get_cert_identifier: resty.openssl unavailable; no CLI fallback server_name="
					.. (server_name or "nil")
			)
			return nil
		end

		local rest_err = nil
		local ok_id, rest_identifier = pcall(function()
			local cert, err = resty_x509.new(cert_pem)
			rest_err = err
			if cert then
				local serial = cert:get_serial_number()
				if serial then
					return tostring(serial):upper()
				end
			end
			return nil
		end)

		if ok_id and rest_identifier then
			-- OPTIMIZATION: Cache the serial number for future reuse
			cert_metadata_cache_set(cert_pem, { serial = rest_identifier })
			return rest_identifier
		end
		if rest_err then
			safe_log(DEBUG, "OCSP get_cert_identifier resty.openssl error: " .. tostring(rest_err))
		end
		return nil
	end

	-- Helper: extract public key fingerprint (SHA256) from certificate or private key PEM string
	-- Uses native lua-resty-openssl only (no /tmp + openssl CLI on the handshake path).
	-- IMPORTANT: Only accepts PEM/DER strings. Do NOT pass cdata pointers from ngx.ssl.parse_pem_cert()
	-- as they are STACK_OF(X509)* — casting to X509* and calling resty.openssl causes a C-level segfault.
	local function get_pubkey_fingerprint(cert_data, is_key)
		if not cert_data then
			return nil
		end
		if type(cert_data) ~= "string" then
			safe_log(
				DEBUG,
				"OCSP get_pubkey_fingerprint: rejecting non-string input (type="
					.. type(cert_data)
					.. ") to prevent segfault"
			)
			return nil
		end
		if #cert_data == 0 then
			return nil
		end

		-- OPTIMIZATION: Check metadata cache before FFI parsing (cert certificates only)
		-- Skip cache for private keys (is_key=true) since they're rarely reused
		if not is_key then
			local cached = cert_metadata_cache_get(cert_data)
			if cached and cached.fingerprint then
				safe_log(DEBUG, "OCSP cert fingerprint cache hit")
				return cached.fingerprint
			end
		end

		local fingerprint = nil
		local ok_rest, rest_err = pcall(function()
			local x509 = require("resty.openssl.x509")
			local pkey = require("resty.openssl.pkey")
			local digest_lib = require("resty.openssl.digest")

			if is_key then
				-- Load as private key (auto-detects PEM/DER)
				local key_obj = pkey.new(cert_data)
				if not key_obj then
					safe_log(DEBUG, "OCSP failed to load private key for fingerprinting")
					return
				end
				-- Export public key to DER format
				local pubkey_der, err = key_obj:tostring(false, "DER") -- false = public key only
				if not pubkey_der then
					safe_log(DEBUG, "OCSP failed to export public key to DER: " .. (err or "unknown"))
					return
				end
				-- Compute SHA256 of the public key DER
				local digest_ctx = digest_lib.new("sha256")
				if digest_ctx then
					digest_ctx:update(pubkey_der)
					fingerprint = to_hex(digest_ctx:final()):lower()
				end
			else
				-- Load as certificate (auto-detects PEM/DER)
				local cert_obj = x509.new(cert_data)
				if not cert_obj then
					safe_log(DEBUG, "OCSP failed to load certificate for fingerprinting")
					return
				end

				-- Compute SHA256 of public key SubjectPublicKeyInfo DER (matches ocsp-refresh.py).
				-- Do not fall back to cert_obj:pubkey_digest() — that OpenSSL helper has produced
				-- digests that diverge from SPKI SHA-256 and would miss the job cache path.
				local digest_ctx = digest_lib.new("sha256")
				if digest_ctx then
					local pub = nil
					local ok_pub, pub_err = pcall(function()
						-- resty.openssl.x509 exposes get_pubkey(), which returns a pkey object.
						pub = cert_obj:get_pubkey()
					end)
					if not ok_pub then
						safe_log(DEBUG, "OCSP export pubkey: cert_obj:get_pubkey() failed: " .. tostring(pub_err))
					end
					if pub then
						local pubkey_der, err = pub:tostring("public", "DER")
						if pubkey_der then
							safe_log(DEBUG, "OCSP export pubkey SPKI DER ok (len=" .. tostring(#pubkey_der) .. ")")
							digest_ctx:update(pubkey_der)
							fingerprint = to_hex(digest_ctx:final()):lower()
						else
							safe_log(DEBUG, "OCSP failed to export cert pubkey SPKI DER: " .. (err or "unknown"))
						end
					else
						safe_log(DEBUG, "OCSP export pubkey: cert_obj:get_pubkey() returned nil")
					end
				end
			end
		end)
		if not ok_rest then
			safe_log(DEBUG, "OCSP get_pubkey_fingerprint resty.openssl error: " .. tostring(rest_err))
		elseif not fingerprint then
			safe_log(
				DEBUG,
				"OCSP get_pubkey_fingerprint: resty.openssl unavailable or failed; no CLI fallback server_name="
					.. (server_name or "nil")
			)
		end

		-- OPTIMIZATION: Cache successful fingerprint extraction
		-- Only cache for certificates (not keys) since keys are rarely reused
		if fingerprint and not is_key then
			cert_metadata_cache_set(cert_data, { fingerprint = fingerprint })
		end

		return fingerprint
	end

	-- OCSP cache directories are named by the SHA256 of SubjectPublicKeyInfo DER.
	-- get_pubkey_fingerprint already computes that hash.
	local function get_ocsp_pubkey_fingerprint(cert_pem)
		return get_pubkey_fingerprint(cert_pem, false)
	end

	-- Pair each leaf with its key and attach issuer certificates to that leaf.
	-- Returns ngx.ssl parsed objects. Intermediates are not separate pairs.
	local function pair_certs_and_keys(certs, keys)
		local num_certs = #certs
		local num_keys = #keys

		safe_log(
			DEBUG,
			"Matching " .. num_certs .. " certificate(s) with " .. num_keys .. " key(s) by public key fingerprint"
		)

		local key_fingerprints = {}
		for i, key in ipairs(keys) do
			local fp = get_pubkey_fingerprint(key, true)
			key_fingerprints[i] = fp
			if fp then
				safe_log(DEBUG, "Key #" .. i .. " fingerprint: " .. fp:sub(1, 16) .. "...")
			else
				safe_log(NOTICE, "Could not extract fingerprint from key #" .. i)
			end
		end

		local leaves = {}
		local intermediates = {}
		local keys_used = {}
		for cert_idx, cert_pem in ipairs(certs) do
			local cert_id = get_cert_identifier(cert_pem) or ("cert_" .. cert_idx)
			local cert_fp = get_pubkey_fingerprint(cert_pem, false)

			if not cert_fp then
				safe_log(
					NOTICE,
					"Certificate #"
						.. cert_idx
						.. " ("
						.. cert_id
						.. "): could not extract public key fingerprint - skipping"
				)
			else
				safe_log(
					DEBUG,
					"Certificate #" .. cert_idx .. " (" .. cert_id .. ") fingerprint: " .. cert_fp:sub(1, 16) .. "..."
				)
				local matched_key = nil
				local matched_key_idx = nil
				for key_idx, key_fp in ipairs(key_fingerprints) do
					if key_fp and cert_fp == key_fp then
						matched_key = keys[key_idx]
						matched_key_idx = key_idx
						break
					end
				end
				if matched_key then
					safe_log(
						DEBUG,
						"Certificate #" .. cert_idx .. " (" .. cert_id .. ") matched with key #" .. matched_key_idx
					)
					keys_used[matched_key_idx] = true
					insert(leaves, {
						pem = cert_pem,
						key = matched_key,
						cert_id = cert_id,
						fp = cert_fp,
					})
				else
					safe_log(
						DEBUG,
						"Certificate #"
							.. cert_idx
							.. " ("
							.. cert_id
							.. ") has no matching key; attaching it as an issuer"
					)
					insert(intermediates, cert_pem)
				end
			end
		end

		for key_idx = 1, num_keys do
			if not keys_used[key_idx] then
				safe_log(NOTICE, "Key #" .. key_idx .. " was not matched to any certificate")
			end
		end

		local pairs = {}
		if not ssl or not ssl.parse_pem_cert or not ssl.parse_pem_priv_key then
			safe_log(ERR, "ngx.ssl PEM parsers are unavailable")
			return pairs
		end

		for _, leaf in ipairs(leaves) do
			-- Issuer-linked path only for set_cert: off-path Must-Staple bag members
			-- must not enter the Certificate message for this leaf.
			local chain_pem = nil
			pcall(function()
				local ocsp_mod = require "bunkerweb.ocsp"
				if ocsp_mod.issuer_linked_chain_pem then
					chain_pem = ocsp_mod.issuer_linked_chain_pem(leaf.pem, intermediates)
				end
			end)
			if type(chain_pem) ~= "string" or chain_pem == "" then
				-- Module unavailable: leaf only. Never bag-concat — off-path Must-Staple
				-- PEMs would fail-close after ClientHello sibling health fallback.
				chain_pem = leaf.pem
			end
			-- OCSP health/attach sees the FULL leaf+intermediates bag so
			-- presentable_chain_blocks can set unresolved_must_staple when it
			-- omits Must-Staple PEMs. set_cert still uses the depleted chain_pem
			-- (client never receives those PEMs). Passing depleted PEM alone
			-- would lose the flag after table.concat → re-parse.
			local ocsp_parts = { leaf.pem }
			if type(intermediates) == "table" then
				for _, ipem in ipairs(intermediates) do
					if type(ipem) == "string" and ipem ~= "" then
						ocsp_parts[#ocsp_parts + 1] = ipem
					end
				end
			end
			local ocsp_bag = table.concat(ocsp_parts, "\n")
			local parsed_cert, cert_err = ssl.parse_pem_cert(chain_pem)
			local parsed_key, key_err = ssl.parse_pem_priv_key(leaf.key)
			if not parsed_cert or not parsed_key then
				safe_log(
					ERR,
					"failed to parse certificate chain or key for "
						.. leaf.cert_id
						.. ": "
						.. tostring(cert_err or key_err)
				)
			else
				insert(pairs, {
					cert = parsed_cert,
					key = parsed_key,
					cert_id = leaf.cert_id,
					matched = true,
					cert_pem_for_ocsp = ocsp_bag,
					cert_fp_for_ocsp = leaf.fp,
				})
			end
		end

		return pairs
	end

	-- =====================================================================
	-- SECTION: site OCSP settings + dual-cert leaf selection + audit logs
	-- SSL_USE_OCSP_STAPLING / OCSP_STAPLE_MODE (multisite). One staple slot
	-- per handshake — order ClientHello-compatible leaves, log skip_slot.
	-- =====================================================================
	-- Helper: check if Redis is enabled globally (with exception handling)
	-- OPTIMIZATION: Use cached variables from get_variables_cached() to avoid shared dict read
	local function is_redis_enabled()
		-- Use cached variables when available (Priority 6 optimization)
		local vars = get_variables_cached()

		if not vars or not vars.global then
			return false -- Default to disabled if not configured
		end

		local value = vars.global["USE_REDIS"]
		if value == nil then
			return false
		end

		-- Normalize and interpret common truthy representations
		if type(value) == "boolean" then
			return value
		end
		local str = tostring(value):lower()
		return str == "1" or str == "true" or str == "on" or str == "yes"
	end

	-- Helper: check if OCSP stapling is enabled for this site.
	-- variables are stored as variables["global"] and variables["<primary service id>"],
	-- matching helpers.load_variables / utils.get_variable. A per-site value wins
	-- when present; otherwise the global value is used. Plugin default is "no".
	-- SNI may be a secondary SERVER_NAME on the service — resolve to the primary id.
	local function resolve_multisite_service_id(vars, sni)
		if not sni or type(vars) ~= "table" then
			return nil
		end
		if type(vars[sni]) == "table" then
			return sni
		end
		local sni_lower = tostring(sni):lower()
		for primary, site_vars in pairs(vars) do
			if primary ~= "global" and type(primary) == "string" and type(site_vars) == "table" then
				if primary:lower() == sni_lower then
					return primary
				end
			end
		end
		for primary, site_vars in pairs(vars) do
			if primary ~= "global" and type(site_vars) == "table" then
				local names = site_vars["SERVER_NAME"]
				if type(names) == "string" then
					for name in names:gmatch("%S+") do
						if name == sni or name:lower() == sni_lower then
							return primary
						end
					end
				end
			end
		end
		return nil
	end

	-- OPTIMIZATION: Cache variables dict in ngx.ctx to avoid repeated shared dict reads
	-- (Priority 6: reduces internalstore:get("variables", true) from 3+ calls to 1 per handshake)
	-- Savings: 0.1-0.4ms per handshake (shared dict read overhead eliminated)
	local function get_variables_cached()
		if ngx.ctx and ngx.ctx.bw_ocsp_variables_cache then
			return ngx.ctx.bw_ocsp_variables_cache
		end

		local ok_get, vars = pcall(function()
			return internalstore:get("variables", true)
		end)

		if not ok_get or type(vars) ~= "table" or type(vars["global"]) ~= "table" then
			return nil
		end

		-- Cache in ngx.ctx for reuse within this handshake (per-request, auto-cleaned)
		if ngx.ctx then
			ngx.ctx.bw_ocsp_variables_cache = vars
		end

		return vars
	end

	-- Per-site OCSP_* from variables dict (site id wins over global). Used by enable + mode.
	local function get_ocsp_site_variable(name)
		local vars = get_variables_cached()
		if not vars or type(vars) ~= "table" or type(vars["global"]) ~= "table" then
			return nil, vars
		end

		local value = vars["global"][name]
		if vars["global"]["MULTISITE"] == "yes" and server_name then
			local service_id = resolve_multisite_service_id(vars, server_name)
			if service_id and type(vars[service_id]) == "table" then
				local site_value = vars[service_id][name]
				if site_value ~= nil then
					value = site_value
				end
			end
		end
		return value, vars
	end

	-- True when USE_OCSP_STAPLING is yes for this site (plugin default no).
	local function is_ocsp_stapling_enabled()
		local value, vars = get_ocsp_site_variable("SSL_USE_OCSP_STAPLING")
		if value == nil and type(vars) ~= "table" then
			safe_log(DEBUG, "staple_decision=stapling_off tag=OCSP_STAPLING_OFF detail=variables_unavailable")
			return false
		end
		if type(value) == "boolean" then
			return value
		end
		if value == nil then
			return false
		end
		local str = tostring(value):lower()
		return str == "1" or str == "true" or str == "on" or str == "yes"
	end

	-- OCSP_STAPLE_MODE: normal (fail-close) | staple_only | open (Must-Staple soft fuse).
	-- Must-Staple fuse both HTTP and stream read. Default normal (fail-close).
	-- Stapling off → effective "open": no staple can be served, so Must-Staple is
	-- not enforced (matches bunkerweb.ocsp staple_mode; upstream served unstapled).
	local function get_ocsp_staple_mode()
		if not is_ocsp_stapling_enabled() then
			return "open"
		end
		local value = get_ocsp_site_variable("OCSP_STAPLE_MODE")
		if value == nil or value == "" then
			return "normal"
		end
		local str = tostring(value):lower()
		if str == "staple_only" or str == "open" or str == "normal" then
			return str
		end
		return "normal"
	end

	-- Closed staple_decision codes live in bunkerweb.ocsp (one vocabulary for HTTP + stream).
	local ocsp_mod_for_decision = nil
	pcall(function()
		ocsp_mod_for_decision = require "bunkerweb.ocsp"
	end)
	local function format_staple_decision(code, fields)
		if ocsp_mod_for_decision and ocsp_mod_for_decision.format_staple_decision then
			return ocsp_mod_for_decision.format_staple_decision(code, fields)
		end
		-- Fallback only if the module failed to load (should not happen in production).
		return "staple_decision=" .. tostring(code or "unmet")
	end

	-- Classify a leaf PEM as "ec", "rsa", or nil. Used to pick one OCSP staple when
	-- ngx.ocsp.set_ocsp_status_resp can only hold a single response per handshake.
	local function cert_pubkey_kind(cert_pem)
		if type(cert_pem) ~= "string" or #cert_pem == 0 or not has_resty_ssl then
			return nil
		end

		-- OPTIMIZATION: Check metadata cache for key kind
		local cached = cert_metadata_cache_get(cert_pem)
		if cached and cached.kind then
			safe_log(DEBUG, "OCSP cert key kind cache hit: " .. cached.kind)
			return cached.kind
		end

		local kind = nil
		pcall(function()
			local cert_obj = resty_x509.new(cert_pem)
			local pub = cert_obj and cert_obj:get_pubkey()
			if not pub then
				return
			end
			local key_type = pub.get_key_type and pub:get_key_type() or nil
			local label = key_type
			if type(key_type) == "table" then
				label = key_type.sn or key_type.ln or key_type.nid
			end
			label = lower(tostring(label or ""))
			if label:find("ec", 1, true) or label:find("id-ec", 1, true) then
				kind = "ec"
			elseif label:find("rsa", 1, true) then
				kind = "rsa"
			end
		end)

		-- OPTIMIZATION: Cache the key kind for future reuse
		if kind then
			cert_metadata_cache_set(cert_pem, { kind = kind })
		end

		return kind
	end

	-- Audit which leaf was stapled — kind + SPKI + der_sha256 + epoch this node served.
	-- Multi-staple NULL slots (from bunkerweb.ocsp.attach) → ok_partial, not hollow ok.
	local function log_ocsp_stapled(kind, fp, resp)
		local der = ocsp_resp_binding(resp) or "-"
		local fp_s = (type(fp) == "string" and #fp == 64) and fp or "-"
		local epoch = ocsp_current_epoch() or "0"
		local worker = "-"
		pcall(function()
			if ngx.worker and ngx.worker.id then
				worker = tostring(ngx.worker.id())
			end
		end)
		if ngx.ctx and fp_s ~= "-" then
			ngx.ctx.bw_ocsp_stapled_fp = fp_s
		end
		local fields = {
			tag = "OCSP_STAPLED",
			kind = kind or "unknown",
			fp = fp_s,
			der_sha256 = der,
			epoch = epoch,
			worker = worker,
			server_name = server_name or "nil",
		}
		local decision = "ok"
		local null_slots = ngx.ctx and tonumber(ngx.ctx.bw_ocsp_multi_null_slots) or nil
		local multi_entries = ngx.ctx and tonumber(ngx.ctx.bw_ocsp_multi_entries) or nil
		local stapled_entries = ngx.ctx and tonumber(ngx.ctx.bw_ocsp_multi_stapled) or nil
		if multi_entries and multi_entries > 0 then
			fields.multi_entries = multi_entries
			fields.stapled_entries = stapled_entries or multi_entries
			fields.null_slots = null_slots or 0
			if (null_slots or 0) > 0 then
				decision = "ok_partial"
				fields.detail = "null_slot_omission"
			end
		end
		safe_log(INFO, format_staple_decision(decision, fields))
	end

	local function log_ocsp_staple_skip(kind, fp, reason)
		local fp_s = "-"
		if type(fp) == "string" and #fp > 0 then
			fp_s = fp
		end
		safe_log(
			NOTICE,
			format_staple_decision(reason or "skip_slot", {
				tag = "OCSP_STAPLE_SKIP",
				kind = kind or "unknown",
				fp = fp_s,
				server_name = server_name or "nil",
			})
		)
	end

	-- ngx.ocsp keeps one staple per connection. Order ClientHello-compatible
	-- leaves (curve-aware signature_algorithms) so a poisoned Must-Staple shard
	-- on the first match can fall back to another leaf this client can verify.
	local function ordered_ocsp_staple_candidates(candidates)
		if not candidates or #candidates == 0 then
			return {}
		end
		if #candidates == 1 then
			return { candidates[1] }
		end
		local sigalgs_ext = ngx.ctx and ngx.ctx.bw_ocsp_sigalgs_ext or nil
		local prefer_kind = ngx.ctx and ngx.ctx.bw_ocsp_prefer_kind or nil
		local ordered = nil
		pcall(function()
			local ocsp_mod = require "bunkerweb.ocsp"
			if ocsp_mod.ordered_leaves_for_handshake then
				ordered = ocsp_mod.ordered_leaves_for_handshake(candidates, sigalgs_ext, prefer_kind)
			elseif ocsp_mod.select_leaf_for_handshake then
				local one = ocsp_mod.select_leaf_for_handshake(candidates, sigalgs_ext, prefer_kind)
				if one then
					ordered = { one }
				end
			end
		end)
		if type(ordered) == "table" and #ordered > 0 then
			return ordered
		end
		return { candidates[1] }
	end

	-- First ClientHello-compatible leaf from ordered_ocsp_staple_candidates;
	-- logs skip_slot for siblings not presented (single Certificate leaf).
	local function select_ocsp_staple_candidate(candidates)
		local ordered = ordered_ocsp_staple_candidates(candidates)
		local chosen = ordered[1]
		if not chosen then
			return nil
		end
		if #candidates > 1 then
			local chosen_kind = cert_pubkey_kind(chosen.ocsp_cert) or "unknown"
			for _, cand in ipairs(candidates) do
				if cand ~= chosen then
					local skip_fp = cand.ocsp_fp_hint
					if (not skip_fp or skip_fp == "") and type(cand.ocsp_cert) == "string" then
						skip_fp = get_ocsp_pubkey_fingerprint(cand.ocsp_cert)
					end
					local kind = cert_pubkey_kind(cand.ocsp_cert) or "unknown"
					local reason = chosen_kind == "rsa" and "single_slot_rsa_prefer" or "single_slot_ecdsa_prefer"
					log_ocsp_staple_skip(kind, skip_fp, reason)
				end
			end
		end
		return chosen
	end

	-- =====================================================================
	-- SECTION: serial / CertID / Must-Staple detection / disk meta gates
	-- Canonical serial hex; CertID bind; TLS Feature Must-Staple; ocsp.json
	-- ligand; colony floor; tombstone; canary paged; AIA pin; serial ban.
	-- =====================================================================
	-- Helper: sanitize domain/cert name for filesystem (replace * with _wildcard_)
	local function sanitize_name(name)
		if not name then
			return nil
		end
		return name:gsub("%*", "_wildcard_")
	end

	-- Canonical uppercase hex serial (no 0x, no leading zeros except "0").
	-- resty BN tostring() is decimal; openssl CLI serials are hex — normalize both here.
	local function canonical_serial_hex(serial)
		if serial == nil then
			return nil
		end
		if type(serial) == "table" and serial.to_hex then
			local ok_hex, hex = pcall(function()
				return serial:to_hex()
			end)
			if ok_hex and type(hex) == "string" and #hex > 0 then
				hex = hex:upper():gsub("^0+", "")
				return hex == "" and "0" or hex
			end
		end
		if type(serial) ~= "string" then
			serial = tostring(serial)
		end
		if serial == "" then
			return nil
		end
		serial = serial:upper():gsub("%s+", ""):gsub("^0X", "")
		if not serial:match("^[0-9A-F]+$") then
			return nil
		end
		serial = serial:gsub("^0+", "")
		return serial == "" and "0" or serial
	end

	-- Helper: extract certificate serial number from PEM (canonical hex).
	-- Handshake path: resty.openssl only — no /tmp + openssl CLI.
	local function get_cert_serial(cert_pem)
		if not cert_pem or #cert_pem == 0 then
			return nil
		end

		if not has_resty_ssl then
			safe_log(
				DEBUG,
				"OCSP get_cert_serial: resty.openssl unavailable; no CLI fallback server_name="
					.. (server_name or "nil")
			)
			return nil
		end

		local cert, err = resty_x509.new(cert_pem)
		if cert then
			local serial_num = cert:get_serial_number()
			local hex = canonical_serial_hex(serial_num)
			if hex then
				return hex
			end
			safe_log(
				DEBUG,
				"OCSP get_cert_serial resty.openssl returned cert but no serial server_name=" .. (server_name or "nil")
			)
		else
			safe_log(DEBUG, "OCSP get_cert_serial resty.openssl parse error: " .. tostring(err))
		end
		return nil
	end

	-- Helper: CertID serial (canonical hex) from OCSP response DER. Returns want_hex
	-- when any SingleResponse names it, else the first serial; callers compare the
	-- result with want_hex. Shares bunkerweb.ocsp's DER parser with stream
	-- (lua-resty-openssl has no OCSP module).
	local function get_ocsp_serial(ocsp_der, want_hex)
		if not ocsp_der or #ocsp_der == 0 then
			return nil
		end
		local ok_mod, shared = pcall(require, "bunkerweb.ocsp")
		if not ok_mod or type(shared) ~= "table" or not shared.ocsp_resp_serial_hex then
			safe_log(DEBUG, "OCSP get_ocsp_serial: bunkerweb.ocsp unavailable server_name=" .. (server_name or "nil"))
			return nil
		end
		local hex = shared.ocsp_resp_serial_hex(ocsp_der, want_hex)
		if not hex then
			safe_log(DEBUG, "OCSP get_ocsp_serial: response DER unparseable server_name=" .. (server_name or "nil"))
		end
		return hex
	end

	-- Helper: CertID must name this handshake leaf (serial + issuer DN).
	-- Fail closed when either side is unreadable — never soft-allow a stale same-key body.
	local function verify_ocsp_cert_match(cert_pem, ocsp_der, issuer_pems)
		if type(cert_pem) ~= "string" or cert_pem == "" or type(ocsp_der) ~= "string" or ocsp_der == "" then
			safe_log(DEBUG, "OCSP CertID refuse: missing leaf PEM or OCSP DER server_name=" .. (server_name or "nil"))
			return false
		end

		local cert_serial = get_cert_serial(cert_pem)
		if not cert_serial then
			safe_log(DEBUG, "OCSP CertID refuse: certificate serial unreadable server_name=" .. (server_name or "nil"))
			return false
		end

		local ocsp_serial = get_ocsp_serial(ocsp_der, cert_serial)
		if not ocsp_serial then
			safe_log(
				DEBUG,
				"OCSP CertID refuse: OCSP response serial unreadable server_name=" .. (server_name or "nil")
			)
			return false
		end

		if cert_serial ~= ocsp_serial then
			safe_log(
				ERR,
				"OCSP CertID serial mismatch: cert="
					.. cert_serial
					.. " ocsp="
					.. ocsp_serial
					.. " server_name="
					.. (server_name or "nil")
			)
			return false
		end

		local leaf_issuer = nil
		if has_resty_ssl and resty_x509 and resty_x509.new then
			pcall(function()
				local leaf_obj = resty_x509.new(cert_pem)
				if leaf_obj and leaf_obj.get_issuer_name then
					local n = leaf_obj:get_issuer_name()
					if n then
						leaf_issuer = tostring(n)
					end
				end
			end)
		end
		if not leaf_issuer then
			safe_log(DEBUG, "OCSP CertID refuse: leaf issuer DN unreadable server_name=" .. (server_name or "nil"))
			return false
		end

		local candidates = issuer_pems
		if type(candidates) ~= "table" or #candidates == 0 then
			safe_log(DEBUG, "OCSP CertID refuse: no issuer candidates server_name=" .. (server_name or "nil"))
			return false
		end
		for _, iss in ipairs(candidates) do
			if type(iss) == "string" and #iss > 0 and has_resty_ssl and resty_x509 and resty_x509.new then
				local matched = false
				pcall(function()
					local iss_obj = resty_x509.new(iss)
					if iss_obj and iss_obj.get_subject_name then
						local subj = iss_obj:get_subject_name()
						if subj and tostring(subj) == leaf_issuer then
							matched = true
						end
					end
				end)
				if matched then
					safe_log(
						DEBUG,
						"OCSP CertID match: serial=" .. cert_serial .. " server_name=" .. (server_name or "nil")
					)
					return true
				end
			end
		end
		safe_log(
			ERR,
			"OCSP CertID issuer mismatch for serial=" .. cert_serial .. " server_name=" .. (server_name or "nil")
		)
		return false
	end

	-- Helper: fast validation using cached metadata fingerprint
	-- This avoids parsing OCSP DER (openssl/resty) just to detect corrupted/incorrect cached responses.
	-- Returns:
	-- - true only if ocsp.json is present, parseable, and fingerprint matches
	-- - false on mismatch, missing/invalid meta, or incomplete arguments (fail closed)
	local function verify_ocsp_fingerprint_match(expected_cert_fp, ocsp_dir)
		if not expected_cert_fp or not ocsp_dir then
			return false
		end

		local meta_path = ocsp_dir .. "/ocsp.json"
		local meta_raw = nil
		pcall(function()
			local fmeta = io.open(meta_path, "r")
			if fmeta then
				meta_raw = fmeta:read("*a")
				fmeta:close()
			end
		end)

		if not meta_raw or #meta_raw == 0 then
			safe_log(
				DEBUG,
				"OCSP fingerprint verify failed (missing ocsp.json) expected_fp="
					.. tostring(expected_cert_fp)
					.. " server_name="
					.. (server_name or "nil")
			)
			return false
		end

		local ok_decode, decoded = pcall(cjson.decode, meta_raw)
		if not ok_decode or type(decoded) ~= "table" then
			safe_log(
				DEBUG,
				"OCSP fingerprint verify failed (invalid ocsp.json) expected_fp="
					.. tostring(expected_cert_fp)
					.. " server_name="
					.. (server_name or "nil")
			)
			return false
		end

		local meta_fp = decoded.fingerprint
		if type(meta_fp) ~= "string" then
			safe_log(
				DEBUG,
				"OCSP fingerprint verify failed (missing fingerprint in ocsp.json) expected_fp="
					.. tostring(expected_cert_fp)
					.. " server_name="
					.. (server_name or "nil")
			)
			return false
		end

		meta_fp = meta_fp:lower()
		if meta_fp == expected_cert_fp then
			return true
		end

		safe_log(
			ERR,
			"OCSP fingerprint mismatch: meta_fp="
				.. meta_fp
				.. " expected_fp="
				.. tostring(expected_cert_fp)
				.. " ocsp_dir="
				.. ocsp_dir
				.. " server_name="
				.. (server_name or "nil")
		)
		return false
	end

	-- True when TLS Feature text asserts status_request (Must-Staple / feature id 5).
	-- Do not substring-match "5": that false-positives on OIDs and other digits.
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
		-- Feature id 5 as a whole decimal token (e.g. "5", "5, 17") — callers must pass
		-- extension text or TLS Feature value line(s), never a full openssl dump.
		for token in text:gmatch("%d+") do
			if token == "5" then
				return true
			end
		end
		return false
	end

	-- Helper: read and parse certificate once for Must-Staple (TLS Feature).
	-- Handshake path: resty.openssl only — no /tmp + openssl CLI. Callers also consult
	-- ocsp.json (ocsp-refresh) when resty cannot see Must-Staple.
	-- AIA OCSP URI pin checks go through bunkerweb.ocsp.aia_uri_pin_ok (same as stream).
	-- Input: cert_pem - certificate in PEM format (passed from plugin, NOT read via ssl.cert_pem())
	-- Returns: { cert_parsed = resty cert object or nil, must_staple = bool, issuer_name = string or nil }
	-- OPTIMIZATION: Extract issuer DN for later cache (Priority 10) to avoid re-parsing in validation
	local function read_certificate_metadata(cert_pem)
		local result = {
			cert_parsed = nil,
			must_staple = false,
			issuer_name = nil,
		}

		if not cert_pem or #cert_pem == 0 then
			return result
		end

		-- Try to parse with resty.openssl (parse once)
		if has_resty_ssl then
			local cert, err = resty_x509.new(cert_pem)
			if cert then
				result.cert_parsed = cert

				-- Extract TLS Feature extension for Must-Staple (OID 1.3.6.1.5.5.7.1.24)
				local tls_feature_ext = cert:get_extension("tlsfeature")
				if tls_feature_ext then
					if tls_feature_is_must_staple(tls_feature_ext:text()) then
						result.must_staple = true
						safe_log(DEBUG, "OCSP-Must-Staple extension found (OID 1.3.6.1.5.5.7.1.24)")
					end
				end

				-- OPTIMIZATION: Extract issuer DN (Priority 10) to cache for validation loop
				-- This prevents re-parsing the same cert in ocsp_validate_response_for_fp()
				pcall(function()
					local issuer_name_obj = cert:get_issuer_name()
					if issuer_name_obj then
						result.issuer_name = tostring(issuer_name_obj)
					end
				end)

				return result
			else
				safe_log(DEBUG, "Certificate parse error with resty.openssl: " .. tostring(err))
			end
		end

		safe_log(
			DEBUG,
			"OCSP read_certificate_metadata: resty.openssl unavailable or failed; no CLI fallback server_name="
				.. (server_name or "nil")
		)
		return result
	end

	-- Read /var/cache/bunkerweb/ssl/{h1}/{h2}/{fp}/ocsp.json → table or nil.
	-- OPTIMIZATION: Deduplicate reads within same handshake via ngx.ctx
	-- Per-handshake cache to avoid repeated disk reads for the same cert_fp
	local function read_ocsp_json_for_fp(cert_fp)
		if not is_fp64_lower_hex(cert_fp) then
			return nil
		end

		-- OPTIMIZATION: Check per-handshake cache first (deduplicate within handshake)
		-- Initialize cache key in ngx.ctx if needed
		if ngx.ctx and not ngx.ctx.ocsp_json_cache then
			ngx.ctx.ocsp_json_cache = {}
		end

		if ngx.ctx and ngx.ctx.ocsp_json_cache then
			local cached = ngx.ctx.ocsp_json_cache[cert_fp]
			if cached ~= nil then
				-- Distinguish between "file not found" (false) and "found" (table)
				if cached == false then
					return nil
				end
				safe_log(DEBUG, "OCSP ocsp.json cache hit (per-handshake) for fp=" .. cert_fp:sub(1, 16) .. "...")
				return cached
			end
		end

		local meta_path = "/var/cache/bunkerweb/ssl/"
			.. cert_fp:sub(1, 1)
			.. "/"
			.. cert_fp:sub(2, 2)
			.. "/"
			.. cert_fp
			.. "/ocsp.json"
		local meta_raw = nil
		pcall(function()
			local fmeta = io.open(meta_path, "r")
			if fmeta then
				meta_raw = fmeta:read("*a")
				fmeta:close()
			end
		end)
		if not meta_raw or #meta_raw == 0 or not cjson then
			if ngx.ctx and ngx.ctx.ocsp_json_cache then
				ngx.ctx.ocsp_json_cache[cert_fp] = false
			end
			return nil
		end
		local ok_decode, decoded = pcall(cjson.decode, meta_raw)
		if ok_decode and type(decoded) == "table" then
			if ngx.ctx and ngx.ctx.ocsp_json_cache then
				ngx.ctx.ocsp_json_cache[cert_fp] = decoded
			end
			return decoded
		end
		if ngx.ctx and ngx.ctx.ocsp_json_cache then
			ngx.ctx.ocsp_json_cache[cert_fp] = false
		end
		return nil
	end

	-- True when ocsp.json marks must_staple for this SPKI (job-written pin).
	-- Job writes this when the leaf TLS Feature was seen at refresh time; used
	-- when resty.openssl cannot parse TLS Feature on the handshake path.
	local function ocsp_json_must_staple(cert_fp)
		-- OPTIMIZATION: Check Must-Staple cache before reading ocsp.json
		local cached = must_staple_cache_get(cert_fp)
		if cached ~= nil then
			safe_log(DEBUG, "OCSP Must-Staple cache hit for fp=" .. (cert_fp or ""):sub(1, 16) .. "...")
			return cached
		end

		local meta = read_ocsp_json_for_fp(cert_fp)
		local result = meta ~= nil and meta.must_staple == true

		-- OPTIMIZATION: Cache the Must-Staple detection result
		must_staple_cache_set(cert_fp, result)

		return result
	end

	-- -------------------------------------------------------------------------
	-- leaf_requires_must_staple(pem, fp) → true | false | nil
	--
	-- Tri-state Must-Staple detection that never requires bunkerweb.ocsp (so a
	-- missing/broken module cannot answer "false" and skip fail-closed).
	--
	--   true  — TLS Feature status_request on any PEM block, OR ocsp.json
	--           must_staple=true for the leaf SPKI.
	--   false — resty parsed the leaf/chain with no TLS Feature, and either
	--           ocsp.json is absent or must_staple is not true.
	--   nil   — unknown (no resty parse AND no ocsp.json). Callers must
	--           fail closed (treat like Must-Staple) — never invent "false".
	--
	-- Used to scope issuer_path / module-miss demotion: non-MS leaves stay
	-- viable unstapled when the OCSP module cannot answer; MS/unknown refuse.
	-- -------------------------------------------------------------------------
	local leaf_ms_cache = {}
	local LEAF_MS_UNKNOWN = {} -- sentinel so cached nil is distinguishable from miss
	local function leaf_requires_must_staple(pem, fp)
		local cache_key = nil
		if type(fp) == "string" and is_fp64_lower_hex(fp:lower()) then
			cache_key = "fp:" .. fp:lower()
		elseif type(pem) == "string" and #pem > 0 then
			local crc = (ngx.crc32_long and ngx.crc32_long(pem)) or #pem
			cache_key = "pem:" .. tostring(crc)
		else
			return nil
		end
		local cached = leaf_ms_cache[cache_key]
		if cached ~= nil then
			if cached == LEAF_MS_UNKNOWN then
				return nil
			end
			return cached
		end

		-- OPTIMIZATION: Check per-worker Must-Staple cache by fingerprint
		-- If we have a valid fingerprint, check if Must-Staple was already determined
		local check_fp = type(fp) == "string" and fp:lower() or nil
		if check_fp and is_fp64_lower_hex(check_fp) then
			local cached_result = must_staple_cache_get(check_fp)
			if cached_result ~= nil then
				safe_log(DEBUG, "OCSP leaf Must-Staple cache hit for fp=" .. check_fp:sub(1, 16) .. "...")
				leaf_ms_cache[cache_key] = cached_result
				return cached_result
			end
		end

		local tls_known, tls_must = false, false
		if type(pem) == "string" and #pem > 0 and has_resty_ssl then
			local blocks = parse_pem_certificates(pem)
			if not blocks or #blocks == 0 then
				blocks = { pem }
			end
			for _, block in ipairs(blocks) do
				local ok_read, meta = pcall(read_certificate_metadata, block)
				if ok_read and meta and meta.cert_parsed then
					tls_known = true
					if meta.must_staple then
						tls_must = true
						break
					end
				end
			end
		end
		if tls_must then
			leaf_ms_cache[cache_key] = true
			return true
		end
		local check_fp = type(fp) == "string" and fp:lower() or nil
		if (not check_fp or not is_fp64_lower_hex(check_fp)) and type(pem) == "string" and #pem > 0 then
			local blocks = parse_pem_certificates(pem)
			local leaf = (blocks and blocks[1]) or pem
			check_fp = get_ocsp_pubkey_fingerprint(leaf)
		end
		if type(check_fp) == "string" and is_fp64_lower_hex(check_fp) then
			local meta = read_ocsp_json_for_fp(check_fp)
			if meta ~= nil then
				if meta.must_staple == true then
					-- Positive MS from ocsp.json is safe even without resty DN proof.
					leaf_ms_cache[cache_key] = true
					-- OPTIMIZATION: Cache per-worker Must-Staple result by fingerprint
					must_staple_cache_set(check_fp, true)
					return true
				end
				-- meta.must_staple ~= true: only trust as proven-false when resty
				-- parsed the PEM (tls_known). Without resty, a lying status[5] /
				-- intermediate fp must not sticky-cache false (would soften
				-- leaf_fail_closed_must_staple and skip outer abort).
				if tls_known then
					leaf_ms_cache[cache_key] = false
					-- OPTIMIZATION: Cache per-worker Must-Staple result by fingerprint
					if check_fp then
						must_staple_cache_set(check_fp, false)
					end
					return false
				end
			end
		end
		if tls_known then
			leaf_ms_cache[cache_key] = false
			-- OPTIMIZATION: Cache per-worker Must-Staple result by fingerprint (if we have FP)
			if check_fp and is_fp64_lower_hex(check_fp) then
				must_staple_cache_set(check_fp, false)
			end
			return false
		end
		-- No resty parse and no trustworthy ocsp.json → unknown.
		leaf_ms_cache[cache_key] = LEAF_MS_UNKNOWN
		return nil
	end
	-- Fail-closed gate over leaf_requires_must_staple: true when Must-Staple OR
	-- unknown; false only when proven not Must-Staple. Prefer this over raw
	-- `has_must_staple` when deciding whether a module/pcall failure may demote.
	local function leaf_fail_closed_must_staple(pem, fp)
		return leaf_requires_must_staple(pem, fp) ~= false
	end

	-- -------------------------------------------------------------------------
	-- resolve_leaf(cert_pem, cert_fp_hint) → leaf_pem, leaf_fp, blocks, fp_to_pem
	--
	-- Pick the handshake end-entity from a PEM chain. blocks[1] is NOT always
	-- the leaf (intermediate-first bags / lying plugin status[5] hints).
	--
	-- Order of preference:
	--   1. Hint SPKI that matches some block AND that block is not an issuer
	--      of another block in the bag (rejects intermediate-as-hint).
	--   2. First block whose subject is not named as issuer by any other block.
	--   3. blocks[1] / first fingerprintable entry (last resort).
	--
	-- PATH B binds Must-Staple + allow-pin from this result BEFORE peer /
	-- stapling-off / ngx.ocsp gates so early exits cannot disagree on the leaf.
	-- -------------------------------------------------------------------------
	local function resolve_leaf(cert_pem, cert_fp_hint)
		local blocks = parse_pem_certificates(cert_pem)
		if not blocks or #blocks == 0 then
			blocks = type(cert_pem) == "string" and { cert_pem } or {}
		end
		local fp_to_pem = {}
		local entries = {}
		for _, block in ipairs(blocks) do
			local fp = get_ocsp_pubkey_fingerprint(block)
			if type(fp) == "string" and is_fp64_lower_hex(fp) then
				fp_to_pem[fp] = block
				entries[#entries + 1] = { pem = block, fp = fp }
			end
		end
		local hint = nil
		if type(cert_fp_hint) == "string" then
			local h = cert_fp_hint:lower()
			if is_fp64_lower_hex(h) then
				hint = h
			end
		end
		local issuer_subjects = {}
		local subject_of = {}
		if has_resty_ssl and resty_x509 and #entries > 0 then
			for _, e in ipairs(entries) do
				pcall(function()
					local c = resty_x509.new(e.pem)
					if c and c.get_subject_name then
						local s = tostring(c:get_subject_name() or "")
						if s ~= "" then
							subject_of[e.fp] = s
						end
					end
					if c and c.get_issuer_name then
						local iss = tostring(c:get_issuer_name() or "")
						if iss ~= "" then
							issuer_subjects[iss] = true
						end
					end
				end)
			end
		end
		local function is_issuer_block(fp)
			local s = subject_of[fp]
			return type(s) == "string" and s ~= "" and issuer_subjects[s] == true
		end
		if hint and fp_to_pem[hint] and not is_issuer_block(hint) then
			return fp_to_pem[hint], hint, blocks, fp_to_pem
		end
		if hint and fp_to_pem[hint] and is_issuer_block(hint) then
			safe_log(
				ERR,
				"OCSP hint matches intermediate SPKI; ignoring hint="
					.. hint:sub(1, 16)
					.. "... server_name="
					.. (server_name or "nil")
			)
		end
		for _, e in ipairs(entries) do
			if not is_issuer_block(e.fp) then
				return e.pem, e.fp, blocks, fp_to_pem
			end
		end
		if #entries > 0 then
			return entries[1].pem, entries[1].fp, blocks, fp_to_pem
		end
		return cert_pem, hint, blocks, fp_to_pem
	end

	-- Positive unix int from a meta field (number or digit string), else nil.
	-- Used for colony floor / local this_update_unix comparisons (never invent 0).
	local function meta_unix_field(meta, key)
		if type(meta) ~= "table" or type(key) ~= "string" then
			return nil
		end
		local u = meta[key]
		if type(u) == "number" and u > 0 then
			return math.floor(u)
		end
		if type(u) == "string" then
			local n = tonumber(u)
			if n and n > 0 then
				return math.floor(n)
			end
		end
		return nil
	end

	-- Parse ocsp-floor/{fp} to CA-signed this_update_unix (colony rank), or nil.
	local function parse_floor_rank(raw)
		if type(raw) ~= "string" or raw == "" then
			return nil
		end
		local trimmed = raw:match("^%s*(.-)%s*$") or raw
		if trimmed:sub(1, 1) ~= "{" or not cjson then
			return nil
		end
		local ok, decoded = pcall(cjson.decode, trimmed)
		if not ok or type(decoded) ~= "table" then
			return nil
		end
		return meta_unix_field(decoded, "this_update_unix")
	end

	-- True when colony floor this_update_unix is ahead of local meta — Must-Staple closed.
	local function cluster_floor_blocks(cert_fp, meta)
		if not is_fp64_lower_hex(cert_fp) then
			return false
		end
		local floor_path = "/var/cache/bunkerweb/ssl/ocsp-floor/" .. cert_fp
		local raw = nil
		pcall(function()
			local f = io.open(floor_path, "r")
			if f then
				raw = f:read("*a")
				f:close()
			end
		end)
		local floor_rank = parse_floor_rank(raw)
		if not floor_rank or floor_rank <= 0 then
			return false
		end
		local local_rank = meta_unix_field(meta, "this_update_unix")
		if not local_rank then
			return false
		end
		if local_rank >= floor_rank then
			return false
		end
		safe_log(
			ERR,
			"OCSP cluster floor ahead of local this_update_unix; Must-Staple closed fp="
				.. cert_fp:sub(1, 16)
				.. "... floor="
				.. tostring(floor_rank)
				.. " local="
				.. tostring(local_rank)
				.. " server_name="
				.. (server_name or "nil")
		)
		return true
	end

	-- Job tombstone writes "tombstoned": true before DER unlink / epoch bump.
	-- Same early refuse as stream (bunkerweb.ocsp): do not wait for paged/epoch/DER.
	local function meta_tombstoned(meta)
		return type(meta) == "table" and meta.tombstoned == true
	end

	-- Live shard must be scheduler-paged (canary handshake) before stapling.
	-- Require explicit paged=true. Missing field is not canary proof.
	local function shard_not_paged(meta)
		if type(meta) ~= "table" then
			return true
		end
		return meta.paged ~= true
	end

	-- Same AIA pin policy as stream (bunkerweb.ocsp.aia_uri_pin_ok):
	-- membership across all leaf AIA OCSP URIs, punctuation-safe extractors.
	-- leaf_pem may be nil on fingerprint-only paths: Must-Staple then refuses
	-- (aia_uri_leaf_unavailable); optional staple still allows pin + ligand.
	-- Returns blocks (bool), detail (staple_decision code or nil).
	-- Caller: Must-Staple → refuse_must_staple(detail); optional → skip staple.
	local function aia_uri_pin_blocks(cert_fp, leaf_pem, must_staple)
		local meta = read_ocsp_json_for_fp(cert_fp)
		-- pcall keeps only the first return; pack ok+why so detail survives.
		local call_ok, packed = pcall(function()
			local ocsp_mod = require "bunkerweb.ocsp"
			if not ocsp_mod.aia_uri_pin_ok then
				return { false, "aia_uri_unpinned" }
			end
			local ok_pin, why = ocsp_mod.aia_uri_pin_ok(leaf_pem, meta, must_staple)
			return { ok_pin, why }
		end)
		if not call_ok then
			safe_log(
				ERR,
				"OCSP aia_uri_pin_ok error: " .. tostring(packed) .. " server_name=" .. (server_name or "nil")
			)
			return true, "aia_uri_unpinned"
		end
		local pin_ok = packed and packed[1]
		local pin_why = packed and packed[2]
		if pin_ok then
			return false, nil
		end
		return true, pin_why or "aia_uri_mismatch"
	end

	-- Shared ligand: delegate to bunkerweb.ocsp (outside-shard ocsp-ligand/{fp}).
	-- HTTP and stream must compute a byte-identical verdict for the same body.
	-- Never fall back to an inlined in-shard-only check — that reopens the
	-- zone-split the outside ligand was meant to close. If require fails,
	-- fail closed (ligand_missing) rather than stapling on private logic.
	-- Returns ok, reason, meta_sha, body_sha.
	local function ocsp_json_ligand_matches(cert_fp, resp)
		local meta = read_ocsp_json_for_fp(cert_fp)
		local ok_mod, ocsp_mod = pcall(require, "bunkerweb.ocsp")
		if not ok_mod or not ocsp_mod or not ocsp_mod.ligand_matches then
			-- Fail closed: never fall back to in-shard-only binding (zone-split).
			return false, "ligand_missing", nil, nil
		end
		return ocsp_mod.ligand_matches(meta, cert_fp, resp)
	end

	-- Fingerprint-hint path cannot validate_ocsp_response without leaf PEM.
	-- Require meta.fingerprint + der_sha256 binding to the exact DER body.
	-- Logs accept/refuse with truncated expected vs observed digests for audit.
	local function ocsp_json_authorizes_resp(cert_fp, resp)
		local fp_short = (type(cert_fp) == "string" and cert_fp:sub(1, 16)) or "?"
		local ok, reason, meta_sha, body_sha = ocsp_json_ligand_matches(cert_fp, resp)
		if not ok then
			if reason == "der_sha256_mismatch" then
				safe_log(
					ERR,
					"OCSP meta der_sha256 refuse fp="
						.. fp_short
						.. "... expected="
						.. ((type(meta_sha) == "string" and meta_sha:sub(1, 16)) or "nil")
						.. "... observed="
						.. ((type(body_sha) == "string" and body_sha:sub(1, 16)) or "nil")
						.. "... server_name="
						.. (server_name or "nil")
				)
			else
				local level = reason == "fingerprint_mismatch_or_missing_meta" and DEBUG or ERR
				safe_log(
					level,
					"OCSP meta der_sha256 refuse fp="
						.. fp_short
						.. "... reason="
						.. tostring(reason)
						.. " server_name="
						.. (server_name or "nil")
				)
			end
			return false
		end
		safe_log(
			INFO,
			"OCSP meta der_sha256 accept fp="
				.. fp_short
				.. "... der_sha256="
				.. meta_sha:sub(1, 16)
				.. "... server_name="
				.. (server_name or "nil")
		)
		return true
	end

	-- Must-Staple may not rely on private crypto-verified L1 alone.
	-- Returns true, or false, raw ligand_verdict reason (caller passes that into
	-- refuse_must_staple so KEEP_ALLOW[ligand_missing] can hold the allow pin;
	-- format_staple_decision still aliases to staple_decision=shared_ligand).
	local function must_staple_binds_shared_ligand(cert_fp, resp)
		local ok, reason, meta_sha, body_sha = ocsp_json_ligand_matches(cert_fp, resp)
		if ok then
			return true
		end
		-- Digest detail at DEBUG; refuse_must_staple emits the alertable ERR tag.
		local fp_short = (type(cert_fp) == "string" and cert_fp:sub(1, 16)) or "?"
		if reason == "der_sha256_mismatch" then
			safe_log(
				DEBUG,
				"OCSP shared ligand mismatch fp="
					.. fp_short
					.. "... expected="
					.. ((type(meta_sha) == "string" and meta_sha:sub(1, 16)) or "nil")
					.. "... observed="
					.. ((type(body_sha) == "string" and body_sha:sub(1, 16)) or "nil")
					.. "... server_name="
					.. (server_name or "nil")
			)
		else
			safe_log(
				DEBUG,
				"OCSP shared ligand miss fp="
					.. fp_short
					.. "... reason="
					.. tostring(reason)
					.. " server_name="
					.. (server_name or "nil")
			)
		end
		return false, tostring(reason or "ligand_mismatch")
	end

	-- serial-blacklist.json bans one leaf serial until the job publishes a newer GOOD.
	-- A different serial_hex (reissue) is allowed. Missing or unreadable serial fails closed.
	local function serial_blacklist_blocks(cert_fp, resp)
		if not is_fp64_lower_hex(cert_fp) or type(resp) ~= "string" or resp == "" then
			return false
		end
		local path = "/var/cache/bunkerweb/ssl/"
			.. cert_fp:sub(1, 1)
			.. "/"
			.. cert_fp:sub(2, 2)
			.. "/"
			.. cert_fp
			.. "/serial-blacklist.json"
		local raw = nil
		pcall(function()
			local f = io.open(path, "r")
			if f then
				raw = f:read("*a")
				f:close()
			end
		end)
		if not raw or raw == "" then
			return false
		end
		local banned_hex = raw:match('"serial_hex"%s*:%s*"([0-9A-Fa-f]+)"')
		if not banned_hex then
			safe_log(
				ERR,
				"OCSP serial blacklist unreadable; refusing staple fp="
					.. cert_fp:sub(1, 16)
					.. "... server_name="
					.. (server_name or "nil")
			)
			return true
		end
		banned_hex = banned_hex:upper():gsub("^0+", "")
		if banned_hex == "" then
			banned_hex = "0"
		end
		local got = get_ocsp_serial(resp, banned_hex)
		if not got then
			safe_log(
				ERR,
				"OCSP serial blacklist present but response serial unreadable; refusing staple fp="
					.. cert_fp:sub(1, 16)
					.. "... server_name="
					.. (server_name or "nil")
			)
			return true
		end
		if got == banned_hex then
			safe_log(
				ERR,
				"OCSP serial blacklist refuse staple fp="
					.. cert_fp:sub(1, 16)
					.. "... serial_hex="
					.. banned_hex:sub(1, 16)
					.. " server_name="
					.. (server_name or "nil")
			)
			return true
		end
		return false
	end

	-- =====================================================================
	-- SECTION: freshness / death clock / intrinsic signed-window policy
	-- Meta owns expires_unix + max_age; L1 cached expires may only shorten.
	-- Constants OCSP_* above must match ocsp-refresh.py and ocsp.lua.
	-- =====================================================================
	-- Absolute nextUpdate only (expires_unix). No ISO+Ns string fallback.
	-- Prefer bunkerweb.ocsp.meta_expires_unix; local decode if module lacks it.
	local function ocsp_meta_expires_unix(meta)
		local call_ok, packed = pcall(function()
			local ocsp_mod = require "bunkerweb.ocsp"
			if ocsp_mod.meta_expires_unix then
				return { ocsp_mod.meta_expires_unix(meta) }
			end
			return { nil }
		end)
		if call_ok and packed then
			return packed[1]
		end
		if type(meta) ~= "table" then
			return nil
		end
		local u = meta.expires_unix
		if type(u) == "number" and u > 0 then
			return math.floor(u)
		end
		if type(u) == "string" then
			local n = tonumber(u)
			if n and n > 0 then
				return math.floor(n)
			end
		end
		return nil
	end

	-- Wall-clock stop from published_unix + max age (independent of nextUpdate).
	local function ocsp_meta_max_age_unix(meta)
		if type(meta) ~= "table" then
			return nil
		end
		local u = meta.max_age_unix
		if type(u) == "number" and u > 0 then
			return math.floor(u)
		end
		if type(u) == "string" then
			local n = tonumber(u)
			if n and n > 0 then
				return math.floor(n)
			end
		end
		local published = meta.published_unix
		if type(published) == "string" then
			published = tonumber(published)
		end
		if type(published) == "number" and published > 0 then
			-- Match PREVIOUS_GOOD_MAX_AGE_SECONDS in ocsp-refresh.py (24h).
			return math.floor(published) + 86400
		end
		return nil
	end

	-- Earlier of nextUpdate (expires_unix) and published+max_age wall stop.
	local function ocsp_meta_effective_expires_unix(meta)
		local exp = ocsp_meta_expires_unix(meta)
		local max_age = ocsp_meta_max_age_unix(meta)
		if exp and max_age then
			if max_age < exp then
				return max_age
			end
			return exp
		end
		return exp or max_age
	end

	-- Job-signed thisUpdate/nextUpdate policy (age + lifetime caps).
	-- Missing this_update_unix → skip (caller still needs a death clock).
	-- Fail closed on future/stale thisUpdate or absurd signed lifetime.
	local function ocsp_intrinsic_timing_ok(meta)
		if type(meta) ~= "table" then
			return true, nil
		end
		local this_u = meta.this_update_unix
		if type(this_u) == "string" then
			this_u = tonumber(this_u)
		end
		if type(this_u) ~= "number" or this_u <= 0 then
			-- No signed thisUpdate pin: retention/skew checks only (expires_unix / max_age).
			return true, nil
		end
		this_u = math.floor(this_u)
		local now = ngx.time()
		if this_u > now + OCSP_CLOCK_SKEW_SECONDS then
			return false, "thisUpdate_future"
		end
		if this_u < now - OCSP_MAX_THIS_UPDATE_AGE_SECONDS then
			return false, "thisUpdate_stale"
		end
		local next_u = meta.next_update_unix
		if type(next_u) == "string" then
			next_u = tonumber(next_u)
		end
		if type(next_u) ~= "number" or next_u <= 0 then
			next_u = ocsp_meta_expires_unix(meta)
		end
		if type(next_u) ~= "number" or next_u <= 0 then
			return false, "thisUpdate_unreadable"
		end
		next_u = math.floor(next_u)
		local lifetime = next_u - this_u
		if lifetime <= 0 then
			return false, "lifetime_invalid"
		end
		if lifetime > OCSP_MAX_INTRINSIC_LIFETIME_SECONDS then
			return false, "lifetime_too_long"
		end
		return true, nil
	end

	-- False at death time (nextUpdate/max_age minus skew).
	-- No death clock → not fresh (fail-closed). Meta owns the clock; L1 expires may only shorten.
	-- Runs ocsp_intrinsic_timing_ok when this_update_unix is present.
	local function ocsp_resp_still_fresh(expires_unix, cert_fp)
		local meta = nil
		if cert_fp then
			meta = read_ocsp_json_for_fp(cert_fp)
		end
		local ok_intrinsic, why = ocsp_intrinsic_timing_ok(meta)
		if not ok_intrinsic then
			safe_log(
				ERR,
				"OCSP intrinsic timing refuse reason="
					.. tostring(why)
					.. " fp="
					.. tostring(cert_fp and cert_fp:sub(1, 16) or "?")
					.. " server_name="
					.. (server_name or "nil")
			)
			return false, why or "unmet"
		end
		local meta_exp = ocsp_meta_expires_unix(meta)
		local max_age = ocsp_meta_max_age_unix(meta)
		local exp = meta_exp
		if exp and max_age and max_age < exp then
			exp = max_age
		elseif max_age and not exp then
			exp = max_age
		end
		if not exp then
			safe_log(
				ERR,
				"OCSP refuse staple: no expires_unix/max_age death clock fp="
					.. tostring(cert_fp and cert_fp:sub(1, 16) or "?")
					.. " server_name="
					.. (server_name or "nil")
			)
			return false, "response_stale"
		end
		-- L1 may only tighten the meta death clock, never extend past stripped meta.
		if type(expires_unix) == "number" and expires_unix > 0 and expires_unix < exp then
			exp = math.floor(expires_unix)
		end
		if ngx.time() >= exp - OCSP_CLOCK_SKEW_SECONDS then
			return false, "response_stale"
		end
		return true
	end

	-- =====================================================================
	-- SECTION: set_ocsp_from_cache — load DER, gate, validate, set_ocsp_status_resp
	--
	-- Inputs:
	--   cert_pem      leaf PEM (or nil → fingerprint-hint path from plugin status[5])
	--   cert_fp_hint  precomputed SPKI when PEM parse is deferred
	--   probe_only    true = pre-set_cert health gate (false → skip this leaf);
	--                 soft fuse never soft-continues a probe miss
	--
	-- Returns true when stapling is optional or succeeded; false when Must-Staple
	-- is unmet and mode aborts (probe_only always false on unmet).
	--
	-- Gate order on a candidate SPKI (fingerprint-hint and PEM paths share it).
	-- Post-lookup body-in-hand order is serial → shared ligand → peer refuse →
	-- floor/tombstone/paged → AIA → key-type → CertID → attach. Early Path A
	-- may peer-refuse before body exists; do not reorder post-lookup just to
	-- match a numbered list — reason strings must stay stable.
	--
	-- Allow-pin polarity: MISSING pin refuses Must-Staple. Handshake only
	-- compare-and-deletes on DROP_ALLOW refuse_cause (raw, pre-alias).
	-- Pin-state / clock / ligand_missing are KEEP_ALLOW.
	--
	-- Lookup: L1 bw2 → disk ocsp.der. Dual-cert installs only the selected leaf SPKI.
	-- staple_decision=CODE vocabulary: bunkerweb.ocsp + ssl/README.md runbook.
	-- =====================================================================
	local function set_ocsp_from_cache(cert_pem, cert_fp_hint, probe_only)
		safe_log(
			DEBUG,
			"OCSP set_ocsp_from_cache() called for server_name="
				.. (server_name or "nil")
				.. " probe_only="
				.. tostring(probe_only == true)
		)
		local now = ngx.now or ngx.time
		local hrtime = ngx.hrtime
		local floor = math.floor

		-- Prefer high-resolution timing (hrtime is nanoseconds) so we do not round small ops to 0ms.
		local function ns_since(t0)
			if hrtime then
				-- hrtime() returns nanoseconds as an integer.
				return hrtime() - t0
			end
			-- Fallback: convert seconds to nanoseconds (best effort).
			return floor((now() - t0) * 1000000000 + 0.5)
		end

		local staple_mode = get_ocsp_staple_mode()

		-- -------------------------------------------------------------------------
		-- refuse_must_staple(reason, resp) — Must-Staple policy miss.
		--
		-- Logs staple_decision=CODE (runbook). Under OCSP_STAPLE_MODE=normal may
		-- DROP_ALLOW the shared pin so siblings fail closed until re-canary.
		--
		-- Bus write rules (reviewers: this is the pin-safety gate):
		--   - probe_only → NEVER write the bus (skip_leaf demotion of one dual-cert
		--     sibling must not compare-and-delete the pin another sibling needs).
		--   - soft fuse (staple_only|open) → NEVER write (recovery must not poison).
		--   - normal attach path → record_peer_refuse unless should_skip_peer_bus.
		--   - skip_bus defaults false on pcall throw (fail closed = may DROP).
		--
		-- probe_only always returns false (demote this leaf). Soft fuse after
		-- install returns true (continue unstapled); normal returns false → abort.
		-- -------------------------------------------------------------------------
		local active_refuse_fp = nil
		local function refuse_must_staple(reason, resp)
			local action = "abort"
			if staple_mode == "staple_only" or staple_mode == "open" then
				action = "continue"
			end
			-- Pre-set_cert probe: never install a Must-Staple leaf without a live shard.
			-- Soft fuse only softens handshake abort after install, not this skip gate.
			if probe_only then
				action = "abort"
			end
			state.abort_must_staple_detail = tostring(reason or "unmet")
			-- Soft fuse continues this handshake; do not poison the HTTP↔stream bus.
			-- probe_only demotions (skip_leaf) must never write the allow-pin bus —
			-- an intermediate capability gap must not compare-and-delete the leaf pin.
			local cert_fp = active_refuse_fp
			if
				not probe_only
				and staple_mode == "normal"
				and type(cert_fp) == "string"
				and is_fp64_lower_hex(cert_fp)
			then
				local d = reason or "unmet"
				local meta = read_ocsp_json_for_fp(cert_fp)
				-- Fail closed: skip_bus stays false unless should_skip_peer_bus returns true.
				-- A pcall throw must not default to "keep the pin" (opposite of peer_refuse_unavailable).
				local skip_bus = false
				local bus_ok, bus_err = pcall(function()
					local ocsp_mod = require "bunkerweb.ocsp"
					if ocsp_mod.should_skip_peer_bus then
						skip_bus = ocsp_mod.should_skip_peer_bus(d, meta, cert_fp) == true
					end
					if not skip_bus and ocsp_mod.record_peer_refuse then
						ocsp_mod.record_peer_refuse(cert_fp, meta, d, resp)
					end
				end)
				if not bus_ok then
					safe_log(
						ERR,
						"OCSP peer-bus pcall failed refuse_cause="
							.. tostring(d)
							.. " err="
							.. tostring(bus_err)
							.. " server_name="
							.. (server_name or "nil")
					)
				end
			end
			safe_log(
				ERR,
				format_staple_decision(reason or "unmet", {
					tag = "OCSP_MUST_STAPLE_REFUSE",
					action = probe_only and "skip_leaf" or action,
					mode = tostring(staple_mode),
					detail = tostring(reason or "unmet"),
					server_name = server_name or "nil",
				})
			)
			if probe_only then
				return false
			end
			return action == "continue"
		end

		-- Allow-pin gate: missing/mismatched/expired pin refuses Must-Staple.
		-- Returns the decision string (caller refuses without re-validate).
		-- Require / peer_refuse_blocks errors fail closed (peer_refuse_unavailable)
		-- so a silent pcall cannot walk Must-Staple past the gate.
		local function peer_generation_refused(resp)
			local cert_fp = active_refuse_fp
			if type(cert_fp) ~= "string" or not is_fp64_lower_hex(cert_fp) then
				return nil
			end
			local call_ok, packed = pcall(function()
				local ocsp_mod = require "bunkerweb.ocsp"
				if ocsp_mod.peer_refuse_blocks then
					return ocsp_mod.peer_refuse_blocks(cert_fp, read_ocsp_json_for_fp(cert_fp), resp)
				end
				return "peer_refuse_unavailable"
			end)
			if not call_ok then
				return "peer_refuse_unavailable"
			end
			return packed
		end

		-- Stapling disabled by site settings (not a Must-Staple refuse).
		local function log_stapling_off(reason)
			safe_log(
				DEBUG,
				format_staple_decision("stapling_off", {
					tag = "OCSP_STAPLING_OFF",
					detail = tostring(reason or "ssl_use_ocsp_stapling_no"),
					server_name = server_name or "nil",
				})
			)
		end

		local pem_ok = type(cert_pem) == "string" and #cert_pem > 0
		local fp_hint = nil
		if type(cert_fp_hint) == "string" then
			local fp = cert_fp_hint:lower()
			if is_fp64_lower_hex(fp) then
				fp_hint = fp
			end
		end

		-- ---------------------------------------------------------------------
		-- PATH A: fingerprint-hint only (no leaf PEM — plugin gave status[5]).
		-- Cannot run ngx.ocsp.validate without PEM; authorize via ocsp.json ligand.
		-- Must-Staple still enforced from job-written must_staple pin.
		-- ---------------------------------------------------------------------
		-- No usable PEM (nil, empty, or ngx.ssl cdata). Fall back to plugin fingerprint hint
		-- (status[5]) so Must-Staple from ocsp.json is still enforced.
		if not pem_ok then
			if cert_pem ~= nil and type(cert_pem) ~= "string" then
				safe_log(
					NOTICE,
					"OCSP cannot fingerprint cdata certificate pointer (type="
						.. type(cert_pem)
						.. ") for "
						.. (server_name or "unknown")
						.. " - using fingerprint hint if available"
				)
			else
				safe_log(
					DEBUG,
					"OCSP no PEM string for " .. (server_name or "unknown") .. " - using fingerprint hint if available"
				)
			end
			if not fp_hint then
				safe_log(
					NOTICE,
					"OCSP skipped: no PEM and no fingerprint hint for "
						.. (server_name or "unknown")
						.. " - Cannot enforce Must-Staple"
				)
				-- Probe: demote this leaf (never install without a bindable SPKI).
				-- Post-install: skip staple; Must-Staple is enforced by harvesting
				-- status[3]/[5] and running probe_only even when ngx.ocsp is nil.
				if probe_only then
					return false
				end
				return true
			end

			active_refuse_fp = fp_hint
			-- Open mode: clear Must-Staple BEFORE peer / stapling-off / ngx.ocsp
			-- (same contract as PATH B). Otherwise probe_only under open/stapling-off
			-- demotes every fingerprint leaf while the PEM path would keep them.
			local has_must_staple = ocsp_json_must_staple(fp_hint)
			if has_must_staple then
				safe_log(
					INFO,
					"OCSP-Must-Staple from ocsp.json for fp="
						.. fp_hint:sub(1, 16)
						.. "... server_name="
						.. (server_name or "nil")
				)
			end
			if staple_mode == "open" then
				if has_must_staple then
					safe_log(
						NOTICE,
						"OCSP_STAPLE_MODE=open - Must-Staple enforcement disabled server_name="
							.. (server_name or "nil")
					)
				end
				has_must_staple = false
			else
				-- Fail closed: unknown (no ocsp.json / resty) refuses like proven MS.
				has_must_staple = leaf_fail_closed_must_staple(cert_pem, fp_hint)
			end

			do
				local peer_dec = peer_generation_refused(nil)
				if peer_dec then
					if has_must_staple then
						return refuse_must_staple(peer_dec)
					end
					return true
				end
			end

			if has_must_staple and cluster_floor_blocks(fp_hint, read_ocsp_json_for_fp(fp_hint)) then
				return refuse_must_staple("cluster_floor")
			end
			do
				local hint_meta = read_ocsp_json_for_fp(fp_hint)
				if meta_tombstoned(hint_meta) then
					ocsp_l1_drop(
						fp_hint,
						"/var/cache/bunkerweb/ssl/"
							.. fp_hint:sub(1, 1)
							.. "/"
							.. fp_hint:sub(2, 2)
							.. "/"
							.. fp_hint
							.. "/ocsp.der"
					)
					if has_must_staple then
						return refuse_must_staple("tombstoned")
					end
					return true
				end
				if shard_not_paged(hint_meta) then
					if has_must_staple then
						return refuse_must_staple("not_paged")
					end
					return true
				end
			end
			do
				local blocks, aia_why = aia_uri_pin_blocks(fp_hint, nil, has_must_staple)
				if blocks then
					if has_must_staple then
						return refuse_must_staple(aia_why or "aia_uri_mismatch")
					end
					return true
				end
			end

			if not is_ocsp_stapling_enabled() then
				if has_must_staple then
					return refuse_must_staple("ssl_use_ocsp_stapling_no")
				end
				log_stapling_off("ssl_use_ocsp_stapling_no")
				return true
			end
			if not ocsp then
				if has_must_staple then
					return refuse_must_staple("ngx_ocsp_unavailable")
				end
				log_stapling_off("ngx_ocsp_unavailable")
				return true
			end

			local ocsp_dir = "/var/cache/bunkerweb/ssl/"
				.. fp_hint:sub(1, 1)
				.. "/"
				.. fp_hint:sub(2, 2)
				.. "/"
				.. fp_hint
			local ocsp_path = ocsp_dir .. "/ocsp.der"
			local resp = nil
			local fresh_refuse_why = nil

			local cache_result, ocsp_verified, cache_epoch, cache_expires, cache_gen = ocsp_l1_get(fp_hint)
			if type(cache_result) == "string" and #cache_result > 0 then
				if not ocsp_l1_matches_disk(fp_hint, ocsp_dir, ocsp_path, cache_result, cache_epoch) then
					ocsp_l1_drop(fp_hint, ocsp_path)
				else
					local fresh, fresh_why = ocsp_resp_still_fresh(cache_expires, fp_hint)
					if not fresh then
						safe_log(
							ERR,
							"OCSP L1 response past nextUpdate/expires; discarding fp="
								.. fp_hint:sub(1, 16)
								.. "... server_name="
								.. (server_name or "nil")
						)
						ocsp_l1_drop(fp_hint, ocsp_path)
						fresh_refuse_why = fresh_why or "response_stale"
					else
						local live_gen = ocsp_live_soft_recall_gen(fp_hint)
						local verified = ocsp_verified_for_resp(ocsp_verified, cache_result, cache_gen, live_gen)
						local authorized = false
						if not verified then
							authorized = ocsp_json_authorizes_resp(fp_hint, cache_result)
						end
						if verified or authorized then
							resp = cache_result
							-- Do not promote fingerprint-only accepts to ocsp_verified
							-- (that requires PEM + validate_ocsp_response). Skip L1 put
							-- during probe_only (losing leaves must not warm shared L1).
							if not verified and not probe_only then
								local exp = cache_expires
									or ocsp_meta_effective_expires_unix(read_ocsp_json_for_fp(fp_hint))
								ocsp_l1_put(fp_hint, cache_result, nil, exp, cache_epoch, live_gen)
							end
						end
					end
				end
			end

			if not resp then
				pcall(function()
					local f = io.open(ocsp_path, "rb")
					if not f then
						return
					end
					local data = f:read("*a")
					f:close()
					if type(data) ~= "string" or #data == 0 then
						return
					end
					local fresh, fresh_why = ocsp_resp_still_fresh(nil, fp_hint)
					if not fresh then
						safe_log(
							ERR,
							"OCSP disk response past nextUpdate/expires; refusing staple fp="
								.. fp_hint:sub(1, 16)
								.. "... server_name="
								.. (server_name or "nil")
						)
						fresh_refuse_why = fresh_why or "response_stale"
						return
					end
					local _, disk_verified, _, _, disk_gen = ocsp_l1_get(fp_hint)
					-- No leaf PEM: prior crypto-verified binding, or job meta that
					-- binds fingerprint + der_sha256 to these exact DER bytes.
					local live_gen = ocsp_live_soft_recall_gen(fp_hint)
					local verified = ocsp_verified_for_resp(disk_verified, data, disk_gen, live_gen)
					local authorized = false
					if not verified then
						authorized = ocsp_json_authorizes_resp(fp_hint, data)
					end
					if verified or authorized then
						resp = data
						if not probe_only then
							local exp = ocsp_meta_effective_expires_unix(read_ocsp_json_for_fp(fp_hint))
							ocsp_l1_put(fp_hint, data, verified and ocsp_resp_binding(data) or nil, exp, nil, live_gen)
						end
					end
				end)
			end

			if not resp then
				safe_log(
					DEBUG,
					"OCSP response not found for fingerprint hint fp="
						.. fp_hint:sub(1, 16)
						.. "... server_name="
						.. (server_name or "nil")
				)
				if has_must_staple then
					return refuse_must_staple(fresh_refuse_why or "response_not_found")
				end
				return true
			end
			if serial_blacklist_blocks(fp_hint, resp) then
				if has_must_staple then
					return refuse_must_staple("serial_blacklisted")
				end
				return true
			end
			if has_must_staple then
				local ligand_ok, ligand_reason = must_staple_binds_shared_ligand(fp_hint, resp)
				if not ligand_ok then
					return refuse_must_staple(ligand_reason or "shared_ligand")
				end
			end

			-- No handshake leaf PEM on this path: require response serial == pinned CertID.
			do
				local meta = read_ocsp_json_for_fp(fp_hint)
				local meta_serial = nil
				if meta and type(meta.certid) == "table" then
					meta_serial = canonical_serial_hex(meta.certid.serial)
				elseif meta then
					meta_serial = canonical_serial_hex(meta.serial)
				end
				local resp_serial = get_ocsp_serial(resp, meta_serial)
				if not meta_serial or not resp_serial or meta_serial ~= resp_serial then
					safe_log(
						ERR,
						"OCSP CertID refuse fingerprint staple (meta/response serial) fp="
							.. fp_hint:sub(1, 16)
							.. "... server_name="
							.. (server_name or "nil")
					)
					if has_must_staple then
						return refuse_must_staple("certid_mismatch")
					end
					return true
				end
			end

			if probe_only then
				-- PATH A probe (fingerprint hint, often no fullchain PEM).
				-- Fingerprint-only Must-Staple cannot prove intermediate readiness
				-- without PEM → refuse. issuer_path module miss / pcall throw is
				-- scoped by leaf_fail_closed_must_staple: non-MS stays viable
				-- (OCSP_MODULE_DEGRADED); MS/unknown demote.
				if has_must_staple and type(cert_pem) ~= "string" then
					return refuse_must_staple("fingerprint_chain_unavailable")
				end
				local ms_gate = leaf_fail_closed_must_staple(cert_pem, fp_hint)
				local path_ok, path_detail = true, nil
				local path_call_ok, path_a, path_b = pcall(function()
					local ocsp_mod = require "bunkerweb.ocsp"
					if not ocsp_mod.issuer_path_intermediate_ready then
						if ms_gate then
							return false, "issuer_path_unavailable"
						end
						return true, nil
					end
					if type(cert_pem) ~= "string" then
						if ms_gate then
							return false, "fingerprint_chain_unavailable"
						end
						return true, nil
					end
					return ocsp_mod.issuer_path_intermediate_ready(cert_pem)
				end)
				if not path_call_ok then
					if ms_gate then
						path_ok, path_detail = false, "issuer_path_unavailable"
					else
						safe_log(
							NOTICE,
							"OCSP_MODULE_DEGRADED action=serve_unstapled detail=issuer_path_pcall server_name="
								.. (server_name or "nil")
						)
						path_ok = true
					end
				else
					path_ok, path_detail = path_a, path_b
				end
				if path_ok == false then
					return refuse_must_staple(path_detail or "unmet")
				end
				return true
			end
			local ok_set, set_ok, set_err
			ok_set = pcall(function()
				-- Missing module must take the exception path (Must-Staple refuse), not plain attach.
				local ocsp_mod = assert(cwd, "bunkerweb.ocsp unavailable")
				if ocsp_mod.attach_ocsp_staple then
					-- Fingerprint-only: no fullchain → cannot scan intermediate Must-Staple.
					set_ok, set_err = ocsp_mod.attach_ocsp_staple(resp, nil)
				else
					set_ok, set_err = ocsp.set_ocsp_status_resp(resp)
				end
			end)
			if not ok_set then
				safe_log(ERR, "OCSP set_ocsp_status_resp exception: " .. tostring(set_ok))
				if has_must_staple then
					return refuse_must_staple("set_staple_exception")
				end
				return true
			end
			if not set_ok then
				safe_log(ERR, "OCSP set_ocsp_status_resp failed: " .. tostring(set_err))
				if
					set_err == "intermediate_must_staple_libssl"
					or set_err == "intermediate_must_staple_colony"
					or has_must_staple
				then
					return refuse_must_staple(
						(set_err == "intermediate_must_staple_libssl" or set_err == "intermediate_must_staple_colony")
								and set_err
							or "set_staple_failed"
					)
				end
				return true
			end
			log_ocsp_stapled(nil, fp_hint, resp)
			return true
		end

		-- ---------------------------------------------------------------------
		-- PATH B: leaf PEM available — full Must-Staple from TLS Feature (or
		-- ocsp.json fallback), dual-cert leaf pick, L1→disk, validate, attach.
		--
		-- Early-bind contract (reviewers): resolve_leaf runs FIRST so every
		-- subsequent gate (open-mode clear, peer refuse, stapling-off, ngx.ocsp
		-- missing, fingerprint walk) agrees on the same leaf SPKI + Must-Staple
		-- verdict. Late bind used to let stapling-off return true before MS was
		-- known, or let blocks[1] overwrite a correct status[5] leaf.
		-- ---------------------------------------------------------------------
		-- Resolve the handshake leaf ONCE before any gate so peer / stapling-off /
		-- ngx.ocsp / open-mode all see the same Must-Staple verdict and fingerprint.
		local t_total_start = hrtime and hrtime() or now()
		local t_resolve_start = hrtime and hrtime() or now()
		local leaf_for_meta, leaf_fp_resolved, resolved_blocks, resolved_fp_to_pem =
			resolve_leaf(cert_pem, cert_fp_hint or fp_hint)
		safe_log(
			DEBUG,
			"OCSP resolve_leaf time_ns="
				.. tostring(ns_since(t_resolve_start))
				.. " leaf_fp="
				.. ((type(leaf_fp_resolved) == "string" and leaf_fp_resolved:sub(1, 16) .. "...") or "nil")
				.. " server_name="
				.. (server_name or "nil")
		)
		if type(leaf_for_meta) ~= "string" or #leaf_for_meta == 0 then
			leaf_for_meta = cert_pem
		end
		local has_must_staple = false
		local t_meta_start = hrtime and hrtime() or now()
		local ok_read, cert_meta = pcall(read_certificate_metadata, leaf_for_meta)
		safe_log(
			DEBUG,
			"OCSP read_certificate_metadata time_ns="
				.. tostring(ns_since(t_meta_start))
				.. " server_name="
				.. (server_name or "nil")
		)
		if ok_read and cert_meta then
			has_must_staple = cert_meta.must_staple
			if has_must_staple then
				safe_log(INFO, "OCSP-Must-Staple extension detected in certificate for " .. (server_name or "unknown"))
			end
			-- Keyed by the PEM it came from: the fingerprint walk validates other leaves
			-- (dual RSA+ECDSA) whose issuer differs.
			if cert_meta.issuer_name and ngx.ctx then
				ngx.ctx.bw_ocsp_issuer_dn = { pem = leaf_for_meta, dn = cert_meta.issuer_name }
			end
		end
		-- When resty cannot see TLS Feature, honor Must-Staple from job-written ocsp.json.
		if not has_must_staple and type(leaf_fp_resolved) == "string" and is_fp64_lower_hex(leaf_fp_resolved) then
			if ocsp_json_must_staple(leaf_fp_resolved) then
				has_must_staple = true
				safe_log(
					INFO,
					"OCSP-Must-Staple from ocsp.json for fp="
						.. leaf_fp_resolved:sub(1, 16)
						.. "... server_name="
						.. (server_name or "unknown")
				)
			end
		end
		-- Bind allow-pin / peer bus to the resolved leaf (covers PEM-string plugins with no hint).
		if type(leaf_fp_resolved) == "string" and is_fp64_lower_hex(leaf_fp_resolved) then
			active_refuse_fp = leaf_fp_resolved
		elseif fp_hint then
			active_refuse_fp = fp_hint
		end
		-- Open mode: clear Must-Staple BEFORE peer / stapling-off / ngx.ocsp gates
		-- so probe_only cannot demote leaves under the recovery fuse (open is
		-- "serve unstapled", not "fail every leaf that cannot staple").
		if has_must_staple and staple_mode == "open" then
			safe_log(
				NOTICE,
				"OCSP_STAPLE_MODE=open - Must-Staple enforcement disabled server_name=" .. (server_name or "nil")
			)
			has_must_staple = false
		elseif staple_mode ~= "open" then
			-- Fail closed: unknown MS (resty miss + no trustworthy ocsp.json) must
			-- refuse shard miss like proven Must-Staple — do not treat unknown as false.
			has_must_staple = leaf_fail_closed_must_staple(leaf_for_meta or cert_pem, leaf_fp_resolved or fp_hint)
		end
		-- Dual-cert health: score this leaf's issuer-linked intermediates (not leaf shard alone).
		-- Early so non-Must-Staple `return true` paths cannot pick a poisoned path. Legal
		-- ok_partial NULL slots pass; Must-Staple intermediates without body demote.
		-- Same scoped fail-closed as PATH A / dual-cert loop (leaf_fail_closed_must_staple).
		if probe_only and staple_mode ~= "open" then
			local ms_gate = leaf_fail_closed_must_staple(cert_pem, leaf_fp_resolved or fp_hint)
			local path_ok, path_detail = true, nil
			local path_call_ok, path_a, path_b = pcall(function()
				local ocsp_mod = require "bunkerweb.ocsp"
				if not ocsp_mod.issuer_path_intermediate_ready then
					if ms_gate then
						return false, "issuer_path_unavailable"
					end
					return true, nil
				end
				return ocsp_mod.issuer_path_intermediate_ready(cert_pem)
			end)
			if not path_call_ok then
				if ms_gate then
					path_ok, path_detail = false, "issuer_path_unavailable"
				else
					safe_log(
						NOTICE,
						"OCSP_MODULE_DEGRADED action=serve_unstapled detail=issuer_path_pcall server_name="
							.. (server_name or "nil")
					)
					path_ok = true
				end
			else
				path_ok, path_detail = path_a, path_b
			end
			if path_ok == false then
				safe_log(
					DEBUG,
					"OCSP probe_only demoted: issuer path not ready detail="
						.. tostring(path_detail)
						.. " server_name="
						.. (server_name or "nil")
				)
				return refuse_must_staple(path_detail or "unmet")
			end
		end
		do
			local peer_dec = peer_generation_refused(nil)
			if peer_dec then
				if has_must_staple then
					return refuse_must_staple(peer_dec)
				end
				return true
			end
		end

		if not is_ocsp_stapling_enabled() then
			if has_must_staple then
				return refuse_must_staple("ssl_use_ocsp_stapling_no")
			end
			log_stapling_off("ssl_use_ocsp_stapling_no")
			return true
		end

		-- Fail fast if ngx.ocsp module is not available.
		if not ocsp then
			if has_must_staple then
				return refuse_must_staple("ngx_ocsp_unavailable")
			end
			log_stapling_off("ngx_ocsp_unavailable")
			return true
		end
		-- Compute certificate public key fingerprint(s) (unique identifiers).
		-- Prefer resolve_leaf result; reuse its block map when present.
		local t_fp_phase_start = hrtime and hrtime() or now()
		local resp = nil
		local resp_fp = nil
		local tried_fps = {}
		local candidate_fps = {}
		local fp_to_cert_pem = resolved_fp_to_pem or {}
		local chain_certs = resolved_blocks
		if type(chain_certs) ~= "table" or #chain_certs == 0 then
			chain_certs = parse_pem_certificates(cert_pem)
			if not chain_certs or #chain_certs == 0 then
				chain_certs = { cert_pem }
			end
		end

		-- Prefer pre-computed / resolved fingerprint.
		if type(leaf_fp_resolved) == "string" and is_fp64_lower_hex(leaf_fp_resolved) then
			candidate_fps[#candidate_fps + 1] = leaf_fp_resolved
			tried_fps[leaf_fp_resolved] = true
			if not fp_to_cert_pem[leaf_fp_resolved] then
				fp_to_cert_pem[leaf_fp_resolved] = leaf_for_meta
			end
		elseif cert_fp_hint and type(cert_fp_hint) == "string" then
			local fp = tostring(cert_fp_hint):lower()
			if is_fp64_lower_hex(fp) and not tried_fps[fp] then
				candidate_fps[#candidate_fps + 1] = fp
				tried_fps[fp] = true
			end
		end

		local t_parse_chain_start = hrtime and hrtime() or now()
		safe_log(
			DEBUG,
			"OCSP parse_pem_certificates(chain) time_ns="
				.. tostring(ns_since(t_parse_chain_start))
				.. " server_name="
				.. (server_name or "nil")
		)

		-- Map subject DN to PEM so issuer lookup can pick the signing certificate
		-- instead of trying every block. resty and the validator use the same tostring(name).
		-- OPTIMIZATION: Cache chain mappings (Priority 7) — skip FFI parsing on identical chains
		local chain_subject_to_pem, chain_issuer_subjects = chain_mapping_cache_get(chain_certs)

		if not chain_subject_to_pem then
			-- Cache miss: build the mappings via FFI parsing
			chain_subject_to_pem = {}
			chain_issuer_subjects = {}
			if has_resty_ssl and resty_x509 and resty_x509.new then
				for _, cert_block_pem in ipairs(chain_certs) do
					pcall(function()
						local cert_obj = resty_x509.new(cert_block_pem)
						if cert_obj and cert_obj.get_subject_name then
							local subject = cert_obj:get_subject_name()
							if subject then
								chain_subject_to_pem[tostring(subject)] = cert_block_pem
							end
						end
						if cert_obj and cert_obj.get_issuer_name then
							local issuer = cert_obj:get_issuer_name()
							if issuer then
								chain_issuer_subjects[tostring(issuer)] = true
							end
						end
					end)
				end
			end

			-- Store in cache for future handshakes with identical chain
			chain_mapping_cache_set(chain_certs, chain_subject_to_pem, chain_issuer_subjects)

			safe_log(
				DEBUG,
				"OCSP chain mapping cache miss: built subject-to-pem for "
					.. tostring(#chain_certs)
					.. " cert(s) server_name="
					.. (server_name or "nil")
			)
		else
			safe_log(
				DEBUG,
				"OCSP chain mapping cache hit: reused subject-to-pem for "
					.. tostring(#chain_certs)
					.. " cert(s) server_name="
					.. (server_name or "nil")
			)
		end

		local der_chain_cache = {}
		if #chain_certs > 1 then
			safe_log(
				DEBUG,
				"OCSP will try multiple certificate blocks from chain of "
					.. #chain_certs
					.. " certificate(s) server_name="
					.. (server_name or "nil")
			)
		end

		-- Add fingerprints for each certificate block (may include the real leaf and intermediates)
		local t_fp_candidates_start = hrtime and hrtime() or now()
		for idx, cert_block_pem in ipairs(chain_certs) do
			local fp = get_ocsp_pubkey_fingerprint(cert_block_pem)
			if fp then
				-- Ensure we keep the PEM block for each computed fingerprint, even
				-- if it was already present from a plugin fingerprint hint.
				if not fp_to_cert_pem[fp] then
					fp_to_cert_pem[fp] = cert_block_pem
				end
				if not tried_fps[fp] then
					candidate_fps[#candidate_fps + 1] = fp
					tried_fps[fp] = true
				end
			end
			if type(fp) == "string" then
				safe_log(
					DEBUG,
					"OCSP cert block #"
						.. idx
						.. " pem_len="
						.. tostring(#cert_block_pem)
						.. " fp="
						.. fp:sub(1, 16)
						.. "... server_name="
						.. (server_name or "nil")
				)
			else
				safe_log(
					DEBUG,
					"OCSP cert block #"
						.. idx
						.. " pem_len="
						.. tostring(cert_block_pem and #cert_block_pem or 0)
						.. " fp=nil server_name="
						.. (server_name or "nil")
				)
			end
		end
		safe_log(
			DEBUG,
			"OCSP candidate_fps compute time_ns="
				.. tostring(ns_since(t_fp_candidates_start))
				.. " server_name="
				.. (server_name or "nil")
		)

		if cert_fp_hint and type(cert_fp_hint) == "string" then
			safe_log(
				DEBUG,
				"OCSP cert_fp_hint=" .. (cert_fp_hint:sub(1, 16) .. "...") .. " server_name=" .. (server_name or "nil")
			)
		else
			safe_log(DEBUG, "OCSP cert_fp_hint=nil server_name=" .. (server_name or "nil"))
		end

		safe_log(
			DEBUG,
			"OCSP candidate_fps count=" .. tostring(#candidate_fps) .. " server_name=" .. (server_name or "nil")
		)

		-- Must-Staple already bound above from resolve_leaf; do not re-promote from
		-- intermediate chain blocks.

		if #candidate_fps == 0 then
			safe_log(NOTICE, "OCSP could not compute any certificate fingerprints for " .. (server_name or "unknown"))
			if has_must_staple then
				return refuse_must_staple("fingerprint_unavailable")
			end
			return true
		end

		-- ngx.ocsp.validate_ocsp_response for this SPKI (+ issuer when available).
		-- Returns: true = crypto OK (cache verified); false = rejected; nil = skipped.
		--
		-- Canary trust: if ocsp.json is paged=true and der_sha256 matches the body,
		-- skip validate entirely (openssl CLI canary already proved; FFI disagreement
		-- must not unpage). CertID + set_ocsp_status_resp still run on attach.
		--
		-- When validate runs: soft ~700ms total budget, ≤4 issuer candidates, leaf
		-- only — intermediates attach later from canary-paged shards (or NULL →
		-- ok_partial). Budget miss → validate_budget (no poison, no peer bus).
		-- Job-written issuer.pem is tried first and pins acceptable issuer SPKI.
		local function ocsp_validate_response_for_fp(cert_fp, cert_for_fp_pem, ocsp_der)
			local t_fn_start_hr = hrtime and hrtime() or nil
			local t_fn_start_sec = now()
			safe_log(
				DEBUG,
				"OCSP ocsp_validate_response_for_fp start fp="
					.. tostring(cert_fp and cert_fp:sub(1, 16) .. "...")
					.. " server_name="
					.. (server_name or "nil")
			)
			-- Declared before finish() so the closure captures this local, not a global.
			local der_binding = nil
			local function finish(retv)
				local time_ns = nil
				if t_fn_start_hr then
					time_ns = hrtime() - t_fn_start_hr
				end
				-- `ngx.hrtime()` can be too fine/granular to show movement (sometimes 0); log us/ms too.
				local time_us = floor(((now() - t_fn_start_sec) * 1000000) + 0.5)
				local time_ms = floor(((now() - t_fn_start_sec) * 1000) + 0.5)
				safe_log(
					DEBUG,
					"OCSP ocsp_validate_response_for_fp end fp="
						.. tostring(cert_fp and cert_fp:sub(1, 16) .. "...")
						.. " result="
						.. tostring(retv)
						.. " time_ns="
						.. tostring(time_ns)
						.. " time_us="
						.. tostring(time_us)
						.. " time_ms="
						.. tostring(time_ms)
						.. " server_name="
						.. (server_name or "nil")
				)

				-- Only successes are cached: false also covers transient outcomes (no issuer.pem
				-- yet, budget abort) that must retry. Definitive rejects use the DER-bound poison.
				if retv == true and der_binding then
					ocsp_validation_cache_set(cert_fp, der_binding, retv)
				end

				return retv
			end

			if not ocsp then
				return finish(false)
			end
			-- Do not require resty.openssl.x509 for validation.
			-- We can still build the DER chain via ngx.ssl and validate via ngx.ocsp.
			if not ssl or not ssl.cert_pem_to_der then
				return finish(false)
			end
			if not cert_for_fp_pem or type(cert_for_fp_pem) ~= "string" then
				return finish(false)
			end

			-- If validation previously failed for this exact OCSP body, skip re-verify briefly.
			-- Bind poison to sha256(DER) so a job-published replacement auto-misses the latch.
			local ocsp_validate_failed_key = "TLS:SSL:ocsp_validate_failed:" .. cert_fp
			local stored_poison = nil
			pcall(function()
				stored_poison = internalstore:get(ocsp_validate_failed_key, true)
			end)

			der_binding = ocsp_resp_binding(ocsp_der)
			if stored_poison and der_binding == stored_poison then
				return finish(false)
			end

			-- OPTIMIZATION: Check per-worker validation cache before expensive FFI crypto
			-- Cache key: cert_fp | ocsp_resp_binding(der)
			-- TTL: 60 seconds (same as poison TTL)
			-- Savings: 1-3ms per cached validation (FFI RSA/ECDSA verify skipped)
			if der_binding then
				local cached_result = ocsp_validation_cache_get(cert_fp, der_binding)
				if cached_result ~= nil then
					safe_log(
						DEBUG,
						"OCSP validation cache hit fp="
							.. tostring(cert_fp and cert_fp:sub(1, 16) .. "...")
							.. " result="
							.. tostring(cached_result)
							.. " server_name="
							.. (server_name or "nil")
					)
					return finish(cached_result)
				end
			end

			-- Trust scheduler canary (openssl CLI + ligands, paged=true) for crypto verify
			-- so CLI vs ngx.ocsp.validate_ocsp_response disagreement cannot unpage a live shard.
			-- canary_paged_body_ok also requires a live allow-pin generation match (soft-fuse /
			-- pin revoke must not keep skip-validate alive on ligand bits alone).
			-- set_ocsp_status_resp / CertID gates still run on the attach path.
			do
				local meta = read_ocsp_json_for_fp(cert_fp)
				local ocsp_mod = nil
				pcall(function()
					ocsp_mod = require "bunkerweb.ocsp"
				end)
				if
					ocsp_mod
					and ocsp_mod.canary_paged_body_ok
					and ocsp_mod.canary_paged_body_ok(meta, cert_fp, ocsp_der)
				then
					safe_log(
						DEBUG,
						"OCSP trusting canary-paged body; skipping ngx.ocsp.validate_ocsp_response for fp="
							.. tostring(cert_fp and cert_fp:sub(1, 16) .. "...")
							.. " server_name="
							.. (server_name or "nil")
					)
					pcall(function()
						internalstore:delete(ocsp_validate_failed_key)
					end)
					return finish(true)
				end
			end

			local ocsp_validate_failure_ttl = 60
			-- 700ms budget across issuer attempts; must match ocsp.lua OCSP_VALIDATE_BUDGET_NS/_S.
			-- Compare in the clock's own unit: hrtime is ns, the now() fallback is seconds.
			local ocsp_validate_timeout_total_ns = 700000000
			local ocsp_validate_timeout_total_s = 0.7
			local ocsp_validate_max_issuer_candidates = 4
			-- Budget clock. ngx.now() is cached per event-loop tick and validate never
			-- yields, so refresh it or elapsed time stays 0 and the budget never fires.
			local function ocsp_validate_clock()
				if hrtime then
					return hrtime()
				end
				if ngx.update_time then
					ngx.update_time()
				end
				return now()
			end
			local ocsp_validate_budget = hrtime and ocsp_validate_timeout_total_ns or ocsp_validate_timeout_total_s
			local t_val_total_start = ocsp_validate_clock()
			local issuer_name = nil

			local cached_dn = ngx.ctx and ngx.ctx.bw_ocsp_issuer_dn
			if cached_dn and cached_dn.pem == cert_for_fp_pem then
				issuer_name = cached_dn.dn
			elseif has_resty_ssl and resty_x509 and resty_x509.new then
				-- Fallback: Optional fast-path: use resty.openssl to derive issuer DN.
				local leaf_cert_obj = resty_x509.new(cert_for_fp_pem)
				if leaf_cert_obj then
					local issuer_name_obj = leaf_cert_obj:get_issuer_name()
					if issuer_name_obj then
						issuer_name = tostring(issuer_name_obj)
					end
				end
			end

			-- ngx.ocsp.validate_ocsp_response needs the issuer certificate. A full chain
			-- supplies it. A leaf-only PEM does not, so fall back to issuer.pem written
			-- by ocsp-refresh.py next to ocsp.der (the issuer used when the response was verified).
			-- OPTIMIZATION: Cache issuer.pem reads in per-worker cache (Priority 8)
			-- Eliminates file I/O on repeat validations of same cert
			local function read_stored_issuer_pem(fp)
				if not is_fp64_lower_hex(fp) then
					return nil
				end

				-- OPTIMIZATION: Check cache first to avoid file I/O
				local cached_pem = stored_issuer_cache_get(fp)
				if cached_pem ~= nil then
					-- Cache hit: pem is either string (found) or false (not found on disk)
					if cached_pem == false then
						return nil
					end
					safe_log(
						DEBUG,
						"OCSP stored issuer cache hit fp=" .. fp:sub(1, 16) .. "... server_name=" .. (server_name or "nil")
					)
					return cached_pem
				end

				-- Cache miss: read from disk
				local issuer_path = "/var/cache/bunkerweb/ssl/"
					.. fp:sub(1, 1)
					.. "/"
					.. fp:sub(2, 2)
					.. "/"
					.. fp
					.. "/issuer.pem"
				local issuer_pem = nil
				pcall(function()
					local f = io.open(issuer_path, "r")
					if not f then
						return
					end
					issuer_pem = f:read("*a")
					f:close()
				end)

				local result = nil
				if issuer_pem and #issuer_pem > 0 then
					result = issuer_pem
				else
					result = false  -- Mark as "not found" for cache
				end

				-- Store in cache: either PEM string or false (not found)
				stored_issuer_cache_set(fp, result)

				if result == false then
					return nil
				end
				return result
			end

			-- Try to validate against multiple possible issuer certificates.
			-- ngx.ocsp.validate_ocsp_response() verifies the OCSP signature and binds it to the
			-- certificate via OCSP CertID, so we can safely try issuers in any order.
			local issuer_pems_to_try = {}
			local seen_issuer = {}
			if issuer_name then
				local issuer_pem = chain_subject_to_pem and chain_subject_to_pem[issuer_name] or nil
				if issuer_pem then
					issuer_pems_to_try[1] = issuer_pem
					seen_issuer[issuer_pem] = true
				end
			end
			if chain_certs then
				for _, cert_block_pem in ipairs(chain_certs) do
					if cert_block_pem and cert_block_pem ~= cert_for_fp_pem then
						-- Avoid duplicates when the DN-mapped issuer is already added.
						if not seen_issuer[cert_block_pem] then
							issuer_pems_to_try[#issuer_pems_to_try + 1] = cert_block_pem
							seen_issuer[cert_block_pem] = true
						end
					end
				end
			end

			-- Always put the job-written issuer first. When it exists, only accept that
			-- issuer SPKI (or an identical re-encoding) — never validate against a different CA.
			local stored_issuer = read_stored_issuer_pem(cert_fp)
			if stored_issuer and #stored_issuer > 0 then
				local want_spki = get_ocsp_pubkey_fingerprint(stored_issuer)
				local compacted = {}
				compacted[1] = stored_issuer
				local seen = { [stored_issuer] = true }
				if want_spki then
					for _, pem in ipairs(issuer_pems_to_try) do
						if pem and not seen[pem] then
							local got = get_ocsp_pubkey_fingerprint(pem)
							if got and got == want_spki then
								seen[pem] = true
								compacted[#compacted + 1] = pem
							end
						end
					end
				end
				issuer_pems_to_try = compacted
			end

			-- No issuer material yet. Do not remember this as a bad response: the job may
			-- write issuer.pem on the next run and the following handshake should try again.
			if #issuer_pems_to_try == 0 then
				return finish(false)
			end
			if #issuer_pems_to_try > ocsp_validate_max_issuer_candidates then
				-- Keep the most likely issuer candidates to avoid excessive parsing.
				-- Index 1 is the job issuer when present, so the cap cannot drop it.
				for i = ocsp_validate_max_issuer_candidates + 1, #issuer_pems_to_try do
					issuer_pems_to_try[i] = nil
				end
			end

			local cached_by_issuer = der_chain_cache[cert_fp]
			if not cached_by_issuer then
				cached_by_issuer = {}
				der_chain_cache[cert_fp] = cached_by_issuer
			end

			local validation_attempted = false
			local budget_aborted = false
			for issuer_idx, issuer_candidate_pem in ipairs(issuer_pems_to_try) do
				-- Soft total-time budget: stop trying more issuers if we already spent too long.
				if ocsp_validate_clock() - t_val_total_start > ocsp_validate_budget then
					budget_aborted = true
					break
				end

				local der_chain = cached_by_issuer[issuer_idx]
				if not der_chain then
					local ordered_chain_pem = cert_for_fp_pem .. "\n" .. issuer_candidate_pem
					local der_cert_chain, err = ssl.cert_pem_to_der(ordered_chain_pem)
					if der_cert_chain then
						cached_by_issuer[issuer_idx] = der_cert_chain
						der_chain = der_cert_chain
					else
						safe_log(
							DEBUG,
							"OCSP validate skipped (cert_pem_to_der failed): "
								.. tostring(err)
								.. " server_name="
								.. (server_name or "nil")
						)
						der_chain = nil
					end
				end

				if der_chain then
					validation_attempted = true
					local ok_pcall, validate_ok, validate_err_or_next = pcall(function()
						return ocsp.validate_ocsp_response(ocsp_der, der_chain)
					end)
					if
						ok_pcall
						and validate_ok == true
						and not (
							type(validate_err_or_next) == "number"
							and validate_err_or_next > 0
							and validate_err_or_next - OCSP_CLOCK_SKEW_SECONDS <= ngx.time()
						)
					then
						-- Clear any leftover poison for this SPKI (prior DER binding).
						pcall(function()
							internalstore:delete(ocsp_validate_failed_key)
						end)
						return finish(true)
					end
				end
			end

			-- Poison only on definitive reject after exhausting issuers.
			-- Soft budget abort must not poison: a later issuer (or a soon-written
			-- issuer.pem) may still validate on the next handshake.
			-- Missing issuer list already returns above without setting this key.
			-- Store sha256(DER) so a later publish of a different body is not blocked.
			if validation_attempted and not budget_aborted then
				local poison_val = der_binding or true
				pcall(function()
					internalstore:set(ocsp_validate_failed_key, poison_val, ocsp_validate_failure_ttl, true)
				end)
				safe_log(
					DEBUG,
					"OCSP validate_failed poison set (definitive reject) fp="
						.. cert_fp:sub(1, 16)
						.. "... ttl="
						.. tostring(ocsp_validate_failure_ttl)
						.. "s server_name="
						.. (server_name or "nil")
				)
			elseif budget_aborted then
				-- Named decision: leaf issuer budget exhausted before attach / intermediates.
				-- Not ok_partial (that is NULL-slot multi-staple after a successful attach).
				-- Demote local L1 verified→unverified (KEEP fleet allow-pin) so the next
				-- handshake cannot treat this body as crypto-proven.
				safe_log(
					ERR,
					format_staple_decision("validate_budget", {
						tag = "OCSP_VALIDATE_BUDGET",
						fp = cert_fp,
						server_name = server_name or "nil",
						detail = "leaf_issuers_only",
					})
				)
				do
					local _, _, packed_epoch, l1_exp, packed_gen = ocsp_l1_get(cert_fp)
					local meta_budget = read_ocsp_json_for_fp(cert_fp)
					local exp = l1_exp or ocsp_meta_expires_unix(meta_budget)
					-- verified_binding nil = park DER for reuse without skip-crypto.
					ocsp_l1_put(
						cert_fp,
						ocsp_der,
						nil,
						exp,
						packed_epoch,
						packed_gen or ocsp_live_soft_recall_gen(cert_fp)
					)
				end
			end
			return finish(false)
		end

		-- Prefer the real leaf fingerprint. Never promote "first ocsp.der on disk" —
		-- intermediates can retain leftover shards and would win that race.
		local intermediate_fps = {}
		if next(chain_issuer_subjects) ~= nil then
			for fp, pem in pairs(fp_to_cert_pem) do
				pcall(function()
					local cert_obj = resty_x509.new(pem)
					local subject = cert_obj and cert_obj:get_subject_name()
					if subject and chain_issuer_subjects[tostring(subject)] then
						intermediate_fps[fp] = true
					end
				end)
			end
		end

		-- Pick exactly one leaf SPKI to staple for (curve-aware ClientHello match).
		local function fp_key_kind(fp)
			local pem = fp and fp_to_cert_pem[fp] or nil
			if type(pem) == "string" and #pem > 0 then
				return cert_pubkey_kind(pem)
			end
			return nil
		end

		local leaf_cands = {}
		for _, fp in ipairs(candidate_fps) do
			if not intermediate_fps[fp] then
				leaf_cands[#leaf_cands + 1] = {
					fp = fp,
					pem = fp_to_cert_pem[fp],
					ocsp_cert = fp_to_cert_pem[fp],
					ocsp_fp_hint = fp,
				}
			end
		end
		local selected_leaf_fp = nil
		-- Prefer the leaf resolve_leaf already chose (stable across intermediate-first chains).
		if
			type(leaf_fp_resolved) == "string"
			and is_fp64_lower_hex(leaf_fp_resolved)
			and not intermediate_fps[leaf_fp_resolved]
		then
			selected_leaf_fp = leaf_fp_resolved
		elseif #leaf_cands == 1 then
			selected_leaf_fp = leaf_cands[1].fp
		elseif #leaf_cands > 1 then
			local chosen = select_ocsp_staple_candidate(leaf_cands)
			selected_leaf_fp = chosen and chosen.fp or leaf_cands[1].fp
		end

		-- Plugin hint may be the RSA leaf while we ECDSA-prefer; only honor hint when
		-- it names the selected leaf (same SPKI), never when it points at the sibling.
		if cert_fp_hint and type(cert_fp_hint) == "string" then
			local hint_fp = cert_fp_hint:lower()
			if is_fp64_lower_hex(hint_fp) and not intermediate_fps[hint_fp] then
				if selected_leaf_fp and hint_fp ~= selected_leaf_fp then
					local hint_kind = fp_key_kind(hint_fp)
					local sel_kind = fp_key_kind(selected_leaf_fp)
					if hint_kind and sel_kind and hint_kind ~= sel_kind then
						log_ocsp_staple_skip(hint_kind, hint_fp, "wrong_key_type_hint")
					else
						safe_log(
							DEBUG,
							"OCSP ignoring cert_fp_hint that is not the selected leaf fp="
								.. hint_fp:sub(1, 16)
								.. "... selected="
								.. selected_leaf_fp:sub(1, 16)
								.. "... server_name="
								.. (server_name or "nil")
						)
					end
				elseif not selected_leaf_fp and tried_fps[hint_fp] then
					selected_leaf_fp = hint_fp
				end
			elseif is_fp64_lower_hex(hint_fp) and tried_fps[hint_fp] then
				safe_log(
					DEBUG,
					"OCSP cert_fp_hint looks like intermediate; ignoring for leaf prefer fp="
						.. hint_fp:sub(1, 16)
						.. "... server_name="
						.. (server_name or "nil")
				)
			end
		end
		if not selected_leaf_fp and leaf_for_meta then
			local fp = get_ocsp_pubkey_fingerprint(leaf_for_meta)
			if is_fp64_lower_hex(fp) then
				selected_leaf_fp = fp
			end
		end

		-- Only this SPKI — no fallthrough to another leaf/key-type shard.
		local candidate_fps_ordered = {}
		if selected_leaf_fp then
			candidate_fps_ordered[1] = selected_leaf_fp
			safe_log(
				DEBUG,
				"OCSP selected leaf fp="
					.. selected_leaf_fp:sub(1, 16)
					.. "... kind="
					.. tostring(fp_key_kind(selected_leaf_fp) or "unknown")
					.. " (no cross-key-type borrow) server_name="
					.. (server_name or "nil")
			)
		end

		safe_log(
			DEBUG,
			"OCSP fingerprint phase total_ns="
				.. tostring(ns_since(t_fp_phase_start))
				.. " server_name="
				.. (server_name or "nil")
		)

		local fresh_refuse_why = nil
		-- Lookup loop: only the selected leaf SPKI (no cross-key-type borrow).
		-- Per candidate: L1 (bw2) → revalidate/drop → disk ocsp.der → authorize.
		for _, cert_fp in ipairs(candidate_fps_ordered) do
			local t_attempt_start = hrtime and hrtime() or now()
			local attempt_hit = false
			safe_log(
				DEBUG,
				"OCSP trying candidate fingerprint raw="
					.. tostring(cert_fp)
					.. " server_name="
					.. (server_name or "nil")
			)
			if is_fp64_lower_hex(cert_fp) then
				safe_log(
					DEBUG,
					"OCSP trying fingerprint: " .. cert_fp:sub(1, 16) .. "... server_name=" .. (server_name or "nil")
				)

				-- Use tree-structured sharded path: /var/cache/bunkerweb/ssl/{hex1}/{hex2}/{full_fingerprint}/ocsp.der
				local hex1 = cert_fp:sub(1, 1)
				local hex2 = cert_fp:sub(2, 2)
				local ocsp_path = "/var/cache/bunkerweb/ssl/" .. hex1 .. "/" .. hex2 .. "/" .. cert_fp .. "/ocsp.der"
				local ocsp_dir = "/var/cache/bunkerweb/ssl/" .. hex1 .. "/" .. hex2 .. "/" .. cert_fp
				safe_log(DEBUG, "OCSP lookup ocsp_path=" .. ocsp_path .. " server_name=" .. (server_name or "nil"))

				-- 1) L1 first (composite epoch|verified_binding|expires|DER).
				-- Drop when .ocsp_epoch advanced or disk der_sha256 no longer matches
				-- (publish / soft-recall / tombstone). Keep across brief ENOENT gap.
				local cache_result, ocsp_verified, cache_epoch, cache_expires, cache_gen = ocsp_l1_get(cert_fp)
				if type(cache_result) == "string" and #cache_result > 0 then
					-- Drop L1 when the job atomically replaced ocsp.der (or removed it),
					-- or when the shared publish epoch advanced (HTTP ↔ stream coherence).
					if not ocsp_l1_matches_disk(cert_fp, ocsp_dir, ocsp_path, cache_result, cache_epoch) then
						safe_log(
							DEBUG,
							"OCSP shared-dict stale vs disk; discarding L1 for fp="
								.. cert_fp:sub(1, 16)
								.. "... server_name="
								.. (server_name or "nil")
						)
						ocsp_l1_drop(cert_fp, ocsp_path)
					else
						local fresh, fresh_why = ocsp_resp_still_fresh(cache_expires, cert_fp)
						if not fresh then
							safe_log(
								ERR,
								"OCSP L1 response past nextUpdate/expires; discarding fp="
									.. cert_fp:sub(1, 16)
									.. "... server_name="
									.. (server_name or "nil")
							)
							ocsp_l1_drop(cert_fp, ocsp_path)
							fresh_refuse_why = fresh_why or "response_stale"
						else
							local live_gen = ocsp_live_soft_recall_gen(cert_fp)
							local ocsp_ok = ocsp_verified_for_resp(ocsp_verified, cache_result, cache_gen, live_gen)
							local ocsp_validated_now = ocsp_ok
							if not ocsp_ok then
								local fp_ok = verify_ocsp_fingerprint_match(cert_fp, ocsp_dir)
								if fp_ok then
									local cert_for_fp_pem = fp_to_cert_pem[cert_fp] or leaf_for_meta
									local validate_res =
										ocsp_validate_response_for_fp(cert_fp, cert_for_fp_pem, cache_result)
									if validate_res == true then
										ocsp_ok = true
										ocsp_validated_now = true
										local binding = ocsp_resp_binding(cache_result)
										if binding and not probe_only then
											local exp = cache_expires
												or ocsp_meta_effective_expires_unix(read_ocsp_json_for_fp(cert_fp))
											ocsp_l1_put(cert_fp, cache_result, binding, exp, cache_epoch, live_gen)
										end
									else
										ocsp_ok = false
										-- Fingerprint matches (SPKI) but validate failed: usually a same-key
										-- renewal still serving an OCSP body for the previous serial — not a
										-- SHA-256 collision.
										local report_key = "TLS:SSL:ocsp_serial_mismatch_reported:" .. cert_fp
										local already_reported = false
										pcall(function()
											already_reported = internalstore:get(report_key, true) == true
										end)
										if not already_reported then
											local serial_mismatch = false
											pcall(function()
												if cert_for_fp_pem and type(cert_for_fp_pem) == "string" then
													local cs = get_cert_serial(cert_for_fp_pem)
													local os_ = get_ocsp_serial(cache_result, cs)
													serial_mismatch = (cs ~= nil and os_ ~= nil and cs ~= os_)
												end
											end)
											if serial_mismatch then
												pcall(function()
													internalstore:set(report_key, true, 300, true) -- throttle per fingerprint
												end)
												safe_log(
													ERR,
													"OCSP serial mismatch for SPKI fp="
														.. cert_fp:sub(1, 16)
														.. "... (stale response after same-key renew?); discarding cache server_name="
														.. (server_name or "nil")
												)
											end
										end
									end
								end
							end

							if ocsp_ok then
								resp = cache_result
								resp_fp = cert_fp
								active_refuse_fp = cert_fp
								attempt_hit = true
								safe_log(
									DEBUG,
									"OCSP found response in shared memory cache for fp="
										.. cert_fp:sub(1, 16)
										.. "... verified="
										.. tostring(ocsp_validated_now)
										.. " server_name="
										.. (server_name or "nil")
								)
								break
							else
								safe_log(
									ERR,
									"OCSP cached response rejected (validation failed); discarding cache for fp="
										.. cert_fp:sub(1, 16)
										.. "... server_name="
										.. (server_name or "nil")
								)
								ocsp_l1_drop(cert_fp, ocsp_path)
							end
						end
					end
				end

				-- 2) Disk fallback: read ocsp.der, freshness + ligand/validate, then L1 put.
				safe_log(
					DEBUG,
					"OCSP looking for cached response at: " .. ocsp_path .. " server_name=" .. (server_name or "nil")
				)
				pcall(function()
					local f, err = io.open(ocsp_path, "rb")
					if f then
						local data = f:read("*a")
						f:close()

						if data and #data > 0 then
							local fresh, fresh_why = ocsp_resp_still_fresh(nil, cert_fp)
							if not fresh then
								safe_log(
									ERR,
									"OCSP disk response past nextUpdate/expires; skipping ocsp.der at: "
										.. ocsp_path
										.. " server_name="
										.. (server_name or "nil")
								)
								ocsp_l1_drop(cert_fp, ocsp_path)
								fresh_refuse_why = fresh_why or "response_stale"
								return
							end
							local _, disk_verified, _, _, disk_gen = ocsp_l1_get(cert_fp)
							local live_gen = ocsp_live_soft_recall_gen(cert_fp)
							local ocsp_ok = ocsp_verified_for_resp(disk_verified, data, disk_gen, live_gen)
							local verified_binding = nil
							if not ocsp_ok then
								local fp_ok = verify_ocsp_fingerprint_match(cert_fp, ocsp_dir)
								if fp_ok then
									local cert_for_fp_pem = fp_to_cert_pem[cert_fp] or leaf_for_meta
									local validate_res = ocsp_validate_response_for_fp(cert_fp, cert_for_fp_pem, data)
									if validate_res == true then
										ocsp_ok = true
										verified_binding = ocsp_resp_binding(data)
									else
										ocsp_ok = false
										-- Same SPKI fp + failed validate: usually stale OCSP after same-key renew.
										local report_key = "TLS:SSL:ocsp_serial_mismatch_reported:" .. cert_fp
										local already_reported = false
										pcall(function()
											already_reported = internalstore:get(report_key, true) == true
										end)
										if not already_reported then
											local serial_mismatch = false
											pcall(function()
												if cert_for_fp_pem and type(cert_for_fp_pem) == "string" then
													local cs = get_cert_serial(cert_for_fp_pem)
													local os_ = get_ocsp_serial(data, cs)
													serial_mismatch = (cs ~= nil and os_ ~= nil and cs ~= os_)
												end
											end)
											if serial_mismatch then
												pcall(function()
													internalstore:set(report_key, true, 300, true) -- throttle per fingerprint
												end)
												safe_log(
													ERR,
													"OCSP serial mismatch for SPKI fp="
														.. cert_fp:sub(1, 16)
														.. "... (stale response after same-key renew?); discarding cache server_name="
														.. (server_name or "nil")
												)
											end
										end
									end
								end
							else
								verified_binding = disk_verified
							end

							if ocsp_ok then
								resp = data
								resp_fp = cert_fp
								active_refuse_fp = cert_fp
								attempt_hit = true
								safe_log(
									INFO,
									"OCSP loaded response from: "
										.. ocsp_path
										.. " server_name="
										.. (server_name or "nil")
								)

								-- Cache in shared memory (TTL 300s) as one composite entry
								if not probe_only then
									local exp = ocsp_meta_effective_expires_unix(read_ocsp_json_for_fp(cert_fp))
									if
										not ocsp_l1_put(
											cert_fp,
											resp,
											verified_binding,
											exp,
											nil,
											ocsp_live_soft_recall_gen(cert_fp)
										)
									then
										safe_log(
											DEBUG,
											"OCSP failed to cache response in shared memory server_name="
												.. (server_name or "nil")
										)
									end
								end
							else
								safe_log(
									ERR,
									"OCSP rejected (validation failed); skipping ocsp.der at: "
										.. ocsp_path
										.. " server_name="
										.. (server_name or "nil")
								)
								ocsp_l1_drop(cert_fp, ocsp_path)
							end
						else
							safe_log(
								DEBUG,
								"OCSP response file is empty: "
									.. ocsp_path
									.. " server_name="
									.. (server_name or "nil")
							)
						end
					else
						if err and lower(err):find("permission denied", 1, true) then
							safe_log(
								ERR,
								"OCSP permission denied reading "
									.. ocsp_path
									.. " server_name="
									.. (server_name or "nil")
							)
						else
							safe_log(
								DEBUG,
								"OCSP response file not found: "
									.. ocsp_path
									.. " server_name="
									.. (server_name or "nil")
							)
						end
					end
				end)

				safe_log(
					DEBUG,
					"OCSP attempt fp="
						.. cert_fp:sub(1, 16)
						.. "..."
						.. " hit="
						.. tostring(attempt_hit)
						.. " time_ns="
						.. tostring(ns_since(t_attempt_start))
						.. " server_name="
						.. (server_name or "nil")
				)
				if resp then
					break
				end
			else
				safe_log(
					DEBUG,
					"OCSP skipping invalid fingerprint format: "
						.. tostring(cert_fp)
						.. " server_name="
						.. (server_name or "nil")
				)
			end
		end

		if not resp then
			safe_log(
				DEBUG,
				"OCSP response not found for any tried certificate public-key fingerprint(s) (server_name="
					.. (server_name or "unknown")
					.. ")"
			)
			if has_must_staple then
				return refuse_must_staple(fresh_refuse_why or "response_not_found")
			end
			return true
		end
		-- Post-lookup gates (body in hand): serial ban → shared ligand → peer refuse
		-- → floor/tombstone/paged → AIA → key-type pin → CertID → attach.
		-- Allow-pin: missing pin refuses; DROP_ALLOW compare-and-deletes only.
		if resp_fp and serial_blacklist_blocks(resp_fp, resp) then
			if has_must_staple then
				return refuse_must_staple("serial_blacklisted")
			end
			return true
		end
		-- Must-Staple: private L1 verify is not enough; bind shared ocsp-ligand
		-- (same stand-in stream uses — HTTP/stream cannot share lua_shared_dict).
		-- Pass raw ligand_verdict reason so KEEP_ALLOW[ligand_missing] holds the pin.
		if has_must_staple and resp_fp then
			local ligand_ok, ligand_reason = must_staple_binds_shared_ligand(resp_fp, resp)
			if not ligand_ok then
				return refuse_must_staple(ligand_reason or "shared_ligand", resp)
			end
		end
		do
			local peer_dec = peer_generation_refused(resp)
			if peer_dec then
				if has_must_staple then
					return refuse_must_staple(peer_dec, resp)
				end
				return true
			end
		end
		if has_must_staple and resp_fp and cluster_floor_blocks(resp_fp, read_ocsp_json_for_fp(resp_fp)) then
			return refuse_must_staple("cluster_floor", resp)
		end
		do
			local resp_meta = resp_fp and read_ocsp_json_for_fp(resp_fp) or nil
			if meta_tombstoned(resp_meta) then
				if resp_fp then
					ocsp_l1_drop(
						resp_fp,
						"/var/cache/bunkerweb/ssl/"
							.. resp_fp:sub(1, 1)
							.. "/"
							.. resp_fp:sub(2, 2)
							.. "/"
							.. resp_fp
							.. "/ocsp.der"
					)
				end
				if has_must_staple then
					return refuse_must_staple("tombstoned")
				end
				return true
			end
			if resp_fp and shard_not_paged(resp_meta) then
				if has_must_staple then
					return refuse_must_staple("not_paged")
				end
				return true
			end
		end
		do
			local leaf_pem = (type(leaf_for_meta) == "string" and #leaf_for_meta > 0) and leaf_for_meta or nil
			if resp_fp then
				local blocks, aia_why = aia_uri_pin_blocks(resp_fp, leaf_pem, has_must_staple)
				if blocks then
					if has_must_staple then
						return refuse_must_staple(aia_why or "aia_uri_mismatch")
					end
					return true
				end
			end
		end

		-- Never attach a sibling key type's body (defense in depth after candidate filter).
		if selected_leaf_fp and resp_fp and resp_fp ~= selected_leaf_fp then
			safe_log(
				ERR,
				"OCSP refuse staple: response fp="
					.. resp_fp:sub(1, 16)
					.. "... is not selected leaf fp="
					.. selected_leaf_fp:sub(1, 16)
					.. "... server_name="
					.. (server_name or "nil")
			)
			if has_must_staple then
				return refuse_must_staple("wrong_key_type_staple")
			end
			return true
		end

		-- CertID must name this handshake leaf (serial + issuer), even for verified L1 hits.
		-- Issuer candidates are pinned to the shard issuer SPKI when issuer.pem exists.
		do
			local leaf_pem = leaf_for_meta
			if resp_fp and fp_to_cert_pem and fp_to_cert_pem[resp_fp] then
				leaf_pem = fp_to_cert_pem[resp_fp]
			end
			local issuer_pems = {}
			local seen = {}
			local want_spki = nil
			if resp_fp and is_fp64_lower_hex(resp_fp) then
				local issuer_path = "/var/cache/bunkerweb/ssl/"
					.. resp_fp:sub(1, 1)
					.. "/"
					.. resp_fp:sub(2, 2)
					.. "/"
					.. resp_fp
					.. "/issuer.pem"
				pcall(function()
					local f = io.open(issuer_path, "r")
					if not f then
						return
					end
					local pem = f:read("*a")
					f:close()
					if type(pem) == "string" and #pem > 0 then
						issuer_pems[#issuer_pems + 1] = pem
						seen[pem] = true
						want_spki = get_ocsp_pubkey_fingerprint(pem)
					end
				end)
			end
			if chain_certs then
				for _, block in ipairs(chain_certs) do
					if type(block) == "string" and block ~= leaf_pem and not seen[block] then
						local spki_ok = true
						if want_spki then
							local got = get_ocsp_pubkey_fingerprint(block)
							spki_ok = (got ~= nil and got == want_spki)
						end
						if spki_ok then
							issuer_pems[#issuer_pems + 1] = block
							seen[block] = true
						end
					end
				end
			end
			if not verify_ocsp_cert_match(leaf_pem, resp, issuer_pems) then
				safe_log(ERR, "OCSP CertID refuse staple before set server_name=" .. (server_name or "nil"))
				if has_must_staple then
					return refuse_must_staple("certid_mismatch")
				end
				return true
			end
		end

		-- Attach: CertID already passed; bunkerweb.ocsp.attach_ocsp_staple (multi)
		-- or set_ocsp_status_resp. Peer refuse + shared ligand ran earlier (post-lookup).
		-- probe_only stops before attach once the leaf shard is known GOOD.
		-- Safely set OCSP stapling with exception handling (only if ocsp module is available)
		if not ocsp then
			safe_log(DEBUG, "OCSP not available (ngx.ocsp module not loaded)")
			if has_must_staple then
				return refuse_must_staple("ngx_ocsp_unavailable")
			end
			return true
		end
		if probe_only then
			local ms_gate = leaf_fail_closed_must_staple(cert_pem, leaf_fp_resolved or active_refuse_fp)
			local path_ok, path_detail = true, nil
			local path_call_ok, path_a, path_b = pcall(function()
				local ocsp_mod = require "bunkerweb.ocsp"
				if not ocsp_mod.issuer_path_intermediate_ready then
					if ms_gate then
						return false, "issuer_path_unavailable"
					end
					return true, nil
				end
				return ocsp_mod.issuer_path_intermediate_ready(cert_pem)
			end)
			if not path_call_ok then
				if ms_gate then
					path_ok, path_detail = false, "issuer_path_unavailable"
				else
					safe_log(
						NOTICE,
						"OCSP_MODULE_DEGRADED action=serve_unstapled detail=issuer_path_pcall server_name="
							.. (server_name or "nil")
					)
					path_ok = true
				end
			else
				path_ok, path_detail = path_a, path_b
			end
			if path_ok == false then
				safe_log(
					DEBUG,
					"OCSP probe_only demoted: issuer path not ready detail="
						.. tostring(path_detail)
						.. " server_name="
						.. (server_name or "nil")
				)
				return refuse_must_staple(path_detail or "unmet")
			end
			safe_log(DEBUG, "OCSP probe_only success server_name=" .. (server_name or "nil"))
			return true
		end
		local ok_pcall, ok_set, oerr
		ok_pcall = pcall(function()
			-- Missing module must take the exception path (Must-Staple refuse), not plain attach.
			local ocsp_mod = assert(cwd, "bunkerweb.ocsp unavailable")
			if ocsp_mod.attach_ocsp_staple then
				-- Pass fullchain so leaf-only libssl can refuse intermediate Must-Staple honestly.
				ok_set, oerr = ocsp_mod.attach_ocsp_staple(resp, cert_pem)
			else
				ok_set, oerr = ocsp.set_ocsp_status_resp(resp)
			end
		end)

		if not ok_pcall then
			safe_log(ERR, "OCSP exception while setting stapling: " .. tostring(ok_set))
			if has_must_staple then
				return refuse_must_staple("set_staple_exception")
			end
		else
			if not ok_set then
				safe_log(ERR, "OCSP failed to set stapling: " .. (oerr or "unknown"))
				if
					oerr == "intermediate_must_staple_libssl"
					or oerr == "intermediate_must_staple_colony"
					or has_must_staple
				then
					return refuse_must_staple(
						(oerr == "intermediate_must_staple_libssl" or oerr == "intermediate_must_staple_colony")
								and oerr
							or "set_staple_failed"
					)
				end
			else
				local pem_for_kind = leaf_for_meta
				if resp_fp and fp_to_cert_pem and fp_to_cert_pem[resp_fp] then
					pem_for_kind = fp_to_cert_pem[resp_fp]
				end
				log_ocsp_stapled(cert_pubkey_kind(pem_for_kind), resp_fp, resp)
			end
		end

		-- If we reach here without returning earlier, OCSP failed but is not required (or succeeded)
		safe_log(
			DEBUG,
			"OCSP set_ocsp_from_cache total time_ns="
				.. tostring(ns_since(t_total_start))
				.. " server_name="
				.. (server_name or "nil")
		)
		return true
	end

	-- =====================================================================
	-- SECTION: plugin ssl_certificate loop — install leaf + staple
	-- For each plugin in phase order: call ssl_certificate → pair certs/keys
	-- → dual-cert probe (probe_only) + issuer-path health → set_cert once
	-- → set_ocsp_from_cache (attach). Must-Staple abort sets state.abort_must_staple;
	-- ngx.exit runs AFTER the top-level pcall (below).
	-- =====================================================================
	-- Call ssl_certificate() methods
	safe_log(DEBUG, "calling ssl_certificate() methods of plugins ...")
	for _, plugin_id in ipairs(phase_order) do
		-- Require call
		safe_log(DEBUG, "Loading plugin: " .. plugin_id)
		local plugin_lua, err = require_plugin(plugin_id)
		if plugin_lua == false then
			safe_log(ERR, "Failed to load plugin " .. plugin_id .. " (not found): " .. (err or "unknown"))
		elseif plugin_lua == nil then
			safe_log(DEBUG, "Plugin " .. plugin_id .. " module not found or failed to load: " .. (err or "unknown"))
		else
			safe_log(DEBUG, "Plugin " .. plugin_id .. " loaded successfully")
			-- Check if plugin has ssl_certificate method
			if plugin_lua.ssl_certificate ~= nil then
				-- New call
				local ok_p, plugin_obj = new_plugin(plugin_lua)
				if not ok_p then
					safe_log(ERR, plugin_obj)
				else
					local ok_c, ret = call_plugin(plugin_obj, "ssl_certificate")
					if not ok_c then
						safe_log(ERR, ret)
					elseif not ret.ret then
						safe_log(ERR, plugin_id .. ":ssl_certificate() call failed : " .. ret.msg)
					else
						safe_log(DEBUG, plugin_id .. ":ssl_certificate() call successful : " .. ret.msg)
						if ret.status then
							safe_log(DEBUG, plugin_id .. " is setting certificate/key(s) : " .. ret.msg)

							-- Clear old certificates before setting new ones (fail-safe).
							-- Also drop any connection OCSP staple left from a prior leaf
							-- (HTTP/2 coalescing / ssl_certificate re-entry); SSL_certs_clear
							-- does not clear SSL_set_tlsext_status_ocsp_resp.
							--
							-- Install-state flags live OUTSIDE the top-level pcall (see
							-- state.certs_cleared / state.leaf_installed / state.leaf_must_staple above).
							-- After clear_certs, a Lua throw that used to `return true`
							-- would hand nginx the static ssl_certificate — fatal for
							-- Must-Staple. Outer handler aborts when cleared/half-installed.
							pcall(clear_certs)
							state.certs_cleared = true
							state.leaf_installed = false
							state.leaf_complete = false
							state.leaf_must_staple = nil
							pcall(function()
								local ocsp_mod = require "bunkerweb.ocsp"
								if ocsp_mod and ocsp_mod.on_ssl_context_swap then
									ocsp_mod.on_ssl_context_swap(internalstore)
								end
							end)

							-- wipe_ssl_ctx: remove a half-installed leaf (set_cert ok,
							-- set_priv_key fail / OCSP throw) so we never leave a naked
							-- Must-Staple cert on the connection. Sets state.certs_cleared again
							-- so the outer abort path still fires if we return without abort.
							local function wipe_ssl_ctx(why)
								pcall(clear_certs)
								pcall(function()
									local ocsp_mod = require "bunkerweb.ocsp"
									if ocsp_mod and ocsp_mod.on_ssl_context_swap then
										ocsp_mod.on_ssl_context_swap(internalstore)
									end
								end)
								state.leaf_installed = false
								state.leaf_complete = false
								state.certs_cleared = true
								safe_log(
									ERR,
									"OCSP wipe_ssl_ctx why="
										.. tostring(why or "unknown")
										.. " server_name="
										.. (server_name or "nil")
								)
							end

							-- Some plugins return PEM strings; others return already-parsed ngx.ssl objects.
							local cert_data = ret.status[1]
							local key_data = ret.status[2]

							local cert_key_pairs = {}
							local ocsp_possible = false

							if type(cert_data) == "string" and type(key_data) == "string" then
								-- Parse multiple certificates and keys (support RSA, ECDSA, PQC, etc.)
								local cert_pem = cert_data
								local key_pem = key_data

								local certs = parse_pem_certificates(cert_pem)
								local keys = parse_pem_keys(key_pem)
								cert_key_pairs = pair_certs_and_keys(certs, keys)
								ocsp_possible = true
							else
								-- Assume ngx.ssl.parse_pem_* was already called by the plugin
								-- Check if original PEM strings are available at indices 3,4 (e.g., from letsencrypt plugin)
								local orig_cert_pem = nil
								local orig_cert_fp = nil
								-- Harvest PEM/FP even when ngx.ocsp is nil so probe_only can still
								-- run ligand/allow-pin/Must-Staple gates (attach stays ocsp-gated).
								if ret.status[3] and type(ret.status[3]) == "string" then
									orig_cert_pem = ret.status[3]
									safe_log(
										DEBUG,
										"Original PEM certificate available for OCSP fingerprinting ("
											.. #orig_cert_pem
											.. " bytes)"
									)
								end
								-- Optional fingerprint hint at index 5 (computed in letsencrypt/customcert load_data)
								if ret.status[5] and type(ret.status[5]) == "string" then
									local fp = ret.status[5]:lower()
									if is_fp64_lower_hex(fp) then
										orig_cert_fp = fp
										safe_log(
											DEBUG,
											"Original cert fingerprint available for OCSP (" .. fp:sub(1, 16) .. "... )"
										)
									end
								end
								-- Resolve leaf via SPKI graph (resolve_leaf), not blocks[1].
								-- Plugin status[5] may name an intermediate on intermediate-first
								-- chains; resolve_leaf keeps the hint only when that SPKI is not
								-- an issuer of another block in status[3].
								if orig_cert_pem then
									local leaf_pem, leaf_fp = resolve_leaf(orig_cert_pem, orig_cert_fp)
									if type(leaf_fp) == "string" and is_fp64_lower_hex(leaf_fp) then
										if orig_cert_fp and orig_cert_fp ~= leaf_fp then
											safe_log(
												ERR,
												"OCSP status[5] fingerprint mismatch vs resolve_leaf SPKI hint="
													.. orig_cert_fp:sub(1, 16)
													.. "... leaf="
													.. leaf_fp:sub(1, 16)
													.. "... server_name="
													.. (server_name or "nil")
											)
										end
										orig_cert_fp = leaf_fp
									end
								end
								cert_key_pairs = {
									{
										cert = cert_data,
										key = key_data,
										cert_id = "parsed",
										matched = true,
										cert_pem_for_ocsp = orig_cert_pem,
										cert_fp_for_ocsp = orig_cert_fp,
									},
								}
							end

							if #cert_key_pairs == 0 then
								safe_log(ERR, "No valid certificate/key pairs extracted from " .. plugin_id)
							else
								safe_log(
									DEBUG,
									"Found " .. #cert_key_pairs .. " certificate/key pair(s) from " .. plugin_id
								)

								-- Present one leaf per handshake (RFC 9846 CertificateEntry bind).
								-- Dual-cert health (when #pairs > 1):
								--   ordered_ocsp_staple_candidates(ClientHello) →
								--   issuer_path_intermediate_ready demote (scoped) →
								--   set_ocsp_from_cache(..., probe_only=true) →
								--   prefer fewest issuer_path_null_slots among viable →
								--   install_pairs = { winner }; siblings log skip_slot.
								-- Soft fuse preferred_soft_pair installs unstapled if all probes fail.
								--
								-- Scoped demotion (reviewers):
								--   Explicit path_ok==false from helper → always demote (intermediate policy).
								--   Module miss / pcall throw → demote only if leaf_fail_closed_must_staple
								--   (MS or unknown). Non-MS leaves stay viable → serve_unstapled.
								--   If every demotion was module-degrade on non-MS, install preferred_soft_pair
								--   instead of emptying install_pairs (avoids fleet outage when ocsp.lua
								--   cannot load). dual_any_policy_refuse gates the soft-fuse abort path.
								local install_pairs = cert_key_pairs
								local preferred_soft_pair = cert_key_pairs[1]
								local dual_any_policy_refuse = false
								if #cert_key_pairs > 1 then
									local pick_list = {}
									for idx, pair in ipairs(cert_key_pairs) do
										local ocsp_cert = pair.cert_pem_for_ocsp
										if type(ocsp_cert) ~= "string" or #ocsp_cert == 0 then
											ocsp_cert = type(pair.cert) == "string" and pair.cert or nil
										end
										pick_list[#pick_list + 1] = {
											idx = idx,
											cert_id = pair.cert_id,
											pem = ocsp_cert,
											ocsp_cert = ocsp_cert,
											ocsp_fp_hint = pair.cert_fp_for_ocsp,
											pair = pair,
										}
									end
									local ordered_picks = ordered_ocsp_staple_candidates(pick_list)
									install_pairs = {}
									preferred_soft_pair = (ordered_picks[1] and ordered_picks[1].pair)
										or cert_key_pairs[1]
									local viable = {}
									local any_policy_refuse = false
									local module_degraded_only = true
									for _, pick in ipairs(ordered_picks) do
										local pair = pick.pair
										local ocsp_cert = pick.ocsp_cert
										local ocsp_fp_hint = pick.ocsp_fp_hint
										local probe_ok = true
										local ms_gate = leaf_fail_closed_must_staple(ocsp_cert, ocsp_fp_hint)
										-- Demote before install when this leaf's issuer path cannot
										-- satisfy intermediate Must-Staple (even if leaf shard is GOOD
										-- or ngx.ocsp is unavailable). Legal ok_partial does not demote.
										-- Module miss / pcall throw: fail closed only for Must-Staple or
										-- unknown leaves; non-MS leaves stay viable unstapled.
										if
											type(ocsp_cert) == "string"
											and #ocsp_cert > 0
											and get_ocsp_staple_mode() ~= "open"
										then
											local path_ok, path_detail = true, nil
											local path_call_ok, path_a, path_b = pcall(function()
												local ocsp_mod = require "bunkerweb.ocsp"
												if not ocsp_mod.issuer_path_intermediate_ready then
													if ms_gate then
														return false, "issuer_path_unavailable"
													end
													return true, nil
												end
												return ocsp_mod.issuer_path_intermediate_ready(ocsp_cert)
											end)
											if not path_call_ok then
												if ms_gate then
													path_ok, path_detail = false, "issuer_path_unavailable"
													module_degraded_only = false
													any_policy_refuse = true
												else
													safe_log(
														NOTICE,
														"OCSP_MODULE_DEGRADED action=serve_unstapled detail=issuer_path_pcall cert="
															.. tostring(pick.cert_id)
															.. " server_name="
															.. (server_name or "nil")
													)
													path_ok = true
												end
											else
												path_ok, path_detail = path_a, path_b
												if path_ok == false then
													module_degraded_only = false
													any_policy_refuse = true
												end
											end
											if path_ok == false then
												safe_log(
													ERR,
													format_staple_decision(path_detail or "unmet", {
														tag = "OCSP_MUST_STAPLE_REFUSE",
														action = "skip_leaf",
														detail = "issuer_path_health",
														server_name = server_name or "nil",
														cert = tostring(pick.cert_id),
													})
												)
												probe_ok = false
											end
										elseif not ocsp_cert and not ocsp_fp_hint and ms_gate then
											-- No PEM/hint for a Must-Staple-or-unknown leaf → demote.
											probe_ok = false
											module_degraded_only = false
											any_policy_refuse = true
										end
										-- Policy probe does not require ngx.ocsp (ligand / allow-pin /
										-- Must-Staple / ngx_ocsp_unavailable still fire). Attach stays ocsp-gated.
										if probe_ok and (ocsp_cert or ocsp_fp_hint) then
											local ok_probe, probe_ret =
												pcall(set_ocsp_from_cache, ocsp_cert, ocsp_fp_hint, true)
											if not ok_probe then
												safe_log(
													ERR,
													"OCSP probe error for "
														.. tostring(pick.cert_id)
														.. ": "
														.. tostring(probe_ret)
												)
												if ms_gate then
													probe_ok = false
													module_degraded_only = false
													any_policy_refuse = true
												end
											elseif probe_ret == false then
												safe_log(
													ERR,
													format_staple_decision("probe_failed", {
														tag = "OCSP_MUST_STAPLE_REFUSE",
														action = "skip_leaf",
														server_name = server_name or "nil",
														cert = tostring(pick.cert_id),
													})
												)
												probe_ok = false
												module_degraded_only = false
												any_policy_refuse = true
											end
										end
										if probe_ok then
											local nulls = 0
											if type(ocsp_cert) == "string" and #ocsp_cert > 0 then
												pcall(function()
													local ocsp_mod = require "bunkerweb.ocsp"
													if ocsp_mod.issuer_path_null_slots then
														nulls = tonumber(ocsp_mod.issuer_path_null_slots(ocsp_cert))
															or 0
													end
												end)
											end
											viable[#viable + 1] = { pick = pick, nulls = nulls }
										end
									end
									if #viable > 0 then
										local best = viable[1]
										for i = 2, #viable do
											if viable[i].nulls < best.nulls then
												best = viable[i]
											end
										end
										local pick = best.pick
										local pair = pick.pair
										local ocsp_cert = pick.ocsp_cert
										if best ~= viable[1] or pick ~= ordered_picks[1] then
											local detail = "staple_health_fallback"
											if best.nulls < viable[1].nulls then
												detail = "path_completeness"
											end
											safe_log(
												NOTICE,
												format_staple_decision("skip_slot", {
													tag = "OCSP_STAPLE_HEALTH_FALLBACK",
													detail = detail,
													null_slots = best.nulls,
													server_name = server_name or "nil",
													cert = tostring(pick.cert_id),
												})
											)
										end
										install_pairs = { pair }
										local chosen_kind = cert_pubkey_kind(ocsp_cert) or "unknown"
										for _, other in ipairs(ordered_picks) do
											if other.pair ~= pair then
												local skip_fp = other.ocsp_fp_hint
												local kind = cert_pubkey_kind(other.ocsp_cert) or "unknown"
												local reason = chosen_kind == "rsa" and "single_slot_rsa_prefer"
													or "single_slot_ecdsa_prefer"
												log_ocsp_staple_skip(kind, skip_fp, reason)
											end
										end
									elseif module_degraded_only and preferred_soft_pair then
										-- All demotions were module-degrade on non-MS leaves: install preferred.
										install_pairs = { preferred_soft_pair }
									else
										install_pairs = {}
									end
									dual_any_policy_refuse = any_policy_refuse
								end

								local all_certs_set = true
								local ocsp_candidates = {}
								local must_staple_probe_refused = (
									#install_pairs == 0
									and #cert_key_pairs > 0
									and (dual_any_policy_refuse or #cert_key_pairs <= 1)
								)
								local refused_pair = preferred_soft_pair

								for idx, pair in ipairs(install_pairs) do
									-- Reset per-leaf abort detail so a sibling soft-fuse refuse
									-- cannot leak into this leaf's post-install throw path
									-- (state.abort_must_staple_detail is shared across the handshake).
									state.abort_must_staple_detail = nil
									safe_log(
										DEBUG,
										"Setting certificate #"
											.. idx
											.. " ("
											.. pair.cert_id
											.. ") from "
											.. plugin_id
											.. (pair.matched and " [matched key]" or " [unmatched - no key found]")
									)

									local ocsp_cert = pair.cert_pem_for_ocsp
									if type(ocsp_cert) ~= "string" or #ocsp_cert == 0 then
										ocsp_cert = type(pair.cert) == "string" and pair.cert or nil
									end
									local ocsp_fp_hint = pair.cert_fp_for_ocsp
									-- Tri-state for outer abort + scoped probe throw handling.
									local ms_gate = leaf_fail_closed_must_staple(ocsp_cert, ocsp_fp_hint)
									state.leaf_must_staple = leaf_requires_must_staple(ocsp_cert, ocsp_fp_hint)

									-- Dual-cert path already probe-gated above; single-leaf still probes here.
									-- Policy probe does not require ngx.ocsp (attach stays ocsp-gated below).
									-- No PEM/hint + MS/unknown → skip (cannot prove ligand/allow-pin).
									-- Probe pcall throw + MS/unknown → skip (same as probe_ret==false).
									local skip_leaf = false
									if #cert_key_pairs <= 1 then
										if not ocsp_cert and not ocsp_fp_hint then
											if ms_gate then
												safe_log(
													ERR,
													format_staple_decision("fingerprint_unavailable", {
														tag = "OCSP_MUST_STAPLE_REFUSE",
														action = "skip_leaf",
														server_name = server_name or "nil",
														cert = "#" .. idx .. " (" .. pair.cert_id .. ")",
													})
												)
												must_staple_probe_refused = true
												refused_pair = pair
												all_certs_set = false
												skip_leaf = true
											end
										else
											local ok_probe, probe_ok =
												pcall(set_ocsp_from_cache, ocsp_cert, ocsp_fp_hint, true)
											if not ok_probe then
												safe_log(
													ERR,
													"OCSP probe error for cert #"
														.. idx
														.. " ("
														.. pair.cert_id
														.. "): "
														.. tostring(probe_ok)
												)
												if ms_gate then
													must_staple_probe_refused = true
													refused_pair = pair
													all_certs_set = false
													skip_leaf = true
												end
											elseif probe_ok == false then
												safe_log(
													ERR,
													format_staple_decision("probe_failed", {
														tag = "OCSP_MUST_STAPLE_REFUSE",
														action = "skip_leaf",
														server_name = server_name or "nil",
														cert = "#" .. idx .. " (" .. pair.cert_id .. ")",
													})
												)
												must_staple_probe_refused = true
												refused_pair = pair
												all_certs_set = false
												skip_leaf = true
											end
										end
									end

									if not skip_leaf then
										local ok_cert, err_cert = set_cert(pair.cert)
										if not ok_cert then
											safe_log(
												ERR,
												"error while setting certificate #"
													.. idx
													.. " ("
													.. pair.cert_id
													.. ") from "
													.. plugin_id
													.. ": "
													.. (err_cert or "unknown")
											)
											all_certs_set = false
											if ms_gate then
												wipe_ssl_ctx("set_cert_failed")
												state.abort_must_staple = true
												state.abort_must_staple_detail = "set_cert_failed"
												return false
											end
										else
											state.leaf_installed = true
											local ok_key = true
											local err_key = nil

											if pair.key then
												ok_key, err_key = set_priv_key(pair.key)
												if not ok_key then
													safe_log(
														ERR,
														"error while setting private key #"
															.. idx
															.. " ("
															.. pair.cert_id
															.. ") from "
															.. plugin_id
															.. ": "
															.. (err_key or "unknown")
													)
													all_certs_set = false
													wipe_ssl_ctx("set_priv_key_failed")
													if ms_gate then
														state.abort_must_staple = true
														state.abort_must_staple_detail = "set_priv_key_failed"
														return false
													end
												end
											else
												safe_log(
													NOTICE,
													"Certificate #"
														.. idx
														.. " ("
														.. pair.cert_id
														.. ") has no matched private key - continuing without key (may fail during TLS handshake)"
												)
											end
											state.leaf_complete = ok_key and pair.key ~= nil

											if ok_key and ocsp then
												insert(ocsp_candidates, {
													idx = idx,
													cert_id = pair.cert_id,
													ocsp_cert = ocsp_cert,
													ocsp_fp_hint = ocsp_fp_hint,
												})
											elseif ok_key and not ocsp then
												safe_log(
													DEBUG,
													"Skipping OCSP setup because ngx.ocsp is disabled (server_name="
														.. (server_name or "nil")
														.. ")"
												)
											end
										end
									end
								end

								if #ocsp_candidates == 0 and must_staple_probe_refused then
									local staple_mode = get_ocsp_staple_mode()
									local action = "abort"
									if staple_mode == "staple_only" or staple_mode == "open" then
										action = "continue"
									end
									safe_log(
										ERR,
										format_staple_decision("probe_failed", {
											tag = "OCSP_MUST_STAPLE_REFUSE",
											action = action == "continue" and "continue_install" or action,
											mode = tostring(staple_mode),
											server_name = server_name or "nil",
										})
									)
									if action == "abort" then
										state.abort_must_staple = true
										state.abort_must_staple_detail = "probe_failed"
										return false
									end
									-- Soft fuse: install the preferred ClientHello leaf only.
									local soft_pair = refused_pair or preferred_soft_pair or install_pairs[1]
									if soft_pair then
										local ok_cert, err_cert = set_cert(soft_pair.cert)
										if not ok_cert then
											safe_log(
												ERR,
												"soft-fuse set_cert ("
													.. tostring(soft_pair.cert_id)
													.. ") failed: "
													.. (err_cert or "unknown")
											)
											-- clear_certs already ran; do not fall through to static leaf.
											wipe_ssl_ctx("soft_fuse_set_cert_failed")
											state.abort_must_staple = true
											state.abort_must_staple_detail = "soft_fuse_set_cert_failed"
											return false
										end
										state.leaf_installed = true
										state.leaf_must_staple = leaf_requires_must_staple(
											soft_pair.cert_pem_for_ocsp
												or (type(soft_pair.cert) == "string" and soft_pair.cert or nil),
											soft_pair.cert_fp_for_ocsp
										)
										if soft_pair.key then
											local ok_key, err_key = set_priv_key(soft_pair.key)
											if not ok_key then
												safe_log(
													ERR,
													"soft-fuse set_priv_key ("
														.. tostring(soft_pair.cert_id)
														.. ") failed: "
														.. (err_key or "unknown")
												)
												wipe_ssl_ctx("soft_fuse_set_priv_key_failed")
												state.abort_must_staple = true
												state.abort_must_staple_detail = "soft_fuse_set_priv_key_failed"
												return false
											end
										end
										state.leaf_complete = soft_pair.key ~= nil
									else
										state.abort_must_staple = true
										state.abort_must_staple_detail = "soft_fuse_no_pair"
										return false
									end
									return true
								end

								local ocsp_choice = select_ocsp_staple_candidate(ocsp_candidates)
								if ocsp_choice then
									local choice_fp = nil
									if type(ocsp_choice.ocsp_cert) == "string" then
										-- resolve_leaf, not blocks[1]: intermediate-first bags /
										-- lying hints must not bind allow-pin / MS to the wrong SPKI.
										local _, leaf_fp = resolve_leaf(ocsp_choice.ocsp_cert, ocsp_choice.ocsp_fp_hint)
										choice_fp = leaf_fp
									end
									if not choice_fp or choice_fp == "" then
										choice_fp = ocsp_choice.ocsp_fp_hint
									elseif
										ocsp_choice.ocsp_fp_hint
										and type(ocsp_choice.ocsp_fp_hint) == "string"
										and ocsp_choice.ocsp_fp_hint:lower() ~= choice_fp
									then
										log_ocsp_staple_skip(
											cert_pubkey_kind(ocsp_choice.ocsp_cert) == "ec" and "rsa" or "ec",
											ocsp_choice.ocsp_fp_hint,
											"wrong_key_type_hint"
										)
									end
									safe_log(
										DEBUG,
										"Setting OCSP for certificate #"
											.. ocsp_choice.idx
											.. " ("
											.. ocsp_choice.cert_id
											.. ") (server_name="
											.. (server_name or "nil")
											.. ", cert_type="
											.. type(ocsp_choice.ocsp_cert)
											.. ", candidates="
											.. tostring(#ocsp_candidates)
											.. ")"
									)
									local ok_ocsp, ocsp_cert_acceptable =
										pcall(set_ocsp_from_cache, ocsp_choice.ocsp_cert, choice_fp)
									if not ok_ocsp then
										safe_log(
											ERR,
											"OCSP function error for cert #"
												.. ocsp_choice.idx
												.. " ("
												.. ocsp_choice.cert_id
												.. "): "
												.. tostring(ocsp_cert_acceptable)
										)
										-- Leaf already set_cert'd; a throw must not leave Must-Staple naked
										-- or fall through to nginx's static default after clear_certs.
										wipe_ssl_ctx("ocsp_exception")
										if leaf_fail_closed_must_staple(ocsp_choice.ocsp_cert, choice_fp) then
											state.abort_must_staple = true
											state.abort_must_staple_detail = "ocsp_exception"
											return false
										end
										-- Non-MS: wipe left state.certs_cleared; continue to next plugin.
									elseif ocsp_cert_acceptable == false then
										safe_log(
											ERR,
											format_staple_decision(state.abort_must_staple_detail or "unmet", {
												tag = "OCSP_MUST_STAPLE_REFUSE",
												action = "abort",
												server_name = server_name or "nil",
												cert = "#" .. ocsp_choice.idx .. " (" .. ocsp_choice.cert_id .. ")",
											})
										)
										wipe_ssl_ctx(state.abort_must_staple_detail or "unmet")
										state.abort_must_staple = true
										if not state.abort_must_staple_detail then
											state.abort_must_staple_detail = "unmet"
										end
										return false
									else
										safe_log(
											DEBUG,
											"OCSP loaded successfully for certificate #"
												.. ocsp_choice.idx
												.. " ("
												.. ocsp_choice.cert_id
												.. ")"
										)
									end
								end

								if all_certs_set then
									safe_log(
										DEBUG,
										"certificate and key set by "
											.. plugin_id
											.. " (presented_leaves="
											.. tostring(#install_pairs)
											.. ")"
									)
									return true
								else
									safe_log(
										NOTICE,
										"some certificates from "
											.. plugin_id
											.. " failed to set, continuing to next plugin"
									)
								end
							end -- end cert_key_pairs check
						end -- end call_plugin result
					end -- end new_plugin result
				end
			else
				safe_log(
					DEBUG,
					"skipped execution of " .. plugin_id .. " because method ssl_certificate() is not defined"
				)
			end -- end ssl_certificate defined check
		end -- end plugin_lua result check
	end -- end for loop

	safe_log(DEBUG, "ssl_certificate phase ended")

	return true
end

return _M
