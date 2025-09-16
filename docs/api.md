# API

## Overview

The BunkerWeb API is the control plane used to manage BunkerWeb instances programmatically: list and manage instances, reload/stop, handle bans, plugins, jobs, configs, and more. It exposes a documented FastAPI application with strong authentication, authorization and rate limiting.

Open the interactive documentation at `/docs` (or `<root_path>/docs` if you set `API_ROOT_PATH`). The OpenAPI schema is available at `/openapi.json`.

!!! warning "Security"
    The API is a privileged control plane. Do not expose it on the public Internet without additional protections.

    At a minimum, restrict source IPs (`API_WHITELIST_IPS`), enable authentication (`API_TOKEN` or API users + Biscuit), and consider putting it behind BunkerWeb with an unguessable path and extra access controls.

## Prerequisites

The API service requires access to the BunkerWeb database (`DATABASE_URI`). It is usually deployed alongside the Scheduler and optionally the Web UI. The recommended setup is to run BunkerWeb in front as a reverse proxy and isolate the API on an internal network.

See the quickstart wizard and architecture guidance in the [quickstart guide](quickstart-guide.md).

## Highlights

- Instance‑aware: broadcasts operational actions to discovered instances.
- Strong auth: Basic for admins, Bearer admin override, or Biscuit ACL for fine‑grained permissions.
- IP allowlist and flexible per‑route rate limiting.
- Standard health/readiness signals and startup safety checks.

## Compose boilerplates

=== "Docker"

    Reverse proxy the API under `/api` with BunkerWeb.

    ```yaml
    x-bw-env: &bw-env
      # Shared instance control-plane allowlist for BunkerWeb/Scheduler
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp"  # QUIC
        environment:
          <<: *bw-env
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb"  # Match the instance service name
          SERVER_NAME: "www.example.com"
          MULTISITE: "yes"
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"
          DISABLE_DEFAULT_SERVER: "yes"
          # Reverse-proxy the API on /api
          www.example.com_USE_REVERSE_PROXY: "yes"
          www.example.com_REVERSE_PROXY_URL: "/api"
          www.example.com_REVERSE_PROXY_HOST: "http://bw-api:8888"
        volumes:
          - bw-storage:/data
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.6.5-rc3
        environment:
          DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"  # Use a strong password
          API_WHITELIST_IPS: "127.0.0.0/8 10.20.30.0/24"                      # API allowlist
          API_TOKEN: "secret"                                                 # Optional admin override token
          API_ROOT_PATH: "/api"                                               # Match reverse-proxy path
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # Avoid issues with large queries
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme"  # Use a strong password
        volumes:
          - bw-data:/var/lib/mysql
        restart: unless-stopped
        networks:
          - bw-db

    volumes:
      bw-data:
      bw-storage:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "Docker Autoconf"

    Same as above but leveraging the Autoconf service to discover and configure services automatically. The API is exposed under `/api` using labels on the API container.

    ```yaml
    x-api-env: &api-env
      AUTOCONF_MODE: "yes"
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db"  # Use a strong password

    services:
      bunkerweb:
        image: bunkerity/bunkerweb:1.6.5-rc3
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp"  # QUIC
        environment:
          AUTOCONF_MODE: "yes"
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.5-rc3
        environment:
          <<: *api-env
          BUNKERWEB_INSTANCES: ""    # Discovered by Autoconf
          SERVER_NAME: ""            # Filled via labels
          MULTISITE: "yes"           # Mandatory with Autoconf
          API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24"
        volumes:
          - bw-storage:/data
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-autoconf:
        image: bunkerity/bunkerweb-autoconf:1.6.5-rc3
        depends_on:
          - bunkerweb
          - bw-docker
        environment:
          <<: *api-env
          DOCKER_HOST: "tcp://bw-docker:2375"
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-docker
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.6.5-rc3
        environment:
          <<: *api-env
          API_WHITELIST_IPS: "127.0.0.0/8 10.20.30.0/24"
          API_TOKEN: "secret"
          API_ROOT_PATH: "/api"
        labels:
          - "bunkerweb.SERVER_NAME=www.example.com"
          - "bunkerweb.USE_REVERSE_PROXY=yes"
          - "bunkerweb.REVERSE_PROXY_URL=/api"
          - "bunkerweb.REVERSE_PROXY_HOST=http://bw-api:8888"
        restart: unless-stopped
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme"
        volumes:
          - bw-data:/var/lib/mysql
        restart: unless-stopped
        networks:
          - bw-db

      bw-docker:
        image: tecnativa/docker-socket-proxy:nightly
        environment:
          CONTAINERS: "1"
          LOG_LEVEL: "warning"
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock:ro
        restart: unless-stopped
        networks:
          - bw-docker

    volumes:
      bw-data:
      bw-storage:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
      bw-docker:
        name: bw-docker
    ```

!!! warning "Reverse proxy path"
    Keep the API path unguessable and combine with the API allowlist and authentication.

    If you already expose another app on the same server name with a template (e.g. `USE_TEMPLATE`), prefer a separate hostname for the API to avoid conflicts.

### All‑In‑One

If you use the All‑In‑One image, the API can be enabled by setting `SERVICE_API=yes`:

```bash
docker run -d \
  --name bunkerweb-aio \
  -e SERVICE_API=yes \
  -e API_WHITELIST_IPS="127.0.0.0/8" \
  -p 80:8080/tcp -p 443:8443/tcp -p 443:8443/udp \
  bunkerity/bunkerweb-all-in-one:1.6.5-rc3
