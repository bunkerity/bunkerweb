# OCSP Stapling System Documentation

Complete documentation for BunkerWeb's OCSP (Online Certificate Status Protocol) stapling implementation.

## 📚 Documentation Files

### [OCSP_ARCHITECTURE_SUMMARY.md](OCSP_ARCHITECTURE_SUMMARY.md)
**High-level overview with visual diagrams** (~1,500 lines)

Start here if you're new to OCSP. Contains:
- System architecture diagram
- Module interaction graph
- Data flow visualization
- Cache hierarchy
- 3 key state machines
- Performance characteristics
- Security guarantees
- Operational runbook

**Best for:** Learning system design, architecture review, incident response

---

### [OCSP_DEEP_DOCUMENTATION.md](OCSP_DEEP_DOCUMENTATION.md)
**Complete function reference manual** (~2,000 lines)

Detailed documentation of all 130+ functions:
- Function signatures, parameters, return types
- Data structures (L1 cache, ocsp.json, state machines)
- Key concepts & design patterns
- Critical path analysis

**Best for:** Implementing features, code review, debugging specific functions

---

### [OCSP_IMPLEMENTATION_GUIDE.md](OCSP_IMPLEMENTATION_GUIDE.md)
**Deep implementation details & debugging** (~2,500 lines)

Practical guide covering:
- 4 critical logic flows (with diagrams)
- 6+ edge cases & solutions
- 8 optimization techniques
- Testing strategy (unit, integration, performance, security)
- Debugging guide with common issues & fixes
- Performance tuning knobs

**Best for:** Implementing bug fixes, performance optimization, debugging, testing

---

### [OCSP_DOCUMENTATION_INDEX.md](OCSP_DOCUMENTATION_INDEX.md)
**Navigation guide & summary** (~500 lines)

Quick reference:
- Quick navigation by task
- Coverage summary (130+ functions, 10+ structures)
- Decision code reference
- File organization by role
- Maintenance notes

**Best for:** Finding specific information, understanding documentation structure

---

## 🎯 Quick Start by Role

### I'm a new developer
1. Read: **OCSP_ARCHITECTURE_SUMMARY.md** (30 min)
2. Read: **OCSP_DEEP_DOCUMENTATION.md** (1-2 hours)
3. Code & inline comments

### I need to fix a bug
1. **OCSP_DOCUMENTATION_INDEX.md** → find function
2. **OCSP_DEEP_DOCUMENTATION.md** → function details
3. **OCSP_IMPLEMENTATION_GUIDE.md** → edge cases & debugging
4. Code

### I need to review a PR
1. **OCSP_DEEP_DOCUMENTATION.md** → verify function signatures
2. Check: generation tuples, soft-recall, caching, error boundaries
3. **OCSP_IMPLEMENTATION_GUIDE.md** → edge case coverage

### I need to optimize performance
1. **OCSP_IMPLEMENTATION_GUIDE.md** → "Optimization Details" section
2. **OCSP_ARCHITECTURE_SUMMARY.md** → performance metrics
3. Profile with: `grep "ms" logs`

### I need to debug an issue
1. **OCSP_IMPLEMENTATION_GUIDE.md** → "Debugging Guide"
2. **OCSP_IMPLEMENTATION_GUIDE.md** → "Common Issues & Fixes"
3. **OCSP_ARCHITECTURE_SUMMARY.md** → "Operational Runbook"

---

## 📊 Quick Reference

### Decision Codes (most common)

| Code | Meaning |
|------|---------|
| `ok` | Staple valid & attached ✓ |
| `stapling_off` | OCSP disabled (skip) |
| `response_not_found` | OCSP file missing (skip) |
| `must_staple_refuse` | Required but missing (refuse) |
| `validate_exhausted` | All issuers failed (refuse) |
| `validate_budget` | Timeout exceeded (skip) |

See OCSP_DEEP_DOCUMENTATION.md for all 20+ codes.

---

### Latency Targets

| Scenario | Target | Notes |
|----------|--------|-------|
| L1 cache hit | <2ms | Most handshakes |
| FFI validation | 15-20ms | Expensive operation |
| Total (cached) | <5ms | With warm L1 |
| Total (FFI miss) | 20-30ms | Cold start |
| With async warm | <2ms | Scheduler pre-validates |

See OCSP_ARCHITECTURE_SUMMARY.md → "Performance Characteristics"

---

## 📁 System Structure

```
src/common/core/ocsp/
├── plugin.json          # OCSP core module metadata
├── jobs/                # Background job (ocsp-refresh.py)
├── QUEUE_SETTINGS.md    # Queue configuration
└── docs/                # This directory
    ├── README.md        # This file
    ├── OCSP_ARCHITECTURE_SUMMARY.md
    ├── OCSP_DEEP_DOCUMENTATION.md
    ├── OCSP_IMPLEMENTATION_GUIDE.md
    └── OCSP_DOCUMENTATION_INDEX.md

src/bw/lua/bunkerweb/    # Lua implementation
├── ocsp.lua             # Central orchestrator (3,691 lines)
├── ocsp_common.lua      # Shared utilities (1,185 lines)
├── ocsp_cert.lua        # Certificate parsing (1,200 lines)
├── ocsp_store.lua       # Cache & metadata (1,685 lines)
├── ocsp_chain.lua       # Chain management (1,520 lines)
├── ocsp_pin.lua         # Cross-subsystem coordination (1,214 lines)
├── ocsp_must_staple.lua # Must-Staple enforcement (194 lines)
├── ocsp_warmer.lua      # Background warming (773 lines)
└── ocsp_http.lua        # HTTP integration (5,964 lines)

src/common/core/ssl/    # SSL core module
├── jobs/ocsp-refresh.py # Python background job

Total: 17,426 lines of production code, 6,500+ lines of documentation
```

