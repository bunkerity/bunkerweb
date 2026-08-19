# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

BunkerWeb's Web UI — a Flask application for managing the BunkerWeb WAF. Server-rendered with Jinja2 templates and vanilla JS (no SPA framework, no bundler). Runs on Gunicorn with threaded workers.

## Development

### Run the full dev stack (UI + API + scheduler + BunkerWeb + MariaDB)

```bash
docker compose -f misc/dev/docker-compose.ui.api.yml up -d
# UI: http://localhost:7000 (admin / P@ssw0rd)
# API: http://localhost:8888 (admin / P@ssw0rd)
```

The dev compose mounts `src/ui/app/`, `src/ui/utils/`, and `src/ui/main.py` as read-only volumes. Code changes require a container restart (`docker compose restart bw-ui`), not a rebuild.

### Rebuild after dependency or Dockerfile changes

```bash
docker compose -f misc/dev/docker-compose.ui.api.yml up -d --build bw-ui
```

### Linting & formatting

```bash
pre-commit run --all-files          # All hooks
black src/ui/                       # Python (160 char lines)
flake8 src/ui/                      # Python lint
prettier --write "src/ui/**/*.{js,css,html,json}"  # Frontend
```

No ESLint or Stylelint — only Prettier for JS/CSS. Python unit tests for the UI's pure `app/utils` helpers and `UIDatabase` live in `tests/unit/ui/` (pytest, via the repo's `.venv-unit`); broader behavior is integration-tested via Docker (see root CLAUDE.md).

## Architecture

### Entry point: `main.py`

`DynamicFlask` — custom Flask subclass that supports dynamic blueprint reloading with priority (pro > external > core plugins). Registers 20 core blueprints, configures middleware stack, and sets up plugin hooks.

### Dependency injection: `app/dependencies.py`

All UI data access goes through `API_CLIENT` — the UI no longer talks to the database directly. `DB` is exported as `None` purely as a backward-compat shim so external plugin blueprints that still `import DB` don't break at load time. Route code must never use it.

Global singletons:

| Object               | Type             | Purpose                                                                                                |
| -------------------- | ---------------- | ------------------------------------------------------------------------------------------------------ |
| `API_CLIENT`         | `ApiClient`      | HTTP client for the BunkerWeb API — primary data access for all routes                                 |
| `DATA`               | `UIData`         | JSON file at `/var/tmp/bunkerweb/ui_data.json` — shared transient state (reload flags, flash messages) |
| `BW_CONFIG`          | `Config`         | Settings & config builder (takes `API_CLIENT`)                                                         |
| `BW_INSTANCES_UTILS` | `InstancesUtils` | Instance metrics and Redis access (takes `API_CLIENT`)                                                 |
| `DB`                 | `None`           | Legacy shim — kept only for backward compatibility with plugins that still import it                   |

Also exported: `CONFIG_TASKS_EXECUTOR` (ThreadPoolExecutor, 4 workers) for non-blocking config tasks, plugin filesystem paths `CORE_PLUGINS_PATH` / `EXTERNAL_PLUGINS_PATH` / `PRO_PLUGINS_PATH`, and `reload_plugins()` / `safe_reload_plugins()` which pull plugin tarballs via `API_CLIENT.get_plugins(with_data=True)` and materialize them on disk.

### API client: `app/api_client.py`

`ApiClient` extends `BaseApiClient` (from `common/utils/base_api_client.py`) and is the single entry point for all UI↔API traffic. Configured from `API_URL` (default `http://bw-api:5000`) and `API_TOKEN`.

- Low-level helpers inherited from base: `_get`, `_post`, `_patch`, `_put`, `_delete`, `_raw_request`, plus a `readonly` property reflecting the API's current state.
- Domain methods grouped by resource: global settings, instances, bans, cache, jobs, services, configs, plugins, users, user preferences, templates, metadata — plus `save_config()` and `checked_changes()`.
- Errors: `ApiClientError` (carries `status_code`) and `ApiUnavailableError`, both re-exported from `app.api_client`. Routes catch these and map to user-facing flashes via `handle_error()` / `error_message()` in `app/routes/utils.py`.

### Routes: `app/routes/`

20 Flask Blueprints. Common patterns:

- Canonical imports from `app.dependencies` — e.g. `from app.dependencies import API_CLIENT, BW_CONFIG, BW_INSTANCES_UTILS, CONFIG_TASKS_EXECUTOR, DATA`. Pick the subset the route needs; never import `DB`.
- `@login_required` on all authenticated routes
- `verify_data_in_form()` for POST validation (from `app/routes/utils.py`)
- `handle_error()` for error flash + redirect
- Long-running operations submit to `CONFIG_TASKS_EXECUTOR`, set `DATA["RELOADING"] = True`, redirect to loading page
- `@cors_required` decorator on JSON/streaming endpoints (requires `Sec-Fetch-Mode: cors` or `X-Requested-With: XMLHttpRequest`)

### Async task flow (plugins, services, configs)

```
Route → DATA["RELOADING"] = True → CONFIG_TASKS_EXECUTOR.submit(task)
  → redirect to loading page → loading page polls DATA → task sets DATA["RELOADING"] = False
  → loading page redirects to final page with flash messages from DATA["TO_FLASH"]
```

### Models: `app/models/`

| File                    | Purpose                                                                                                 |
| ----------------------- | ------------------------------------------------------------------------------------------------------- |
| `ui_database.py`        | `UIDatabase` — UI-specific DB methods (users, sessions, roles, permissions)                             |
| `models.py`             | `UiUsers` (extends SQLAlchemy `Users` + Flask-Login `UserMixin`), `AnonymousUser`                       |
| `config.py`             | `Config` — configuration builder and validator (takes an `api_client` dependency — no direct DB access) |
| `instance.py`           | `InstancesUtils` — instance aggregation, Redis operations (takes an `api_client` dependency)            |
| `ui_data.py`            | `UIData` — JSON file store for cross-process state                                                      |
| `biscuit.py`            | Biscuit token auth (RBAC middleware)                                                                    |
| `totp.py`               | TOTP/2FA management                                                                                     |
| `reverse_proxied.py`    | WSGI middleware for X-Forwarded-\* headers                                                              |
| `template.py`           | `get_ui_templates()` — template wizard functionality                                                    |
| `safe_session_cache.py` | `SafeFileSystemCache` — secure JSON-serialized session storage fallback                                 |

### Authentication

- Flask-Login with `session_protection = "strong"` (validates IP + User-Agent per request)
- Sessions stored in Redis (if available) or `SafeFileSystemCache`
- Session cookie: `__Host-bw_ui_session` (Secure, HttpOnly, SameSite=Lax)
- Biscuit tokens for RBAC (role mapped to read/write operations)
- TOTP 2FA support with recovery codes
- CSRF via Flask-WTF on all POST requests

### Plugin hook system

Plugins can extend the UI by providing `ui/hooks.py` and `ui/blueprints/`. Hook types: `before_request`, `after_request`, `teardown_request`, `context_processor`, `scripts`, `styles`. Hooks are deduplicated by `(module, qualname)`. Higher-priority plugin blueprints override lower-priority ones with the same name.

### Frontend

- **JS**: Vanilla JavaScript + jQuery. Page-specific scripts in `app/static/js/pages/`. No modules or bundling.
- **CSS**: Bootstrap 5.3.3 + custom CSS variables in `overrides.css`. Dark mode via `data-bs-theme` attribute.
- **i18n**: server-rendered, with a small browser helper. No client library.
  - **Server-side (Flask-Babel)** — `app/i18n.py` resolves the locale (session → user preference → `Accept-Language` → `en`) and `src/ui/translations/<locale>/LC_MESSAGES/` holds the compiled catalogs. **Every** template uses `_('some.key')` and arrives already translated; `tests/unit/ui/test_i18n_migration.py` fails on any `data-i18n*` in a template.
  - **Browser** — `/locales/<lang>.js` serves the locale's JSON as `window.BW_I18N` from a plain `<script>` ahead of every page script, and `t()` in `js/i18n.js` reads it synchronously. Use it for strings JavaScript builds. `window.i18next` is a shim over the same `t()` for plugin front-ends. `applyTranslations(root)` still exists but only for markup a script just built from a string — never on load.
  - **When JS reads a key out of rendered markup, it breaks.** DataTables SearchPane filters did; they match `data-value` now and `tests/unit/ui/test_searchpane_filters.py` bans the old form.
  - The 18 JSON files in `app/static/locales/` are the source of truth for both halves: `misc/dev/i18n/json_to_po.py` generates the gettext catalogs from them, and a unit test fails if they drift. Message ids are the dotted keys, not English text. See `misc/dev/i18n/README.md` — in particular why `br`/`tw` are remapped to `pt_BR`/`zh_Hant` and when a literal `%` must be doubled.
