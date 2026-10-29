# BunkerWeb tests

Two suites live here. They share no tooling.

| Suite | Path | What it is |
| --- | --- | --- |
| Unit | `tests/unit/` | Fast pytest suite over the Python layers, multi-engine. Own venv, own requirements. See [`unit/README.md`](unit/README.md). Nothing below touches it. |
| Integration / API / UI | `tests/` (this level) | YAML specs validated by Pydantic models, executed by Python runners, orchestrated from shell. |

The integration framework came from `bunkerity/bunkerweb-tests` (snapshot `23c77b1`, 2026-07-15)
and reached 1.6 through the 1.7 branch (`tests/` at `541cdc477`), degraded to the 1.6 topology:
bunkerweb, scheduler, autoconf, UI and — for an `api` run only — the standalone API. There is no
worker, no jobs broker, no `push-configs` job and no Swarm arm in 1.6; `scripts/utils.sh` refuses a
checkout that carries `src/worker/`. Product, specs and CI move at one commit.

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
    verify_ssl: false
    string: "Hello World"
```

The example is copied to `/tmp/example-stack` before anything is rewritten, so the
directory you ship stays untouched. The copy gets the images built from this commit and
a scheduler forced onto Let's Encrypt staging with BunkerNet, DNSBL and the anonymous
report off. If the example ships a `setup-<integration>.sh`, the runner executes it from
the copy first, and the matching `cleanup-` script at teardown — several examples fix a
web root's ownership or install a Helm chart there, and skipping that step gets you a
stack that boots and serves nothing.

Which file gets deployed depends on the integration, and so does what it replaces:

| Integration | File | Deployed |
| --- | --- | --- |
| Docker | `docker-compose.yml` | Replaces the framework's stack — the example ships BunkerWeb itself |
| Autoconf | `autoconf.yml` | On top of the framework's stack — the example ships applications and their `bunkerweb.*` labels |
| Kubernetes | `kubernetes.yml` | On top, same idea, through `kubectl apply` |

Linux has no example mode: it installs a package into a systemd container rather than
deploying a compose file.

On Docker the example owns the stack, so anything the runner does to "the stack" has to
be routed to its compose project (`example-stack`) instead of the framework's files —
restarts, teardown, log dumps. Miss one and the symptom lands somewhere else entirely: a
restart against the framework's composes fails with `container name "/bw-scheduler" is
already in use`, and a log dump against them prints empty sections under every heading.
The framework's own `bw-db` network is skipped for the same reason — it claims
10.10.10.0/24, which `examples/proxy-protocol` wants for its `net-proxy`.

Three traps came over with the example scenarios the deleted legacy harness used to run.
That harness casefolded both sides of a string assertion, it used `requests` and followed
redirects, and it never verified TLS; this framework does none of that by default. The
migrated assertions in `core/example-*.yml` therefore carry `ignore_case: true`, `follow_redirects: true` and
`verify_ssl: false`. The last one is not optional on an example stack: the domains only
resolve through the framework's dnsmasq, Let's Encrypt can never issue for them, and
BunkerWeb serves its self-signed fallback. Write new specs without the first two: assert
the case a page actually returns, and let a redirect be a redirect.

A request that carries a body gets `Content-Type: application/x-www-form-urlencoded`
unless the spec sets one. `requests` did that; `httpx` does not, and CRS rules 920340 and
920640 turn a bodied request without the header into a 403 long before it reaches what
the spec is testing. Set `Content-Type: null` to send it bare on purpose.

Nothing rejects a key a model does not declare — pydantic drops it. A misspelt or
invented field means the assertion you thought you wrote never runs.

## Running locally

You can run the whole thing on a workstation. No pipeline, no self-hosted runner.

You need Docker, `redis-cli` (`apt install redis-tools`) and Python 3.13.

```bash
python3 -m venv .venv-tests
.venv-tests/bin/pip install --require-hashes -r tests/requirements.txt

# The shell scripts call bare `python3`, so activate the venv rather than
# calling its interpreter by path — otherwise parse.py runs against the system
# interpreter and dies on `cannot import name 'DockerClient' from 'docker'`.
source .venv-tests/bin/activate

