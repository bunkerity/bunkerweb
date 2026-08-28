# AGENTS.md

Agent guide for native Linux packaging (DEB, RPM) in `src/linux/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Root: [../../AGENTS.md](../../AGENTS.md) (short) and [../../CLAUDE.md](../../CLAUDE.md) (architecture)
- Build reference: [../../BUILD.md](../../BUILD.md)

## What This Is

Everything needed to build native Linux packages, plus the systemd units and lifecycle scripts that run on an installed system.

FreeBSD is **not** packaged here. It is served by the official `www/bunkerweb` port, which builds from the source tarball with its own rc.d scripts and patches. The runtime still detects FreeBSD (`src/common/confs/nginx.conf` selects kqueue, `src/common/helpers/utils.sh` resolves the nginx paths and drives rc.d) — only the in-repo packaging lane is gone.

## Critical Rules

- Package builds use the per-distro Dockerfile plus its `fpm-*` options file. Keep DEB and RPM lifecycle behavior aligned where it applies.
- Linux packages ship the BunkerWeb, Scheduler, Worker, API and UI services.
- Service scripts source the shared helpers and read `/etc/bunkerweb/*.env`.
- Preserve the `MANAGER_MODE`, `WORKER_MODE` and `SERVICE_*` enablement logic in the postinstall script.
- Shell scripts must pass ShellCheck, with the right shebang: `#!/bin/bash` for bash features, `#!/bin/sh` for POSIX-only.

## Build Pipeline

Each supported distro has three artifacts, named by convention — run `ls src/linux/Dockerfile-*` for the current supported set:

1. **`Dockerfile-<distro>`** — multi-stage image compiling NGINX and the BunkerWeb dependencies (C libraries and Python packages), minifying the frontend assets, installing `fpm`, producing the packaging image.
2. **`fpm-<distro>`** — the fpm options file: package metadata, dependencies, file mappings. Uses the `%VERSION%` and `%ARCH%` placeholders.
3. **`fpm.sh`** — the entrypoint inside the image; substitutes the placeholders and runs `fpm`. Shared by every distro of the same package type.

```
package.sh <distro> <arch> [version]
  -> docker run local/bunkerweb-<distro>
       -> fpm.sh <deb|rpm>
            -> fpm (reads the .fpm options file) -> /data/bunkerweb.<type>
```

```bash
docker build -f src/linux/Dockerfile-ubuntu -t local/bunkerweb-ubuntu:latest .
bash src/linux/package.sh ubuntu amd64          # -> package-ubuntu/bunkerweb_<version>-1_amd64.deb

docker build -f src/linux/Dockerfile-rhel-9 -t local/bunkerweb-rhel-9:latest .
bash src/linux/package.sh rhel-9 x86_64         # package type is auto-detected

pre-commit run --all-files
```

## Systemd Services

Five units, all `Type=simple` with `Restart=always`:

| Service                       | Script                           | PID file                | Purpose                                                                                                                                                                                                                                 |
| ----------------------------- | -------------------------------- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `bunkerweb.service`           | `scripts/start.sh`               | `nginx.pid`             | NGINX reverse proxy                                                                                                                                                                                                                     |
| `bunkerweb-scheduler.service` | `scripts/bunkerweb-scheduler.sh` | `scheduler.pid`         | Job scheduler and DB migrations. Pre-initializes the DB (`save_config.py --init`) before `main.py` to break the scheduler↔API↔DB-init deadlock                                                                                          |
| `bunkerweb-worker.service`    | `scripts/bunkerweb-worker.sh`    | `worker.pid`            | Celery job executor, peer of the scheduler: it runs the jobs the scheduler dispatches, `push-configs` included. The broker (redis-server/valkey/redis) is an fpm `--depends` and is enabled by the postinstall when the worker will run |
| `bunkerweb-ui.service`        | `scripts/bunkerweb-ui.sh`        | `ui.pid` / `tmp-ui.pid` | Web UI (gunicorn)                                                                                                                                                                                                                       |
| `bunkerweb-api.service`       | `scripts/bunkerweb-api.sh`       | `api.pid`               | REST API (gunicorn). The scheduler hard-requires it — they share a generated `API_TOKEN` through `variables.env` — so it is enabled whenever the scheduler is                                                                           |

## Lifecycle Scripts

- `scripts/beforeInstall.sh` — backs up `/etc/nginx`, creates the scheduler enablement flag for upgrades from ≤ 1.5.12.
- `scripts/postinstall.sh` — decompresses the deps, sets permissions, migrates config files from old locations, enables/disables services per the mode variables, runs the setup wizard on a fresh install.
- `scripts/afterRemoveDEB.sh` — remove vs purge vs upgrade; backs up env files and the database during upgrades.
- `scripts/afterRemoveRPM.sh` — the same logic under RPM's `$1` convention (`0` = remove, `1` = upgrade).

### Service modes (postinstall)

- **Standalone** (default, neither mode set): BunkerWeb + Scheduler + Worker + API + UI.
- **Manager-only** (`MANAGER_MODE=yes`): Scheduler + Worker + API + UI; BunkerWeb disabled.
- **Worker-only** (`WORKER_MODE=yes`): BunkerWeb enabled; Scheduler, Celery worker and UI disabled.
- The Celery worker and the API follow the scheduler, since the scheduler dispatches jobs through the API. `SERVICE_API=no` opts the API out; `SERVICE_BUNKERWEB=no`, `SERVICE_SCHEDULER=no`, `SERVICE_UI=no` disable individual services.

## Runtime Script Patterns

Every service script sources `/usr/share/bunkerweb/helpers/utils.sh` for `get_python_bin`, `get_bunkerweb_pythonpath`, `run_as_nginx`, `export_env_file` and `log`; runs BunkerWeb processes as the `nginx` user through `run_as_nginx`; and reads `/etc/bunkerweb/variables.env` plus its own component env file (`scheduler.env`, `worker.env`, `ui.env`, `api.env`). The API service script supports `start|stop|reload`; the other service scripts also expose `restart`. `do_and_check_cmd` is the checked-execution pattern used throughout.

## Installed Layout

| Path                    | Purpose                                                                                                     |
| ----------------------- | ----------------------------------------------------------------------------------------------------------- |
| `/usr/share/bunkerweb/` | Application code, plugins, deps                                                                             |
| `/etc/bunkerweb/`       | Configuration (`variables.env`, `scheduler.env`, `worker.env`, `ui.env`, `api.env`, `plugins/`, `configs/`) |
| `/var/lib/bunkerweb/`   | Persistent data (`db.sqlite3`)                                                                              |
| `/var/tmp/bunkerweb/`   | Temporary files (setgid 2770)                                                                               |
| `/var/log/bunkerweb/`   | Logs (rotated by `bunkerweb.logrotate`)                                                                     |
| `/var/run/bunkerweb/`   | PID files                                                                                                   |
| `/var/cache/bunkerweb/` | Cache                                                                                                       |

Ownership is `root:nginx` for application files and `nginx:nginx` for runtime and data directories. Dependencies ship compressed as `deps.tar.gz` (with `pigz` when available) and are decompressed by the postinstall.

## Adding a Distro

1. Copy the closest `Dockerfile-<distro>` (Ubuntu/Debian for DEB, RHEL for RPM).
2. Write `fpm-<distro>` with that distro's package names.
3. For RPM distros needing Rocky repos, add `rocky-<ver>.repo` and the matching GPG key.
4. Update the distro detection in `package.sh` if the naming differs.
5. `fpm.sh` and the lifecycle scripts are shared — nothing to add there.
