# OCSP Stapling System: Architecture Summary

**Document Type:** Visual architecture guide + reference  
**Audience:** Anyone needing a high-level understanding of OCSP system design  
**Last Updated:** 2026-09-29

---

## System at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│ TLS Handshake (Client → NGINX)                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├─→ ssl_certificate phase
                   │
        ┌──────────▼────────────┐
        │ http_ssl_certificate()│ (ocsp_http.lua)
        │ (HTTP integration)    │
        └──────────┬────────────┘
                   │
        ┌──────────▼────────────────────────────┐
        │ set_certs_from_pem()                  │ (ocsp.lua)
        │ - Parse multi-cert PEM                │
        │ - Rank leaves by Must-Staple + sig-alg│
        │ - Staple best leaf                    │
        └──────────┬────────────────────────────┘
                   │
        ┌──────────▼────────────────────────────┐
        │ try_staple()                          │ (ocsp.lua)
        │ - L1 cache lookup                     │
        │ - Tier 2: metadata validation         │
        │ - Tier 3: FFI validation              │
        │ - Attach via ngx.ocsp                 │
        └──────────┬────────────────────────────┘
                   │
        ┌──────────▼─────────────────────────────────────┐
        │ attach_ocsp_staple()                          │
        │ (ocsp_chain.lua)                              │
        │ - Check multi-staple capability               │
        │ - Build FFI stack                             │
        │ - Call ngx.ocsp.set_ocsp_status_resp          │
        │ - Handle intermediate Must-Staple             │
        └──────────┬─────────────────────────────────────┘
                   │
                   └─→ TLS response with OCSP staple
```

---

## Module Interaction Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                       ocsp.lua                                  │
│                  Central Orchestrator                           │
│  - try_staple() [core validation logic]                        │
│  - validate() [FFI wrapper]                                    │
│  - set_certs_from_pem() [TLS hook entry]                       │
│  - ordered_leaves_for_handshake() [ranking]                    │
└──────────┬───────────────┬──────────────┬─────────────┬────────┘
           │               │              │             │
    ┌──────▼──────┐  ┌─────▼─────┐  ┌─────▼──────┐  ┌──▼───────┐
    │ ocsp_common │  │ ocsp_cert │  │ ocsp_store │  │ocsp_chain│
    │             │  │           │  │            │  │          │
    │ - Settings  │  │ - SPKI FP │  │ - L1 cache │  │ - Chain  │
    │ - Constants │  │ - Parse   │  │ - Metadata │  │ - Staple │
    │ - Logging   │  │ - CertID  │  │ - Fresh.   │  │ - Multi  │
    │ - Paths     │  │ - Must-S. │  │ - Ligand   │  │          │
    └─────────────┘  └───────────┘  └────────────┘  └──────────┘
           ▲               ▲              ▲              ▲
           │               │              │              │
           └──────────┬────┴──────────────┴──────────────┘
                      │
             ┌────────▼──────────┐
             │ ocsp_pin.lua       │
             │ (Allow-pin bus)    │
             │ - Peer refuse      │
             │ - Skip-validate    │
             │ - Must-Staple      │
             └────────────────────┘
                      │
             ┌────────▼──────────────────┐
             │ ocsp_must_staple.lua       │
             │ (Enforcement logic)        │
             │ - Tri-state detection     │
             │ - Fail-closed semantics   │
             └────────────────────────────┘
                      │
             ┌────────▼──────────────────┐
             │ ocsp_warmer.lua            │
             │ (Background optimization) │
             │ - L1 warming              │
             │ - Lazy deletion           │
             └────────────────────────────┘
```

---

## Data Flow: Request-Response Lifecycle