# Build what is missing, then run (<integration> <type> <release> <spec>)
./tests/scripts/test.sh Docker core dev headers
```

Some actions address a container by name from the runner rather than through BunkerWeb —
`bunkernet` talks straight to `http://custom-api:8000`. CI resolves those by appending
`misc/conf/dnsmasq.hosts` to `/etc/hosts`; do the same locally, or that spec fails with a
connection error while everything else passes:

```bash
sudo tee -a /etc/hosts < tests/misc/conf/dnsmasq.hosts
```

Read the file first. It maps bare names — `redis`, `valkey`, `crowdsec`, `php-fpm` — to
10.20.30.x, system-wide, which is fine on a throwaway CI host and less fine on a workstation
that uses those names for something else.

**Do not edit anything under `tests/scripts/` while a run is in flight.** Bash reads a script
incrementally, by byte offset, so an insert above the point it has reached shifts the rest of the
file under it and the running shell dies mid-command on a syntax error that is not in the file
(`run.sh: line 234: syntax error near unexpected token 'fi'` while `bash -n run.sh` is clean).
The spec's own verdict up to that point is still valid; everything after it — the final
`All tests passed`, the exit code — is not.

**Host paths live under one disposable root.** `BW_TESTS_HOST_ROOT` (default
`<checkout>/.cache/e2e-host`) holds everything the harness bind-mounts, writes or cleans on the host:
`var/www/html`, `var/log/bunkerweb`, `var/lib/bunkerweb`, `run/php` and `etc/bunkerweb` — the last
being `BW_TESTS_ETC`, where `generate.py` writes `variables.env`, `api.env` and `ui.env`.
`scripts/utils.sh` derives `BW_TESTS_WWW`, `BW_TESTS_LOG`, `BW_TESTS_LIB`, `BW_TESTS_PHP` and
`BW_TESTS_ETC` from it and exports them; the compose files under `tests/` read those with `:?`, so
a run that skipped `utils.sh` fails instead of mounting the machine's real `/var/lib/bunkerweb`.
The cleanup functions delete databases and truncate logs through those paths and can reach nothing
else. `BW_TESTS_ETC` may be overridden but must stay inside the root. Set `BW_TESTS_HOST_ROOT=/`
only on a throwaway runner that provisions the real paths itself. `/tmp/output` stays shared and
unrooted. Files the containers create under the root are root-owned: delete them with a
container, and keep the root out of any Docker build context (`build.sh` streams only `src/`).

`UI_HOST_PORT` (default `7000`) is the host port the `ui` stacks publish the web UI on. Nothing
in the suite drives it — every spec reaches the UI through BunkerWeb, and `UI_HOST` stays
`http://bw-ui:7000` on the internal network — but any host process already holding 7000 makes
the whole `ui` type fail at boot with `address already in use`. Export `UI_HOST_PORT=7001` (or
anything free) on such a machine.

On the Kubernetes arm the same variable moves the `127.0.0.1:<port>:30070` publish the cluster is
created with, so a machine running an AirPlay receiver (uxplay and friends listen on 7000) can still
create a cluster. It has to be set for the whole run, not just the `ui` type: the port list is
applied once, when `minikube start` creates the node, and port publishes cannot be added to a
running cluster afterwards. `build.sh` checks every host port in that list before starting and names
the process holding any of them, rather than letting docker fail on the first conflict 45 seconds in
and leave a half-created node behind.

**A bare container name will not fail loudly on a workstation — it will hang.** Actions the
runner dials must use a `*.example.com` name (answered from `/etc/hosts`) or a published port on
`127.0.0.1`, never a bare name like `custom-api`. The suite expects dnsmasq to answer those, but the
runner asks the host's own resolver, and any `search` domain in `/etc/resolv.conf` turns the bare
name into an FQDN in someone else's zone. If that zone answers wildcard — as the author's did —
then *no* bare name can ever return NXDOMAIN: `custom-api`, `app1` and
`definitely-not-a-real-host-xyz9` all resolve to a real host, the connection is attempted, and the
action dies on a ten-second timeout that looks like anything except DNS. `ActionData.check_url` now
rejects these at parse time, and the same check covers `tool` arguments and `script` argv. Settings
in `config` are exempt on purpose: those are resolved inside the container network, where dnsmasq is
authoritative and a bare name is correct.

