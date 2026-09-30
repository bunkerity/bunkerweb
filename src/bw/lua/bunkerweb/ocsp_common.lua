--[[
================================================================================
OCSP Common Module: Shared Configuration, Decision Codes, and Utilities
================================================================================

MODULE OVERVIEW:
This module provides shared constants, logging, and utility functions for the
entire OCSP stapling system. It is the single source of truth for:

1. STAPLE_DECISION codes: Closed vocabulary of outcomes for OCSP staple
   decisions (ok, ok_partial, stapling_off, peer_refuse, tombstoned, etc.)
   used for machine-readable logging and runbook navigation.

2. DROP/KEEP policies: Governs allow-pin bus behavior (fleet-wide peer refuse
   vs local-only policy) and determines when certificates should be
   tombstoned or refused.

3. SNI resolution: Multisite service identification with explicit precision
   tiers (exact match → case-insensitive → domain search) and domain table
   caching using weak maps to auto-invalidate on configuration reload.

4. Settings access: Unified interface for reading multisite settings with
   per-site override support (e.g., SERVICE_NAME_SSL_USE_OCSP_STAPLING).

5. Constants: Shared timing, clock-skew, validation budgets, and path
   definitions used consistently across HTTP and stream subsystems.

ARCHITECTURE:
- Weak-map-based domain caching: SNI index keyed by site_vars table identity
  (not written to shared dict; per-request ngx.ctx caches the vars pointer).
- Per-request variable caching: One datastore lookup per handshake, cached
  in ngx.ctx for multi-lookup efficiency.
- Staple decision normalization: Aliases (canary_*, shared_ligand_*) collapsed
  to closed codes; all logs use fixed field ordering for forensics.

EXPORTS:
- Public (via _M): format_staple_decision, current_ocsp_epoch, stapling_enabled, soften_must_staple, staple_mode
- Internal (via _M.internal): SNI resolution, domain tables, settings access, utility functions for pin/store modules

DEPENDENCIES:
- No external module dependencies; used by all other OCSP modules
- Called by stream ssl_certificate, HTTP endpoints, and background jobs

================================================================================
]]

-- Shared OCSP stapling config, staple_decision codes, logging, paths and constants.
-- Part of bunkerweb.ocsp; other modules use the .internal table, callers use bunkerweb.ocsp.
local _M = {}

local ngx = ngx

-- ============================================================================
-- LOG(level, msg)
-- ============================================================================
-- PURPOSE:
--   Centralized logging wrapper delegating to ngx.log().
--   Single point of control for filtering/redirection if needed.
--
-- PARAMETERS:
--   level (number): ngx log level (ngx.ERR, ngx.INFO, ngx.DEBUG, etc.)
--   msg (string): message string to log
--
-- RETURNS:
--   (nil): side effects only
--
-- SIDE EFFECTS:
--   - Calls: ngx.log(level, msg) for actual logging
--   - Logs: message to error log
--   - Performance: O(1) delegation to ngx
--
-- DESIGN NOTES:
--   - Centralization: enables global log filtering/redirection
--   - Direct delegation: no transformation or buffering
--   - Used throughout: all OCSP modules use this for consistency
--   - Future-proof: decouples internal code from ngx API
--
-- RELATED:
--   - format_staple_decision() — formats structured logs
--   - Used by: all OCSP modules (common, store, pin, chain, etc.)
--
-- ============================================================================
local function log(level, msg)
	ngx.log(level, msg)
end

-- Validate SNI against service's declared domains (security hardening).
-- Returns: true if SNI is in the service's SERVER_NAME list, false otherwise.
-- Domain tables live in a weak map keyed by site_vars — never write onto the
-- shared worker-LRU variables table (that object is also GET /variables / pairs()).
-- Entry stores the SERVER_NAME string used to build so in-place string updates
-- (if any) rebuild instead of serving a stale token set.
--
-- WEAK-MAP ARCHITECTURE:
--   Keys are site_vars table objects (not strings). When configuration is reloaded,
--   a new vars table replaces the old one in the datastore. The weak map automatically
--   drops entries keyed by the old table (no live references remain), preventing
--   stale cache hits across config reloads. No explicit invalidation needed.
local domains_by_site_vars = setmetatable({}, { __mode = "k" })
-- Full SNI index keyed by the vars table identity (same pollution concern).
-- Index stores primary names only; domain tables always come from get_or_build.
-- Same weak-map mechanics: reload → old vars table has no references → entry auto-dropped.
local sni_index_by_vars = setmetatable({}, { __mode = "k" })

-- Build or retrieve cached domain lookup table for a service.
-- Parses SERVER_NAME setting into a set of domain→true mappings (both exact
-- and lowercase variants) for O(1) SNI membership testing.
--
-- Caching strategy: Memoized in weak map (domains_by_site_vars) keyed by
-- site_vars table identity. Entry includes the source SERVER_NAME string so
-- in-place config updates (rare) trigger a rebuild instead of stale cache hits.
--
-- @param site_vars: service configuration table (vars[primary_service_id])
-- @return: {domain → true, domain_lower → true, ...} for all SERVER_NAME tokens
-- @note: Weak-map key ensures cache is auto-invalidated when configuration
--        is reloaded (new vars table replaces old one in datastore)
--
-- DESIGN: Weak-map memoization with source string validation
--   1. Key by site_vars TABLE identity (not content) — survives across LuaJIT gcs
--   2. Store source=SERVER_NAME string in entry — detects in-place mutations
--   3. Rebuild if source changed → no stale caches from config hotpatches
--   4. Both exact + lowercase entries for case-insensitive SNI matching
--   5. O(1) lookup via domain_table[sni] or domain_table[sni_lower]
-- ============================================================================
-- GET_OR_BUILD_DOMAIN_TABLE(site_vars)
-- ============================================================================
-- PURPOSE:
--   Builds or retrieves cached domain lookup table for SNI validation.
--   Weak-map memoized; auto-invalidates on config reload.
--
-- PARAMETERS:
--   site_vars (table): service configuration {SERVER_NAME: "...", ...}
--
-- RETURNS:
--   (table): {domain→true, domain_lower→true, ...} for O(1) SNI membership
--   (empty): if site_vars invalid or SERVER_NAME missing
--
-- SIDE EFFECTS:
--   - Cache: memoizes in domains_by_site_vars weak map (keyed by site_vars)
--   - Reads: site_vars["SERVER_NAME"] setting
--   - Performance: O(1) cache hit, O(n) rebuild where n = domain count
--
-- DESIGN NOTES:
--   - Weak-map key: table identity (survives LuaJIT gc)
--   - Source tracking: detects in-place mutations (config hotpatches)
--   - Case normalization: both exact and lowercase entries
--   - O(1) lookup: via domain_table[sni] or [sni_lower]
--   - Auto-invalidate: config reload → new vars → old entry dropped
--
-- RELATED:
--   - sni_in_service_domains() — uses this table
--   - build_sni_index() — higher-level SNI resolution
--
-- ============================================================================
local function get_or_build_domain_table(site_vars)
	if type(site_vars) ~= "table" then
		return {}
	end
	local names = site_vars["SERVER_NAME"]
	local source = type(names) == "string" and names or ""
	local entry = domains_by_site_vars[site_vars]
	if entry and entry.source == source then
		return entry.domains
	end
	local domain_table = {}
	if source ~= "" then
		for domain in source:gmatch("%S+") do
			domain_table[domain] = true
			domain_table[domain:lower()] = true
		end
	end
	domains_by_site_vars[site_vars] = { source = source, domains = domain_table }
	return domain_table
end

-- ============================================================================
-- SNI_IN_SERVICE_DOMAINS(site_vars, sni)
-- ============================================================================
-- PURPOSE:
--   Validates SNI against service's declared SERVER_NAME domains.
--   Case-insensitive membership test (security hardening).
--
-- PARAMETERS:
--   site_vars (table): service configuration {SERVER_NAME: "...", ...}
--   sni (string): SNI hostname from TLS handshake
--
-- RETURNS:
--   (true): SNI is in the service's domain list (exact or lowercase match)
--   (false): SNI not found or invalid input
--
-- SIDE EFFECTS:
--   - Calls: get_or_build_domain_table() (may cache in weak map)
--   - Reads: site_vars["SERVER_NAME"]
--   - Performance: O(1) table lookup (after domain table built)
--
-- DESIGN NOTES:
--   - Case-insensitive: SNI lowercased for comparison
--   - Security: rejects mismatched SNI (prevents cert misuse)
--   - Efficiency: leverages cached domain_table (O(1))
--   - Fail-closed: false for invalid input (conservative)
--   - Used by: certificate selection in multisite mode
--
-- RELATED:
--   - get_or_build_domain_table() — builds lookup table
--   - build_sni_index() — higher-level SNI resolution
--
-- ============================================================================
local function sni_in_service_domains(site_vars, sni)
	if not site_vars or not sni or type(site_vars) ~= "table" then
		return false
	end
	local names = site_vars["SERVER_NAME"]
	if type(names) ~= "string" or names == "" then
		return false
	end
	local sni_lower = tostring(sni):lower()
	local domain_table = get_or_build_domain_table(site_vars)
	return domain_table[sni] or domain_table[sni_lower] or false
end

