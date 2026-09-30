# OCSP Plugin UI Architecture

## Overview

The OCSP plugin provides a comprehensive web UI for managing OCSP (Online Certificate Status Protocol) stapling configuration across all services in BunkerWeb. This document describes the architecture, code organization, and extension points.

## Directory Structure

```
src/common/core/ocsp/ui/
├── actions.py                          # Status card display (pre_render hook)
└── blueprints/
    ├── ocsp.py                         # Flask blueprint with routes
    └── templates/
        ├── ocsp_overview.html          # Status overview page
        └── ocsp_settings.html          # Configuration settings page
```

## Architecture Components

### 1. Flask Blueprint (`blueprints/ocsp.py`)

The blueprint defines all HTTP routes and handles requests.

**Route Registration**:
- Blueprint is auto-discovered by BunkerWeb's UI loader
- Located in `ui/blueprints/` directory
- Module name becomes blueprint name: `ocsp`
- URL prefix: `/ocsp` (automatically added by loader)

**Routes Defined**:

| Route | Method | Handler Function | Purpose |
|-------|--------|------------------|---------|
| `/ocsp` | GET | `ocsp_overview()` | Status overview page |
| `/ocsp/settings` | GET | `ocsp_settings()` | Settings configuration page |
| `/ocsp/fetch-responses` | POST | `fetch_ocsp_responses()` | Fetch new OCSP responses |
| `/ocsp/service-status` | GET | `get_service_status()` | Get detailed service status (JSON API) |

**Helper Functions**:

```python
format_datetime(dt)
```
- Converts datetime objects to "YYYY-MM-DD HH:MM:SS UTC" format
- Handles strings and None values gracefully

```python
calculate_remaining_time(end_time)
```
- Converts remaining duration to human-readable format
- Returns "Xd Yh" for days, "Xh Ym" for hours/minutes, "Xm" for minutes
- Detects expired certificates/OCSP responses

```python
get_certificate_info(service)
```
- Core function for certificate parsing and timing extraction
- Parses X.509 certificates using cryptography library
- Reads OCSP cache files to estimate response validity
- Calculates next refresh time (20% into validity period)
- Returns dict with all timing information

```python
get_services_ocsp_status()
```
- Retrieves OCSP configuration for all services
- Builds service list with certificate and OCSP timing info
- Used by both overview and settings pages

### 2. Status Card Display (`actions.py`)

The `pre_render()` function provides status card data for the plugin page.

**How it Works**:
1. BunkerWeb UI calls `pre_render()` when rendering `/plugins/ocsp`
2. Function returns dict with status card definitions
3. UI framework renders cards based on returned data

**Status Cards Defined**:

| Card | Type | Key | Description |
|------|------|-----|-------------|
| OCSP Job Status | ping_status | "ping_status" | Async validation job health |
| Cached Responses | counter | "counter_ocsp_cache_entries" | Number of cached OCSP responses |
| Pending Validations | counter | "counter_ocsp_pending" | Certificates awaiting validation |
| Configuration | info | "info_configuration" | Link to settings page |

**Card Properties**:
- `title`: Display name
- `value`: Current value/status
- `subtitle`: Optional description
- `svg_color`: Icon color (success, warning, info)
- `action_url`: Link to navigate to
- `action_label`: Button text
- `col-size`: Bootstrap grid class (col-12 col-md-4)

### 3. Templates

#### ocsp_overview.html

**Structure**:
```html
Header (title + fetch button)
├── Services Table
│   ├── thead (column headers)
│   └── tbody (service rows with status badges)
├── Configuration Guide (legend)
└── Service Details Modal
    └── Details content (populated by JavaScript)
```

**Technologies**:
- Jinja2 templating for backend rendering
- Bootstrap 5 for styling and components
- DataTables.js for table functionality
- JavaScript for dynamic modals and AJAX

**Key Features**:
1. Responsive table with sticky header
2. Service details modal with AJAX loading
3. XSS protection via HTML escaping
4. Color-coded status badges
5. Tooltip timestamps on hover

**Data Flow**:
1. Python: `ocsp_overview()` calls `get_services_ocsp_status()`
2. Template receives `services` list
3. Jinja2 renders table rows for each service
4. JavaScript enables DataTables sorting/searching
5. Click "Details" → AJAX call to `/ocsp/service-status`
6. Response JSON used to populate modal

#### ocsp_settings.html

**Structure**:
```html
Header (title + view status button)
├── Navigation Tabs
│   ├── Global Settings Tab
│   │   ├── Form with settings inputs
│   │   └── Save button
│   └── Per-Service Configuration Tab
│       ├── Services table
│       └── Configure buttons per row
└── Service Configuration Modal
    └── Per-service settings form
```

**Technologies**:
- Bootstrap Tabs for multi-section UI
- Form elements with validation feedback
- DataTables for service listing
- Modal for service configuration

**Key Features**:
1. Tab interface for global vs per-service settings
2. Toggle visibility of dependent fields (e.g., staple mode)
3. Helpful descriptions for each setting
4. Read-only cache directory display
5. Modal for per-service configuration

**Data Flow**:
1. Python: `ocsp_settings()` retrieves global settings and services
2. Template renders global settings form
3. Template renders services table from services list
4. JavaScript enables editing via modal
5. Submit button triggers save (future implementation)

