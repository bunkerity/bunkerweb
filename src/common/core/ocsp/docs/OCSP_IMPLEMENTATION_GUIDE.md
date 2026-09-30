# OCSP Stapling System: Implementation Deep Dive

**Last Updated:** 2026-09-29  
**Audience:** Developers maintaining/extending the OCSP system  
**Purpose:** Logic flows, edge cases, optimization details, and debugging guide

---

## Part 1: Critical Logic Flows

### Flow 1: TLS Handshake → Staple Attachment

```
TLS Client Hello
  ↓
nginx ssl_certificate phase
  ↓
http_ssl_certificate() [ocsp_http.lua]
  ├─ Get SNI from ClientHello
  ├─ Resolve site config from datastore
  └─ Call set_certs_from_pem(cert_pem, key_pem, internalstore, server_name, prefer_kind)
      ├─ Parse multi-cert PEM → leaves array
      ├─ Call ordered_leaves_for_handshake(leaves, sigalgs_ext, prefer_kind)
      │   ├─ Parse ClientHello signature_algorithms extension (binary)
      │   ├─ For each leaf:
      │   │   ├─ Detect Must-Staple status (tri-state)
      │   │   ├─ Check public key kind vs sig-alg compatibility
      │   │   └─ Score leaf by (Must-Staple health, sig-alg fit, preference)
      │   ├─ Sort by score (descending)
      │   └─ Return ordered array
      ├─ For each leaf in order:
      │   ├─ Set ngx.var.ssl_certificate = leaf PEM
      │   ├─ Set ngx.var.ssl_certificate_key = key PEM
      │   ├─ Call staple_one_leaf()
      │   │   ├─ Try to read OCSP response from disk
      │   │   ├─ Call try_staple() [critical path]
      │   │   │   ├─ TIER 1: L1 Cache (shared dict, ~0.1-1ms)
      │   │   │   │   ├─ Lookup: cache_key(fingerprint)
      │   │   │   │   ├─ Parse bw3 entry (epoch|binding|gen|expires|der)
      │   │   │   │   ├─ Verify: epoch match, binding == DER SHA, gen match
      │   │   │   │   ├─ Check: expires_unix > now + clock_skew
      │   │   │   │   └─ SUCCESS: skip FFI, return "ok"
      │   │   │   │
      │   │   │   ├─ TIER 1 MISS → Tier 2
      │   │   │   │
      │   │   │   ├─ TIER 2: Freshness + Metadata Validation (~1-5ms)
      │   │   │   │   ├─ Check async_validation status (pending|validated|failed)
      │   │   │   │   ├─ Check Must-Staple enforcement
      │   │   │   │   ├─ Check peer_refuse blocks (cluster consensus)
      │   │   │   │   ├─ Check serial_blacklist (revocation)
      │   │   │   │   ├─ Check resp_still_fresh() (time bounds)
      │   │   │   │   ├─ Check canary_paged_body_ok (ligand safety)
      │   │   │   │   └─ Decision: proceed to Tier 3 or skip FFI
      │   │   │   │
      │   │   │   ├─ SKIP FFI (if mode=open or Must-Staple=false)
      │   │   │   │   ├─ Attach response speculatively
      │   │   │   │   ├─ Queue async validation (pending state)
      │   │   │   │   └─ Return "ok"
      │   │   │   │
      │   │   │   ├─ TIER 3: FFI Validation (~10-20ms)
      │   │   │   │   ├─ Build issuer_candidates (shard pin + chain)
      │   │   │   │   ├─ Dedupe by SPKI (prevent multiply-counted costs)
      │   │   │   │   ├─ Deterministic shuffle via LCG
      │   │   │   │   ├─ For each issuer (max 10):
      │   │   │   │   │   ├─ Check validate_budget (50ms hardcap)
      │   │   │   │   │   ├─ Call validate(ocsp, ssl, ocsp_der, leaf_pem, issuer_pem)
      │   │   │   │   │   │   ├─ Parse leaf+issuer to DER (Tier 1+2 cache)
      │   │   │   │   │   │   ├─ Call ngx.ocsp.validate_ocsp_response (FFI)
      │   │   │   │   │   │   ├─ Check death-time (nextUpdate - skew)
      │   │   │   │   │   │   ├─ Cache result (per-request + persistent)
      │   │   │   │   │   │   └─ Return boolean
      │   │   │   │   │   ├─ If valid:
      │   │   │   │   │   │   ├─ Store shared_validation result
      │   │   │   │   │   │   ├─ Early-exit (success, don't test others)
      │   │   │   │   │   │   └─ Break
      │   │   │   │   │   └─ Else: continue to next issuer
      │   │   │   │   ├─ If all issuers fail: return "validate_exhausted"
      │   │   │   │   └─ If budget exceeded: return "validate_budget"
      │   │   │   │
      │   │   │   └─ attach_ocsp_staple(ocsp_der, chain_pems, must_staple)
      │   │   │       ├─ Check multi-staple capability
      │   │   │       ├─ Build FFI stack (PEM → DER)
      │   │   │       ├─ Call ngx.ocsp.set_ocsp_status_resp (wrapped in pcall)
      │   │   │       ├─ Check intermediate Must-Staple
      │   │   │       └─ Return decision code
      │   │   │
      │   │   └─ Log outcome (log_ocsp_stapled or log_ocsp_staple_skip)
      │   │
      │   └─ If success: break (leaf stapled, done)
      │
      └─ Return to nginx (certificate + key + staple installed)
         ↓
Client receives cert + OCSP staple
```