```
TLS Handshake Start
       │
       ├─ SNI resolved → site config
       │
       ├─ Leaf certificate parsed
       │
       ├─ SPKI fingerprint computed
       │
       ├─ OCSP response located (disk path)
       │
       └─→ OCSP Validation Pipeline:
           │
           ├─ [L1 Cache Lookup] ◄── /var/cache/bunkerweb/ssl/ 
           │  │ (shared dict: internalstore)
           │  │ • epoch match
           │  │ • binding SHA match
           │  │ • generation match
           │  └─ HIT? → attach & return ✓
           │  └─ MISS → continue
           │
           ├─ [Metadata Validation] ◄── ocsp.json (shard)
           │  │ • freshness check (thisUpdate/nextUpdate)
           │  │ • tombstone check (revoked?)
           │  │ • serial blacklist check (CRL)
           │  │ • cluster floor consensus (expiry agreement)
           │  └─ FAIL? → skip staple & return
           │
           ├─ [Skip-Validate Gate] ◄── mode + Must-Staple
           │  │ • mode=open → skip FFI
           │  │ • Must-Staple=false → skip FFI
           │  │ • Unknown/true → continue
           │  └─ SKIP? → attach speculatively & return
           │
           ├─ [Canary-Paged Check] ◄── ocsp-ligand/ + generation
           │  │ • paged + gen match + DER SHA match?
           │  └─ PASS? → trust & attach & return
           │
           ├─ [FFI Validation] ◄── ngx.ocsp.validate_ocsp_response
           │  │ • Build issuer list (shard pin + chain)
           │  │ • For each issuer (max 10, dedupe by SPKI):
           │  │   ├─ validate() → FFI crypto verify
           │  │   └─ PASS? → attach & return
           │  │ • Budget exceeded? → skip & return
           │  │ • All issuers fail? → return failure
           │  └─
           │
           └─ Attach Decision → log outcome

       │
       └─ TLS handshake continues
          Client receives cert ± OCSP staple
```

---

## Cache Hierarchy

```
┌────────────────────────────────────────────────────────────────┐
│                     OCSP Caching Layers                        │
└────────────────────────────────────────────────────────────────┘

┌─ L0: Per-Request (Tier 1, Critical Path) ──────────────────┐
│                                                            │
│  ngx.ctx.bw_ocsp_der_cache                               │
│  ├─ PEM → DER parsing cache                              │
│  ├─ Key: "leaf_spki|issuer_spki"                         │
│  ├─ TTL: single request                                  │
│  └─ Performance: <0.1ms (memory)                          │
│                                                            │
│  ngx.ctx.bw_ffi_validation_cache                         │
│  ├─ FFI validation result cache                          │
│  ├─ Key: "der_sha|issuer_spki"                           │
│  ├─ TTL: single request                                  │
│  └─ Performance: <0.1ms (memory)                          │
│                                                            │
└────────────────────────────────────────────────────────────┘

┌─ L1: Shared Dict (Tier 1, Worker Cache) ──────────────────┐
│                                                            │
│  ngx.shared.internalstore (HTTP)                         │
│  ngx.shared.internalstore_stream (stream)                │
│  ├─ Format: "bw3\0" + epoch + binding + gen + DER       │
│  ├─ Key: "OCSP:RESPONSE:" + fingerprint                  │
│  ├─ TTL: 300s (min of response lifetime + 300s)          │
│  ├─ Size: ~1-50KB per cert                               │
│  └─ Performance: 0.1-1ms (shared memory)                  │
│                                                            │
│  Epoch Coherence Bus:                                     │
│  ├─ ".ocsp_epoch" → global version                       │
│  ├─ Job bumps on cert rotation                           │
│  └─ Cache auto-invalidates on generation mismatch        │
│                                                            │
└────────────────────────────────────────────────────────────┘

┌─ L2: Disk Metadata (Tier 2, Durable) ────────────────────┐
│                                                            │
│  /var/cache/bunkerweb/ssl/{h}/{l}/{fp}/ocsp.json        │
│  ├─ JSON metadata (SPKI, DER SHA, gen, expires, etc.)   │
│  ├─ Updated by scheduler (ocsp-refresh.py)              │
│  ├─ TTL: job-maintained (until response expires)        │
│  └─ Performance: 1-5ms (disk read + JSON parse)          │
│                                                            │
│  /var/cache/bunkerweb/ssl/{h}/{l}/{fp}/ocsp.der        │
│  ├─ DER-encoded OCSP response                           │
│  ├─ Binary format                                        │
│  ├─ Updated by scheduler                                │
│  └─ Performance: 2-5ms (disk read)                       │
│                                                            │
└────────────────────────────────────────────────────────────┘

┌─ L3: Outside-Ligand (Tier 2.5, Paged) ──────────────────┐
│                                                            │
│  /var/cache/bunkerweb/ssl/ocsp-ligand/{fp}              │
│  ├─ Canary-paged copy (atomic promotion)                │
│  ├─ DER SHA + soft_recall_gen binding                   │
│  ├─ Updated atomically by scheduler                     │
│  ├─ TTL: response lifetime                              │
│  └─ Performance: 1-2ms (disk read, trusted if paged)    │
│                                                            │
└────────────────────────────────────────────────────────────┘

┌─ L4: Consensus Blocks (Cluster Coordination) ────────────┐
│                                                            │
│  /var/cache/bunkerweb/ssl/ocsp-floor/{fp}               │
│  ├─ Cluster-wide expiry consensus (MIN function)        │
│  ├─ Prevents one node's old OCSP from exceeding others  │
│  ├─ Updated by scheduler (after consensus read)         │
│  └─ Performance: 1-2ms (disk read)                       │
│                                                            │
│  /var/cache/bunkerweb/ssl/serial-blacklist.json         │
│  ├─ Revoked serial numbers (CRL-like)                   │
│  ├─ Cluster-sourced (all nodes publish revokes)         │
│  └─ Performance: 1-2ms (disk read)                       │
│                                                            │
└────────────────────────────────────────────────────────────┘

                    Cache Hit Progression:
                    ┌──────────────────────┐
                    │ Per-request cache    │ < 0.1ms
                    │ (fastest)            │
                    └──────┬───────────────┘
                           │ MISS
                    ┌──────▼───────────────┐
                    │ L1 shared dict       │ 0.1-1ms
                    │ (worker-level)       │
                    └──────┬───────────────┘
                           │ MISS
                    ┌──────▼───────────────┐
                    │ L2+ disk metadata    │ 1-5ms
                    │ (persistent)         │
                    └──────┬───────────────┘
                           │ MISS or EXPIRE
                    ┌──────▼───────────────┐
                    │ Tier 3: FFI          │ 10-20ms
                    │ (expensive)          │
                    └──────────────────────┘
```