-- Build efficient O(1) index for SNI → primary service ID resolution.
-- Pre-computes: (1) primary service ID names (exact + lowercase for Tier 2),
-- (2) domain primaries set (services with SERVER_NAME for Tier 3 search).
-- Validation: tracks service_count to detect in-place mutation of vars table
-- (config reload triggers index rebuild on count mismatch).
--
-- @param vars: Configuration table {primary_service_id → site_vars, ...}
-- @return: {primary_lower={...}, domain_primaries={...}, service_count=N}
-- @note: Memoized in sni_index_by_vars (weak map); rebuilt if service count changes
-- ============================================================================
-- BUILD_SNI_INDEX(vars)
-- ============================================================================
-- PURPOSE:
--   Builds efficient O(1) SNI lookup index with Tier 2 & Tier 3 caching.
--   Memoized via weak map; auto-rebuilds on config reload (service count change).
--
-- PARAMETERS:
--   vars (table): Configuration {service_id → site_vars, global → {...}, ...}
--
-- RETURNS:
--   (table): {primary_lower={map}, domain_primaries={set}, service_count=N}
--
-- SIDE EFFECTS:
--   - Calls: get_or_build_domain_table() for domain cache warm-up
--   - Cache: stored in sni_index_by_vars weak map (keyed by vars table)
--   - Performance: O(n) where n = services with SERVER_NAME
--
-- DESIGN NOTES:
--   - Tier 2 index: primary_lower maps lowercase names to originals
--   - Tier 3 prep: domain_primaries lists services to search in Tier 3
--   - Service count: detects in-place mutations (triggers rebuild)
--   - Weak map: auto-invalidates when vars replaced on config reload
--   - Global skip: never treats "global" settings bag as service
--
-- RELATED:
--   - resolve_multisite_service_id_from_vars() — uses this index
--   - sni_in_service_domains() — Tier 3 domain matching
--
-- ============================================================================
local function build_sni_index(vars)
	if not vars or type(vars) ~= "table" then
		return {}
	end

	local index = {
		primary_lower = {}, -- Map: lowercase_name -> original_name
		domain_primaries = {}, -- Set: primary_name → true (has SERVER_NAME)
		service_count = 0, -- Track count to detect in-place mutations of vars
	}

	for primary, site_vars in pairs(vars) do
		-- Skip global + underscore meta keys (never treat as services).
		if
			primary ~= "global"
			and type(primary) == "string"
			and primary:sub(1, 1) ~= "_"
			and type(site_vars) == "table"
		then
			index.service_count = index.service_count + 1
			local primary_lower = primary:lower()
			-- First wins when two primaries lower to the same string.
			if not index.primary_lower[primary_lower] then
				index.primary_lower[primary_lower] = primary
			end

			if type(site_vars["SERVER_NAME"]) == "string" and site_vars["SERVER_NAME"] ~= "" then
				index.domain_primaries[primary] = true
				-- Warm domain cache (source-validated); Tier 3 re-fetches via get_or_build.
				get_or_build_domain_table(site_vars)
			end
		end
	end

	return index
end

-- Resolve SNI to service ID using explicit precision tiers and O(1) index lookup.
-- Precision tiers (highest to lowest):
--   Tier 1: Exact match on primary service ID (FQDN as service name)
--   Tier 2: Case-insensitive match on primary service ID (via cached index)
--   Tier 3: SERVER_NAME token search (exact then case-insensitive)
-- When multiple primaries match Tier 3 domains, lexicographic first wins to ensure
-- deterministic behavior across nondeterministic pairs() iteration.
--
-- @param vars: Configuration table (all multisite definitions)
-- @param sni: SNI hostname from TLS ClientHello
-- @return: Primary service ID (key in vars) or nil
-- @note: Cached index validates service_count; rebuilds if vars was mutated in-place
--
-- ALGORITHM: Three-tier SNI matching with deterministic tiebreaking
--   Tier 1: O(1) exact lookup — vars[sni] is a table and sni != "global" / "_*"
--   Tier 2: O(1) cached index lookup — sni_index.primary_lower[sni_lower]
--           (pre-indexed during build_sni_index; first-wins on collisions)
--   Tier 3: O(domains) domain table walk over all primaries with SERVER_NAME
--           (every domain_table O(1) lookup; lexicographic tiebreak for multi-match)
--   Invariant: service_count tracking detects in-place mutations; rebuilds on mismatch
--
-- WHY TIERS:
--   Tier 1 handles config where service primary_id equals the SNI (most common).
--   Tier 2 handles case variance in service names (FQDNs are case-insensitive).
--   Tier 3 handles SERVER_NAME multivalue (multiple FQDNs aliasing one service).
--   Lexicographic tiebreak ensures same result across LuaJIT nondeterministic iteration
--   (nondeterministic pairs() → must impose deterministic order via comparison).
--
-- PERFORMANCE:
--   Tier 1 hit: O(1) table lookup (most handshakes)
--   Tier 2 hit: O(1) cached index (subdomains or case variance)
--   Tier 3: O(k * d) where k = services with SERVER_NAME, d = domains per service
--           (typical: k ≤ 50, d ≤ 5, lexicographic tiebreak adds O(k*log k) comparison)
--
-- MULTISITE CONFIG EXAMPLE:
--   vars = {
--     global = {...},
--     "www.example.com" = {SERVER_NAME = "www.example.com api.example.com", ...},
--     "cdn.example.com" = {SERVER_NAME = "cdn.example.com", ...},
--   }
--   resolve("www.example.com") → Tier 1 hit: "www.example.com"
--   resolve("api.example.com") → Tier 3 hit: "www.example.com" (SERVER_NAME token)
--   resolve("Api.example.com") → Tier 3 hit (case-insensitive): "www.example.com"
-- ============================================================================
-- RESOLVE_MULTISITE_SERVICE_ID_FROM_VARS(vars, sni)
-- ============================================================================
-- PURPOSE:
--   Resolves SNI hostname to multisite service ID via three-tier precision matching.
--   Deterministic tiebreaking ensures consistent results across nondeterministic iteration.
--
-- PARAMETERS:
--   vars (table): Configuration {service_id → site_vars, ...}
--   sni (string): SNI hostname from TLS handshake
--
-- RETURNS:
--   (string): service ID (primary key in vars)
--   (nil): if SNI not found in any tier
--
-- SIDE EFFECTS:
--   - Calls: build_sni_index() if cached index stale
--   - Cache: sni_index_by_vars weak map (keyed by vars table identity)
--   - Performance: O(1) Tier 1/2, O(k*d*log k) worst-case Tier 3
--
-- DESIGN NOTES:
--   - Tier 1: exact match on service primary ID (most common)
--   - Tier 2: case-insensitive via cached index (subdomains)
--   - Tier 3: SERVER_NAME token search with lexicographic tiebreak
--   - Service count validation: detects in-place mutations of vars
--   - Deterministic: nondeterministic pairs() overcome via sorting
--
-- RELATED:
--   - build_sni_index() — caches Tier 2 index
--   - sni_in_service_domains() — Tier 3 domain lookup
--   - get_site_variable() — uses this for multisite setting override
--
-- ============================================================================
local function resolve_multisite_service_id_from_vars(vars, sni)
	if not sni or type(vars) ~= "table" then
		return nil
	end

	-- Tier 1: exact match on primary service id (FQDN as service name).
	-- Skip "global" (settings bag, not a service) and underscore meta keys.
	if type(vars[sni]) == "table" and sni ~= "global" and tostring(sni):sub(1, 1) ~= "_" then
		return sni
	end

	local sni_index = sni_index_by_vars[vars]
	-- Validate cached index: if service count changed, vars was mutated in-place; rebuild
	if sni_index then
		local current_service_count = 0
		for primary, _ in pairs(vars) do
			if primary ~= "global" and type(primary) == "string" and primary:sub(1, 1) ~= "_" then
				current_service_count = current_service_count + 1
			end
		end
		if current_service_count ~= sni_index.service_count then
			sni_index = nil
		end
	end

	if not sni_index then
		sni_index = build_sni_index(vars)
		sni_index_by_vars[vars] = sni_index
	end

	local sni_lower = tostring(sni):lower()

	-- Tier 2: case-insensitive match via pre-indexed lowercase names
	local primary_from_lower = sni_index.primary_lower[sni_lower]
	if primary_from_lower then
		return primary_from_lower
	end

	-- Tier 3: domain search — lexicographic primary wins when tokens overlap
	-- (pairs() order is nondeterministic across workers / LuaJIT).
	-- Domain tables always via get_or_build (rebuilds if SERVER_NAME string changed).
	local best = nil
	for primary in pairs(sni_index.domain_primaries) do
		local domain_table = get_or_build_domain_table(vars[primary])
		if domain_table[sni] or domain_table[sni_lower] then
			if not best or primary < best then
				best = primary
			end
		end
	end

	return best
end

-- Apply per-site setting override: check site-specific value, fall back to global.
-- Implements multisite configuration hierarchy: site-specific > global (default).
-- Used for settings like SSL_USE_OCSP_STAPLING that can have per-service values.
--
-- @param vars: Configuration table
-- @param service_id: Primary service ID (key in vars for this site)
-- @param name: Setting name (e.g., "SSL_USE_OCSP_STAPLING")
-- @param global_value: Value from vars["global"][name] (fallback)
-- @return: Site-specific value if present, otherwise global_value
-- @note: service_id=nil or vars[service_id] not a table → returns global_value
-- ============================================================================
-- APPLY_SITE_OVERRIDE(vars, service_id, name, global_value)
-- ============================================================================
-- PURPOSE:
--   Applies per-site setting override: site-specific wins global (multisite hierarchy).
--   Returns service-specific value if present, else global fallback.
--
-- PARAMETERS:
--   vars (table): Configuration {service_id → site_vars, ...}
--   service_id (string|nil): Primary service ID for this site
--   name (string): Setting name (e.g., "SSL_USE_OCSP_STAPLING")
--   global_value (any): Fallback value from vars["global"][name]
--
-- RETURNS:
--   (value): site-specific value if found, else global_value
--
-- SIDE EFFECTS:
--   - Reads: vars[service_id][name]
--   - Performance: O(1) table lookup
--
-- DESIGN NOTES:
--   - Hierarchy: service_id value wins global (per-site override)
--   - Nil safe: returns global if service_id missing or not a table
--   - Simple: no transformation or validation (caller validates)
--   - Used by: get_site_variable() for multisite resolution
--
-- RELATED:
--   - get_site_variable() — multisite setting read with SNI resolution
--   - resolve_multisite_service_id_from_vars() — SNI to service_id
--
-- ============================================================================
local function apply_site_override(vars, service_id, name, global_value)
	if not service_id or type(vars[service_id]) ~= "table" then
		return global_value
	end
	local site_value = vars[service_id][name]
	if site_value ~= nil then
		return site_value
	end
	return global_value
end