---

### Flow 2: Background Validation (ocsp-refresh.py)

```
Every 60 seconds (Scheduler)
  ↓
For each certificate fingerprint:
  ├─ Read ocsp.json metadata
  ├─ Check if OCSP response needs refresh
  ├─ Check if expires_unix within 20% of lifetime
  │   └─ If yes: fetch from responder
  ├─ ocsp._M.async_validate_response(fingerprint, ocsp_der, issuers, leaf_pem, meta)
  │   ├─ For each issuer:
  │   │   ├─ Call validate() [10-20ms FFI]
  │   │   └─ If valid: break
  │   ├─ Mark async_validation_done (TTL 3600s, generation-bound)
  │   └─ Return "validated"
  ├─ warm_cache(internalstore, fingerprint, ocsp_der, meta)
  │   ├─ Validate freshness
  │   ├─ Calculate TTL (min(remaining_lifetime, 300s))
  │   ├─ Build bw3 entry (epoch|binding|gen|expires|der)
  │   └─ Store in ngx.shared.internalstore (or internalstore_stream)
  ├─ Update ocsp.json (write metadata to disk)
  │   ├─ spki_fp
  │   ├─ der_sha256
  │   ├─ soft_recall_gen
  │   ├─ expires_unix
  │   ├─ must_staple flag
  │   └─ serial_hex
  └─ Check for soft-recall (certificate rotation)
      ├─ If old cert detected:
      │   ├─ Increment soft_recall_gen
      │   ├─ Invalidate all cached OCSP for old DER
      │   └─ Update ocsp.json
      └─ Notify TLS path (allow-pin revocation, shared dict update)
```

---

### Flow 3: Soft-Recall (Certificate Rotation)

**Trigger:** Certificate body changes (new DER)

**Problem:** If cert A (DER1) was stapled with OCSP response X, then cert rotates to B (DER2), old response X should not attach to B.

**Solution:** Generation tuple (SHA256(DER), soft_recall_gen)

**Mechanism:**

```
Initial state:
  ocsp.json: {spki_fp, der_sha256="abc123...", soft_recall_gen=1, ...}
  L1 cache: "bw3\0" + epoch + "abc123...|gen=1" + ... + der_bytes

Certificate rotated (new DER):
  1. Detect: new_der_sha256 ≠ stored_der_sha256
  2. Action: increment soft_recall_gen (1 → 2)
  3. Write: ocsp.json with new der_sha256 + gen=2
  4. Result: L1 entry (with gen=1) now fails the gen-match check
     ├─ Old entry skipped (generation mismatch)
     └─ New OCSP fetched (and validated with gen=2)

TLS Handshake with new cert:
  ├─ Attempt L1 hit with new cert (DER2)
  ├─ L1 entry found but gen=1 ≠ current_gen=2
  ├─ Generation mismatch → evict L1 (skip it)
  ├─ Proceed to Tier 2 validation (slower, but safe)
  └─ Eventually: new OCSP (with gen=2) loaded into L1

Result: Old OCSP(DER1, gen=1) never attaches to Cert(DER2, gen=2) ✓
```

**Benefits:**
- No stale OCSP after cert rotation
- No explicit invalidation needed (implicit via generation mismatch)
- Scales to many concurrent certs
- Soft-recall survives connection reuse (no global "epoch bump" needed)

