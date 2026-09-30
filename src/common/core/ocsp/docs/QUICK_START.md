# OCSP Stapling - Quick Start Guide

**Get OCSP stapling working in 5 minutes**

---

## What is OCSP Stapling?

OCSP stapling makes TLS handshakes faster and more private by having your server provide certificate status updates directly to clients.

**Benefits**: Faster TLS, better privacy, improved reliability

---

## Prerequisites

- ✅ BunkerWeb installed and running
- ✅ Valid SSL certificate with OCSP responder URL
- ✅ Network connectivity to OCSP responder

**Certificate Check**:
```bash
openssl x509 -in /path/to/cert.pem -ocsp_uri -noout
```

Should output an OCSP responder URL. If empty, your certificate doesn't support OCSP stapling.

---

## Step 1: Enable OCSP Async Validation (Global)

**Set this once, applies to all services:**

```bash
export OCSP_ASYNC_VALIDATION=yes
```

This enables the background job that fetches OCSP responses.

---

## Step 2: Enable OCSP Stapling Per Service

**For each service that needs OCSP:**

```bash
# For service example.com
export example.com_SSL_USE_OCSP_STAPLING=yes

# For service api.example.com
export api.example.com_SSL_USE_OCSP_STAPLING=yes
```

Replace `example.com` with your actual service name.

---

## Step 3: Restart BunkerWeb

```bash
# Docker
docker restart bunkerweb

# Docker Compose
docker-compose restart bunkerweb

# Systemd
systemctl restart bunkerweb
```

---

## Step 4: Verify It's Working

### Check 1: Status Page

Navigate to BunkerWeb UI → OCSP Plugin → Status Overview

Look for:
- ✅ Green OCSP Status badge ("yes")
- ✅ Cached responses count (>0)
- ✅ Certificate remaining time shown

### Check 2: TLS Handshake

```bash
openssl s_client -connect example.com:443 \
  -tls1_2 \
  -status \
  < /dev/null 2>&1 | grep -A 2 "OCSP response:"
```

Expected output:
```
OCSP response:
OCSP Response Status: successful
```

### Check 3: Manual Verification

```bash
# Check if OCSP response is cached
ls -la /var/cache/bunkerweb/ocsp/

# Should show cached response files
```

---

## Common First-Time Issues

### Issue: "No OCSP response data available"

**Cause**: Certificate doesn't have OCSP URL

**Fix**: 
```bash
# Check certificate
openssl x509 -in /path/to/cert.pem -text -noout | grep -i "ocsp"

# Should show OCSP responder URL
# If not, your certificate doesn't support OCSP stapling
```

**Solution**: Use a certificate that supports OCSP:
- Let's Encrypt: Use ZeroSSL instead of Let's Encrypt
- Custom CA: Ensure certificate has OCSP URL

### Issue: "OCSP validation failed"

**Cause**: Responder unreachable or not responding

**Fix**:
```bash
# Test responder directly
openssl ocsp -issuer /path/to/issuer.pem \
             -cert /path/to/cert.pem \
             -url http://ocsp-responder.example.com

# Should return "good" or "revoked", not an error
```

**Solution**: 
- Check network connectivity
- Wait 1-5 minutes for first validation
- Check responder status

### Issue: "Settings not taking effect"

**Cause**: Settings not loaded or restarted

**Fix**:
```bash
# Verify settings are set
echo $example.com_SSL_USE_OCSP_STAPLING

# Should output "yes"

# Restart to load
docker-compose restart bunkerweb

# Wait 1 minute for job to run
sleep 60
```

---

## Next Steps

### For Production

1. **Check your current configuration:**
   - Go to `/ocsp/settings` in BunkerWeb UI
   - Verify global settings look good
   - Enable OCSP for all services

2. **Monitor OCSP status:**
   - Check `/ocsp` daily for status
   - Look for "Expired" OCSP responses (shouldn't happen)
   - Monitor cached response count

3. **Fine-tune for your load:**
   - If you have 1000+ certificates:
     - Increase `OCSP_BATCH_SIZE` to 20-50
     - Change `OCSP_ASYNC_SCHEDULE` to `5minute`
   - If you have <50 certificates:
     - Default settings work fine

### For Troubleshooting

**See**: [TROUBLESHOOTING_FAQ.md](TROUBLESHOOTING_FAQ.md)

### For Advanced Configuration

**See**: [SETTINGS_REFERENCE.md](SETTINGS_REFERENCE.md)

### For Detailed Guide

**See**: [OCSP_STAPLING_GUIDE.md](OCSP_STAPLING_GUIDE.md)

---

## Configuration Summary

**Minimal production configuration:**

```bash
# Enable async validation
export OCSP_ASYNC_VALIDATION=yes

# Enable for your services
export example.com_SSL_USE_OCSP_STAPLING=yes
export api.example.com_SSL_USE_OCSP_STAPLING=yes
export www.example.com_SSL_USE_OCSP_STAPLING=yes

# Optional: Adjust for your load
# export OCSP_BATCH_SIZE=20
# export OCSP_ASYNC_SCHEDULE=5minute

# Restart
docker-compose restart bunkerweb
```

That's it! OCSP stapling is now enabled.

---

## Verification Checklist

- [ ] Exported `OCSP_ASYNC_VALIDATION=yes`
- [ ] Exported `{SERVICE}_SSL_USE_OCSP_STAPLING=yes` for each service
- [ ] Restarted BunkerWeb
- [ ] Waited 1-5 minutes
- [ ] Checked status page (green badges)
- [ ] Verified with `openssl s_client` command
- [ ] Confirmed cached responses exist

---

## Getting Help

- **Status not showing**: [Status Page Not Updating](#issue-status-page-not-updating)
- **Responses showing as expired**: [Troubleshooting FAQ](TROUBLESHOOTING_FAQ.md)
- **Want more control**: [Settings Reference](SETTINGS_REFERENCE.md)
- **Need details**: [OCSP Stapling Guide](OCSP_STAPLING_GUIDE.md)

---

## Key Points to Remember

1. **Prerequisites**: Certificate must have OCSP responder URL
2. **Two settings**: Global `OCSP_ASYNC_VALIDATION` + per-service `SSL_USE_OCSP_STAPLING`
3. **Takes time**: First validation takes 1-5 minutes
4. **Check status**: Use `/ocsp` page to monitor
5. **Restart required**: Changes need BunkerWeb restart

---

**That's all you need to get started! 🚀**

For questions or issues, check [TROUBLESHOOTING_FAQ.md](TROUBLESHOOTING_FAQ.md).
