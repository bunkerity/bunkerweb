# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See also the [root CLAUDE.md](../../CLAUDE.md) for project-wide architecture, build commands, and conventions.

## What This Directory Is

`src/common/` is BunkerWeb's shared library layer — used by the Scheduler, API, UI, Autoconf, and CLI. It owns the database, configuration generation, plugin system, and shared utilities. No component runs independently of this code.

## Architecture

### Data Flow

```
settings.json + plugin.json schemas
        ↓
  Configurator (validates settings against regex/type)
        ↓
  Database (persists validated settings)
        ↓
  Templator (renders Jinja2 → NGINX configs via ProcessPoolExecutor)
        ↓
  NGINX reload
```

### Database Layer (`db/`)

**`Database.py` (~520 lines)** is a thin coordinator: it composes the domain mixins in `db_methods/` (`config_read`, `config_save`, `plugins`, `plugins_update`, `jobs`, `services`, `instances`, `templates`, `ui_users`, `metadata`, `initialization`, `custom_configs`) and owns connection pooling and session management. The query implementations described below now live in those mixins — the 5,974-line monolith was split in commit `f97db1261`, modernizing to SQLAlchemy 2.0. Key patterns:

- **Transient error resilience**: The `@retry_on_transient_db_errors` decorator wraps most DB methods with configurable retry count/delay (`DATABASE_REQUEST_RETRY_*` env vars). Readonly fallback mode exists for degraded reads.
- **Settings validation is in Database, not just Configurator**: `is_valid_setting(setting, value)` validates against pre-compiled regex caches at runtime.
- **Multisite prefixing**: Settings with `context=multisite` are stored/queried with server name prefix (`www.example.com_SETTING_ID`). Global settings have no prefix. The Database class handles dual lookup (service-specific → global fallback).
- **Suffix settings**: Settings marked with `"multiple": "group-name"` in `plugin.json` support `SETTING_1`, `SETTING_2`, etc. Regex validation applies per-value.
- **File-backed settings**: When a setting's value is a file, `Global_values` / `Services_settings` store the filename separately from the value for atomic updates.
- **Custom configs storage**: Custom NGINX blocks are stored as `LargeBinary` (up to 4GB) with checksum tracking. Types (per `CUSTOM_CONFIGS_TYPES_ENUM` in `model.py`): `http`, `stream`, `server_http`, `server_stream`, `default_server_http`, `modsec`, `modsec_crs`, `crs_plugins_before`, `crs_plugins_after` — note there is a `default_server_http` but no `default_server_stream`. Custom configs have an `is_draft` flag for multi-step UI workflows.

**`model.py`** defines 29 SQLAlchemy ORM classes (plus the `JSONText` TypeDecorator). Key tables:

- `Plugins`, `Settings` — plugin registry and settings schema
- `Global_values`, `Services_settings` — actual config values (with optional file names)
- `Services` — multisite service definitions
- `Jobs`, `Jobs_cache`, `Jobs_runs` — scheduled task tracking and cache storage
- `Custom_configs` — per-service or global NGINX config blocks
- `Instances` — BunkerWeb instance registry
- `Templates`, `Template_steps`, `Template_settings`, `Template_custom_configs` — UI wizard templates
- `Selects`, `Multiselects` — setting option enums
- `Bw_cli_commands` — CLI command registry
- `Plugin_pages` — plugin UI page definitions
- `Metadata` — key-value metadata store for change signaling
- `Users`, `Roles`, `Permissions`, `RolesUsers`, `RolesPermissions` — RBAC for UI
- `API_users`, `API_permissions` — fine-grained API access control
- `UserSessions`, `UserRecoveryCodes` — 2FA support
- `JSONText` TypeDecorator — stores JSON as text for `UserColumnsPreferences`

**Migrations** (`alembic/`): Separate version directories per DB engine — `mariadb_versions/`, `mysql_versions/`, `postgresql_versions/`, `sqlite_versions/`. Each migration must be written for all four.

### Configuration Generation (`gen/`)

**`Configurator.py`**: Loads `settings.json` + all `plugin.json` files at startup. Pre-compiles all validation regexes for O(1) membership testing. Has an exclusion set for system env vars (Docker, Kubernetes, Python internals). `IGNORE_REGEX_CHECK=yes` disables validation (dev mode only).

