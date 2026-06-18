# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See also the [root CLAUDE.md](../../CLAUDE.md) for project-wide architecture, build commands, and conventions.

## Purpose

This directory contains everything needed to build native Linux and FreeBSD packages (DEB, RPM, FreeBSD `.pkg`) for BunkerWeb, plus the systemd/rc.d service definitions and lifecycle scripts that run on installed systems.

## Architecture

### Package Build Pipeline

Each supported distro has three artifacts:

1. **`Dockerfile-<distro>`** — Multi-stage Docker image that compiles NGINX, BunkerWeb dependencies (C libs + Python packages), minifies frontend assets, installs `fpm`, and produces the final packaging image.
2. **`fpm-<distro>`** — fpm options file (`.fpm`) declaring package metadata, dependencies, and file mappings. Uses `%VERSION%` and `%ARCH%` placeholders replaced at build time.
3. **`fpm.sh`** — Entrypoint script inside the Docker image that substitutes placeholders and runs `fpm` to produce the package.

**FreeBSD** is special: it cannot be built in Docker. `build-freebsd.sh` runs natively on a FreeBSD host, stages the entire tree under `/tmp/bunkerweb-stage`, builds dependencies via `src/deps/install-freebsd.sh`, and calls `fpm` directly.

### Build Flow

```
package.sh <distro> <arch> [version]
  └─ docker run local/bunkerweb-<distro>
       └─ fpm.sh <deb|rpm>
            └─ fpm (reads .fpm options file) → /data/bunkerweb.<type>
```

Build a packaging Docker image first, then run `package.sh`:

```bash
# From repo root
docker build -f src/linux/Dockerfile-ubuntu -t local/bunkerweb-ubuntu:latest .
bash src/linux/package.sh ubuntu amd64
# Output: package-ubuntu/bunkerweb_<version>-1_amd64.deb
```

For RPM-based distros, use the appropriate Dockerfile and the type is auto-detected:

```bash
docker build -f src/linux/Dockerfile-rhel-9 -t local/bunkerweb-rhel-9:latest .
bash src/linux/package.sh rhel-9 x86_64
```

### Supported Distros

| Distro                  | Dockerfile                   | fpm file              | Package type |
| ----------------------- | ---------------------------- | --------------------- | ------------ |
| Ubuntu 26.04 (Resolute) | `Dockerfile-ubuntu`          | `fpm-ubuntu`          | DEB          |
| Ubuntu Noble (24.04)    | `Dockerfile-ubuntu-noble`    | `fpm-ubuntu-noble`    | DEB          |
| Ubuntu Jammy (22.04)    | `Dockerfile-ubuntu-jammy`    | `fpm-ubuntu-jammy`    | DEB          |
| Debian Bookworm         | `Dockerfile-debian-bookworm` | `fpm-debian-bookworm` | DEB          |
| Debian Trixie           | `Dockerfile-debian-trixie`   | `fpm-debian-trixie`   | DEB          |
| RHEL 8                  | `Dockerfile-rhel-8`          | `fpm-rhel-8`          | RPM          |
| RHEL 9                  | `Dockerfile-rhel-9`          | `fpm-rhel-9`          | RPM          |
| RHEL 10                 | `Dockerfile-rhel-10`         | `fpm-rhel-10`         | RPM          |
| Fedora 43               | `Dockerfile-fedora-43`       | `fpm-fedora-43`       | RPM          |
| Fedora 44               | `Dockerfile-fedora-44`       | `fpm-fedora-44`       | RPM          |
| FreeBSD                 | N/A (native build)           | `fpm-freebsd`         | FreeBSD pkg  |

### Systemd Services (Linux)

Five systemd units, all using `Type=simple` with `Restart=always`:

| Service                       | Script                           | PID file                | Purpose                                                                                                                                                                                                 |
| ----------------------------- | -------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `bunkerweb.service`           | `scripts/start.sh`               | `nginx.pid`             | NGINX reverse proxy                                                                                                                                                                                     |
| `bunkerweb-scheduler.service` | `scripts/bunkerweb-scheduler.sh` | `scheduler.pid`         | Job scheduler + DB migrations. Pre-inits the DB (`save_config.py --init`) before `main.py` to break the scheduler↔API↔DB-init deadlock                                                                  |
| `bunkerweb-worker.service`    | `scripts/bunkerweb-worker.sh`    | `worker.pid`            | Celery job executor (runs the jobs the scheduler dispatches, incl. `push-configs`). Peer of the scheduler. Broker = redis-server/valkey/redis, shipped as an fpm `--depends` and enabled by postinstall |
| `bunkerweb-ui.service`        | `scripts/bunkerweb-ui.sh`        | `ui.pid` / `tmp-ui.pid` | Web UI (gunicorn)                                                                                                                                                                                       |
| `bunkerweb-api.service`       | `scripts/bunkerweb-api.sh`       | `api.pid`               | REST API (gunicorn). The scheduler hard-requires it (shares a generated `API_TOKEN` via `variables.env`); enabled whenever the scheduler is enabled                                                     |

### rc.d Services (FreeBSD)

FreeBSD uses `rc.d/` scripts (`bunkerweb`, `bunkerweb_scheduler`, `bunkerweb_ui`, `bunkerweb_api`) that wrap the same `scripts/*.sh` via `/usr/sbin/daemon`. The Celery **worker is not yet packaged for FreeBSD** — there is no `bunkerweb_worker` rc.d script, `fpm-freebsd` declares no broker dependency, and `postinstall-freebsd.sh` does not install or enable it. (Linux DEB/RPM packages do ship `bunkerweb-worker.service` and a `redis-server` dependency.)

