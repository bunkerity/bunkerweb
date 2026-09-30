# OCSP Plugin UI Pages Documentation

## Overview

The OCSP plugin provides three main UI pages for managing and monitoring OCSP (Online Certificate Status Protocol) stapling configuration and certificate validity.

## Pages and Routes

### 1. OCSP Plugin Page (`/plugins/ocsp`)

**Purpose**: Main plugin status dashboard showing OCSP metrics and quick links

**Components**:
- **OCSP Job Status Card**: Shows status of async validation job
  - Value: "yes" (running), "no" (failed), "unknown" (unable to determine)
  - Action: "View Status Overview" button links to `/ocsp`

- **Cached Responses Card**: Count of cached OCSP responses
  - Shows number of responses currently in cache
  - Useful for understanding cache warmth

- **Pending Validations Card**: Count of certificates awaiting validation
  - Shows backlog of certificates needing OCSP validation
  - High numbers may indicate responder issues

- **Configuration Card**: Quick access to settings
  - Action: "Open Settings" button links to `/ocsp/settings`
  - Allows quick navigation to configuration interface

**Access**: 
- Click on OCSP plugin in `/plugins` list
- Or navigate directly to `/plugins/ocsp`

---

### 2. OCSP Status Overview (`/ocsp`)

**Purpose**: Real-time dashboard showing all services' OCSP configuration and certificate validity

**Main Table Columns**:
| Column | Description |
|--------|-------------|
| Service | Service/domain name |
| SSL | Whether SSL/TLS is enabled (icon badge) |
| OCSP | Whether OCSP stapling is enabled (icon badge) |
| Must-Staple | Must-staple extension enforcement status |
| Multi-Cert | Multiple certificate deployment status |
| Cert Expires | Human-readable remaining certificate validity (e.g., "90d 5h") |
| OCSP Expires | Remaining OCSP response validity (e.g., "6d 12h") |
| Next Refresh | Scheduled OCSP response refresh date |
| Actions | Fetch & Details buttons |

**Features**:

1. **Status Indicators**
   - Color-coded badges for quick status visualization
   - Green: enabled/yes, Orange/Yellow: disabled/warning, Gray: N/A
   - Tooltips show full timestamps on hover

2. **Fetch New Responses**
   - Button to manually trigger OCSP response refresh
   - Can fetch for all services at once
   - Per-service fetch button available in actions

3. **Service Details Modal**
   - Click "Details" button to view comprehensive service information
   - Shows:
     - Service configuration (SSL, OCSP, Must-Staple, Multi-Cert)
     - Certificate paths
     - **Certificate Validity Section**
       - Valid from timestamp
       - Valid until timestamp
       - Remaining validity
     - **OCSP Response Validity Section**
       - OCSP start time (when response was created)
       - OCSP end time (when response expires)
       - Remaining validity (time before refresh needed)
       - Next planned refresh (when refresh job will run)

4. **Configuration Guide**
   - Built-in legend explaining configuration options
   - Time column descriptions
   - Information about OCSP stapling

**Sorting & Filtering**:
- DataTables integration allows sorting by any column
- Search/filter by service name or status
- Pagination for large deployments

**Navigation**:
- "View Status" button from settings page
- Direct URL: `/ocsp`
- Link from plugin page status cards

---

### 3. OCSP Configuration Settings (`/ocsp/settings`)

**Purpose**: Centralized interface for global and per-service OCSP configuration

**Tab 1: Global Settings**

Configure OCSP job behavior and defaults:

- **Asynchronous OCSP Validation** (toggle)
  - Enable/disable background OCSP validation job
  - Default: yes (enabled)
  - Impact: Reduces TLS handshake latency

- **Validation Schedule** (dropdown)
  - Options: Every minute (1m), Every 5 minutes (5m), Every hour (1h)
  - Default: minute
  - Trade-off: More frequent = fresher responses, higher load

- **Validation Batch Size** (number input)
  - How many certificates to validate per job cycle
  - Default: 10
  - Higher = faster warmup but higher responder load
  - Lower = slower but more conservative

- **OCSP Request Rate Limit** (number input with /sec unit)
  - Maximum requests per second to OCSP responder
  - Default: 50 req/s
  - Prevents overwhelming responder during startup

- **Default OCSP Staple Mode** (dropdown)
  - Options:
    - `normal` (default): Strictly enforce must-staple, refuse handshakes
    - `staple_only`: Prefer stapled certificates, fall back if needed
    - `open`: Recovery mode, disable must-staple enforcement
  - Detailed descriptions provided for each option

- **OCSP Cache Directory** (read-only text)
  - Shows: `/var/cache/bunkerweb/ocsp`
  - Informational only (set at deployment)

**Tab 2: Per-Service Configuration**

Configure OCSP settings for each individual service:

**Table Columns**:
| Column | Description |
|--------|-------------|
| Service | Service/domain name |
| SSL Enabled | Whether SSL is active |
| OCSP Stapling | Whether stapling is enabled |
| Staple Mode | Current staple mode (normal/staple_only/open) |
| Must-Staple | Must-staple enforcement status |
| Actions | Configure button |