-- Cached variables access implementing two-tier caching strategy.
-- Tier 1 (per-request): ngx.ctx caches the vars table pointer for this handshake.
-- Tier 2 (per-worker): datastore worker-LRU caches (get(..., true)) across requests.
-- This reduces the cost of per-handshake multisite resolution from full datastore
-- lookup to ngx.ctx table read.
--
-- @param internalstore: Datastore wrapper (bunkerweb.datastore instance)
-- @return: Variables table {global={...}, primary1={...}, ...} or nil
-- @note: First handshake on worker pays datastore cost; subsequent handshakes
--        hit ngx.ctx (per-request) + worker LRU (per-worker) caches
-- ============================================================================
-- GET_VARS_CACHED(internalstore)
-- ============================================================================
-- PURPOSE:
--   Gets configuration variables with two-tier caching (per-request + worker LRU).
--   Avoids datastore cost for repeated handshakes on same worker.
--
-- PARAMETERS:
--   internalstore (table): Datastore wrapper (bunkerweb.datastore)
--
-- RETURNS:
--   (table): {global={...}, service_id={...}, ...} configuration
--   (nil): if datastore unavailable or variables not found
--
-- SIDE EFFECTS:
--   - Reads: ngx.ctx cache (per-request), internalstore worker-LRU
--   - Cache: ngx.ctx stores vars pointer (full handshake lifespan)
--   - Performance: O(1) ngx.ctx hit, O(n) datastore miss (n=size of vars)
--
-- DESIGN NOTES:
--   - Tier 1: per-request ngx.ctx (handshake lifespan)
--   - Tier 2: worker-LRU datastore cache (cross-request)
--   - Identification: internalstore identity used as cache key
--   - First hit: pays datastore cost, subsequent hits from ngx.ctx
--   - Idempotent: safe to call multiple times in same request
--
-- RELATED:
--   - get_site_variable() — uses this to read settings
--   - resolve_multisite_service_id_from_vars() — uses vars from this
--
-- ============================================================================
local function get_vars_cached(internalstore)
	if not internalstore then
		return nil
	end

	local internalstore_id = tostring(internalstore):match("[0-9a-f]+$") or tostring(internalstore)
	local req_cache_key = "ocsp_vars_" .. internalstore_id

	if ngx.ctx and ngx.ctx[req_cache_key] then
		return ngx.ctx[req_cache_key]
	end

	local ok, vars = pcall(function()
		return internalstore:get("variables", true)
	end)

	if ok and type(vars) == "table" then
		if ngx.ctx then
			ngx.ctx[req_cache_key] = vars
		end
		return vars
	end

	return nil
end

