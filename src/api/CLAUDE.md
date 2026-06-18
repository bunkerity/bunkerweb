# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See also the [root CLAUDE.md](../../CLAUDE.md) for project-wide architecture, build commands, and conventions.

## What This Is

The BunkerWeb API — a FastAPI control plane for BunkerWeb (open-source WAF). Manages configuration, instances, plugins, bans, and scheduler artifacts. Lives at `src/api/` within the larger BunkerWeb monorepo.

## Architecture

### Startup Flow

1. `entrypoint.sh` launches Gunicorn with a custom Uvicorn worker (`utils/worker.py`)
2. `utils/gunicorn.conf.py` `on_starting()` hook runs pre-fork: initializes Biscuit EdDSA keys, creates/updates API user in DB, builds ACL cache file, bootstraps permissions from JSON
3. `app/main.py` `create_app()` builds the FastAPI app: mounts middleware (IP whitelist, rate limiter, rate-limit headers), includes the core router, registers error handlers
4. `app/routers/core.py` assembles all sub-routers; `/auth` is mounted **unconditionally** (the endpoint itself returns 401 when no API users exist in the database)

### Request Lifecycle

```
Request → IP Whitelist (middleware) → Rate Limiter → Route Match → Auth Guard (per-endpoint dep) → Handler → Rate-Limit Headers (middleware) → Error Normalization → Response
```

Only the IP whitelist and the rate-limit-headers middleware are true middleware. The auth guard is attached as a FastAPI per-endpoint dependency (`dependencies=[Depends(guard)]` in `app/routers/core.py`), so it runs **after** FastAPI matches a route — `/docs`, `/openapi.json`, `/health`, `/ping`, and `/auth/*` never reach it because they don't have it as a dependency.

All errors normalize to `{"status": "error", "message": "..."}`.

### Three-Tier Authentication (`app/auth/guard.py`)

The `BiscuitWithAdminBearer` guard runs on every request (except `/health`, `/ping`, `/auth/*`, docs endpoints):

1. **HTTP Basic** — if credentials provided, must match an admin API user (bcrypt, 30s cache)
2. **Bearer API_TOKEN** — if `API_TOKEN` env var matches the bearer token, grants full admin access
3. **Biscuit Token** — EdDSA-signed authorization tokens with embedded facts and fine-grained ACL permissions. Issued at `POST /auth`. Verified in `app/auth/biscuit.py` with freshness + IP binding + per-resource permission checks

Skipped paths: `/health`, `/ping`, `/auth/*`, `/docs*`, `/redoc*`, `/openapi.json`, `/openapi.yaml`

### Routers (`app/routers/`)

| Router               | Prefix                                | Purpose                                                                                                                                |
| -------------------- | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `core.py`            | `/`                                   | Hub — assembles all routers, provides `/ping` and `/health`                                                                            |
| `auth.py`            | `/auth`                               | Login, Biscuit token issuance                                                                                                          |
| `instances.py`       | `/instances`                          | Instance CRUD (sub-routes include `/{hostname}/*`), broadcast reload/stop/ping                                                         |
| `services.py`        | `/services`                           | Service config CRUD, convert, export                                                                                                   |
| `global_settings.py` | `/global_settings` + `/global_config` | Read/update global settings. `PUT /global_settings/config` updates config, `POST /global_settings/validate` validates without applying |
| `configs.py`         | `/configs`                            | Custom NGINX config management (upload, CRUD)                                                                                          |
| `bans.py`            | `/bans`                               | Ban/unban IPs across instances                                                                                                         |
| `plugins.py`         | `/plugins`                            | Plugin list, upload (tar.gz/zip), delete. `GET /plugins?with_data=true` returns base64-encoded plugin data                             |
| `cache.py`           | `/cache`                              | Job cache file inspection/purge                                                                                                        |
| `jobs.py`            | `/jobs`                               | List jobs, trigger execution                                                                                                           |
| `users.py`           | `/users`                              | API user CRUD (create, list, update, delete)                                                                                           |
| `system.py`          | `/system`                             | System info, version, reload, restart                                                                                                  |
| `templates.py`       | `/templates`                          | Server template CRUD                                                                                                                   |
| `metadata.py`        | `/metadata`                           | Plugin/setting metadata lookups                                                                                                        |

