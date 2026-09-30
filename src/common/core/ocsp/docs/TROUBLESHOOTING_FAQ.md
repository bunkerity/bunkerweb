# OCSP Troubleshooting FAQ

**Solutions for "OCSP doesn't work" problems**

---

## Quick Diagnosis

**Is OCSP not working? Run these 3 checks:**

### Check 1: Is OCSP enabled?

```bash
# Check global setting
env | grep OCSP_ASYNC_VALIDATION

# Check service setting
env | grep example.com_SSL_USE_OCSP_STAPLING

# Should both be "yes"
```

### Check 2: Is BunkerWeb running?

```bash
# Docker
docker ps | grep bunkerweb

# Systemd
systemctl status bunkerweb
```

### Check 3: Is there a cached response?

```bash
ls -la /var/cache/bunkerweb/ocsp/

# Should show files like: 0/*, 1/*, etc.
```

---

## Common "It Doesn't Work" Problems

---

## Q: Certificate doesn't show OCSP responder URL

**Symptom**: OCSP validation fails for all services with this certificate

**Solution**:

Your certificate doesn't support OCSP stapling.

**For Let's Encrypt**:
```bash
# Current (doesn't work): Let's Encrypt
AUTO_LETS_ENCRYPT=yes
LETS_ENCRYPT_SERVER=letsencrypt

# Fix: Use ZeroSSL instead
LETS_ENCRYPT_SERVER=zerossl
LETS_ENCRYPT_ZEROSSL_API_KEY=your-key-here
```

**For Custom Certificates**:
```bash
# Check if certificate has OCSP URL
openssl x509 -in /path/to/cert.pem -text -noout | grep -A1 "Authority Information Access"

# Should show "OCSP - URI:http://..."
# If not, request certificate with OCSP from your CA
```

**For Self-Signed Certificates**:
- Self-signed certificates cannot have OCSP URLs
- Use a CA-signed certificate instead

**Workaround** (temporary):
```bash
# Disable OCSP for this service until you get correct certificate
export example.com_SSL_USE_OCSP_STAPLING=no
```

---

## Q: Status shows "Unknown" or no response cached

**Symptom**: 
- OCSP Job Status shows "unknown"
- Cached responses count is 0
- Next refresh shows "Unknown"

**Cause**: Job hasn't run yet or failed to fetch responses

**Solution**:

1. **Wait for job to run** (1-5 minutes):
```bash
# Default schedule is every minute
# Wait and check status page again
sleep 60
```

2. **Check job logs**:
```bash
# Docker
docker logs bunkerweb | grep -i ocsp

# Systemd
journalctl -u bunkerweb -g ocsp --since "5 minutes ago"

# Should show validation attempts
```

3. **If no log entries**:
- Job hasn't started yet, wait longer
- Check if `OCSP_ASYNC_VALIDATION=yes` is set
- Restart BunkerWeb if setting just changed