---

### Flow 4: Cross-Handshake Validation Sharing

**Problem:** Many concurrent clients for same cert = many redundant 10-20ms FFI calls

**Solution:** First handshake validates; others reuse result (60s window)

**Mechanism:**

```
Handshake 1: cert=Leaf, response=OCSP_X
  ├─ Look for shared validation result
  │   └─ No entry found (first handshake)
  ├─ Claim lock: set_shared_validation_in_flight()
  │   └─ Store "in_flight" in shared dict (ttl=60s)
  ├─ Validate (FFI, 10-20ms)
  ├─ Success: set_shared_validation_result(fingerprint, meta, resp, true)
  │   └─ Store "pass" (generation-bound, ttl=60s)
  └─ Attach staple

Handshake 2: cert=Leaf, response=OCSP_X (concurrent)
  ├─ Look for shared validation result
  │   └─ Found: "in_flight" (Handshake 1 is validating)
  ├─ Wait up to 100ms for result (brief spin)
  ├─ Result appears (from Handshake 1): "pass"
  ├─ Reuse validation (0.1ms instead of 10-20ms)
  └─ Attach staple

Handshake 3: cert=Leaf, response=OCSP_Y (after Handshake 1 succeeded)
  ├─ Look for shared validation result of OCSP_X
  │   └─ Found but generation mismatch (different response body)
  ├─ Result not reusable
  ├─ Validate OCSP_Y locally
  └─ Attach staple
```

**Generation Binding:**
- Key: `OCSP:VALIDATE:{fingerprint}:{sha256(der)}|{soft_recall_gen}`
- Value: "pass" or "in_flight"
- **Why:** Soft-recall or re-page invalidates old result (new DER = different key)

---

## Part 2: Edge Cases & Error Handling

### Edge Case 1: issuer.pem Absent (Shard Pin Missing)

**Scenario:** Shard directory has no issuer.pem file

**Behavior:**
```lua
-- issuer_candidates() logic:
if stored_issuer_spki == nil then
    read_file(issuer_path(fingerprint))  -- returns nil
    issuer_absent = true
    want_spki = nil
end

if issuer_absent and not want_spki then
    -- FAIL-OPEN: Accept chain issuers without SPKI pin
    log(ngx.DEBUG, "OCSP issuer.pem absent; accepting chain issuers without SPKI pin")
    -- ... continue to build issuer_candidates from chain
end
```

**Effect:**
- ✅ Handshake continues (no cert = fail-open)
- ⚠️  Less secure (no issuer pin, any matching issuer works)
- → Scheduler should pre-fetch issuer.pem

---

### Edge Case 2: issuer.pem Present But Unreadable

**Scenario:** issuer.pem exists but parsing fails (corrupted, permission issue)

**Behavior:**
```lua
local want_spki = stored and spki_fingerprint(stored) or nil
if stored and not want_spki then
    -- issuer.pem present but unparsable
    log(ngx.ERR, "OCSP issuer.pem unreadable SPKI for fp " .. fp_short .. 
                 "; refusing chain fallthrough")
    return {}  -- Empty issuer list → issuer_unavailable → skip staple
end
```

**Effect:**
- ❌ Staple skipped (KEEP policy)
- → Scheduler or admin must fix issuer.pem
- → Fail-closed (conservative safety)

---

### Edge Case 3: validate() Budget Exceeded

**Scenario:** 50ms time budget depleted mid-issuer walk

**Behavior:**
```lua
-- In try_staple issuer loop:
if over_budget then
    log(ngx.ERR, format_staple_decision("validate_budget", {...}))
    -- Do NOT store pass/fail (budget is transient)
    clear_shared_validation_in_flight(fingerprint, meta, resp)
    return false, "validate_budget", false
end
```

**Effect:**
- ❌ Staple skipped (KEEP policy)
- ✅ Shared validation lock released (peers not stuck)
- ⚠️  force_ffi latch set (next handshake must finish FFI)
- → Implies issuer list too long or system overloaded

---

### Edge Case 4: Ligand Paging (Outside-Ligand Stale)

**Scenario:** ocsp-ligand/{fp} file is paged but DER diverged (cache coherence failure)