That guard is parse-time rather than a note because the same mechanism had already bitten this suite
once, one layer down. `misc/conf/coredns.conf` carries a block whose comment describes it exactly —
ndots:5 search-path escapes falling through to the host's upstream resolver, "e.g. dedyn.io wildcard
DNS", resolving in-cluster service names to public IPs and stopping nginx from starting. It arrived
with the framework in `71247ab38`, diagnosed and fixed for CoreDNS, while the runner-side path stayed
open and failed months later in `bunkernet` for the same reason. A comment fixing one config file did
not generalise to the next occurrence; a validator that refuses the shape does.

**A running Kubernetes arm and any other arm are mutually exclusive on one workstation.** The
minikube node publishes `127.0.0.1:80` and `127.0.0.1:443`, fixed at node creation, and Docker,
Linux, Autoconf and All-in-one all want the same two ports. Starting one of those while the cluster
is up fails 45 seconds in with `Bind for 127.0.0.1:80 failed: port is already allocated`, and the
aborted start then runs a full clean that takes the framework's state Redis with it — so the last
line on screen is `Could not connect to Redis at 127.0.0.1:6390`, which points nowhere near the
cause. There is nothing to configure around this: two arms that both want the standard HTTP port
cannot share it. Run `minikube stop` first — it frees both ports and keeps the node, so coming back
is one `minikube start` rather than the full re-create `minikube delete` would cost.

Outside CI (`IN_CICD` unset), `build.sh` builds any missing `bunkerity/<image>:tests` from
the Dockerfiles in this checkout. It reuses an image that already exists, so the second run
starts in seconds. Delete an image when you want it rebuilt. The framework starts its own
state Redis from `misc/docker/redis.yml`, on **127.0.0.1:6390** rather than the default 6379:
the Linux integration runs `network_mode: host`, so a Redis the product starts on 6379 would
collide with it. `TESTS_REDIS_PORT` overrides it; the scripts go through the
`redis_cli` wrapper in `scripts/utils.sh` and the Python entry points read the same variable.

Running specs back to back locally is where CI and a workstation diverge. CI gives every spec
a fresh runner; here they share one Docker daemon, and the SQLite database lives in the
`bw-storage` volume, which `start.sh` creates outside any compose project — so `down -v`
never touches it. `cleanup_stack` removes it on a full clean for that reason. If you drive the
scripts by hand rather than through `test.sh`, remove it yourself between specs
(`docker volume rm -f bw-storage`), or the next stack boots on the previous spec's global
settings: a run that set `REDIS_HOST=valkey` leaves the following API answering 500 to every
`/ping` while it waits on a container that is gone.

Once a stack is up, you can drive narrower loops:

```bash
.venv-tests/bin/python tests/parse.py core --integration Docker   # what would run
.venv-tests/bin/python tests/generate.py Docker core "headers;check_headers" --dev
.venv-tests/bin/python tests/core.py "headers;check_headers" Docker
HEADLESS=1 .venv-tests/bin/python tests/ui.py "panel;login" Docker
```

`parse.py` emits one matrix entry per spec file; run `python3 tests/parse.py core --integration Docker`
for the current count rather than trusting a number written here.

An `xpath` or `ui` action drives Firefox through Selenium, and `core_handlers/selenium_common.py`
looks for the driver at `./geckodriver` or `/usr/local/bin/geckodriver` — nowhere else. CI installs
Firefox and geckodriver explicitly; a workstation whose only Firefox is the snap fails with
`NoSuchDriverException`, so symlink your driver into the repo root (it is gitignored, as is the
`geckodriver.log` the framework writes there on every browser action).

**`restart_stack: false` on an action does not exempt that action from a fresh config** — the
field controls whether the *next* action's config gets applied before its own assertion runs,
not the current one (see `action.py`'s docstring). Copy it onto every action in a spec (as
`customcert.yml`/`bans.yml` do, where it is safe because those specs never change a setting
mid-file) and only the very first action's config ever takes effect: a later assertion expecting
a changed setting gets the *previous* value, because the new setting was written to
`variables.env` but the scheduler was never told to reload before the request fired. Leave it at
the default `true` unless an action's own config specifically must wait for a later one.