**`Templator.py`**: Renders NGINX configs from Jinja2 templates in `confs/`. Uses `ProcessPoolExecutor` for parallel rendering. `ConfigurableCustomUndefined` gracefully falls back to config dict values for undefined template variables. Includes SSL helpers: `_supports_tls_group()` tests cipher support with result caching, `_best_ssl_ecdh_curve()` selects optimal ECDH curve.

### Plugin System (`core/`)

42 core plugins, each following the same structure:

- `plugin.json` — settings schema with `context`, `type`, `regex`, `default`, `multiple`, `select` fields
- `<name>.lua` — Lua request-time processing (uses `require "bunkerweb.plugin"` and `require "bunkerweb.utils"`)
- `jobs/` — Python background tasks with schedule (`once`/`minute`/`hour`/`day`/`week`), `reload` flag (triggers NGINX reload on success), `run_async` flag
- `confs/` — NGINX config template fragments
- `ui/` (optional) — Custom UI pages and actions

`order.json` defines plugin execution order across phases: `init`, `init_worker`, `set`, `ssl_client_hello_default`, `ssl_certificate`, `access`, `headers`, `log`, `preread`, `log_stream`, `log_default`, `timer`, `init_workers`.

The `stream` field in `plugin.json` (`yes`/`no`/`partial`) controls whether a plugin runs in TCP/UDP stream mode.

### Utilities (`utils/`)

- **`jobs.py`**: `Job` class manages cache at `/var/cache/bunkerweb/<plugin_id>/`. Uses `_write_atomic()` to prevent partial files. Thread-safe tar.gz extraction with LOCK. `restore_cache()` rebuilds from database. `EXPIRE_TIME` dict controls cleanup scheduling.
- **`ApiCaller.py`**: `send_to_apis()` POSTs/GETs to multiple API endpoints in parallel via `ThreadPoolExecutor`. `send_files()` handles tar.gz uploads. Used by CLI, Scheduler, and Autoconf.
- **`common_utils.py`**: `handle_docker_secrets()` reads from `/run/secrets` when present (distro-agnostic). `effective_cpu_count()` respects cgroup limits. `bytes_hash()`/`file_hash()` use SHA512. `PLUGIN_TAR_COMPRESS_LEVEL = 3`.
- **`logger.py`**: `BWLogger` supports stderr, file, and syslog (UDP/TCP). Configured via `LOG_LEVEL`, `LOG_FILE_PATH`, `LOG_SYSLOG_ADDRESS`, `LOG_SYSLOG_TAG`. Has SQLAlchemy-specific log level control.

### API Client (`api/`)

`API.py` is a thin HTTP client for inter-component communication. Constructor: `API(endpoint, host=None, token=None)`. Falls back from HTTPS to HTTP automatically. Uses bearer token auth. `from_instance(dict)` builds from database instance records.

### CLI (`cli/`)

`CLI.py` inherits from `ApiCaller`. Commands: `ban`, `unban`, `bans`, `plugin_list`, `custom` (plugin-specific). Connects directly to database and Redis for cache operations. Entry point: `main.py` → `bwcli` script in `helpers/` (installed to `/usr/bin/bwcli` by the Linux packaging in `src/linux/`).

### Settings Schema (`settings.json`)

65 settings in `settings.json` (mostly `global`; additional settings defined per-plugin in `plugin.json`). Each entry:

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

## Key Patterns to Know

- **Job names are global across all plugins** — no namespace isolation, collisions are possible
- **Lua and Python are fully decoupled** — Lua uses NGINX shared dicts synchronized by the Scheduler; it never calls Python directly
- **`settings.json` is loaded once at startup** — runtime changes require database updates + reload signal
- **All four DB engines must be supported** — SQLite (WAL mode), MariaDB, MySQL, PostgreSQL. Migrations need all four version directories.
- **Connection pooling**: QueuePool for all engines. SQLite uses WAL for better concurrency.
- **Template rendering scales with CPUs** — `ProcessPoolExecutor` in Templator, `ThreadPoolExecutor` in ApiCaller
