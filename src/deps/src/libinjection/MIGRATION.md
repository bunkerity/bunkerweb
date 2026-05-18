# Migration Guide: libinjection v3.x to v4.0

This guide helps you migrate from libinjection v3.x to v4.0, which introduces a breaking API change in error handling.

## Overview of Changes

Version 4.0 introduces a new error handling model that **prevents process termination** on parser errors. Instead of calling `abort()` when encountering invalid parser states, the library now returns an error code that your application can handle gracefully.

## What Changed

### Return Type Change

All detection functions now return `injection_result_t` enum instead of `int`:

```c
typedef enum injection_result_t {
    LIBINJECTION_RESULT_FALSE = 0,   // No injection detected (benign input)
    LIBINJECTION_RESULT_TRUE = 1,    // Injection detected
    LIBINJECTION_RESULT_ERROR = -1   // Parser error (invalid state)
} injection_result_t;
```

### Affected Functions

- `libinjection_xss()`
- `libinjection_sqli()`
- `libinjection_is_xss()`
- `libinjection_h5_next()`

### New Header File

Include the new error header:
```c
#include "libinjection_error.h"  // New in v4.0
```

## Migration Strategies

### Strategy 1: Full Migration (Recommended)

Update your code to explicitly check all three return values:

**Before (v3.x):**
```c
#include "libinjection.h"
#include "libinjection_sqli.h"

int check_input(const char *input) {
    struct libinjection_sqli_state state;
    char fingerprint[8];
    int result;
    
    libinjection_sqli_init(&state, input, strlen(input), FLAG_NONE);
    result = libinjection_is_sqli(&state);
    
    if (result) {
        log("SQLi detected: %s", state.fingerprint);
        return 1;  // Block request
    }
    
    return 0;  // Allow request
}
```

**After (v4.0):**
```c
#include "libinjection.h"
#include "libinjection_error.h"
#include "libinjection_sqli.h"

int check_input(const char *input) {
    struct libinjection_sqli_state state;
    char fingerprint[8];
    injection_result_t result;
    
    libinjection_sqli_init(&state, input, strlen(input), FLAG_NONE);
    result = libinjection_is_sqli(&state);
    
    if (result == LIBINJECTION_RESULT_ERROR) {
        log_error("Parser error - treating as suspicious");
        return 1;  // Block on error (fail-safe)
    } else if (result == LIBINJECTION_RESULT_TRUE) {
        log("SQLi detected: %s", state.fingerprint);
        return 1;  // Block request
    }
    
    return 0;  // Allow request
}
```

### Strategy 2: Minimal Migration (Quick Fix)

For quick migration with minimal code changes, treat errors as detections:

```c
injection_result_t result;

result = libinjection_sqli(input, len, fingerprint);

// Treat error as detection (fail-safe approach)
if (result == LIBINJECTION_RESULT_TRUE || result == LIBINJECTION_RESULT_ERROR) {
    // Block request
    return 1;
}

return 0;  // Allow only if LIBINJECTION_RESULT_FALSE
```

### Strategy 3: Backward Compatible Check

If you need to maintain compatibility during transition:

```c
injection_result_t result;

result = libinjection_xss(input, len);

// Old style: simple truthy check still works for detection
// but won't distinguish error from injection
if (result) {
    // Handles both LIBINJECTION_RESULT_TRUE and LIBINJECTION_RESULT_ERROR (since -1 is truthy)
    return 1;
}

return 0;
```

**Warning:** This approach treats errors as benign input when checking `!result`, which is unsafe.

## Migration by Use Case

### Web Application Firewall (WAF)

Recommended approach: **Fail-safe** - block on both detection and error.

```c
injection_result_t sqli_result = libinjection_sqli(input, len, fp);
injection_result_t xss_result = libinjection_xss(input, len);

if (sqli_result == LIBINJECTION_RESULT_TRUE || sqli_result == LIBINJECTION_RESULT_ERROR ||
    xss_result == LIBINJECTION_RESULT_TRUE || xss_result == LIBINJECTION_RESULT_ERROR) {
    
    log_security_event(input, sqli_result, xss_result);
    return HTTP_403_FORBIDDEN;
}

return HTTP_200_OK;
```

### Logging/Monitoring System

Recommended approach: **Distinguish** between detection and errors.

```c
injection_result_t result = libinjection_xss(input, len);

switch (result) {
    case LIBINJECTION_RESULT_TRUE:
        log_metric("xss.detected", 1);
        alert_security_team(input);
        break;
    
    case LIBINJECTION_RESULT_ERROR:
        log_metric("xss.parser_error", 1);
        log_error("Parser error on input: %.*s", (int)len, input);
        // Continue processing - may be benign malformed input
        break;
    
    case LIBINJECTION_RESULT_FALSE:
        log_metric("xss.clean", 1);
        break;
}
```

### Embedded System

Recommended approach: **Graceful degradation** with error recovery.

```c
injection_result_t result = libinjection_sqli(input, len, fp);

if (result == LIBINJECTION_RESULT_ERROR) {
    // Log error but don't block - keep system running
    error_count++;
    
    if (error_count > ERROR_THRESHOLD) {
        // Too many errors - may indicate attack or bug
        enter_safe_mode();
    }
    
    return ALLOW;  // Degrade gracefully
}

return (result == LIBINJECTION_RESULT_TRUE) ? BLOCK : ALLOW;
```

