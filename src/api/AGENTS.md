# AGENTS.md

Agent guide for the BunkerWeb FastAPI control plane in `src/api/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Root: [../../AGENTS.md](../../AGENTS.md) (short) and [../../CLAUDE.md](../../CLAUDE.md) (architecture)
- Shared code: [../common/AGENTS.md](../common/AGENTS.md)

## What This Is

The API is the control plane: configuration, instances, plugins, bans, users, and scheduler artifacts. Everything the UI shows passes through it. It owns no NGINX rendering of its own — mutations mark plugins/config as changed and the Scheduler regenerates.

## Critical Rules

- `app/main.py` creates the FastAPI app; `app/routers/core.py` only assembles routers.
- One router file per resource under `app/routers/`, mounted at its own prefix. run `ls` for the current set; two exceptions are worth knowing: `/auth` is mounted **unconditionally** (the endpoint itself 401s when no API users exist), and `global_settings.py` serves both `/global_settings` and `/global_config`.
- Auth is a per-endpoint dependency (`dependencies=[Depends(guard)]`), not global middleware, so it runs **after** route matching. `/health`, `/ping`, `/auth/*` and the docs endpoints never reach it because they simply do not declare it.
- Add a Biscuit ACL special case in `app/auth/biscuit.py` (`_resolve_resource_and_perm()`) only when a protected endpoint's intended permission differs from the generic `<resource>_<verb>` fallback; otherwise keep the fallback.
- Request/response models live in `app/schemas.py`; keep validators aligned with the DB enums and the accepted method names.
- Keep service/config mutations on the API path that marks changes for the Scheduler — bypassing it produces a DB write no instance ever sees.
- Instance broadcasts go through `ApiCaller`; a single-instance failure aggregates into a 502 for the caller.

## Architecture

### Startup

1. `entrypoint.sh` launches Gunicorn with the custom Uvicorn worker (`utils/worker.py`).
2. `utils/gunicorn.conf.py::on_starting()` runs **pre-fork**: Biscuit EdDSA keys, API user create/update, ACL cache file, permission bootstrap.
3. `app/main.py::create_app()` mounts middleware (IP whitelist, rate limiter, rate-limit headers), includes the core router, discovers plugin routers, registers error handlers.

### Request lifecycle

```
Request -> IP whitelist (middleware) -> rate limiter -> route match
        -> auth guard (per-endpoint dep) -> handler
        -> rate-limit headers (middleware) -> error normalization -> response
```

All errors normalize to `{"status": "error", "message": "..."}`.

### Three-tier authentication (`app/auth/guard.py`)

1. **HTTP Basic** — must match an admin API user (bcrypt, 30s cache).
2. **Bearer `API_TOKEN`** — env-provided token, full admin access.
3. **Biscuit token** — EdDSA-signed, issued at `POST /auth`, verified with freshness + IP binding + per-resource ACL facts `api_perm(resource_type, resource_id | "*", permission)`.

### Plugin-shipped routers

`app/routers/plugin_loader.py` mounts the `api/router.py` of every plugin declaring `extensions.api`, at `/<plugin_id>`, with the auth guard and rate limiter injected at mount time. The tier/integrity gate runs **before** the plugin's Python is imported; a colliding prefix is refused; a broken plugin is logged and skipped without taking the API down.

### Configuration (`app/config.py`)

`ApiConfig` (Pydantic `YamlBaseSettings`) resolves in precedence order: environment variables, Docker secrets (`/run/secrets`), YAML (`/etc/bunkerweb/api.yml`), env file (`/etc/bunkerweb/api.env`), defaults. Booleans accept `yes/no/true/false/1/0/on/off`.

### Shared code

The API imports the monorepo's shared modules via `sys.path` manipulation using container paths under `/usr/share/bunkerweb/`: `Database` and `model` from `src/common/db/`, `API`/`ApiCaller` from `src/common/api/`, `common_utils` and `logger` from `src/common/utils/`. API-specific persistence is `app/models/api_database.py` (users and permissions).

`app/utils.py` holds the lazy, pooled singletons `get_db()` and `get_api_db()`, closed by the lifespan handler.

### Container paths

| Path                                          | Purpose                         |
| --------------------------------------------- | ------------------------------- |
| `/var/lib/bunkerweb/.api_biscuit_public_key`  | Biscuit public key              |
| `/var/lib/bunkerweb/.api_biscuit_private_key` | Biscuit private key             |
| `/var/lib/bunkerweb/api_acl.json`             | ACL cache, generated at startup |
| `/var/lib/bunkerweb/api_acl_bootstrap.json`   | Optional ACL bootstrap          |
| `/var/tmp/bunkerweb/api.healthy`              | Health file, created when ready |
| `/etc/bunkerweb/api.yml`                      | YAML config                     |

## Commands

```bash
pip install --require-hashes -r src/api/requirements.txt   # compiled from requirements.in

docker compose -f misc/dev/docker-compose.api.yml up -d        # BunkerWeb, API, Scheduler, Worker, broker, MariaDB, test upstream
docker compose -f misc/dev/docker-compose.api.misc.yml up -d   # + Redis
docker compose -f misc/dev/docker-compose.ui.api.yml up -d     # full stack

pre-commit run --all-files
./tests/scripts/test.sh docker core dev <category>   # see tests/AGENTS.md
```

Dev compose mounts `app/` and `utils/` read-only; with `DEBUG=1` (the compose default) Gunicorn reloads workers on change. A restart is only needed with `DEBUG` off or when editing `entrypoint.sh`/`gunicorn.conf.py`. Dev credentials: `admin`/`P@ssw0rd`.

Unit tests for `APIDatabase` and the `schemas.py` validators live in `tests/unit/api/`; behavior is covered by the Docker integration run.

`celery` is deliberately absent from `requirements.in` — it is installed into the image from `src/worker/requirements.txt` at build time and used lazily by the jobs router through `app/celery_app.py`.

## Runtime Gotchas

- **Biscuit freshness and IP binding** (`app/auth/biscuit.py`): `API_BISCUIT_TTL_SECONDS` defaults to 3600; `off`/`disabled`/`0` disables expiry. IP binding is enforced unless the caller is a private IP **and** `CHECK_PRIVATE_IP=no`.
- **Instance broadcasting** (`app/deps.py`, `ApiCaller.send_to_apis`): `get_instances_api_caller()` rebuilds the caller from the DB on **every** request and falls back to the internal API if the DB is down. Broadcasts are single-pass with a default 5s timeout (`API_HTTP_TIMEOUT`) and no retry.
- **Bulk-operation method guard**: service/config mutations only accept `method ∈ {autoconf, scheduler, manual, ui, wizard}` so one component cannot clobber another's records. Extending the set means updating both the validator and the DB enums.
- **Startup hard-exits** (`utils/gunicorn.conf.py::on_starting`): `exit(1)` if Biscuit keys fail to load, DB init exceeds 60s, or no auth method is configured (no API users **and** no `API_TOKEN`). `OVERRIDE_API_CREDS=yes` makes env credentials overwrite the DB record on boot. `API_ACL_BOOTSTRAP_FILE` seeds users and permissions and accepts either a dict or a list for the permissions block.
- **Rate limiting** (`app/rate_limit.py`, configured through `API_RATE_LIMIT_*`) accepts several syntaxes (`10/hour`, NGINX-style `100r/m`), path patterns with wildcards or regex, method filters and IP exemptions. **Wildcard rules are shell-glob, not regex**, unless flagged as regex. `API_ROOT_PATH` is stripped before matching. For Redis Sentinel, master auth goes in the main URI and Sentinel auth in `sentinel_kwargs`.
- **Custom config types** accept both hyphen and underscore variants (`server-http`/`server_http`), normalized to underscores internally.
- `GET /openapi.yaml` is a custom endpoint alongside the standard `/openapi.json`.
