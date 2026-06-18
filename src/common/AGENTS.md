# AGENTS.md

Local agent guide for BunkerWeb shared libraries in `src/common/`.

## Read First

- Root guide: [../../AGENTS.md](../../AGENTS.md)
- Long-form shared-code notes: [CLAUDE.md](CLAUDE.md)
- Plugin reference: [../../docs/plugins.md](../../docs/plugins.md)

## Critical Rules

- This layer is shared by Scheduler, API, UI, Autoconf, CLI, and Worker. Treat changes as cross-component.
- Settings flow through `settings.json`, plugin `plugin.json` schemas, `Configurator`, DB persistence, and `Templator`.
- DB migrations must support SQLite, MariaDB, MySQL, and PostgreSQL version directories.
- Lua and Python are decoupled; Lua uses NGINX shared dict state synchronized by Scheduler, not Python calls.
- Plugin job names are global across all plugins; avoid collisions.
- Preserve plugin metadata shape and `order.json` execution ordering.

## Commands

```bash
pre-commit run --all-files
python3 tests/main.py docker
```

## Pitfalls

- `Database.py` composes mixins under `db_methods/`; avoid reintroducing monolithic query logic.
- Runtime validation uses compiled regex caches, not only one-time Configurator checks.
- Custom config types include `default_server_http` but not `default_server_stream`.
- Template rendering and API fanout use process/thread pools; keep callables pickleable where required.
