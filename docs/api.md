# API

## Role of the API

The BunkerWeb API is the control plane for managing instances, services, bans, plugins, jobs, and custom configs. It runs as a FastAPI app behind Gunicorn and should stay on a trusted network. Interactive docs live at `/docs` (or `<API_ROOT_PATH>/docs`); the OpenAPI schema is at `/openapi.json`.

!!! warning "Keep it private"
    Do not expose the API directly to the Internet. Keep it on an internal network, restrict source IPs, and require authentication.

!!! info "Quick facts"
    - Health endpoints: `GET /ping` and `GET /health`
    - Root path: set `API_ROOT_PATH` when reverse-proxying on a sub-path so docs and OpenAPI links work
    - Auth is mandatory: Biscuit tokens, admin Basic, or an override Bearer token
    - IP allowlist defaults to RFC1918 ranges (`API_WHITELIST_IPS`); disable only if upstream controls access
    - Rate limiting defaults on; `/auth` always has its own limit

## Security checklist

- Network: keep traffic internal; bind to loopback or an internal interface and restrict source IPs with `API_WHITELIST_IPS` (enabled by default).
- Auth present: set `API_USERNAME`/`API_PASSWORD` (admin) and, if needed, `API_ACL_BOOTSTRAP_FILE` for extra users/ACLs; keep an override `API_TOKEN` only for break-glass use.
- Path hiding: when reverse-proxying, pick an unguessable `API_ROOT_PATH` and mirror it on the proxy.
- Rate limiting: leave it on unless another layer enforces equivalent limits; `/auth` is always rate limited.
- TLS: terminate TLS at the proxy or set `API_SSL_ENABLED=yes` with cert/key paths.

## Run it

Choose the flavor that matches your environment.

=== "Docker"

    Minimal Compose-style layout with the API behind BunkerWeb. Adjust versions and passwords before use.

    ```yaml
    x-bw-env: &bw-env
      # We use an anchor to avoid repeating the same settings for both services
      API_WHITELIST_IP: "127.0.0.0/8 10.20.30.0/24" # Make sure to set the correct IP range so the scheduler can send the configuration to the instance (internal BunkerWeb API)
      # Optional: set an API token and mirror it in both containers (internal BunkerWeb API)
      API_TOKEN: ""
      DATABASE_URI: "mariadb+pymysql://bunkerweb:changeme@bw-db:3306/db" # Remember to set a stronger password for the database

    services:
      bunkerweb:
        # This is the name that will be used to identify the instance in the Scheduler
        image: bunkerity/bunkerweb:1.6.7~rc1
        ports:
          - "80:8080/tcp"
          - "443:8443/tcp"
          - "443:8443/udp" # For QUIC / HTTP3 support
        environment:
          <<: *bw-env # We use the anchor to avoid repeating the same settings for all services
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-services

      bw-scheduler:
        image: bunkerity/bunkerweb-scheduler:1.6.7~rc1
        environment:
          <<: *bw-env
          BUNKERWEB_INSTANCES: "bunkerweb" # Make sure to set the correct instance name
          SERVER_NAME: "api.example.com"
          MULTISITE: "yes"
          USE_REDIS: "yes"
          REDIS_HOST: "redis"
          DISABLE_DEFAULT_SERVER: "yes"
          AUTO_LETS_ENCRYPT: "yes"
          api.example.com_USE_TEMPLATE: "api"
          api.example.com_USE_REVERSE_PROXY: "yes"
          api.example.com_REVERSE_PROXY_URL: "/"
          api.example.com_REVERSE_PROXY_HOST: "http://bw-api:8888"
        volumes:
          - bw-storage:/data # This is used to persist the cache and other data like the backups
        restart: "unless-stopped"
        networks:
          - bw-universe
          - bw-db

      bw-api:
        image: bunkerity/bunkerweb-api:1.6.7~rc1
        environment:
          <<: *bw-env
          API_USERNAME: "admin"
          API_PASSWORD: "Str0ng&P@ss!"
          # API_TOKEN: "admin-override-token" # optional
          FORWARDED_ALLOW_IPS: "*" # Be careful with this setting; only use it if you are sure that the reverse proxy is the only way to access the API
          API_ROOT_PATH: "/"
        networks:
          - bw-universe
          - bw-db

      bw-db:
        image: mariadb:11
        # We set the max allowed packet size to avoid issues with large queries
        command: --max-allowed-packet=67108864
        environment:
          MYSQL_RANDOM_ROOT_PASSWORD: "yes"
          MYSQL_DATABASE: "db"
          MYSQL_USER: "bunkerweb"
          MYSQL_PASSWORD: "changeme" # Remember to set a stronger password for the database
        volumes:
          - bw-data:/var/lib/mysql
        restart: "unless-stopped"
        networks:
          - bw-db

      redis: # Redis service for the persistence of reports/bans/stats
        image: redis:8-alpine
        command: >
          redis-server
          --maxmemory 256mb
          --maxmemory-policy allkeys-lru
          --save 60 1000
          --appendonly yes
        volumes:
          - redis-data:/data
        restart: "unless-stopped"
        networks:
          - bw-universe

    volumes:
      bw-data:
      bw-storage:
      redis-data:

    networks:
      bw-universe:
        name: bw-universe
        ipam:
          driver: default
          config:
            - subnet: 10.20.30.0/24 # Make sure to set the correct IP range so the scheduler can send the configuration to the instance
      bw-services:
        name: bw-services
      bw-db:
        name: bw-db
    ```

