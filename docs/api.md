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
- ACL scopes: config, service, plugin, and global-settings **write** permissions are admin-equivalent (their payload renders to raw NGINX/Lua = code execution) — grant them only to fully trusted users. `instances_create` and `instances_update` are admin-equivalent too, by a different route: calls to a registered instance carry the `API_TOKEN` admin override, and the scheduler pushes the generated configuration and cache (TLS private keys included) to every registered instance. See [Permissions and ACL](#permissions-and-acl).
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
        image: bunkerity/bunkerweb:1.7.0-beta
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
        image: bunkerity/bunkerweb-scheduler:1.7.0-beta
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
        image: bunkerity/bunkerweb-api:1.7.0-beta
        environment:
          <<: *bw-env
          API_USERNAME: "admin"
          API_PASSWORD: "Str0ng&P@ss!"
          # API_TOKEN: "admin-override-token" # optional
          FORWARDED_ALLOW_IPS: "127.0.0.0/8,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16" # Be careful with this setting; only use it if you are sure that the reverse proxy is the only way to access the API
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
          --maxmemory-policy volatile-lru
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
      bunkerity/bunkerweb-all-in-one:1.7.0-beta
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
- Resource types: `instances`, `global_config`, `services`, `configs`, `plugins`, `cache`, `bans`, `jobs`.
- Permission names:
  - `instances_*`: `instances_read`, `instances_update`, `instances_delete`, `instances_create`, `instances_execute`
  - `global_config_*`: `global_config_read`, `global_config_update`
  - `services`: `service_read`, `service_create`, `service_update`, `service_delete`, `service_convert`, `service_export`
  - `configs`: `configs_read`, `config_read`, `config_create`, `config_update`, `config_delete`
  - `plugins`: `plugin_read`, `plugin_create`, `plugin_delete`
  - `cache`: `cache_read`, `cache_delete`
  - `bans`: `ban_read`, `ban_update`, `ban_delete`, `ban_created`
  - `jobs`: `job_read`, `job_run`
- `resource_id` is usually the second path component (e.g. `/services/{id}`); `"*"` grants global access.
- Bootstrap non-admin users and grants with `API_ACL_BOOTSTRAP_FILE` or a mounted `/var/lib/bunkerweb/api_acl_bootstrap.json`. Each user takes a plaintext `password` or a pre-hashed `password_hash`/`password_bcrypt` (see tip below).

!!! danger "These write permissions are admin-equivalent"
    Granting any of the following is equivalent to granting full administrative access. The content they write — custom configs, service variables (e.g. `REVERSE_PROXY_URL`), uploaded plugins, and global settings — is rendered **verbatim** into raw NGINX / OpenResty Lua configuration that runs on the BunkerWeb workers and scheduler. A token holding one of them can therefore execute arbitrary code as the BunkerWeb process user. The instance write scopes are admin-equivalent for a different reason: every call to a registered instance carries the `API_TOKEN` admin override, and the scheduler pushes the generated configuration and the cache (TLS private keys included) to every instance in the database, so registering a single endpoint collects all of it:

    - `instances`: `instances_create`, `instances_update`
    - `configs`: `config_create`, `config_update`, `config_delete` (and `POST /configs/upload`)
    - `services`: `service_create`, `service_update`, `service_convert`
    - `plugins`: `plugin_create`
    - `global_config`: `global_config_update`

    Treat these exactly like admin: **never grant them to a party you would not trust as an administrator.** Reserve read scopes (`*_read`, `service_export`, `cache_read`, …) for limited or automation tokens. Granting one of these to a non-admin user emits a warning in the API logs.

!!! tip "Pre-hashed bootstrap passwords"
    Replace a user's plaintext `password` with a **bcrypt hash** via `password_hash` (or `password_bcrypt`) so credentials never sit in the file as plaintext. The hash must be a valid bcrypt hash (`$2a$`/`$2b$`/`$2y$`) whose cost factor is at least `10` (`12`+ recommended). A malformed or too-weak hash is **ignored**: the loader falls back to the user's plaintext `password` if present; otherwise a new user gets a secure random password you won't know, and an existing user keeps its current one. A plaintext `password` is strength-checked (8+ chars with upper/lower/digit/special). The admin `API_PASSWORD` env var accepts plaintext only — pre-hashing applies to these ACL users.

    Generate a hash:

    ```bash
    python3 -c "import bcrypt; print(bcrypt.hashpw(b'Str0ng&P@ss!', bcrypt.gensalt(rounds=13)).decode())"
    ```

    Then use it in the bootstrap file instead of `password`:

    ```json
    "password_hash": "$2b$13$replace-with-the-hash-printed-above"
    ```

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

!!! warning "The example above grants an admin-equivalent scope"
    `config_update` is a code-execution-capable permission (see the danger note above), so this `ci` user is as powerful as an admin for configuration writes — only issue such a token to automation you fully trust. For a read-only integration, drop `config_update` and keep just the `*_read` scopes.

## Per-instance credentials and TLS pinning

Each instance record can override the global `API_TOKEN` used for control-plane calls. Set `credential` on `POST /instances` or `PATCH /instances/{hostname}`. The API stores it with the shared AES-256-GCM keyring and never returns the plaintext: `GET /instances` exposes only `credential_set` and `credential_updated_at`. A per-instance credential takes precedence for API fan-out, Worker actions, configuration and cache pushes, and the `API_TOKEN` written into that instance's generated configuration. Send an empty `credential` in a PATCH to return to the global token.

Automated integrations can declare the same fields with grouped environment variables. Start a group with `BUNKERWEB_INSTANCE_HOST`, then use `BUNKERWEB_INSTANCE_API_TOKEN`, `BUNKERWEB_INSTANCE_LISTEN_HTTPS`, `BUNKERWEB_INSTANCE_HTTPS_PORT`, `BUNKERWEB_INSTANCE_SERVER_NAME`, `BUNKERWEB_INSTANCE_TLS_MODE`, and `BUNKERWEB_INSTANCE_TLS_FINGERPRINT`. Add the same numeric suffix to every key for more instances, for example `_1` and `_2`. The older `BUNKERWEB_INSTANCES` list still uses the global API settings for every host.

TLS trust is also stored per instance:

- `tls_mode: "off"` keeps the compatibility behavior. An instance with `listen_https: true` uses HTTPS without certificate verification and retries over plain HTTP after a TLS connection error.
- `tls_mode: "pinned"` checks the leaf certificate against the SHA-256 digest in `tls_fingerprint`. Colons and uppercase hex are accepted and normalized. A missing or mismatched fingerprint fails the call, and BunkerWeb never downgrades that instance to HTTP.

!!! warning "Pinning is the only verified TLS mode"
    There is no per-instance CA-validation mode. `off` does not verify the certificate, even when the endpoint uses HTTPS. `pinned` on an HTTP endpoint has no certificate to check, so pair it with `listen_https: true`. Update the stored fingerprint when the instance certificate rotates or control-plane calls to that instance will fail.

### Enrollment: an alternative to setting `credential` by hand

An instance registered through the web UI, the API, or declared through the environment (`method="manual"`) can instead be **enrolled**: an operator issues a single-use, time-limited code with `POST /instances/{hostname}/enroll` (shown once — optional `ttl_seconds`, default 900s, capped at 3600s), and the instance redeems it itself at boot with `POST /instances/enroll` (body `{hostname, code}`) — the one endpoint in this router with no auth guard, since it runs before the instance has any credential to authenticate with; its protection is the code's own single use, TTL and SHA-512-at-rest hash, plus the shared rate limiter and the API's IP whitelist. From that point on the instance stores and answers only to its own minted credential — the operator never has to see or set it. An enrolled credential is rotated or revoked with `POST /instances/{hostname}/rotate`/`revoke`, and a revoked instance is refused at the same dial funnel every control-plane call passes through. An instance that loses its persisted credential *file* after enrolling refuses to start rather than falling back to the global `API_TOKEN` it had already renounced — recreating it with no data volume at all is outside that guard's reach, since the marker that would trip it is lost together with the credential. Enrollment and an explicitly-set `credential` are independent: use whichever suits how the instance is provisioned.

## Rate limiting

Enabled by default with two strings: `API_RATE_LIMIT` (global, default `100r/m`) and `API_RATE_LIMIT_AUTH` (default `10r/m` or `off`). Rates accept NGINX-style notation (`3r/s`, `40r/m`, `200r/h`) or verbose forms (`100/minute`, `200 per 30 minutes`). Configure via:

- `API_RATE_LIMIT`, `API_RATE_LIMIT_AUTH`
- `API_RATE_LIMIT_ENABLED`, `API_RATE_LIMIT_HEADERS_ENABLED`
- `API_RATE_LIMIT_RULES` (CSV/JSON/YAML string or file path)
- `API_RATE_LIMIT_STRATEGY`, `API_RATE_LIMIT_KEY`, `API_RATE_LIMIT_EXEMPT_IPS`
- Storage is in-memory or Redis/Valkey when `USE_REDIS=yes` plus `REDIS_*` settings (Sentinel supported).

Requests authenticated with the admin `API_TOKEN` are exempt, whatever the limits say. That token already grants full admin access, so limiting it protects nothing — and it is what BunkerWeb's own components (web UI, Scheduler, Worker) use, all from the same network, so a per-IP limit otherwise counts the whole control plane as a single client. A bearer token that does not match stays limited like any other caller.

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
| `API_FORWARDED_ALLOW_IPS`                          | Trusted proxy IPs for `X-Forwarded-*`                                                       | Comma-separated IPs/CIDRs | `127.0.0.1,::1` (package default)  |
| `API_PROXY_ALLOW_IPS`                              | Trusted proxy IPs for PROXY protocol                                                        | Comma-separated IPs/CIDRs | `FORWARDED_ALLOW_IPS`              |

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
| `API_RATE_LIMIT_EXEMPT_IPS`      | Skip limits for these IPs/CIDRs (on top of the always-exempt admin `API_TOKEN`) | Space/comma-separated                                     | unset          |
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

!!! warning "Without Redis the limit is per worker"
    The fallback storage lives in the process memory of each Gunicorn worker, so every worker enforces the configured rate on its own: with `MAX_WORKERS=4` and `API_RATE_LIMIT_AUTH=10r/m`, a client spread across the workers gets up to 40 attempts a minute. Point the API at Redis/Valkey — or run a single worker — wherever the limit is a security control rather than a courtesy.

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
| `MAX_REQUESTS`                  | Requests before a Gunicorn worker is recycled (prevents memory bloat)             | Integer                                         | `1000`                                                             |
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
  - `PUT /instances/bulk`: bulk-reconcile instances by `method` (used by autoconf). Refuses `method="ui"` or `method="manual"` — either would delete-and-recreate every enrolled row of that kind, wiping its minted credential.
  - Enrollment: `POST /instances/{hostname}/enroll` (needs `instances_enroll`) issues a single-use, time-limited enrollment code shown once, with an optional `ttl_seconds` override. `POST /instances/enroll` — body `{hostname, code}` — is the one route in this router with no `Depends(guard)`: the booting instance calls it itself to redeem the code and receive its credential; its protection is the code's own single use, TTL and hash, plus the shared rate limiter and the IP whitelist. From then on the instance refuses the global `API_TOKEN` and answers only to its own stored credential. `POST /instances/{hostname}/rotate` and `POST /instances/{hostname}/revoke` (need `instances_rotate`) rotate or revoke a live credential — rotation is two-phase and answers `502` rather than force through an instance it cannot reach, and a revoked instance is refused at every dial from then on.
  - `PATCH /instances/{hostname}/status`: set an instance's `up`/`down`/`failover` status directly (used by the scheduler's own healthcheck loop).
  - Health/actions: `GET /instances/ping`, `GET /instances/{hostname}/ping`, `GET /instances/{hostname}/health`, `POST /instances/reload?test=yes|no`, `POST /instances/{hostname}/reload`, `POST /instances/stop`, `POST /instances/{hostname}/stop`.
  - `GET /instances/{hostname}/health` forwards what the instance says about itself — `ok`, `loading` or `reloading` — where `ping` only answers "reachable". An instance that restarted stays in `loading` until it receives a configuration, and in that state its timer-driven plugins are disabled, so the scheduler uses this to decide whether to re-push. Both routes need the `instances_read` permission.
  - A reload against a busy instance is retried rather than reported failed, so the worst-case latency of `POST /instances/{hostname}/reload` (and the fleet-wide `POST /instances/reload`) is ~54s, not the ~35s a fixed-lock read would suggest — a caller with a shorter timeout may see one reported as failed while it is only slow.