**Behavior:**
```lua
if canary_paged_body_ok(meta, fingerprint, resp) then
    -- Canary checks: paged flag + generation match + DER SHA match
    log(ngx.DEBUG, "OCSP trusting canary-paged body; skipping ngx.ocsp.validate_ocsp_response")
    return finish_attach(false)  -- Skip FFI
else
    -- Canary failed: ligand stale or generation mismatch
    log(ngx.WARN, "OCSP canary-paged check failed; falling back to full validation")
    -- Continue to Tier 3 FFI
end
```

**Effect:**
- ⚠️  Canary failed → fallback to full FFI validation
- ✅ Correct response attached (safety preserved)
- → Scheduler ligand update may have raced with TLS read

---

### Edge Case 5: Multi-Cert Leaf Ranking

**Scenario:** Multiple leaves (RSA + ECDSA), Must-Staple status differs

**Leaf Array:**
```lua
leaves = {
  "-----BEGIN... (RSA, Must-Staple=true, OCSP=missing)",
  "-----BEGIN... (ECDSA, Must-Staple=false, OCSP=valid)",
}
```

**Ranking Logic:**
```lua
-- ordered_leaves_for_handshake():
-- 1. Must-Staple health (true > false > nil)
-- 2. Sig-alg fit (does ClientHello sig_algorithms match?)
-- 3. Key preference (prefer_kind from ClientHello)

-- Result:
-- ECDSA (no Must-Staple) gets higher score than RSA (Must-Staple but missing OCSP)
-- → Use ECDSA (safer: no Must-Staple to enforce)
leaves_ranked = {
  "-----BEGIN... (ECDSA, Must-Staple=false, OCSP=valid)",   -- Score: 10
  "-----BEGIN... (RSA, Must-Staple=true, OCSP=missing)",    -- Score: 5
}
```

**Effect:**
- ✅ Prefer leaf without Must-Staple risk (fail safer)
- ✅ Honor ClientHello sig-algs (TLS compliance)
- ⚠️  Later leaves may have better OCSP but worse Must-Staple → skip them

---

### Edge Case 6: Soft-Recall Clears force_ffi Latch

**Scenario:** Certificate rotates while force_ffi latch is active

**Mechanism:**
```lua
-- force_ffi latch stores: "der_sha256|soft_recall_gen|hmac_tag"
-- is_ffi_needed() checks: current_gen == stored_gen

-- If cert rotates (soft_recall_gen increments):
old_latch: "abc123...|soft_recall_gen=1|tag"
new_gen: soft_recall_gen=2

is_ffi_needed():
  if stored_gen (1) ≠ current_gen (2):
    return false  -- Latch stale, clear it
```

**Effect:**
- ✅ Latch auto-clears on cert rotation
- ✅ No explicit cleanup needed
- → Prevents permanent "must-FFI" after validate_budget

---

## Part 3: Optimization Details

### Optimization 1: Per-Request Caching

**Where:** validate() function

**What:**
- PEM → DER parsing (Tier 1: ngx.ctx + Tier 2: shared dict)
- FFI validation results (per-request cache key = DER SHA + issuer SPKI)

**Why:**
- Multi-issuer walk parses same leaf repeatedly
- Same (response, issuer) pair tested multiple times
- Typical: 2-5ms → 0.1ms

**Code:**
```lua
local ctx = ngx.ctx
if der_cache_key and ctx then
    if not ctx.bw_ocsp_der_cache then
        ctx.bw_ocsp_der_cache = {}
    end
    local cached_entry = ctx.bw_ocsp_der_cache[der_cache_key]
    if cached_entry and cached_entry.gen == current_gen then
        der_chain = cached_entry.chain
        return  -- Hit: skip parsing
    end
end
```

---

### Optimization 2: Persistent DER Cache

**Where:** shared dict `bw_ocsp_validations`

**What:** Store parsed DER + generation across handshakes

**Why:** Cold start (next handshake) benefits from prior parse

**TTL:** 3600s (per OCSP lifetime)

---

### Optimization 3: Presentable Chain Caching

**Where:** ocsp_chain.lua

**What:** Per-request cache of issuer-linked chain

**Why:**
- Multiple phases call presentable_chain_blocks() (probe, health, attach)
- Chain building is O(n) (filter bad certs from bag)

**Cache Key:** "leaf_spki|intermediate_bag_identity"

**Reason for Key:** Prevent (leaf A, thin bag) from poisoning (leaf A, fat bag)

---

### Optimization 4: Weak-Map SNI Caching

**Where:** ocsp_common.lua

**What:** SNI → domain table lookup (weak-map keyed by site_vars table)

