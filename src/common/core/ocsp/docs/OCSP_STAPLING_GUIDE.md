# OCSP Stapling Configuration Guide

## What is OCSP Stapling?

OCSP (Online Certificate Status Protocol) stapling is a TLS feature that improves certificate validation performance and privacy. Instead of clients contacting an OCSP responder to check certificate revocation status, the server provides a pre-fetched OCSP response directly during the TLS handshake.

### Benefits

1. **Performance**: Clients don't need to make separate OCSP requests
2. **Privacy**: Clients' certificate validation requests aren't logged by OCSP responders
3. **Reliability**: Reduces dependency on OCSP responder availability
4. **User Experience**: Faster TLS handshakes, especially for first connections

### How It Works

1. **Server fetches** OCSP response from certificate's OCSP responder
2. **Server caches** the response locally
3. **Client connects** via TLS
4. **Server includes** cached OCSP response in handshake
5. **Client validates** without additional OCSP lookup

## BunkerWeb OCSP Implementation

### Architecture Components

```
┌──────────────────────────────────────────┐
│  BunkerWeb OCSP Stapling System         │
├──────────────────────────────────────────┤
│                                          │
│  UI Layer (Web Interface)               │
│  ├── /ocsp (Status Overview)            │
│  ├── /ocsp/settings (Configuration)     │
│  └── /plugins/ocsp (Status Cards)       │
│                                          │
│  ↓                                       │
│                                          │
│  Config Layer (Settings Management)     │
│  ├── Global OCSP Settings               │
│  ├── Per-Service SSL Settings           │
│  └── Database/Environment Storage       │
│                                          │
│  ↓                                       │
│                                          │
│  Background Job (ocsp-async-validate)  │
│  ├── Certificate Discovery              │
│  ├── OCSP Response Fetching             │
│  ├── Cache Management                   │
│  └── Retry Logic (Exponential Backoff)  │
│                                          │
│  ↓                                       │
│                                          │
│  Runtime (Lua/NGINX)                    │
│  ├── OCSP Response Stapling             │
│  ├── Must-Staple Enforcement            │
│  └── Cache Serving                      │
│                                          │
└──────────────────────────────────────────┘
```

### Configuration Hierarchy

```
Environment Variables (Highest Priority)
    ↓
Database Config (Persisted Settings)
    ↓
Plugin Defaults (Hard-coded Defaults)
```

**Global Settings** (apply to all services):
```
OCSP_ASYNC_VALIDATION      Enable/disable background job
OCSP_ASYNC_SCHEDULE        Job frequency (minute/5minute/hour)
OCSP_BATCH_SIZE            Certs per job cycle
OCSP_REQUEST_RATE_LIMIT    Requests/second to responder
OCSP_STAPLE_MODE           Default must-staple mode
OCSP_CACHE_DIR             Cache directory path
OCSP_*_TTL                 Redis TTL for queue entries
OCSP_RESPONDER_RETRY_*     Retry interval settings
```

**Per-Service Settings** (service-specific override):
```
{SERVICE}_SSL_USE_OCSP_STAPLING    Enable/disable for service
{SERVICE}_OCSP_STAPLE_MODE         Service-specific mode
{SERVICE}_SSL_MUST_STAPLE          Enforce must-staple
{SERVICE}_SSL_CERTIFICATE_PATH     Certificate file path
```

## Configuration Best Practices

### For Most Users (Recommended)

```
Global Settings:
- OCSP_ASYNC_VALIDATION=yes         (enabled)
- OCSP_ASYNC_SCHEDULE=minute        (validate every minute)
- OCSP_STAPLE_MODE=normal           (strict enforcement)
- OCSP_BATCH_SIZE=10                (reasonable default)
- OCSP_REQUEST_RATE_LIMIT=50        (non-aggressive)

Per-Service:
- SSL_USE_OCSP_STAPLING=yes         (enable for all)
- OCSP_STAPLE_MODE=normal           (use global default)
```

This configuration:
- Keeps OCSP responses fresh (validated every minute)
- Enforces must-staple for maximum security
- Won't overload responders
- Provides quick recovery from transient failures

### For High-Traffic Deployments (10,000+ req/s)

```
Global Settings:
- OCSP_ASYNC_SCHEDULE=5minute       (reduce load: validate every 5min)
- OCSP_BATCH_SIZE=50                (faster warmup, higher load)
- OCSP_REQUEST_RATE_LIMIT=100       (higher limit for volume)
- OCSP_STAPLE_MODE=staple_only      (graceful degradation)

Per-Service:
- SSL_USE_OCSP_STAPLING=yes         (enable for all)
- OCSP_STAPLE_MODE=staple_only      (use staple_only mode)
```