=== "All-in-One"

    ```bash
    docker run -d \
      --name bunkerweb-aio \
      -e SERVICE_API=yes \
      -e API_WHITELIST_IPS="127.0.0.0/8" \
      -p 80:8080/tcp -p 443:8443/tcp -p 443:8443/udp \
      bunkerity/bunkerweb-all-in-one:1.6.7~rc1
    ```

=== "Linux"

    The DEB/RPM packages ship `bunkerweb-api.service`, managed through `/usr/share/bunkerweb/scripts/bunkerweb-api.sh`.

    - Enable/start: `sudo systemctl enable --now bunkerweb-api.service`
    - Reload: `sudo systemctl reload bunkerweb-api.service`
    - Logs: journal plus `/var/log/bunkerweb/api.log`
    - Default listen: `127.0.0.1:8888` with `API_WHITELIST_IPS=127.0.0.1`
    - Config files: `/etc/bunkerweb/api.env` (auto-created with commented defaults on first start) and `/etc/bunkerweb/api.yml`
    - Environment sources: `api.env`, `variables.env`, `/run/secrets/<VAR>`, then exported to the Gunicorn process

    Edit `/etc/bunkerweb/api.env` to set `API_USERNAME`/`API_PASSWORD`, allowlist, TLS, rate limits, or `API_ROOT_PATH`, then `systemctl reload bunkerweb-api`.

## Authentication and authorization

- `/auth` issues Biscuit tokens. Credentials can come from Basic auth, form fields, JSON body, or a Bearer header equal to `API_TOKEN` (admin override).
- Admin users can also call protected routes directly with HTTP Basic (no Biscuit needed).
- If the Bearer token matches `API_TOKEN`, access is full/admin. Otherwise the Biscuit guard enforces ACL.
- Biscuit payload includes user, time, client IP, host, version, a coarse `role("api_user", ["read", "write"])`, and either `admin(true)` or fine-grained `api_perm(resource_type, resource_id|*, permission)`.
- TTL is `API_BISCUIT_TTL_SECONDS` (0/off disables expiry). Keys live at `/var/lib/bunkerweb/.api_biscuit_private_key` and `.api_biscuit_public_key` unless provided via `BISCUIT_PRIVATE_KEY`/`BISCUIT_PUBLIC_KEY`.
- Auth endpoints are exposed only when at least one API user exists in the database.

!!! tip "Auth quickstart"
    1. Set `API_USERNAME` and `API_PASSWORD` (and `OVERRIDE_API_CREDS=yes` if you need to re-seed).
    2. Call `POST /auth` with Basic auth; read `.token` from the response.
    3. Use `Authorization: Bearer <token>` on subsequent calls.

