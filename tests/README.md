# BunkerWeb tests

Two suites live here. They share no tooling.

| Suite | Path | What it is |
| --- | --- | --- |
| Unit | `tests/unit/` | Fast pytest suite over the Python layers, multi-engine. Own venv, own requirements. See [`unit/README.md`](unit/README.md). Nothing below touches it. |
| Integration / API / UI | `tests/` (this level) | YAML specs validated by Pydantic models, executed by Python runners, orchestrated from shell. |

The integration framework came from `bunkerity/bunkerweb-tests`, snapshot **`23c77b1`**
(2026-07-15) plus its uncommitted working tree. Product, specs and CI now move at one
commit. The old repository keeps its history; we imported a snapshot, not a rebase.

## Writing a test

One YAML file per subject: `core/*.yml`, `api/*.yml`, `ui/*.yml`. Each file declares
actions. Each action carries a type, and that type picks both the Pydantic model that
validates it and the handler that runs it.

```yaml
# tests/core/headers.yml
actions:
  check_headers:
    type: header
    url: "http://www.example.com"
    method: "HEAD"
    response_headers:
      Server: null # null asserts the header is absent
```

Per-integration overrides live inside the action (`Docker:`, `Linux:`, …). A `null` value
deletes the inherited key instead of overriding it. Set `integrations: "all"` or list the
ones you want.

Core actions accept these types: `string`, `status`, `header`, `url`, `database`, `bwcli`,
`redis`, `tool`, `ssl`, `xpath`, `cookie`. UI steps: `setup`, `login`, `access`, `click`,
`send_keys`, `find`, `refresh`, plus the service, instance and global-config CRUD steps.

Adding a core action type takes four edits: a model in `models/`, a handler in
`core_handlers/`, an export in `core_handlers/__init__.py`, a dispatch branch in `core.py`.
A UI step takes three: model in `models/ui/`, handler in `ui_handlers/`, dispatch in
`ui.py`.

### Testing an example

A spec can put an `examples/` stack under test instead of one the framework composes.
Add `example: <name>` at the top of a core spec and the runner deploys
`examples/<name>/docker-compose.yml` as a user would, then asserts against it:

```yaml
example: php-singlesite

integrations:
  - "Docker"

actions:
  serves_the_php_app:
    type: string
    url: "https://www.example.com"
    string: "Hello World"
    tls: "www.example.com"
```

The example is copied to `/tmp/example-stack` before anything is rewritten, so the
directory you ship stays untouched. The copy gets the images built from this commit and
a scheduler forced onto Let's Encrypt staging with BunkerNet, DNSBL and the anonymous
report off.

Two traps when you move a scenario over from `tests/examples/<name>.json`. The legacy
harness casefolds both sides of a string assertion, and it used `requests`, which follows
redirects; this framework does neither by default. Migrated assertions therefore carry
`ignore_case: true` and `follow_redirects: true`. Write new specs without them: assert the
case a page actually returns, and let a redirect be a redirect.

## Running locally

You can run the whole thing on a workstation. No pipeline, no self-hosted runner.

You need Docker, `redis-cli` (`apt install redis-tools`) and Python 3.13.

```bash
python3 -m venv .venv-tests
.venv-tests/bin/pip install --require-hashes -r tests/requirements.txt

# Keep generated env files away from a real installation (see below)
export BW_TESTS_ETC=/tmp/bunkerweb-tests/etc

# Build what is missing, then run
./tests/scripts/test.sh docker core dev headers
```

`BW_TESTS_ETC` roots the generated `variables.env`, `api.env`, `worker.env` and `ui.env`.
It defaults to `/etc/bunkerweb`, which suits a throwaway CI host. On a machine that has
BunkerWeb installed, that default overwrites your real config, so export the variable
before you run. The compose fragments read the same variable and follow.

Outside CI (`IN_CICD` unset), `build.sh` builds any missing `bunkerity/<image>:tests` from
the Dockerfiles in this checkout. It reuses an image that already exists, so the second run
starts in seconds. Delete an image when you want it rebuilt. The framework starts its own
state Redis from `misc/docker/redis.yml`.

Once a stack is up, you can drive narrower loops:

```bash
.venv-tests/bin/python tests/parse.py core --integration Docker   # what would run
.venv-tests/bin/python tests/generate.py Docker core "headers;check_headers" --dev
.venv-tests/bin/python tests/core.py "headers;check_headers" Docker
HEADLESS=1 .venv-tests/bin/python tests/ui.py "panel;login" Docker
```

`parse.py` emits one matrix entry per spec file. For Docker that is **37 core, 9 api and 7
ui** entries. The migration conception recorded 37/8/7; api gained `instances-validation`,
which arrived with the source working tree.

## Stack shape since 1.7

The scheduler stopped running jobs. It posts them to the API, the API queues them on a
Valkey broker, and `bw-worker` executes them. Every stack therefore carries bunkerweb,
scheduler, API, worker and broker, whatever the test type. Drop one of them and the stack
still boots, runs zero jobs, and passes any test that never needed one.

The job broker stays separate from the WAF datastore Redis. 1.7 split those two roles, and
core specs assert on datastore keys.

All-in-one is exempt: its entrypoint enables the worker and forces the API on by itself.

## Integrations

Docker, Linux, Autoconf, Kubernetes, All-in-one. `utils/integrations.yml` maps each
integration and architecture to a runner. The values are JSON and feed `runs-on` directly.

- **Swarm**: not ported yet. Its rows sit at `TODO`, and `tests/main.py` with `SwarmTest.py`
  stay in the tree until someone ports it.
- **ARM**: disabled. The builds provision an ARM node on demand (`create-arm.yml`, buildx
  over SSH, then `rm-arm.yml`). A test matrix would hold that node for a whole run instead
  of one build, so we priced it out rather than enabling it by default.

## CI

`.github/workflows/integration-tests.yml` is the reusable entry point. It takes `TYPE`,
`TEST` (`INTEGRATION;ARCH;RUNS_ON;TEST`) and `RELEASE`. `1.7-dev.yml` parses the specs,
then fans out one job per integration. `container-build.yml` publishes the images under
their `-tests` names and the workflow retags them to what the stacks reference.

## The legacy harness

`tests/main.py` and the `*Test.py` classes predate the migration. They still run the
example scenarios, and they pin their own dependencies in `legacy-requirements.{in,txt}`;
`tests/requirements.txt` belongs to the framework.

Scenario descriptors sit in `tests/examples/<name>.json`, one per `examples/<name>/`
directory, and the `name` field points back at the directory to deploy. They used to live
inside the example folder, which put test assertions in documentation that users copy.
Adding a scenario means adding a file here, not editing the example.

The harness goes away once those scenarios run on the framework. That needs an example
mode (deploy the example's own compose rather than a generated stack) and it needs the
example stacks to work on 1.7 first: 24 of the 25 ship no `bw-api` and no `bw-worker`, so
they run zero jobs, and 19 of those ask for `AUTO_LETS_ENCRYPT` certificates that can never
be issued.
