# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See also the [root CLAUDE.md](../../CLAUDE.md) for project-wide architecture, build commands, and conventions.

## Component Overview

`src/bw/` is the BunkerWeb core NGINX container — the reverse proxy runtime that processes HTTP/Stream requests through a Lua plugin pipeline. It packages the Lua runtime, entrypoint script, loading page, and static assets (GeoIP databases, root CA) into a Docker image based on `nginx:1.28.3-alpine-slim`.

This component has no Python code of its own. It depends on `src/common/` (core plugins, confs, gen, helpers, utils, settings.json) and `src/deps/` (compiled NGINX modules, Python deps for config generation).

## Build

```bash
# Build the BunkerWeb Docker image (run from repo root)
docker build -f src/bw/Dockerfile -t bunkerweb:dev .

# Faster dev build (skip HTML minification)
docker build -f src/bw/Dockerfile -t bunkerweb:dev --build-arg SKIP_MINIFY=yes .
```

The Dockerfile is a multi-stage build: stage 1 compiles NGINX deps from `src/deps/`, stage 2 copies artifacts into a slim runtime image. The final image runs as `nginx:nginx` (non-root).

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
| `datastore.lua`    | Worker-local LRU (100k entries) + NGINX shared dict abstraction.                                                                   |
| `cachestore.lua`   | Multi-level cache: L1 worker LRU → L2 shared dict (mlcache) → L3 Redis (optional). Gracefully degrades without Redis.              |
| `clusterstore.lua` | Redis connection pool with Sentinel support. Lazy init — only connects when cosockets are available.                               |
| `api.lua`          | Internal NGINX API (`/ping`, `/reload`, `/ban`, `/unban`, `/bans`, `/health`, config upload endpoints). Token + IP whitelist auth. |
| `ctx.lua`          | FFI-based context stashing for subrequest preservation.                                                                            |
| `logger.lua`       | Thin wrapper around `ngx.log` with prefix formatting.                                                                              |
| `mmdb.lua`         | Module-level singletons loading MaxMind country/ASN databases.                                                                     |

### Request Processing Flow

1. **Init phase**: `helpers.lua` loads plugin metadata into `internalstore` shared dict, parses variables, pre-compiles require paths.
2. **Per-request**: `helpers.fill_ctx()` populates `ngx.ctx.bw` with IP, URI, headers, and fresh datastore/cachestore/clusterstore instances.
3. **Plugin execution**: For each plugin in `PLUGINS_ORDER_<PHASE>`, instantiate via `plugin:new(ctx)` and call the phase method (set/rewrite/access/content/header_filter/body_filter/log/preread).
4. **Return convention**: All phase methods return `{ret, msg, status, redirect, data}`.

### Subsystem Handling (HTTP vs Stream)

Lua modules detect `ngx.config.subsystem` ("http" or "stream") and select the appropriate shared dicts (e.g., `datastore` vs `datastore_stream`, `cachestore` vs `cachestore_stream`). Stream uses `preread` and `log_stream` phases instead of HTTP access/content phases.

### Cosocket Awareness

Async operations (Redis, DNS) require cosockets, which are only available in certain NGINX phases. Code checks `utils.is_cosocket_available()` and falls back to LRU/shared dict when unavailable (init, init_worker, log phases).

### Shared Memory Dictionaries

| Dict                                           | Purpose                                    |
| ---------------------------------------------- | ------------------------------------------ |
| `internalstore`                                | Plugin metadata, compiled variables        |
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
- `misc/` — Static assets: `asn.mmdb`, `country.mmdb` (GeoIP), `root-ca.pem`
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
