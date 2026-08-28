# AGENTS.md

Agent guide for the BunkerWeb shared library layer in `src/common/`. This is the canonical guide for this directory; `CLAUDE.md` here is a pointer to it.

## Read First

- Root: [../../AGENTS.md](../../AGENTS.md) (short) and [../../CLAUDE.md](../../CLAUDE.md) (architecture)
- Database layer: [db/AGENTS.md](db/AGENTS.md)
- Plugin contract: [core/AGENTS.md](core/AGENTS.md)
- Plugin reference (user-facing): [../../docs/plugins.md](../../docs/plugins.md)

## What This Is

The shared library used by the Scheduler, API, UI, Autoconf, CLI and Worker. It owns the database, configuration generation, the plugin system and the shared utilities. **No component runs independently of this code — treat every change as cross-component.**

## Critical Rules

- Settings flow through `settings.json` and the plugin `plugin.json` schemas → `Configurator` → database → `Templator`. Do not bypass a stage.
- Every schema change must work on SQLite, MariaDB, MySQL and PostgreSQL, and migrations need a revision in each engine directory. See [db/AGENTS.md](db/AGENTS.md).
- Lua and Python are decoupled: Lua reads NGINX shared-dict state that the Scheduler synchronizes, and never calls Python.
- **Job names are global across all plugins.** There is no namespace isolation; a collision silently changes queue routing and cache paths.
- Preserve the plugin metadata shape and the `order.json` execution ordering.

## Layout

- `db/` — models, `Database` coordinator, `db_methods/` mixins, Alembic. Its own guide: [db/AGENTS.md](db/AGENTS.md).
- `core/` — the core plugins. Its own guide: [core/AGENTS.md](core/AGENTS.md).
- `gen/` — settings validation and NGINX rendering.
- `confs/` — the Jinja2 templates rendered into NGINX configuration.
- `utils/` — shared helpers.
- `api/` — the HTTP client for inter-component calls.
- `cli/` and `helpers/` — data setup, healthchecks, and the `bwcli` wrapper.
- `settings.json` — the global settings schema.

## Data Flow

```
settings.json + plugin.json schemas
        -> Configurator   (validates against type + regex)
        -> Database       (persists validated settings)
        -> Templator      (renders Jinja2 -> NGINX configs, ProcessPoolExecutor)
        -> NGINX reload
```

## Configuration Generation (`gen/`)

- **`Configurator.py`** loads `settings.json` and every `plugin.json` at startup and pre-compiles all validation regexes for O(1) membership testing. It carries an exclusion set for system environment variables (Docker, Kubernetes, Python internals). `IGNORE_REGEX_CHECK=yes` disables validation — development only.
- **`Templator.py`** renders the templates in `confs/` with a `ProcessPoolExecutor`. `ConfigurableCustomUndefined` falls back to config-dict values for undefined template variables. SSL helpers: `_supports_tls_group()` tests cipher support with result caching, `_best_ssl_ecdh_curve()` picks the ECDH curve.
- `main.py` and `save_config.py` are the subprocess entry points the Scheduler shells out to.

**Validation is not one-shot.** The Configurator validates at generation time and the Database validates again at runtime (`is_valid_setting`) against its own compiled regex caches. Both matter.

## Settings Schema (`settings.json`)

Global settings live here; per-plugin settings live in each `plugin.json`. Entry shape:

```json
{
  "SETTING_ID": {
    "context": "global|multisite",
    "default": "value",
    "help": "description",
    "id": "kebab-case-id",
    "label": "Display label",
    "regex": "^validation_regex$",
    "type": "password|text|number|file|check|select|multiselect|multivalue",
    "multiple": "group-name",
    "separator": " ",
    "select": ["opt1", "opt2"]
  }
}
```

`multiple` enables the numbered families (`SETTING_1`, `SETTING_2`, …), validated per value. `settings.json` is read once at startup: a runtime change means a database update plus a reload signal.

## Utilities (`utils/`)

- **`jobs.py`** — the `Job` class managing the cache at `/var/cache/bunkerweb/<plugin_id>/`. `_write_atomic()` prevents partial files; tar.gz extraction is thread-safe under a lock; `restore_cache()` rebuilds from the database; `EXPIRE_TIME` drives cleanup scheduling. Also `defer_change_acknowledgement()`, the worker-side half of the deferred-ack chain.
- **`ApiCaller.py`** — `send_to_apis()` fans out to multiple endpoints through a `ThreadPoolExecutor`; `send_files()` uploads tar.gz. Used by the CLI, Scheduler and Autoconf.
- **`base_api_client.py`** — the base class the UI and Autoconf API clients both extend.
- **`common_utils.py`** — `handle_docker_secrets()` (reads `/run/secrets` when present), `effective_cpu_count()` (respects cgroup limits), `bytes_hash()`/`file_hash()` (SHA512), plugin tar compression level.
- **`logger.py`** — `BWLogger` over stderr, file and syslog (UDP/TCP), configured by `LOG_LEVEL`, `LOG_FILE_PATH`, `LOG_SYSLOG_ADDRESS`, `LOG_SYSLOG_TAG`, with SQLAlchemy-specific level control.
- **`job_queues.py`** — `HEAVY_JOBS` and `queue_for()`: the single source of truth for Celery queue routing, imported by both the API dispatch side and the worker.
- **`location_claims.py`** — the render-time half of the per-service location namespace guard; its mutation-time mirror is `db/db_methods/locations.py`. Both compare _rendered_ locations, and normalizing only one produces a false refusal.

## API Client (`api/`)

`API.py` is a thin HTTP client for inter-component communication: `API(endpoint, host=None, token=None)`, bearer-token auth, HTTPS→HTTP fallback only for unpinned legacy connections (pinned TLS never downgrades), and `from_instance(dict)` to build one from a database instance record.

## CLI (`cli/`)

`CLI.py` inherits from `ApiCaller` and provides `ban`, `unban`, `bans`, `plugin_list` and the per-plugin `custom` commands. It reaches the database and Redis directly for cache operations. Entry point: `cli/main.py`, wrapped by `helpers/bwcli`, installed to `/usr/bin/bwcli` by the Linux packaging.

## Runtime Gotchas

- **`_db_session` is not reentrant.** It yields the shared scoped session and its `finally` calls `session.remove()`, so a nested `with self._db_session()` closes the session the outer block holds: everything it loaded becomes detached (the next lazy load raises `DetachedInstanceError`) and anything pending is discarded. Never call another session-opening method from inside a session — resolve the value first and pass it in, or pass `session=` where the callee accepts one. This bit `renew_self_signed_certificate`, which resolved the encryption keyring inside its own session; on a stock install (no `CERTIFICATE_ENCRYPTION_*` env) that read opens a session, `deploy-certificates` died on every run, and `certificates_changed` stayed set forever. The unit tests missed it because they all configure the env keyring; `tests/unit/db/test_certificates.py::test_renew_works_without_an_environment_keyring` covers the fallback now.
- Custom config types include `default_server_http` but **no** `default_server_stream`.
- Template rendering and API fan-out use process and thread pools — keep callables pickleable where a process pool is involved.
- Connection pooling is `QueuePool` on every engine; SQLite runs in WAL mode.

## Commands

```bash
pre-commit run --all-files
./tests/scripts/test.sh docker core dev <category>   # see tests/AGENTS.md
```