**Why:** Config reload auto-invalidates (new vars = new table object)

**Performance:** O(1) after rebuild, O(n) only on reload

---

### Optimization 5: Budget Guards

**Where:** try_staple() issuer loop

**What:** 50ms hardcap on FFI validation per handshake

**Why:**
- Prevent slow client → slow TLS handshake cascade
- Early-exit on first valid issuer (most certs have 1-2 issuers)
- Max 10 issuer candidates (prevent cert bomb)

**Code:**
```lua
if (hrtime() - t0) > OCSP_VALIDATE_BUDGET_NS then
    log(ngx.ERR, "OCSP validate_budget exceeded")
    return false, "validate_budget", false
end
```

---

### Optimization 6: Async Validation

**Where:** ocsp-refresh.py (background job)

**What:** Pre-validate OCSP responses off-path

**Why:**
- TLS path skips FFI if async_validation_done (0.1ms instead of 10-20ms)
- Handshake latency: 50ms → 1-5ms (10x improvement)

**Cost:** Scheduler CPU (one worker validates for many clients)

---

### Optimization 7: Lazy Initialization

**Where:** ocsp_http.lua

**What:** Load OCSP module on first request, not at startup

**Why:** Reduce nginx startup time (OCSP not needed until first TLS handshake)

---

### Optimization 8: Batch SPKI Fingerprinting

**Where:** ocsp_cert.lua

**Function:** batch_spki_fingerprints(cert_pems)

**What:** Fingerprint multiple certs in one pass

**Why:** Avoid repeated FFI calls for same cert

---

## Part 4: Testing Strategy

### Unit Tests

**Test:** `spki_fingerprint()` stability
```lua
local pem1 = read_file("example.pem")
local fp1a = spki_fingerprint(pem1)
local fp1b = spki_fingerprint(pem1)
assert(fp1a == fp1b, "SPKI should be deterministic")

local pem2 = rewrap_cert(pem1)  -- Same DER, different PEM encoding
local fp2 = spki_fingerprint(pem2)
assert(fp1a == fp2, "SPKI should be encoding-agnostic")
```

**Test:** Generation tuple binding
```lua
local meta = {soft_recall_gen = 1, ...}
local resp = read_ocsp_response()

local sha1, gen1 = generation_tuple(meta, resp)
assert(gen1 == 1, "Generation should match metadata")

-- Soft-recall: increment gen
meta.soft_recall_gen = 2
local sha2, gen2 = generation_tuple(meta, resp)
assert(gen2 == 2, "Generation should update on metadata change")
assert(sha1 == sha2, "DER SHA should remain same (body unchanged)")
```

**Test:** Weak-map auto-invalidation
```lua
local vars1 = {SERVER_NAME = "example.com"}
local domain_table1 = get_or_build_domain_table(vars1)
assert(domain_table1["example.com"] == true, "Domain should be in table")

-- Config reload: new vars object
local vars2 = {SERVER_NAME = "newsite.com"}
local domain_table2 = get_or_build_domain_table(vars2)
assert(domain_table2["newsite.com"] == true, "New domain should be in table")
assert(domain_table2["example.com"] == nil, "Old domain should not leak into new table")

-- Weak-map cleanup: collect_garbage (simulate old vars object being freed)
collectgarbage()
-- Old vars1 entry should be auto-evicted from weak map
```

---

### Integration Tests

**Scenario 1: L1 Cache Hit**
1. Handshake with Cert A (OCSP in cache)
2. Check: shared dict lookup succeeds
3. Check: ngx.ocsp.validate_ocsp_response NOT called (FFI skipped)
4. Check: staple attached successfully
5. Verify: elapsed time < 5ms (L1 hit is fast)

**Scenario 2: FFI Validation (L1 Miss)**
1. Handshake with Cert B (OCSP not in cache)
2. Check: shared dict lookup fails
3. Check: ngx.ocsp.validate_ocsp_response called (FFI executed)
4. Check: staple attached successfully
5. Verify: elapsed time 15-25ms (FFI is slow)

**Scenario 3: Soft-Recall (Cert Rotation)**
1. Handshake 1: Cert A (gen=1) → staple X attached
2. Simulate rotation: new DER for Cert A
3. Increment gen (1 → 2)
4. Handshake 2: Cert A (gen=2)
5. Check: L1 entry (gen=1) rejected (generation mismatch)
6. Check: New OCSP staple (or deferred if not ready)
7. Verify: old staple X never attaches to new cert

