# OCSP Plugin - Complete Settings Reference

## Overview

This document provides comprehensive documentation of all OCSP-related configuration variables in BunkerWeb, including global settings, per-service settings, and their usage.

**Last Updated**: 2026-09-30  
**Format Version**: 1.0

---

## Quick Index

- [Global OCSP Settings](#global-ocsp-settings)
- [Per-Service SSL/OCSP Settings](#per-service-sslocsp-settings)
- [Setting Configuration Methods](#setting-configuration-methods)
- [Configuration Precedence](#configuration-precedence)
- [Setting Examples](#setting-examples)
- [Validation Rules](#validation-rules)

---

## Quick Reference - All Settings Overview

### Global Settings (14 total)

| Setting | Type | Default | Purpose |
|---------|------|---------|---------|
| `OCSP_ASYNC_VALIDATION` | check | `yes` | Enable/disable background OCSP job |
| `OCSP_ASYNC_SCHEDULE` | select | `minute` | Job frequency (minute/5minute/hour) |
| `OCSP_BATCH_SIZE` | number | `10` | Certificates per job cycle |
| `OCSP_REQUEST_RATE_LIMIT` | number | `50` | Requests/second to OCSP responder |
| `OCSP_RATE_LIMIT_JITTER` | number | `20` | Jitter percentage (0-100%) |
| `OCSP_STAPLE_MODE` | select | `normal` | Default must-staple mode (normal/staple_only/open) |
| `OCSP_CACHE_DIR` | text | `/var/cache/bunkerweb/ocsp` | OCSP response cache directory |
| `OCSP_QUEUE_TTL_PENDING` | number | `300` | TTL for pending validations (seconds) |
| `OCSP_QUEUE_TTL_VALIDATED` | number | `86400` | TTL for validated responses (seconds) |
| `OCSP_QUEUE_TTL_FAILED` | number | `3600` | TTL for failed validations (seconds) |
| `OCSP_QUEUE_TTL_PROCESSING` | number | `600` | TTL for processing state (seconds) |
| `OCSP_RESPONDER_RETRY_INITIAL` | number | `1` | Initial retry delay (seconds) |
| `OCSP_RESPONDER_RETRY_MAX` | number | `300` | Maximum retry delay (seconds) |
| `OCSP_RATE_LIMIT_JITTER` | number | `20` | Rate limit jitter percentage |

### Per-Service Settings (6 total)

| Setting Pattern | Type | Default | Purpose |
|-----------------|------|---------|---------|
| `{SERVICE}_SSL_USE_OCSP_STAPLING` | check | `no` | Enable OCSP stapling for service |
| `{SERVICE}_OCSP_STAPLE_MODE` | select | (global) | Service-specific staple mode override |
| `{SERVICE}_SSL_MUST_STAPLE` | check | `no` | Enforce must-staple on service |
| `{SERVICE}_SSL_CERTIFICATE_PATH` | text | (auto) | Path to service certificate |
| `{SERVICE}_SSL_CERTIFICATE_KEY_PATH` | text | (auto) | Path to service private key |
| `{SERVICE}_SSL_MULTI_CERT` | check | `no` | Enable RSA/ECDSA multi-cert support |

**Note**: Replace `{SERVICE}` with actual service name (e.g., `example.com_SSL_USE_OCSP_STAPLING`)

### Settings Summary by Category

**Performance & Behavior**:
- `OCSP_ASYNC_VALIDATION` - Enable/disable job
- `OCSP_ASYNC_SCHEDULE` - Job frequency
- `OCSP_BATCH_SIZE` - Batch processing
- `OCSP_REQUEST_RATE_LIMIT` - Rate limiting
- `OCSP_RATE_LIMIT_JITTER` - Request spreading

**Cache & Storage**:
- `OCSP_CACHE_DIR` - Cache location
- `OCSP_QUEUE_TTL_*` - State TTLs (pending/validated/failed/processing)

**Retry Strategy**:
- `OCSP_RESPONDER_RETRY_INITIAL` - First retry delay
- `OCSP_RESPONDER_RETRY_MAX` - Max retry delay

**Security & Modes**:
- `OCSP_STAPLE_MODE` - Global enforcement mode
- `{SERVICE}_SSL_USE_OCSP_STAPLING` - Per-service enable/disable
- `{SERVICE}_OCSP_STAPLE_MODE` - Per-service mode override
- `{SERVICE}_SSL_MUST_STAPLE` - Must-staple enforcement

**Certificates**:
- `{SERVICE}_SSL_CERTIFICATE_PATH` - Certificate file
- `{SERVICE}_SSL_CERTIFICATE_KEY_PATH` - Key file
- `{SERVICE}_SSL_MULTI_CERT` - Multi-cert support

---

## Global OCSP Settings

Global settings apply to all services and control the OCSP job behavior, caching, and retry logic.

### OCSP_ASYNC_VALIDATION

**Purpose**: Enable or disable asynchronous OCSP validation job

| Property | Value |
|----------|-------|
| **Variable Name** | `OCSP_ASYNC_VALIDATION` |
| **Context** | global |
| **Type** | check (yes/no) |
| **Default** | yes |
| **Regex** | `^(yes\|no)$` |
| **Setting ID** | ocsp-async-validation |
| **Label** | Enable async OCSP validation |

**Description**:
Enables or disables the background OCSP validation job. When enabled, BunkerWeb runs a scheduler job that periodically fetches new OCSP responses for certificates. This reduces TLS handshake latency by validating responses asynchronously rather than on-demand.

**Behavior**:
- `yes` (enabled): Background job runs on schedule, keeps responses fresh
- `no` (disabled): No automatic validation, manual refresh only

**Performance Impact**:
- Enabled: Higher CPU/network usage, faster TLS handshakes
- Disabled: Lower resource usage, slower handshakes during validation

**Use Cases**:
- Production: Set to `yes` (default)
- Development: Can set to `no` for offline testing
- High-traffic: Keep at `yes` for best performance

**Example**:
```bash
export OCSP_ASYNC_VALIDATION=yes
```

---

### OCSP_ASYNC_SCHEDULE

**Purpose**: Control how frequently the OCSP validation job runs

| Property | Value |
|----------|-------|
| **Variable Name** | `OCSP_ASYNC_SCHEDULE` |
| **Context** | global |
| **Type** | select (dropdown) |
| **Default** | minute |
| **Regex** | `^(minute\|5minute\|hour)$` |
| **Valid Values** | minute, 5minute, hour |
| **Setting ID** | ocsp-async-schedule |
| **Label** | Async validation schedule |

**Description**:
Controls how often the background OCSP validation job runs. More frequent schedules keep responses fresher but use more resources.

**Valid Options**:

| Value | Schedule | Use Case |
|-------|----------|----------|
| `minute` | Every 1 minute | High-security, low-traffic deployments |
| `5minute` | Every 5 minutes | Balanced (default recommended) |
| `hour` | Every 1 hour | High-traffic, conservative approach |

**OCSP Response Validity**:
- OCSP responses typically valid for 7 days
- Responses refreshed at 20% into validity window (~1.4 days for 7-day responses)
- Frequent validation ensures cache hits during refresh window

**Resource Usage**:
- `minute`: Highest frequency, highest load
- `5minute`: Balanced (recommended)
- `hour`: Lowest frequency, lowest load

**Example**:
```bash
export OCSP_ASYNC_SCHEDULE=minute    # Every minute (default)
export OCSP_ASYNC_SCHEDULE=5minute   # Every 5 minutes
export OCSP_ASYNC_SCHEDULE=hour      # Every hour
```

---

### OCSP_BATCH_SIZE

**Purpose**: Number of OCSP validations to process per job cycle

| Property | Value |
|----------|-------|
| **Variable Name** | `OCSP_BATCH_SIZE` |
| **Context** | global |
| **Type** | number (integer) |
| **Default** | 10 |
| **Regex** | `^[1-9][0-9]*$` |
| **Minimum** | 1 |
| **Maximum** | No limit (practical: 100-1000) |
| **Setting ID** | ocsp-batch-size |
| **Label** | Validation batch size |

**Description**:
Controls how many certificates are validated per job cycle. Prevents overwhelming the OCSP responder at startup by spreading requests over multiple cycles.

**Trade-offs**:
- **Low values** (1-5): Conservative, slow warmup, responder-friendly
- **Medium values** (10-20): Balanced (default recommended)
- **High values** (50+): Fast warmup, higher responder load

**Formula**:
```
Time to validate all certs = (Number of certs / Batch Size) × Schedule Interval
```

**Examples**:
- 100 certs, batch 10, schedule 1min: ~10 minutes to validate all
- 100 certs, batch 50, schedule 1min: ~2 minutes to validate all

**Responder Load Impact**:
- With `OCSP_REQUEST_RATE_LIMIT=50 req/s`
- Batch 10: ~0.2 requests/s (1 cert per 5 seconds)
- Batch 50: ~1 request/s (1 cert per 1 second)

**Recommendations**:
- Small deployments (<50 certs): 5-10
- Medium deployments (50-500 certs): 10-20
- Large deployments (1000+ certs): 20-50

**Example**:
```bash
export OCSP_BATCH_SIZE=10      # Validate 10 certs per cycle (default)
export OCSP_BATCH_SIZE=5       # Conservative: 5 per cycle
export OCSP_BATCH_SIZE=50      # Aggressive: 50 per cycle
```

---

### OCSP_REQUEST_RATE_LIMIT

**Purpose**: Maximum OCSP requests per second to responder

| Property | Value |
|----------|-------|
| **Variable Name** | `OCSP_REQUEST_RATE_LIMIT` |
| **Context** | global |
| **Type** | number (integer) |
| **Default** | 50 |
| **Regex** | `^[1-9][0-9]*$` |
| **Unit** | requests/second |
| **Minimum** | 1 |
| **Maximum** | No limit (practical: 100-1000) |
| **Setting ID** | ocsp-request-rate-limit |
| **Label** | OCSP request rate limit |

**Description**:
Prevents overwhelming the OCSP responder with too many simultaneous requests. Works with `OCSP_RATE_LIMIT_JITTER` to smooth request distribution.

**Responder Impact**:
- Lower limits: More responder-friendly, slower warmup
- Higher limits: Faster warmup, more responder load

**Typical Responder Capacity**:
- Small responder: 10-50 req/s
- Medium responder: 50-200 req/s
- Large responder: 200+ req/s

**Rate Calculation**:
```
Actual rate = (Batch Size / Schedule Interval) ± Jitter
Example: 10 certs per minute = 10/60 = 0.167 req/s (well within limit)
```

**Jitter Effect**:
- `OCSP_RATE_LIMIT_JITTER=20` adds ±20% randomization
- Prevents thundering herd of synchronized requests
- Spreads load more evenly to responder

**Recommendations**:
- Public responders (Let's Encrypt OCSP): 10-30 req/s
- Private responders: 50-200 req/s
- Unknown capacity: Start conservative (20) and increase

**Example**:
```bash
export OCSP_REQUEST_RATE_LIMIT=50     # 50 requests/sec (default)
export OCSP_REQUEST_RATE_LIMIT=20     # Conservative for public responders
export OCSP_REQUEST_RATE_LIMIT=100    # Aggressive for private responders
```

---

### OCSP_RATE_LIMIT_JITTER

**Purpose**: Add randomization to request delays to prevent thundering herd

| Property | Value |
|----------|-------|
| **Variable Name** | `OCSP_RATE_LIMIT_JITTER` |
| **Context** | global |
| **Type** | number (percentage) |
| **Default** | 20 |
| **Regex** | `^[0-9]+$` |
| **Unit** | percentage (0-100) |
| **Minimum** | 0 |
| **Maximum** | 100 |
| **Setting ID** | ocsp-rate-limit-jitter |
| **Label** | Rate limit jitter |

**Description**:
Adds randomization (±X%) to request delays to prevent synchronized requests from overwhelming the responder. Works in conjunction with `OCSP_REQUEST_RATE_LIMIT`.

**Jitter Effect**:
- 0: No jitter, perfectly synchronized requests
- 20: ±20% randomization (default, recommended)
- 50: ±50% randomization (high randomization)
- 100: ±100% randomization (maximum spread)

**Example with 20% Jitter**:
```
Base delay: 1 second
With jitter: 0.8 to 1.2 seconds (±20%)
Effect: Spreads requests over time window
```

**Thundering Herd Problem**:
- Without jitter: All validations happen at same time each cycle
- With jitter: Validations spread out over time
- Result: Smoother load on responder

**Recommendations**:
- Default (20): Good balance, prevents herd
- Conservative deployments: 10-20
- High-traffic deployments: 20-50
- Disable (0): Only if request timing is critical

**Example**:
```bash
export OCSP_RATE_LIMIT_JITTER=20      # ±20% randomization (default)
export OCSP_RATE_LIMIT_JITTER=0       # No jitter, perfectly synchronized
export OCSP_RATE_LIMIT_JITTER=50      # High jitter, maximum spread
```

---

### OCSP_STAPLE_MODE

**Purpose**: Default OCSP staple mode for all services (global default)

| Property | Value |
|----------|-------|
| **Variable Name** | `OCSP_STAPLE_MODE` |
| **Context** | global |
| **Type** | select (dropdown) |
| **Default** | normal |
| **Regex** | `^(normal\|staple_only\|open)$` |
| **Valid Values** | normal, staple_only, open |
| **Setting ID** | ocsp-staple-mode |
| **Label** | OCSP staple mode |

**Description**:
Global default for how strictly to enforce OCSP must-staple requirements. Per-service settings override this global default.

**Valid Options**:

| Mode | Behavior | Use Case |
|------|----------|----------|
| `normal` | Strict: Refuse TLS if must-staple unmet | High-security, compliance |
| `staple_only` | Prefer stapled, fallback if needed | Production (balanced) |
| `open` | Disable enforcement, allow unstapled | Recovery, development |

**Mode Details**:

**normal (Strict)**
- Enforces OCSP responses for must-staple certificates
- Refuses TLS handshake if response unavailable
- Highest security posture
- May refuse connections if responder down
- Good for: Compliance-heavy environments

**staple_only (Balanced)**
- Prefers OCSP-stapled certificates
- Falls back to unstapled if no response cached
- Graceful degradation
- Won't block connections
- Good for: Production deployments

**open (Recovery)**
- Disables must-staple enforcement
- Serves unstapled if response missing
- Emergency fallback mode
- Maximum availability
- Good for: Troubleshooting, temporary recovery

**Interaction with Per-Service Settings**:
- Global: `OCSP_STAPLE_MODE=normal`
- Service override: `{SERVICE}_OCSP_STAPLE_MODE=staple_only`
- Result: Service uses staple_only, other services use normal

**Example**:
```bash
export OCSP_STAPLE_MODE=normal        # Strict enforcement (default)
export OCSP_STAPLE_MODE=staple_only   # Balanced
export OCSP_STAPLE_MODE=open          # Recovery mode
```

---

### OCSP_CACHE_DIR

**Purpose**: Directory where OCSP responses are cached

| Property | Value |
|----------|-------|
| **Variable Name** | `OCSP_CACHE_DIR` |
| **Context** | global |
| **Type** | text (file path) |
| **Default** | `/var/cache/bunkerweb/ocsp` |
| **Regex** | `^/.*$` |
| **Access** | Read/write by BunkerWeb process |
| **Setting ID** | ocsp-cache-dir |
| **Label** | OCSP cache directory |

**Description**:
File system path where OCSP responses are cached between refresh cycles. Typically set at deployment time and rarely changed.

**Directory Structure**:
```
/var/cache/bunkerweb/ocsp/
├── 0/  (16-way sharding for performance)
│   ├── cert-fingerprint-hash-1.ocsp
│   ├── cert-fingerprint-hash-2.ocsp
│   └── ...
├── 1/
│   └── ...
├── ...
└── f/
    └── ...
```

**Requirements**:
- Writable by BunkerWeb process (usually `www-data` or container user)
- Persistent between container restarts
- Sufficient disk space for OCSP responses (~1-10 KB per response)
- For 1000 certificates: ~10-100 MB typical

**Permissions**:
```bash
# Typical setup
chmod 755 /var/cache/bunkerweb/ocsp
chown www-data:www-data /var/cache/bunkerweb/ocsp
```

**Performance Notes**:
- 16-way sharding reduces directory listing time
- Only set at deployment time
- Cannot be changed at runtime
- Each service's responses cached independently

**Example**:
```bash
# In Dockerfile or docker-compose
export OCSP_CACHE_DIR=/var/cache/bunkerweb/ocsp

# Check cache contents
ls -la /var/cache/bunkerweb/ocsp/
du -sh /var/cache/bunkerweb/ocsp/
```

---

### OCSP_QUEUE_TTL_PENDING

**Purpose**: Redis TTL (Time To Live) for pending validation entries

| Property | Value |
|----------|-------|
| **Variable Name** | `OCSP_QUEUE_TTL_PENDING` |
| **Context** | global |
| **Type** | number (seconds) |
| **Default** | 86400 |
| **Regex** | `^[0-9]+$` |
| **Unit** | seconds |
| **Default Duration** | 1 day (86400s) |
| **Setting ID** | ocsp-queue-ttl-pending |
| **Label** | Pending queue TTL |

**Description**:
Redis TTL for validation queue entries in "pending" state (awaiting first validation attempt). Entries older than this are automatically expired and cleaned up.

**Queue States**:
- `pending`: Awaiting first validation
- `processing`: Currently being validated
- `validated`: Successfully validated, cached
- `failed`: Validation failed, awaiting retry

**Default Reasoning**:
- 86400 seconds = 1 day
- Aligns with certificate validity periods
- Long enough to retry failed validations
- Short enough to clean up old entries

**Typical Flow**:
1. Certificate detected → Entry created (pending)
2. Validation job runs → Entry moves to processing
3. Validation succeeds → Entry moves to validated (TTL_VALIDATED applies)
4. If not validated in 1 day → Entry expires, retry on next cycle

**Adjustment Guidelines**:
- Shorter (43200s = 12h): Aggressive cleanup, faster retry
- Default (86400s = 1d): Balanced
- Longer (604800s = 7d): Conservative, longer retry window

**Impact on Resource Usage**:
- Longer TTL: More Redis memory usage
- Shorter TTL: More cleanup cycles
- Default: ~1-5 MB per 1000 entries

**Example**:
```bash
export OCSP_QUEUE_TTL_PENDING=86400    # 1 day (default)
export OCSP_QUEUE_TTL_PENDING=43200    # 12 hours (aggressive)
export OCSP_QUEUE_TTL_PENDING=604800   # 7 days (conservative)
```

---

### OCSP_QUEUE_TTL_VALIDATED

**Purpose**: Redis TTL for successfully validated OCSP response entries

| Property | Value |
|----------|-------|
| **Variable Name** | `OCSP_QUEUE_TTL_VALIDATED` |
| **Context** | global |
| **Type** | number (seconds) |
| **Default** | 604800 |
| **Regex** | `^[0-9]+$` |
| **Unit** | seconds |
| **Default Duration** | 7 days (604800s) |
| **Setting ID** | ocsp-queue-ttl-validated |
| **Label** | Validated responses TTL |

**Description**:
Redis TTL for validation queue entries in "validated" state (successfully validated). Matches typical OCSP response validity period (7 days).

**OCSP Response Lifecycle**:
```
Created (Now)
    ↓
Valid until (Now + 7 days typical)
    ↓
Refresh before expiry (at ~1.4 days = 20% into validity)
    ↓
Refresh cycle runs → New response fetched
    ↓
Cache expires (7 days in queue) if not refreshed
```

**Default Reasoning**:
- 604800 seconds = 7 days
- Matches typical OCSP response validity (7 days)
- Allows response to remain cached through full validity
- Ensures next refresh cycle finds previous cached entry

**Refresh Window**:
- Response valid: 7 days
- Refresh attempt: At day ~1.4 (20% into validity)
- Cache retention: 7 days
- Result: Fresh responses always available

**Typical Values**:
- Conservative: 3 days (259200s) - keep responses shorter
- Default: 7 days (604800s) - match OCSP validity
- Aggressive: 14 days (1209600s) - keep cache longer

**Example**:
```bash
export OCSP_QUEUE_TTL_VALIDATED=604800  # 7 days (default, matches OCSP validity)
export OCSP_QUEUE_TTL_VALIDATED=259200  # 3 days (conservative)
export OCSP_QUEUE_TTL_VALIDATED=1209600 # 14 days (keep longer)
```

---

### OCSP_QUEUE_TTL_FAILED

**Purpose**: Redis TTL for failed validation entries

| Property | Value |
|----------|-------|
| **Variable Name** | `OCSP_QUEUE_TTL_FAILED` |
| **Context** | global |
| **Type** | number (seconds) |
| **Default** | 86400 |
| **Regex** | `^[0-9]+$` |
| **Unit** | seconds |
| **Default Duration** | 1 day (86400s) |
| **Setting ID** | ocsp-queue-ttl-failed |
| **Label** | Failed entries TTL |

**Description**:
Redis TTL for validation queue entries in "failed" state (validation attempt failed). Entries older than this are automatically retried.

**Failure Scenarios**:
- Network timeout to responder
- Responder returns error (500, 503, etc.)
- Invalid response from responder
- Certificate not found by responder

**Retry Logic**:
1. Validation attempt fails → Entry marked as failed
2. Wait for TTL_FAILED duration (1 day)
3. TTL expires → Entry removed from queue
4. Next validation cycle → Retry validation

**Exponential Backoff** (if implemented):
- First failure: Retry in 1 day
- Second failure: Retry in 2 days
- Third failure: Retry in 4 days
- Max backoff: 24 hours (cap)

**Adjustment Guidelines**:
- Shorter (3600s = 1h): Fast retry, loads responder if failing
- Default (86400s = 1d): Balanced, gives responder recovery time
- Longer (604800s = 7d): Conservative, assumes transient failures

**Impact of TTL_FAILED**:
- Too short: Hammers failing responder
- Too long: Slow recovery from transient failures
- Default: Good balance for transient network issues

**Example**:
```bash
export OCSP_QUEUE_TTL_FAILED=86400     # 1 day (default)
export OCSP_QUEUE_TTL_FAILED=3600      # 1 hour (aggressive retry)
export OCSP_QUEUE_TTL_FAILED=604800    # 7 days (conservative retry)
```

---

### OCSP_QUEUE_TTL_PROCESSING

**Purpose**: Redis TTL for entries currently being processed

| Property | Value |
|----------|-------|
| **Variable Name** | `OCSP_QUEUE_TTL_PROCESSING` |
| **Context** | global |
| **Type** | number (seconds) |
| **Default** | 3600 |
| **Regex** | `^[0-9]+$` |
| **Unit** | seconds |
| **Default Duration** | 1 hour (3600s) |
| **Setting ID** | ocsp-queue-ttl-processing |
| **Label** | Processing entries TTL |

**Description**:
Redis TTL for validation queue entries in "processing" state. Stale processing entries (validation job crashed/hung) are automatically cleaned up and requeued.

**Processing State Lifecycle**:
```
pending → [Job picks up] → processing
    ↓
[Job validates] (typically 1-10 seconds)
    ↓
validated/failed
```

**Purpose of TTL**:
- Detect crashed/hung validation jobs
- Automatically requeue stale entries
- Prevent infinite processing state
- Recover from job failures

**Stale Entry Detection**:
```
If (Current_Time - Entry_Timestamp) > TTL_PROCESSING:
    Entry marked stale → Cleanup → Requeue as pending
```

**Default Reasoning**:
- 3600 seconds = 1 hour
- Validation typically completes in seconds
- 1 hour is safe maximum for crash detection
- Won't incorrectly requeue slow validations

**Adjustment Guidelines**:
- Shorter (600s = 10min): Faster recovery from crashes
- Default (3600s = 1h): Safe default
- Longer (7200s = 2h): Conservative for very slow responders

**Impact**:
- Too short: May requeue before completion
- Too long: Slow recovery from job crashes
- Default: Good balance

**Example**:
```bash
export OCSP_QUEUE_TTL_PROCESSING=3600  # 1 hour (default)
export OCSP_QUEUE_TTL_PROCESSING=600   # 10 minutes (aggressive recovery)
export OCSP_QUEUE_TTL_PROCESSING=7200  # 2 hours (conservative)
```

---

### OCSP_RESPONDER_RETRY_INITIAL

**Purpose**: Initial retry interval when OCSP responder fails

| Property | Value |
|----------|-------|
| **Variable Name** | `OCSP_RESPONDER_RETRY_INITIAL` |
| **Context** | global |
| **Type** | number (seconds) |
| **Default** | 300 |
| **Regex** | `^[0-9]+$` |
| **Unit** | seconds |
| **Default Duration** | 5 minutes (300s) |
| **Setting ID** | ocsp-responder-retry-initial |
| **Label** | Responder retry interval |

**Description**:
Initial retry interval for OCSP responder failures. Uses exponential backoff: each failure doubles the interval until reaching max.

**Exponential Backoff Example**:
```
Initial: 300s (5 min)
1st retry failure → 600s (10 min)
2nd retry failure → 1200s (20 min)
3rd retry failure → 2400s (40 min)
... exponential growth ...
Capped at: OCSP_RESPONDER_RETRY_MAX (86400s = 24h)
```

**Responder Failure Scenarios**:
- Network timeout
- HTTP 500/503 errors
- Connection refused
- DNS resolution failure
- Invalid certificate chain

**Retry Strategy**:
1. First attempt fails
2. Wait RETRY_INITIAL (300s)
3. Second attempt
4. If fails: Wait RETRY_INITIAL × 2 (600s)
5. If fails: Wait RETRY_INITIAL × 4 (1200s)
6. ... doubles each time ...
7. Capped at RETRY_MAX (86400s)

**Adjustment Guidelines**:
- Aggressive (60s): Fast retry, higher responder load
- Default (300s = 5min): Balanced
- Conservative (900s = 15min): Slower recovery

**Example Scenarios**:
```
Scenario 1: Transient network blip
- Initial retry in 5 min
- Usually recovers on second attempt

Scenario 2: Responder under load
- Exponential backoff spreads retry attempts
- Gives responder time to recover
- Reduces cascade failures
```

**Example**:
```bash
export OCSP_RESPONDER_RETRY_INITIAL=300    # 5 minutes (default)
export OCSP_RESPONDER_RETRY_INITIAL=60     # 1 minute (aggressive)
export OCSP_RESPONDER_RETRY_INITIAL=900    # 15 minutes (conservative)
```

---

### OCSP_RESPONDER_RETRY_MAX

**Purpose**: Maximum retry interval for OCSP responder failures

| Property | Value |
|----------|-------|
| **Variable Name** | `OCSP_RESPONDER_RETRY_MAX` |
| **Context** | global |
| **Type** | number (seconds) |
| **Default** | 86400 |
| **Regex** | `^[0-9]+$` |
| **Unit** | seconds |
| **Default Duration** | 24 hours (86400s) |
| **Setting ID** | ocsp-responder-retry-max |
| **Label** | Responder retry max interval |

**Description**:
Maximum retry interval for OCSP responder failures. Caps exponential backoff to prevent infinite delays.

**Exponential Backoff Cap**:
```
Without cap:
300s → 600s → 1200s → 2400s → 4800s → 9600s ... (grows forever)

With cap (86400s):
300s → 600s → 1200s → ... → 86400s → 86400s → 86400s (stops growing)
```

**Purpose of Cap**:
- Prevent excessively long retry delays
- Ensure eventual recovery attempts
- Cap resource usage and memory

**Default Reasoning**:
- 86400 seconds = 24 hours
- Allows responder full day to recover
- Long enough for infrastructure maintenance
- Still attempts retry daily

**Relationship with RETRY_INITIAL**:
```
Initial: 300s (5 min)
After 8 failures: 300s × 2^8 = 76800s (~21.3 hours)
After 9 failures: Would be 153600s, but capped at 86400s (24 hours)
```

**Adjustment Guidelines**:
- Shorter (3600s = 1h): More aggressive retry, lower resilience
- Default (86400s = 24h): Standard, allows day for recovery
- Longer (604800s = 7d): Very conservative, full week retry

**Example**:
```bash
export OCSP_RESPONDER_RETRY_MAX=86400      # 24 hours (default)
export OCSP_RESPONDER_RETRY_MAX=3600       # 1 hour (aggressive)
export OCSP_RESPONDER_RETRY_MAX=604800     # 7 days (very conservative)
```

---

## Per-Service SSL/OCSP Settings

These settings are defined in the SSL plugin and apply per-service. Use them to customize OCSP behavior for individual services.

### SSL_USE_OCSP_STAPLING

**Purpose**: Enable or disable OCSP stapling for a specific service

| Property | Value |
|----------|-------|
| **Variable Name** | `{SERVICE}_SSL_USE_OCSP_STAPLING` |
| **Context** | multisite (per-service) |
| **Type** | check (yes/no) |
| **Default** | no |
| **Regex** | `^(yes\|no)$` |
| **Global Equivalent** | None (SSL plugin only) |
| **Setting ID** | ssl-use-ocsp-stapling |
| **Label** | Use OCSP stapling |

**Description**:
Enable or disable OCSP stapling for a specific service. Must be enabled to serve OCSP responses during TLS handshakes.

**Service Name Substitution**:
```
SERVICE placeholder is replaced with actual service/domain:
- For service "example.com": example.com_SSL_USE_OCSP_STAPLING
- For service "www.example.com": www.example.com_SSL_USE_OCSP_STAPLING
- For service "api.example.com": api.example.com_SSL_USE_OCSP_STAPLING
```

**Prerequisites**:
- Certificate must advertise OCSP responder
- OCSP responder must be reachable
- OCSP_ASYNC_VALIDATION should be enabled globally

**Certificate Requirements**:
- Must have valid OCSP URL (Authority Information Access extension)
- Let's Encrypt: Doesn't provide OCSP, use ZeroSSL
- Self-signed: Must be configured with OCSP URL
- Custom CA: Must provide OCSP responder

**Behavior When Disabled**:
- No OCSP responses served
- OCSP_STAPLE_MODE ignored (treated as "open")
- Must-staple enforcement disabled
- Clients perform own OCSP validation (if browser supports)

**Behavior When Enabled**:
- OCSP responses served in TLS handshake
- OCSP_STAPLE_MODE enforcement enabled
- Must-staple certificates strictly enforced
- Faster TLS handshakes for clients

**Example**:
```bash
# Enable for specific service
export example.com_SSL_USE_OCSP_STAPLING=yes

# Disable for specific service
export api.example.com_SSL_USE_OCSP_STAPLING=no

# Docker Compose
environment:
  - example.com_SSL_USE_OCSP_STAPLING=yes
  - api.example.com_SSL_USE_OCSP_STAPLING=no
```

---

### OCSP_STAPLE_MODE (Per-Service Override)

**Purpose**: Per-service override of OCSP staple mode

| Property | Value |
|----------|-------|
| **Variable Name** | `{SERVICE}_OCSP_STAPLE_MODE` |
| **Context** | multisite (per-service) |
| **Type** | select (dropdown) |
| **Valid Values** | normal, staple_only, open |
| **Global Default** | normal (from global OCSP_STAPLE_MODE) |
| **Setting ID** | ocsp-staple-mode |
| **Label** | OCSP staple mode |

**Description**:
Per-service override for OCSP staple mode. When set, overrides the global default for that specific service.

**Service Name Substitution**:
```
SERVICE placeholder replaced with actual service:
- For "example.com": example.com_OCSP_STAPLE_MODE
- For "api.example.com": api.example.com_OCSP_STAPLE_MODE
```

**Mode Options** (same as global):

| Mode | Behavior |
|------|----------|
| `normal` | Strict: Refuse if must-staple unmet |
| `staple_only` | Prefer stapled, fallback if needed |
| `open` | Disable enforcement, allow unstapled |

**Configuration Precedence**:
```
Per-service setting (if set)
    ↓
Global OCSP_STAPLE_MODE (fallback)
```

**Common Use Cases**:

**Global: normal, Service override: staple_only**
```
Global config: Strict for all services
Service override: One service in beta, use lenient mode
```

**Global: staple_only, Service override: normal**
```
Global config: Lenient for most services
Service override: One service requires strict compliance
```

**Example**:
```bash
# Global default
export OCSP_STAPLE_MODE=normal

# Service-specific overrides
export example.com_OCSP_STAPLE_MODE=staple_only    # Lenient for example.com
export api.example.com_OCSP_STAPLE_MODE=normal     # Strict for API

# Result:
# - example.com: Uses staple_only
# - api.example.com: Uses normal (strict)
# - Other services: Use global normal
```

---

### SSL_MUST_STAPLE

**Purpose**: Enforce must-staple for a specific service

| Property | Value |
|----------|-------|
| **Variable Name** | `{SERVICE}_SSL_MUST_STAPLE` |
| **Context** | multisite (per-service) |
| **Type** | check (yes/no) |
| **Default** | no |
| **Regex** | `^(yes\|no)$` |
| **Global Equivalent** | None (per-service only) |
| **Setting ID** | ssl-must-staple |
| **Label** | Enforce must-staple |

**Description**:
Force must-staple enforcement for a specific service. Only applies if certificate has must-staple extension.

**Service Name Substitution**:
```
SERVICE placeholder replaced:
- "example.com": example.com_SSL_MUST_STAPLE
- "api.example.com": api.example.com_SSL_MUST_STAPLE
```

**Certificate Prerequisites**:
- Certificate must have must-staple extension
- Let's Encrypt: No must-staple support (use ZeroSSL)
- ZeroSSL: Full must-staple support
- Custom CA: Depends on CA configuration

**Behavior**:
- `yes`: Must-staple strictly enforced, OCSP response required
- `no`: Must-staple optional, unstapled allowed

**Interaction with OCSP_STAPLE_MODE**:
```
OCSP_STAPLE_MODE affects how must-staple is enforced:
- normal: Refuse if unmet
- staple_only: Fallback to unstapled
- open: Disable enforcement
```

**Practical Example**:
```bash
# Certificate has must-staple extension
# Enable enforcement
export example.com_SSL_MUST_STAPLE=yes

# Result: TLS will fail if OCSP response unavailable

# Disable (allow unstapled fallback)
export example.com_SSL_MUST_STAPLE=no
```

---

### SSL_CERTIFICATE_PATH (Information Only)

**Purpose**: Path to certificate file (informational)

| Property | Value |
|----------|-------|
| **Variable Name** | `{SERVICE}_SSL_CERTIFICATE_PATH` |
| **Context** | multisite (per-service) |
| **Type** | text (file path) |
| **Example** | `/etc/letsencrypt/live/example.com/fullchain.pem` |
| **Setting ID** | ssl-certificate-path |
| **Label** | SSL certificate path |

**Description**:
Path to the SSL certificate file for this service. Used to parse certificate details for OCSP configuration.

**Used By OCSP UI**:
- Displayed in service details modal
- Used to extract certificate validity times
- Used to parse certificate OCSP responder URL

**Example**:
```bash
export example.com_SSL_CERTIFICATE_PATH=/etc/letsencrypt/live/example.com/fullchain.pem
```

---

### SSL_CERTIFICATE_KEY_PATH (Information Only)

**Purpose**: Path to certificate private key file (informational)

| Property | Value |
|----------|-------|
| **Variable Name** | `{SERVICE}_SSL_CERTIFICATE_KEY_PATH` |
| **Context** | multisite (per-service) |
| **Type** | text (file path) |
| **Example** | `/etc/letsencrypt/live/example.com/privkey.pem` |
| **Setting ID** | ssl-certificate-key-path |
| **Label** | SSL certificate key path |

**Description**:
Path to the certificate private key file. Informational only (not used by OCSP validation).

**Used By OCSP UI**:
- Displayed in service details modal
- Shows certificate key location
- Informational for troubleshooting

**Example**:
```bash
export example.com_SSL_CERTIFICATE_KEY_PATH=/etc/letsencrypt/live/example.com/privkey.pem
```

---

### SSL_MULTI_CERT

**Purpose**: Enable multiple certificates per service (e.g., RSA + ECDSA)

| Property | Value |
|----------|-------|
| **Variable Name** | `{SERVICE}_SSL_MULTI_CERT` |
| **Context** | multisite (per-service) |
| **Type** | check (yes/no) |
| **Default** | no |
| **Regex** | `^(yes\|no)$` |
| **Related** | Affects certificate handling strategy |
| **Setting ID** | ssl-multi-cert |
| **Label** | Multi-cert support |

**Description**:
Enable deployment of multiple certificates per service (e.g., RSA for older clients, ECDSA for modern clients).

**Multi-Cert Strategies**:
```
Single cert: One certificate (RSA or ECDSA)
    ↓ Client connects
    ↓ Negotiates TLS
    ↓ Receives single cert

Multi-cert: Multiple certificates available
    ↓ Client connects
    ↓ Negotiates TLS signature algorithms
    ↓ Server selects best-matching cert
    ↓ Client receives RSA or ECDSA based on preference
```

**Certificate Types**:
- RSA: Broader compatibility, larger handshake
- ECDSA: Smaller, faster, newer clients only
- Both: Maximum compatibility

**OCSP Impact**:
- Single cert: One OCSP response to cache/serve
- Multi-cert: Multiple OCSP responses (one per cert type)

**Example**:
```bash
# Enable multi-cert (RSA + ECDSA)
export example.com_SSL_MULTI_CERT=yes

# This enables:
# - RSA certificate deployment
# - ECDSA certificate deployment
# - Separate OCSP response for each

# Disable (single cert only)
export example.com_SSL_MULTI_CERT=no
```

---

## Setting Configuration Methods

### Method 1: Environment Variables

**Usage**: Set before starting BunkerWeb

```bash
# Global settings
export OCSP_ASYNC_VALIDATION=yes
export OCSP_ASYNC_SCHEDULE=minute
export OCSP_BATCH_SIZE=10

# Per-service settings
export example.com_SSL_USE_OCSP_STAPLING=yes
export example.com_OCSP_STAPLE_MODE=normal
```

**Advantages**:
- Simple for containerized deployments
- Visible in process environment
- Easy to override per deployment

**Disadvantages**:
- Requires restart to change
- All settings must be set before start
- Environment can become cluttered

### Method 2: Configuration File

**Usage**: Pre-baked configuration file

```bash
# /etc/bunkerweb/env
OCSP_ASYNC_VALIDATION=yes
OCSP_ASYNC_SCHEDULE=minute
OCSP_BATCH_SIZE=10
example.com_SSL_USE_OCSP_STAPLING=yes
```

**Advantages**:
- Organized, readable configuration
- Easy to version control
- Can be templated

**Disadvantages**:
- Still requires restart to change
- Must manage file distribution

### Method 3: Docker Compose

**Usage**: Configuration in docker-compose.yml

```yaml
environment:
  # Global settings
  - OCSP_ASYNC_VALIDATION=yes
  - OCSP_ASYNC_SCHEDULE=minute
  - OCSP_BATCH_SIZE=10
  
  # Per-service settings
  - example.com_SSL_USE_OCSP_STAPLING=yes
  - example.com_OCSP_STAPLE_MODE=normal
```

**Advantages**:
- Declarative configuration
- Easy to version control
- Self-documenting

**Disadvantages**:
- Requires container restart to change

### Method 4: Kubernetes

**Usage**: ConfigMap for configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: bunkerweb-config
data:
  OCSP_ASYNC_VALIDATION: "yes"
  OCSP_ASYNC_SCHEDULE: "minute"
  OCSP_BATCH_SIZE: "10"
  example.com_SSL_USE_OCSP_STAPLING: "yes"
```

**Advantages**:
- Native Kubernetes configuration
- Easy to manage across cluster
- Supports hot-reload (with ConfigMap watchers)

### Method 5: OCSP UI

**Usage**: Web interface configuration (future)

- Navigate to `/ocsp/settings`
- Configure global and per-service settings
- Changes saved to database
- Some settings require restart (marked)

**Status**: Currently UI reads settings, save functionality in development

---

## Configuration Precedence

Configuration values are resolved in this order (highest to lowest priority):

```
1. Per-service environment variable (e.g., example.com_SSL_USE_OCSP_STAPLING)
2. Global environment variable (e.g., OCSP_ASYNC_VALIDATION)
3. Database configuration (from BunkerWeb database)
4. Default value from plugin.json
```

**Example Resolution**:
```
Setting: OCSP_ASYNC_VALIDATION for service "example.com"

Check 1: example.com_OCSP_ASYNC_VALIDATION env var?
         No → Continue

Check 2: OCSP_ASYNC_VALIDATION env var?
         Yes → Use value = "yes"
         
Result: example.com uses value "yes" from global setting
```

---

## Setting Examples

### Example 1: Recommended Production Configuration

```bash
# Global OCSP settings
export OCSP_ASYNC_VALIDATION=yes
export OCSP_ASYNC_SCHEDULE=minute
export OCSP_STAPLE_MODE=normal
export OCSP_BATCH_SIZE=10
export OCSP_REQUEST_RATE_LIMIT=50
export OCSP_RATE_LIMIT_JITTER=20

# Per-service: Enable OCSP stapling
export example.com_SSL_USE_OCSP_STAPLING=yes
export www.example.com_SSL_USE_OCSP_STAPLING=yes
export api.example.com_SSL_USE_OCSP_STAPLING=yes
```

**Result**:
- All services use OCSP stapling
- Responses validated every minute
- Strict must-staple enforcement
- Balanced batch size and rate limiting

### Example 2: High-Traffic Configuration

```bash
# Global: Conservative job settings
export OCSP_ASYNC_VALIDATION=yes
export OCSP_ASYNC_SCHEDULE=5minute      # Every 5 min instead of 1 min
export OCSP_STAPLE_MODE=staple_only     # Graceful fallback
export OCSP_BATCH_SIZE=50               # Faster warmup
export OCSP_REQUEST_RATE_LIMIT=100      # Higher limit

# Per-service: Mixed configuration
export example.com_SSL_USE_OCSP_STAPLING=yes
export example.com_OCSP_STAPLE_MODE=staple_only

export api.example.com_SSL_USE_OCSP_STAPLING=yes
export api.example.com_OCSP_STAPLE_MODE=normal  # Override to strict
```

**Result**:
- Less frequent validation (5 min)
- Higher batch size (faster)
- Graceful fallback for most services
- Strict enforcement for API only

### Example 3: Development/Testing Configuration

```bash
# Global: Disable automatic validation
export OCSP_ASYNC_VALIDATION=no
export OCSP_STAPLE_MODE=open

# Per-service: No OCSP stapling
export example.com_SSL_USE_OCSP_STAPLING=no
```

**Result**:
- No background OCSP job
- No must-staple enforcement
- Easier testing without OCSP responder
- Manual refresh only

---

## Validation Rules

Each setting has a regex pattern for validation.

### OCSP_ASYNC_VALIDATION

**Regex**: `^(yes|no)$`  
**Valid Values**: yes, no  
**Invalid Examples**: YES, Yes, true, 1

### OCSP_ASYNC_SCHEDULE

**Regex**: `^(minute|5minute|hour)$`  
**Valid Values**: minute, 5minute, hour  
**Invalid Examples**: 1minute, 10minute, hourly

### OCSP_BATCH_SIZE

**Regex**: `^[1-9][0-9]*$`  
**Valid Values**: 1, 5, 10, 20, 100, 1000  
**Invalid Examples**: 0, -5, 10.5, abc

### OCSP_REQUEST_RATE_LIMIT

**Regex**: `^[1-9][0-9]*$`  
**Valid Values**: 1, 10, 50, 100, 500  
**Invalid Examples**: 0, -50, 50.5, unlimited

### OCSP_RATE_LIMIT_JITTER

**Regex**: `^[0-9]+$`  
**Valid Values**: 0, 5, 10, 20, 50, 100  
**Invalid Examples**: -20, 150, 20.5, yes

### OCSP_STAPLE_MODE

**Regex**: `^(normal|staple_only|open)$`  
**Valid Values**: normal, staple_only, open  
**Invalid Examples**: strict, lenient, normal_strict

### OCSP_CACHE_DIR

**Regex**: `^/.*$`  
**Valid Values**: /var/cache/bunkerweb/ocsp, /opt/ocsp/cache  
**Invalid Examples**: var/cache/bunkerweb/ocsp, ./ocsp, C:\ocsp

### Queue TTL Settings

**Regex**: `^[0-9]+$`  
**Valid Values**: 3600, 86400, 604800, 0 (disabled)  
**Invalid Examples**: -86400, 1hour, 86400s

### Retry Settings

**Regex**: `^[0-9]+$`  
**Valid Values**: 60, 300, 900, 3600, 86400  
**Invalid Examples**: -300, 5minutes, unlimited

### Per-Service Settings

**Regex**: Same as global equivalents  
**Valid Examples**:
- `example.com_SSL_USE_OCSP_STAPLING=yes`
- `api.example.com_OCSP_STAPLE_MODE=normal`
- `www.example.com_SSL_MUST_STAPLE=no`

**Invalid Examples**:
- `example.com_SSL_USE_OCSP_STAPLING=YES` (case-sensitive)
- `api.example_com_OCSP_STAPLE_MODE=normal` (wrong separator)

---

## See Also

- [UI_PAGES.md](UI_PAGES.md) - Web UI documentation
- [OCSP_STAPLING_GUIDE.md](OCSP_STAPLING_GUIDE.md) - Configuration guide and best practices
- [UI_ARCHITECTURE.md](UI_ARCHITECTURE.md) - Technical architecture documentation
- `/ocsp/plugin.json` - Source of truth for OCSP settings
- `/ssl/plugin.json` - SSL and OCSP stapling settings
