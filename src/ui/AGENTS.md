# AGENTS.md

Agent guide for the BunkerWeb Flask web UI in `src/ui/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Root: [../../AGENTS.md](../../AGENTS.md) (short) and [../../CLAUDE.md](../../CLAUDE.md) (architecture)
- API guide: [../api/AGENTS.md](../api/AGENTS.md) — the UI's only data source

## What This Is

Server-rendered Flask + Jinja2 with vanilla JS and jQuery. No SPA framework, no bundler. Runs on Gunicorn with threaded workers on port 7000.

## Critical Rules

- **All data access goes through `API_CLIENT`.** The UI does not talk to the database. `DB` in `app/dependencies.py` is exported as `None`, a backward-compatibility shim so old external plugin blueprints that `import DB` still load. Route code must never use it.
- One blueprint per page under `app/routes/`; run `ls` for the current set. Blueprint priority is pro > external > core, and a higher-priority plugin blueprint overrides a lower-priority one of the same name.
- Reuse the existing route patterns: `@login_required`, `verify_data_in_form()` for POST validation, `handle_error()` for the error flash + redirect, `@cors_required` on JSON/streaming endpoints (it requires `Sec-Fetch-Mode: cors` or `X-Requested-With: XMLHttpRequest`), and `CONFIG_TASKS_EXECUTOR` for anything long-running.
- User-visible strings go through the i18n catalogs. `data-i18n` in a template is banned and tested against.

## Architecture

### Entry point

`main.py` defines `DynamicFlask`, a Flask subclass supporting dynamic blueprint reloading with the priority order above, registers the core blueprints, wires the middleware stack and the plugin hooks.

### Dependency injection (`app/dependencies.py`)

Singletons: `API_CLIENT` (the `ApiClient`, primary and only data path), `DATA` (`UIData`, a JSON file at `/var/tmp/bunkerweb/ui_data.json` holding transient cross-process state such as reload flags and pending flashes), `BW_CONFIG` (`Config`, settings and config builder), `BW_INSTANCES_UTILS` (`InstancesUtils`, instance metrics and Redis access). Both of the latter take `API_CLIENT` as a dependency.

Also exported: `CONFIG_TASKS_EXECUTOR` (a 4-worker ThreadPoolExecutor), the plugin filesystem paths `CORE_PLUGINS_PATH` / `EXTERNAL_PLUGINS_PATH` / `PRO_PLUGINS_PATH`, and `reload_plugins()` / `safe_reload_plugins()`, which pull plugin tarballs via `API_CLIENT.get_plugins(with_data=True)` and materialize them on disk.

### API client (`app/api_client.py`)

`ApiClient` extends `BaseApiClient` (`common/utils/base_api_client.py`) and is the single entry point for UI↔API traffic. Configured from `API_URL` (default `http://bw-api:5000`) and `API_TOKEN`. Low-level `_get`/`_post`/`_patch`/`_put`/`_delete`/`_raw_request` come from the base, plus a `readonly` property reflecting the API state; domain methods are grouped by resource. Errors are `ApiClientError` (carries `status_code`) and `ApiUnavailableError`, both re-exported from `app.api_client`; routes map them to user-facing flashes via `handle_error()` / `error_message()` in `app/routes/utils.py`.

### Async task flow

```
Route -> DATA["RELOADING"] = True -> CONFIG_TASKS_EXECUTOR.submit(task)
      -> redirect to loading page -> loading page polls DATA
      -> task sets DATA["RELOADING"] = False
      -> loading page redirects, flashing DATA["TO_FLASH"]
```

### Models (`app/models/`)

`config.py` (`Config`) and `instance.py` (`InstancesUtils`) both take an `api_client` and hold no DB access. `ui_database.py` (`UIDatabase`) covers users, sessions, roles and permissions; `models.py` has `UiUsers` (SQLAlchemy `Users` + Flask-Login `UserMixin`) and `AnonymousUser`. The rest are small and self-describing: `ui_data.py`, `biscuit.py`, `totp.py`, `reverse_proxied.py`, `template.py`, `safe_session_cache.py`.

### Authentication

Flask-Login with `session_protection = "strong"` (IP + User-Agent validated per request). Sessions live in Redis when available, otherwise `SafeFileSystemCache`. Cookie: `__Host-bw_ui_session` (Secure, HttpOnly, SameSite=Lax). Biscuit tokens carry RBAC; TOTP 2FA with recovery codes; CSRF via Flask-WTF on every POST.

### Plugin hooks

A plugin extends the UI with `ui/hooks.py` and `ui/blueprints/`. Hook types: `before_request`, `after_request`, `teardown_request`, `context_processor`, `scripts`, `styles`. Hooks are deduplicated by `(module, qualname)`.

### Frontend

- **JS**: vanilla + jQuery, page scripts in `app/static/js/pages/`, no modules, no bundling. Libraries are vendored in `app/static/libs/`.
- **CSS**: Bootstrap with custom variables in `overrides.css`; dark mode via `data-bs-theme`.
- **Minification** happens only in the Docker build (UglifyJS, cssnano); skip with `SKIP_MINIFY=yes`.

### i18n

Server-rendered, with a small browser helper:

- **Server (Flask-Babel)**: `app/i18n.py` resolves the locale (session → user preference → `Accept-Language` → `en`); compiled catalogs live in `src/ui/translations/<locale>/LC_MESSAGES/`. Templates use `_('some.key')` and arrive translated. `tests/unit/ui/test_i18n_migration.py` fails on any `data-i18n*` in a template.
- **Browser**: `/locales/<lang>.js` publishes the locale JSON as `window.BW_I18N` from a plain `<script>` ahead of every page script; `t()` in `js/i18n.js` reads it synchronously. `window.i18next` is a shim over the same `t()` for plugin front-ends. `applyTranslations(root)` is only for markup a script just built — never on load.
- **JS reading a key out of rendered markup breaks.** DataTables SearchPane filters did; they match `data-value` now and `tests/unit/ui/test_searchpane_filters.py` bans the old form.
- The JSON files in `app/static/locales/` are the source of truth for both halves: `misc/dev/i18n/json_to_po.py` generates the gettext catalogs from them and a unit test fails on drift. Message ids are the dotted keys, not English text. Read `misc/dev/i18n/README.md` — especially why `br`/`tw` map to `pt_BR`/`zh_Hant`, and when a literal `%` must be doubled.

### Gunicorn (`utils/gunicorn.conf.py`)

`gthread` workers (CPU count - 1), threads = workers × 2, port 7000, optional TLS from env. `post_fork()` is a deliberate no-op: the UI holds no SQLAlchemy connections any more, so there is nothing to dispose after fork.

## Commands

```bash
docker compose -f misc/dev/docker-compose.ui.api.yml up -d           # UI :7000, API :8888 (admin / P@ssw0rd)
docker compose -f misc/dev/docker-compose.ui.api.yml restart bw-ui   # code change
docker compose -f misc/dev/docker-compose.ui.api.yml up -d --build bw-ui  # dependency / Dockerfile change

pre-commit run --all-files
```

Dev compose mounts `app/`, `utils/` and `main.py` read-only, so a restart picks up code changes; a rebuild is only needed for dependencies or the Dockerfile. Prettier is the only frontend linter (no ESLint, no Stylelint); Jinja templates are linted by the `djlint` pre-commit hook. Unit tests for the pure `app/utils` helpers and `UIDatabase` live in `tests/unit/ui/`.

## Runtime Gotchas

- **`{% from %}` does not pass context, and `script_nonce` comes from a context processor.** Jinja globals (`_`, `url_for`, `csrf_token`) still resolve in an imported macro; anything a context processor supplies does not. A macro emitting an inline `<script nonce="{{ script_nonce }}">` renders `nonce=""`, CSP blocks the script, and nothing happens — no error, no 500, one console line, and `curl` shows a perfectly good page. `components/service-options.html` hit exactly this and emptied every service picker on `/certificates`, `/upstreams` and `/redirects`. Import such macros `with context` and pin it in a test (`tests/unit/ui/test_service_options.py` asserts both the rendered nonce and the import line).
- **Jinja comments do not nest.** A `{# ... #}` inside a macro's doc comment closes it early and turns the rest of the file into live template code. At least it is loud: `UndefinedError` on render.
- **Page scripts are `defer`red, so they run before `DOMContentLoaded`** — as do jQuery `$(document).ready` callbacks. A macro populating DOM for page code to read must run at parse time (an IIFE), placed after the elements it fills, not from a `DOMContentLoaded` listener.
- **`procps` must stay in the Dockerfile.** The two-app handoff (`temp.py` serves a placeholder on 7000 until `main.py` is ready, then `on_starting` shells out to `kill`) and `app/utils.py:restart_workers` (`pgrep` + `kill -HUP`) both need it; Debian images have no `/bin/kill` or `pgrep` without it, and the UI never starts.
- Long-running work must go through `CONFIG_TASKS_EXECUTOR` and the `DATA["RELOADING"]` flow, or the request blocks a Gunicorn thread.

## Key Utilities

- `app/utils.py`: `flash()` (i18n-aware), `get_multiples()` (parses numbered settings such as `REVERSE_PROXY_URL_1`), `get_blacklisted_settings()`, `is_editable_method()`, bcrypt password hashing
- `app/routes/utils.py`: `verify_data_in_form()`, `handle_error()`, `wait_applying()` (polls metadata until the Scheduler is idle), `extract_file_setting_names()`

## Environment

| Variable                                                | Default              | Purpose                                                               |
| ------------------------------------------------------- | -------------------- | --------------------------------------------------------------------- |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD`                     | —                    | Initial admin credentials                                             |
| `API_URL`                                               | `http://bw-api:5000` | API base URL — all UI data flows through it                           |
| `API_TOKEN`                                             | —                    | Shared secret for authenticating to the API (required in dev compose) |
| `DATABASE_URI`                                          | sqlite               | Used indirectly via the API; the UI does not connect                  |
| `FLASK_SECRET`                                          | generated            | Session signing key                                                   |
| `SESSION_LIFETIME_HOURS`                                | 12                   | Session duration                                                      |
| `MAX_WORKERS` / `MAX_THREADS`                           | auto                 | Gunicorn workers/threads                                              |
| `UI_MAX_CONTENT_LENGTH`                                 | 50MB                 | Max upload size                                                       |
| `UI_SSL_ENABLED` / `UI_SSL_CERTFILE` / `UI_SSL_KEYFILE` | —                    | TLS                                                                   |
| `DEBUG`                                                 | —                    | Flask debug mode                                                      |