### Configuration Loading (`app/config.py`)

`ApiConfig` (Pydantic `YamlBaseSettings`) loads from multiple sources in precedence order:

1. Environment variables (highest priority)
2. Docker secrets (`/run/secrets`)
3. YAML file (`/etc/bunkerweb/api.yml`)
4. Env file (`/etc/bunkerweb/api.env`)
5. Defaults

Boolean settings accept `yes/no/true/false/1/0/on/off`.

### Shared Dependencies (from `src/common/`)

The API imports from the monorepo's shared modules via `sys.path` manipulation (container paths under `/usr/share/bunkerweb/`):

- `Database` (`src/common/db/Database.py`) — SQLAlchemy ORM wrapper, pooled connections
- `API`, `ApiCaller` (`src/common/api/`) — HTTP clients for communicating with BunkerWeb NGINX instances
- `common_utils` (`src/common/utils/common_utils.py`) — Docker secrets, hashing, version info
- `logger` (`src/common/utils/logger.py`) — Unified logging with syslog support
- `model` (`src/common/db/model.py`) — SQLAlchemy models including `API_users`, `API_permissions`

API-specific models: `app/models/api_database.py` (APIDatabase wraps API user/permission queries).

### Key Singletons (`app/utils.py`)

- `get_db()` — shared `Database` instance for BunkerWeb config/settings
- `get_api_db()` — shared `APIDatabase` instance for API users/permissions
- Both are lazy-initialized, pooled, and closed on app shutdown via the lifespan handler

### Rate Limiting (`app/rate_limit.py`)

Complex engine supporting multiple syntax formats (`10/hour`, `100r/m` NGINX-style), path patterns with wildcards/regex, method filtering, Redis/Redis Sentinel storage, and IP exemptions. Configured via `API_RATE_LIMIT_*` env vars.

## Development

### Running Locally

```bash
# Minimal API-only stack (API + MariaDB)
docker compose -f misc/dev/docker-compose.api.yml up -d

# Extended API stack (adds Redis + scheduler + test upstream — use when exercising rate limits, broadcasting, or reverse-proxy flows)
docker compose -f misc/dev/docker-compose.api.misc.yml up -d

# Full stack with UI
docker compose -f misc/dev/docker-compose.ui.api.yml up -d
```

The dev compose mounts `src/api/app/` and `src/api/utils/` as read-only volumes. With `DEBUG=1` (set by default in the compose files) Gunicorn watches `app/` via `reload_extra_files` and reloads workers on file change — no container restart needed. Restart is only required when `DEBUG` is off or when editing outside `app/`/`utils/` (e.g. `entrypoint.sh`, `gunicorn.conf.py`).

Dev credentials: API `admin`/`P@ssw0rd`, DB `bunkerweb`/`secret`.

### Dependencies

```bash
pip install -r src/api/requirements.txt  # compiled from requirements.in
```

Key packages: `fastapi==0.137.1`, `uvicorn==0.49.0`, `gunicorn==26.0.0`, `biscuit-python` (pinned to a Git commit, ~0.4.1), `bcrypt==5.0.0`, `slowapi==0.1.10`, `pydantic==2.13.4`, `pydantic-settings==2.14.1`. `celery` is **not** in `requirements.in`; it (with `redis`) is installed into the image from `src/worker/requirements.txt` at build time (the certbot stack is stripped — see `src/api/Dockerfile`). The `jobs` router uses it lazily via `app/celery_app.py` to dispatch to the worker queue.

### Linting & Formatting