**Configuration Modal** (opened by "Configure" button):

Per-service settings include:

1. **Enable OCSP Stapling** (toggle checkbox)
   - Enable/disable OCSP stapling for this service
   - Note: Certificate must advertise OCSP responder
   - For Let's Encrypt: Use ZeroSSL as CA

2. **OCSP Staple Mode** (dropdown, visible only when stapling enabled)
   - Options: normal, staple_only, open
   - Overrides global default for this service
   - Detailed help text included

3. **Enforce Must-Staple** (toggle checkbox)
   - Only applies if certificate has must-staple extension
   - Requires OCSP response for TLS handshake

**Info Section**:
- Explains OCSP stapling modes
- Shows benefits of each configuration
- Provides recommendations

**Navigation**:
- Direct URL: `/ocsp/settings`
- Link from plugin page configuration card
- Link from status overview page

---

## Time Display Formats

### Remaining Time Display

Times are shown in human-readable format:
- **Multiple days**: `90d 5h` (90 days, 5 hours)
- **Less than day**: `23h 15m` (23 hours, 15 minutes)
- **Less than hour**: `45m` (45 minutes)
- **Expired**: `Expired` (shown in red)

### Timestamp Display

Full timestamps shown in tooltips and modals:
- Format: `YYYY-MM-DD HH:MM:SS UTC`
- Example: `2026-10-05 12:30:00 UTC`

### Refresh Schedule Display

Next refresh dates displayed as:
- Date only in table column: `2024-10-08`
- Full timestamp in details modal: `2024-10-08 12:30:00 UTC`

---

## User Workflows

### Workflow 1: Monitor OCSP Health

1. Navigate to `/plugins/ocsp`
2. Check status cards:
   - Is async job running?
   - How many responses cached?
   - Any pending validations?
3. Click "View Status Overview" to see details
4. Review certificate/OCSP expiry times
5. Check if any services approaching renewal

### Workflow 2: Enable OCSP Stapling

1. Navigate to `/ocsp/settings`
2. Click "Per-Service Configuration" tab
3. Find desired service
4. Click "Configure" button
5. Enable "OCSP Stapling" checkbox
6. Select "OCSP Staple Mode"
7. Enable "Enforce Must-Staple" if needed
8. Click "Save Configuration"
9. Monitor status in `/ocsp` for response availability

### Workflow 3: Troubleshoot Missing OCSP Responses

1. Go to `/ocsp` status overview
2. Find service with high OCSP remaining time or no cached response
3. Click "Fetch" button to manually refresh
4. Check service details modal for:
   - OCSP response status
   - Last refresh time
   - Responder issues
5. If issues persist, go to `/ocsp/settings`
6. Adjust batch size, rate limit, or schedule
7. Set staple mode to `open` for recovery if needed

---

## API Endpoints

### GET /ocsp/service-status

Retrieve detailed status for a specific service.

**Parameters**:
- `service` (required): Service/domain name

**Response** (JSON):
```json
{
  "service": "example.com",
  "ssl_enabled": true,
  "ocsp_enabled": true,
  "must_staple": false,
  "multi_cert": true,
  "ocsp_staple_mode": "normal",
  "ssl_certificate_path": "/path/to/cert.pem",
  "ssl_certificate_key_path": "/path/to/key.pem",
  "cert_start": "2024-10-05 12:30:00 UTC",
  "cert_end": "2026-10-05 12:30:00 UTC",
  "cert_remaining": "1y 11m",
  "ocsp_start": "2024-10-05 12:30:00 UTC",
  "ocsp_end": "2024-10-12 12:30:00 UTC",
  "ocsp_remaining": "6d 12h",
  "next_refresh": "2024-10-08 12:30:00 UTC"
}
```

### POST /ocsp/fetch-responses

Trigger manual OCSP response refresh.

**Request** (JSON):
```json
{
  "services": ["example.com", "www.example.com"]
}
```

**Response** (JSON):
```json
{
  "status": "ok",
  "message": "Queued OCSP refresh for 2 service(s)",
  "services": ["example.com", "www.example.com"]
}
```

---

## Security Notes

- All pages require login (`@login_required`)
- Admin checks for sensitive operations (fetch responses)
- HTML output is escaped to prevent XSS attacks
- Input validation on service names
- Read-only display of deployment-time settings

---

## Troubleshooting

### No services showing
- Check if any SSL-enabled services are configured
- Verify SERVER_NAME setting is populated

### OCSP responses showing as "Unknown"
- Certificate may not advertise OCSP responder
- For Let's Encrypt, must use ZeroSSL or other CA with OCSP

### High pending validations count
- Job may be rate-limited or overloaded
- Try increasing batch size or rate limit
- Check responder status

### Settings not saving
- Feature currently displays UI only
- Edit in `/global-settings` (global) or `/services/<name>` (per-service)
- Future updates will add save functionality
