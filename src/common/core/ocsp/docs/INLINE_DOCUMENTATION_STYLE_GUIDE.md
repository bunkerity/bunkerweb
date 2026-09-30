# OCSP Inline Documentation Style Guide

**Purpose:** Standard format for adding comprehensive inline documentation to all OCSP source code

**Status:** Template ready - waiting to be applied to all functions

---

## Function Header Template

Every function (local and public `_M.*`) must have a documentation header before its definition.

### Format

```lua
-- ============================================================================
-- FUNCTION_NAME(param1, param2, param3)
-- ============================================================================
-- PURPOSE:
--   One-line summary of what this function does. Be specific about outcome.
--
-- PARAMETERS:
--   param1 (type): Description. Constraints (e.g., must be non-empty, 64 hex chars).
--   param2 (type): Description. What happens if nil/false?
--   param3 (type): Optional. Description.
--
-- RETURNS:
--   return_value (type): Description of the value.
--   OR on success: (value1, value2) if multiple returns
--   OR on error: (nil, error_message_string)
--   OR: (boolean) for true/false returns
--
-- SIDE EFFECTS:
--   - Modifies: ngx.ctx.xxx_cache, ngx.shared.bw_xxx
--   - Reads: ocsp.json from disk at ocsp_path(fingerprint)
--   - May call FFI: ngx.ocsp.validate_ocsp_response
--   - May log via: log(ngx.ERR, ...)
--   [Only include actual side effects for this function]
--
-- DESIGN NOTES:
--   - Why this approach was chosen over alternatives
--   - Key constraints or invariants (e.g., "gen must never decrease")
--   - Performance characteristics: O(n) scan, ~1-5ms typical
--   - Edge cases to watch: empty lists, nil values, malformed input
--   - Related/called functions: issuer_candidates, validate
--
-- EXAMPLE:
--   local result, err = function_name(cert_pem, issuer_pem, 3600)
--   if not result then
--     log(ngx.ERR, "Failed: " .. err)
--     return false
--   end
--   log(ngx.INFO, "Success: " .. result)
--
-- ============================================================================
local function function_name(param1, param2, param3)
  -- Implementation
end
```

---

## Inline Comments Template

For complex logic blocks (not just one-liners), use structured comments:

### Complex Algorithm

```lua
-- ────────────────────────────────────────────────────────────────────
-- [Algorithm Name]: Detailed explanation of what this block does
-- ────────────────────────────────────────────────────────────────────
-- Logic flow:
--   1. Check constraint X (reason: ...)
--   2. Iterate over list Y
--   3. Accumulate result Z
--   4. Return final value
--
local result = {}
for i, item in ipairs(list) do
  -- Condition check: skip if already seen (prevent duplicates)
  if seen[item] then
    goto continue
  end
  seen[item] = true
  
  -- Validation: item must be string, non-empty
  if type(item) ~= "string" or item == "" then
    goto continue
  end
  
  -- Fingerprint extraction: compute SPKI SHA256
  local fp = spki_fingerprint(item)
  if not fp then
    goto continue
  end
  
  result[#result + 1] = fp
  ::continue::
end
return result
```

### Conditional Branch

```lua
-- Decision: choose X vs Y based on criteria
if condition_a and condition_b then
  -- Path A: happens when X is true AND Y is true (rare case)
  -- Why: explanation of this branch's logic
  return "path_a", details
elseif condition_a then
  -- Path B: happens when X is true (common case)
  -- Why: most handshakes follow this path
  return "path_b"
else
  -- Path C: fallback (safeguard)
  -- Why: conservative default, guarantees termination
  return false, "path_c_error"
end
```

### Loop with State Machine