4. **If "validation failed" errors**:
   - See [OCSP Responder Unreachable](#q-ocsp-responder-unreachable)

---

## Q: OCSP responder unreachable

**Symptom**:
- Logs show "Connection refused" or "timeout"
- Status shows validation errors
- Cached responses stuck at old timestamp

**Cause**: Cannot reach OCSP responder

**Diagnosis**:
```bash
# Extract responder URL from certificate
OCSP_URL=$(openssl x509 -in /path/to/cert.pem -ocsp_uri -noout)
echo "Testing responder: $OCSP_URL"

# Test connectivity
curl -v "$OCSP_URL" 2>&1 | head -20

# Should connect (even if OCSP error)
```

**Solutions**:

1. **Check network connectivity**:
```bash
# Can you reach the responder?
ping $(echo $OCSP_URL | cut -d'/' -f3)

# Is DNS working?
nslookup $(echo $OCSP_URL | cut -d'/' -f3)

# Test with curl
curl -I "$OCSP_URL"
```

2. **Check firewall/proxy**:
```bash
# Ensure outbound HTTPS (port 443) allowed
# Check if proxy blocking requests
# Whitelist OCSP responder domain if needed
```

3. **Check responder status**:
- Visit responder status page if available
- Try from different location (might be regional)
- Contact responder administrator

4. **Reduce request rate** (if responder overloaded):
```bash
# Lower from default 50 to 20
export OCSP_REQUEST_RATE_LIMIT=20

# Restart
docker-compose restart bunkerweb
```

**Temporary Workaround**:
```bash
# Switch to lenient mode (allows unstapled)
export OCSP_STAPLE_MODE=open

# Restart
docker-compose restart bunkerweb
```

---

## Q: "OCSP Response Expired" in status page

**Symptom**:
- OCSP remaining time shows "Expired"
- Certificate still shows remaining time
- Clients may be seeing unstapled responses

**Cause**: OCSP response not refreshed in time

**Why this happens**:
- Responder was down during refresh window
- Batch size too small, takes too long to validate
- Job schedule too infrequent
- Rate limiting too aggressive

**Solutions**:

1. **Increase batch size** (process more per cycle):
```bash
# Default: 10
# Try: 20-30
export OCSP_BATCH_SIZE=20

docker-compose restart bunkerweb
```

2. **More frequent validation**:
```bash
# Default: minute (every 1 min)
# Already at maximum frequency
# If still failing, job has systemic issue (see next)
```

3. **Increase rate limit**:
```bash
# Default: 50 req/s
# Try: 100 req/s (if responder can handle)
export OCSP_REQUEST_RATE_LIMIT=100

docker-compose restart bunkerweb
```

4. **Manual refresh**:
```bash
# Trigger immediate refresh via UI
# Go to /ocsp → Click "Fetch New Responses"

# Or wait - job will retry in next cycle
```

5. **Check responder status**:
- Responder might have been down
- See [OCSP Responder Unreachable](#q-ocsp-responder-unreachable)

**Prevention**:
- Monitor `/ocsp` page daily
- Alert if OCSP remaining < 1 day
- Ensure responder is monitored/healthy

---

## Q: Settings not taking effect

**Symptom**:
- Changed setting, but behavior unchanged
- Status page shows old values
- Previous configuration still active

**Cause**: Settings not reloaded

**Solution**:

1. **Verify setting is set**:
```bash
# Check it's in environment
env | grep OCSP

# Should show your setting with correct value
```

2. **Check for typos**:
```bash
# Service name must match exactly
export example.com_SSL_USE_OCSP_STAPLING=yes
# ↑ Exact match to domain name

# Wrong:
export example_com_SSL_USE_OCSP_STAPLING=yes  # ✗ (underscore instead of dot)
```

3. **Restart BunkerWeb**:
```bash
docker-compose restart bunkerweb

# Wait for restart (30-60 seconds)
sleep 30

# Check status page
```

4. **Verify change took effect**:
```bash
# Check logs
docker logs bunkerweb | grep -i "OCSP_ASYNC"

# Should show your new setting
```

**Configuration methods**:
- Environment variables (require restart)
- Config file (require restart)
- Docker Compose (require restart)
- OCSP UI (future - may auto-apply)

---

## Q: No services showing in status page

**Symptom**:
- `/ocsp` page shows "No services configured"
- `/ocsp/settings` empty
- Cannot find any services

**Cause**: `SERVER_NAME` not configured

**Solution**:

1. **Set SERVER_NAME**:
```bash
# At least one service
export SERVER_NAME=example.com

# Multiple services
export SERVER_NAME="example.com api.example.com www.example.com"

docker-compose restart bunkerweb
```

2. **Verify in UI**:
```bash
# Status page should now show services
# http://localhost:7000/ocsp
```

---

## Q: Can't connect to UI status page

**Symptom**:
- `/ocsp` returns 404 or connection refused
- Cannot access `/ocsp/settings`
- UI pages not loading

**Cause**: OCSP plugin not loaded or UI not accessible

**Solution**:

1. **Verify BunkerWeb is running**:
```bash
docker ps | grep bunkerweb
# Should show running container
```

2. **Verify UI port accessible**:
```bash
# Default port: 7000
curl http://localhost:7000/

# Should return HTML (not connection refused)
```

3. **Check OCSP plugin installed**:
```bash
# Check plugin exists
ls -la src/common/core/ocsp/plugin.json

# Should exist
```

4. **Restart BunkerWeb**:
```bash
docker-compose restart bunkerweb

# Wait 30 seconds
sleep 30

# Try again
curl http://localhost:7000/ocsp
```

---

## Q: High pending validations count

**Symptom**:
- "Pending Validations" count high (100+)
- Takes a long time to decrease
- New services slow to validate

**Cause**: Job cannot keep up with certificate count

**Solution**:

1. **Increase batch size**:
```bash
# Default: 10
# For 1000+ certificates, try: 50-100
export OCSP_BATCH_SIZE=50

docker-compose restart bunkerweb
```

2. **Increase rate limit**:
```bash
# Default: 50 req/s
# Try: 100-200 req/s
export OCSP_REQUEST_RATE_LIMIT=100

docker-compose restart bunkerweb
```

3. **Reduce jitter** (if safe):
```bash
# Default: 20%
# Try: 10% (spreads less, faster)
export OCSP_RATE_LIMIT_JITTER=10

docker-compose restart bunkerweb
```

4. **Check responder capacity**:
- If responder slow, requests queue up
- See [OCSP Responder Unreachable](#q-ocsp-responder-unreachable)

**Expected behavior**:
- New services: Validate within 1-10 minutes
- Existing services: Continuous refresh cycle

---

## Q: Clients showing connection errors

**Symptom**:
- TLS handshake failures
- "certificate verify failed" errors
- Some clients cannot connect

**Cause**: OCSP staple mode too strict

**Solution**:

1. **Check OCSP_STAPLE_MODE**:
```bash
env | grep OCSP_STAPLE_MODE

# If "normal": strict enforcement
# If "staple_only": graceful fallback
# If "open": no enforcement
```

2. **Switch to lenient mode** (temporary):
```bash
# Allow connections even without OCSP
export OCSP_STAPLE_MODE=open

docker-compose restart bunkerweb
```

3. **Investigate root cause**:
- Are OCSP responses cached? (Check `/var/cache/bunkerweb/ocsp/`)
- Is responder working? (See [OCSP Responder Unreachable](#q-ocsp-responder-unreachable))
- Are responses expired? (Check status page)

4. **Return to strict mode** once fixed:
```bash
export OCSP_STAPLE_MODE=normal

docker-compose restart bunkerweb
```

---

## Q: High disk usage in cache directory

**Symptom**:
- `/var/cache/bunkerweb/ocsp/` using lots of space
- More than expected
- Growing over time

**Cause**: Many certificates or old responses not cleaned

**Solution**:

1. **Check cache size**:
```bash
du -sh /var/cache/bunkerweb/ocsp/

# Rough estimate: ~1-10 KB per certificate
# 1000 certs should be ~10-100 MB max
```

2. **Manual cleanup** (safe):
```bash
# Find old files (not accessed in 7 days)
find /var/cache/bunkerweb/ocsp/ -type f -atime +7 -delete

# Or delete entire cache (will be rebuilt)
rm -rf /var/cache/bunkerweb/ocsp/*
```

3. **Check for bugs**:
- If size keeps growing, may have cache leak
- Check logs for errors
- See [Status shows Unknown](#q-status-shows-unknown-or-no-response-cached)

---

## Q: Job consuming too much CPU

**Symptom**:
- High CPU usage from OCSP job
- Server slow when job runs
- Regular CPU spikes

**Cause**: Job parameters too aggressive

**Solution**:

1. **Reduce batch size**:
```bash
# Default: 10
# Try: 5 (fewer certs per cycle)
export OCSP_BATCH_SIZE=5

docker-compose restart bunkerweb
```

2. **Reduce schedule frequency**:
```bash
# Default: minute (every 1 min)
# Try: 5minute
export OCSP_ASYNC_SCHEDULE=5minute

docker-compose restart bunkerweb
```

3. **Reduce rate limit**:
```bash
# Default: 50 req/s
# Try: 20 req/s (slower, less CPU)
export OCSP_REQUEST_RATE_LIMIT=20

docker-compose restart bunkerweb
```

---

## When to Escalate

**If none of the above work:**

1. **Collect diagnostics**:
```bash
# Logs from last hour
docker logs --since 1h bunkerweb > /tmp/bunkerweb.log

# Cache directory contents
ls -la /var/cache/bunkerweb/ocsp/ > /tmp/ocsp-cache.txt

# Settings
env | grep OCSP > /tmp/ocsp-settings.txt

# Status page screenshot
# Navigate to http://localhost:7000/ocsp, take screenshot
```

2. **Check documentation**:
- [SETTINGS_REFERENCE.md](SETTINGS_REFERENCE.md) - All settings explained
- [OCSP_STAPLING_GUIDE.md](OCSP_STAPLING_GUIDE.md) - Detailed configuration
- [UI_PAGES.md](UI_PAGES.md) - UI feature documentation

3. **Report issue with**:
- Error logs
- Settings values
- Certificate information
- Steps to reproduce

---

## Need More Help?

- **Getting started**: [QUICK_START.md](QUICK_START.md)
- **All settings**: [SETTINGS_REFERENCE.md](SETTINGS_REFERENCE.md)
- **Configuration guide**: [OCSP_STAPLING_GUIDE.md](OCSP_STAPLING_GUIDE.md)
- **UI features**: [UI_PAGES.md](UI_PAGES.md)

---

## Key Troubleshooting Checklist

- [ ] Certificate has OCSP responder URL
- [ ] `OCSP_ASYNC_VALIDATION=yes` is set
- [ ] `{SERVICE}_SSL_USE_OCSP_STAPLING=yes` is set per service
- [ ] BunkerWeb restarted after settings change
- [ ] Waited 1-5 minutes for first validation
- [ ] Status page shows cached responses (>0)
- [ ] No connection errors in logs
- [ ] OCSP remaining time > 0 (not expired)
- [ ] Responder connectivity verified
- [ ] Rate limit appropriate for responder

**✓ Check all above = OCSP should work!**