## Permissions and ACL

- Coarse role: GET/HEAD/OPTIONS require `read`; write verbs require `write`.
- Fine-grained ACL is enforced when routes declare required permissions; `admin(true)` bypasses checks.
- Resource types: `instances`, `global_settings`, `services`, `configs`, `plugins`, `cache`, `bans`, `jobs`.
- Permission names:
  - `instances_*`: `instances_read`, `instances_update`, `instances_delete`, `instances_create`, `instances_execute`
  - `global_settings_*`: `global_settings_read`, `global_settings_update`
  - `services`: `service_read`, `service_create`, `service_update`, `service_delete`, `service_convert`, `service_export`
  - `configs`: `configs_read`, `config_read`, `config_create`, `config_update`, `config_delete`
  - `plugins`: `plugin_read`, `plugin_create`, `plugin_delete`
  - `cache`: `cache_read`, `cache_delete`
  - `bans`: `ban_read`, `ban_update`, `ban_delete`, `ban_created`
  - `jobs`: `job_read`, `job_run`
- `resource_id` is usually the second path component (e.g. `/services/{id}`); `"*"` grants global access.
- Bootstrap non-admin users and grants with `API_ACL_BOOTSTRAP_FILE` or a mounted `/var/lib/bunkerweb/api_acl_bootstrap.json`. Passwords may be plaintext or bcrypt hashes.

??? example "Minimal ACL bootstrap"
    ```json
    {
      "users": {
        "ci": {
          "admin": false,
          "password": "Str0ng&P@ss!",
          "permissions": {
            "services": { "*": { "service_read": true } },
            "configs": { "*": { "config_read": true, "config_update": true } }
          }
        }
      }
    }
    ```

## Rate limiting

Enabled by default with two strings: `API_RATE_LIMIT` (global, default `100r/m`) and `API_RATE_LIMIT_AUTH` (default `10r/m` or `off`). Rates accept NGINX-style notation (`3r/s`, `40r/m`, `200r/h`) or verbose forms (`100/minute`, `200 per 30 minutes`). Configure via:

- `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`
- `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_HEADERS_ENABLED`
- `API_RATE_LIMIT_RULES` (CSV/JSON/YAML string or file path)
- `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`
- Storage is in-memory or Redis/Valkey when `USE_REDIS=yes` plus `REDIS_*` settings (Sentinel supported).

Limiter strategies (powered by `limits`):

- `fixed-window` (default): bucket resets at each interval boundary; cheapest and fine for coarse limits.
- `moving-window`: true rolling window using precise timestamps; smoother but heavier on storage operations.
- `sliding-window-counter`: hybrid that smooths with weighted counts from the previous window; lighter than moving but smoother than fixed.

