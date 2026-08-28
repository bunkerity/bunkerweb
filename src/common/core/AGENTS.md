# AGENTS.md

Agent guide for the BunkerWeb core plugins in `src/common/core/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Shared layer: [../AGENTS.md](../AGENTS.md)
- Root: [../../../AGENTS.md](../../../AGENTS.md) (short) and [../../../CLAUDE.md](../../../CLAUDE.md) (architecture)
- User-facing plugin reference: [../../../docs/plugins.md](../../../docs/plugins.md)

## The Plugin Contract

One directory per plugin, `ls` for the current set. External and PRO plugins use the same shape from `/etc/bunkerweb/plugins` and `/etc/bunkerweb/pro/plugins`.

| Path                            | Role                                                                                |
| ------------------------------- | ----------------------------------------------------------------------------------- |
| `plugin.json`                   | Metadata and settings schema. Required                                              |
| `<name>.lua`                    | Request-time processing (`require "bunkerweb.plugin"`, `require "bunkerweb.utils"`) |
| `confs/`                        | Jinja2 NGINX fragments merged into the rendered config                              |
| `jobs/`                         | Python background tasks, executed by the Worker                                     |
| `ui/`                           | Optional UI contribution: `actions.py`, blueprints, templates                       |
| `api/router.py`                 | Optional FastAPI router (see Extensions)                                            |
| `db/models.py`, `db/methods.py` | Optional tables and query mixin (see Extensions)                                    |
| `bwcli/`                        | Optional `bwcli` subcommands                                                        |
| `README.md`                     | **Also the published documentation** — see the docs trap below                      |

`order.json` at this level defines the execution order per phase: `init`, `init_worker`, `set`, `ssl_client_hello_default`, `ssl_certificate`, `access`, `headers`, `log`, `preread`, `log_stream`, `log_default`, `timer`, `init_workers`.

## `plugin.json`

Top level: `id`, `name`, `description`, `version`, `stream`, `settings`, optional `jobs`, optional `extensions`.

`stream` is `yes`, `no` or `partial` and decides whether the plugin runs in TCP/UDP stream mode.

Each setting carries `context` (`global` or `multisite`), `default`, `help`, `id` (kebab-case), `label`, `regex`, `type` (`password|text|number|file|check|select|multiselect|multivalue`), and optionally `multiple` (the group name enabling `SETTING_1`, `SETTING_2`, … with the regex applied per value), `separator` and `select`.

A job entry carries `name`, `file`, `every` (`once|minute|hour|day|week`), `reload` and `async`.

## Jobs

Jobs are dispatched by the Scheduler and executed by the Worker (`src/worker/`). Two rules matter more than the rest:

- **The exit code is a protocol.** `sys.exit(1)` means "something changed" — it ships the job cache to the instances and requests a debounced reload. `sys.exit(0)` means success with no change. Anything else is a failure. A plain `return 1` from the module does nothing: return values are discarded and reported as `0`.
- **Job names are globally unique across every plugin.** There is no namespacing. A name collision silently changes queue routing (heavy vs default) and shares the cache path.

Write to the cache atomically (`Job._write_atomic` in `src/common/utils/jobs.py`) and commit the "already done" marker **last** — that is what makes a job safe to re-run, and delivery is at-least-once. Cache lives at `/var/cache/bunkerweb/<plugin_id>/`.

## Extensions (API and DB)

A plugin can extend the control plane by declaring `extensions` in `plugin.json`:

```json
"extensions": {
  "api": { "module": "api/router.py", "prefix": "/<id>" },
  "db":  { "models": "db/models.py", "methods": "db/methods.py", "table_prefix": "bw_<id>_" }
}
```

`api/router.py` must expose `router = APIRouter(...)`; `db/models.py` declares tables named with the plugin's `table_prefix`; `db/methods.py` may expose a `Database<Plugin>Mixin`.

`src/common/utils/plugin_extensions.py` is the single discovery point, used by the API (router mount and model registration), the Scheduler (model registration before `create_all`) and the Worker (model registration for job queries). The API mounts the router at `/<plugin_id>` with the auth guard and rate limiter injected at mount time — a plugin author cannot forget authentication — and refuses a prefix that collides with an existing router. One broken plugin is logged and skipped; it never takes the process down.

**Trust model**: `core` and `pro` plugins are first-party and enabled by default. `external` plugins ship third-party Python that would run inside the API process and define tables in the central database — a real RCE and schema-poisoning surface — so their api/db extensions are disabled unless `PLUGIN_API_EXTENSIONS_ALLOW_EXTERNAL=yes`, and even then are checksum-verified against the DB plugin record. The discovery roots are hardcoded, not env-overridable, on purpose.

## Docs Trap

`docs/json2md.py` builds the published `features.md` from the plugin metadata, but **a plugin's `README.md` wins over its `plugin.json` settings table**. A setting added without touching the README is invisible in the documentation, and a plugin with `settings: {}` is skipped entirely. `json2md.py` runs in no CI job and no pre-commit hook, so nothing catches it. See [../../../docs/AGENTS.md](../../../docs/AGENTS.md).

## Lua Side

Plugin Lua code runs inside the pipeline documented in [../../../src/bw/AGENTS.md](../../../src/bw/AGENTS.md). The rules that bite most often: read request metadata from `self.ctx.bw` rather than re-resolving it, keep `self.variables` for configuration settings, prefix any per-request state you stash in `ctx.bw` with your plugin id, and remember that cosockets (Redis, DNS) do not exist in the init, init_worker and log phases.

Lua never calls Python. It reads NGINX shared-dict state that the Scheduler synchronizes.
