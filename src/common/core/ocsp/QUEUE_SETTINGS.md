# OCSP Redis Queue Configuration Guide

Complete reference for persistent OCSP validation queue settings.

## Overview

The OCSP queue manages certificate validation with:
- **Persistent storage** (Redis) that survives crashes
- **Responder health tracking** with exponential backoff
- **Rate limiting** to prevent startup DDOS
- **429 handling** to respect responder rate limits

---

## Queue TTL Settings

Control how long entries stay in Redis before auto-expiration.

### OCSP_QUEUE_TTL_PENDING
**Default:** `86400` (1 day)  
**Type:** Integer (seconds)  
**Range:** 3600 - 604800 (1 hour - 7 days recommended)

Time to keep pending validations in queue before expiring.

**Purpose:**
- Prevent queue from growing indefinitely
- Auto-cleanup for entries that couldn't be validated
- Aligned with 7-day certificate rotation cycle

**When to adjust:**
- **Shorter** (e.g., 3600 = 1 hour): Quick cleanup, retry new certs faster
- **Longer** (e.g., 259200 = 3 days): More patience before giving up

**Example:**
```bash
OCSP_QUEUE_TTL_PENDING=172800  # 2 days instead of 1
```

---

### OCSP_QUEUE_TTL_VALIDATED
**Default:** `604800` (7 days)  
**Type:** Integer (seconds)  
**Range:** 86400 - 2592000 (1-30 days)

Time to keep validated OCSP responses in cache.

**Purpose:**
- Cache validated responses for reuse
- Matches 7-day certificate lifetime
- Auto-expires when cert rotates

**When to adjust:**
- **Shorter** (e.g., 259200 = 3 days): Frequent re-validation, uses more responder resources
- **Longer** (e.g., 1209600 = 14 days): Less responder load, but less fresh data

**Example:**
```bash
OCSP_QUEUE_TTL_VALIDATED=259200  # 3 days for more frequent validation
```

---

### OCSP_QUEUE_TTL_FAILED
**Default:** `86400` (24 hours)  
**Type:** Integer (seconds)  
**Range:** 3600 - 604800 (1 hour - 7 days)

Time to keep failed validation entries before retry.

**Purpose:**
- Prevent retry spam when responder has issues
- Allow recovery time (usually transient issues resolve in hours)
- Auto-cleanup of old failures

**When to adjust:**
- **Shorter** (e.g., 3600 = 1 hour): Aggressive retries (for reliable responders)
- **Longer** (e.g., 604800 = 7 days): Conservative (for flaky responders)

**Example:**
```bash
OCSP_QUEUE_TTL_FAILED=3600  # Retry after 1 hour instead of 24
```

---

### OCSP_QUEUE_TTL_PROCESSING
**Default:** `3600` (1 hour)  
**Type:** Integer (seconds)  
**Range:** 300 - 3600 (5 minutes - 1 hour)

Time to keep "in-progress" entries before considering them stale.

**Purpose:**
- Detect jobs that crash mid-validation
- Prevent entries from getting stuck forever
- Safety valve for stale processing locks

**When to adjust:**
- **Shorter** (e.g., 600 = 10 min): Faster stale detection, but risky if validation takes long
- **Longer** (e.g., 7200 = 2 hours): Patience for slow operations, but longer recovery

**Example:**
```bash
OCSP_QUEUE_TTL_PROCESSING=1800  # 30 minutes (longer validation timeout)
```

---

## Responder Health Settings

Track OCSP responder health and implement exponential backoff for failures.

### OCSP_RESPONDER_RETRY_INITIAL
**Default:** `300` (5 minutes)  
**Type:** Integer (seconds)  
**Range:** 60 - 3600 (1 minute - 1 hour)

Initial backoff interval when responder fails.

**Purpose:**
- First retry delay for transient failures
- Base for exponential backoff calculation
- Prevents hammering a temporarily-down responder

**Backoff sequence:**
```
Attempt 1 fails → Wait 5 min (INITIAL)
Attempt 2 fails → Wait 10 min (5 × 2^1)
Attempt 3 fails → Wait 20 min (5 × 2^2)
Attempt 4 fails → Wait 40 min (5 × 2^3)
...capped at MAX
```

**When to adjust:**
- **Shorter** (e.g., 60 = 1 min): Aggressive retries (for reliable responders)
- **Longer** (e.g., 900 = 15 min): Conservative (for flaky networks)

**Example:**
```bash
OCSP_RESPONDER_RETRY_INITIAL=60  # Retry sooner (1 min instead of 5)
```

---

### OCSP_RESPONDER_RETRY_MAX
**Default:** `86400` (24 hours)  
**Type:** Integer (seconds)  
**Range:** 3600 - 604800 (1 hour - 7 days)

Maximum backoff interval (prevents infinite exponential growth).

**Purpose:**
- Cap exponential backoff at reasonable limit
- Ensure eventual retry even after many failures
- Prevent entries from being abandoned forever

