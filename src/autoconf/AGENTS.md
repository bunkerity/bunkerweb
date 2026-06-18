# AGENTS.md

Local agent guide for BunkerWeb Autoconf in `src/autoconf/`.

## Read First

- Root guide: [../../AGENTS.md](../../AGENTS.md)
- Long-form Autoconf notes: [CLAUDE.md](CLAUDE.md)
- API guide: [../api/AGENTS.md](../api/AGENTS.md)

## Critical Rules

- Autoconf watches Docker, Swarm, or Kubernetes and writes configuration only through the FastAPI API.
- Controllers translate labels or annotations into settings, services, instances, and custom configs.
- Preserve the shared debounce and `update_needed()` before `apply()` pattern.
- `apply()` must signal Scheduler changes through API metadata and checked-changes calls.
- API degraded mode keeps watching events but skips writes until the API recovers.
- Swarm mode is deprecated but still present.

## Commands

```bash
docker build -f src/autoconf/Dockerfile -t bunkerweb-autoconf:dev .
docker compose -f misc/dev/docker-compose.autoconf.yml up -d
docker compose -f misc/dev/docker-compose.autoconf.yml up -d --force-recreate bw-autoconf
pip install -r src/autoconf/requirements.txt
pre-commit run --all-files
```

## Pitfalls

- Dev compose does not volume-mount Autoconf source; rebuild and recreate for code changes.
- Kubernetes watchers run in multiple threads and share `_internal_lock`.
- `API_ERROR_TIMEOUT` controls when repeated API failures escalate.
- `_set_autoconf_loaded()` should happen once after the first successful apply.