```bash
# From repo root
pre-commit run --all-files

# Or individually
black --line-length 160 src/api/    # Python formatting
flake8 --max-line-length=160 --ignore=E266,E402,E501,E722,W503 src/api/
```

### Testing

No unit tests in `src/api/`. Integration tests run against live Docker environments from the repo root:

```bash
python3 tests/main.py docker
```

### Key File Paths (Container)

| Path                                          | Purpose                          |
| --------------------------------------------- | -------------------------------- |
| `/var/lib/bunkerweb/.api_biscuit_public_key`  | Biscuit public key               |
| `/var/lib/bunkerweb/.api_biscuit_private_key` | Biscuit private key              |
| `/var/lib/bunkerweb/api_acl.json`             | ACL cache (generated at startup) |
| `/var/lib/bunkerweb/api_acl_bootstrap.json`   | Optional ACL bootstrap file      |
| `/var/tmp/bunkerweb/api.healthy`              | Health file (created when ready) |
| `/etc/bunkerweb/api.yml`                      | YAML config file                 |

## Important Patterns

- **Dependency injection**: FastAPI `Depends()` for DB access (`app/deps.py`), auth guard, API clients
- **Pydantic schemas**: All request/response models in `app/schemas.py` with validators
- **Config types**: Custom configs accept both hyphen and underscore variants (`server-http`/`server_http`), normalized internally to underscores
- **Instance broadcasting**: Routers call BunkerWeb NGINX instances via `ApiCaller` for operations like reload/stop/ban
- **Plugin changes**: Service/config mutations mark plugins as changed in DB, triggering the Scheduler to regenerate NGINX configs
- **`core.py` is NOT the app entry point**: It's the router hub. The actual FastAPI app is created in `main.py`
- **OpenAPI YAML**: Custom `GET /openapi.yaml` endpoint exports the OpenAPI spec as YAML (in addition to the standard JSON `/openapi.json`)

## Runtime Gotchas

Non-obvious behaviors worth knowing before editing:

- **Biscuit freshness & IP binding** (`app/auth/biscuit.py`): `API_BISCUIT_TTL_SECONDS` defaults to 3600; set to `off`/`disabled`/`0` to disable expiry. IP binding is enforced unless the caller is a private IP **and** `CHECK_PRIVATE_IP=no`. ACL is serialized as Biscuit facts `api_perm(resource_type, resource_id | "*", permission)`; the path → (resource, perm) mapping lives in `_resolve_resource_and_perm()` — add a case there when introducing a new protected endpoint.
- **Instance broadcasting** (`app/deps.py`, `ApiCaller.send_to_apis`): `get_instances_api_caller()` rebuilds the caller from the DB on **every** request; if the DB is down it falls back to the internal API only. Broadcasts are single-pass with a default 5s timeout (`API_HTTP_TIMEOUT`) — no retry. Any single-instance failure aggregates to a 502 for the caller.
- **Bulk-operation method guard**: service/config mutations only accept `method ∈ {autoconf, scheduler, manual, ui, wizard}` (`app/schemas.py`) to prevent one component from clobbering another's records. Extending the set requires updating the validator and the DB enums.
- **Startup hard-exits** (`utils/gunicorn.conf.py::on_starting`): the process `exit(1)`s if Biscuit keys fail to load, DB init exceeds 60s, or no auth method is configured (no API users **and** no `API_TOKEN`). `OVERRIDE_API_CREDS=yes` forces the env-provided admin creds to overwrite the DB record on boot. `API_ACL_BOOTSTRAP_FILE` (default `/var/lib/bunkerweb/api_acl_bootstrap.json`) seeds users and permissions on startup and accepts either dict or list shapes for the permissions block.
- **Rate-limit path matching** (`app/rate_limit.py`): wildcard rules are **shell-glob** style by default, not regex (explicit regex rules must be flagged as such). `API_ROOT_PATH` is stripped from the request path before matching. For Redis Sentinel, credentials are split: master auth goes in the main URI, Sentinel auth in `sentinel_kwargs`.
