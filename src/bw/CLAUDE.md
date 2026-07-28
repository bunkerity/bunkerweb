# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See also the [root CLAUDE.md](../../CLAUDE.md) for project-wide architecture, build commands, and conventions.

## Component Overview

`src/bw/` is the BunkerWeb core NGINX container — the reverse proxy runtime that processes HTTP/Stream requests through a Lua plugin pipeline. It packages the Lua runtime, entrypoint script, loading page, and static assets (GeoIP databases, root CA) into a Docker image based on `nginx:1.30.4` (Debian/glibc — migrated off Alpine because the certbot-dns-multi Go/CGO bridge cannot load on musl).

This component has no Python code of its own. It depends on `src/common/` (core plugins, confs, gen, helpers, utils, settings.json) and `src/deps/` (compiled NGINX modules, Python deps for config generation).

## Build

```bash
# Build the BunkerWeb Docker image (run from repo root)
docker build -f src/bw/Dockerfile -t bunkerweb:dev .

# Faster dev build (skip HTML minification)
docker build -f src/bw/Dockerfile -t bunkerweb:dev --build-arg SKIP_MINIFY=yes .
```

The Dockerfile is a multi-stage build: stage 1 compiles NGINX deps from `src/deps/`, stage 2 copies artifacts into the Debian-based `nginx:1.30.4` runtime image. The final image runs as `nginx:nginx` (non-root).

## Linting & Formatting

```bash
# Lua formatting (excludes middleclass.lua — third-party)
stylua src/bw/lua/bunkerweb/

# Lua linting
luacheck src/bw/lua --std min --codes --ranges --no-cache

# Shell linting
shellcheck src/bw/entrypoint.sh

# Run all pre-commit hooks
pre-commit run --all-files
```

Config files at repo root: `.luacheckrc` (globals: `ngx`, `delay`, `unpack`; ignores: `411`), `stylua.toml` (`call_parentheses = "Input"`, sort requires enabled).

## Lua Architecture

### Module Overview

All classes use `middleclass` (third-party OOP in `lua/middleclass.lua` — do not lint or modify).

| Module             | Role                                                                                                                               |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| `plugin.lua`       | Base class for all plugins. Instantiated per-request with access to variables, datastores, and metrics.                            |
| `helpers.lua`      | Init-time utilities: plugin loading/ordering, variable parsing, context filling (`fill_ctx`), context saving for subrequests.      |
| `utils.lua`        | Request-time utilities: variable lookup, IP/ban/whitelist management, DNS, GeoIP, sessions, security helpers.                      |
| `datastore.lua`    | Worker-local LRU (1k entries by default, set via `DATASTORE_LRU_SIZE`) + NGINX shared dict abstraction.                            |
| `cachestore.lua`   | Multi-level cache: L1 worker LRU → L2 shared dict (mlcache) → L3 Redis (optional). Gracefully degrades without Redis.              |
| `clusterstore.lua` | Redis connection pool with Sentinel support. Lazy init — only connects when cosockets are available.                               |
| `api.lua`          | Internal NGINX API (`/ping`, `/reload`, `/ban`, `/unban`, `/bans`, `/health`, config upload endpoints). Token + IP whitelist auth. |
| `ctx.lua`          | FFI-based context stashing for subrequest preservation.                                                                            |
| `logger.lua`       | Thin wrapper around `ngx.log` with prefix formatting.                                                                              |
| `mmdb.lua`         | Module-level singletons loading the country/ASN/city databases from `/var/cache/bunkerweb/geoip/` (city may be nil).               |

### Request Processing Flow

1. **Init phase**: `helpers.lua` loads plugin metadata into `internalstore` shared dict, parses variables, pre-compiles require paths.
2. **Per-request**: `helpers.fill_ctx()` populates `ngx.ctx.bw` with IP, URI, headers, and fresh datastore/cachestore/clusterstore instances.
3. **Plugin execution**: For each plugin in `PLUGINS_ORDER_<PHASE>`, instantiate via `plugin:new(ctx)` and call the phase method (set/rewrite/access/content/header_filter/body_filter/log/preread).
4. **Return convention**: All phase methods return a table with named keys (built by `self:ret(...)`): `{ ret = ..., msg = ..., status = ..., redirect = ..., data = ... }`.

### Enriched request context (`ctx.bw`)

`fill_ctx()` resolves the request/session metadata **once**, then every plugin reads it from `self.ctx.bw` — never re-resolve it. `self.variables` stays reserved for configuration settings.

| Field                                      | Value                                                                                                                                                                                                                  |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `kind`                                     | `http` or `stream`                                                                                                                                                                                                     |
| `protocol`                                 | `http`, `https`, `tcp` or `udp`                                                                                                                                                                                        |
| `remote_addr`, `server_name`, `time_local` | as seen by NGINX                                                                                                                                                                                                       |
| `ip_is_global`, `ip_is_ipv4`, `ip_is_ipv6` | booleans                                                                                                                                                                                                               |
| `ip_version`                               | `4` or `6`                                                                                                                                                                                                             |
| `country`                                  | ISO 3166-1 alpha-2 code, `local` (non-global IP) or `unknown` (MMDB missing or lookup failed)                                                                                                                          |
| `city`                                     | city name, or `nil` — the city database is opt-in (`GEOIP_CITY`) and absent by default                                                                                                                                 |
| `asn_number`, `asn_org`                    | number / string, or `nil`                                                                                                                                                                                              |
| `country_ok`, `asn_ok`, `city_ok`          | booleans — `true` when the value is authoritative (including "no ASN because the IP is not global"), `false` only when the lookup itself failed                                                                        |
| HTTP only                                  | `request_id`, `uri`, `request_uri`, `request_method`, `http_user_agent`, `http_host`, `http_content_type`, `http_content_length`, `http_origin`, `http_accept`, `http_referer`, `http_version`, `start_time`, `scheme` |

