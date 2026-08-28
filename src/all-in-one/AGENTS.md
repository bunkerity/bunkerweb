# AGENTS.md

Agent guide for the BunkerWeb all-in-one (AIO) Docker image in `src/all-in-one/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Root: [../../AGENTS.md](../../AGENTS.md) (short) and [../../CLAUDE.md](../../CLAUDE.md) (architecture)
- Build reference: [../../BUILD.md](../../BUILD.md)

## What This Is

Every BunkerWeb component in a single container managed by **supervisord**: BunkerWeb (NGINX), Scheduler, Worker, UI, API, Autoconf, Redis, CrowdSec and a log-streaming service. Only AIO-specific behavior is documented here.

## Critical Rules

- Service toggles are applied by `entrypoint.sh` — it `sed`s `autostart`/`autorestart` in the `supervisor.d/*.ini` files **before** supervisord starts.
- `SERVICE_WORKER` defaults to enabled only when `SERVICE_SCHEDULER=yes`. Keep the Scheduler/Worker/API coupling intact.
- Persistent data is rooted at `/data` and exposed through symlinks to the standard runtime paths.
- CrowdSec, Redis and logstream behavior is AIO-specific — do not leak those assumptions into the standalone components.
- Dependency versions are bumped in `deps/*.json` and read by the Dockerfile through `jq`.

## Build and Run

```bash
docker build -f src/all-in-one/Dockerfile -t bunkerweb:dev .                              # context = repo root
docker build -f src/all-in-one/Dockerfile --build-arg SKIP_MINIFY=yes -t bunkerweb:dev .  # faster dev build
docker compose -f misc/dev/docker-compose.all-in-one.yml up -d
pre-commit run --all-files
```

Multi-stage: the builder compiles Go (for CrowdSec), re2, CrowdSec, the NGINX deps and the Python packages; the final stage is the Debian `nginx` runtime image — migrated off Alpine because the certbot-dns-multi lego bridge is glibc-only. **`procps` is required**: the supervisord→main-app handoff and the container healthcheck (`src/common/helpers/healthcheck-all-in-one.sh`, shipped to `/usr/share/bunkerweb/helpers/`) use `kill`/`pgrep`/`pkill`.

Dev ports: 80→8080, 443→8443 (TCP/UDP), 7000 for the UI. Credentials match the root guide.

## Service Management

Supervisord (`supervisord.conf`, per-service `supervisor.d/*.ini`) starts services by priority:

| Priority | Service   | Toggle              | Default                                                              |
| -------- | --------- | ------------------- | -------------------------------------------------------------------- |
| 10       | bunkerweb | (always on)         | yes                                                                  |
| 12       | redis     | `USE_REDIS`         | yes                                                                  |
| 12       | crowdsec  | `USE_CROWDSEC`      | no                                                                   |
| 15       | logstream | (always on)         | yes                                                                  |
| 20       | ui        | `SERVICE_UI`        | yes                                                                  |
| 25       | api       | `SERVICE_API`       | no                                                                   |
| 28       | worker    | `SERVICE_WORKER`    | yes, only when `SERVICE_SCHEDULER=yes` (auto-set by `entrypoint.sh`) |
| 30       | scheduler | `SERVICE_SCHEDULER` | yes                                                                  |
| 30       | autoconf  | `AUTOCONF_MODE`     | no                                                                   |

### Entrypoint flow

1. Source the helpers (`/usr/share/bunkerweb/helpers/utils.sh`) and set up the `/data` folder.
2. Create the Redis/CrowdSec data directories if needed.
3. Handle Docker secrets (`handle_docker_secrets`).
4. Detect the integration mode (Swarm/Kubernetes/Autoconf) and write the `INTEGRATION` file.
5. Install signal traps (SIGTERM/SIGINT → graceful shutdown, SIGHUP → reload).
6. Configure the supervisor `.ini` files for the enabled services.
7. With CrowdSec enabled: register the machine, set up the bouncer, install or upgrade collections and parsers.
8. With Redis enabled on a local host: ensure the symlinks and enable the service.
9. Start supervisord in the foreground and wait on its PID.

### Log streaming

`logstream.sh` tails the NGINX access/error logs and the ModSecurity audit log to container stdout/stderr with prefixes (`[NGINX.ACCESS]`, `[NGINX.ERROR]`, `[MODSEC]`). `service-log-wrapper.sh` wraps a service command and tees its output with a prefix. `logging-utils.sh` implements `HIDE_SERVICE_LOGS`.

## Bundled Dependencies

Compiled in the builder stage, pinned in `deps/*.json` (`go.json`, `crowdsec.json`, `re2.json` — version, URL, commit, per-arch checksums). Build scripts live in `scripts/` (`install-go.sh`, `install-crowdsec.sh`, `install-re2.sh`, and `utils.sh` providing `git_clone_commit`). To bump a version, edit the JSON — the Dockerfile reads it with `jq`.

## CrowdSec Configuration (`conf/`)

- `config.yaml` — SQLite DB under `/var/lib/crowdsec/data`, local API on `127.0.0.1:8000`, Prometheus on `127.0.0.1:6060`
- `acquis.yaml` — acquisition of the BunkerWeb `access.log`, `error.log` and `modsec_audit.log`
- `appsec.yaml` — AppSec module on `127.0.0.1:7422`
- `redis.conf` — Redis on `127.0.0.1` with AOF persistence to `/var/lib/redis/`

## Data Persistence

| Container path         | Symlink target                |
| ---------------------- | ----------------------------- |
| `/var/cache/bunkerweb` | `/data/cache`                 |
| `/var/lib/bunkerweb`   | `/data/lib`                   |
| `/var/www/html`        | `/data/www`                   |
| `/etc/bunkerweb/*`     | `/data/{configs,plugins,pro}` |
| `/var/lib/crowdsec`    | `/data/crowdsec`              |
| `/var/lib/redis`       | `/data/redis`                 |

Exposed ports: `8080` HTTP, `8443` HTTPS (TCP + UDP/QUIC), `7000` UI, `8888` API when `SERVICE_API=yes`.

## Environment (AIO-specific)

- `SERVICE_UI`, `SERVICE_SCHEDULER`, `SERVICE_API` — per-service toggles.
- `SERVICE_WORKER` — the Celery worker. `entrypoint.sh` defaults it to `yes` only when `SERVICE_SCHEDULER=yes`; set it explicitly to override.
- `WORKER_CONCURRENCY` / `WORKER_MAX_MEMORY_KB` / `WORKER_QUEUES` — worker tuning. **The AIO worker hostname is hardcoded to `worker@%%h` in `supervisor.d/worker.ini`; there is no `WORKER_HOSTNAME` override here.**
- `AUTOCONF_MODE` — enables the autoconf service.
- `USE_CROWDSEC` / `CROWDSEC_API` / `CROWDSEC_API_KEY` / `CROWDSEC_APPSEC_URL`, plus `CROWDSEC_EXTRA_COLLECTIONS` / `CROWDSEC_DISABLE_PARSERS` (space-separated).
- `USE_REDIS` / `REDIS_HOST` — defaults to local `127.0.0.1`.
- `HIDE_SERVICE_LOGS` — comma-separated service keys to suppress (e.g. `nginx.access,modsec`).
- **`MULTISITE` defaults to `yes` in AIO**, unlike standalone BunkerWeb.

## Shell Conventions

Scripts use `#!/bin/bash` with `set -euo pipefail`, except `entrypoint.sh`, which omits `set -e` for controlled error handling. ShellCheck is the linter; `entrypoint.sh` carries several `SC2317` disables because of functions used in traps. Log output goes through the `log` helper: `log "COMPONENT" "emoji" "message"`.
