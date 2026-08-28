# AGENTS.md

Agent guide for the BunkerWeb NGINX/Lua runtime in `src/bw/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Root: [../../AGENTS.md](../../AGENTS.md) (short) and [../../CLAUDE.md](../../CLAUDE.md) (architecture)
- Shared code: [../common/AGENTS.md](../common/AGENTS.md)

## What This Is

The core NGINX container: the reverse-proxy runtime that processes HTTP and Stream requests through a Lua plugin pipeline. It packages the Lua runtime, the entrypoint, the loading page and static assets (GeoIP bootstrap databases, root CA) on top of `nginx:1.30.4` — Debian/glibc, migrated off Alpine because the certbot-dns-multi Go/CGO bridge cannot load on musl. Verify the pin in the Dockerfile before quoting it.

There is **no Python here**. This component depends on `src/common/` (core plugins, confs, gen, helpers, utils, settings) and `src/deps/` (compiled NGINX modules, Python deps for config generation).

## Critical Rules

- Request behavior runs through the Lua plugin phases, ordered by `PLUGINS_ORDER_<PHASE>`.
- HTTP and Stream are different subsystems with different shared dicts and different phases. Respect the split.
- Redis, DNS and any other async operation need cosockets, which do not exist in every phase.
- `lua/middleclass.lua` is third-party: do not lint, format or modify it.
- Generated NGINX config comes from the shared generation pipeline, never from ad-hoc runtime edits.

## Lua Architecture

Modules live in `lua/bunkerweb/`; run `ls` for the current set. They fall into families:

- **Plugin machinery** — `plugin.lua` (base class, instantiated per request) and `helpers.lua` (init-time plugin loading and ordering, variable parsing, `fill_ctx`, context saving for subrequests).
- **Storage tiers** — `datastore.lua` (worker-local LRU, size via `DATASTORE_LRU_SIZE`, over an NGINX shared dict), `cachestore.lua` (L1 worker LRU → L2 shared dict via mlcache → L3 Redis, degrading gracefully without Redis), `clusterstore.lua` (Redis pool with Sentinel support, lazily initialized only where cosockets exist).
- **Request-time utilities** — `utils.lua` (variable lookup, IP/ban/whitelist handling, DNS, GeoIP, sessions, security helpers) and `ctx.lua` (FFI-based context stashing across subrequests).
- **Surfaces and services** — `api.lua` (the internal NGINX API: ping, reload, ban/unban/bans, health, config upload; token plus IP-whitelist auth), `internal_api.lua`, `ban_sync.lua`, `ratelimit.lua`, `pushswap.lua`, `logger.lua`, and `mmdb.lua` (module-level singletons over the country/ASN/city databases in `/var/cache/bunkerweb/geoip/`; city may be nil).

All classes use `middleclass`.

### Request flow

1. **Init**: `helpers.lua` loads plugin metadata into the `internalstore` shared dict, parses variables, pre-compiles require paths.
2. **Per request**: `helpers.fill_ctx()` populates `ngx.ctx.bw` with the request metadata plus fresh datastore/cachestore/clusterstore instances.
3. **Plugin execution**: for each plugin in `PLUGINS_ORDER_<PHASE>`, instantiate with `plugin:new(ctx)` and call the phase method (set/rewrite/access/content/header_filter/body_filter/log/preread).
4. **Return convention**: every phase method returns a table built by `self:ret(...)` — `{ ret, msg, status, redirect, data }`.

### Enriched request context (`ctx.bw`)

`fill_ctx()` resolves request and session metadata **once**; every plugin reads it from `self.ctx.bw` and never re-resolves. `self.variables` stays reserved for configuration settings.

| Field                                      | Value                                                                                                                                                                                                                  |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `kind`                                     | `http` or `stream`                                                                                                                                                                                                     |
| `protocol`                                 | `http`, `https`, `tcp` or `udp`                                                                                                                                                                                        |
| `remote_addr`, `server_name`, `time_local` | as seen by NGINX                                                                                                                                                                                                       |
| `ip_is_global`, `ip_is_ipv4`, `ip_is_ipv6` | booleans                                                                                                                                                                                                               |
| `ip_version`                               | `4` or `6`                                                                                                                                                                                                             |
| `country`                                  | ISO 3166-1 alpha-2, `local` (non-global IP) or `unknown` (MMDB missing or lookup failed)                                                                                                                               |
| `city`                                     | city name, or `nil` — the city database is opt-in (`GEOIP_CITY`) and absent by default                                                                                                                                 |
| `asn_number`, `asn_org`                    | number / string, or `nil`                                                                                                                                                                                              |
| `country_ok`, `asn_ok`, `city_ok`          | `true` when the value is authoritative (including "no ASN because the IP is not global"), `false` only when the lookup itself failed                                                                                   |
| HTTP only                                  | `request_id`, `uri`, `request_uri`, `request_method`, `http_user_agent`, `http_host`, `http_content_type`, `http_content_length`, `http_origin`, `http_accept`, `http_referer`, `http_version`, `start_time`, `scheme` |

Enrichment is fail-open: a GeoIP failure never blocks a request and is logged at most once per worker. `utils.get_country()` / `get_asn()` / `get_city()` remain for lookups on **another** IP (the bans API, for instance) — not for the current request. A missing _optional_ database returns `false` rather than `nil`, which is how `fill_ctx` tells "city is not enabled" (silent) from "the lookup failed" (warn once).

The `*_ok` flags let a policy engine tell a **fact** from an **unknown**: a private IP has no ASN (`asn_number = nil`, `asn_ok = true` → the predicate is FALSE), whereas a broken MMDB also has no ASN but `asn_ok = false` → the predicate must degrade to UNKNOWN instead of silently reading as "no match".

Predicate semantics of the fields policies match on: `uri` is the NGINX-normalized, percent-decoded path **without** the query string (`/login%2Fx` matches a `/login/` prefix), `request_method` is upper-case, `remote_addr` is the effective client IP **after** Real-IP, and `server_name` is the service's first server name — the service identity used by per-service keys.

Plugins may store their own request state in `ctx.bw` prefixed with their plugin id (`antibot_session_data`, `sessions_checks`, …). Keep that convention: it is what stops core plugins, external plugins and PRO extensions from colliding in a shared table.

`helpers.export_ctx_vars(ctx)` mirrors the context into the `$bw_*` NGINX variables (`$bw_kind`, `$bw_protocol`, `$bw_ip_is_global`, `$bw_ip_version`, `$bw_country`, `$bw_city`, `$bw_asn_number`, `$bw_asn_org`) for use in `LOG_FORMAT`. Call it only from a phase where writing `ngx.var` is allowed — `set-lua.conf` (HTTP) and `preread-stream-lua.conf` (Stream) — and from a server block that declares the variables (`server-http/server.conf`, `server-stream/server-stream.conf`).

### HTTP vs Stream

Modules read `ngx.config.subsystem` and pick the matching shared dicts (`datastore` vs `datastore_stream`, `cachestore` vs `cachestore_stream`, …). Stream uses the `preread` and `log_stream` phases instead of the HTTP access/content phases.

### Cosockets

Async work (Redis, DNS) needs cosockets, available only in some phases. Check `utils.is_cosocket_available()` and fall back to the LRU or shared dict in init, init_worker and log phases.

### Shared dictionaries

| Dict                                           | Purpose                                    |
| ---------------------------------------------- | ------------------------------------------ |
| `internalstore` / `internalstore_stream`       | Plugin metadata, compiled variables        |
| `datastore` / `datastore_stream`               | General key-value store                    |
| `cachestore` / `cachestore_stream`             | mlcache L1+L2                              |
| `cachestore_ipc` / `cachestore_ipc_stream`     | mlcache IPC                                |
| `cachestore_miss` / `cachestore_miss_stream`   | Miss tracking (thundering-herd prevention) |
| `cachestore_locks` / `cachestore_locks_stream` | Distributed locks                          |

### Variable access

```lua
-- via utils, with multisite site-search
value, err = utils.get_variable("SETTING_NAME", true, ctx)