---

## Key State Machines

### State Machine 1: OCSP Validation Status (Per-Cert)

```
┌────────────────────────────────────┐
│ NONE (not started)                 │
└──────────────┬──────────────────────┘
               │ TLS path detects need
               ▼
┌────────────────────────────────────┐
│ PENDING (queued to async job)       │ TTL: 120s
│ mark_async_validation_pending()     │
└──────────────┬──────────────────────┘
               │ (async job runs in parallel)
               ├─ Job validates (FFI) ──→ SUCCESS
               │                        → VALIDATED (gen-bound)
               │                        → TTL: 3600s
               │
               └─ Job validates (FFI) ──→ FAILURE
                                      → FAILED (gen-bound)
                                      → TTL: 3600s

┌────────────────────────────────────┐
│ VALIDATED (crypto confirmed)        │
│ TLS skips FFI, uses cached result   │
└────────────────────────────────────┘

┌────────────────────────────────────┐
│ FAILED (crypto failed)              │
│ TLS attempts local FFI              │
└────────────────────────────────────┘

Soft-Recall (Cert Rotation):
┌────────────────────────────────────┐
│ ANY STATE → NONE                    │
│ (soft_recall_gen increments)        │
│ (generation mismatch clears status) │
└────────────────────────────────────┘
```

### State Machine 2: Leaf Selection (Must-Staple)

```
┌─────────────────────────────────────────┐
│ Multiple leaves (RSA, ECDSA, EdDSA...)   │
└────────────────┬────────────────────────┘
                 │
                 ├─→ Detect Must-Staple (tri-state):
                 │   ├─ true (TLS Feature 5 or ocsp.json)
                 │   ├─ false (explicitly not required)
                 │   └─ nil (unknown, treat as true)
                 │
                 ├─→ Check ClientHello sig_algorithms:
                 │   ├─ Match leaf public key kind
                 │   ├─ Rank by fit
                 │   └─ Prefer first match
                 │
                 ├─→ Check OCSP availability:
                 │   ├─ true → must have OCSP or refuse
                 │   ├─ false → optional, staple if available
                 │   └─ nil → enforce (fail-closed)
                 │
                 ├─→ Score each leaf:
                 │   score = (must_staple_health) × 100
                 │         + (sig_alg_fit) × 10
                 │         + (preference) × 1
                 │
                 ├─→ Sort by score (descending)
                 │
                 └─→ Select first leaf (best score)

Result: Ranked array
├─ [0] Best health + sig-alg + pref
├─ [1] Good health, decent sig-alg
├─ [2] Fair, sig-alg mismatch
└─ [n] Worst, Must-Staple unprovable
```

### State Machine 3: Soft-Recall (Cert Rotation)

