# AGENTS.md

Local agent guide for the BunkerWeb NGINX/Lua runtime in `src/bw/`.

## Read First

- Root guide: [../../AGENTS.md](../../AGENTS.md)
- Long-form runtime notes: [CLAUDE.md](CLAUDE.md)
- Common guide: [../common/AGENTS.md](../common/AGENTS.md)

## Critical Rules

- This component has no Python application code; it packages NGINX, Lua runtime, entrypoint, and static assets.
- Request behavior runs through Lua plugin phases and `PLUGINS_ORDER_<PHASE>`.
- Respect HTTP vs stream subsystem differences and shared dict names.
- Redis, DNS, and other async operations require cosocket-available phases.
- `lua/middleclass.lua` is third-party code; do not lint or modify it.
- Generated NGINX config comes from shared config generation, not ad hoc runtime edits.

## Commands

```bash
docker build -f src/bw/Dockerfile -t bunkerweb:dev .
docker build -f src/bw/Dockerfile -t bunkerweb:dev --build-arg SKIP_MINIFY=yes .
stylua src/bw/lua/bunkerweb/
luacheck src/bw/lua --std min --codes --ranges --no-cache
shellcheck src/bw/entrypoint.sh
pre-commit run --all-files
```

## Pitfalls

- Runtime container paths live under `/usr/share/bunkerweb/`, `/etc/nginx/`, and `/data/`.
- Cosockets are unavailable in init, init_worker, and log phases; use fallbacks.
- `KEEP_CONFIG_ON_RESTART=yes` preserves existing NGINX config across restarts.
- Logs are redirected to container stdout/stderr through `/proc/1/fd/{1,2}`.