**When to adjust:**
- **Shorter** (e.g., 14400 = 4 hours): Give up sooner on broken responder
- **Longer** (e.g., 604800 = 7 days): Wait longer before retry

**Example:**
```bash
OCSP_RESPONDER_RETRY_MAX=14400  # Max 4 hours instead of 24
```

---

## Rate Limiting & Throttling Settings

Prevent startup DDOS when validating many pending certificates.

### OCSP_BATCH_SIZE
**Default:** `10`  
**Type:** Integer (certs per cycle)  
**Range:** 1 - 100

Number of OCSP validations to process per job cycle (1 minute).

**Purpose:**
- Prevent overwhelming responder on startup
- Spread out validation load over time
- Gentle warmup instead of thundering herd

**Calculation:** Time to validate N certs = (N / BATCH_SIZE) minutes

**Examples:**
```
BATCH_SIZE=10:   1000 certs → 100 minutes warmup
BATCH_SIZE=50:   1000 certs → 20 minutes warmup
BATCH_SIZE=1:    1000 certs → 1000 minutes warmup (very slow)
```

**When to adjust:**
- **Smaller** (e.g., 5): Slower warmup, less responder load
- **Larger** (e.g., 50): Faster warmup, more responder load

**Recommended by responder capacity:**
```bash
# Reliable, high-capacity responder (>1000 req/s available)
OCSP_BATCH_SIZE=50

# Medium responder (~100-500 req/s available)
OCSP_BATCH_SIZE=20

# Low-capacity or shared responder (<100 req/s)
OCSP_BATCH_SIZE=5

# Very constrained (testing, shared OCSP)
OCSP_BATCH_SIZE=1
```

---

### OCSP_REQUEST_RATE_LIMIT
**Default:** `50`  
**Type:** Integer (requests per second)  
**Range:** 1 - 1000

Maximum request rate to OCSP responder.

**Purpose:**
- Don't hammer responder even within a batch
- Spread requests evenly over time
- Respect responder's published rate limits

**Timing per request:** 1000ms / RATE_LIMIT = delay between requests

**Examples:**
```
RATE_LIMIT=50:  1000/50 = 20ms between requests (gentle)
RATE_LIMIT=200: 1000/200 = 5ms between requests (faster)
RATE_LIMIT=1:   1000/1 = 1000ms between requests (very slow)
```

**When to adjust:**
- **Lower** (e.g., 10): Respect responder's published limits (e.g., "10 req/sec")
- **Higher** (e.g., 200): Take advantage of high-capacity responders

**Responder rate limits (typical):**
```bash
# Public Let's Encrypt OCSP (~1000 req/s)
OCSP_REQUEST_RATE_LIMIT=100  # Conservative: use 100/1000 capacity

# Corporate OCSP (~100 req/s)
OCSP_REQUEST_RATE_LIMIT=50   # Conservative: use 50/100 capacity

# Shared/testing OCSP (~10 req/s)
OCSP_REQUEST_RATE_LIMIT=5    # Conservative: use 5/10 capacity
```

---

### OCSP_RATE_LIMIT_JITTER
**Default:** `20`  
**Type:** Integer (0-100, percent variation)  
**Range:** 0 - 100

Randomize delays to prevent thundering herd.

**Purpose:**
- Spread requests across time instead of synchronized burst
- Prevent multiple instances from hammering responder at same time
- Natural distribution instead of perfect intervals

**Effect:** Delay randomized by ±(JITTER%)

**Examples:**
```
JITTER=0:   Exact delays (20ms, 20ms, 20ms) - synchronized
JITTER=20:  Varied delays (16-24ms) - natural spread
JITTER=50:  High variation (10-30ms) - very random
```

**When to adjust:**
- **Lower** (0-10): Predictable, consistent load (single instance)
- **Higher** (30-100): Loose spread, good for multiple instances

**Multi-instance example (3 pods):**
```bash
# All configured with JITTER=20
Pod 1: 16, 18, 21, 19, 22ms delays
Pod 2: 22, 17, 23, 18, 20ms delays
Pod 3: 19, 21, 17, 24, 18ms delays
Result: Requests spread across all instances, no spike ✓
```

---

## Complete Configuration Examples

### Example 1: Let's Encrypt (Public, High-Capacity)
```bash
# Let's Encrypt OCSP: ~1000 req/s capacity, reliable
USE_REDIS=yes
REDIS_HOST=redis
REDIS_PORT=6379

# Queues
OCSP_QUEUE_TTL_PENDING=86400      # 1 day (default)
OCSP_QUEUE_TTL_VALIDATED=604800   # 7 days (default)
OCSP_QUEUE_TTL_FAILED=86400       # 24 hours (default)

# Responder health
OCSP_RESPONDER_RETRY_INITIAL=300  # 5 min (default)
OCSP_RESPONDER_RETRY_MAX=86400    # 24 hours (default)

# Throttling (aggressive - responder can handle it)
OCSP_BATCH_SIZE=50                # 50 certs/min
OCSP_REQUEST_RATE_LIMIT=200       # 200 req/sec
OCSP_RATE_LIMIT_JITTER=20         # ±20%

# Result: 1000 certs warm up in ~20 min
```