Trade-offs:
- Less frequent refreshes (5min vs 1min)
- Faster processing but higher responder load
- Fallback to unstapled if issues occur
- Better availability, slightly reduced security

### For High-Security Requirements

```
Global Settings:
- OCSP_ASYNC_VALIDATION=yes
- OCSP_ASYNC_SCHEDULE=minute        (frequent validation)
- OCSP_STAPLE_MODE=normal           (strict enforcement)
- OCSP_BATCH_SIZE=5                 (cautious load)
- OCSP_REQUEST_RATE_LIMIT=20        (conservative)

Per-Service:
- SSL_USE_OCSP_STAPLING=yes
- OCSP_STAPLE_MODE=normal           (must-staple enforced)
```

Impact:
- Maximum security posture
- Higher responder load
- More conservative but safer
- Better for compliance-heavy environments

### For Testing/Development

```
Global Settings:
- OCSP_ASYNC_VALIDATION=no          (disable background job)
- OCSP_STAPLE_MODE=open             (no enforcement)

Per-Service:
- SSL_USE_OCSP_STAPLING=no          (disable for testing)
```

Use cases:
- Testing without OCSP responder availability
- Development environments
- Certificate testing before production
- Troubleshooting certificate issues

## OCSP Staple Modes Explained

### Mode 1: Normal (Strict)

**Behavior**: Strictly enforce OCSP responses for must-staple certificates

```
Client connects
    ↓
Server checks: Does cert have must-staple?
    ↓
    YES → Is OCSP response cached and valid?
            ↓
            YES → Staple response, proceed
            NO → REFUSE handshake, log error
    ↓
    NO → Proceed without staple
```

**Use cases**:
- High-security requirements
- Compliance mandates
- Sites with must-staple certificates

**Pros**:
- Maximum security
- Ensures OCSP validation
- Compliance-friendly

**Cons**:
- Will refuse connections if OCSP unavailable
- Higher operational overhead
- Requires reliable responder

### Mode 2: Staple Only (Balanced)

**Behavior**: Prefer OCSP-stapled certificates, fall back if needed

```
Client connects
    ↓
Server checks: Is OCSP response cached and valid?
    ↓
    YES → If must-staple cert, staple it
    NO → Skip stapling
    ↓
Proceed with or without staple (client still works)
```

**Use cases**:
- Production environments
- Balance of security and availability
- Most common real-world deployments

**Pros**:
- Graceful degradation
- Better availability
- OCSP preferred when available
- Won't break if responder fails

**Cons**:
- Less strict than normal mode
- Unstapled connections on failures
- May not meet strict compliance

### Mode 3: Open (Recovery)

**Behavior**: Disable must-staple enforcement, serve unstapled if needed

```
Client connects
    ↓
Server checks: Is OCSP response cached?
    ↓
    YES → Staple it if available
    NO → Serve without staple
    ↓
Proceed (will work regardless)
```

**Use cases**:
- OCSP responder outages
- Troubleshooting
- Temporary recovery
- Development/testing

**Pros**:
- Maximum availability
- Will never block connections
- Emergency fallback

**Cons**:
- No must-staple enforcement
- OCSP validation skipped if no cache
- Reduced security posture
- Should be temporary

## Common Issues and Solutions

### Issue: "OCSP Response Expired"

**Symptoms**:
- Status shows "Expired" for OCSP remaining time
- Recent OCSP refresh hasn't occurred

**Causes**:
- Async validation job not running
- Responder failures during last refresh window
- Job schedule too infrequent

**Solutions**:
1. Check job status in `/plugins/ocsp` status cards
2. Verify `OCSP_ASYNC_VALIDATION=yes`
3. Reduce `OCSP_ASYNC_SCHEDULE` (minute → more frequent)
4. Click "Fetch" button to manually refresh
5. Check responder connectivity in logs

### Issue: "OCSP Responder Unavailable"

**Symptoms**:
- Fetch responses button shows error
- Pending validations count increasing
- Status card shows error

**Causes**:
- Network connectivity to responder
- Responder overloaded (rate limiting)
- Wrong OCSP responder URL in certificate

**Solutions**:
1. Reduce `OCSP_REQUEST_RATE_LIMIT` (50 → 20)
2. Increase `OCSP_BATCH_SIZE` intervals (spread out requests)
3. Check certificate has valid OCSP URL:
   ```bash
   openssl x509 -in cert.pem -ocsp_uri -noout
   ```
4. Verify network connectivity to responder
5. Switch to `staple_only` mode for graceful degradation
6. Check responder status page

### Issue: "Certificate Approaching Expiry"

**Symptoms**:
- Cert remaining time showing days, not months
- Status page warning colors

