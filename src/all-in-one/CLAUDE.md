# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

The all-in-one (AIO) image packages every BunkerWeb component into a single Docker container managed by **supervisord**. It bundles: BunkerWeb (NGINX), Scheduler, Worker, UI, API, Autoconf, Redis, CrowdSec, and a log streaming service.

See the root `CLAUDE.md` for the overall BunkerWeb architecture — this file covers AIO-specific details only.

## Build

```bash
# From repo root (build context must be the repo root)
docker build -f src/all-in-one/Dockerfile -t bunkerweb:dev .

# Skip asset minification for faster dev builds
docker build -f src/all-in-one/Dockerfile --build-arg SKIP_MINIFY=yes -t bunkerweb:dev .
```

The Dockerfile is a multi-stage build: a `builder` stage compiles Go (for CrowdSec), re2, CrowdSec, NGINX deps, and Python packages; the final stage is `nginx:1.30.2` (Debian/trixie — migrated off Alpine because the certbot-dns-multi lego bridge is glibc-only). `procps` is required (the supervisord→main-app handoff and `healthcheck-all-in-one.sh` use `kill`/`pgrep`/`pkill`).

## Run (Dev)

```bash
docker compose -f misc/dev/docker-compose.all-in-one.yml up -d
```

Ports: 80->8080, 443->8443 (TCP/UDP), 7000 (UI). Uses MariaDB. Dev credentials match the root CLAUDE.md.

## Architecture

### Service Management

Supervisord manages 9 services with priority-based startup order:

| Priority | Service   | Toggle Env Var      | Default                                                              |
| -------- | --------- | ------------------- | -------------------------------------------------------------------- |
| 10       | bunkerweb | (always on)         | yes                                                                  |
| 12       | redis     | `USE_REDIS`         | yes                                                                  |
| 12       | crowdsec  | `USE_CROWDSEC`      | no                                                                   |
| 15       | logstream | (always on)         | yes                                                                  |
| 20       | ui        | `SERVICE_UI`        | yes                                                                  |
| 25       | api       | `SERVICE_API`       | no                                                                   |
| 28       | worker    | `SERVICE_WORKER`    | yes (only when `SERVICE_SCHEDULER=yes`; auto-set by `entrypoint.sh`) |
| 30       | scheduler | `SERVICE_SCHEDULER` | yes                                                                  |
| 30       | autoconf  | `AUTOCONF_MODE`     | no                                                                   |

Config files: `supervisor.d/*.ini`. Supervisord config: `supervisord.conf`.

Services are toggled by `entrypoint.sh` using `sed` to flip `autostart`/`autorestart` in `.ini` files before supervisord starts.

### Entrypoint Flow (`entrypoint.sh`)

1. Sources helpers (`/usr/share/bunkerweb/helpers/utils.sh`) and runs `/data` folder setup
2. Creates Redis/CrowdSec data directories if needed
3. Handles Docker secrets (`handle_docker_secrets`)
4. Detects integration mode (Swarm/Kubernetes/Autoconf) and writes to `INTEGRATION` file
5. Sets up signal traps (SIGTERM/SIGINT -> graceful shutdown, SIGHUP -> reload)
6. Configures supervisor `.ini` files for enabled/disabled services
7. If CrowdSec enabled: registers machine, sets up bouncer, installs/upgrades collections and parsers
8. If Redis enabled with local host: ensures symlinks and enables service
9. Starts supervisord in foreground, waits on PID

### Log Streaming

- `logstream.sh`: Tails NGINX access/error logs and ModSecurity audit logs to container stdout/stderr with prefixes (`[NGINX.ACCESS]`, `[NGINX.ERROR]`, `[MODSEC]`)
- `service-log-wrapper.sh`: Wraps service commands, tees output to log files with configurable prefix
- `logging-utils.sh`: Provides `HIDE_SERVICE_LOGS` env var support (comma-separated service keys to suppress)

### Bundled Dependencies

Compiled in the builder stage, versions pinned in `deps/*.json`:

- **Go** (`go.json`): Used to compile CrowdSec and re2. Multi-arch checksums (amd64, arm64, armv6l, 386).
- **CrowdSec** (`crowdsec.json`): Built with static linking. Version and commit pinned.
- **re2** (`re2.json`): Google regex library. Version and commit pinned.

Build scripts in `scripts/`: `install-go.sh`, `install-crowdsec.sh`, `install-re2.sh`, `utils.sh` (provides `git_clone_commit` helper).

### CrowdSec Configuration (`conf/`)

- `config.yaml`: Main CrowdSec config — SQLite DB at `/var/lib/crowdsec/data`, local API on `127.0.0.1:8000`, Prometheus on `127.0.0.1:6060`
- `acquis.yaml`: Log acquisition for BunkerWeb logs (`access.log`, `error.log`, `modsec_audit.log`)
- `appsec.yaml`: AppSec module listening on `127.0.0.1:7422`
- `redis.conf`: Redis on `127.0.0.1`, AOF persistence to `/var/lib/redis/`

### Data Persistence

The `/data` volume holds all persistent state. Symlinks map standard paths to `/data`:

| Container Path         | Symlink Target                | Purpose                |
| ---------------------- | ----------------------------- | ---------------------- |
| `/var/cache/bunkerweb` | `/data/cache`                 | Cache files            |
| `/var/lib/bunkerweb`   | `/data/lib`                   | Runtime data           |
| `/var/www/html`        | `/data/www`                   | Web content            |
| `/etc/bunkerweb/*`     | `/data/{configs,plugins,pro}` | Custom configs/plugins |
| `/var/lib/crowdsec`    | `/data/crowdsec`              | CrowdSec data          |
| `/var/lib/redis`       | `/data/redis`                 | Redis persistence      |

### Exposed Ports

- `8080`: HTTP
- `8443`: HTTPS (TCP + UDP/QUIC)
- `7000`: Web UI
- `8888`: API (when `SERVICE_API=yes`)

## Key Environment Variables (AIO-specific)

These are unique to the AIO image (not in the root CLAUDE.md):

- `SERVICE_UI`, `SERVICE_SCHEDULER`, `SERVICE_API`: Enable/disable individual services
- `SERVICE_WORKER`: Enable/disable the Celery worker service. `entrypoint.sh` auto-defaults it to `yes` only when `SERVICE_SCHEDULER=yes`; set it explicitly to override
- `WORKER_CONCURRENCY` / `WORKER_MAX_MEMORY_KB` / `WORKER_QUEUES`: Worker tuning knobs (concurrency default 2, memory cap default 300000 KB, queues default `default,heavy`). The AIO worker hostname is hardcoded to `worker@%%h` in `supervisor.d/worker.ini` — there is no `WORKER_HOSTNAME` override here
- `AUTOCONF_MODE`: Enables the autoconf service
- `USE_CROWDSEC` / `CROWDSEC_API` / `CROWDSEC_API_KEY` / `CROWDSEC_APPSEC_URL`: CrowdSec configuration
- `CROWDSEC_EXTRA_COLLECTIONS` / `CROWDSEC_DISABLE_PARSERS`: Space-separated lists for CrowdSec customization
- `USE_REDIS` / `REDIS_HOST`: Redis configuration (defaults to local `127.0.0.1`)
- `HIDE_SERVICE_LOGS`: Comma-separated service keys to suppress in output (e.g., `nginx.access,modsec`)
- `MULTISITE`: Defaults to `yes` in AIO (unlike standalone BunkerWeb)

## Shell Script Conventions

- All scripts use `#!/bin/bash` and `set -euo pipefail` (except `entrypoint.sh` which omits `set -e` for controlled error handling)
- `shellcheck` is the linter — many `SC2317` disables exist in `entrypoint.sh` due to functions used in traps
- Log output uses the `log` helper from `/usr/share/bunkerweb/helpers/utils.sh` with format: `log "COMPONENT" "emoji" "message"`

## Updating Dependency Versions

To update Go, CrowdSec, or re2: edit the corresponding `deps/*.json` file (version, URL, commit, checksums). The `Dockerfile` reads these at build time via `jq`.
