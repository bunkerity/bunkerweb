# AGENTS.md

Agent guide for `tests/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Root: [quick guide](../AGENTS.md#fast-start) and [architecture](../ARCHITECTURE.md#architecture)
- **[README.md](README.md)** — the full integration-framework manual: writing specs, per-integration overrides, running locally, stack shape, CI. This guide orients; that one explains.
- **[unit/README.md](unit/README.md)** — the pytest suite: venv setup, the engine matrix, the `api_app` lane, the coverage gate.

## The Two Suites Share No Tooling

| Suite                  | Path                  | What it is                                                                                                                  |
| ---------------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Unit                   | `tests/unit/`         | Fast pytest over the Python layers, multi-engine (SQLite / PostgreSQL / MariaDB). Own venv (`.venv-unit`), own requirements |
| Integration / API / UI | `tests/` (this level) | YAML specs validated by Pydantic models, executed by Python runners, orchestrated from shell                                |

```bash
# Unit
python3 -m venv .venv-unit
.venv-unit/bin/pip install --require-hashes -r tests/unit/requirements.txt
.venv-unit/bin/pytest                                   # SQLite
.venv-unit/bin/pytest --db-engines=sqlite,postgresql,mariadb   # full matrix, see unit/README.md

# Integration
python3 -m venv .venv-tests
.venv-tests/bin/pip install --require-hashes -r tests/requirements.txt
source .venv-tests/bin/activate                         # the shell scripts call bare `python3`
./tests/scripts/test.sh Docker core dev headers         # <integration> <type> <release> <category>
```

Every host path the harness binds or cleans lives under `BW_TESTS_HOST_ROOT` (default `<checkout>/.cache/e2e-host`, see README "Running locally"); `scripts/utils.sh` derives and exports the rest.

`test.sh` chains `build.sh` then `run.sh`; the other scripts in `tests/scripts/` are the stack lifecycle (`start`, `stop`, `restart`, `wait`, `log`) plus the `before/` and `after/` hooks.

## Writing a Spec

One YAML file per subject under `core/`, `api/`, `ui/`. Each file declares actions; an action's `type` selects both the Pydantic model that validates it and the handler that runs it. Per-integration overrides live inside the action (`Docker:`, `Linux:`, …), where a `null` value **deletes** the inherited key rather than overriding it.

Adding a core action type is four edits — a model in `models/`, a handler in `core_handlers/`, an export in `core_handlers/__init__.py`, a dispatch branch in `core.py`. A UI step is three — model in `models/ui/`, handler in `ui_handlers/`, dispatch in `ui.py`.

**Nothing rejects a key a model does not declare — Pydantic drops it.** A misspelt or invented field means the assertion you thought you wrote never runs. The current action types are listed in the README; the models directory is the authority.

## Gotchas

- **The legacy harness is gone.** `tests/main.py`, the `*Test.py` classes, `tests/create.sh`, `tests/rm.sh`, `tests/ansible/`, `tests/terraform/`, the per-feature `tests/core/<name>/` stacks and the `examples/*/tests.json` descriptors were deleted; `staging.yml`, `dev.yml` and `ui.yml` have their own `parse-tests-*` / `run-*-tests-*` jobs. `tests/scripts/test.sh` is the entry point; the `core.py` / `api.py` / `ui.py` runners below it can be driven directly for a single spec, but nothing else orchestrates a run.
- Example stacks are covered by `core/example-*.yml`, one spec per `examples/<name>/` directory, with the `example:` key naming the directory to deploy. The assertions live here, not in the example folder, so user-facing documentation carries none.
- **The Linux arm runs one distro — except from `staging.yml`.** `dev.yml`/`ui.yml` pass `--dev` and get `utils/integrations.yml`'s `dev:` block, `ubuntu/noble` alone; `staging.yml` omits `--dev`, reads the `staging:` block and narrows it in its `parse-tests-core` job (GitHub caps a job's matrix at 256 entries). `utils/packages.yml` maps each row to the `linux-build.yml` leg: dev's `ubuntu` leg is 26.04 (`ubuntu/resolute`), `ubuntu/noble` is the `ubuntu-noble` leg.
- **Swarm is not part of 1.6.** The arm, `tests/swarm/` and the Swarm specs were not imported; a spec naming `Swarm` is skipped with a warning by `parse.py`.
- **1.6 topology: no worker, no jobs broker, no `push-configs` wait.** A framework-managed stack is bunkerweb + scheduler (+ autoconf on Autoconf and Kubernetes, + the UI on a `ui` run, + the standalone API on an `api` run). The scheduler pushes the configuration itself and only reports healthy once it has, so `wait.sh` waits on container health alone. `stack_has_worker()` in `scripts/utils.sh` is keyed on the presence of `src/worker/` (never on a version string: CI stamps `src/VERSION` with `dev`/`testing`) and `utils.sh` refuses a checkout that answers yes. `API_TOKEN` stays set on every stack: the instance API requires it.
- `database` actions run their SQL in the scheduler container (its image ships `sqlite3`, `mariadb` and `psql` and mounts the same `bw-storage` volume).
- **Do not edit anything under `tests/scripts/` while a run is in flight.** Bash reads a script incrementally by byte offset, so an insert above the current point shifts the rest of the file and the running shell dies on a syntax error that is not in the file. The verdict up to that point is still valid; the final `All tests passed` and the exit code are not.
- Every compose file under `tests/docker/` and `tests/misc/docker/` shares one implicit compose project, so a `down` targets the project, not the file — and the end-of-run cleanup adds `--remove-orphans`. Give a new compose file an explicit top-level `name:` if it must be torn down on its own.
- Some actions address a container by name from the runner (`bunkernet` talks straight to its custom API). CI appends `tests/misc/conf/dnsmasq.hosts` to `/etc/hosts`; read that file before doing the same locally — it maps bare names like `redis` and `valkey` system-wide.
- **A stale app tree left under `$BW_TESTS_WWW` by an old example-stack run collides with a fresh one.** Every harness container bind-mounts it (`tests/docker/docker-compose.bunkerweb.yml` and the scheduler/all-in-one files alongside it) additively — `provision_www_root` "never deletes what is already there" — so a leftover WordPress install, for instance, turns `/wp-admin` into a real directory nginx redirects with a `301` before the fresh container's app is ever reached (`AssertionError: /wp-admin: 301` on `admin_interface_probe`). The files are root-owned (written by containers): clear them with a container, not from the host shell. Docker example compose files under `examples/` still bind-mount the machine's real `/var/www/html`; `utils/example.py` has to rewrite that path to `$BW_TESTS_WWW` when it materialises them.

## CI

`.github/workflows/integration-tests.yml` is the reusable entry point, taking `TYPE`, `TEST` (`INTEGRATION;ARCH;RUNS_ON;TEST`) and `RELEASE`. `utils/integrations.yml` maps each integration and architecture to a runner; ARM is disabled on purpose (a matrix would hold an on-demand ARM node for a whole run).