```

## Authentication

Supported ways to authenticate requests:

- Basic admin: When credentials belong to an admin API user, protected endpoints accept `Authorization: Basic <base64(username:password)>`.
- Admin Bearer override: If `API_TOKEN` is configured, `Authorization: Bearer <API_TOKEN>` grants full access.
- Biscuit token (recommended): Obtain a token from `POST /auth` using Basic credentials or a JSON/form body containing `username` and `password`. Use the returned token as `Authorization: Bearer <token>` on subsequent calls.

Example: get a Biscuit, list instances, then reload all instances.

```bash
# 1) Get a Biscuit token with admin credentials
TOKEN=$(curl -s -X POST -u admin:changeme http://api.example.com/auth | jq -r .token)

# 2) List instances
curl -H "Authorization: Bearer $TOKEN" http://api.example.com/instances

# 3) Reload configuration across all instances (no test)
curl -X POST -H "Authorization: Bearer $TOKEN" \
     "http://api.example.com/instances/reload?test=no"
```

### Biscuit facts and checks

Tokens embed facts like `user(<username>)`, `client_ip(<ip>)`, `domain(<host>)`, and a coarse role `role("api_user", ["read", "write"])` derived from DB permissions. Admins include `admin(true)` while non‑admins carry fine‑grained facts such as `api_perm(<resource_type>, <resource_id|*>, <permission>)`.

Authorization maps the route/method to required permissions; `admin(true)` always passes. When fine‑grained facts are absent, the guard falls back to the coarse role: GET/HEAD/OPTIONS require `read`; write verbs require `write`.

Keys are stored at `/var/lib/bunkerweb/.api_biscuit_private_key` and `/var/lib/bunkerweb/.api_biscuit_public_key`. You can also provide `BISCUIT_PUBLIC_KEY`/`BISCUIT_PRIVATE_KEY` via environment variables; if neither files nor env are set, the API generates a key pair at startup and persists it securely.

## Permissions (ACL)

This API supports two authorization layers:

- Coarse role: Tokens carry `role("api_user", ["read"[, "write"]])` for endpoints without a fine‑grained mapping. Read maps to GET/HEAD/OPTIONS; write maps to POST/PUT/PATCH/DELETE.
- Fine‑grained ACL: Tokens embed `api_perm(<resource_type>, <resource_id|*>, <permission>)` and routes declare what they require. `admin(true)` bypasses all checks.

Supported resource types: `instances`, `global_config`, `services`, `configs`, `plugins`, `cache`, `bans`, `jobs`.

Permission names by resource type:

- instances: `instances_read`, `instances_update`, `instances_delete`, `instances_create`, `instances_execute`
- global_config: `global_config_read`, `global_config_update`
- services: `service_read`, `service_create`, `service_update`, `service_delete`, `service_convert`, `service_export`
- configs: `configs_read`, `config_read`, `config_create`, `config_update`, `config_delete`
- plugins: `plugin_read`, `plugin_create`, `plugin_delete`
- cache: `cache_read`, `cache_delete`
- bans: `ban_read`, `ban_update`, `ban_delete`, `ban_created`
- jobs: `job_read`, `job_run`

Resource IDs: For fine‑grained checks, the second path segment is treated as `resource_id` when meaningful. Examples: `/services/{service}` -> `{service}`; `/configs/{service}/...` -> `{service}`. Use `"*"` (or omit) to grant globally for a resource type.

User and ACL configuration:

- Admin user: Set `API_USERNAME` and `API_PASSWORD` to create the first admin at startup. To rotate creds later, set `OVERRIDE_API_CREDS=yes` (or ensure the admin was created with method `manual`). Only one admin exists; additional attempts fall back to non‑admin creation.
- Non‑admin users and grants: Provide `API_ACL_BOOTSTRAP_FILE` pointing to a JSON file, or mount `/var/lib/bunkerweb/api_acl_bootstrap.json`. The API reads it at startup to create/update users and permissions.
- ACL cache file: A read‑only summary is written at `/var/lib/bunkerweb/api_acl.json` at startup for introspection; authorization evaluates DB‑backed grants baked into the Biscuit token.

Bootstrap JSON examples (both forms supported):

```json
{
  "users": {
    "ci": {
      "admin": false,
      "password": "Str0ng&P@ss!",
      "permissions": {
        "services": {
          "*": { "service_read": true },
          "app-frontend": { "service_update": true, "service_delete": false }
        },
        "configs": {
          "app-frontend": { "config_read": true, "config_update": true }
        }
      }
    },
    "ops": {
      "admin": false,
      "password_hash": "$2b$13$...bcrypt-hash...",
      "permissions": {
        "instances": { "*": { "instances_execute": true } },
        "jobs": { "*": { "job_run": true } }
      }
    }
  }
}
```

Or list form:

```json
{
  "users": [
    {
      "username": "ci",
      "password": "Str0ng&P@ss!",
      "permissions": [
        { "resource_type": "services", "resource_id": "*", "permission": "service_read" },
        { "resource_type": "services", "resource_id": "app-frontend", "permission": "service_update" }
      ]
    }
  ]
}
```

Notes:

- Passwords may be plaintext (`password`) or bcrypt (`password_hash` / `password_bcrypt`). Weak plaintext passwords are rejected in non‑debug builds; if missing, a random one is generated and a warning is logged.
- `resource_id: "*"` (or null/empty) grants globally on that resource type.
- Existing users can have passwords updated and additional grants applied via bootstrap.

## Feature reference

The API is organised by resource-focused routers. Use the sections below as a capability map; the interactive schema at `/docs` documents request/response models in detail.

### Core and authentication

- `GET /ping`, `GET /health`: lightweight liveness probes for the API service itself.
- `POST /auth`: exchange Basic credentials (or the admin override token) for a Biscuit. Accepts JSON, form, or `Authorization` headers. Admins may also continue using HTTP Basic directly on protected routes when desired.

### Instances control plane

- `GET /instances`: list registered instances, including creation/last-seen timestamps, registration method, and metadata.
- `POST /instances`: register a new API-managed instance (hostname, optional port, server name, friendly name, method).
- `GET /instances/{hostname}` / `PATCH /instances/{hostname}` / `DELETE /instances/{hostname}`: inspect, update mutable fields, or remove API-managed instances.
- `DELETE /instances`: bulk removal; skips non-API instances and reports them in `skipped`.
- `GET /instances/ping` and `GET /instances/{hostname}/ping`: health checks across all or individual instances.
- `POST /instances/reload?test=yes|no`, `POST /instances/{hostname}/reload`: trigger configuration reloads (test mode performs dry-run validation).
- `POST /instances/stop`, `POST /instances/{hostname}/stop`: relay stop commands to instances.

### Global configuration

- `GET /global_config`: fetch non-default settings (use `full=true` for the entire config, `methods=true` to include provenance).
- `PATCH /global_config`: upsert API-owned (`method="api"`) global settings; validation errors call out unknown or read-only keys.

### Service lifecycle

- `GET /services`: enumerate services with metadata, including draft status and timestamps.
- `GET /services/{service}`: retrieve non-default overlays (`full=false`) or the full config snapshot (`full=true`) for a service.
- `POST /services`: create services, optionally as draft, and seed prefixed variables (`{service}_{KEY}`). Updates the `SERVER_NAME` roster atomically.
- `PATCH /services/{service}`: rename services, toggle draft flags, and update prefixed variables. Ignores direct edits to `SERVER_NAME` within `variables` for safety.
- `DELETE /services/{service}`: remove a service and its derived configuration keys.
- `POST /services/{service}/convert?convert_to=online|draft`: quickly switch draft/online state without altering other variables.

### Custom configuration snippets

- `GET /configs`: list custom config fragments (HTTP/server/stream/ModSecurity/CRS hooks) for a service (`service=global` by default). `with_data=true` embeds UTF-8 content when printable.
- `POST /configs` and `POST /configs/upload`: create new snippets from JSON payloads or uploaded files. Accepted types include `http`, `server_http`, `default_server_http`, `modsec`, `modsec_crs`, `stream`, `server_stream`, and CRS plugin hooks. Names must match `^[\w_-]{1,64}$`.
- `GET /configs/{service}/{type}/{name}`: retrieve a snippet with optional content (`with_data=true`).
- `PATCH /configs/{service}/{type}/{name}` and `PATCH .../upload`: update or move API-managed snippets; template- or file-managed entries stay read-only.
- `DELETE /configs` and `DELETE /configs/{service}/{type}/{name}`: prune API-managed snippets while preserving template-managed ones, returning a `skipped` list for ignored entries.

### Ban orchestration

- `GET /bans`: aggregate active bans reported by all instances.
- `POST /bans` or `POST /bans/ban`: apply one or multiple bans. Payloads may be JSON objects, arrays, or stringified JSON. `service` is optional; when omitted the ban is global.
- `POST /bans/unban` or `DELETE /bans`: remove bans globally or per service using the same flexible payloads.

### Plugin management

- `GET /plugins?type=all|external|ui|pro`: list plugins with metadata; `with_data=true` includes packaged bytes when available.
- `POST /plugins/upload`: install UI plugins from `.zip`, `.tar.gz`, or `.tar.xz` archives. Archives may bundle multiple plugins as long as each contains a `plugin.json`.
- `DELETE /plugins/{id}`: remove a UI plugin by ID (`^[\w.-]{4,64}$`).

### Job cache and execution

- `GET /cache`: list cached artifacts produced by scheduler jobs, filtered by service, plugin ID, or job name. `with_data=true` includes printable file content.
- `GET /cache/{service}/{plugin}/{job}/{file}`: fetch a specific cache file (`download=true` streams an attachment).
- `DELETE /cache` or `DELETE /cache/{service}/{plugin}/{job}/{file}`: delete cache files and notify the scheduler about affected plugins.
- `GET /jobs`: inspect known jobs, their schedule metadata, and cache summaries.
- `POST /jobs/run`: request job execution by flagging the associated plugin(s) as changed.

### Operational notes

- Write endpoints persist to the shared database; instances pick up changes via scheduler sync or after a `/instances/reload`.
- Errors are normalised to `{ "status": "error", "message": "..." }` with appropriate HTTP status codes (422 validation, 404 not found, 403 ACL, 5xx upstream failures).

## Rate limiting

Per‑client rate limiting is handled by SlowAPI. Enable/disable it and shape limits via environment variables or `/etc/bunkerweb/api.yml`.

- `API_RATE_LIMIT_ENABLED` (default: `yes`)
- Default limit: `API_RATE_LIMIT_TIMES` per `API_RATE_LIMIT_SECONDS` (e.g. `100` per `60`)
- `API_RATE_LIMIT_RULES`: inline JSON/CSV, or a path to a YAML/JSON file with per‑route rules
- Storage backend: in‑memory or Redis/Valkey when `USE_REDIS=yes` and `REDIS_*` variables are provided (Sentinel supported)
- Headers: `API_RATE_LIMIT_HEADERS_ENABLED` (default: `yes`)

Example YAML (mounted at `/etc/bunkerweb/api.yml`):

```yaml
API_RATE_LIMIT_ENABLED: yes
API_RATE_LIMIT_DEFAULTS: ["200/minute"]
API_RATE_LIMIT_RULES:
  - path: "/auth"
    methods: "POST"
    times: 10
    seconds: 60
  - path: "/instances*"
    methods: "GET|POST"
    times: 100
    seconds: 60
```

## Configuration

You can configure the API via environment variables, Docker secrets, and the optional `/etc/bunkerweb/api.yml` or `/etc/bunkerweb/api.env` files. Key settings:

- Docs & schema: `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL`, `API_ROOT_PATH`.
- Auth basics: `API_TOKEN` (admin override Bearer), `API_USERNAME`/`API_PASSWORD` (create/update admin), `OVERRIDE_API_CREDS`.
- ACL and users: `API_ACL_BOOTSTRAP_FILE` (JSON path).
- Biscuit policy: `API_BISCUIT_TTL_SECONDS` (0/off disables TTL), `CHECK_PRIVATE_IP` (bind token to client IP unless private).
- IP allowlist: `API_WHITELIST_ENABLED`, `API_WHITELIST_IPS`.
- Rate limiting (core): `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_TIMES`, `API_RATE_LIMIT_SECONDS`, `API_RATE_LIMIT_HEADERS_ENABLED`.
- Rate limiting (advanced): `API_RATE_LIMIT_AUTH_TIMES`, `API_RATE_LIMIT_AUTH_SECONDS`, `API_RATE_LIMIT_RULES`, `API_RATE_LIMIT_DEFAULTS`, `API_RATE_LIMIT_APPLICATION_LIMITS`, `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`, `API_RATE_LIMIT_STORAGE_OPTIONS`.
- Rate limiting storage: in‑memory or Redis/Valkey when `USE_REDIS=yes` and Redis settings like `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DATABASE`, `REDIS_SSL`, or Sentinel variables are set. See the Redis settings table in `docs/features.md`.
- Network/TLS: `API_LISTEN_ADDR`, `API_LISTEN_PORT`, `API_FORWARDED_ALLOW_IPS`, `API_SSL_ENABLED`, `API_SSL_CERTFILE`, `API_SSL_KEYFILE`, `API_SSL_CA_CERTS`.

### How configuration is loaded

Precedence from highest to lowest:

- Environment variables (e.g. container `environment:` or exported shell vars)
- Secrets files under `/run/secrets` (Docker/K8s secrets; filenames match variable names)
- YAML file at `/etc/bunkerweb/api.yml`
- Env file at `/etc/bunkerweb/api.env` (key=value lines)
- Built‑in defaults

Notes:

- YAML supports inlining secret files with `<file:relative/path>`; the path is resolved against `/run/secrets`.
- Set doc URLs to `off`/`disabled`/`none` to disable endpoints (e.g. `API_DOCS_URL=off`).
- If `API_SSL_ENABLED=yes`, you must also set `API_SSL_CERTFILE` and `API_SSL_KEYFILE`.
- If Redis is enabled (`USE_REDIS=yes`), provide Redis details; see Redis section in `docs/features.md`.

### Authentication and users

- Admin bootstrap: set `API_USERNAME` and `API_PASSWORD` to create the first admin. To re‑apply later, set `OVERRIDE_API_CREDS=yes`.
- Non‑admins and permissions: provide `API_ACL_BOOTSTRAP_FILE` with a JSON path (or mount to `/var/lib/bunkerweb/api_acl_bootstrap.json`). The file may list users and fine‑grained grants.
- Biscuit keys: either set `BISCUIT_PUBLIC_KEY`/`BISCUIT_PRIVATE_KEY` or mount files at `/var/lib/bunkerweb/.api_biscuit_public_key` and `/var/lib/bunkerweb/.api_biscuit_private_key`. If none are provided, the API generates and persists a key pair at startup.

### TLS and networking

- Bind address/port: `API_LISTEN_ADDR` (default `0.0.0.0`), `API_LISTEN_PORT` (default `8888`).
- Reverse proxies: set `API_FORWARDED_ALLOW_IPS` to the proxy IPs so Gunicorn trusts `X‑Forwarded‑*` headers.
- TLS termination in the API: `API_SSL_ENABLED=yes` plus `API_SSL_CERTFILE` and `API_SSL_KEYFILE`; optional `API_SSL_CA_CERTS`

### Rate limiting quick recipes

- Disable globally: `API_RATE_LIMIT_ENABLED=no`
- Set a simple global limit: `API_RATE_LIMIT_TIMES=100`, `API_RATE_LIMIT_SECONDS=60`
- Per‑route rules: set `API_RATE_LIMIT_RULES` to a JSON/YAML file path or inline YAML in `/etc/bunkerweb/api.yml`.

!!! warning "Startup safety"
    The API exits if there is no authentication path configured (no Biscuit keys, no admin user, and no `API_TOKEN`). Ensure at least one method is set before starting.

Startup safety: The API exits if no authentication path is available (no Biscuit keys, no admin API user, and no `API_TOKEN`). Ensure at least one is configured.

!!! info "Root path and proxies"
    If you deploy the API behind BunkerWeb on a sub‑path, set `API_ROOT_PATH` to that path so `/docs` and relative routes work correctly when proxied.

## Operations

- Health: `GET /health` returns `{"status":"ok"}` when the service is up.
- Linux service: a `systemd` unit named `bunkerweb-api.service` is packaged. Customize via `/etc/bunkerweb/api.env` and manage with `systemctl`.
- Startup safety: the API fails fast when no authentication path is available (no Biscuit keys, no admin user, no `API_TOKEN`). Errors are written to `/var/tmp/bunkerweb/api.error`.
