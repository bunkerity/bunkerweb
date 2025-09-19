# Repository Guidelines

## Project Structure & Module Organization

Source lives in `src/`: `api/` (FastAPI service), `ui/` (admin UI), `linux/` (distribution packages and service units), `bw/` and `common/` (core WAF logic), plus packaging targets like `all-in-one/` and other platform bundles. Integration assets and manifests are under `examples/`, while reusable configuration templates live in `env/`. MkDocs content for docs.bunkerweb.io sits in `docs/`. System tests, fixtures, and helper scripts are consolidated in `tests/`.

## Build, Test, and Development Commands

Bootstrap Python deps per component, e.g. `pip install -r src/api/requirements.txt` or `pip install -r src/ui/requirements.txt`. Build a full appliance image with `docker build -f src/all-in-one/Dockerfile .`. Exercise integrations locally via `python tests/main.py docker`; swap `docker` for `linux`, `autoconf`, `swarm`, or `kubernetes` as needed (set the matching `TEST_DOMAIN*` env vars first). Regenerate docs with `mkdocs serve --watch` from the repo root. Run `pre-commit run --all-files` before pushing to execute the standard formatters and linters.

## Coding Style & Naming Conventions

Python uses Black (160 char lines) and Flake8 with ignores defined in `.pre-commit-config.yaml`; prefer snake_case for modules and functions, PascalCase for classes. Lua code is formatted with StyLua (see `stylua.toml`) and linted with Luacheck; follow lowercase module names and descriptive function names. Shell scripts must pass ShellCheck and stay POSIX-compatible unless a `#!/bin/bash` shebang is explicit. Front-end assets follow Prettier defaults.

## Testing Guidelines

High-level acceptance suites live in `tests/` and orchestrate Dockerized environments—verify Docker access and required `TEST_DOMAIN*` env vars before running. Add scenario files under `examples/<use-case>/tests.json` with descriptive names; tests should assert observable behavior rather than internals. For unit-style Python additions, provide lightweight checks inside the relevant module and hook them into integration flows when feasible. Capture regressions by replicating failing requests in the automated suites.

## Commit & Pull Request Guidelines

Use concise, present-tense messages; the history favors Conventional Commits (`feat:`, `fix:`, `docs:`) or `<component> - …` prefixes. Reference issue IDs when closing or relating tickets. Each PR should include a summary of changes, validation steps (commands or screenshots for UI changes), and updated docs or config when behavior shifts. Coordinate breaking changes with maintainers and flag them clearly in both commit body and PR description.

## Security & Configuration Tips

Never commit secrets—use sample files in `env/` or add new templates when introducing config. Review `.trivyignore` and `.gitleaksignore` before adjusting dependencies. When touching TLS, keys, or rule bundles, document rotation steps and default hardening in the accompanying docs update.