Enrichment is fail-open: a GeoIP failure never blocks a request, and it is logged at most once per worker. `utils.get_country()` / `utils.get_asn()` / `utils.get_city()` remain for lookups on **another** IP (e.g. the bans API) — not for the current request. A missing _optional_ database returns `false` rather than `nil`, which is how `fill_ctx` tells "city is not enabled" (silent) from "the lookup failed" (warn once).

The `*_ok` flags exist so a policy engine can tell a **fact** from an **unknown**: a private IP has no ASN (`asn_number = nil`, `asn_ok = true` → a predicate is `FALSE`), whereas a broken MMDB also has no ASN but `asn_ok = false` → the predicate must degrade to `UNKNOWN` instead of silently reading as "no match".

Predicate semantics of the fields policies match on: `uri` is the NGINX-normalized, percent-decoded path **without** the query string (`/login%2Fx` matches a `/login/` prefix), `request_method` is upper-case, `remote_addr` is the effective client IP **after** Real-IP, and `server_name` is the service's first server name — the service identity used by per-service keys.

Plugins may store their own request state in `ctx.bw`, prefixed with their plugin id (`antibot_session_data`, `sessions_checks`, …). Keep that convention: it is what stops core plugins, external plugins and PRO extensions from colliding in a shared table.

`helpers.export_ctx_vars(ctx)` mirrors the context into the `$bw_*` NGINX variables (`$bw_kind`, `$bw_protocol`, `$bw_ip_is_global`, `$bw_ip_version`, `$bw_country`, `$bw_city`, `$bw_asn_number`, `$bw_asn_org`) so they can be used in `LOG_FORMAT`. Call it only from a phase where writing `ngx.var` is allowed — `set-lua.conf` (HTTP) and `preread-stream-lua.conf` (Stream) — and from a server block that declares the variables (`server-http/server.conf`, `server-stream/server-stream.conf`).

### Subsystem Handling (HTTP vs Stream)

Lua modules detect `ngx.config.subsystem` ("http" or "stream") and select the appropriate shared dicts (e.g., `datastore` vs `datastore_stream`, `cachestore` vs `cachestore_stream`). Stream uses `preread` and `log_stream` phases instead of HTTP access/content phases.

### Cosocket Awareness

Async operations (Redis, DNS) require cosockets, which are only available in certain NGINX phases. Code checks `utils.is_cosocket_available()` and falls back to LRU/shared dict when unavailable (init, init_worker, log phases).

### Shared Memory Dictionaries

| Dict                                           | Purpose                                    |
| ---------------------------------------------- | ------------------------------------------ |
| `internalstore` / `internalstore_stream`       | Plugin metadata, compiled variables        |
| `datastore` / `datastore_stream`               | General key-value store                    |
| `cachestore` / `cachestore_stream`             | mlcache L1+L2                              |
| `cachestore_ipc` / `cachestore_ipc_stream`     | mlcache IPC                                |
| `cachestore_miss` / `cachestore_miss_stream`   | Miss tracking (thundering herd prevention) |
| `cachestore_locks` / `cachestore_locks_stream` | Distributed locks                          |

### Variable Access

```lua
-- From utils (with multisite site-search)
value, err = utils.get_variable("SETTING_NAME", true, ctx)

-- From plugin instance (already resolved at init)
value = self.variables["SETTING_NAME"]

-- Multisite: prefix with server name
-- e.g., www.example.com_USE_ANTIBOT=captcha
```

## Directory Layout

- `lua/bunkerweb/` — Lua runtime modules (the core of this component)
- `lua/middleclass.lua` — Third-party OOP library (do not modify)
- `loading/index.html` — Static loading page shown while BunkerWeb initializes
- `misc/` — Static assets: `asn.mmdb`, `country.mmdb` (GeoIP bootstrap fallbacks; there is deliberately no `city.mmdb` — it is 125 MB and downloaded on demand), `root-ca.pem`
- `entrypoint.sh` — Container startup: detects integration mode, generates temp config, starts NGINX
- `Dockerfile` — Multi-stage build producing the runtime image

## Entrypoint Behavior

`entrypoint.sh` runs the following sequence:

1. Source helpers, detect integration mode (Docker/Swarm/Kubernetes/Autoconf)
2. Generate temporary NGINX config via `python3 gen/main.py` (loading state)
3. Start NGINX in foreground (`daemon off`)
4. Trap SIGTERM (stop), SIGHUP (reload), and wait on the NGINX process

`KEEP_CONFIG_ON_RESTART=yes` skips temp config regeneration and preserves existing NGINX config across container restarts.

## Container Runtime Layout

Inside the container, files live under `/usr/share/bunkerweb/`:

- `lua/`, `core/`, `confs/`, `gen/`, `helpers/`, `utils/` — Code
- `/data/` — Persistent volume mount (cache, lib, www, configs, plugins, pro)
- `/etc/nginx/` — Generated NGINX configuration
- Logs redirected to `/proc/1/fd/{1,2}` (container stdout/stderr)