---

## 🔑 Key Concepts

### Soft-Recall (Certificate Rotation)
When a certificate is rotated, OCSP responses for the old cert are automatically invalidated via generation tuples. No explicit cleanup needed—implicit invalidation prevents stale OCSP from attaching to new certs.

### Two-Tier Validation
1. **Tier 1 (TLS critical path):** L1 cache lookup (~0.1-1ms) + metadata validation
2. **Tier 2 (Background job):** FFI validation (~10-20ms), results cached for TLS path
3. **Tier 3 (Async):** Pre-warming for next handshakes

### Generation Tuples
State is bound to (SHA256(DER), soft_recall_gen). When cert rotates, gen increments, invalidating all cached state for old DER without explicit deletion.

### Cross-Handshake Sharing
Multiple concurrent clients for the same cert share the first handshake's validation result (60s window). Prevents thundering-herd FFI calls.

### Fail-Closed Semantics
Unknown state → enforce strict policy. Example: Must-Staple unknown → treat as required (enforced).

---

## ✅ Documentation Completeness

- [x] All 9 modules documented (ocsp_common through ocsp_http)
- [x] All 130+ public functions documented
- [x] All data structures documented
- [x] 4 critical logic flows with diagrams
- [x] 6+ edge cases with solutions
- [x] 8 optimizations explained
- [x] Testing strategy (4 types)
- [x] Debugging guide + playbooks
- [x] Performance metrics
- [x] Security guarantees (5 proven)
- [x] State machines (3 documented)
- [x] Integration points (3 documented)
- [x] Operational runbook

---

## 📞 Quick Links

- **Function Reference:** OCSP_DEEP_DOCUMENTATION.md
- **Logic Flows:** OCSP_IMPLEMENTATION_GUIDE.md → "Critical Logic Flows"
- **Edge Cases:** OCSP_IMPLEMENTATION_GUIDE.md → "Edge Cases & Error Handling"
- **Debugging:** OCSP_IMPLEMENTATION_GUIDE.md → "Debugging Guide"
- **Performance:** OCSP_ARCHITECTURE_SUMMARY.md → "Performance Characteristics"
- **Security:** OCSP_ARCHITECTURE_SUMMARY.md → "Security Guarantees"
- **Incident Response:** OCSP_ARCHITECTURE_SUMMARY.md → "Operational Runbook"

---

## 📖 Reading Guide

**Total time investment by familiarity level:**

- **Beginner (completely new):** 2-3 hours
  1. OCSP_ARCHITECTURE_SUMMARY.md (30 min)
  2. OCSP_DEEP_DOCUMENTATION.md (1-2 hours)
  3. Code + comments (30 min)

- **Intermediate (familiar with some modules):** 1-2 hours
  1. OCSP_ARCHITECTURE_SUMMARY.md (20 min)
  2. OCSP_DEEP_DOCUMENTATION.md (relevant sections, 30-60 min)
  3. Code for specific functions

- **Advanced (deep OCSP knowledge):** 30 min
  1. Quick reference check (10 min)
  2. Code + comments (20 min)

---

## 🚀 Getting Started

1. **First time here?** → Read OCSP_ARCHITECTURE_SUMMARY.md
2. **Have a task?** → Check OCSP_DOCUMENTATION_INDEX.md → "Quick Navigation by Task"
3. **Need a function?** → Search OCSP_DEEP_DOCUMENTATION.md
4. **Stuck debugging?** → OCSP_IMPLEMENTATION_GUIDE.md → "Common Issues & Fixes"

---

## 📖 Documentation by Use Case

**Choose your path based on what you need:**

```
"I'm new" 
  → Read QUICK_START.md (5 minutes)

"It's not working" 
  → Check TROUBLESHOOTING_FAQ.md (find your issue)

"I need details" 
  → Read OCSP_STAPLING_GUIDE.md (comprehensive guide)

"I want all settings" 
  → See SETTINGS_REFERENCE.md (all 20 settings documented)

"I'm developing" 
  → Check UI_ARCHITECTURE.md (code structure & extension points)
```

### UI & Configuration Documentation

- **[QUICK_START.md](QUICK_START.md)** - Get OCSP working in 5 minutes
- **[TROUBLESHOOTING_FAQ.md](TROUBLESHOOTING_FAQ.md)** - Solutions for common problems
- **[UI_PAGES.md](UI_PAGES.md)** - User guide for web interface
- **[OCSP_STAPLING_GUIDE.md](OCSP_STAPLING_GUIDE.md)** - Configuration and best practices
- **[SETTINGS_REFERENCE.md](SETTINGS_REFERENCE.md)** - All 20 settings documented
- **[UI_ARCHITECTURE.md](UI_ARCHITECTURE.md)** - Developer guide and extension points
- **[UI_DOCUMENTATION_INDEX.md](UI_DOCUMENTATION_INDEX.md)** - Navigation and quick reference

---

**Created:** 2026-09-29  
**Status:** Complete & comprehensive ✅  
**Ready for:** Production use, code review, knowledge transfer

