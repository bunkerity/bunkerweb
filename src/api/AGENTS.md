# AGENTS.md

Local agent guide for the BunkerWeb FastAPI control plane in `src/api/`.

## Read First

- Root guide: [../../AGENTS.md](../../AGENTS.md)
- Long-form API notes: [CLAUDE.md](CLAUDE.md)
- Shared code guide: [../common/AGENTS.md](../common/AGENTS.md)

## Critical Rules

- `app/main.py` creates the FastAPI app; `app/routers/core.py` only assembles routers.
- Auth is a per-endpoint dependency, not global middleware. Public routes such as `/health`, `/ping`, `/auth/*`, and docs endpoints bypass it by design.
- Add protected endpoints to the Biscuit ACL path mapping in `app/auth/biscuit.py`.
- Keep service/config mutations on the API path that marks plugin/config changes for the Scheduler.
- Instance broadcast operations use `ApiCaller`; single-instance failures can aggregate to a 502.
- API schemas live in `app/schemas.py`; keep validators aligned with DB enums and accepted method names.

## Commands

```bash
pip install -r src/api/requirements.txt
docker compose -f misc/dev/docker-compose.api.yml up -d
docker compose -f misc/dev/docker-compose.api.misc.yml up -d
docker compose -f misc/dev/docker-compose.ui.api.yml up -d
pre-commit run --all-files
black --line-length 160 src/api/
flake8 --max-line-length=160 --ignore=E266,E402,E501,E722,W503 src/api/
python3 tests/main.py docker
```

## Pitfalls

- API imports shared modules through container-style paths under `/usr/share/bunkerweb/`.
- Startup exits if Biscuit keys, DB init, or auth configuration fail.
- `API_ROOT_PATH` is stripped before rate-limit path matching.
- Celery is used lazily by the jobs router; keep Worker routing behavior in sync with `src/worker/`.