```lua
-- ────────────────────────────────────────────────────────────────────
-- Multi-Issuer Validation Loop with Budget Guard
-- ────────────────────────────────────────────────────────────────────
-- Walks issuer list, attempting FFI validation for each.
-- Stops early on: (1) first success, (2) budget exhaustion, (3) list end.
--
local t0 = ngx.hrtime()
for i = 1, #issuers do
  -- Budget check: prevent slow handshakes (50ms hardcap)
  local elapsed_ns = ngx.hrtime() - t0
  if elapsed_ns > OCSP_VALIDATE_BUDGET_NS then
    -- Budget exceeded: abort walk, mark FFI_NEEDED latch
    log(ngx.ERR, "OCSP validate budget exceeded at issuer " .. i)
    mark_ffi_needed(internalstore, fingerprint, meta, resp)
    return false, "validate_budget", false
  end
  
  -- Early exit: first issuer validates successfully
  if validate(ocsp, ssl, resp, leaf_pem, issuers[i], shard_issuer_spki) then
    set_shared_validation_result(fingerprint, meta, resp, true)
    return true, nil, true  -- did_ffi = true (crypto proven)
  end
end

-- Loop end: all issuers failed
return false, "validate_exhausted", false
```

### Error Handling / Edge Case

```lua
-- Edge case: response DER present, but unparseable
-- This is distinct from response_not_found (file missing)
-- Treat as irrecoverable error (fail-closed)
if type(ocsp_der) ~= "string" or ocsp_der == "" then
  log(ngx.ERR, "OCSP response DER invalid: type=" .. type(ocsp_der) .. " len=" .. #(ocsp_der or ""))
  return false, "response_invalid", "der_parse_failed"
end
```

---

## Documentation Checklist

For each function being documented, verify:

- [ ] **Function name, parameters** clearly listed
- [ ] **PURPOSE** is one specific sentence (not vague)
- [ ] **PARAMETERS** include type + constraints + what if nil
- [ ] **RETURNS** cover all possible outcomes (success, error, edge cases)
- [ ] **SIDE EFFECTS** list what gets modified/read
- [ ] **DESIGN NOTES** explain WHY (not just WHAT)
- [ ] **EXAMPLE** shows real-world usage (if not trivial)
- [ ] **Related functions** cross-referenced (e.g., "calls issuer_candidates")
- [ ] **Performance note** included (e.g., "O(n), typical 1-5ms")
- [ ] **Edge cases** called out (empty list, nil input, etc.)

---

## Function Categories & Documentation Depth

### Category 1: Critical Path Functions
**Documentation Depth:** MAXIMUM

Examples:
- `try_staple()` - core validation logic
- `validate()` - FFI wrapper
- `set_certs_from_pem()` - TLS handshake entry
- `ordered_leaves_for_handshake()` - ranking logic

**Requires:**
- Full header with all sections
- Inline comments for every logic block
- Multiple examples
- Performance analysis
- Edge case coverage

### Category 2: Cache / State Management
**Documentation Depth:** HIGH

Examples:
- `get_l1()` - cache read
- `warm_cache()` - cache write
- `get_async_validation_status()` - state check
- `mark_async_validation_done()` - state update

**Requires:**
- Full header
- State transition comments
- Side effects clearly listed
- Generation/lifecycle notes

### Category 3: Utility / Helper Functions
**Documentation Depth:** MEDIUM

Examples:
- `spki_fingerprint()` - computation
- `resp_still_fresh()` - validation gate
- `issuer_candidates()` - list building
- `certid_matches_handshake_leaf()` - verification

**Requires:**
- Full header with purpose
- Parameter constraints
- Return value description
- Related functions

### Category 4: Simple Accessors
**Documentation Depth:** BASIC

Examples:
- `leaf_pem_of()` - flexible extraction
- `leaf_fp_of()` - fingerprint getter
- `ocsp_path()` - path constant
- `current_ocsp_epoch()` - epoch getter

**Requires:**
- One-line PURPOSE
- Parameter types
- Return type
- Example (if not obvious)

---

## Cross-References

Link related functions using comment references:

```lua
-- RELATED:
--   - issuer_candidates() — builds issuer list for validation
--   - validate() — performs single issuer validation
--   - set_shared_validation_result() — caches result for peers
```

---

## Performance Annotations

Include timing notes where relevant:

```lua
-- PERFORMANCE:
--   L1 hit: <0.1ms (shared dict lookup)
--   L1 miss + FFI: 15-20ms (ngx.ocsp.validate_ocsp_response)
--   Per-request cache: <0.1ms (memory table)
--   Typical case: <5ms (cold miss) or <2ms (cache hit)
```

---

## Generation / Soft-Recall Notes

For state-related functions, document generation binding:

```lua
-- GENERATION BINDING:
--   This function returns state bound to (SHA256_DER, soft_recall_gen).
--   When cert rotates, soft_recall_gen increments.
--   Old state with mismatched gen is automatically invalid.
--   No explicit cleanup needed — implicit invalidation via generation.
```

---

## Examples: Before & After

### BEFORE (minimal documentation)

```lua
local function resp_still_fresh(ocsp_der, meta, grace_seconds)
  -- Check if response is not expired
  if not ocsp_der or not meta then
    return false
  end
  -- ... 20 lines of logic
  return true
end
```

### AFTER (comprehensive documentation)

```lua
-- ============================================================================
-- resp_still_fresh(ocsp_der, meta, grace_seconds)
-- ============================================================================
-- PURPOSE:
--   Validate OCSP response time bounds (thisUpdate, nextUpdate, intrinsic lifetime).
--   Returns true if response is fresh within tolerance, false if expired/future.
--
-- PARAMETERS:
--   ocsp_der (string): OCSP response DER bytes (required, non-empty)
--   meta (table): ocsp.json metadata containing expires_unix (optional, may improve accuracy)
--   grace_seconds (number): additional tolerance (e.g., 300 for 5min grace period)
--
-- RETURNS:
--   (boolean): true if response is fresh (not expired + valid time bounds)
--              false if response is expired, future, or invalid
--
-- SIDE EFFECTS:
--   None (read-only function)
--
-- DESIGN NOTES:
--   - Fail-closed: invalid responses return false (conservative)
--   - Time bounds validated:
--     (1) thisUpdate check: response_time >= thisUpdate - clock_skew
--     (2) nextUpdate check: now <= nextUpdate + grace_seconds
--     (3) Intrinsic lifetime: (nextUpdate - thisUpdate) <= MAX_LIFETIME (5 days)
--   - Clock skew (OCSP_CLOCK_SKEW_SECONDS=300) tolerates 5min drift
--   - Meta.expires_unix used if available (scheduler-computed for accuracy)
--   - Performance: ~0.5-1ms (DER parse + timestamp checks)
--
-- EXAMPLE:
--   local ocsp_der = read_file(ocsp_path(fingerprint))
--   local meta = read_ocsp_json(fingerprint)
--   if resp_still_fresh(ocsp_der, meta, 0) then
--     log(ngx.INFO, "OCSP response is fresh")
--   else
--     log(ngx.WARN, "OCSP response expired, need refresh")
--   end
--
-- ============================================================================
local function resp_still_fresh(ocsp_der, meta, grace_seconds)
  -- Implementation here
end
```

---

## Rolling Out Documentation

### Phase 1 (Done)
- [x] Create documentation template (this file)
- [x] Examples of before/after

### Phase 2 (Next)
- [ ] Apply to 4 critical functions:
  - [ ] `try_staple()` (ocsp.lua, ~270 lines)
  - [ ] `validate()` (ocsp.lua, ~280 lines)
  - [ ] `set_certs_from_pem()` (ocsp.lua, ~300 lines)
  - [ ] `ordered_leaves_for_handshake()` (ocsp.lua, ~100 lines)

### Phase 3 (After Phase 2)
- [ ] Apply to 10 store/cache functions (ocsp_store.lua)
- [ ] Apply to 5 chain functions (ocsp_chain.lua)
- [ ] Apply to 5 cert functions (ocsp_cert.lua)

### Phase 4 (After Phase 3)
- [ ] Apply to remaining 50+ helper/utility functions
- [ ] Verify all functions documented
- [ ] Create INDEX of all documented functions

---

## Success Criteria

✅ Every function has:
- [x] Purpose statement
- [x] Parameter documentation
- [x] Return value documentation
- [x] Related functions
- [x] Performance note

✅ Complex logic blocks have:
- [x] Multi-line comments explaining flow
- [x] Edge case notes
- [x] Design rationale

✅ Total coverage:
- [x] 100% of public functions (_M.*)
- [x] 100% of critical local functions
- [x] 95%+ of helper functions

---

## Maintenance

When updating a function:
1. Update documentation header if signature changes
2. Update example if behavior changes
3. Add inline comments if logic changes
4. Update performance notes if timing changes

Keep docs in sync with code at all times.