-- from a plugin instance, already resolved at init
value = self.variables["SETTING_NAME"]

-- multisite settings are prefixed with the server name:
-- www.example.com_USE_ANTIBOT=captcha
```

## Layout

- `lua/bunkerweb/` — the runtime modules
- `lua/middleclass.lua` — third-party, untouched
- `loading/index.html` — the page served while BunkerWeb initializes
- `misc/` — static assets: `asn.mmdb` and `country.mmdb` as GeoIP bootstrap fallbacks (there is deliberately no `city.mmdb`, it is ~125 MB and downloaded on demand), plus `root-ca.pem`
- `entrypoint.sh` — startup: detect the integration mode, generate the temporary config, start NGINX
- `Dockerfile` — multi-stage: compile the NGINX deps from `src/deps/`, then assemble the runtime image, which runs as `nginx:nginx`

## Commands

```bash
docker build -f src/bw/Dockerfile -t bunkerweb:dev .
docker build -f src/bw/Dockerfile -t bunkerweb:dev --build-arg SKIP_MINIFY=yes .   # skip HTML minification

stylua src/bw/lua/bunkerweb/
luacheck src/bw/lua --std min --codes --ranges --no-cache
shellcheck src/bw/entrypoint.sh
pre-commit run --all-files
```

Lua style is configured at the repo root: `.luacheckrc` (declared globals and ignored codes — read the comments there, a global that looks removable is not always) and `stylua.toml` (`call_parentheses = "Input"`, sorted requires).

## Runtime Gotchas

- Cosockets are unavailable in the init, init_worker and log phases; code that forgets this fails at runtime only under load.
- `KEEP_CONFIG_ON_RESTART=yes` skips temporary-config regeneration and preserves the existing NGINX config across restarts.
- Logs are redirected to `/proc/1/fd/{1,2}` (container stdout/stderr).
- The entrypoint traps SIGTERM (stop) and SIGHUP (reload) and waits on the NGINX process.
- Container layout: code under `/usr/share/bunkerweb/` (`lua/`, `core/`, `confs/`, `gen/`, `helpers/`, `utils/`), persistent volume at `/data/` (cache, lib, www, configs, plugins, pro), generated config in `/etc/nginx/`.