More detail and trade-offs: [https://limits.readthedocs.io/en/stable/strategies.html](https://limits.readthedocs.io/en/stable/strategies.html)

??? example "Inline CSV"
    ```
    API_RATE_LIMIT_RULES='POST /auth 10r/m, GET /instances* 200r/m, POST|PATCH /services* 40r/m'
    ```

??? example "YAML file"
    ```yaml
    API_RATE_LIMIT: 200r/m
    API_RATE_LIMIT_AUTH: 15r/m
    API_RATE_LIMIT_RULES:
      - path: "/auth"
        methods: "POST"
        rate: "10r/m"
      - path: "/instances*"
        methods: "GET|POST"
        rate: "100r/m"
    ```

## Configuration sources and precedence

1. Environment variables (including Docker/Compose `environment:`)
2. Secrets in `/run/secrets/<VAR>` (Docker)
3. YAML at `/etc/bunkerweb/api.yml`
4. Env file at `/etc/bunkerweb/api.env`
5. Built-in defaults

### Runtime & time zone

| Setting | Description                                                                                    | Accepted values                                | Default                                |
| ------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------- | -------------------------------------- |
| `TZ`    | Time zone for API logs and time-based claims (e.g., Biscuit TTL evaluation and log timestamps) | TZ database name (e.g., `UTC`, `Europe/Paris`) | unset (container default, usually UTC) |

Disable docs or schema by setting their URLs to `off|disabled|none|false|0`. Set `API_SSL_ENABLED=yes` with `API_SSL_CERTFILE` and `API_SSL_KEYFILE` to terminate TLS in the API. When reverse-proxying, set `API_FORWARDED_ALLOW_IPS` to the proxy IPs so Gunicorn trusts `X-Forwarded-*` headers.

### Configuration reference (power users)

#### Surface & docs

| Setting                                            | Description                                                                                 | Accepted values           | Default                            |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------- | ---------------------------------- |
| `API_DOCS_URL`, `API_REDOC_URL`, `API_OPENAPI_URL` | Paths for Swagger, ReDoc, and OpenAPI schema; set to `off/disabled/none/false/0` to disable | Path or `off`             | `/docs`, `/redoc`, `/openapi.json` |
| `API_ROOT_PATH`                                    | Mount prefix when reverse-proxying                                                          | Path (e.g. `/api`)        | empty                              |
| `API_FORWARDED_ALLOW_IPS`                          | Trusted proxy IPs for `X-Forwarded-*`                                                       | Comma-separated IPs/CIDRs | `127.0.0.1` (package default)      |

#### Auth, ACL, Biscuit

| Setting                                     | Description                                | Accepted values                                                  | Default                  |
| ------------------------------------------- | ------------------------------------------ | ---------------------------------------------------------------- | ------------------------ |
| `API_USERNAME`, `API_PASSWORD`              | Bootstrap admin user                       | Strings; strong password required in non-debug                   | unset                    |
| `OVERRIDE_API_CREDS`                        | Re-apply admin creds on startup            | `yes/no/on/off/true/false/0/1`                                   | `no`                     |
| `API_TOKEN`                                 | Admin override Bearer token                | Opaque string                                                    | unset                    |
| `API_ACL_BOOTSTRAP_FILE`                    | Path to JSON for users/permissions         | File path or mounted `/var/lib/bunkerweb/api_acl_bootstrap.json` | unset                    |
| `BISCUIT_PRIVATE_KEY`, `BISCUIT_PUBLIC_KEY` | Biscuit keys (hex) if not using files      | Hex strings                                                      | auto-generated/persisted |
| `API_BISCUIT_TTL_SECONDS`                   | Token lifetime; `0/off` disables expiry    | Integer seconds or `off/disabled`                                | `3600`                   |
| `CHECK_PRIVATE_IP`                          | Bind Biscuit to client IP (except private) | `yes/no/on/off/true/false/0/1`                                   | `yes`                    |

#### Allowlist

| Setting                 | Description                     | Accepted values                | Default                |
| ----------------------- | ------------------------------- | ------------------------------ | ---------------------- |
| `API_WHITELIST_ENABLED` | Toggle IP allowlist middleware  | `yes/no/on/off/true/false/0/1` | `yes`                  |
| `API_WHITELIST_IPS`     | Space/comma-separated IPs/CIDRs | IPs/CIDRs                      | RFC1918 ranges in code |

#### Rate limiting

| Setting                          | Description                                 | Accepted values                                           | Default        |
| -------------------------------- | ------------------------------------------- | --------------------------------------------------------- | -------------- |
| `API_RATE_LIMIT`                 | Global limit (NGINX-style string)           | `3r/s`, `100/minute`, `500 per 30 minutes`                | `100r/m`       |
| `API_RATE_LIMIT_AUTH`            | `/auth` limit (or `off`)                    | same as above or `off/disabled/none/false/0`              | `10r/m`        |
| `API_RATE_LIMIT_ENABLED`         | Enable limiter                              | `yes/no/on/off/true/false/0/1`                            | `yes`          |
| `API_RATE_LIMIT_HEADERS_ENABLED` | Inject rate limit headers                   | same as above                                             | `yes`          |
| `API_RATE_LIMIT_RULES`           | Per-path rules (CSV/JSON/YAML or file path) | String or path                                            | unset          |
| `API_RATE_LIMIT_STRATEGY`        | Algorithm                                   | `fixed-window`, `moving-window`, `sliding-window-counter` | `fixed-window` |
| `API_RATE_LIMIT_KEY`             | Key selector                                | `ip`, `header:<Name>`                                     | `ip`           |
| `API_RATE_LIMIT_EXEMPT_IPS`      | Skip limits for these IPs/CIDRs             | Space/comma-separated                                     | unset          |
| `API_RATE_LIMIT_STORAGE_OPTIONS` | JSON merged into storage config             | JSON string                                               | unset          |

#### Redis/Valkey (for rate limits)

| Setting                                              | Description          | Accepted values                | Default            |
| ---------------------------------------------------- | -------------------- | ------------------------------ | ------------------ |
| `USE_REDIS`                                          | Enable Redis backend | `yes/no/on/off/true/false/0/1` | `no`               |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_DATABASE`         | Connection details   | Host, int, int                 | unset, `6379`, `0` |
| `REDIS_USERNAME`, `REDIS_PASSWORD`                   | Auth                 | Strings                        | unset              |
| `REDIS_SSL`, `REDIS_SSL_VERIFY`                      | TLS and verification | `yes/no/on/off/true/false/0/1` | `no`, `yes`        |
| `REDIS_TIMEOUT`                                      | Timeout (ms)         | Integer                        | `1000`             |
| `REDIS_KEEPALIVE_POOL`                               | Pool keepalive       | Integer                        | `10`               |
| `REDIS_SENTINEL_HOSTS`                               | Sentinel hosts       | Space-separated `host:port`    | unset              |
| `REDIS_SENTINEL_MASTER`                              | Sentinel master name | String                         | unset              |
| `REDIS_SENTINEL_USERNAME`, `REDIS_SENTINEL_PASSWORD` | Sentinel auth        | Strings                        | unset              |

!!! info "DB-provided Redis"
    If Redis/Valkey settings are present in the BunkerWeb database configuration, the API will automatically reuse them for rate limiting even without `USE_REDIS` set in the environment. Override via environment variables when you need a different backend.

#### Listener & TLS

| Setting                               | Description                    | Accepted values                | Default                              |
| ------------------------------------- | ------------------------------ | ------------------------------ | ------------------------------------ |
| `API_LISTEN_ADDR`, `API_LISTEN_PORT`  | Bind address/port for Gunicorn | IP or hostname, int            | `127.0.0.1`, `8888` (package script) |
| `API_SSL_ENABLED`                     | Enable TLS in API              | `yes/no/on/off/true/false/0/1` | `no`                                 |
| `API_SSL_CERTFILE`, `API_SSL_KEYFILE` | PEM cert and key paths         | File paths                     | unset                                |
| `API_SSL_CA_CERTS`                    | Optional CA/chain              | File path                      | unset                                |

#### Logging & runtime (package defaults)

| Setting                         | Description                                                                       | Accepted values                                 | Default                                                            |
| ------------------------------- | --------------------------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------ |
| `LOG_LEVEL`, `CUSTOM_LOG_LEVEL` | Base log level / override                                                         | `debug`, `info`, `warning`, `error`, `critical` | `info`                                                             |
| `LOG_TYPES`                     | Destinations                                                                      | Space-separated `stderr`/`file`/`syslog`        | `stderr`                                                           |
| `LOG_FILE_PATH`                 | Log file location (used when `LOG_TYPES` includes `file` or `CAPTURE_OUTPUT=yes`) | File path                                       | `/var/log/bunkerweb/api.log` when file/capture enabled, else unset |
| `LOG_SYSLOG_ADDRESS`            | Syslog target (`udp://host:514`, `tcp://host:514`, socket)                        | Host:port, proto-prefixed host, or socket path  | unset                                                              |
| `LOG_SYSLOG_TAG`                | Syslog tag                                                                        | String                                          | `bw-api`                                                           |
| `MAX_WORKERS`, `MAX_THREADS`    | Gunicorn workers/threads                                                          | Integer or unset for auto                       | unset                                                              |
| `CAPTURE_OUTPUT`                | Capture Gunicorn stdout/stderr into the configured handlers                       | `yes` or `no`                                   | `no`                                                               |

## API surface (capability map)

- **Core**
  - `GET /ping`, `GET /health`: liveness checks for the API itself.
- **Auth**
  - `POST /auth`: issue Biscuit tokens; accepts Basic, form, JSON, or Bearer override when `API_TOKEN` matches.
- **Instances**
  - `GET /instances`: list instances with creation/last-seen metadata.
  - `POST /instances`: register an instance (hostname/port/server_name/method).
  - `GET/PATCH/DELETE /instances/{hostname}`: inspect, update mutable fields, or delete API-managed instances.
  - `DELETE /instances`: bulk delete API-managed instances; non-API entries are skipped.
  - Health/actions: `GET /instances/ping`, `GET /instances/{hostname}/ping`, `POST /instances/reload?test=yes|no`, `POST /instances/{hostname}/reload`, `POST /instances/stop`, `POST /instances/{hostname}/stop`.
- **Global settings**
  - `GET /global_settings`: non-defaults by default; add `full=true` for all settings, `methods=true` to include provenance.
  - `PATCH /global_settings`: upsert API-owned globals; read-only keys are rejected.
- **Services**
  - `GET /services`: list services (include drafts by default).
  - `GET /services/{service}`: fetch non-defaults or full config (`full=true`); `methods=true` includes provenance.
  - `POST /services`: create a service (draft or online), set variables, and update `SERVER_NAME` roster atomically.
  - `PATCH /services/{service}`: rename, update variables, toggle draft.
  - `DELETE /services/{service}`: remove service and derived config keys.
  - `POST /services/{service}/convert?convert_to=online|draft`: switch draft/online quickly.
- **Custom configs**
  - `GET /configs`: list snippets (default service `global`); `with_data=true` embeds printable content.
  - `POST /configs`, `POST /configs/upload`: create snippets via JSON or file upload.
  - `GET /configs/{service}/{type}/{name}`: fetch snippet; `with_data=true` for content.
  - `PATCH /configs/{service}/{type}/{name}`, `PATCH .../upload`: update or move API-managed snippets.
  - `DELETE /configs` or `DELETE /configs/{service}/{type}/{name}`: remove API-managed snippets; template-managed entries are skipped.
  - Supported types: `http`, `server_http`, `default_server_http`, `modsec`, `modsec_crs`, `stream`, `server_stream`, CRS/plugin hooks.
- **Bans**
  - `GET /bans`: aggregate active bans from instances.
  - `POST /bans` or `/bans/ban`: apply one or more bans; payload can be object, array, or stringified JSON.
  - `POST /bans/unban` or `DELETE /bans`: remove bans globally or per service.
- **Plugins (UI plugins)**
  - `GET /plugins`: list plugins; `with_data=true` includes packaged bytes when available.
  - `POST /plugins/upload`: install UI plugins from `.zip`, `.tar.gz`, `.tar.xz`.
  - `DELETE /plugins/{id}`: remove a plugin by ID.
- **Cache (job artefacts)**
  - `GET /cache`: list cache files with filters (`service`, `plugin`, `job_name`); `with_data=true` embeds printable content.
  - `GET /cache/{service}/{plugin}/{job}/{file}`: fetch/download a specific cache file (`download=true`).
  - `DELETE /cache` or `DELETE /cache/{service}/{plugin}/{job}/{file}`: delete cache files and notify scheduler.
- **Jobs**
  - `GET /jobs`: list jobs, schedules, and cache summaries.
  - `POST /jobs/run`: mark plugins as changed to trigger associated jobs.

## Operational behaviour

- Error responses are normalized to `{"status": "error", "message": "..."}` with appropriate HTTP status codes.
- Write operations persist to the shared database; instances consume changes via scheduler sync or after a reload.
- `API_ROOT_PATH` must match the reverse-proxy path so `/docs` and links work correctly.
- Startup exits if no authentication path exists (no Biscuit keys, no admin user, and no `API_TOKEN`); errors are logged to `/var/tmp/bunkerweb/api.error`.