### Example 2: Corporate OCSP (Medium, Moderate Load)
```bash
# Corporate CA OCSP: ~100 req/s capacity, shared
USE_REDIS=yes

# Queues (more conservative)
OCSP_QUEUE_TTL_PENDING=172800     # 2 days
OCSP_QUEUE_TTL_VALIDATED=604800   # 7 days
OCSP_QUEUE_TTL_FAILED=172800      # 48 hours

# Responder health (longer backoff)
OCSP_RESPONDER_RETRY_INITIAL=600  # 10 min
OCSP_RESPONDER_RETRY_MAX=86400    # 24 hours

# Throttling (moderate - be polite)
OCSP_BATCH_SIZE=20                # 20 certs/min
OCSP_REQUEST_RATE_LIMIT=50        # 50 req/sec (half capacity)
OCSP_RATE_LIMIT_JITTER=30         # ±30%

# Result: 1000 certs warm up in ~50 min
```

### Example 3: Flaky/Shared OCSP (Low Capacity, Unreliable)
```bash
# Shared/testing OCSP: ~10 req/s, unreliable
USE_REDIS=yes

# Queues (very conservative, long TTLs)
OCSP_QUEUE_TTL_PENDING=259200     # 3 days
OCSP_QUEUE_TTL_VALIDATED=604800   # 7 days
OCSP_QUEUE_TTL_FAILED=604800      # 7 days

# Responder health (very patient backoff)
OCSP_RESPONDER_RETRY_INITIAL=900  # 15 min
OCSP_RESPONDER_RETRY_MAX=604800   # 7 days

# Throttling (very gentle - don't overload)
OCSP_BATCH_SIZE=5                 # 5 certs/min
OCSP_REQUEST_RATE_LIMIT=5         # 5 req/sec (respects limit)
OCSP_RATE_LIMIT_JITTER=50         # ±50%

# Result: 1000 certs warm up in ~200 min (slow, but safe)
```

---

## Monitoring & Troubleshooting

### Check Queue Stats
```bash
redis-cli LLEN ocsp:pending
# Returns: number of certs waiting for validation

redis-cli HLEN ocsp:validated
# Returns: number of validated responses in cache

redis-cli HLEN ocsp:responder_health
# Returns: number of unhealthy responders (in backoff)
```

### Check Responder Health
```bash
redis-cli HGETALL ocsp:responder_health
# Returns: {responder_url: "last_failure_time:attempt_count", ...}

# Example output:
# "https://ocsp.ca.com"  "1695312345:3"  (3 failures, last at that time)
```

### Monitor Job Execution
```bash
# Check job runs
grep "OCSP Async Validation Job" /var/log/bunkerweb.log

# Monitor queue decrease
watch -n 60 'redis-cli LLEN ocsp:pending'
# Should decrease by ~BATCH_SIZE every minute during warmup
```

### Diagnose Startup DDOS Issue

If responder returns 429 during startup:

```bash
# 1. Check current batch size
echo $OCSP_BATCH_SIZE  # See current setting

# 2. Reduce it
OCSP_BATCH_SIZE=5      # Much slower

# 3. Or reduce rate limit
OCSP_REQUEST_RATE_LIMIT=10  # Much lower

# 4. Check if helps
redis-cli HGETALL ocsp:responder_health
# Should be empty if no longer being rate-limited
```

---

## Summary Table

| Setting | Default | Min | Max | Purpose |
|---------|---------|-----|-----|---------|
| `OCSP_QUEUE_TTL_PENDING` | 86400 | 3600 | 604800 | Pending entries expiry |
| `OCSP_QUEUE_TTL_VALIDATED` | 604800 | 86400 | 2592000 | Cache lifetime |
| `OCSP_QUEUE_TTL_FAILED` | 86400 | 3600 | 604800 | Failed retry delay |
| `OCSP_QUEUE_TTL_PROCESSING` | 3600 | 300 | 3600 | Stale detection |
| `OCSP_RESPONDER_RETRY_INITIAL` | 300 | 60 | 3600 | First backoff |
| `OCSP_RESPONDER_RETRY_MAX` | 86400 | 3600 | 604800 | Max backoff |
| `OCSP_BATCH_SIZE` | 10 | 1 | 100 | Certs/cycle |
| `OCSP_REQUEST_RATE_LIMIT` | 50 | 1 | 1000 | Max req/sec |
| `OCSP_RATE_LIMIT_JITTER` | 20 | 0 | 100 | ±% variation |

---

## Best Practices

1. **Start with defaults** — they're tuned for typical use
2. **Monitor startup** — watch `ocsp:pending` decrease during warmup
3. **Check responder health** — empty `ocsp:responder_health` = good
4. **Adjust for your responder** — know its rate limit and capacity
5. **Test changes** — verify with small number of certs first
6. **Use jitter** — important for multiple instances/pods

