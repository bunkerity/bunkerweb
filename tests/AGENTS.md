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

- **`tests/main.py` is the legacy harness, not the entry point.** It and the `*Test.py` classes predate the migration; one pipeline (`staging-tests.yml`) still calls them against released artifacts on real domains, and they pin their own `legacy-requirements.{in,txt}`. Two gaps keep them alive: Swarm, which the framework does not run, and the Linux examples, because example mode deploys a compose file while the Linux integration installs a package into a systemd container. `tests/main.py` also _accepts_ an `ansible` argument that has no branch in its dispatch chain — it validates, then exits 1 with `Test.init() failed`.
- Scenario descriptors live in `tests/examples/<name>.json`, one per `examples/<name>/` directory, with `name` pointing back at the directory to deploy. They live here, not in the example folder, so that user-facing documentation carries no test assertions. Adding a scenario means adding a file here.
- **A healthy stack is not a configured one.** The scheduler queues `push-configs` and returns, so `wait.sh` waits for the worker to report that job done before any action runs. `wait_config.py` additionally requires the scheduler's change flags to be clear — `certificates_changed` is in that list because a certificate provider and `deploy-certificates` race in the same batch.
- **Every stack carries bunkerweb, scheduler, API, worker and broker**, whatever the test type. Drop one and the stack still boots, runs zero jobs, and passes any test that never needed one. All-in-one is exempt — its entrypoint enables the worker and forces the API on by itself.
- The job broker is **not** the WAF datastore Redis; 1.7 split those roles and core specs assert on datastore keys.
- `database` actions run their SQL in the API container: the scheduler image lost `sqlite3` when the database clients moved to the API, and both mount the same volume.
- **Do not edit anything under `tests/scripts/` while a run is in flight.** Bash reads a script incrementally by byte offset, so an insert above the current point shifts the rest of the file and the running shell dies on a syntax error that is not in the file. The verdict up to that point is still valid; the final `All tests passed` and the exit code are not.
- Every compose file under `tests/docker/` and `tests/misc/docker/` shares one implicit compose project, so a `down` targets the project, not the file — and the end-of-run cleanup adds `--remove-orphans`. Give a new compose file an explicit top-level `name:` if it must be torn down on its own.
- Some actions address a container by name from the runner (`bunkernet` talks straight to its custom API). CI appends `tests/misc/conf/dnsmasq.hosts` to `/etc/hosts`; read that file before doing the same locally — it maps bare names like `redis` and `valkey` system-wide.

## CI

`.github/workflows/integration-tests.yml` is the reusable entry point, taking `TYPE`, `TEST` (`INTEGRATION;ARCH;RUNS_ON;TEST`) and `RELEASE`. `utils/integrations.yml` maps each integration and architecture to a runner. Swarm rows sit at `TODO`; ARM is disabled on purpose (a matrix would hold an on-demand ARM node for a whole run).