### Package Lifecycle Scripts

| Script                            | When                   | Purpose                                                                                                                                                                                                |
| --------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `scripts/beforeInstall.sh`        | Pre-install            | Backs up `/etc/nginx`, creates scheduler enablement flag for upgrades from <= 1.5.12                                                                                                                   |
| `scripts/postinstall.sh`          | Post-install           | Decompresses deps, sets permissions, migrates config files from old locations, manages systemd services based on `MANAGER_MODE`/`WORKER_MODE`/`SERVICE_*` env vars, runs setup wizard on fresh install |
| `scripts/afterRemoveDEB.sh`       | Post-remove (DEB)      | Handles remove vs purge vs upgrade; backs up env files and DB during upgrades                                                                                                                          |
| `scripts/afterRemoveRPM.sh`       | Post-remove (RPM)      | Same logic adapted for RPM's `$1` argument convention (`0`=remove, `1`=upgrade)                                                                                                                        |
| `scripts/postinstall-freebsd.sh`  | Post-install (FreeBSD) | FreeBSD-specific postinstall (delegated from `postinstall.sh`)                                                                                                                                         |
| `scripts/beforeInstallFreeBSD.sh` | Pre-install (FreeBSD)  | FreeBSD-specific pre-install tasks                                                                                                                                                                     |
| `scripts/afterRemoveFreeBSD.sh`   | Post-remove (FreeBSD)  | FreeBSD-specific cleanup (delegated from afterRemove scripts)                                                                                                                                          |

### Service Mode Logic (postinstall.sh)

The postinstall script enables/disables services based on environment variables:

- **Standalone mode** (default, no `MANAGER_MODE`/`WORKER_MODE`): enables BunkerWeb + Scheduler + Worker + API + UI
- **Manager-only mode** (`MANAGER_MODE=yes`, no `WORKER_MODE`): enables Scheduler + Worker + API + UI, disables BunkerWeb
- **Worker-only mode** (`WORKER_MODE=yes`, no `MANAGER_MODE`): enables BunkerWeb, disables Scheduler + Worker + UI
- **bunkerweb-worker** (Celery) and **bunkerweb-api**: enabled wherever the scheduler is enabled (they are peers of the scheduler, since the scheduler dispatches jobs through the API to the Celery worker). `SERVICE_API=no` opts the API out. The broker (redis-server/valkey/redis) is enabled by postinstall when the worker will run.
- Individual services can be disabled with `SERVICE_BUNKERWEB=no`, `SERVICE_SCHEDULER=no`, `SERVICE_UI=no`

### Runtime Script Patterns

All service scripts (`start.sh`, `bunkerweb-scheduler.sh`, `bunkerweb-worker.sh`, `bunkerweb-ui.sh`, `bunkerweb-api.sh`):

- Source `/usr/share/bunkerweb/helpers/utils.sh` for `get_python_bin`, `get_bunkerweb_pythonpath`, `run_as_nginx`, `export_env_file`, `log`
- Accept `start|stop|reload|restart` as the first argument
- Run BunkerWeb processes as the `nginx` user via `run_as_nginx`
- Read configuration from `/etc/bunkerweb/variables.env` plus component-specific env files (`scheduler.env`, `ui.env`, `api.env`)

### Key Filesystem Paths (Installed System)

| Path                    | Purpose                                                                           |
| ----------------------- | --------------------------------------------------------------------------------- |
| `/usr/share/bunkerweb/` | Application code, plugins, deps                                                   |
| `/etc/bunkerweb/`       | Configuration (variables.env, ui.env, scheduler.env, api.env, plugins/, configs/) |
| `/var/lib/bunkerweb/`   | Persistent data (db.sqlite3)                                                      |
| `/var/tmp/bunkerweb/`   | Temporary files (setgid 2770)                                                     |
| `/var/log/bunkerweb/`   | Log files                                                                         |
| `/var/run/bunkerweb/`   | PID files                                                                         |
| `/var/cache/bunkerweb/` | Cache                                                                             |

## Key Conventions

- All shell scripts must pass `shellcheck`. Use `#!/bin/bash` for bash features, `#!/bin/sh` for POSIX-only scripts (FreeBSD rc.d).
- Log rotation: `bunkerweb.logrotate` (Linux), `bunkerweb.newsyslog.conf` (FreeBSD).
- File ownership follows `root:nginx` for application files, `nginx:nginx` for runtime/data directories.
- The `do_and_check_cmd` pattern is used throughout lifecycle scripts for checked command execution.
- Dependencies are compressed as `deps.tar.gz` (using `pigz` when available) during build and decompressed during postinstall.
- fpm options files use `%VERSION%` and `%ARCH%` as placeholders — `fpm.sh` performs the substitution.

## Adding a New Distro

1. Create `Dockerfile-<distro>` based on the closest existing one (Ubuntu/Debian for DEB, RHEL for RPM)
2. Create `fpm-<distro>` with correct package dependencies for that distro's package names
3. For RPM distros that need Rocky repos: add `rocky-<ver>.repo` and `RPM-GPG-KEY-Rocky-<ver>`
4. Update `package.sh` distro detection if the naming convention differs
5. The `fpm.sh` and lifecycle scripts are shared across all distros of the same package type