- **Global settings**
  - `GET /global_settings`: non-defaults by default; add `full=true` for all settings, `methods=true` to include provenance.
  - `PATCH /global_settings`: upsert API-owned globals; read-only keys are rejected. A setting owned by another source (`scheduler`, i.e. an environment variable, plus `autoconf`, `manual`, `wizard`) cannot be taken over: the whole payload is rejected with `409` naming each key and its owner, and nothing is written. Re-sending a value a foreign-owned key already holds is not a conflict.
  - `GET /global_config`, `PATCH /global_config`: aliases of `GET`/`PATCH /global_settings`, kept for backward compatibility.
  - `POST /global_settings/validate`: validate a setting name and, optionally, a candidate value against `is_valid_setting`, without persisting anything.
  - `PUT /global_settings/config`: replace the complete config environment in one call (used by autoconf to persist its merged configuration; the UI's config editor uses it too). Unlike `PATCH`, the payload IS the whole desired state — any in-scope key it omits is deleted. Refuses (`400`) a configuration that would strand a service's http-01 challenge, except for `method="autoconf"`, where the conflict is logged and saved anyway rather than leaving the rest of the fleet unconfigured.
- **Services**
  - `GET /services`: list services (include drafts by default).
  - `GET /services/{service}`: fetch non-defaults or full config (`full=true`); `methods=true` includes provenance.
  - `POST /services`: create a service (draft or online), set variables, and update `SERVER_NAME` roster atomically.
  - `PATCH /services/{service}`: rename, update variables, toggle draft.
  - `DELETE /services/{service}`: remove service and derived config keys.
  - `POST /services/{service}/convert?convert_to=online|draft&mode=standard|redirect_only`: switch draft/online and/or declare the service mode — the two axes are independent, at least one is required, and a call carrying neither answers `400` (previously `422`, when `convert_to` was a required parameter). `mode=redirect_only` answers `409` with a `reasons` array when the service still carries something the redirect-only allowlist forbids; `mode=standard` is always accepted. Refused `403` for the reserved `default-server`, same as every other conversion on it.
  - `GET /services/redirect-candidates` (needs `service_read`): every non-draft service other than the reserved `default-server` and not already declared `redirect_only`, each answered with `would_qualify` and `blocking_reasons` (empty when it qualifies), as `{"status": "success", "candidates": [{"service": ..., "would_qualify": ..., "blocking_reasons": [...]}]}`. Read-only — it changes nothing and bills nothing.
  - The reserved `default-server` service is returned by `GET /services` flagged `reserved: true` — **only when `MULTISITE=yes`**; with `MULTISITE=no` the row does not exist and is not listed, and the default server behaves exactly as it did in 1.6. It is the block that answers requests matching no configured service — an unknown hostname, a raw IP address — exposed as a service so its certificate, TLS settings, response headers and error pages can be read and written like any other. It is permanent: `POST /services` with that name, `DELETE /services/default-server`, a `PATCH` that renames it (or renames another service onto it), a `PATCH` that drafts it and `POST /services/default-server/convert?convert_to=draft` all answer `403` with one sentence saying why. `PATCH /services/default-server` with `variables` is the supported way to configure it, and it is never counted against the PRO service quota. Two `variables` keys are refused there with `400`: `SERVER_TYPE`, at any value including the stored one, because the reserved id never gets a `server{}` block of either kind for it to switch — a read-modify-write client must strip it from the payload it echoes back; and a `DEFAULT_SERVER_STREAM_PORTS_SSL` entry that `DEFAULT_SERVER_STREAM_PORTS` does not contain.
- **Custom configs**
  - `GET /configs`: list snippets (default service `global`); `with_data=true` embeds printable content.
  - `POST /configs`, `POST /configs/upload`: create snippets via JSON or file upload.
  - `GET /configs/{service}/{type}/{name}`: fetch snippet; `with_data=true` for content.
  - `PATCH /configs/{service}/{type}/{name}`, `PATCH .../upload`: update or move API-managed snippets.
  - `DELETE /configs` or `DELETE /configs/{service}/{type}/{name}`: remove API-managed snippets; template-managed entries are skipped.
  - `PUT /configs/bulk`: replace every custom config carrying a given `method` tag in one call (used by autoconf to sync its discovered configurations). An advisory-only failure (rows already committed, message-only) still answers `200`; a real refusal answers `400`, never `500` — the caller's HTTP client drops the body of a `5xx`.
  - Supported types: `http`, `server_http`, `default_server_http`, `modsec`, `modsec_crs`, `stream`, `server_stream`, CRS/plugin hooks.
- **Bans**
  - `GET /bans`: list the active bans from the database (the durable list). **Changed in 1.7** — this used to aggregate the instances' in-memory bans, which under-reports after a restart.
  - `GET /bans/instances`: the previous behaviour, kept as its own endpoint — what each instance is enforcing right now.
  - `GET /bans/timeseries?start=...&end=...&bucket=hour`: active-ban occupancy per interval over `[start, end)`. `bw_bans` keeps one row per `(ip, ban_scope, service_id)` and a re-ban rewrites `created_at`, so this is a point-in-time occupancy count, not an event/creation history.
  - `POST /bans` or `/bans/ban`: apply one or more bans; payload can be object, array, or stringified JSON. The ban is persisted, then sent to the instances.
  - `POST /bans/unban` or `DELETE /bans`: remove bans globally or per service. A revoke that cannot be persisted is refused, because an instance that missed it would otherwise re-teach the ban to the fleet.
- **Plugins (UI plugins)**
  - `GET /plugins`: list plugins; `with_data=true` includes packaged bytes when available.
  - `POST /plugins/upload`: install UI plugins from `.zip`, `.tar.gz`, `.tar.xz`.
  - `PUT /plugins/external`: bulk-replace external/PRO plugins in the database (`delete_missing` prunes what the payload omits); archive bytes travel base64-encoded over JSON.
  - `DELETE /plugins/{id}`: remove a plugin by ID.
  - `GET /plugins/{id}/page`: the plugin's UI page data as a `tar.gz` blob, `404` if the plugin has none.
  - `GET /plugins/{id}/icon`: the plugin's shipped icon file, if any (only an `@file/<name>` marker has one; a static-asset name, a boxicon class, or no icon at all answers `404`). Served with `Content-Security-Policy: default-src 'none'; sandbox`, `X-Content-Type-Options: nosniff` and a quoted `Content-Disposition: inline`, so an SVG icon cannot execute script if opened by direct navigation; files over 512KB answer `413`.
- **Cache (job artefacts)**
  - `GET /cache`: list cache files with filters (`service`, `plugin`, `job_name`); `with_data=true` embeds printable content.
  - `GET /cache/{service}/{plugin}/{job}/{file}`: fetch/download a specific cache file (`download=true`).
  - `DELETE /cache` or `DELETE /cache/{service}/{plugin}/{job}/{file}`: delete cache files and notify scheduler.
- **Jobs**
  - `GET /jobs`: list jobs, schedules, and cache summaries.
  - `GET /jobs/{name}/last-run`: the newest persisted run for one job.
  - `POST /jobs/run`: mark plugins as changed to trigger associated jobs.
  - `POST /jobs/dispatch`: dispatch jobs straight to the Celery workers, bypassing the scheduler's own trigger path; answers `503` if no broker is configured. The response's `run_id` per job is a log-correlation token (it prefixes every worker log line for that run) and not a pollable handle — there is deliberately no endpoint to fetch a dispatched job's result, since the app runs with no Celery result backend.
  - `GET /jobs/queue`: current state of the Celery worker queues (`503` with no broker configured).
- **Web cache**
  - `GET /web-cache/status`, `GET /web-cache/metrics`: per-service reverse-proxy cache status and metrics.
  - `POST /web-cache/purge`: purge one URL, or the whole cache for a service.
- **System**
  - `GET /system/readonly`: whether the database is currently in a read-only/failover state.
  - `POST /system/checked-changes`: acknowledge processed change-tracking flags.
- **Users** (web UI accounts, not API callers)
  - `GET/POST /users`, `GET/PATCH /users/{username}`: account management.
  - `GET/DELETE /users/{username}/sessions`, `POST /users/{username}/login`: session listing/revocation and login.
  - `POST /users/{username}/recovery-codes/refresh|use`: TOTP recovery codes.
  - `POST /users/{username}/totp/use`: consume a TOTP counter once so the same code cannot be replayed on another UI worker. A refusal is not an error — it is the replay defence firing — so the caller distinguishes it from an outage by the `200` response's `consumed: false`.
  - `GET/POST /users/{username}/webauthn-credentials`, `GET /users/webauthn-credentials/{id}`, `PATCH/DELETE /users/{username}/webauthn-credentials/{id}`: passkey/WebAuthn credentials.
  - `GET/PATCH /users/{username}/preferences/{key}`, `POST /users/{username}/access`, `GET /users/{username}/permissions`: per-user KV preferences and ACL introspection.
- **Templates**
  - `GET /templates`, `GET /templates/{id}`: list/fetch a reusable service template.
  - `POST /templates`, `PATCH /templates/{id}`, `DELETE /templates/{id}`: create, update, or remove one.
- **Resource groups**
  - `GET /resource_groups`, `GET /resource_groups/{id}`, `GET /resource_groups/{id}/references`: list/fetch a reusable typed resource-list alias and see what still references it before deleting it.
  - `POST /resource_groups`, `PATCH /resource_groups/{id}`, `DELETE /resource_groups/{id}`, `POST /resource_groups/{id}/clone`: manage a group.
- **Metadata**
  - `GET /metadata`, `PATCH /metadata`: PRO license state and scheduler-wide flags. Cannot be used to overwrite the certificate/credential encryption keyring.
- **Certificates**
  - `GET /certificates`, `GET /certificates/sources`, `GET /certificates/{id}`, `GET /certificates/{id}/download`: the centralized certificate inventory and the plugin-declared sources feeding it.
  - `PATCH /certificates/{id}`, `POST /certificates/{id}/revoke`, `DELETE /certificates/{id}`: manage a certificate's lifecycle.
  - `POST /certificates/{id}/attachments`, `DELETE /certificates/{id}/attachments/{service}`: attach a certificate to a service, or detach it.
- **Redirects** / **Upstreams** — reusable, attachable resources with the same shape
  - `GET/POST /redirects`, `GET/PATCH/DELETE /redirects/{id}`, `POST/DELETE /redirects/{id}/attachments[/{service}]`: HTTP redirect rules attachable to several services at once.
  - `GET/POST /upstreams`, `GET/PATCH/DELETE /upstreams/{id}`, `POST/DELETE /upstreams/{id}/attachments[/{service}]`: upstream pools (HTTP, gRPC, or stream) attachable to a reverse-proxy path, or to a whole stream service.
- **Metrics**
  - `GET /metrics/timings`: per-plugin, per-phase timing aggregate across instances (`METRICS_COLLECT_TIMINGS`).
  - `GET /metrics/requests`, `GET /metrics/requests/timeseries`, `GET /metrics/requests/top-offenders`, `GET /metrics/requests/top-rules`: the persisted Reports data behind the web UI's Reports dashboard, filterable by `protocol` (`http`, `tcp`, `udp`) among other facets.
  - `GET /metrics/threatmap`: near-real-time blocked-traffic feed behind the personal Threatmap page.
- **Certificate sources** (plugin-shipped)
  - `GET /bunkernet/effectiveness`, `GET /bunkernet/stats`: BunkerNet community threat-intelligence effectiveness and usage stats.
  - `POST /customcert/certificates/upload`: register an operator-provided certificate in the inventory.
  - `POST /letsencrypt/certificates`, `POST /letsencrypt/certificates/renew-due`, `GET /letsencrypt/certificates/orphans`: issue, renew due certificates in bulk, and list orphaned ones.
  - `POST /selfsigned/certificates`, `POST /selfsigned/certificates/renew-due`, `POST /selfsigned/certificates/{certificate_id}/renew`: issue, bulk-renew due certificates, or renew one by id.
- **Workflows** (plugin-shipped, mounted at `/workflows`)
  - `GET /workflows`, `POST /workflows`, `GET/PATCH/DELETE /workflows/{id}`, `POST /workflows/{id}/clone`: the security-workflow engine's conditional rule chains.
  - `GET/PUT /workflows/{id}/definition`: read or replace a workflow's compiled rule definition.
  - `POST /workflows/validate`, `POST /workflows/{id}/test`: validate a definition, or dry-run it against a sample request before saving.
  - `POST /workflows/{id}/attachments`, `DELETE /workflows/{id}/attachments/{service}`: attach a workflow to a service, or detach it.

## Operational behaviour

- Error responses are normalized to `{"status": "error", "message": "..."}` with appropriate HTTP status codes.
- Write operations persist to the shared database; instances consume changes via scheduler sync or after a reload.
- `API_ROOT_PATH` must match the reverse-proxy path so `/docs` and links work correctly.
- Startup exits if no authentication path exists (no Biscuit keys, no admin user, and no `API_TOKEN`); errors are logged to `/var/tmp/bunkerweb/api.error`.