```
Current State:
┌───────────────────────────────────────┐
│ soft_recall_gen = N                    │
│ der_sha256 = ABC123...                 │
│ L1 cache: (binding="ABC...", gen=N)    │
│ allow-pin: (sha="ABC...", gen=N)       │
│ async_status: "validated|ABC|N" (TTL) │
└───────────────────────────────────────┘

Trigger: Cert Rotates (New DER)
       ↓ Scheduler detects new DER

Action 1: Increment generation
┌───────────────────────────────────────┐
│ soft_recall_gen = N+1                  │
│ der_sha256 = XYZ789... (NEW)           │
│ ocsp.json updated with gen=N+1        │
│ .ocsp_epoch bumped (coherence bus)    │
└───────────────────────────────────────┘

Action 2: Invalidation (implicit, no explicit delete)
┌───────────────────────────────────────┐
│ Old L1 entry:                          │
│   check: gen=N in storage              │
│   check: current_gen=N+1               │
│   result: MISMATCH → skip & evict     │
│                                        │
│ Old allow-pin:                         │
│   check: gen=N in pin                  │
│   check: current_gen=N+1               │
│   result: MISMATCH → not reusable     │
│                                        │
│ Old async_status:                      │
│   check: "validated|ABC|N"             │
│   check: current_gen=N+1               │
│   result: MISMATCH → not valid        │
└───────────────────────────────────────┘

Effect: Old OCSP(ABC, gen=N) never attaches to new cert ✓
Cost: None (implicit invalidation via generation mismatch)
Recovery: Scheduler fetches new OCSP with gen=N+1
```

---

## Performance Characteristics

### Latency Breakdown (TLS Handshake)

| Phase | Best | Typical | Worst |
|-------|------|---------|-------|
| **Per-Request Cache** | 0.05ms | 0.1ms | 0.2ms |
| **L1 Lookup** | 0.05ms | 0.2ms | 1ms |
| **Metadata Validation** | 0.5ms | 1ms | 2ms |
| **FFI (per issuer)** | 8ms | 15ms | 25ms |
| **Total (L1 hit)** | ~0.5ms | ~1-5ms | ~3ms |
| **Total (FFI miss)** | ~15ms | ~20-30ms | ~50ms |
| **Total (async done)** | ~0.5ms | ~1-2ms | ~3ms |

### Memory Usage

| Component | Per-Cert | 100 Certs | Notes |
|-----------|----------|-----------|-------|
| **L1 Cache** | 1-50KB | 100KB-5MB | Shared dict |
| **DER Cache** | 2-5KB | 200KB-500KB | Per-request |
| **PEM Memo** | 1-2KB | 100-200KB | Per-worker, max 512 |
| **Chain Cache** | 5-20KB | 500KB-2MB | Per-request |
| **Total DRAM** | ~10-75KB | ~1-8MB | 8-16 workers: 8-128MB |

### Throughput

| Workload | L1 Hit | FFI Miss | Async Warm |
|----------|--------|----------|-----------|
| **Handshakes/sec** | 1000+ | 30-50 | 500+ |
| **Avg Latency** | <2ms | 20-30ms | <3ms |
| **p99 Latency** | <5ms | 40-50ms | <5ms |

---

## Integration Points

### HTTP Subsystem Integration (ocsp_http.lua)

```
nginx.conf:
  lua_ssl_certificate_by_lua_block {
    local ocsp = require("bunkerweb.ocsp_http")
    ocsp.http_ssl_certificate()
  }

Data Flow:
  ClientHello (SNI, sig_algorithms)
    ↓
  GET /variables (datastore)
  ├─ site config (SSL_CERTIFICATE, SSL_CERTIFICATE_KEY, ...)
  └─ OCSP settings (SSL_USE_OCSP_STAPLING, ...)
    ↓
  ocsp._M.set_certs_from_pem(...)
    ↓
  TLS response + OCSP staple
```

### Stream (SSL) Subsystem (stream/ocsp.lua)

```
nginx.conf:
  stream {
    ssl_certificate_by_lua_block {
      local ocsp = require("bunkerweb.stream.ocsp")
      ocsp.stream_ssl_certificate()
    }
  }

Data Flow:
  TLS ClientHello
    ↓
  stream_ocsp (similar flow, stream-specific hooks)
    ↓
  TLS response + OCSP staple
```

### Background Job (ocsp-refresh.py)

```
Scheduler (Python):
  Every 60 seconds:
    ├─ For each cert fingerprint:
    │   ├─ Read ocsp.json metadata
    │   ├─ Check if needs refresh (20% TTL threshold)
    │   ├─ Fetch from responder (AIA URL)
    │   ├─ Call ocsp._M.async_validate_response()
    │   ├─ warm_cache() → L1 shared dict
    │   └─ Update ocsp.json
    │
    └─ Check for soft-recall
        └─ If new cert detected:
           ├─ Increment soft_recall_gen
           └─ Publish to TLS path (.ocsp_epoch)
```

