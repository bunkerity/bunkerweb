# OCSP Stapling System: Complete Function Documentation

**Last Updated:** 2026-09-29  
**Total Lines of Code:** 17,426 Lua lines across 9 modules  
**Purpose:** Comprehensive reference for every function and logic block in BunkerWeb's OCSP stapling system

---

## Table of Contents

1. [ocsp_common.lua](#ocsp_common) - Shared configuration & utilities
2. [ocsp_cert.lua](#ocsp_cert) - Certificate parsing & fingerprinting
3. [ocsp_store.lua](#ocsp_store) - Metadata storage & cache management
4. [ocsp_chain.lua](#ocsp_chain) - Chain presentation & staple attachment
5. [ocsp_pin.lua](#ocsp_pin) - Cross-subsystem coordination
6. [ocsp_must_staple.lua](#ocsp_must_staple) - Must-Staple enforcement
7. [ocsp_warmer.lua](#ocsp_warmer) - Background cache warming
8. [ocsp.lua](#ocsp) - Central orchestrator
9. [ocsp_http.lua](#ocsp_http) - HTTP subsystem integration

---

# ocsp_common.lua {#ocsp_common}

**Responsibility:** Shared constants, settings access, SNI resolution, staple decision codes, and utilities used across all OCSP modules.

**Key Concepts:**
- Staple decision closed vocabulary (deterministic machine-readable codes)
- Weak-map SNI caching (auto-invalidates on config reload)
- Per-site settings override (multisite support)
- Unified logging & path definitions

## Functions

### `log(level, msg)`
**Type:** Logging utility  
**Parameters:**
- `level` (number): ngx log level (ngx.ERR, ngx.INFO, ngx.DEBUG, etc.)
- `msg` (string): message to log

**Returns:** nil  
**Purpose:** Centralized logging wrapper; all OCSP logs route through here for filtering/redirection.  
**Usage:** `log(ngx.INFO, "OCSP response valid for 60s")`

---

### `get_or_build_domain_table(site_vars)`
**Type:** SNI domain lookup cache builder  
**Parameters:**
- `site_vars` (table): service configuration object (vars[primary_service_id])

**Returns:** table: domain→true mappings for O(1) SNI membership testing  
**Key Design:**
- **Weak-map memoization:** keyed by site_vars table identity (not content)
- **Source validation:** stores SERVER_NAME string to detect in-place mutations
- **Case-insensitive:** both exact + lowercase entries for SNI matching
- **Auto-invalidation:** config reload → new vars table → old entry auto-dropped

**Logic Flow:**
1. Check weak map for existing entry
2. If found and SERVER_NAME unchanged, return cached domains
3. Else: parse SERVER_NAME tokens, build domain_table with exact + lowercase entries
4. Store {source, domains} in weak map
5. Return domain_table

**Performance:** O(n) build (n = SERVER_NAME tokens), O(1) lookups  
**Called by:** `sni_in_service_domains`, SNI resolution path  

---

### `sni_in_service_domains(site_vars, sni)`
**Type:** SNI validation gate  
**Parameters:**
- `site_vars` (table): service configuration
- `sni` (string): Server Name Indication from ClientHello

**Returns:** boolean  
**Purpose:** Security hardening: verify SNI is in service's declared domains.  
**Logic:**
1. Validate inputs (non-nil, proper types)
2. Get or build domain table for this site
3. Check SNI against both exact + lowercase entries
4. Return true if found, false otherwise

**Security Note:** Prevents SNI spoofing; certificate must match SNI to attach staple.

---

### `build_sni_index(vars)`
**Type:** SNI-to-service index builder  
**Parameters:**
- `vars` (table): configuration table {primary_service_id → site_vars, ...}

**Returns:** table with keys: primary_lower (lowercase index), domain_primaries (set), service_count  
**Purpose:** Pre-compute O(1) SNI → primary service ID resolution with three tiers:
1. **Tier 1:** primary service names (exact + lowercase for Tier 2)
2. **Tier 2:** case-insensitive fallback
3. **Tier 3:** domain search via site_vars.SERVER_NAME

**Cache Invalidation:** tracks service_count to detect in-place mutations (triggers rebuild)

---

### Staple Decision Codes

**Constant Values:** Closed vocabulary of OCSP staple outcomes (machine-readable for logs).

| Code | Meaning | Action |
|------|---------|--------|
| `ok` | Response valid, staple attached | Pass |
| `ok_partial` | Valid but missing chain cert | Pass (degrade) |
| `stapling_off` | OCSP stapling disabled | Skip |
| `peer_refuse` | Cluster peer refused | Skip (cluster consensus) |
| `tombstoned` | Certificate blacklisted | Refuse |
| `must_staple_refuse` | Must-Staple unprovable | Refuse (fail-closed) |
| `shared_ligand_poisoned` | Outside-ligand data stale | Retry FFI |
| `canary_paged_fail` | Ligand paging failed | Fallback |
| `issuer_unavailable` | Issuer not found | Skip (open) |
| `certid_mismatch` | OCSP response names wrong cert | Refuse |
| `response_expired` | nextUpdate passed | Refuse |
| `response_future` | thisUpdate not reached | Refuse |
| `response_too_old` | thisUpdate too old | Refuse |
| `response_not_found` | No OCSP response | Skip (open) |
| `validation_failed` | FFI validate failed | Refuse |
| `validation_timeout` | FFI took too long | Skip (budget) |
| `cluster_floor_fail` | Cluster consensus missing | Skip |
| `serial_blacklist` | Serial is revoked | Refuse |
| `validation_in_flight` | Async validation pending | Attach speculatively |

---

### Settings Access Functions

#### `ocsp_staple_mode(internalstore, server_name)`
**Returns:** string: "open" | "staple_only" | "normal"  
**Purpose:** Read per-site mode from ENV or database with override support.

#### `stapling_enabled(internalstore, server_name)`
**Returns:** boolean  
**Purpose:** Check if SSL_USE_OCSP_STAPLING is enabled for a site.

#### `soften_must_staple(internalstore, server_name)`
**Returns:** boolean  
**Purpose:** Check if Must-Staple enforcement can be softened (soft-fuse mode).

---

### Path & Constant Definitions

#### `ocsp_path()`
**Returns:** string: base OCSP cache directory (e.g., `/var/cache/bunkerweb/ssl`)

#### `issuer_path(fingerprint)`
**Returns:** string: path to issuer.pem for a certificate fingerprint

#### `read_file(path)`
**Returns:** string | nil: file contents or nil if not found/error

#### Constants

```lua
OCSP_CLOCK_SKEW_SECONDS = 300        -- Allow 5min clock drift
OCSP_VALIDATE_BUDGET_NS = 50_000_000  -- 50ms FFI time budget
OCSP_VALIDATE_BUDGET_S = 0.05        -- Same in seconds
OCSP_VALIDATE_MAX_ISSUERS = 10       -- Max issuer candidates to try
OCSP_MAX_INTRINSIC_LIFETIME_SECONDS = 432000  -- 5 days max response age
OCSP_MAX_THIS_UPDATE_AGE_SECONDS = 3600      -- thisUpdate must be recent
```

---

# ocsp_cert.lua {#ocsp_cert}

**Responsibility:** Pure certificate/OCSP DER parsing with per-worker memoization. No disk access, all FFI-based.

**Key Concepts:**
- Per-worker PEM memo (512 entries, LRU)
- Per-worker OCSP DER memo (256 entries)
- SPKI fingerprinting for shard directory names
- CertID matching (serial + issuer DN + SPKI)
- Must-Staple detection (TLS Feature extension)

## Memoization Architecture

### Per-Worker PEM Memo

**Structure:** `pem_memo{pem_bytes → {profile}}` + `pem_memo_touch{pem → gen}` + `pem_touch_gen` (counter)

**Capacity:** 512 entries max (O(1) hits, O(n) eviction when full)

**Profile Contents:**
```lua
{
  spki_fp = "sha256_hex",           -- SPKI fingerprint
  serial_hex = "hex_string",        -- Certificate serial
  serial_decimal = 123,             -- Serial as number
  issuer_dn = "C=US,O=CA",         -- Issuer distinguished name
  subject_dn = "CN=example.com",   -- Subject DN
  must_staple = true|false,        -- TLS Feature 5 present
  key_kind = "RSA"|"ECDSA"|"Ed25519", -- Public key type
  pubkey_bits = 2048,              -- Key size for RSA/ECDSA
  aia_uris = {"http://ocsp..."},  -- AIA Authority Info Access URLs
  is_self_signed = true|false,    -- Self-signed flag
}
```

### Functions in Memo Block

#### `touch_pem(pem)`
**Purpose:** Mark PEM as recently accessed for LRU ordering.  
**Side Effect:** Increments pem_touch_gen (per-worker counter)

#### `evict_lru()`
**Returns:** boolean: true if entry evicted, false if cache empty  
**Purpose:** Remove least-recently-used PEM when cache full.  
**Algorithm:** O(n) scan for minimum touch value, delete one victim

---

## Public Functions

### `pem_blocks(cert_pem)`
**Parameters:** cert_pem (string): PEM string (may contain multiple blocks)  
**Returns:** table of PEM block strings  
**Purpose:** Split multi-cert PEM bundles into individual certificates.

**Logic:**
1. Use gmatch to extract all "-----BEGIN CERTIFICATE-----...-----END CERTIFICATE-----" blocks
2. If no blocks found, return input as-is (handles malformed PEM)
3. Return array of blocks

**Performance:** O(n) regex scan, one pass

---

### `spki_fingerprint(cert_pem)`
**Parameters:** cert_pem (string): certificate PEM  
**Returns:** string: SHA256 hex fingerprint (64 chars) | nil if parse fails

**Purpose:** Extract SPKI (Subject Public Key Info) fingerprint for shard directory naming.

**Key Design:**
- Uses native lua-resty-openssl FFI (no shell spawning)
- Memoized per-worker (same PEM always gets same FP)
- Lowercase hex for consistency with disk paths

**Usage:** Shard path = `/var/cache/bunkerweb/ssl/{h}/{l}/{fp}/`

---

### `has_must_staple(cert_pem)`
**Returns:** boolean: true if TLS Feature 5 (OCSP Must-Staple) extension present

**Purpose:** Detect Must-Staple requirement at cert parse time (tri-state: true/false/unknown).

**TLS Feature Extension (OID 1.3.6.1.5.5.7.1.24):**
- Feature ID 5 = OCSP Must-Staple
- Presence = certificate requires OCSP staple to be valid
- Absence = Must-Staple not required

---

### `cert_spki_fingerprint(cert_pem)`
**Returns:** string: SPKI fingerprint | nil  
**Purpose:** Same as `spki_fingerprint` (alias for compatibility).

---

### `certid_matches_handshake_leaf(ocsp_der, leaf_pem, issuer_pem)`
**Parameters:**
- ocsp_der (string): OCSP response DER bytes
- leaf_pem (string): leaf certificate PEM
- issuer_pem (string): issuer certificate PEM

**Returns:** boolean  
**Purpose:** Verify OCSP response names this leaf (RFC 6960 CertID match).

**CertID Components (must all match):**
1. Serial number (from response → matches leaf)
2. Issuer DN hash (from response → matches issuer's subject)
3. Issuer key hash (optional; if present → matches issuer SPKI)

**Security:** Prevents OCSP response for Certificate A from attaching to Certificate B.

---

### `ocsp_resp_serial_hex(ocsp_der)`
**Returns:** string: serial number as hex | nil  
**Purpose:** Extract certificate serial from OCSP response DER.

**Algorithm:**
1. Parse DER OID structure (RFC 5280 serial location)
2. Extract raw bytes
3. Convert to hex string
4. Memoize per-worker (OCSP DER memo, 256 entries)

**Performance:** ~1-2ms (FFI + parsing, memoized)

---

### `key_spki_fingerprint(pubkey_pem)`
**Parameters:** pubkey_pem (string): public key or cert PEM  
**Returns:** string: SPKI fingerprint | nil

**Purpose:** Extract fingerprint from asymmetric key (not cert body).

---

### `aia_uri_pin_ok(cert_pem, uri_hint)`
**Parameters:**
- cert_pem (string): certificate to check
- uri_hint (string): expected OCSP responder URI

**Returns:** boolean  
**Purpose:** Verify OCSP responder URI is declared in cert AIA extension.

**Security Gate:** Prevents OCSP responses from unauthorized responders.

---

### `parse_pem_keys(pem_multi)`
**Parameters:** pem_multi (string): multi-block PEM (certs + keys)  
**Returns:** table: {key_pem, cert_pem_blocks...}

**Purpose:** Extract keys + certificates from mixed PEM bundles (used in multisite chains).

---

### `cert_pubkey_kind(cert_pem)`
**Returns:** string: "RSA" | "ECDSA" | "Ed25519" | "Ed448" | nil

**Purpose:** Determine certificate public key type (used for signature algorithm ranking).

---

### `cert_sig_profile(cert_pem)`
**Returns:** table: {scheme_oid, hash_alg, signature_alg} | nil

**Purpose:** Extract signature algorithm info from cert (used for TLS 1.3 ranking).

---

### `leaf_matches_scheme(cert_pem, sigalg_oid)`
**Returns:** boolean  
**Purpose:** Check if certificate's public key matches a TLS 1.3 signature algorithm OID.

---

### `batch_spki_fingerprints(cert_pems)`
**Parameters:** cert_pems (table): array of PEM strings  
**Returns:** table: {spki_fp...} (preserves nil for unparseable certs)

**Purpose:** Fingerprint multiple certs in batch (optimization #8).

---

# ocsp_store.lua {#ocsp_store}

**Responsibility:** Metadata storage (ocsp.json), outside-ligand bindings, L1 cache management, freshness gates.

**Key Concepts:**
- **Shard Metadata (ocsp.json):** job-published certificate facts
- **Outside Ligand:** canary-paged binding outside SPKI structure
- **L1 Cache (bw3 format):** shared-dict with epoch coherence bus
- **Freshness Gates:** validates OCSP response time bounds
- **Must-Staple Resolution:** tri-state (true/false/nil unknown)

## Cache Hierarchy

| Layer | Storage | TTL | Purpose |
|-------|---------|-----|---------|
| L1 | ngx.shared.internalstore (bw3) | 300s | TLS path optimization |
| L2 | /var/cache/.../ocsp.json | Job-maintained | Shard metadata |
| L3 | /var/cache/.../ocsp-ligand/{fp} | Job-maintained | Atomic paging |
| L4 | /var/cache/.../ocsp-floor/{fp} | Job-maintained | Cluster consensus |

## Constants & Structures

### L1 Cache Format (bw3)

```
"bw3\0" .. epoch .. "\0" .. binding .. "\0" .. gen .. "\0" .. expires .. "\0" .. der_bytes
```

**Fields:**
- `epoch` (string): `.ocsp_epoch` value (global coherence bus)
- `binding` (string): SHA256 of DER (verified_binding)
- `gen` (number): soft_recall_gen (prevents stale on re-page)
- `expires` (number): unix timestamp (TTL gate)
- `der_bytes` (string): actual OCSP response DER

### ocsp.json Structure

```json
{
  "spki_fp": "64-char-hex",
  "der_sha256": "64-char-hex",
  "soft_recall_gen": 1,
  "expires_unix": 1234567890,
  "must_staple": true,
  "serial_hex": "deadbeef"
}
```

---

## Functions

### `positive_unix(v)`
**Parameters:** v (number|string): value to parse  
**Returns:** positive integer unix timestamp | nil

**Purpose:** Secure timestamp parsing preventing coercion attacks.

**Validation Rules:**
- **Numbers:** Reject NaN, infinity, non-positive
- **Strings:** Reject unless all digits (no "1e2" notation)
- **Other types:** Return nil (fail-closed)

**Security:** Prevents "9e99" being parsed as valid TTL.

---

### `l1_ttl_from_expires(expires_unix)`
**Returns:** number: 0-300 (TTL in seconds for shared dict)

**Purpose:** Calculate residence time in L1 cache.

**Logic:**
1. Validate expires_unix (positive_unix)
2. Calculate remaining_time = expires_unix - now
3. Cap at L1_MAX_TTL (300s), floor at 0
4. Return result (never longer than OCSP lifetime)

---

### `resp_still_fresh(ocsp_der, meta, grace_seconds)`
**Parameters:**
- ocsp_der (string): OCSP response DER
- meta (table): ocsp.json metadata
- grace_seconds (number): additional tolerance (default 0)

**Returns:** boolean  
**Purpose:** Check if OCSP response has valid time bounds.

**Validation Gates:**
1. **thisUpdate check:** response_time ≥ thisUpdate - clock_skew (response ready)
2. **nextUpdate check:** now ≤ nextUpdate + grace_seconds (not expired)
3. **Intrinsic lifetime:** (nextUpdate - thisUpdate) ≤ MAX_LIFETIME
4. **Metadata consistency:** expires from meta if available

**Performance:** ~0.5-1ms (DER parse + timestamp checks)

---

### `meta_effective_expires_unix(meta, resp_der)`
**Returns:** number: unix timestamp when response expires | nil

**Purpose:** Determine effective expiry from ocsp.json or DER parsing.

**Logic:**
1. Try meta.expires_unix (job-computed)
2. Else: parse OCSP DER for nextUpdate
3. Return valid timestamp or nil (no expiry info)

---

### `entry_verified(entry)`
**Returns:** boolean: true if binding field present (L1 verified)

**Purpose:** Check if L1 cache entry has verified_binding (SHA256 match).

---

### `get_l1(internalstore, fingerprint)`
**Returns:** table: {epoch, binding, gen, expires, der} | nil

**Purpose:** Parse bw3 L1 cache entry for fingerprint.

**Logic:**
1. Read from internalstore:get(cache_key(fingerprint))
2. Parse magic + fields
3. Return structured entry or nil (not cached)

---

### `l1_matches_disk(entry, stored_sha, stored_gen)`
**Returns:** boolean  
**Purpose:** Verify L1 entry matches current disk state.

**Checks:**
- entry.binding == stored_sha (DER SHA256)
- entry.gen == stored_gen (soft-recall generation)

---

### `drop_cache(internalstore, fingerprint)`
**Returns:** nil  
**Purpose:** Evict L1 entry (called on poison or reject).

**Guard:** Checks ngx.ctx.bw_ocsp_skip_l1_drop (ranking phase).

---

### `warm_cache(internalstore, fingerprint, ocsp_der, meta)`
**Returns:** nil  
**Purpose:** Pre-load OCSP response into L1 shared dict.

**Logic:**
1. Parse DER + validate freshness
2. Calculate TTL (min of remaining lifetime, 300s)
3. Build bw3 entry with verified binding
4. Store in internalstore with TTL

---

### `read_ocsp_json(fingerprint)`
**Returns:** table: metadata object | nil

**Purpose:** Load shard ocsp.json metadata from disk.

**Path:** `/var/cache/bunkerweb/ssl/{h}/{l}/{fp}/ocsp.json`

---

### `ligand_or_meta(meta, fingerprint)`
**Returns:** table: outside-ligand data if paged, else meta

**Purpose:** Get current OCSP binding state (live > cached).

**Priority:**
1. Check outside-ligand (paged copy, most current)
2. Fallback to meta (shard metadata)
3. Return which was used for truthful generation tuples

---

### `soft_recall_gen_of(meta_or_ligand, fingerprint)`
**Returns:** number: soft_recall_gen | nil

**Purpose:** Extract generation field from metadata.

**Used for:** Soft-recall prevention (stale OCSP after cert rotation)

---

### `generation_tuple(meta, resp_der)`
**Returns:** tuple (sha, gen) | (nil, nil)

**Purpose:** Extract DER binding + generation for cross-handshake sharing.

**Returns:**
- sha: SHA256(DER) as hex string (64 chars)
- gen: soft_recall_gen number

---

### `meta_tombstoned(meta)`
**Returns:** boolean  
**Purpose:** Check if certificate is blacklisted (via ocsp.json flag).

---

### `serial_blacklist_blocks(meta, resp_der)`
**Returns:** table: array of serial blacklist block entries | nil

**Purpose:** Get serial revocation status for this response.

**Source:** ocsp-floor/serial-blacklist.json (cluster consensus)

---

### `cluster_floor_blocks(meta)`
**Returns:** table: array of cluster consensus entries | nil

**Purpose:** Get cluster-wide expiry consensus (prevents stale responses).

---

### `ocsp_json_authorizes_resp(meta, resp_der)`
**Returns:** boolean  
**Purpose:** Check if ocsp.json explicitly authorizes this response.

**Validation:**
- meta.der_sha256 == SHA256(resp_der)
- meta not tombstoned
- meta not expired

---

### `shard_not_paged(ligand_verdict)`
**Returns:** boolean  
**Purpose:** Check if shard is in clean (non-paged) state.

**Used for:** Prevent L1 poisoning from paged/stale data

---

### `must_staple_binds_shared_ligand(meta, resp_der)`
**Returns:** boolean  
**Purpose:** Check if Must-Staple is enforced + bound to shared ligand.

**Logic:** Must-Staple (true) + ligand_paged = strict enforcement

---

### `resolve_leaf_must_staple(cert_pem, meta)`
**Returns:** tri-state: true | false | nil (unknown)

**Purpose:** Determine if leaf has Must-Staple requirement.

**Sources (in order):**
1. TLS Feature extension (from cert_pem)
2. ocsp.json flag (from meta)
3. nil if neither set (unknown, treat as Must-Staple conservative)

---

# ocsp_chain.lua {#ocsp_chain}

**Responsibility:** Chain presentation + multi-staple attachment (TLS 1.3).

**Key Concepts:**
- **Issuer-Linked Chains:** filter cert bags keeping only verified path
- **Presentable Chains:** cache per-request to avoid redundant building
- **Multi-Staple:** attach leaf + intermediates (OpenSSL 3.6+)
- **Connection Staple Clearing:** prevent leaf A's staple landing on leaf B

## Functions

### `pem_blocks(cert_pem)` (re-exported from ocsp_cert)
Split multi-cert PEM into individual blocks.

---

### `issuer_linked_chain_blocks(leaf_pem, all_blocks, fingerprint, stored_issuer_pem)`
**Parameters:**
- leaf_pem (string): leaf certificate PEM
- all_blocks (table): cert bag (includes cross-signs, extras)
- fingerprint (string): leaf SPKI fingerprint
- stored_issuer_pem (string|false|nil): shard issuer.pem

**Returns:** table: ordered chain {leaf, intermediates...} (verified issuer path only)

**Purpose:** Build certificate chain by filtering cert bag; keep only verified issuer path.

**Algorithm:**
1. Verify leaf against issuer.pem (if shard has one)
2. Walk chain via DN matching: next cert's subject = prev cert's issuer
3. Stop at self-signed root or issuer mismatch
4. Drop off-path certs (cannot fail-close Must-Staple)
5. Return ordered list

**Security:** Prevents using unauthorized cross-signs.

---

### `presentable_chain_blocks(leaf_pem, all_pem, fingerprint, apply_soften)`
**Parameters:**
- leaf_pem (string): leaf certificate
- all_pem (string): multi-cert PEM bundle
- fingerprint (string): leaf SPKI fingerprint
- apply_soften (boolean): soften Must-Staple checks

**Returns:** table: {leaf, intermediates...}

**Caching:** Per-request (ngx.ctx.bw_ocsp_presentable_blocks_cache)

**Purpose:** Get issuer-linked chain with caching (optimization #3).

**Logic:**
1. Check ngx.ctx cache (per-request)
2. If miss: call issuer_linked_chain_blocks
3. Cache result, return

---

### `openssl_multi_staple_ready()`
**Returns:** boolean: true if OpenSSL 3.6+ (supports SSL_CTRL 143)

**Purpose:** Detect multi-staple capability (leaf + intermediates).

**Mechanism:**
- Probes SSL_ctrl(143) return value
- Publishes worker vote to shared dict
- Colony MIN (any leaf-only peer → leaf-only fleet) prevents failures

---

### `attach_ocsp_staple(ocsp_der, chain_pems, must_staple)`
**Parameters:**
- ocsp_der (string): OCSP response DER
- chain_pems (table): {leaf_pem, intermediate_pem...}
- must_staple (boolean): whether Must-Staple is enforced

**Returns:** string: STAPLE_DECISION code | nil

**Purpose:** Attach OCSP staple via FFI (ngx.ocsp.set_ocsp_status_resp).

**Algorithm:**
1. Check multi-staple capability (OpenSSL 3.6+)
2. Decide leaf-only vs multi-staple format
3. Build FFI stack (convert PEM to DER)
4. Call ngx.ocsp.set_ocsp_status_resp
5. Wrap in pcall (TLS alert 80 safety)

**Returns:** "ok" (success) | "ok_partial" (chain incomplete) | decision code on failure

---

### `clear_connection_staple()`
**Returns:** nil  
**Purpose:** Drop L1 on context swap (HTTP/2 coalescing).

**Reason:** Prevent leaf A's staple from landing on leaf B (security).

---

### `note_connection_staple(fingerprint)`
**Returns:** nil  
**Purpose:** Remember which cert was stapled (for clearing on swap).

---

### `issuer_path_intermediate_ready(fingerprint)`
**Returns:** boolean  
**Purpose:** Check if issuer.pem exists + is readable (chain available).

---

### `issuer_path_null_slots(fingerprint)`
**Returns:** number: count of missing intermediates in chain

**Purpose:** Diagnose chain incompleteness for logging.

---

# ocsp_pin.lua {#ocsp_pin}

**Responsibility:** Cross-subsystem coordination via allow-pin bus.

**Key Concepts:**
- **Allow-Pin Bus:** distributed validation results (HTTP → stream)
- **Skip-Validate:** use cached pins instead of FFI when safe
- **Peer-Refuse:** cluster consensus (coordinate refusals)
- **Compare-and-Delete:** atomic revocation (generation-bound)

## Functions

### `canary_trust_ok(ligand)`
**Parameters:** ligand (table): outside-ligand data

**Returns:** boolean  
**Purpose:** Check if ligand data is safe to trust (paged + generation-matched).

**Validation:**
- Ligand present (paged)
- Generation matches current cert state
- DER SHA256 matches binding

---

### `peer_refuse_blocks(meta)`
**Returns:** table: peer refusal entries | nil

**Purpose:** Get cluster consensus refusal blocks (from ocsp.json).

---

### `must_staple_refuse(meta, must_staple_state)`
**Returns:** string: STAPLE_DECISION code if Must-Staple forces refuse

**Logic:**
- If must_staple = true + no valid response → MUST_STAPLE_REFUSE
- If must_staple = nil (unknown) → treat as true (fail-closed)
- Otherwise → no forced refuse

---

### `allow_pin_set(fingerprint, sha, gen, ttl)`
**Returns:** nil  
**Purpose:** Publish allow-pin to shared dict (validation succeeded).

**Usage:** After FFI validates, store result for cross-subsystem reuse.

---

### `allow_pin_get(fingerprint)`
**Returns:** tuple (sha, gen) | (nil, nil)

**Purpose:** Retrieve allow-pin (skip-validate fast path).

---

### `compare_and_delete_revoke(fingerprint, expected_sha, expected_gen)`
**Returns:** boolean: true if revoked (deleted)

**Purpose:** Atomic revocation (generation-bound safety).

**Used by:** Soft-recall to revoke stale pins after cert rotation.

---

# ocsp_must_staple.lua {#ocsp_must_staple}

**Responsibility:** Must-Staple enforcement with fail-closed semantics.

**Key Concepts:**
- **Tri-State Detection:** true (required) | false (not required) | nil (unknown)
- **Fail-Closed:** nil/unknown treated as Must-Staple (enforce)
- **Soft-Fuse Modes:** can soften enforcement for compatibility

## Functions

### `is_must_staple(cert_pem, server_name, internalstore)`
**Parameters:**
- cert_pem (string): certificate
- server_name (string): site identifier
- internalstore (table): shared state

**Returns:** tri-state: true | false | nil

**Purpose:** Determine if Must-Staple is required for a certificate.

**Sources:**
1. TLS Feature 5 extension (from cert)
2. ocsp.json flag (from metadata)
3. nil (unknown)

---

### `enforce_must_staple(cert_pem, ocsp_response, server_name, internalstore, soften)`
**Parameters:**
- cert_pem (string): certificate
- ocsp_response (string|nil): OCSP response DER or nil
- server_name (string): site identifier
- internalstore (table): shared state
- soften (boolean): allow soft-fuse mode

**Returns:** boolean: true if OCSP must be provided (enforce), false if optional

**Logic:**
1. Detect Must-Staple requirement
2. If nil/unknown: treat as required (fail-closed)
3. If soften=true + mode="open": return false (allow missing)
4. Otherwise: return requirement status

---

# ocsp_warmer.lua {#ocsp_warmer}

**Responsibility:** Background cache warming for L1 optimization.

**Key Concepts:**
- **Pre-Warming:** Load OCSP responses into L1 at startup
- **Background Refresh:** Re-validate responses before expiry
- **Lazy Deletion:** Defer invalidation until next access

## Functions

### `maybe_rearm_l1_warmer()`
**Returns:** nil  
**Purpose:** Schedule next L1 warming cycle if needed.

**Used by:** ocsp.lua after attaching staple (mark cache as valid).

---

### `warm_cache_on_startup()`
**Returns:** table: {warmed=N, stale=N, invalid=N, failed=N}

**Purpose:** Pre-load OCSP responses from disk into L1 at worker startup.

**Algorithm:**
1. Scan ocsp.json files in cache directory
2. For each: read OCSP DER, check freshness
3. Validate response (basic checks: not expired, file recent)
4. Mark as "validated" in async state (skip TLS FFI)
5. Return statistics

---

### `refresh_ocsp_in_background()`
**Returns:** nil  
**Purpose:** Refresh soon-to-expire OCSP responses before expiry.

**Used by:** Background scheduler (off-path, not TLS critical path).

---

# ocsp.lua {#ocsp}

**Responsibility:** Central orchestrator for OCSP stapling across HTTP and stream subsystems.

**Key Concepts:**
- **Two-Tier Validation:** Tier 1 (L1 cache) + Tier 2 (FFI)
- **Async Validation State:** pending|validated|failed (generation-bound)
- **Dual-Cert Leaf Ranking:** Choose best leaf by Must-Staple health + sig-alg fit
- **Allow-Pin Bus Coordination:** Share validation results across subsystems

## Core Validation Flow

```
TLS Handshake (ssl_certificate)
    ↓
set_certs_from_pem()
    ├─→ ordered_leaves_for_handshake() [rank by Must-Staple + sig-alg]
    └─→ staple() [for each leaf]
            ├─→ Tier 1: L1 cache hit
            ├─→ Tier 2: FFI validation (on miss)
            └─→ attach via ngx.ocsp.set_ocsp_status_resp()
```

## Functions

### `async_validation_key(fingerprint)`
**Returns:** string: "OCSP:ASYNC_VALIDATE:{fingerprint}" | nil

**Purpose:** Generate shared-dict key for async validation state.

---

### `async_status_payload(status, meta, resp, fingerprint)`
**Parameters:**
- status (string): "pending" | "validated" | "failed"
- meta (table): metadata
- resp (string): OCSP response DER
- fingerprint (string): certificate fingerprint

**Returns:** string: "status|sha|gen" | nil

**Purpose:** Encode async validation status with generation binding.

**Format:** `"pending|sha256_64chars|gen123"`

**Why:** Bind status to specific response body (soft-recall prevents stale status from blocking new body).

---

### `parse_async_status_payload(raw)`
**Returns:** tuple (status, sha, gen) | (nil, nil, nil)

**Purpose:** Decode async validation status payload.

**Security:** Rejects legacy bare status (no gen) to prevent soft-recall blocking.

---

### `mark_async_validation_pending(fingerprint, meta, resp)`
**Returns:** nil  
**Purpose:** Mark response as queued for async validation (TTL 120s).

---

### `mark_async_validation_done(fingerprint, meta, resp)`
**Returns:** nil  
**Purpose:** Mark response as validated by async job (TTL 3600s).

---

### `mark_async_validation_failed(fingerprint, meta, resp)`
**Returns:** nil  
**Purpose:** Mark response as invalid per async job (TTL 3600s).

---

### `get_async_validation_status(fingerprint, meta, resp)`
**Returns:** string: "pending" | "validated" | "failed" | nil

**Purpose:** Retrieve async status (only if generation matches).

**Gen Check:** Soft-recall invalidates stale status.

---

### `issuer_candidates(blocks, leaf_pem, fingerprint, stored_pem)`
**Parameters:**
- blocks (table): certificate chain blocks
- leaf_pem (string): leaf certificate
- fingerprint (string): leaf SPKI fingerprint
- stored_pem (string|false|nil): shard issuer.pem (false = absent)

**Returns:** table: ordered PEM list (deduped by SPKI)

**Purpose:** Build list of issuers for ngx.ocsp.validate attempts.

**Algorithm:**
1. If stored_pem provided, use it (shard pin)
2. Else: read issuer.pem from disk
3. Extract SPKI fingerprint (pin target)
4. Filter chain blocks: keep only matching SPKI
5. If issuer absent: accept chain issuers (fail-open)
6. Dedupe by SPKI (re-encodings don't burn validate budget)
7. Return ordered list

**Security Note:** If issuer.pem present but unparsable, refuse chain fallthrough (fail-closed).

---

### `validate(ocsp, ssl, ocsp_der, leaf_pem, issuer_pem, shard_issuer_spki)`
**Parameters:**
- ocsp (ffi): ngx.ocsp module (FFI object)
- ssl (ffi): OpenSSL SSL module
- ocsp_der (string): OCSP response DER
- leaf_pem (string): leaf certificate
- issuer_pem (string): issuer certificate
- shard_issuer_spki (string): expected issuer SPKI (nil = no pin)

**Returns:** boolean: true if valid, false otherwise

**Purpose:** One FFI validation attempt (signature + death-time check).

**Algorithm:**
1. Call ngx.ocsp.validate_ocsp_response (10-20ms FFI)
2. Check death-time: now ≤ nextUpdate - clock_skew
3. If shard_issuer_spki set: verify issuer SPKI matches
4. Return validation result

---

### `set_shared_validation_result(fingerprint, meta, resp, result)`
**Returns:** nil  
**Purpose:** Store validation result for cross-handshake sharing.

**Binding:** SHA256(DER) + soft_recall_gen (generation-bound, TTL 60s)

**Why Not Share Failures:** Thin issuer bag must not block fatter chain for 60s.

---

### `get_shared_validation_result(fingerprint, meta, resp, max_wait_ms)`
**Returns:** string: "pass" | nil

**Purpose:** Retrieve cached validation result from sibling handshake.

**Cold Path:** If no concurrent validator, return nil (don't spin 100ms).

---

### `mark_ffi_needed(internalstore, fingerprint, meta, resp)`
**Returns:** nil  
**Purpose:** Record that FFI validation is required (response not in async_validated).

**Used by:** Budget enforcement (prevent spinning on fatter chains).

---

### `is_ffi_needed(internalstore, fingerprint, meta, resp)`
**Returns:** boolean  
**Purpose:** Check if this specific response body needs FFI validation.

**Checks:** Generation match (soft-recall invalidates).

---

### `try_staple(internalstore, server_name, fingerprint, leaf_pem, probe_only, meta, chain_blocks, apply_soften)`
**Parameters:**
- internalstore (table): shared state
- server_name (string): site identifier
- fingerprint (string): leaf SPKI fingerprint
- leaf_pem (string): leaf certificate
- probe_only (boolean): skip attachment (health check only)
- meta (table): ocsp.json metadata
- chain_blocks (table): {leaf, intermediates...}
- apply_soften (boolean): allow Must-Staple softening

**Returns:** string: STAPLE_DECISION code (ok | ok_partial | validation_failed | ...)

**Purpose:** Core stapling logic: validate leaf + attach response.

**Tier 1 - L1 Cache (fast path, ~0.1-1ms):**
1. Check L1 (shared dict)
2. If hit + verified binding + generation match: skip FFI
3. If hit + paged ligand: check canary-paged safety

**Tier 2 - FFI Validation (on miss, ~10-20ms):**
1. Read OCSP response from disk
2. Build issuer candidates (shard pin + chain)
3. Walk issuer list, calling validate() for each
4. Store result in shared validation (thundering-herd)
5. Cache in L1 for next handshake

**Attachment (if valid):**
1. Build presentable chain
2. Check Must-Staple enforcement
3. Call attach_ocsp_staple()
4. Mark async_validation_done (skip next TLS FFI)

**Budget Guard:**
- Track FFI time per handshake (50ms budget)
- Skip later candidates if budget exhausted

---

### `log_ocsp_stapled(server_name, kind, fp, resp)`
**Returns:** nil  
**Purpose:** Log successful OCSP staple attachment.

**Output:** `OCSP OK fingerprint={fp} server={server_name} decision=ok`

---

### `log_ocsp_staple_skip(kind, fp, reason, server_name)`
**Returns:** nil  
**Purpose:** Log skipped/refused OCSP staple.

**Output:** `OCSP SKIP reason={reason} fingerprint={fp}`

---

### `ordered_leaves_for_handshake(leaves, sigalgs_ext, prefer_kind)`
**Parameters:**
- leaves (table): {leaf_pem...} array
- sigalgs_ext (string): TLS 1.3 signature_algorithms extension (binary)
- prefer_kind (string): preferred key type ("ECDSA" | "RSA" | nil)

**Returns:** table: reordered leaves (best match first)

**Purpose:** Rank leaves by Must-Staple health + TLS 1.3 signature algorithm compatibility.

**Algorithm:**
1. Parse ClientHello signature_algorithms extension
2. For each leaf: check Must-Staple status + key kind
3. Score by: (a) Must-Staple health, (b) sig-alg fit, (c) key preference
4. Sort leaves by score (descending)
5. Return ordered list

**Why:** Avoid leaf with Must-Staple if staple unavailable; use weakest Must-Staple first (fail safer).

---

### `select_leaf_for_handshake(leaves, sigalgs_ext, prefer_kind)`
**Returns:** string: leaf_pem | nil

**Purpose:** Select single best leaf from array.

**Uses:** ordered_leaves_for_handshake, picks first.

---

### `leaf_pem_of(leaf)` / `leaf_fp_of(leaf)`
**Parameters:** leaf (string|table): leaf certificate (PEM or {pem, fp} tuple)

**Returns:** string: PEM or fingerprint

**Purpose:** Extract leaf PEM or fingerprint from flexible input format.

---

### `set_certs_from_pem(cert_pem, key_pem, internalstore, server_name, prefer_kind)`
**Parameters:**
- cert_pem (string): multi-cert PEM bundle
- key_pem (string): private key PEM
- internalstore (table): shared state
- server_name (string): site identifier
- prefer_kind (string): preferred key type

**Returns:** nil (side effect: installs certs + staples via FFI)

**Purpose:** Main TLS handshake hook (ssl_certificate phase).

**Algorithm:**
1. Parse multi-cert PEM → array of leaves
2. Call ordered_leaves_for_handshake() → rank by Must-Staple + sig-alg
3. Set ngx.var.ssl_certificate, ngx.var.ssl_certificate_key (leaf + key)
4. For each leaf: call staple() → attach OCSP response
5. Break on first success (must-staple or best health)

---

### `staple_from_fingerprint(internalstore, server_name, fingerprint, probe_only, mode, chain_blocks)`
**Parameters:**
- internalstore (table): shared state
- server_name (string): site identifier
- fingerprint (string): leaf SPKI fingerprint
- probe_only (boolean): health check only
- mode (string): "open" | "staple_only" | "normal"
- chain_blocks (table): {leaf, intermediates...}

**Returns:** string: STAPLE_DECISION code | nil

**Purpose:** Staple a single leaf by fingerprint (parametric helper).

---

### `staple_one_leaf(internalstore, server_name, leaf_pem, cert_fp_hint, probe_only, apply_soften)`
**Parameters:**
- internalstore (table): shared state
- server_name (string): site identifier
- leaf_pem (string): certificate
- cert_fp_hint (string): fingerprint hint (optimization)
- probe_only (boolean): health check
- apply_soften (boolean): Must-Staple softening

**Returns:** string: STAPLE_DECISION code | nil

**Purpose:** Staple a single leaf (main entry point).

---

### `_M.staple(internalstore, server_name, cert_pem, cert_fp_hint)`
**Purpose:** Public API for stapling a certificate.

---

### `_M.probe(internalstore, server_name, cert_pem, cert_fp_hint, apply_soften)`
**Purpose:** Health check (staple without attachment, used for diagnostics).

---

### `_M.requires_must_staple(cert_pem, cert_fp_hint)`
**Returns:** boolean | nil  
**Purpose:** Detect Must-Staple requirement (public API).

---

### `_M.prefer_kind_from_sigalgs(ext)`
**Parameters:** ext (string): signature_algorithms extension (binary)

**Returns:** string: "ECDSA" | "RSA" | nil

**Purpose:** Determine preferred key type from ClientHello.

---

### `_M.capture_client_hello()`
**Returns:** table: {signature_algorithms, ...} | nil

**Purpose:** Parse and cache ClientHello for access across request phases.

---

### `_M.handshake_sni(fallback)`
**Parameters:** fallback (string): default SNI if detection fails

**Returns:** string: SNI from ssl_client_hello_server_name or fallback

**Purpose:** Get TLS 1.3 SNI early (before ssl_certificate phase).

---

### `_M.async_validate_response(fingerprint, ocsp_der, issuers, leaf_pem, meta)`
**Parameters:**
- fingerprint (string): certificate fingerprint
- ocsp_der (string): OCSP response DER
- issuers (table): {issuer_pem...}
- leaf_pem (string): leaf certificate
- meta (table): metadata

**Returns:** string: "validated" | "failed" | nil

**Purpose:** Background job validation (off-path, called by ocsp-refresh.py).

**Algorithm:**
1. For each issuer: call validate()
2. If any succeeds: mark_async_validation_done, return "validated"
3. Else: mark_async_validation_failed, return "failed"

---

# ocsp_http.lua {#ocsp_http}

**Responsibility:** HTTP subsystem integration (lua_ssl_certificate phase + access phases).

**Key Concepts:**
- **Lazy Initialization:** Load OCSP on first use (reduce startup cost)
- **Error Boundaries:** Wrap all OCSP calls in pcall (prevent TLS failures)
- **Multisite SNI:** Use SNI + datastore to route to correct site config

## Functions

### `init_http_ocsp()`
**Returns:** table: ocsp module | nil

**Purpose:** Lazy-load OCSP module on first HTTP request.

**Why Lazy:** Reduce NGINX startup time (no OCSP until first TLS handshake).

---

### `http_ssl_certificate()`
**Returns:** nil (side effect: installs cert + staple via FFI)

**Purpose:** HTTP lua_ssl_certificate hook.

**Algorithm:**
1. Get SNI from TLS handshake
2. Resolve site config from datastore
3. Read cert_pem + key_pem (from site config or file)
4. Call ocsp._M.set_certs_from_pem()
5. Wrap in pcall (error boundary)

**Security:** Prevents OCSP exceptions from breaking TLS.

---

### `http_get_ocsp_status()` (example HTTP API)
**Returns:** JSON response with OCSP staple info

**Purpose:** Diagnostic endpoint (check staple health).

---

## Integration Points

- **lua_ssl_certificate:** Hook for all TLS handshakes
- **access/rewrite:** Optional health checks
- **logging phase:** Optional diagnostics

---

## Summary Table

| Module | Lines | Key Functions | Role |
|--------|-------|---|------|
| ocsp_common | 1185 | log, get_or_build_domain_table, staple_decision codes | Config + utilities |
| ocsp_cert | 1200 | spki_fingerprint, has_must_staple, certid_matches | Cert parsing |
| ocsp_store | 1685 | resp_still_fresh, get_l1, warm_cache, read_ocsp_json | Storage + cache |
| ocsp_chain | 1520 | issuer_linked_chain_blocks, attach_ocsp_staple | Chain + attachment |
| ocsp_pin | 1214 | canary_trust_ok, peer_refuse_blocks, allow_pin_* | Coordination |
| ocsp_must_staple | 194 | is_must_staple, enforce_must_staple | Must-Staple |
| ocsp_warmer | 773 | maybe_rearm_l1_warmer, warm_cache_on_startup | Background |
| ocsp | 3691 | try_staple, validate, ordered_leaves_for_handshake | Orchestrator |
| ocsp_http | 5964 | http_ssl_certificate, http_get_ocsp_status | HTTP integration |
| **TOTAL** | **17,426** | | |

---

## Key Design Patterns

### 1. **Weak-Map Memoization**
Used for: SNI domains, PEM profiles, chain caches
- **Why:** Auto-invalidates on config reload (new vars table)
- **Safety:** No explicit cleanup needed

### 2. **Generation Tuples**
Used for: Async validation state, soft-recall prevention
- **Format:** (SHA256_DER, soft_recall_gen)
- **Why:** Bind state to specific cert body; prevent stale after rotation

### 3. **Shared Validation Results**
Used for: Cross-handshake thundering-herd protection
- **TTL:** 60s (match validate budget)
- **Binding:** DER SHA + generation
- **Why:** Concurrent handshakes share first validator's result

### 4. **L1 Cache Hierarchy**
Tiers:
1. Shared dict (bw3 format) - 300s TTL
2. Disk shard metadata - job-maintained
3. Outside-ligand - paged, canary-trusted
4. Cluster consensus - floor blocks

### 5. **Soft-Recall (Cert Rotation)**
- **Trigger:** Certificate rotation detected (new DER)
- **Mechanism:** Increment soft_recall_gen
- **Effect:** Invalidate all cached OCSP for old DER
- **Safety:** Generation tuple prevents stale OCSP attaching to new cert

### 6. **Budget Guards**
- **Validate budget:** 50ms per TLS handshake
- **Issuer candidates:** Max 10 (prevent DoS)
- **Cache entries:** 512 PEM memo, 256 DER memo, 64 chain fallback

### 7. **Fail-Closed Semantics**
- **Must-Staple unknown:** Treat as required (enforce)
- **Issuer unavailable:** Skip (open) unless shard-pinned
- **Response unreadable:** Refuse (fail-closed)

### 8. **Error Boundaries**
- **HTTP integration:** All calls wrapped in pcall (prevent TLS failure)
- **FFI calls:** Defensive null checks + type validation
- **Disk reads:** Graceful nil returns (filesystem permission, missing files)

---

## Critical Paths

### TLS Handshake (0-100ms budget)

```
ssl_certificate phase (NGINX)
  ↓
lua_ssl_certificate (HTTP integration)
  ↓
set_certs_from_pem() [ocsp.lua]
  ├─ ordered_leaves_for_handshake() [~5ms]
  │   ├─ Parse ClientHello
  │   └─ Rank by Must-Staple + sig-alg
  ├─ For each leaf: staple()
  │   ├─ staple_from_fingerprint()
  │   │   └─ try_staple() [~50ms budget]
  │   │       ├─ L1 hit [0.1-1ms] ← most handshakes stop here
  │   │       ├─ Tier 2: validate() [10-20ms] on miss
  │   │       │   ├─ Build issuer candidates
  │   │       │   └─ Call ngx.ocsp.validate_ocsp_response (FFI)
  │   │       └─ attach_ocsp_staple() [0.5-1ms]
  │   └─ Log + return decision
  └─ Set ngx.var.ssl_certificate + key
```

### Background Job (ocsp-refresh.py)

```
Every 60 seconds (scheduler)
  ↓
For each certificate:
  ├─ async_validate_response() [10-20ms FFI]
  ├─ Store result in shared dict (async_validation_done)
  ├─ Update L1 cache (warm_cache)
  └─ Write ocsp.json metadata
```

---

## Testing Checklist

- [ ] L1 cache hit (most handshakes ~1ms)
- [ ] L1 cache miss + FFI validation (10-20ms)
- [ ] Soft-recall (cert rotation invalidates OCSP)
- [ ] Must-Staple enforcement (refuse without staple)
- [ ] Cross-handshake sharing (concurrent handshakes share result)
- [ ] Async validation state tracking
- [ ] Paged ligand canary checks
- [ ] Serial blacklist enforcement
- [ ] Cluster floor consensus
- [ ] Multisite SNI resolution
- [ ] Multi-cert leaf ranking (by Must-Staple + sig-alg)
- [ ] Error boundaries (pcall wrapping)
- [ ] Budget guards (50ms per handshake, 10 issuers max)
- [ ] Connection staple clearing (HTTP/2 coalescing)
- [ ] Weak-map auto-invalidation (config reload)