**An nginx variable inside a `config:` value needs its `$` doubled.** A setting like
`LOG_FORMAT: "CITYPROBE=[$bw_city]END"` lands in `variables.env`, which reaches the scheduler
container through Compose's `env_file:` — and Compose interpolates `$VAR` in an env file exactly
like it does in the compose YAML itself. A single `$bw_city` is silently swallowed (no such
Compose-level variable exists), so nginx's own `log_format` directive never sees the variable
reference at all. `docker compose` does warn (`The "bw_city" variable is not set. Defaulting to
a blank string.`) during the push, but nothing surfaces that warning into the test's own
pass/fail output, so the symptom just looks like the plugin never populated the variable.
Compose's own escape (`$$` → literal `$`) is what survives the trip: write
`"CITYPROBE=[$$bw_city]END"` for any setting value that must reach nginx carrying a literal `$`.

## Stack shape

The 1.6 scheduler pushes the configuration itself and runs its own jobs, so a stack is bunkerweb
plus scheduler (plus autoconf on Autoconf and Kubernetes, the UI on a `ui` run and the standalone
API on an `api` run). There is no worker, no jobs broker and no `push-configs` job; `wait.sh` waits
on container health, and the scheduler only reports healthy once it has applied the configuration.
`stack_has_worker()` in `scripts/utils.sh` answers from the presence of `src/worker/`, never from a
version string (CI stamps `src/VERSION` with `dev` or `testing`), and the harness refuses to run
when it says yes.

`API_TOKEN` is still set on every stack: the instance API (`API_TOKEN` is a core setting) requires
it from the scheduler and from `core/api.yml`, and an `api` run's standalone API accepts it as its
admin bearer.

`database` actions run their SQL in the scheduler container, whose image ships `sqlite3`,
`mariadb` and `psql`, and which mounts the same `bw-storage` volume as the API. On All-in-one the
one container serves both.

Every compose file under `tests/docker/` and `tests/misc/docker/` runs in the same implicit
compose project (`docker`, from the directory name), so `docker compose -f <one>.yml down` targets
the project rather than that file — and the end-of-run cleanup adds `--remove-orphans`, which
takes down everything else in it, including the framework's own state Redis on 127.0.0.1:6390.
That is where the `Could not connect to Redis` lines at the end of a run come from. Give a new
compose file an explicit top-level `name:` if you need it to be torn down on its own.

The Redis and Valkey containers are started once and reused: `start.sh` runs `docker compose up`
only when no such container exists, so an action that changes `/tmp/valkey.env` (a password, a
user, TLS) reaches a server still running the previous action's configuration unless the action
before it asked for a `full_clean`. `generate.py` also empties `/tmp/valkey-acl` on every action
and writes the ACL file only for an action that declares a `user:`, so the entrypoint passes
`--aclfile` only when the file is actually there — without that guard, the first action to
recreate the container without a user aborts valkey at startup and nothing listens on either
port.

A `redis` action with `cluster: true` runs against a three-master Redis Cluster
(`misc/docker/redis-cluster.yml`, no replicas). The nodes sit on `bw-universe` at fixed addresses
(`10.20.30.81-83`, named `redis-cluster-1..3` in `dnsmasq.hosts`) and announce those addresses, which
is what `CLUSTER SLOTS` returns to BunkerWeb. `redis-cluster-init` forms the cluster and exits;
`start.sh` waits for `cluster_state:ok`. The runner reaches the nodes through the published ports
`127.0.0.1:7001-7003` (`cluster_port` is the first), remapped from the announced addresses, runs the
query on every primary, and `cluster_owner: N` asserts that node N holds every key of `keys`. A cluster
needs `REDIS_DATABASE: "0"`. The stack exists on the Docker-network arms only (Docker, Autoconf,
All-in-one); Linux and Kubernetes have no cluster manifest.