---

## Security Guarantees

### Guarantee 1: No Stale OCSP After Cert Rotation

**Mechanism:** Soft-recall generation tuples

**Proof:**
- Gen increments on cert rotation
- L1 cache checks: binding AND gen match
- Old gen ≠ new gen → cache miss
- Old OCSP never attaches to new cert ✓

### Guarantee 2: Issuer PIN Prevents Wrong Cert Issuer

**Mechanism:** SPKI fingerprinting

**Proof:**
- If issuer.pem present: shard pin enforced
- issuer_candidates() filters by SPKI
- Wrong issuer SPKI rejected
- Cross-signed cert cannot bypass pin ✓

### Guarantee 3: Must-Staple Enforcement

**Mechanism:** Tri-state detection + fail-closed

**Proof:**
- Unknown (nil) treated as true (enforce)
- TLS Feature 5 + ocsp.json checked
- Missing OCSP refused (fail-closed)
- No speculative attach without OCSP ✓

### Guarantee 4: Cross-Handshake Sharing Safe

**Mechanism:** Generation-bound validation state

**Proof:**
- Shared result keyed by (FP, DER_SHA, gen)
- Soft-recall invalidates old results (gen mismatch)
- First validator's result reused by peers
- No cross-cert contamination ✓

### Guarantee 5: Cluster Consensus Prevents Stale

**Mechanism:** ocsp-floor consensus

**Proof:**
- MIN(expiry) across all nodes
- One node's old OCSP cannot exceed consensus
- All nodes converge on same expiry
- Cluster prevents holdout staleness ✓

---

## Operational Runbook

### Incident: Staples Not Attaching

**Diagnosis:**
1. Check decision codes in logs: `grep "OCSP_SKIP\|OCSP_REFUSE" logs`
2. Decision = `response_not_found` → OCSP response missing (see below)
3. Decision = `must_staple_refuse` → enforcement + missing OCSP
4. Decision = `validate_exhausted` → all issuers failed FFI

**Response:**
- `response_not_found`: Wait for scheduler (60s), check responder
- `must_staple_refuse`: Set `SSL_USE_OCSP_STAPLING_MODE=open`
- `validate_exhausted`: Check issuer.pem, add to shard

---

### Incident: Slow Handshakes (50ms+)

**Diagnosis:**
1. Check metric: `grep "ffi_validate_ms" logs`
2. If >20ms: FFI running in TLS path (async not warmed)
3. Check: `grep "ASYNC_VALIDATE\|async_validation_pending" logs`

**Response:**
- Wait for async validation to warm (60s cycle)
- Check scheduler health: `systemctl status bunkerweb-scheduler`
- Monitor CPU: FFI may be slow under load

---

### Incident: Certificate Rotation Fails

**Diagnosis:**
1. Check logs: `grep "soft-recall\|soft_recall_gen" logs`
2. Check ocsp.json gen: `cat /var/cache/bunkerweb/ssl/??/??/{fp}/ocsp.json`

**Response:**
- Soft-recall is expected (not an error)
- Generation increment is normal behavior
- Old OCSP intentionally rejected (safety feature)
- Wait 60s for scheduler to validate new OCSP

---

### Incident: Must-Staple Refusing Connections

**Diagnosis:**
1. Check decision: `grep "MUST_STAPLE_REFUSE" logs`
2. Verify cert has TLS Feature 5: `openssl x509 -text -noout < cert.pem | grep -A2 "TLS Feature"`

**Response:**
- **Option A (Production):** Fix OCSP responder availability
- **Option B (Temporary):** Set `SSL_USE_OCSP_STAPLING_MODE=open`
- **Option C (Permanent):** Remove TLS Feature 5 from cert

---

## Summary: Core Design Principles

1. **Fail-Closed:** Unknown state → enforce strict policy
2. **Generation Tuples:** Implicit invalidation on cert rotation
3. **Two-Tier Validation:** Cached path (TLS critical) + async path (background)
4. **Budget Guards:** 50ms hardcap prevents latency cascade
5. **Weak-Map Memoization:** Auto-invalidates on config reload
6. **Lazy Deletion:** No explicit cleanup, implicit via generation/epoch
7. **Cluster Consensus:** Min function prevents holdout staleness
8. **Error Boundaries:** All OCSP calls wrapped in pcall()
9. **Cross-Subsystem Pins:** Allow-pin bus coordinates HTTP ↔ stream
10. **Observability:** Structured logging with decision codes