- **Libs**: Vendored in `app/static/libs/` (DataTables, Ace editor, ApexCharts, Leaflet, Flatpickr, etc.)
- **Minification**: Only during Docker build (UglifyJS for JS, cssnano for CSS). Skip with `SKIP_MINIFY=yes` build arg.

### Jinja macros: `{% from ... %}` does not pass context

`{% from "components/x.html" import macro %}` imports **without** context. Jinja globals (`_`,
`url_for`, `csrf_token`) still resolve, but anything a **context processor** supplies does not —
and `script_nonce` is one of those.

A macro that emits an inline `<script nonce="{{ script_nonce }}">` therefore renders `nonce=""`,
the page's CSP blocks the script, and whatever it was going to do never happens. **No error, no
500, one console line — and `curl` shows a perfectly good page.** A failure that is invisible from
the server side is the kind that ships. `components/service-options.html` hit exactly this: every
service picker on `/certificates`, `/upstreams` and `/redirects` rendered empty.

Import such a macro `with context`, and pin it in a test — `tests/unit/ui/test_service_options.py`
asserts both the rendered nonce and the import line on each page that uses one.

Two neighbours of the same trap:

- **Jinja comments do not nest.** A `{# ... #}` inside a macro's doc comment closes it early and
  turns the rest of the file into live template code. Loud, at least: `UndefinedError` on render.
- **Page scripts are `defer`red, so they run _before_ `DOMContentLoaded`** — as do jQuery's
  `$(document).ready` callbacks. A macro that populates DOM for page code to read must run at parse
  time (an IIFE) and be called _after_ the elements it fills, not from a `DOMContentLoaded`
  listener, which would fire too late.

### Gunicorn: `utils/gunicorn.conf.py`

`gthread` worker class (multi-threaded). Workers = CPU count - 1, threads = workers \* 2. Port 7000. TLS support via env vars. `post_fork()` is a no-op now — the UI no longer holds SQLAlchemy connections (all data flows through the API), so there is nothing to dispose after fork.

**Two-app handoff:** `temp.py` serves a "starting" placeholder on 7000 until `main.py` is ready, then `gunicorn.conf.py on_starting` shells out (`subprocess.call(["kill", ...])`) to stop temp and bind 7000. `app/utils.py:restart_workers` similarly uses `pgrep`+`kill -HUP` on plugin reload. **`procps` must be installed** (Debian images have no `/bin/kill`/`pgrep` without it) or the UI never starts — keep it in the Dockerfile.

## Key utilities

- `app/utils.py`: `flash()` (enhanced with i18n), `get_multiples()` (parse numbered settings like `REVERSE_PROXY_URL_1`), `get_blacklisted_settings()`, `is_editable_method()`, password hashing (bcrypt, rounds=13)
- `app/routes/utils.py`: `verify_data_in_form()`, `handle_error()`, `wait_applying()` (polls DB metadata until scheduler is idle), `extract_file_setting_names()`

## Important env vars for the UI

| Variable                                                | Default              | Purpose                                                                         |
| ------------------------------------------------------- | -------------------- | ------------------------------------------------------------------------------- |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD`                     | —                    | Initial admin credentials                                                       |
| `API_URL`                                               | `http://bw-api:5000` | BunkerWeb API base URL — all UI data flows through it                           |
| `API_TOKEN`                                             | —                    | Shared secret for authenticating to the API (required in dev compose)           |
| `DATABASE_URI`                                          | sqlite               | SQLAlchemy connection string (used indirectly via the API; UI does not connect) |
| `FLASK_SECRET`                                          | generated            | Session signing key                                                             |
| `SESSION_LIFETIME_HOURS`                                | 12                   | Session duration                                                                |
| `MAX_WORKERS` / `MAX_THREADS`                           | auto                 | Gunicorn workers/threads                                                        |
| `UI_MAX_CONTENT_LENGTH`                                 | 50MB                 | Max upload size                                                                 |
| `UI_SSL_ENABLED` / `UI_SSL_CERTFILE` / `UI_SSL_KEYFILE` | —                    | TLS config                                                                      |
| `DEBUG`                                                 | —                    | Flask debug mode                                                                |