On an `api` run `bw-api` publishes `127.0.0.1:8888`, which the `api/*.yml` specs address directly. Anything
else that wants a host port has to avoid it — CrowdSec used to take 8888 and now publishes 8889
(`misc/docker/crowdsec.yml`, with the Linux `CROWDSEC_API` override following it), because docker
refuses to start the container with "port is already allocated". CrowdSec also downloads its whole
hub before reporting healthy, so `generate.py` raises the health timeout to 300s for any spec that
carries `crowdsec_config`.

## The ui specs and the settings panes

A service or the global configuration has two panes since the settings monolith was split:
**compose** (a shelf of plugin on/off toggles) and **raw** (an ACE editor holding the whole
`KEY=value` document). The easy and advanced panes are gone, and per-plugin editing moved to
`/services/<service>/plugins/<plugin>` and `/global-settings/plugins/<plugin>`.

`ui_handlers/services.py` drives **raw** for every value round-trip: it posts the same keys
through the same route as compose, and a text document is a steadier target than one widget per
setting. Two consequences worth knowing before writing a `ui` spec:

- The compose shelf and the per-plugin pages have **no coverage**. Settings are verified end to
  end, the compose UI itself is not.
- The pane is selected by URL (`?mode=raw`), not by clicking a tab. On `/services` and
  `/global-settings` those pills are links on purpose — both panes re-render from the database on
  navigation, so an unsaved twin cannot exist.
- A multiline value (a PEM block in a `file` setting) cannot go through raw here: the handler
  parses one key per line and would rewrite such a value as its first line alone.

Three more traps a `ui` spec hits sooner or later, all handled in `utils/ui.py` and `ui.py`:

- **The window is sized explicitly (1920x1080), never maximized.** Headless Firefox maximizes to
  the virtual screen (1366x768), which undoes the `--width/--height` given to the binary. At that
  width DataTables Responsive folds the right-hand columns into child rows, so every row-action
  button is in the DOM but `display: none` and no click can reach it. `assert_button_click`
  expands the collapsed parent row (`td.dtr-control`) before retrying, so a narrow viewport is
  recoverable rather than fatal.
- **`assert_button_click` re-resolves its selector on every attempt for 10 seconds.** These pages
  redraw themselves (Responsive recomputes on resize and on tab switch), so a node found once is
  regularly detached or momentarily unclickable by the time the click lands. It ends the run when
  the budget expires; the one call site that wants the exception instead — the wizard's optional
  confirm-DNS step — passes `error=True`.
- **`data-i18n` lives on a button's inner `<span>`, never on the `<button>`** (see
  `components/button.html`), and a DataTables colvis entry renders as `"4. <span>Method</span>"`.
  Match the span, not the button's own attributes or its whole text.
- **A toolbar collection entry is the `<a class="dropdown-item">` inside `<li class="dt-button">`**,
  and `contains(@class, "dt-button")` also matches the toolbar's own `div.dt-buttons` — which sits
  earlier in the document, so a loose selector clicks *that*, the click does nothing, and the step
  still reports success. Anchor these on
  `//div[contains(@class, "dt-button-collection")]//a[contains(@class, "dropdown-item")]`.
- **`type: find` proves an element is in the DOM, never that it can be clicked.** The onboarding
  drawer — `offcanvas-end`, 400 px of fixed overlay with no backdrop — used to auto-open on the
  first page a session rendered and sat on that page's toolbar. Every `find` in every ui spec
  stayed green throughout, because the buttons were findable the whole time; only the click reds,
  and only on the page that happens to click. The assertion that catches it is `by: js`: the
  expression returns the node only when `document.elementFromPoint` at its centre resolves back
  to it, and `find` ends the run when the expression returns null. `first_run_cta_receives_click`
  in `ui/instances.yml`, `ui/services.yml` and `ui/configs.yml` is that guard, and it checks
  `#onboarding-button` first so it cannot pass vacuously on a session where the walkthrough is
  not rendered at all. A visibility or `is_displayed()` check is **not** a substitute — both were
  green during the defect.

## Integrations

Docker, Linux, Autoconf, Kubernetes, All-in-one. `utils/integrations.yml` maps each
integration and architecture to a runner. The values are JSON and feed `runs-on` directly.

