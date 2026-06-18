# AGENTS.md

Local agent guide for the BunkerWeb Flask web UI in `src/ui/`.

## Read First

- Root guide: [../../AGENTS.md](../../AGENTS.md)
- Long-form UI notes: [CLAUDE.md](CLAUDE.md)
- API guide: [../api/AGENTS.md](../api/AGENTS.md)

## Critical Rules

- UI data access goes through `API_CLIENT` and API client layers. Do not add direct database access.
- `DB` in `app/dependencies.py` is a backward-compatibility shim only.
- The app is Flask/Jinja with vanilla JS, jQuery, and static assets. There is no SPA framework or frontend bundler.
- Use existing blueprint, form validation, `handle_error()`, and `CONFIG_TASKS_EXECUTOR` patterns for route work.
- Keep plugin hook and blueprint priority behavior intact: pro, then external, then core.
- Preserve i18n patterns in `app/static/locales/` and `data-i18n` usage.

## Commands

```bash
docker compose -f misc/dev/docker-compose.ui.api.yml up -d
docker compose -f misc/dev/docker-compose.ui.api.yml restart bw-ui
docker compose -f misc/dev/docker-compose.ui.api.yml up -d --build bw-ui
pre-commit run --all-files
black src/ui/
flake8 src/ui/
prettier --write "src/ui/**/*.{js,css,html,json}"
```

## Pitfalls

- Dev compose mounts UI paths read-only; restart `bw-ui` for code changes, rebuild for dependency or Dockerfile changes.
- `procps` is required for the temp-app handoff and worker reload helpers.
- Sessions use Redis when available, with `SafeFileSystemCache` fallback.
- Frontend minification happens only during Docker build and can be skipped with `SKIP_MINIFY=yes`.