## Testing Your Migration

### 1. Compile-time Checks

After migration, your code should compile with the new type:

```c
injection_result_t result;  // Not 'int'
result = libinjection_xss(input, len);
```

### 2. Runtime Testing

Test with these scenarios:

```c
// Normal detection - should return LIBINJECTION_RESULT_TRUE
libinjection_xss("<script>alert(1)</script>", 28);

// Benign input - should return LIBINJECTION_RESULT_FALSE
libinjection_xss("hello world", 11);

// Edge cases that might trigger LIBINJECTION_RESULT_ERROR
libinjection_xss("", 0);  // Empty string
// Very long inputs, deeply nested structures, etc.
```

### 3. Error Handling Test

Verify your error handling:

```c
injection_result_t result = libinjection_xss(test_input, len);

assert(result == LIBINJECTION_RESULT_FALSE || 
       result == LIBINJECTION_RESULT_TRUE || 
       result == LIBINJECTION_RESULT_ERROR);  // Only valid values

// Ensure you handle all three cases
switch (result) {
    case LIBINJECTION_RESULT_FALSE: /* ... */ break;
    case LIBINJECTION_RESULT_TRUE:  /* ... */ break;
    case LIBINJECTION_RESULT_ERROR: /* ... */ break;
}
```

## Common Pitfalls

### ❌ Don't: Ignore errors

```c
// WRONG - error becomes benign
if (result == LIBINJECTION_RESULT_TRUE) {
    block();
}
// LIBINJECTION_RESULT_ERROR falls through as allowed!
```

### ✅ Do: Explicitly handle errors

```c
// CORRECT
if (result == LIBINJECTION_RESULT_ERROR) {
    handle_error();
} else if (result == LIBINJECTION_RESULT_TRUE) {
    block();
}
```

### ❌ Don't: Use simple equality for "not detected"

```c
// WRONG - error will pass this check
if (result == 0) {  // Only catches LIBINJECTION_RESULT_FALSE
    allow();
}
```

### ✅ Do: Use enum constants

```c
// CORRECT
if (result == LIBINJECTION_RESULT_FALSE) {
    allow();
}
```

## Language Bindings

### Python

The enum values are accessible as integers in the Python binding:

```python
import libinjection

result = libinjection.xss(test_input)

if result == -1:  # LIBINJECTION_RESULT_ERROR
    handle_error()
elif result == 1:  # LIBINJECTION_RESULT_TRUE
    block_request()
else:  # result == 0, LIBINJECTION_RESULT_FALSE
    allow_request()
```

### PHP

```php
<?php
$result = libinjection_xss($input);

if ($result === -1) {  // LIBINJECTION_RESULT_ERROR
    handle_error();
} elseif ($result === 1) {  // LIBINJECTION_RESULT_TRUE
    block_request();
} else {  // $result === 0, LIBINJECTION_RESULT_FALSE
    allow_request();
}
```

### Lua

```lua
local libinjection = require "libinjection"

local result = libinjection.xss(input)

if result == -1 then  -- LIBINJECTION_RESULT_ERROR
    handle_error()
elseif result == 1 then  -- LIBINJECTION_RESULT_TRUE
    block_request()
else  -- result == 0, LIBINJECTION_RESULT_FALSE
    allow_request()
end
```

## Why This Change?

### The Problem with v3.x

In v3.x, when the parser encountered an invalid state (e.g., cursor position exceeding string length), it would call `assert()` or `abort()`, immediately terminating your entire process:

```c
// v3.x behavior (REMOVED in v4.0)
assert(hs->len >= hs->pos);  // CRASH if violated
```

This was problematic for:
- **Web servers**: Malicious input could crash the server
- **Embedded systems**: Required high availability, no crashes
- **Production services**: Needed graceful degradation

### The Solution in v4.0

Parser errors now return `LIBINJECTION_RESULT_ERROR` instead of terminating:

```c
// v4.0 behavior
if (hs->len < hs->pos) {
    return LIBINJECTION_RESULT_ERROR;  // Graceful error return
}
```

Your application can now:
- Log the error for debugging
- Continue running other requests
- Implement custom error policies
- Monitor error rates

## Need Help?

- **Issues**: https://github.com/libinjection/libinjection/issues
- **Pull Request**: https://github.com/libinjection/libinjection/pull/65
- **Documentation**: See README.md for updated examples

## Checklist

Use this checklist to verify your migration:

- [ ] Updated all `int` return types to `injection_result_t`
- [ ] Added `#include "libinjection_error.h"`
- [ ] Explicitly handle `LIBINJECTION_RESULT_ERROR` in all code paths
- [ ] Updated language binding code (if applicable)
- [ ] Added tests for error conditions
- [ ] Verified fail-safe behavior (block on error in security contexts)
- [ ] Updated logging/monitoring to track error rates
- [ ] Tested with edge cases (empty strings, very long inputs, etc.)
- [ ] Reviewed all `if (result)` checks for proper error handling
- [ ] Updated internal documentation and team guidelines

---

**Version**: 4.0.0  
**Last Updated**: 2025  
**Status**: Current