- **Swarm**: not part of 1.6. A spec that names it is skipped with a warning by `parse.py`.
- **ARM**: disabled. The builds provision an ARM node on demand (`create-arm.yml`, buildx
  over SSH, then `rm-arm.yml`). A test matrix would hold that node for a whole run instead
  of one build, so we priced it out rather than enabling it by default.

## CI

`.github/workflows/integration-tests.yml` is the reusable entry point. It takes `TYPE`,
`TEST` (`INTEGRATION;ARCH;RUNS_ON;TEST`) and `RELEASE`. `dev.yml`, `ui.yml`
and `staging.yml` each parse the specs, then fan out one job per integration.
`container-build.yml` publishes the images under their `-tests` names and the workflow
retags them to what the stacks reference.

`tests/parse.py "core"|"api"|"ui"` is invoked from `dev.yml` (`core`), `ui.yml` (`ui`) and
`staging.yml` (`core` and `api`). The dev pipelines pass `--dev` and read `utils/integrations.yml`'s
`dev:` block: `ubuntu/noble` alone on Linux, every other integration a single `ubuntu-latest` row.
`staging.yml` does not pass `--dev` and reads the `staging:` block, which carries the live Linux
distro rows (`el/8`, `el/9`, `el/10`, `fedora/43`, `fedora/44`, `ubuntu/resolute`, `ubuntu/noble`,
`ubuntu/jammy`, `debian/bookworm`, `debian/trixie`; aarch64/arm64 stay `TODO`). GitHub caps a job's
matrix at 256 entries, so `staging.yml` narrows the parsed Linux list before fanning out; see the
comment in its `parse-tests-core` job.

`utils/packages.yml` maps each Linux row to the `linux-build.yml` leg that built its package
(`package-<name>-<arch>`): dev's `ubuntu` leg is Ubuntu 26.04 (`ubuntu/resolute`, `FROM ubuntu:resolute`),
noble is the separate `ubuntu-noble` leg.

## The legacy harness (deleted)

`tests/main.py`, the `*Test.py` classes, `tests/create.sh`, `tests/rm.sh`, `tests/ansible/`,
`tests/terraform/`, the per-feature stacks under `tests/core/<name>/`, the old `tests/ui/*_page.py`
Selenium classes, the `examples/*/tests.json` descriptors and the workflows that ran them
(`test-core*.yml`, `tests-ui*.yml`, `staging-tests.yml`, `staging-create-infra.yml`,
`staging-delete-infra.yml`) are replaced by the specs and runners above. Each `examples/<name>/` has
a `core/example-<name>.yml` spec instead of a descriptor. `git log` keeps the old harness.

The old harness tested released artifacts on self-hosted runners against real domains with real
Let's Encrypt certificates. This framework's domains are the fixed `*.example.com` names in
`tests/misc/conf/dnsmasq.hosts`, resolved by a local dnsmasq container to `127.0.0.1` or a fixed
overlay IP; no code path takes a runtime-supplied domain, so that coverage is not recovered here.

`core/internalcert/` stayed. It is not a stack: it runs one container with its own volume and
checks a property of the container lifecycle rather than of a configured deployment — the
internal certificates are generated on first boot, served by the listener that owns them, and
survive a restart byte for byte. `core/internalcert.yml` schedules it as a `script` action.

One thing went with the deleted directories and had no replacement: `bwcli ban`, `unban` and
`bans`. The `bwcli` action type was used only for `plugin backup save/list/restore`, and the
`/bans` API specs exercise the HTTP path rather than the CLI — which is not the same path,
since `bans` reads the database first and treats it as the source of truth. `core/bwcli.yml`
covers it now: a global ban and a service-scoped one, each listed back, then both lifted.

Asserting the unban's own success message was not enough: the message is printed by the
command, not derived from the ban store, so it would pass against a `bwcli` that reported
success and removed nothing. The `bwcli` action now takes `not_result` beside `result` —
either one, enforced by the model — and the spec lists the bans back after lifting them and
requires each address to be absent. That is the check that fails if the unban is a no-op.