-- Read a multisite setting: per-site (primary service id) wins over global.
-- SNI→service index is keyed by vars-table identity (weak map), not written onto
-- the shared variables object; reload replaces that table and forces a rebuild.
-- Per-request ngx.ctx still caches the vars pointer (optimization #1).
-- ============================================================================
-- GET_SITE_VARIABLE(internalstore, server_name, name)
-- ============================================================================
-- PURPOSE:
--   Reads multisite setting with per-site override: service_name_SETTING wins global.
--   Resolves SNI to service ID; applies per-site override if multisite mode.
--
-- PARAMETERS:
--   internalstore (table): datastore with variables table
--   server_name (string|nil): multisite service name (SNI, optional)
--   name (string): setting name (e.g., "SSL_USE_OCSP_STAPLING")
--
-- RETURNS:
--   (value): per-site override if found and multisite mode, else global value
--   (nil): if setting missing or multisite disabled
--
-- SIDE EFFECTS:
--   - Calls: get_vars_cached(), resolve_multisite_service_id_from_vars()
--   - Calls: apply_site_override() for per-site resolution
--   - Reads: MULTISITE, {SERVICE_NAME}_{SETTING}, global {SETTING}
--   - Performance: O(1) cache hit, O(n) SNI resolution on multisite (n=service count)
--
-- DESIGN NOTES:
--   - Per-site wins: SERVICE_NAME_SETTING beats global SETTING
--   - Weak-map SNI index: auto-invalidates on config reload
--   - Per-request cache: vars pointer cached in ngx.ctx
--   - Multisite guard: SNI resolution only if MULTISITE=yes
--   - Fallback: global setting when no per-site override
--
-- RELATED:
--   - resolve_multisite_service_id_from_vars() — SNI→service mapping
--   - apply_site_override() — applies per-site value
--   - stapling_enabled() — uses this for SSL_USE_OCSP_STAPLING
--
-- ============================================================================
local function get_site_variable(internalstore, server_name, name)
	local vars = get_vars_cached(internalstore)
	if not vars or type(vars["global"]) ~= "table" then
		return nil
	end
	local value = vars["global"][name]
	if vars["global"]["MULTISITE"] == "yes" and server_name then
		-- Per-request SNI resolution: always resolve against current config, no caching
		local service_id = resolve_multisite_service_id_from_vars(vars, server_name)
		-- Separate phase: apply per-site override
		value = apply_site_override(vars, service_id, name, value)
	end
	return value
end

-- A per-site value wins. The plugin default is "no".
-- ============================================================================
-- STAPLING_ENABLED(internalstore, server_name)
-- ============================================================================
-- PURPOSE:
--   Checks if OCSP stapling is enabled for a server via SSL_USE_OCSP_STAPLING.
--   Per-site setting wins; defaults to false (plugin default is "no").
--
-- PARAMETERS:
--   internalstore (table): datastore with variables
--   server_name (string): multisite service name (for override lookup)
--
-- RETURNS:
--   (true): SSL_USE_OCSP_STAPLING=yes/true/1/on (boolean or string)
--   (false): setting missing, nil, or falsy value
--
-- SIDE EFFECTS:
--   - Calls: get_site_variable() — reads setting from store
--   - Reads: SSL_USE_OCSP_STAPLING per-site setting
--   - Performance: O(1) variable lookup + string parse
--
-- DESIGN NOTES:
--   - Per-site override: SERVER_NAME_SSL_USE_OCSP_STAPLING wins
--   - Fallback: global SSL_USE_OCSP_STAPLING, then default false
--   - String parsing: accepts "1", "true", "on", "yes" (case-insensitive)
--   - Boolean passthrough: type-check before parsing
--   - Default safe: "no" (no stapling) when not explicitly enabled
--
-- RELATED:
--   - ocsp_staple_mode() — checks mode (normal/staple_only/open)
--   - get_site_variable() — reads multisite settings
--
-- ============================================================================
local function stapling_enabled(internalstore, server_name)
	local value = get_site_variable(internalstore, server_name, "SSL_USE_OCSP_STAPLING")
	if type(value) == "boolean" then
		return value
	end
	if value == nil then
		return false
	end
	local str = tostring(value):lower()
	return str == "1" or str == "true" or str == "on" or str == "yes"
end

-- Must-Staple fuse both HTTP and stream read. Default "normal" (fail-close).
-- staple_only / open soft-continue instead of aborting the handshake.
-- Stapling off (SSL_USE_OCSP_STAPLING=no, the default) → effective "open": no
-- staple can be served, so Must-Staple is not enforced (upstream served unstapled).
-- This is intentional policy (not a silent bug): refuse codes still log
-- ssl_use_ocsp_stapling_no when a Must-Staple leaf hits the stapling-off path.
-- Unknown OCSP_STAPLE_MODE values coerce to "normal" (fail-close), never soft-open.
-- ============================================================================
-- OCSP_STAPLE_MODE(internalstore, server_name)
-- ============================================================================
-- PURPOSE:
--   Reads Must-Staple soft-fuse mode: "normal" (fail-close), "staple_only", or "open".
--   Per-site setting via OCSP_STAPLE_MODE; defaults to "normal" when stapling enabled.
--
-- PARAMETERS:
--   internalstore (table): datastore with variables
--   server_name (string): multisite service name (for override lookup)
--
-- RETURNS:
--   (string): one of "normal" (default), "staple_only", or "open" (soft-fuse)
--
-- SIDE EFFECTS:
--   - Calls: stapling_enabled(), get_site_variable()
--   - Reads: SSL_USE_OCSP_STAPLING and OCSP_STAPLE_MODE settings
--   - Performance: O(1) variable lookups + string parse
--
-- DESIGN NOTES:
--   - Per-site override: SERVER_NAME_OCSP_STAPLE_MODE wins
--   - Mode semantics: normal = fail-close, staple_only/open = soft-fuse
--   - Stapling off: returns "open" even if OCSP_STAPLE_MODE says otherwise
--   - Unknown values: coerce to "normal" (never soft-open on bad config)
--   - Policy: intentional; Must-Staple still logged but not enforced
--
-- RELATED:
--   - stapling_enabled() — checks if stapling is enabled
--   - get_site_variable() — reads multisite settings
--   - must_staple_refuse() (ocsp_pin) — uses mode to filter enforcement
--
-- ============================================================================
local function ocsp_staple_mode(internalstore, server_name)
	if not stapling_enabled(internalstore, server_name) then
		return "open"
	end
	local value = get_site_variable(internalstore, server_name, "OCSP_STAPLE_MODE")
	if value == nil or value == "" then
		return "normal"
	end
	local str = tostring(value):lower()
	if str == "staple_only" or str == "open" or str == "normal" then
		return str
	end
	return "normal"
end

--[[
Closed vocabulary of OCSP staple outcomes. Each code maps to a section in the
SSL runbook (docs/ssl.md) for operators troubleshooting stapling failures.

USAGE: format_staple_decision(code, {fields}) normalizes raw reasons to these
codes and outputs machine-readable logs with canonical field ordering (no
information leakage, forensics auditable).

CATEGORIES (by outcome):
  Success: ok, ok_partial (multi-staple with NULL slots)
  Configuration: stapling_off, skip_slot, ssl_use_ocsp_stapling_no
  Metadata/Lifecycle: tombstoned, response_stale, response_not_found,
    response_empty, cluster_floor, not_paged, shard_not_paged
  Validation: validate_budget, validate_exhausted, probe_failed, probe_no_material
  Certificate: certid_mismatch, certid_unreadable, issuer_ambiguous,
    issuer_unavailable, issuer_unresolved_must_staple, aia_uri_mismatch,
    aia_uri_unpinned, aia_uri_missing_on_leaf, aia_uri_leaf_unavailable,
    fingerprint_unavailable, fingerprint_chain_unavailable, wrong_key_type_staple
  Time: thisUpdate_future, thisUpdate_stale, thisUpdate_unreadable,
    lifetime_invalid, lifetime_too_long
  Must-Staple: intermediate_must_staple_libssl, intermediate_must_staple_colony,
    multi_staple_attach_failed, set_staple_failed, set_staple_exception
  Generation/Recall: canary_refused (canary_*_* prefixed), peer_refuse,
    peer_refuse_bus, allow_pin_missing, allow_pin_expired, allow_pin_mismatch,
    allow_pin_claim_inflight, gen_type_drift
  Shared/Ligand: shared_ligand (ligand_* prefixed), ligand_* details
  Other: ngx_ocsp_unavailable, await_sni, serial_blacklisted, unmet

ALIAS NORMALIZATION (format_staple_decision):
  Raw "canary_*" → "canary_refused" (machine search requires exact prefix)
  Raw "shared_ligand_*" → "shared_ligand" (collapse ligand details)
  Pre-alias raw saved as refuse_cause= for pin DROP/KEEP policy lookup
]]
local STAPLE_DECISION = {
	ok = true,
	ok_partial = true,
	stapling_off = true,
	skip_slot = true,
	cluster_floor = true,
	not_paged = true,
	aia_uri_mismatch = true,
	aia_uri_unpinned = true,
	aia_uri_missing_on_leaf = true,
	aia_uri_leaf_unavailable = true,
	ssl_use_ocsp_stapling_no = true,
	ngx_ocsp_unavailable = true,
	response_not_found = true,
	response_stale = true,
	serial_blacklisted = true,
	tombstoned = true,
	shared_ligand = true,
	certid_mismatch = true,
	certid_unreadable = true,
	issuer_ambiguous = true,
	set_staple_failed = true,
	set_staple_exception = true,
	fingerprint_unavailable = true,
	wrong_key_type_staple = true,
	probe_failed = true,
	probe_no_material = true,
	thisUpdate_future = true,
	thisUpdate_stale = true,
	lifetime_invalid = true,
	lifetime_too_long = true,
	thisUpdate_unreadable = true,
	canary_refused = true,
	peer_refuse = true,
	peer_refuse_bus = true,
	allow_pin_missing = true,
	allow_pin_expired = true,
	allow_pin_mismatch = true,
	-- μs claim/restore window (or reclaimable orphan claim) — not "never canaried".
	allow_pin_claim_inflight = true,
	-- soft_recall_gen present but non-integer (type drift). Local refuse; KEEP pin.
	gen_type_drift = true,
	await_sni = true,
	intermediate_must_staple_libssl = true,
	-- Colony min is leaf-only (a live peer lacks multi-staple); not a local libssl gap.
	-- Transient: must not stick after the leaf-only worker leaves.
	intermediate_must_staple_colony = true,
	-- Fingerprint-only attach/probe with no PEM chain: intermediate Must-Staple unprovable.
	fingerprint_chain_unavailable = true,
	-- Multi-staple stack build / SSL_set0 failed after leaf set; intermediate MS refused.
	multi_staple_attach_failed = true,
	-- Issuer DN in the bag did not resolve, and Must-Staple intermediates were
	-- omitted from the presented chain. Refuse so leaf-only attach cannot
	-- succeed while those intermediates were in the bag.
	issuer_unresolved_must_staple = true,
	-- Soft ngx.ocsp.validate budget aborted during leaf issuer tries; multi-staple
	-- stack was never attached (not ok_partial — that name is NULL-slot attach only).
	validate_budget = true,
	-- Body present but no accepted issuer PEM/SPKI for ngx.ocsp.validate (not a missing DER).
	issuer_unavailable = true,
	-- Every issuer candidate failed validate (body present; not empty queue, not missing DER).
	validate_exhausted = true,
	-- Disk ocsp.der exists but is zero-length (truncate race); not ENOENT.
	response_empty = true,
	-- Fingerprint-only path cannot finish a gen-bound force_ffi walk (no leaf PEM issuers).
	force_ffi_pending = true,
	unmet = true,
}

--[[
Allow-pin bus policy: determines whether a refuse reason should DROP (revoke)
the fleet allow-pin or KEEP it (local refuse only, do not touch shared state).

This is the single source of truth for pin.lua and the SSL runbook.

POLICY RATIONALE:
- DROP: Semantic poison about this (body, leaf, colony, canary). If one worker
  refuses due to data integrity (serial mismatch, cert/issuer binding, etc.),
  sibling workers must also refuse until a new generation is canary-paged.

- KEEP: Transient local state or this worker's view. Examples: stale reader
  (response_stale), clock skew (thisUpdate_future), budget abort (validate_budget),
  or soft-fuse mode (set_staple_failed). Revoking the fleet pin would cause
  Must-Staple outage if other workers have valid state.

KEYS: Raw refuse_cause strings BEFORE runbook alias collapse. This ensures
pin policy is deterministic: aliasing "shared_ligand_missing" → "shared_ligand"
happens after DROP/KEEP determination.

INVARIANT (enforced in should_skip_peer_bus): Every cause that should_skip_peer_bus
returns true for MUST also be in KEEP_ALLOW_ON_REFUSE (transient refuses never
enter the fleet bus).
]]
local DROP_ALLOW_ON_REFUSE = {
	certid_mismatch = true,
	aia_uri_mismatch = true,
	aia_uri_unpinned = true,
	aia_uri_missing_on_leaf = true,
	aia_uri_leaf_unavailable = true,
	tombstoned = true,
	serial_blacklisted = true,
	cluster_floor = true,
	-- Bare "shared_ligand" is the runbook ALIAS — KEEP (see below). Only concrete
	-- binding failures DROP. ligand_missing stays KEEP (promote-tear ENOENT).
	ligand_mismatch = true,
	der_sha256_mismatch = true,
	missing_der_sha256 = true,
	invalid_der_sha256 = true,
	fingerprint_mismatch_or_missing_meta = true,
	canary_refused = true,
}

local KEEP_ALLOW_ON_REFUSE = {
	not_paged = true,
	validate_budget = true,
	intermediate_must_staple_colony = true,
	intermediate_must_staple_libssl = true,
	set_staple_failed = true,
	set_staple_exception = true,
	response_not_found = true,
	response_stale = true,
	await_sni = true,
	probe_failed = true,
	allow_pin_missing = true,
	allow_pin_expired = true,
	allow_pin_mismatch = true,
	allow_pin_claim_inflight = true,
	gen_type_drift = true,
	ligand_missing = true,
	shared_ligand = true,
	peer_refuse_unavailable = true,
	fingerprint_chain_unavailable = true,
	multi_staple_attach_failed = true,
	issuer_unresolved_must_staple = true,
	issuer_unavailable = true,
	validate_exhausted = true,
	response_empty = true,
	force_ffi_pending = true,
	-- CertID parse/ambiguity glitches (not serial/issuer poison) — do not DROP pin.
	certid_unreadable = true,
	issuer_ambiguous = true,
	probe_no_material = true,
	thisUpdate_future = true,
	thisUpdate_stale = true,
	lifetime_invalid = true,
	lifetime_too_long = true,
	thisUpdate_unreadable = true,
	-- Local policy / capability / missing material — never fleet pin or peer bus.
	ssl_use_ocsp_stapling_no = true,
	ngx_ocsp_unavailable = true,
	fingerprint_unavailable = true,
	wrong_key_type_staple = true,
	stapling_off = true,
	skip_slot = true,
	unmet = true,
	peer_refuse = true,
	peer_refuse_bus = true,
	-- Pre-alias raws that normalize to KEEP targets (exact-match for should_skip_peer_bus).
	variables_unavailable = true,
	wrong_key_type_hint = true,
	single_slot_ecdsa_prefer = true,
	single_slot_rsa_prefer = true,
}

-- DROP causes that may revoke using meta.der_sha256 when resp is nil.
local META_ONLY_DROP_ALLOW = {
	tombstoned = true,
	serial_blacklisted = true,
	cluster_floor = true,
	canary_refused = true,
}

local STAPLE_DECISION_ALIAS = {
	single_slot_ecdsa_prefer = "skip_slot",
	single_slot_rsa_prefer = "skip_slot",
	wrong_key_type_hint = "skip_slot",
	variables_unavailable = "stapling_off",
	-- Raw ligand_verdict reasons stay on refuse_cause=; runbook staple_decision=
	-- collapses to shared_ligand so ops still land on one README section.
	ligand_missing = "shared_ligand",
	ligand_mismatch = "shared_ligand",
	der_sha256_mismatch = "shared_ligand",
	missing_der_sha256 = "shared_ligand",
	invalid_der_sha256 = "shared_ligand",
	fingerprint_mismatch_or_missing_meta = "shared_ligand",
	peer_refuse_unavailable = "peer_refuse",
}

-- Normalize staple_decision codes to closed vocabulary for machine-readable logs.
-- Maps dynamic/detailed reason codes (canary_*, shared_ligand_*) to fixed categories
-- (canary_refused, shared_ligand) while preserving the original reason for auditing.
-- Used by format_staple_decision to generate machine-readable, runbook-linkable logs.
--
-- @param code: decision code string (e.g., "certid_mismatch", "canary_cert_changed", etc.)
-- @return: normalized_code (closed vocabulary), alias_detail (pre-normalize raw or nil)
--
-- NORMALIZATION RULES:
--   1. Exact match in STAPLE_DECISION_ALIAS → return alias, raw (e.g., "wrong_key_type_hint" → "skip_slot", "wrong_key_type_hint")
--   2. Prefix "canary_" → return "canary_refused", raw (e.g., "canary_cert_changed" → "canary_refused", "canary_cert_changed")
--   3. Prefix "shared_ligand_" → return "shared_ligand", raw (e.g., "shared_ligand_missing" → "shared_ligand", "shared_ligand_missing")
--   4. Exact match in STAPLE_DECISION → return code, nil (e.g., "certid_mismatch" → "certid_mismatch", nil)
--   5. Default → return "unmet", raw (unknown code)
--
-- DESIGN RATIONALE:
--   - Operators can grep logs for staple_decision=shared_ligand to find all ligand issues
--   - Raw reason in refuse_cause= preserves details for forensics (pin DROP/KEEP lookup)
--   - Runbook navigation: fixed codes stay stable; detailed reasons can evolve
--
-- EXAMPLES:
--   normalize_staple_decision("certid_mismatch") → "certid_mismatch", nil
--   normalize_staple_decision("canary_cert_changed") → "canary_refused", "canary_cert_changed"
--   normalize_staple_decision("shared_ligand_missing") → "shared_ligand", "shared_ligand_missing"
--   normalize_staple_decision("unknown_code") → "unmet", "unknown_code"
-- ============================================================================
-- NORMALIZE_STAPLE_DECISION(code)
-- ============================================================================
-- PURPOSE:
--   Normalizes dynamic decision codes to closed vocabulary for runbook navigation.
--   Preserves raw detail for forensics; aliases complex codes to fixed categories.
--
-- PARAMETERS:
--   code (string|nil): decision code (e.g., "certid_mismatch", "canary_cert_changed")
--
-- RETURNS:
--   (string, string|nil): (normalized_code, alias_detail)
--     - normalized_code: closed-vocabulary code (runbook section name)
--     - alias_detail: pre-alias raw if aliased, else nil
--
-- SIDE EFFECTS:
--   - Reads: STAPLE_DECISION_ALIAS and STAPLE_DECISION tables
--   - Logs: none
--   - Performance: O(1) table lookup + prefix check
--
-- DESIGN NOTES:
--   - Closed vocabulary: enables fixed runbook sections
--   - Prefix rules: canary_* → "canary_refused", shared_ligand_* → "shared_ligand"
--   - Alias preservation: raw detail preserved in refuse_cause for DROP/KEEP policy
--   - Fail-safe: unknown codes map to "unmet" (conservative)
--   - Used by: format_staple_decision() for canonical logging
--
-- RELATED:
--   - format_staple_decision() — uses result for log formatting
--   - STAPLE_DECISION_ALIAS, STAPLE_DECISION — policy tables
--
-- ============================================================================
local function normalize_staple_decision(code)
	local raw = tostring(code or "unmet")
	if STAPLE_DECISION_ALIAS[raw] then
		return STAPLE_DECISION_ALIAS[raw], raw
	end
	if raw:sub(1, 7) == "canary_" then
		return "canary_refused", raw
	end
	if raw:sub(1, 14) == "shared_ligand_" then
		return "shared_ligand", raw
	end
	if STAPLE_DECISION[raw] then
		return raw, nil
	end
	return "unmet", raw
end

-- Format OCSP staple decision into machine-readable log line with canonical field ordering.
-- Emits staple_decision=CODE as the primary machine-searchable field (runbook navigator).
-- Canonical field ordering prevents information leakage and improves auditability.
-- All logs use fixed ordering regardless of how many fields are present.
--
-- LOG FORMAT (canonical order):
--   staple_decision=CODE tag=TAG action=ACTION mode=MODE kind=KIND fp=FP \
--   detail=DETAIL alias=ALIAS refuse_cause=CAUSE der_sha256=SHA ... [EXTRA]
--
-- NORMALIZATION FLOW:
--   1. Input code → normalize_staple_decision → (decision, alias_detail)
--   2. decision = closed-vocabulary code (e.g. "shared_ligand", "certid_mismatch")
--   3. alias_detail = pre-alias raw if code was aliased (e.g. "ligand_missing" if collapsed from "shared_ligand_missing")
--   4. refuse_cause = alias_detail XOR raw (holds pre-alias detail for pin DROP/KEEP lookup)
--   5. Canonical order: tag, action, mode, kind, fp, detail, alias, refuse_cause, der_sha256, ... (no side-channels)
--
-- FIELD SEMANTICS:
--   - staple_decision: Primary machine code (runbook section); fixed vocabulary
--   - refuse_cause: Pre-alias raw detail (for pin DROP/KEEP policy lookup)
--   - detail: Full detail string (may be same as alias or raw refuse reason)
--   - alias: When normalization collapsed code (e.g., "canary_cert_changed" was aliased to "canary_refused")
--   - subsystem: Always stamped (HTTP or stream) so logs cannot look identical while diverging
--
-- INVARIANT: refuse_cause MUST hold the pre-alias raw for DROP/KEEP policy matching
--   Example: "shared_ligand_ligand_missing"
--   → decision="shared_ligand", refuse_cause="ligand_missing"
--   → pin.lua checks KEEP_ALLOW_ON_REFUSE["ligand_missing"] to decide CAS-delete
--
-- WHY CANONICAL ORDERING:
--   - Prevents side-channel leaks where field order reveals internal resolution hierarchy
--   - Ensures consistent parsing across logging aggregators
--   - Makes log scanning reliable (grep staple_decision= without parsing order)
--   - Audit trail: field order never changes, reducing parsing code surface
--
-- @param code: decision code to format (may be aliased like "canary_*" or "shared_ligand_*")
-- @param fields: optional table of additional fields {tag=X, action=Y, mode=Z, ...}
-- @return: formatted log line string, e.g. "staple_decision=ok tag=OCSP_STAPLED fp=abc... der_sha256=xyz..."
-- ============================================================================
-- FORMAT_STAPLE_DECISION(code, fields)
-- ============================================================================
-- PURPOSE:
--   Formats OCSP decision codes into machine-readable logs with canonical field ordering.
--   Primary machine-searchable field enables runbook navigation and forensics.
--
-- PARAMETERS:
--   code (string|nil): decision code (may be aliased like "canary_cert_changed")
--   fields (table|nil): additional fields {tag=X, action=Y, fp=Z, detail=W, ...}
--
-- RETURNS:
--   (string): formatted log line (e.g., "staple_decision=ok tag=... action=...")
--
-- SIDE EFFECTS:
--   - Calls: normalize_staple_decision() for code mapping
--   - Logs: none (returns string for caller to log)
--   - Performance: O(n) where n = number of fields
--
-- DESIGN NOTES:
--   - Canonical ordering: prevents information leakage and parsing ambiguity
--   - Subsystem always stamped: logs cannot diverge between HTTP and stream
--   - Refuse_cause preservation: holds pre-alias raw for policy lookup
--   - Field escaping: values quoted if containing spaces/special chars
--   - Runbook navigation: staple_decision= is primary grep target
--   - Audit trail: fixed ordering enables reliable log parsing
--
-- RELATED:
--   - normalize_staple_decision() — maps codes to closed vocabulary
--   - log() — caller logs the result
--   - STAPLE_DECISION table — closed-vocabulary codes
--
-- ============================================================================
local function format_staple_decision(code, fields)
	local raw = tostring(code or "unmet")
	local decision, alias_detail = normalize_staple_decision(code)
	local parts = { "staple_decision=" .. decision }
	local f = {}
	if type(fields) == "table" then
		for k, v in pairs(fields) do
			f[k] = v
		end
	end
	-- Always stamp subsystem so HTTP/stream logs cannot look identical while diverging.
	if (f.subsystem == nil or f.subsystem == "") and ngx.config and ngx.config.subsystem then
		f.subsystem = ngx.config.subsystem
	end
	-- Forensic invariant: refuse_cause= holds the pre-alias raw whenever we collapsed
	-- a code (ligand_* → shared_ligand, canary_* → canary_refused, …). Pin DROP/KEEP
	-- must key that raw — never staple_decision= alone. If the caller already set
	-- refuse_cause, keep it; otherwise use alias_detail or the raw closed code.
	if f.refuse_cause == nil or f.refuse_cause == "" then
		if alias_detail then
			f.refuse_cause = alias_detail
		elseif
			decision ~= "ok"
			and decision ~= "ok_partial"
			and decision ~= "stapling_off"
			and decision ~= "skip_slot"
		then
			f.refuse_cause = raw
		end
	end
	if alias_detail then
		if f.detail == nil or f.detail == "" then
			f.detail = alias_detail
		elseif tostring(f.detail) ~= alias_detail then
			-- Caller preseeded detail= with a different string — do not hide the alias
			-- raw (already in refuse_cause=); also surface it as alias=.
			f.alias = alias_detail
		end
	end
	-- Canonical field ordering: fixed sequence for consistent log parsing.
	-- Prevents side-channel leaks where field order reveals internal resolution hierarchy.
	local order = {
		"tag",
		"action",
		"mode",
		"kind",
		"fp",
		"detail",
		"alias",
		"refuse_cause",
		"der_sha256",
		"epoch",
		"worker",
		"server_name",
		"subsystem",
		"multi_entries",
		"stapled_entries",
		"null_slots",
	}
	local seen = { staple_decision = true }
	for _, key in ipairs(order) do
		local val = f[key]
		if val ~= nil and val ~= "" then
			parts[#parts + 1] = key .. "=" .. tostring(val)
			seen[key] = true
		end
	end
	-- Append any dynamic fields not in canonical order (rare; audit these).
	for key, val in pairs(f) do
		if not seen[key] and val ~= nil and val ~= "" then
			parts[#parts + 1] = key .. "=" .. tostring(val)
		end
	end
	return table.concat(parts, " ")
end

-- Single source of truth for closed staple_decision=CODE log lines (HTTP + stream).
function _M.format_staple_decision(code, fields)
	return format_staple_decision(code, fields)
end

-- Convert a Must-Staple miss into abort (normal) or soft continue (fuse).
-- Always logs staple_decision=CODE (runbook) with tag=OCSP_MUST_STAPLE_REFUSE
-- and refuse_cause= raw detail (pre-alias) so pin/bus forensics survive collapse.
-- Skips a second ERR when set_certs_from_pem already logged action=continue_install
-- for this handshake (ngx.ctx.bw_ocsp_soft_fuse_logged) — one intentional fuse, one line.
--
-- Return contract (callers MUST branch on the second value, not bare falsiness):
--   soft continue → false, nil, "continue"
--   abort         → false, "must_staple", "abort"
-- Stream ssl_certificate already checks soft_reason == "must_staple".
-- ============================================================================
-- SOFTEN_MUST_STAPLE(mode, ok, reason, detail)
-- ============================================================================
-- PURPOSE:
--   Converts Must-Staple refusal to soft continue or abort based on mode.
--   Implements soft-fuse policy: normal=abort, staple_only/open=continue.
--
-- PARAMETERS:
--   mode (string): soft-fuse mode ("normal", "staple_only", "open")
--   ok (boolean): original success flag (passed through if reason != "must_staple")
--   reason (string|nil): refusal reason (check if "must_staple")
--   detail (string|nil): refusal detail for logging (pre-alias)
--
-- RETURNS:
--   (bool, string|nil, string): (ok_flag, soft_reason, action)
--     - ok_flag: false for "must_staple" (never staple)
--     - soft_reason: nil (continue), "must_staple" (abort)
--     - action: "continue" (soft), "abort" (hard), or passthrough
--
-- SIDE EFFECTS:
--   - Calls: log() for staple_decision logging
--   - Reads: ngx.ctx.bw_ocsp_soft_fuse_logged (dedup log)
--   - Logs: ERR with staple_decision when must_staple missed
--   - Performance: ~0.5-2ms (logging only on must_staple refusal)
--
-- DESIGN NOTES:
--   - Soft-fuse modes: normal=fail-closed, staple_only/open=fail-soft
--   - Logging: staple_decision=must_staple with refuse_cause preserved
--   - Dedup guard: skips log if set_certs_from_pem already logged
--   - Return contract: callers must check soft_reason, not bare false
--   - Handshake safety: refuses to staple (ok=false always)
--   - Stream aware: ssl_certificate checks soft_reason == "must_staple"
--
-- RELATED:
--   - format_staple_decision() — formats log lines
--   - ocsp_staple_mode() — reads mode setting
--   - _M.soften_must_staple() — public export
--
-- ============================================================================
local function soften_must_staple(mode, ok, reason, detail)
	if reason ~= "must_staple" then
		return ok, reason
	end
	local action = "abort"
	if mode == "staple_only" or mode == "open" then
		action = "continue"
	end
	local raw_cause = tostring(detail or "unmet")
	local already = ngx.ctx and ngx.ctx.bw_ocsp_soft_fuse_logged
	if not already then
		log(
			ngx.ERR,
			format_staple_decision(raw_cause, {
				tag = "OCSP_MUST_STAPLE_REFUSE",
				action = action,
				mode = mode or "normal",
				refuse_cause = raw_cause,
			})
		)
	end
	if action == "continue" then
		return false, nil, "continue"
	end
	return false, "must_staple", "abort"
end

-- Exported so stream ssl_certificate await_sni can apply the same fuse as staple().
function _M.staple_mode(internalstore, server_name)
	return ocsp_staple_mode(internalstore, server_name)
end

-- Exported for the HTTP stapling-off fast path (one parser for SSL_USE_OCSP_STAPLING).
function _M.stapling_enabled(internalstore, server_name)
	return stapling_enabled(internalstore, server_name)
end

function _M.soften_must_staple(mode, ok, reason, detail)
	return soften_must_staple(mode, ok, reason, detail)
end

-- Optional stapling skipped (no Must-Staple). Distinct from Must-Staple refuse.
-- ============================================================================
-- LOG_STAPLING_OFF(reason)
-- ============================================================================
-- PURPOSE:
--   Logs when optional OCSP stapling is skipped (SSL_USE_OCSP_STAPLING=no).
--   Distinct from Must-Staple refusal; no enforcement when feature disabled.
--
-- PARAMETERS:
--   reason (string|nil): skip reason (default: "ssl_use_ocsp_stapling_no")
--
-- RETURNS:
--   (nil): side effects only
--
-- SIDE EFFECTS:
--   - Calls: log(), format_staple_decision()
--   - Logs: DEBUG level staple_decision=stapling_off
--   - Performance: O(n) logging only (no I/O)
--
-- DESIGN NOTES:
--   - Level DEBUG: normal expected behavior (not an error)
--   - Decision code: "stapling_off" (runbook section)
--   - Tag: "OCSP_STAPLING_OFF" for aggregation
--   - Reason: pre-alias detail for troubleshooting
--   - Distinct: not Must-Staple (no enforcement when disabled)
--
-- RELATED:
--   - stapling_enabled() — checks if feature enabled
--   - format_staple_decision() — formats log line
--
-- ============================================================================
local function log_stapling_off(reason)
	log(
		ngx.DEBUG,
		format_staple_decision("stapling_off", {
			tag = "OCSP_STAPLING_OFF",
			detail = tostring(reason or "ssl_use_ocsp_stapling_no"),
		})
	)
end

-- Validate that a string is a 64-character lowercase hex string (SHA256 digest).
-- OCSP cache directories are named by SPKI fingerprints in this format.
-- This check is security-critical: prevents path traversal via malformed fps.
--
-- @param fp: candidate fingerprint string
-- @return: true if fp is a valid 64-char hex string (a, b, c, d, e, f, 0-9), false otherwise
-- @note: Allows A-F (uppercase); callers normalize to lowercase for disk paths
--
-- Performance: O(1) validation (string ops only, no I/O)
-- Security: Rejects any input that could escape the sharded directory tree
-- ============================================================================
-- IS_FP64(fp)
-- ============================================================================
-- PURPOSE:
--   Validates fingerprint format: exactly 64 lowercase hex characters.
--   Used as security gatekeeper for path construction (prevents traversal).
--
-- PARAMETERS:
--   fp (any): potential fingerprint (checked for type, length, format)
--
-- RETURNS:
--   (true): exactly 64 hex chars (case-insensitive match)
--   (false): invalid type, length, or non-hex content
--
-- SIDE EFFECTS:
--   - Logs: none
--   - Performance: O(1) type/length/regex check
--
-- DESIGN NOTES:
--   - Gatekeeper: early rejection prevents path traversal attacks
--   - Format strict: 64 hex chars only (no flexibility)
--   - Case-insensitive: match accepts both cases
--   - Used throughout: all path construction functions check this first
--
-- RELATED:
--   - fingerprint_shard() — uses is_fp64 for validation
--   - ocsp_path() — guards path construction
--
-- ============================================================================
local function is_fp64(fp)
	return type(fp) == "string" and #fp == 64 and fp:match("^%x+$") ~= nil
end

-- Convert binary bytes to lowercase hex string (e.g., SHA256 digest output).
-- Used to format digest outputs from lua-resty-openssl for cache keys and logging.
--
-- @param bin: binary string (raw bytes from OpenSSL digest)
-- @return: lowercase hex string (double length of input, e.g., 32 bytes → 64 hex chars)
--
-- Performance: O(n) where n = input length (one format call per byte)
-- Example: to_hex("\x00\xff") → "00ff"
-- ============================================================================
-- TO_HEX(bin)
-- ============================================================================
-- PURPOSE:
--   Converts binary bytes to lowercase hex string (OpenSSL digest formatting).
--   Used for SHA256, SHA1, and other digest output formatting.
--
-- PARAMETERS:
--   bin (string): binary string (raw bytes, may contain nulls)
--
-- RETURNS:
--   (string): lowercase hex string (2 chars per input byte)
--
-- SIDE EFFECTS:
--   - Performance: O(n) where n = #bin
--
-- DESIGN NOTES:
--   - Lowercase: consistent with fingerprint normalization
--   - Byte-by-byte: uses string.format %02x for each byte
--   - Length: output = 2 * #input (e.g., 32 bytes → 64 hex chars)
--   - Used by: cache key generation, fingerprinting
--
-- RELATED:
--   - resp_binding() — hashes OCSP response to hex
--   - cache_key() — formats fingerprint hex
--
-- ============================================================================
local function to_hex(bin)
	local hex = {}
	for i = 1, #bin do
		hex[i] = string.format("%02x", string.byte(bin, i))
	end
	return table.concat(hex)
end

-- Read a file from disk, returning content and distinguish ENOENT vs empty file.
-- Two-value return allows callers to handle race conditions (truncation during write).
-- Used throughout OCSP to read metadata (ocsp.json), responses (ocsp.der), issuers.
--
-- @param path: file path string (empty or non-string → returns nil, "missing")
-- @return: file content (string) or nil (on error or empty)
-- @return: secondary status string: "missing" (ENOENT), "empty" (0-byte file), or nil (success + data)
--
-- DISTINGUISH CASES:
--   read_file(path) → data, nil              [file exists, has content]
--   read_file(path) → nil, "missing"         [ENOENT: file does not exist]
--   read_file(path) → nil, "empty"           [file exists but is zero-length]
--
-- Performance: O(n) disk I/O (reads entire file; use for small files only)
-- Security: path must be validated by caller (used for SPKI-sharded dirs only)
--
-- NOTE: Empty files are treated specially because truncation races during atomic
--       writes (via os.rename) can leave zero-byte files. Callers distinguish this
--       from missing files to decide whether to retry or fall back.
-- ============================================================================
-- READ_FILE(path)
-- ============================================================================
-- PURPOSE:
--   Reads file content from disk, distinguishing ENOENT from empty files.
--   Two-value return enables callers to handle atomic write races.
--
-- PARAMETERS:
--   path (string|nil): file path (empty or non-string → returns nil, "missing")
--
-- RETURNS:
--   (string, nil): (data, nil) if file exists and has content
--   (nil, "missing"): if ENOENT (file does not exist)
--   (nil, "empty"): if file exists but is zero-length
--
-- SIDE EFFECTS:
--   - Reads: entire file content from disk
--   - Performance: O(n) disk I/O where n = file size
--
-- DESIGN NOTES:
--   - Two-value return: distinguishes race conditions from missing files
--   - Empty files: treated specially (rename race safety)
--   - Small files only: reads entire content into memory
--   - Best-effort: no error logging (callers decide)
--   - Used for: ocsp.json, ocsp.der, issuer.pem reading
--
-- RELATED:
--   - path_exists() — lightweight existence check
--   - ocsp_path(), issuer_path() — file path construction
--
-- ============================================================================
local function read_file(path)
	if type(path) ~= "string" or path == "" then
		return nil, "missing"
	end
	local f = io.open(path, "rb")
	if not f then
		return nil, "missing"
	end
	local data = f:read("*a")
	f:close()
	if data and #data > 0 then
		return data
	end
	-- Empty file ≠ ENOENT: callers that only use the first return still see nil,
	-- but second return lets refuse paths distinguish truncate races from absence.
	return nil, "empty"
end

-- Extract first two hex chars (high and low nybbles) for sharded directory layout.
-- OCSP cache uses 16×16 = 256 subdirectories to distribute files evenly and avoid
-- inode exhaustion in any single directory (common with 10k+ certificates).
-- Never invents a shared 0/0 sink for invalid fingerprints.
--
-- @param fingerprint: SHA256 hex string (64 chars, validated by is_fp64)
-- @return: h (first hex char, "0"-"f"), l (second hex char, "0"-"f")
--          or nil, nil if fingerprint is not a valid fp64
--
-- DIRECTORY STRUCTURE:
--   /var/cache/bunkerweb/ssl/{h}/{l}/{fingerprint}/ocsp.der
--                                      ↑ full 64-char fingerprint
--                              ↑ second hex digit (0-f)
--                      ↑ first hex digit (0-f)
--
-- Performance: O(1) string operations
-- Example: fingerprint_shard("abc123...") → "a", "b"
--
-- Security: Non-fp64 inputs rejected early; prevents path traversal via "../"
-- ============================================================================
-- FINGERPRINT_SHARD(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Extracts shard indices (first 2 hex chars) for 256-way directory sharding.
--   Distributes OCSP cache evenly across fs to prevent inode exhaustion.
--
-- PARAMETERS:
--   fingerprint (string): 64-char hex SPKI fingerprint (validated by is_fp64)
--
-- RETURNS:
--   (string, string): (h, l) = first two hex digits (e.g., "a", "b")
--   (nil, nil): if fingerprint not valid fp64 (rejected early)
--
-- SIDE EFFECTS:
--   - Calls: is_fp64() for validation
--   - Performance: O(1) string ops
--
-- DESIGN NOTES:
--   - Sharding: 16×16 = 256 directories (/var/cache/bunkerweb/ssl/h/l/...)
--   - Distribution: prevents single-directory inode exhaustion
--   - Security: rejects non-fp64 inputs early (path traversal guard)
--   - Used by: ocsp_path(), issuer_path(), cache_key() for path construction
--
-- RELATED:
--   - is_fp64() — validates fingerprint format first
--   - ocsp_path() — uses shards for cache path
--
-- ============================================================================
local function fingerprint_shard(fingerprint)
	if type(fingerprint) ~= "string" or not is_fp64(fingerprint) then
		return nil, nil
	end
	local fp = fingerprint:lower()
	return fp:sub(1, 1), fp:sub(2, 2)
end

-- Build filesystem path to OCSP response DER file from SPKI fingerprint.
-- Uses sharded directory structure: /var/cache/bunkerweb/ssl/{h}/{l}/{fp}/ocsp.der
--
-- @param fingerprint: SHA256 hex string (64 chars, validated by is_fp64)
-- @param collision_index: optional numeric suffix for rare SPKI directory collisions
-- @return: full filesystem path string, or nil if fingerprint is not valid fp64
--
-- SHARDING RATIONALE:
--   16×16 (256) subdirectories distribute files evenly, preventing inode exhaustion
--   in a single directory. First 2 hex chars determine {h}/{l} shard location.
--   Each SPKI gets a directory: /var/cache/bunkerweb/ssl/a/b/abcdef1234.../
--   Inside: ocsp.der (response), issuer.pem (issuer cert), ocsp.json (metadata)
--
-- COLLISION_INDEX (rare):
--   If two different certificates somehow have the same SPKI (should never happen),
--   append .N to distinguish them: ocsp.der vs ocsp.der.1 vs ocsp.der.2
--   Practically: collision_index is always 0 or nil (single response per SPKI)
--
-- EXAMPLES:
--   ocsp_path("abc123def456...") → "/var/cache/bunkerweb/ssl/a/b/abc123def456.../ocsp.der"
--   ocsp_path("abc123def456...", 1) → "/var/cache/bunkerweb/ssl/a/b/abc123def456.../ocsp.der.1"
--   ocsp_path("invalid") → nil
--
-- Performance: O(1) string operations (no I/O)
-- Security: Non-fp64 rejected early; prevents path traversal via "../"
-- Called by: warm_cache, attach operations, response reading
-- ============================================================================
-- OCSP_PATH(fingerprint, collision_index)
-- ============================================================================
-- PURPOSE:
--   Builds canonical OCSP DER response file path from SPKI fingerprint.
--   Uses 256-way sharded directory structure for filesystem scalability.
--
-- PARAMETERS:
--   fingerprint (string): 64-char hex SPKI fingerprint (validated by is_fp64)
--   collision_index (number|nil): optional numeric suffix (rarely used, default 0)
--
-- RETURNS:
--   (string): full path /var/cache/bunkerweb/ssl/{h}/{l}/{fp}/ocsp.der[.N]
--   (nil): if fingerprint not valid fp64
--
-- SIDE EFFECTS:
--   - Calls: fingerprint_shard() for h/l extraction
--   - Performance: O(1) string concatenation
--
-- DESIGN NOTES:
--   - Sharding: 256 subdirs prevent single-directory inode exhaustion
--   - Collision handling: .N suffix for rare SPKI collisions (should never occur)
--   - Deterministic: same fingerprint always yields same path
--   - Security: rejects non-fp64 early (prevents path traversal)
--   - Used by: response reading, warming, cache operations
--
-- RELATED:
--   - fingerprint_shard() — extracts h/l shards
--   - issuer_path() — similar for issuer certificate
--   - cache_key() — Lua table key generation
--
-- ============================================================================
local function ocsp_path(fingerprint, collision_index)
	local h, l = fingerprint_shard(fingerprint)
	if not h then
		return nil
	end
	local fp = fingerprint:lower()
	local base = "/var/cache/bunkerweb/ssl/" .. h .. "/" .. l .. "/" .. fp .. "/ocsp.der"
	if collision_index and collision_index > 0 then
		return base .. "." .. tostring(collision_index)
	end
	return base
end

-- Build filesystem path to issuer certificate PEM file from leaf SPKI fingerprint.
-- Parallel structure to ocsp_path but stores issuer chain instead of OCSP response.
--
-- @param fingerprint: SHA256 hex string (64 chars, validated by is_fp64)
-- @return: full filesystem path string, or nil if fingerprint is not valid fp64
--
-- PATH STRUCTURE:
--   /var/cache/bunkerweb/ssl/{h}/{l}/{fp}/issuer.pem
--   Same sharding as ocsp_path (first 2 hex chars determine {h}/{l})
--   Stores PEM-encoded issuer certificate(s) for validating this leaf
--
-- WHY SEPARATE FROM LEAF:
--   Leaf certificate is passed in TLS handshake; OCSP response comes from network.
--   Issuer is stored separately because: same issuer may sign multiple leaves,
--   issuer updates independently (when CA rotates its key or cert chain changes).
--   By fingerprinting the LEAF, we know which issuer to load for that specific cert.
--
-- EXAMPLES:
--   issuer_path("abc123def456...") → "/var/cache/bunkerweb/ssl/a/b/abc123def456.../issuer.pem"
--   issuer_path("invalid") → nil
--
-- Performance: O(1) string operations (no I/O)
-- Called by: FFI validation (get issuer PEM for ngx.ocsp.validate_ocsp_response)
-- Paired with: ocsp_path (same fingerprint → both DER and PEM locations)
-- ============================================================================
-- ISSUER_PATH(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Builds canonical issuer certificate PEM file path from leaf SPKI fingerprint.
--   Uses same sharding as ocsp_path for filesystem organization.
--
-- PARAMETERS:
--   fingerprint (string): 64-char hex SPKI fingerprint (leaf cert)
--
-- RETURNS:
--   (string): full path /var/cache/bunkerweb/ssl/{h}/{l}/{fp}/issuer.pem
--   (nil): if fingerprint not valid fp64
--
-- SIDE EFFECTS:
--   - Calls: fingerprint_shard() for h/l extraction
--   - Performance: O(1) string concatenation
--
-- DESIGN NOTES:
--   - Parallel structure: same {h}/{l}/{fp} shard as ocsp_path
--   - Keyed by leaf: fingerprints leaf cert to find its issuer
--   - Separate from leaf: issuer updates independently
--   - PEM format: stores issuer certificate chain for FFI validation
--   - Used by: ngx.ocsp.validate_ocsp_response (needs issuer for sig verification)
--
-- RELATED:
--   - ocsp_path() — OCSP response path (same fingerprint)
--   - cache_key() — L1 cache key generation
--
-- ============================================================================
local function issuer_path(fingerprint)
	local h, l = fingerprint_shard(fingerprint)
	if not h then
		return nil
	end
	local fp = fingerprint:lower()
	return "/var/cache/bunkerweb/ssl/" .. h .. "/" .. l .. "/" .. fp .. "/issuer.pem"
end

-- Generate L1 shared-dict cache key for OCSP response storage.
-- Keys must be deterministic: same fingerprint → same key for cache coherence.
-- Keys must be unique: different certs (different fingerprints) get different keys.
--
-- CACHE KEY FORMAT:
--   "TLS:SSL:ocsp:{fingerprint_lowercase}"
--   Prefix "TLS:SSL:" namespaces OCSP keys in shared dict (avoid collisions with other systems)
--   fingerprint: lowercase 64-char hex (normalized by cache operations)
--
-- AUTO-INVALIDATION ON CERT ROTATION:
--   When certificate rotates (same key, different serial/issuer):
--   - Old cert has fingerprint A → cache key "TLS:SSL:ocsp:aaa..."
--   - New cert has fingerprint B → cache key "TLS:SSL:ocsp:bbb..."
--   - Keys differ → old L1 entry NOT reused for new cert
--   - "Verified" flag from old cert does NOT apply to new cert (critical safety)
--
-- @param fingerprint: SHA256 hex string (64 chars)
-- @return: cache key string "TLS:SSL:ocsp:...", or nil if fingerprint is not valid fp64
--
-- Performance: O(1) string concatenation
-- Security: Non-fp64 rejected; prevents cache key injection via arbitrary strings
-- Lifetime: Key persists for duration of cert deployment (until rotation)
-- Called by: L1 cache operations (get_l1, warm_cache, drop_cache)
-- ============================================================================
-- CACHE_KEY(fingerprint)
-- ============================================================================
-- PURPOSE:
--   Generates L1 shared-dict cache key for OCSP response storage.
--   Deterministic and unique; auto-invalidates on cert rotation.
--
-- PARAMETERS:
--   fingerprint (string): 64-char hex SPKI fingerprint
--
-- RETURNS:
--   (string): cache key "TLS:SSL:ocsp:{fingerprint_lower}"
--   (nil): if fingerprint not valid fp64
--
-- SIDE EFFECTS:
--   - Calls: is_fp64() for validation
--   - Performance: O(1) string concatenation
--
-- DESIGN NOTES:
--   - Prefix "TLS:SSL:": namespaces OCSP in shared dict
--   - Deterministic: same fp → same key (cache coherence)
--   - Unique: different fps → different keys (no collisions)
--   - Auto-invalidate: cert rotation (same key, diff serial) → new key
--   - Safety: old L1 verdict cannot leak to new cert
--   - Security: rejects non-fp64 (prevents key injection)
--
-- RELATED:
--   - ocsp_path(), issuer_path() — filesystem paths (same fingerprint)
--   - L1 cache operations — stores OCSP responses under this key
--
-- ============================================================================
local function cache_key(fingerprint)
	if type(fingerprint) ~= "string" or not is_fp64(fingerprint) then
		return nil
	end
	return "TLS:SSL:ocsp:" .. fingerprint:lower()
end

-- Bind verified flag to OCSP DER bytes (not SPKI alone). Same-key renewals keep the fingerprint.
-- Compute SHA256 digest of OCSP response DER bytes for binding verification.
-- Binds "response is valid" verdict to the exact DER bytes, not just the SPKI.
-- Essential for Same-Key Renewals: after cert rotation with same key, old DER
-- cannot falsely inherit the "verified" mark from a newer DER for the new cert.
--
-- @param resp: OCSP response DER bytes (binary string, may contain null bytes)
-- @return: lowercase hex SHA256 digest (64 chars) or nil if resp is empty/invalid
--
-- WHY THIS MATTERS:
--   Certificate rotation scenario:
--   1. old_cert issued under issuer X with serial 100 → old_resp = SHA256("...1000 bytes...")
--   2. new_cert issued under issuer X with serial 200 (same key) → new_resp = SHA256("...1000 bytes different...")
--   3. SHA256 hashes differ → verified cache entry for old_resp NOT applied to new_resp
--   4. Prevents serving stale "verified" flag after certificate renewal
--
-- Performance: ~1ms for typical ~200-byte OCSP response (OpenSSL SHA256 + to_hex)
-- Error handling: Fails closed (returns nil) on FFI exceptions or invalid digest length
-- ============================================================================
-- RESP_BINDING(resp)
-- ============================================================================
-- PURPOSE:
--   Computes SHA256 digest of OCSP response DER for binding verified verdict to bytes.
--   Prevents stale "verified" flags from leaking to different OCSP responses.
--
-- PARAMETERS:
--   resp (string|nil): OCSP response DER bytes (binary, may contain nulls)
--
-- RETURNS:
--   (string): 64-char lowercase hex SHA256 (der binding)
--   (nil): if resp empty/invalid or digest error
--
-- SIDE EFFECTS:
--   - Calls: require("resty.openssl.digest") for SHA256
--   - Calls: to_hex() for hex formatting
--   - Performance: ~1ms (OpenSSL SHA256 + hex conversion)
--
-- DESIGN NOTES:
--   - Binding: ties "verified" verdict to exact DER bytes (not SPKI)
--   - Same-key renewal: old DER hash ≠ new DER hash → no stale cache
--   - Fail-closed: returns nil on digest error (conservative)
--   - FFI safe: wraps OpenSSL call in pcall()
--   - Used by: cache binding, L1 verification gates
--
-- RELATED:
--   - cache_key() — fingerprint-based key (separate from DER binding)
--   - ms_cache_key() (ocsp_must_staple) — binds Must-Staple to DER too
--
-- ============================================================================
local function resp_binding(resp)
	if type(resp) ~= "string" or #resp == 0 then
		return nil
	end
	local ok, digest = pcall(function()
		local digest_lib = require("resty.openssl.digest")
		local ctx = digest_lib.new("sha256")
		ctx:update(resp)
		return to_hex(ctx:final())
	end)
	if ok and type(digest) == "string" and #digest == 64 then
		return digest
	end
	return nil
end

-- Declared clock-skew budget. Must match ocsp-refresh.py OCSP_CLOCK_SKEW_SECONDS.
-- Death time = expires_unix/max_age minus skew: stop stapling before the CA's
-- advertised nextUpdate so a lagging worker clock cannot serve a dead response.
local OCSP_CLOCK_SKEW_SECONDS = 300
-- Soft ngx.ocsp.validate budget on the TLS path (match HTTP ssl-certificate-by-lua).
local OCSP_VALIDATE_BUDGET_NS = 700000000 -- 700ms when ngx.hrtime is available
local OCSP_VALIDATE_BUDGET_S = 0.7
local OCSP_VALIDATE_MAX_ISSUERS = 4
-- Signed-window policy; must match ocsp-refresh.py.
local OCSP_MAX_INTRINSIC_LIFETIME_SECONDS = 7 * 24 * 3600
local OCSP_MAX_THIS_UPDATE_AGE_SECONDS = 7 * 24 * 3600

-- Shared with the HTTP ssl_certificate path: job bumps this file so both
-- internalstore and internalstore_stream drop stale L1 without cross-dict APIs.
-- Always re-read: a mid-handshake bump must not be masked by an ngx.ctx pin.
local OCSP_EPOCH_PATH = "/var/cache/bunkerweb/ssl/.ocsp_epoch"

-- Read .ocsp_epoch (job coherence bus). HTTP and stream L1 must match this string.
-- First non-space token on the first line (leading whitespace allowed) — never
-- require the whole file to be a single token (extra lines / comments must not
-- desync HTTP vs stream readers).
--
-- Why one parser: a prior HTTP-only reader used ^%s*(%S+)%s*$ over the whole file
-- and rejected multi-line epochs that stream accepted → HTTP L1 miss / stream hit
-- on the same body. Both call sites must use this function (or the export below).
-- ============================================================================
-- CURRENT_OCSP_EPOCH()
-- ============================================================================
-- PURPOSE:
--   Reads job coherence epoch from /var/cache/bunkerweb/ssl/.ocsp_epoch.
--   HTTP and stream L1 caches must match this string for cache coherence.
--
-- PARAMETERS:
--   (none)
--
-- RETURNS:
--   (string): first non-space token from epoch file, or "0" if missing/unreadable
--
-- SIDE EFFECTS:
--   - Reads: /var/cache/bunkerweb/ssl/.ocsp_epoch
--   - Performance: ~1-5ms (file I/O, best-effort)
--
-- DESIGN NOTES:
--   - Job coordination: job bumps this file to invalidate stale L1 caches
--   - Unified parser: HTTP and stream use this to prevent L1 desync
--   - Robust format: allows leading whitespace, multi-line (ignores extras)
--   - Safe default: "0" if file missing or unreadable (conservative)
--   - First-token only: skips lines after first (comments OK)
--   - No cross-dict: both subsystems re-read this file always
--
-- RELATED:
--   - ocsp-refresh.py — job bumps this file
--   - L1 cache invalidation — keyed by epoch value
--   - _M.current_ocsp_epoch() — public export
--
-- ============================================================================
local function current_ocsp_epoch()
	local epoch = "0"
	pcall(function()
		local f = io.open(OCSP_EPOCH_PATH, "r")
		if not f then
			return
		end
		local raw = f:read("*l")
		f:close()
		if type(raw) == "string" and #raw > 0 then
			-- Allow leading whitespace on the first line (same as prior HTTP reader).
			epoch = raw:match("^%s*(%S+)") or "0"
		end
	end)
	return epoch
end

-- Public: HTTP ssl-certificate-by-lua.conf delegates here so the handshake never
-- reimplements epoch tokenization. Returns "0" when the file is missing/unreadable.
function _M.current_ocsp_epoch()
	return current_ocsp_epoch()
end

-- Test if a file exists on disk without reading content.
-- Used for lightweight checks (e.g., "is issuer.pem present?") without full I/O.
--
-- @param path: file path string
-- @return: true if file exists and can be opened for reading, false otherwise
--
-- NOTE: Does NOT distinguish ENOENT from permission errors (both return false).
--       "File does not exist" and "permission denied" are both treated as "not present".
--       Callers that need to differentiate should use read_file() instead.
--
-- Performance: O(1) filesystem stat (very fast, <1ms even over NFS)
-- Used by: restore_claimed_pin, revoke_allow_pin (cache coherence checks)
-- ============================================================================
-- PATH_EXISTS(path)
-- ============================================================================
-- PURPOSE:
--   Lightweight file existence check without reading content.
--   Returns true if file can be opened for reading.
--
-- PARAMETERS:
--   path (string|nil): file path to check
--
-- RETURNS:
--   (true): file exists and is readable
--   (false): file missing, unreadable, or path invalid
--
-- SIDE EFFECTS:
--   - Performs: file open attempt (lightweight O(1) check)
--   - Performance: <1ms even over NFS
--
-- DESIGN NOTES:
--   - No distinction: ENOENT and EACCES both return false (conservative)
--   - No content read: only checks readability (fast)
--   - Best-effort: fails closed on any error
--   - Used by: cache coherence checks (claim existence)
--
-- RELATED:
--   - read_file() — reads content (distinguishes ENOENT vs empty)
--
-- ============================================================================
local function path_exists(path)
	local f = io.open(path, "rb")
	if f then
		f:close()
		return true
	end
	return false
end

-- Normalize and validate a certificate fingerprint hint from user input.
-- Converts to lowercase and validates format (64-char hex).
-- Used in fingerprint-only paths where caller provides a SPKI hint instead of full cert.
--
-- @param cert_fp_hint: fingerprint string (may be nil, non-string, or non-hex)
-- @return: normalized lowercase fp64 string, or nil if invalid
--
-- NORMALIZATION:
--   1. Reject non-strings (numbers, tables, userdata, nil) → return nil
-- ============================================================================
-- NORMALIZE_FP_HINT(cert_fp_hint)
-- ============================================================================
-- PURPOSE:
--   Normalizes and validates fingerprint from user input (lowercase + format check).
--   Used when caller provides SPKI hint instead of full certificate.
--
-- PARAMETERS:
--   cert_fp_hint (any): fingerprint candidate (string, nil, or invalid type)
--
-- RETURNS:
--   (string): normalized lowercase fp64 (64-char hex) if valid
--   (nil): if non-string, wrong length, or non-hex content
--
-- SIDE EFFECTS:
--   - Performance: O(n) where n = string length
--
-- DESIGN NOTES:
--   - Type check: rejects non-strings (fails closed)
--   - Normalization: converts to lowercase for consistency
--   - Validation: checks 64-char hex format (is_fp64)
--   - Idempotent: normalizing already-lowercase fp is safe
--   - Used by: fingerprint hint validation paths
--
-- RELATED:
--   - is_fp64() — format validation
--   - cache_key(), ocsp_path() — use normalized fingerprints
--
-- ============================================================================
--   2. Convert to lowercase (is_fp64 allows A-F; we normalize to a-f)
--   3. Validate with is_fp64() (must be exactly 64 hex chars)
--   4. Return lowercase fp, or nil if validation failed
--
-- Performance: O(1) type check + lowercase conversion + validation
-- Called by: fingerprint-hint paths (probe health, cert ranking)
local function normalize_fp_hint(cert_fp_hint)
	if type(cert_fp_hint) ~= "string" then
		return nil
	end
	local fp = cert_fp_hint:lower()
	if is_fp64(fp) then
		return fp
	end
	return nil
end

_M.internal = {
	DROP_ALLOW_ON_REFUSE = DROP_ALLOW_ON_REFUSE,
	KEEP_ALLOW_ON_REFUSE = KEEP_ALLOW_ON_REFUSE,
	META_ONLY_DROP_ALLOW = META_ONLY_DROP_ALLOW,
	OCSP_CLOCK_SKEW_SECONDS = OCSP_CLOCK_SKEW_SECONDS,
	OCSP_MAX_INTRINSIC_LIFETIME_SECONDS = OCSP_MAX_INTRINSIC_LIFETIME_SECONDS,
	OCSP_MAX_THIS_UPDATE_AGE_SECONDS = OCSP_MAX_THIS_UPDATE_AGE_SECONDS,
	OCSP_VALIDATE_BUDGET_NS = OCSP_VALIDATE_BUDGET_NS,
	OCSP_VALIDATE_BUDGET_S = OCSP_VALIDATE_BUDGET_S,
	OCSP_VALIDATE_MAX_ISSUERS = OCSP_VALIDATE_MAX_ISSUERS,
	apply_site_override = apply_site_override,
	cache_key = cache_key,
	current_ocsp_epoch = current_ocsp_epoch,
	fingerprint_shard = fingerprint_shard,
	format_staple_decision = format_staple_decision,
	is_fp64 = is_fp64,
	issuer_path = issuer_path,
	log = log,
	log_stapling_off = log_stapling_off,
	normalize_fp_hint = normalize_fp_hint,
	ocsp_path = ocsp_path,
	ocsp_staple_mode = ocsp_staple_mode,
	path_exists = path_exists,
	read_file = read_file,
	resp_binding = resp_binding,
	sni_in_service_domains = sni_in_service_domains,
	soften_must_staple = soften_must_staple,
	stapling_enabled = stapling_enabled,
	to_hex = to_hex,
}

return _M