**Causes**:
- Certificate nearing end of validity
- Renewal not scheduled
- Auto-renewal failed

**Solutions**:
1. If Let's Encrypt: Check `AUTO_LETS_ENCRYPT=yes`
2. Verify certificate renewal job is running
3. Check certificate file timestamps
4. Look at responder's certificate (may be limiting OCSP validity)
5. Plan certificate renewal in `/services/<name>` SSL settings

### Issue: "Must-Staple Not Enforced"

**Symptoms**:
- Modal shows "Must-Staple: Disabled"
- Despite setting `SSL_MUST_STAPLE=yes`

**Causes**:
- Certificate doesn't have must-staple extension
- Setting name mismatch
- Configuration not applied

**Solutions**:
1. Verify certificate has must-staple extension:
   ```bash
   openssl x509 -in cert.pem -text -noout | grep "OCSP"
   ```
2. Use certificate with must-staple, or
3. Obtain certificate from CA supporting it:
   - ZeroSSL supports must-staple
   - Let's Encrypt doesn't (use ZeroSSL for LE replacement)

### Issue: "Batch Size Too High/Low"

**Too High** (100+):
- Responder gets overwhelmed at startup
- Rate limiting kicks in
- Validation takes longer

**Too Low** (1-2):
- Slow warmup period
- Takes long time to validate all certs
- Might not keep up with high turnover

**Solutions**:
1. **Optimal** for most: 10-20
2. **High traffic**: 30-50
3. **Conservative**: 5-10
4. Adjust `OCSP_REQUEST_RATE_LIMIT` proportionally

## Monitoring and Maintenance

### Key Metrics to Monitor

| Metric | Location | Healthy | Warning | Alert |
|--------|----------|---------|---------|-------|
| Job Status | `/plugins/ocsp` | Running | Unknown | Failed |
| Cached Responses | Status card | Increasing | Stable | Decreasing |
| Pending Validations | Status card | 0-10 | 10-100 | 100+ |
| Cert Remaining | `/ocsp` table | 90+ days | 30-90 days | <30 days |
| OCSP Remaining | `/ocsp` table | 5+ days | 1-5 days | <1 day |
| Last Refresh | Details modal | Within 1h | 1-6h | 6h+ |

### Daily Checks

1. ✓ Review `/ocsp` status overview
2. ✓ Check for any "Expired" certificates
3. ✓ Verify job status is "running"
4. ✓ Check responder connectivity

### Weekly Maintenance

1. ✓ Review metrics trends
2. ✓ Check if batch size needs tuning
3. ✓ Verify rate limit appropriate
4. ✓ Test manual OCSP refresh

### Quarterly Review

1. ✓ Analyze job performance
2. ✓ Optimize batch size if needed
3. ✓ Review certificate rotation schedule
4. ✓ Evaluate OCSP staple mode effectiveness

## Troubleshooting Guide

### Check Certificate OCSP Support

```bash
# View OCSP responder URL in certificate
openssl x509 -in /path/to/cert.pem -ocsp_uri -noout

# View full certificate details
openssl x509 -in /path/to/cert.pem -text -noout | grep -A5 "Authority Information"
```

### Check OCSP Responder Connectivity

```bash
# Test OCSP responder response
openssl ocsp -issuer /path/to/issuer.pem \
              -cert /path/to/cert.pem \
              -url http://ocsp-url.example.com
```

### Check Cache Directory

```bash
# List cached OCSP responses
ls -lh /var/cache/bunkerweb/ocsp/

# Check cache file age
find /var/cache/bunkerweb/ocsp/ -type f -mtime 0  # Modified today

# Calculate OCSP validity from file timestamp
stat /var/cache/bunkerweb/ocsp/cached-response-file
```

### Review Logs

```bash
# Check BunkerWeb OCSP job logs
journalctl -u bunkerweb -g "ocsp" --since "1 hour ago"

# Check system logs for connectivity issues
grep -i "ocsp" /var/log/syslog

# Check NGINX access logs for OCSP requests
grep "ocsp" /var/log/nginx/access.log
```

## Glossary

| Term | Definition |
|------|-----------|
| OCSP | Online Certificate Status Protocol |
| Must-Staple | Certificate extension requiring OCSP response in TLS handshake |
| Stapling | Including OCSP response in TLS handshake |
| Responder | OCSP server that provides certificate status |
| Handshake | Initial TLS connection negotiation |
| Revocation | Certificate marked as invalid before expiry |
| TTL | Time To Live (how long data is cached) |
| Batch Size | Number of items processed per job cycle |
| Rate Limit | Maximum requests per unit time |
| Exponential Backoff | Retry delays increase over time |