**Scenario 4: Cross-Handshake Sharing**
1. Handshake 1 starts: set lock "in_flight"
2. Handshake 2 arrives (concurrent): waits for result
3. Handshake 1 completes: set "pass" (validation success)
4. Handshake 2 receives: reuses result (0.1ms)
5. Both staple successfully
6. Verify: FFI called once, shared by two handshakes

**Scenario 5: Soft-Fuse Mode (open)**
1. Set SSL_USE_OCSP_STAPLING_MODE=open
2. Handshake with Must-Staple=false cert
3. Check: FFI skipped (validate() not called)
4. Check: staple attached speculatively
5. Check: async validation queued (pending)
6. Verify: TLS latency < 2ms (skip FFI benefit)

---

### Performance Tests

**Metric:** p50, p99 TLS handshake latency

**Baseline (no OCSP):**
- Expected: ~10-20ms (TCP + cert exchange)

**With OCSP (L1 hit):**
- Expected: ~15-25ms (L1 cache adds ~5ms)

**With OCSP (FFI miss):**
- Expected: ~30-50ms (L1 miss + FFI adds ~20ms)

**With OCSP (async done):**
- Expected: ~12-18ms (async speeds up TLS path)

---

### Security Tests

**Test: Soft-Recall Prevents Stale OCSP**
```lua
-- Setup:
local cert_der = read_file("cert.der")
local ocsp_response = fetch_ocsp(cert_der)  -- Valid 60 days

-- Scenario:
-- Day 1: attach ocsp_response (gen=1)
-- Day 35: renew cert → new_cert_der
-- Day 35: increment gen (1 → 2)

-- Test:
-- Old L1 entry: (binding="sha1...", gen=1, der=ocsp_response)
-- Current state: gen=2, new_cert_der
-- Result: L1 entry REJECTED (gen mismatch)
-- Outcome: old OCSP never attaches to new cert ✓
```

**Test: Issuer Pin Prevents Wrong SPKI**
```lua
-- Setup:
local issued_by_ca_a = read_cert("issued_by_ca_a.pem")
local issued_by_ca_b = read_cert("issued_by_ca_b.pem")  -- Cross-signed

-- Scenario:
-- Shard pin: issuer.pem = CA_A's cert
-- SPKI mismatch: OCSP signed by CA_B

-- Test:
local candidates = issuer_candidates(blocks, leaf_pem, fingerprint, ca_a_pem)
-- Result: CA_B filtered out (SPKI mismatch)
-- Outcome: only CA_A issuer tried, staple succeeds ✓
```

**Test: Must-Staple Enforcement**
```lua
-- Setup:
local must_staple_cert = read_cert("must_staple.pem")  -- TLS Feature 5
local response_missing = nil

-- Test:
local should_enforce = is_must_staple(must_staple_cert)
assert(should_enforce == true, "Must-Staple should be detected")

-- Result: staple required, response missing
-- Outcome: staple refused, TLS fails ✓
```

---

## Part 5: Debugging Guide

### Log Prefixes

| Prefix | Meaning | Filter |
|--------|---------|--------|
| `OCSP_STAPLED` | Staple attached | ✓ success |
| `OCSP_SKIP` | Staple skipped | ⚠️  normal |
| `OCSP_REFUSE` | Staple refused | ❌ error |
| `OCSP_VALIDATE_BUDGET` | FFI timeout | ⚠️  overload |
| `OCSP_FUN` | Fundamental issue | ❌ error |

### Debug Logging

**Enable via:**
```bash
SSL_LOG_LEVEL=debug  # NGINX debug logging
BW_LOG_LEVEL=debug   # BunkerWeb debug logging
```

**Key Debug Lines:**
```lua
log(ngx.DEBUG, "OCSP L1 hit: skip FFI")          -- Cache working
log(ngx.DEBUG, "OCSP validating with issuer N")  -- FFI called
log(ngx.ERR, "OCSP FFI validation slow: XXms")   -- Latency issue
log(ngx.ERR, "OCSP cert_parse slow: XXms")       -- DER parse issue
```

### Telemetry Context

**Per-Request Metrics** (stored in ngx.ctx):