### 4. Database Integration

**Configuration Storage**:
- Global settings: Environment variables or database config
- Service settings: Prefixed with service name (e.g., `example.com_SSL_USE_OCSP_STAPLING`)

**Database Access**:
```python
from app.dependencies import DB

db_config = DB.get_config()  # Get all config
value = db_config.get("OCSP_ASYNC_VALIDATION", "yes")
service_value = db_config.get(f"{service}_SSL_USE_OCSP_STAPLING", "no")
```

**Related Settings** (in SSL plugin):
- `SSL_USE_OCSP_STAPLING` (multisite context)
- `OCSP_STAPLE_MODE` (multisite context, used by SSL plugin)

**OCSP Plugin Settings** (global context):
- `OCSP_ASYNC_VALIDATION`
- `OCSP_ASYNC_SCHEDULE`
- `OCSP_BATCH_SIZE`
- `OCSP_REQUEST_RATE_LIMIT`
- `OCSP_STAPLE_MODE` (global default)
- `OCSP_CACHE_DIR`
- Queue TTL settings (pending, validated, failed, processing)
- Responder retry settings

### 5. Security Architecture

**Authentication**:
- All routes require `@login_required`
- Blueprint inherits user context from Flask session

**Authorization**:
- POST operations check `current_user.admin`
- Fetch responses restricted to administrators

**Input Validation**:
- Service name validated with regex
- Query parameters sanitized
- All HTML output escaped with `escapeHtml()` function

**Data Protection**:
- Certificate paths displayed but not downloaded via UI
- Sensitive values shown in info cards only (no password fields)

## Extension Points

### Adding New Status Cards

To add a new status card to the plugin page:

1. **Define card in `actions.py`** (pre_render function):
```python
ret["counter_custom"] = {
    "value": 42,
    "title": "CUSTOM METRIC",
    "subtitle": "Description",
    "svg_color": "success",
    "col-size": "col-12 col-md-4",
}
```

2. **Template automatically renders** based on prefix:
   - `ping_*`: Status indicator (up/down)
   - `counter_*`: Number display
   - `info_*`: Information card
   - `date_*`: Date/timestamp display

### Adding New Configuration Settings

To add new OCSP settings:

1. **Add to `plugin.json`**:
```json
"NEW_SETTING": {
    "context": "global",  // or "multisite"
    "default": "value",
    "help": "Description",
    "id": "new-setting",
    "label": "New Setting",
    "regex": "^pattern$",
    "type": "check|text|select|number"
}
```

2. **Update UI form** in template:
```html
<input type="text" id="new-setting" value="{{ global_settings.NEW_SETTING }}">
```

3. **Update blueprint** to handle new setting:
```python
new_setting = db_config.get("NEW_SETTING", "default")
global_settings["NEW_SETTING"] = new_setting
```

### Adding New Routes

To add new API endpoint:

1. **Define route in `ocsp.py`**:
```python
@ocsp.route("/ocsp/new-endpoint", methods=["GET", "POST"])
@login_required
def new_endpoint():
    """Docstring."""
    # Implementation
    return jsonify({"result": "value"}), 200
```

2. **Update navigation** in templates if user-facing

3. **Add documentation** in UI_PAGES.md

## Code Quality Standards

### Docstrings

All functions have comprehensive docstrings:
```python
def function_name(param):
    """
    Short description.
    
    Longer description with context and behavior.
    
    Args:
        param (type): Description
        
    Returns:
        type: Description
    """
```

### Comments

- Add comments for non-obvious logic
- Explain "why", not "what" (code shows what)
- Use inline comments sparingly

### Error Handling

```python
try:
    # Core logic
except Exception as e:
    logger.error(f"Descriptive error message: {e}")
    logger.debug(format_exc())  # Full traceback for debugging
    return error_message("User-friendly message"), 500
```

### HTML/XSS Protection

```javascript
const escapeHtml = str => {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
};
```

## Testing

### Manual Testing Checklist

- [ ] Status overview loads all services
- [ ] Certificate times display correctly
- [ ] OCSP response times estimated correctly
- [ ] Settings form displays all fields
- [ ] Service details modal loads via AJAX
- [ ] Navigation between pages works
- [ ] Responsive design on mobile
- [ ] Login required enforced
- [ ] Admin check works for POST operations

### Performance Considerations

- `get_services_ocsp_status()` iterates all services - optimize if 1000+ services
- Certificate parsing is I/O bound - cache results if frequently called
- OCSP cache files scanned on each request - consider caching
- DataTables loads all rows client-side - consider server-side pagination

## Future Enhancements

1. **Settings Save Functionality**
   - Implement `/ocsp/settings/save` endpoint
   - Update global and per-service configurations
   - Add form validation and error messages

2. **OCSP Response Preview**
   - Decode and display OCSP response details
   - Show responder information
   - Display certificate chain

3. **Historical Metrics**
   - Track OCSP validation times over time
   - Alert on validation delays
   - Dashboard showing trends

4. **Bulk Operations**
   - Select multiple services for batch updates
   - Enable/disable OCSP stapling for groups
   - Schedule bulk OCSP refreshes

5. **WebSocket Updates**
   - Real-time status updates
   - Live job progress display
   - Notifications on configuration changes
