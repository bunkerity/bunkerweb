# AGENTS.md

Agent guide for `tests/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Root: [../AGENTS.md](../AGENTS.md) (short) and [../CLAUDE.md](../CLAUDE.md) (architecture)
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
export BW_TESTS_ETC=/tmp/bunkerweb-tests/etc            # keep generated env files off a real install
./tests/scripts/test.sh docker core dev headers         # <integration> <type> <release> <category>
```

`test.sh` chains `build.sh` then `run.sh`; the other scripts in `tests/scripts/` are the stack lifecycle (`start`, `stop`, `restart`, `wait`, `log`) plus the `before/` and `after/` hooks.

## Writing a Spec

One YAML file per subject under `core/`, `api/`, `ui/`. Each file declares actions; an action's `type` selects both the Pydantic model that validates it and the handler that runs it. Per-integration overrides live inside the action (`Docker:`, `Linux:`, …), where a `null` value **deletes** the inherited key rather than overriding it.

Adding a core action type is four edits — a model in `models/`, a handler in `core_handlers/`, an export in `core_handlers/__init__.py`, a dispatch branch in `core.py`. A UI step is three — model in `models/ui/`, handler in `ui_handlers/`, dispatch in `ui.py`.

**Nothing rejects a key a model does not declare — Pydantic drops it.** A misspelt or invented field means the assertion you thought you wrote never runs. The current action types are listed in the README; the models directory is the authority.

## Gotchas

- **The legacy harness is gone.** `tests/main.py`, the `*Test.py` classes, `tests/examples/*.json` and `legacy-requirements.{in,txt}` were deleted once the Swarm arm and Linux example mode landed. `staging-tests.yml` was its only caller and now runs nothing — read its header before touching the staging pipeline. `tests/scripts/test.sh` is the entry point; the `core.py` / `api.py` / `ui.py` runners below it can be driven directly for a single spec, but nothing else orchestrates a run.
- Example stacks are covered by `core/example-*.yml`, one spec per `examples/<name>/` directory, with the `example:` key naming the directory to deploy. The assertions live here, not in the example folder, so user-facing documentation carries none. Two arms are deliberately not covered — `nextcloud` and `wordpress` on Linux — and each spec says why in its `integrations:` block.
- **`linux-build.yml` pushes a `<distro>-tests` image that nothing pulls.** Its only consumer was the deleted staging arm; the Linux integration builds its systemd runtime locally instead (`integration-tests.yml`, `docker build -f tests/linux/Dockerfile-<distro>`). Every pipeline passing `TEST: true` still builds and pushes it. Give it a consumer or drop the push — do not assume it is load-bearing because it is still there.
- **The Linux arm runs one distro.** All four `parse.py` callers pass `--dev`, and `utils/integrations.yml`'s `dev:` block lists `ubuntu/noble` alone. The `staging:` block's nine live distro rows have no caller at all: adding a spec does not widen distro coverage, and nothing in CI will tell you so.
- **A healthy stack is not a configured one.** The scheduler queues `push-configs` and returns, so `wait.sh` waits for the worker to report that job done before any action runs. `wait_config.py` additionally requires the scheduler's change flags to be clear — `certificates_changed` is in that list because a certificate provider and `deploy-certificates` race in the same batch.
- **Every framework-managed current stack carries bunkerweb, scheduler, API, worker and broker.** Docker examples provide their own stack, and pre-1.7 upgrade stages do not use this topology. Drop one from a current framework-managed stack and it still boots, runs zero jobs, and passes any test that never needed one. All-in-one is exempt — its entrypoint enables the worker and forces the API on by itself.
- The job broker is **not** the WAF datastore Redis; 1.7 split those roles and core specs assert on datastore keys.
- `database` actions run their SQL in the API container: the scheduler image lost `sqlite3` when the database clients moved to the API, and both mount the same volume.
- **Do not edit anything under `tests/scripts/` while a run is in flight.** Bash reads a script incrementally by byte offset, so an insert above the current point shifts the rest of the file and the running shell dies on a syntax error that is not in the file. The verdict up to that point is still valid; the final `All tests passed` and the exit code are not.
- Every compose file under `tests/docker/` and `tests/misc/docker/` shares one implicit compose project, so a `down` targets the project, not the file — and the end-of-run cleanup adds `--remove-orphans`. Give a new compose file an explicit top-level `name:` if it must be torn down on its own.
- Some actions address a container by name from the runner (`bunkernet` talks straight to its custom API). CI appends `tests/misc/conf/dnsmasq.hosts` to `/etc/hosts`; read that file before doing the same locally — it maps bare names like `redis` and `valkey` system-wide.

## CI

`.github/workflows/integration-tests.yml` is the reusable entry point, taking `TYPE`, `TEST` (`INTEGRATION;ARCH;RUNS_ON;TEST`) and `RELEASE`. `utils/integrations.yml` maps each integration and architecture to a runner. Swarm rows sit at `TODO`; ARM is disabled on purpose (a matrix would hold an on-demand ARM node for a whole run).