```lua
ngx.ctx.bw_ocsp_metrics = {
    ffi_validate_ms = 15.2,          -- FFI duration
    der_cache_tier1_hit = true,      -- Per-req cache
    der_cache_tier2_hit = false,     -- Shared dict cache
}

ngx.ctx.bw_ocsp_disk_io = {
    cert_parse_ms = 2.1,             -- DER parse duration
}

ngx.ctx.bw_ffi_validation_cache = {...}  -- Validation cache
ngx.ctx.bw_ffi_cache_hits = 3            -- Per-req hits
ngx.ctx.bw_ffi_cache_misses = 1          -- Per-req misses
```

**Log Access:**
```bash
grep "OCSP_STAPLED\|OCSP_SKIP\|OCSP_REFUSE" /var/log/bunkerweb/bunkerweb.log
```

---

## Part 6: Common Issues & Fixes

### Issue 1: Staple Not Attaching (Decision: response_not_found)

**Cause:** OCSP response file missing

**Debug:**
```bash
ls -la /var/cache/bunkerweb/ssl/??/??/{fp}/ocsp.der
# If missing: scheduler job not running or failed
```

**Fix:**
1. Check scheduler: `systemctl status bunkerweb-scheduler`
2. Check logs: `/var/log/bunkerweb/scheduler.log`
3. Force refresh: trigger ocsp-refresh.py manually

---

### Issue 2: Slow Handshakes (50ms+ latency)

**Cause:** FFI validation running in TLS path

**Debug:**
```bash
grep "ffi_validate_ms" /var/log/bunkerweb/bunkerweb.log | tail -10
# Should be: 0.1ms (cached) or 15-20ms (FFI), not 50ms+
```

**Fix:**
1. Wait for scheduler (async validation pre-warms cache)
2. Check issuer list size (max 10 attempted)
3. Monitor CPU load (FFI may be slow under load)

---

### Issue 3: Soft-Recall Blocking Staple

**Cause:** Generation mismatch after cert rotation

**Debug:**
```bash
grep "generation mismatch\|soft-recall" /var/log/bunkerweb/bunkerweb.log
```

**Why:** Expected! Soft-recall intentionally blocks old OCSP on new cert

**Fix:** Wait for scheduler to validate new OCSP response (60s cycle)

---

### Issue 4: Must-Staple Refusing Staple

**Cause:** Certificate requires OCSP but response unavailable

**Debug:**
```bash
grep "must_staple_refuse\|MUST_STAPLE_REFUSE" /var/log/bunkerweb/bunkerweb.log
```

**Fix:**
1. Check OCSP responder is accessible
2. Check cert has valid TLS Feature 5 extension
3. Soft-fuse: set `SSL_USE_OCSP_STAPLING_MODE=open` (temporary)

---

## Part 7: Performance Tuning

### Knob 1: Validate Budget (OCSP_VALIDATE_BUDGET_S)

**Current:** 50ms (0.05s)

**Increase to 100ms:**
- Allows more issuer candidates per handshake
- Handshake latency +50ms (usually unacceptable)

**Decrease to 25ms:**
- Forces early-exit
- Risky: may skip valid issuer
- Only if system severely overloaded

### Knob 2: L1 Cache TTL (L1_MAX_TTL)

**Current:** 300s

**Increase to 600s:**
- Longer cache residency
- Risk: miss newer OCSP response

**Decrease to 120s:**
- Shorter cycle: more disk reads
- Benefit: faster response to OCSP updates

### Knob 3: Async Validation TTL

**Current:** 3600s (1 hour)

**Increase to 86400s:**
- Longer result caching
- Risk: scheduler outage → stale "validated" claims

**Decrease to 600s:**
- Shorter caching
- Benefit: faster recovery from scheduler outage

---

## Summary Checklist

**When Adding New OCSP Feature:**
- [ ] Update generation tuple if state changes
- [ ] Wrap FFI calls in pcall()
- [ ] Add soft-recall invalidation if needed
- [ ] Cache results (L1 + persistent)
- [ ] Test with multi-cert + Must-Staple + soft-fuse
- [ ] Measure TLS latency (p50/p99)
- [ ] Document edge cases

**When Debugging OCSP Issue:**
- [ ] Check scheduler logs (is async validation running?)
- [ ] Check OCSP responder (curl test)
- [ ] Check shard metadata (ls ocsp.json)
- [ ] Check L1 cache (shared dict key exists?)
- [ ] Check TLS logs (decision code, FFI latency)
- [ ] Check Must-Staple mode (open vs normal)
- [ ] Check cert freshness (not expired, not future)

