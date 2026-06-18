# AGENTS.md

Local agent guide for native Linux and FreeBSD packaging in `src/linux/`.

## Read First

- Root guide: [../../AGENTS.md](../../AGENTS.md)
- Long-form packaging notes: [CLAUDE.md](CLAUDE.md)
- Build reference: [../../BUILD.md](../../BUILD.md)

## Critical Rules

- Package builds use distro Dockerfiles plus `fpm-*` option files; FreeBSD builds natively, not in Docker.
- Keep DEB, RPM, and FreeBSD lifecycle behavior aligned where applicable.
- Linux packages ship Scheduler, Worker, API, UI, and BunkerWeb services; FreeBSD does not yet package the Celery worker.
- Service scripts source shared helpers and read `/etc/bunkerweb/*.env` files.
- Preserve `MANAGER_MODE`, `WORKER_MODE`, and `SERVICE_*` enablement logic in postinstall scripts.
- Shell scripts must pass ShellCheck and use the correct POSIX vs Bash shebang.

## Commands

```bash
docker build -f src/linux/Dockerfile-ubuntu -t local/bunkerweb-ubuntu:latest .
bash src/linux/package.sh ubuntu amd64
docker build -f src/linux/Dockerfile-rhel-9 -t local/bunkerweb-rhel-9:latest .
bash src/linux/package.sh rhel-9 x86_64
pre-commit run --all-files
```

## Pitfalls

- fpm files use `%VERSION%` and `%ARCH%` placeholders replaced by `fpm.sh`.
- Runtime paths and ownership differ between application files and data directories.
- `do_and_check_cmd` is the common lifecycle-script pattern.
- The broker service is enabled by postinstall when the Worker will run.
