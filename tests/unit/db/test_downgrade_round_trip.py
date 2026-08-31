"""An operator who upgraded 1.6.x -> 1.7 must be able to go back.

1.7 promises a guaranteed restore: put back a pre-upgrade backup, run the old images again.
Nothing in the repository proved that, so this walks the whole path an operator walks, on every
engine the unit suite can reach, through the product's own code -- `backup_database` and
`restore_database` from `src/common/core/backup/backup.py`, the same functions
`bwcli plugin backup save|restore` calls -- and never a hand-rolled dump:

    1.6.13 schema + rows  ->  backup  ->  alembic upgrade head  ->  write 1.7-only rows
                                                                        |
    old code's queries run  <-  1.6.13 schema + the same rows  <-  restore

The interesting half is the fourth step. A restore is a **downgrade by replacement**: the 1.7-only
rows an operator created between the upgrade and the rollback are destroyed, and the alembic
revision goes back with them so the old images stamp-check clean. That loss is correct, and it is
asserted explicitly rather than left to be discovered on the day someone needs it -- an assertion
that says "these rows are gone" is a specification of what an operator gives up, and it fails loudly
if a future change makes a restore leave 1.7 debris behind instead.

Not a duplicate of `test_upgrade_schema_parity.py`. That file asks whether an upgraded database
matches a fresh one; this one asks whether an upgraded database can be put back. It reuses that
file's baseline machinery on purpose -- `_baseline_metadata`, `_revision_for`, `_product_uri`,
`_wipe` and `BASELINE_TAG` are imported from it rather than copied, so the two tests can never
disagree about what "the schema 1.6.13 shipped" or "the revision the product stamps" means. Two
copies of that would drift the first time the baseline tag moves.

Engines with no client binary skip, exactly as an unreachable engine already does: `backup_database`
shells out to `sqlite3` / `pg_dump` / `mariadb-dump` and `restore_database` to `sqlite3` / `psql` /
`mariadb`, so without them there is nothing to measure and a green run would mean nothing.

**Known-broken today, and deliberately not fixed here.** The 1.7 alembic heads create
`bw_resources.type` as `ENUM('certificate')` while the model declares `String(64)`, so an *upgraded*
PostgreSQL/MySQL/MariaDB database rejects rows a *fresh* one accepts. Measured here, it is bigger
than "the three non-certificate types are rejected": on PostgreSQL the model binds a varchar and
there is no implicit cast from varchar to an enum, so **every** insert into `bw_resources` fails,
`certificate` included, and an upgraded PostgreSQL install cannot write the table at all. MariaDB
and MySQL accept `certificate` and truncate the other three. That is the release blocker the closing
docs+Alembic chantier owns (the heads are regenerated there, so any revision written here would be
thrown away). The test states the intended contract -- every 1.7-only row inserts -- and `xfail`s
what that defect breaks, naming it and listing the cascade. It never routes around the broken path:
the round trip continues with whatever rows did land, so the restore assertions still run.
"""

import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from shutil import which

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text

from model import Base  # type: ignore

# The baseline is defined once, in the parity test, and imported rather than restated -- see the
# module docstring. pytest's default `prepend` import mode puts this file's own directory on
# `sys.path` at collection, so the sibling resolves whether the suite, the directory or this single
# file was named on the command line.
from test_upgrade_schema_parity import (  # noqa: E402
    ALEMBIC,
    BASELINE_VERSION,
    _baseline_metadata,
    _product_uri,
    _revision_for,
    _wipe,
)

# `backup_database` picks its dump binary from the URI's drivername and `restore_database` its
# restore binary the same way, so an engine missing either has nothing to prove here and skips --
# the same treatment an unconfigured or unreachable engine already gets. Each entry is the
# alternative (dump, restore) PAIRS the product accepts: `mysql_client_command` prefers the MariaDB
# client and falls back to the MySQL one, and a host with `mysqldump` but no `mysql` can dump and
# not restore, so the pair has to be checked together rather than binary by binary.
CLIENT_BINARIES = {
    "sqlite": (("sqlite3", "sqlite3"),),
    "postgresql": (("pg_dump", "psql"),),
    "mariadb": (("mariadb-dump", "mariadb"), ("mysqldump", "mysql")),
    "mysql": (("mysqldump", "mysql"), ("mariadb-dump", "mariadb")),
}


def _clients_present(db_engine):
    return any(all(which(binary) for binary in pair) for pair in CLIENT_BINARIES[db_engine])


FIXED_DT = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

# The fingerprint of the known `bw_resources.type` Alembic head defect, per engine family, as the
# servers actually word it. The xfail below matches on these rather than on "a resource insert
# failed", so a future unrelated defect in the same table cannot inherit this one's excuse.
ENUM_DEFECT_MARKERS = (
    "resource_types_enum",  # PostgreSQL: DatatypeMismatch / InvalidTextRepresentation
    "Data truncated for column 'type'",  # MariaDB and MySQL: DataError 1265
)

# The one table 1.6.13 had and 1.7 dropped. A restore has to bring it back: the old code selects
# from it, and `Base.metadata` -- which is what `restore_database` drops with -- does not name it,
# so nothing but the dump can recreate it.
DROPPED_IN_17 = "bw_ui_user_columns_preferences"

# What an operator loses, enumerated. Every one of these is a table 1.7 introduced, so a 1.6.13 dump
# cannot contain it and a restore must remove it; the point of listing them is that the loss is a
# specification rather than a surprise.
SEVENTEEN_ONLY_TABLES = (
    "bw_bans",
    "bw_certificates",
    "bw_metrics_baseline",
    "bw_metrics_requests",
    "bw_redirects",
    "bw_resource_attachments",
    "bw_resource_group_entries",
    "bw_resource_group_usages",
    "bw_resource_groups",
    "bw_resources",
    "bw_ui_user_preferences",
    "bw_ui_user_webauthn_credentials",
    "bw_upstream_servers",
    "bw_upstreams",
    "bw_workflows",
)

# Columns 1.7 added to tables that already existed in 1.6.13. A restore replays a dump written by
# the 1.6.13 schema, so these have to be gone afterwards -- if one survived, the restored database
# would be neither shape and the old code's INSERTs would hit a NOT NULL column it never heard of.
SEVENTEEN_ONLY_COLUMNS = {
    "bw_instances": ("credential_ciphertext", "credential_key_id", "credential_nonce", "credential_updated_at", "tls_fingerprint", "tls_mode"),
    "bw_metadata": ("certificate_keyring", "certificate_keyring_active", "certificates_changed", "last_certificates_change"),
    "bw_plugins": ("enabled", "icon"),
    "bw_settings": ("case_insensitive",),
}


@contextmanager
def _engine(uri):
    engine = create_engine(uri)
    try:
        yield engine
    finally:
        engine.dispose()


def _seed_baseline(engine, metadata):
    """Representative 1.6.13 rows, inserted through the baseline metadata rather than the 1.7 model.

    Core inserts, not the ORM: the 1.7 mapped classes carry columns this schema does not have, so
    they cannot address it at all. Every value is fixed -- no `now()`, no autoincrement left to the
    engine where it is compared -- because these rows are the ones asserted byte-identical after the
    round trip, and a value the database chose would compare equal to itself for the wrong reason.
    """
    tables = metadata.tables
    with engine.begin() as conn:
        conn.execute(
            tables["bw_plugins"].insert(),
            [
                {
                    "id": "general",
                    "name": "General",
                    "description": "Core settings",
                    "version": "1.0",
                    "stream": "partial",
                    "type": "core",
                    "method": "manual",
                    "data": None,
                    "checksum": None,
                    "config_changed": False,
                    "last_config_change": None,
                }
            ],
        )
        conn.execute(
            tables["bw_settings"].insert(),
            [
                {
                    "id": "SERVER_NAME",
                    "name": "Server name",
                    "plugin_id": "general",
                    "context": "multisite",
                    "default": "",
                    "help": "List of the virtual hosts served by BunkerWeb",
                    "label": "Server name",
                    "regex": "^.*$",
                    "type": "text",
                    "multiple": None,
                    "separator": " ",
                    "accept": None,
                    "order": 0,
                },
                {
                    "id": "USE_ANTIBOT",
                    "name": "Antibot",
                    "plugin_id": "general",
                    "context": "multisite",
                    "default": "no",
                    "help": "Challenge suspicious clients",
                    "label": "Antibot",
                    "regex": "^.*$",
                    "type": "select",
                    "multiple": None,
                    "separator": " ",
                    "accept": None,
                    "order": 1,
                },
            ],
        )
        conn.execute(
            tables["bw_jobs"].insert(),
            [{"name": "roundtrip-job", "plugin_id": "general", "file_name": "roundtrip.py", "every": "day", "reload": True, "run_async": False}],
        )
        conn.execute(
            tables["bw_services"].insert(),
            [
                {"id": "app1.example.com", "method": "manual", "is_draft": False, "creation_date": FIXED_DT, "last_update": FIXED_DT},
                {"id": "app2.example.com", "method": "autoconf", "is_draft": True, "creation_date": FIXED_DT, "last_update": FIXED_DT},
            ],
        )
        conn.execute(
            tables["bw_services_settings"].insert(),
            [
                {"service_id": "app1.example.com", "setting_id": "USE_ANTIBOT", "value": "captcha", "file_name": None, "suffix": 0, "method": "manual"},
                {"service_id": "app2.example.com", "setting_id": "USE_ANTIBOT", "value": "javascript", "file_name": None, "suffix": 0, "method": "autoconf"},
            ],
        )
        conn.execute(
            tables["bw_global_values"].insert(),
            [{"setting_id": "SERVER_NAME", "value": "app1.example.com app2.example.com", "file_name": None, "suffix": 0, "method": "manual"}],
        )
        conn.execute(
            tables["bw_custom_configs"].insert(),
            [
                {
                    "service_id": "app1.example.com",
                    "type": "server_http",
                    "name": "roundtrip",
                    # Bytes with a NUL and a non-ASCII byte on purpose: a BLOB is where a dump
                    # dialect most easily loses fidelity, and "byte-identical" has to mean it.
                    "data": b"# roundtrip\x00\xc3\xa9 more_clients 10.0.0.0/8;",
                    "checksum": "e" * 128,
                    "method": "manual",
                    "is_draft": False,
                }
            ],
        )
        conn.execute(
            tables["bw_ui_users"].insert(),
            [
                {
                    "username": "admin",
                    "email": None,
                    "password": "$2b$12$" + "a" * 53,
                    "method": "manual",
                    "admin": True,
                    "theme": "light",
                    "language": "en",
                    "totp_secret": None,
                    "creation_date": FIXED_DT,
                    "update_date": FIXED_DT,
                }
            ],
        )
        conn.execute(
            tables["bw_metadata"].insert(),
            [{"id": 1, "is_initialized": True, "first_config_saved": True, "integration": "Docker", "version": BASELINE_VERSION}],
        )
        conn.execute(
            tables[DROPPED_IN_17].insert(),
            [{"user_name": "admin", "table_name": "services", "columns": {"1": True, "2": False}}],
        )


def _snapshot(engine, metadata, tables):
    """Every row of `tables`, read through the baseline metadata, ordered and hashable.

    Read column by column in the metadata's own order rather than with `SELECT *`, so a restored
    database that happens to have the columns in a different order still compares equal on the data
    -- and so a table that came back with a column missing raises here instead of quietly comparing
    a shorter tuple.
    """
    out = {}
    with engine.connect() as conn:
        for name in tables:
            table = metadata.tables[name]
            columns = [table.c[c.name] for c in table.columns]
            rows = conn.execute(select(*columns).order_by(*columns)).fetchall()
            out[name] = [tuple(_normalise(value) for value in row) for row in rows]
    return out


def _normalise(value):
    """Compare values, not their per-engine Python rendering.

    Two round-trip artefacts are not data loss and must not read as it: MariaDB hands back `DATETIME`
    naive where PostgreSQL keeps the offset it was given, and MariaDB renders a `BOOLEAN` as the
    `TINYINT(1)` it really is. Everything else -- strings, bytes, numbers, NULL -- is compared as it
    comes back.
    """
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, bool):
        return int(value)
    return value


def _write_seventeen_only_rows(engine):
    """The rows a restore is going to destroy: one of each 1.7-only shape.

    Each insert gets its own transaction and its own `except`, for two reasons. A failure here is
    data -- the known ENUM defect makes three of them fail on some engines and the report needs to
    name which -- and on PostgreSQL a failed statement poisons the transaction, so one rejected
    insert in a shared block would take every later one with it and the result would say nothing
    about them.
    """
    resource_ids = {kind: f"00000000-0000-4000-8000-00000000000{index}" for index, kind in enumerate(("certificate", "redirect", "upstream", "workflow"))}
    tables = Base.metadata.tables

    plan = [
        (
            f"resource:{kind}",
            tables["bw_resources"],
            {"id": rid, "type": kind, "name": f"roundtrip-{kind}", "description": "", "creation_date": FIXED_DT, "last_update": FIXED_DT},
        )
        for kind, rid in resource_ids.items()
    ]
    plan += [
        (
            "upstream",
            tables["bw_upstreams"],
            {"resource_id": resource_ids["upstream"], "method": "manual", "protocol": "http", "backend_ssl": False, "keepalive": 32},
        ),
        (
            "upstream_server",
            tables["bw_upstream_servers"],
            {
                "resource_id": resource_ids["upstream"],
                "host": "10.0.0.1:8080",
                "weight": 1,
                "max_fails": 3,
                "fail_timeout": "10s",
                "backup": False,
                "down": False,
                "order": 0,
            },
        ),
        (
            "redirect",
            tables["bw_redirects"],
            {
                "resource_id": resource_ids["redirect"],
                "from_path": "/old",
                "to_url": "https://example.com/new",
                "status_code": "301",
                "append_request_uri": True,
            },
        ),
        (
            "workflow",
            tables["bw_workflows"],
            {"resource_id": resource_ids["workflow"], "schema_version": 1, "definition": '{"rules": []}'},
        ),
        (
            "ban",
            tables["bw_bans"],
            {
                "ip": "203.0.113.7",
                "ban_scope": "global",
                "service_id": "_",
                "origin": "ui",
                "reason": "roundtrip",
                "reason_data": None,
                "country": "FR",
                "created_at": FIXED_DT,
                "created_by": "admin",
                "expires_at": None,
                "revoked_at": None,
                "revoked_by": None,
            },
        ),
    ]
    plan += [
        (
            f"metrics_request:{protocol}",
            tables["bw_metrics_requests"],
            {
                "request_id": f"roundtrip-{protocol}",
                "instance_hostname": "bw-1",
                "date": FIXED_DT,
                "protocol": protocol,
                "ip": "203.0.113.8",
                "country": "FR",
                "method": "GET" if protocol == "http" else None,
                "url": "/" if protocol == "http" else None,
                "status": 200,
                "user_agent": None,
                "reason": "-",
                "server_name": "app1.example.com",
                "data": None,
                "security_mode": "block",
                "listen_port": 443 if protocol == "http" else 5432,
                "created_at": FIXED_DT,
            },
        )
        for protocol in ("http", "stream")
    ]

    written, failed = [], {}
    for label, table, values in plan:
        try:
            with engine.begin() as conn:
                conn.execute(table.insert(), [values])
            written.append(label)
        except Exception as error:  # noqa: BLE001 -- the message is the finding
            failed[label] = f"{type(error).__name__}: {str(error).splitlines()[0]}"
    return written, failed


def _run_round_trip(db_engine, tmp_path, quiet_logger, monkeypatch):
    """The whole operator path, once, capturing everything the assertions below read.

    Returns plain data, never a live connection: the assertions run long after the fixture, and on
    PostgreSQL/MariaDB they run against a database the *next* parametrization has already wiped.
    """
    # Order matters, and it is the whole difference between "absent" and "broken". `_product_uri`
    # skips an engine that is unconfigured or unreachable -- a legitimate absence, and the treatment
    # the rest of the suite already gives it. Only once it has returned do we know the engine IS
    # there, and an engine that is there with no client binary is a broken environment, so it FAILS.
    # Skipping that case is how a guarantee quietly stops being measured: this is the only test in
    # `tests/unit/` that shells out to a database client, so nothing else goes red first to warn
    # anyone, and a runner image that drops one would leave the matrix green and the downgrade
    # promise unproven.
    uri = _product_uri(db_engine, tmp_path)
    if not _clients_present(db_engine):
        return {
            "fail": f"{db_engine} is reachable but none of its client binaries are installed "
            f"({' / '.join(' + '.join(pair) for pair in CLIENT_BINARIES[db_engine])}); "
            f"backup_database and restore_database shell out to them, so this is a broken environment, not an absent engine",
        }

    import backup  # noqa: E402 -- on sys.path via the fixture below

    baseline = _baseline_metadata()
    baseline_tables = sorted(baseline.tables)

    # Same three moves as `test_upgrade_schema_parity`, for the same reasons: `DATABASE_URI` is what
    # `entrypoint.sh:83-99` re-exports and `env.py:34-38` reads, the chdir is what makes
    # `alembic.ini`'s relative `script_location`/`version_locations` resolve, and the explicit
    # `version_locations` is required because `command.stamp` freezes the `ScriptDirectory` from the
    # config before env.py ever runs.
    monkeypatch.setenv("DATABASE_URI", uri)
    monkeypatch.chdir(ALEMBIC)
    config = Config("alembic.ini")
    config.set_main_option("version_locations", f"{db_engine}_versions")
    baseline_revision = _revision_for(BASELINE_VERSION, db_engine)

    # Everything from here to the final capture runs inside a `try` whose `finally` wipes, and that
    # is not tidiness -- it is the difference between this test failing and this test taking every
    # other lane down with it. PostgreSQL and MariaDB are ONE database for the whole run.
    # `backup_database` calls `sys_exit(1)` on a dump failure (`backup.py:493,497`), and `SystemExit`
    # is not an `Exception`, so one transient `pg_dump` hiccup would leave the shared database at the
    # restored 1.6.13 shape. `fixtures.engines.reset_schema` then cannot reset it -- it clears with
    # `Base.metadata.drop_all`, which cannot drop `bw_ui_users` while the 1.6-only
    # `bw_ui_user_columns_preferences` still holds a FK to it -- so EVERY later test taking the `db`
    # fixture errors in setup, in whatever lane pytest-randomly scheduled next. A bare `finally`
    # covers `SystemExit`, `KeyboardInterrupt` and ordinary failures alike; a `_wipe` that raises
    # during unwinding chains onto the original rather than hiding it.
    try:
        return _round_trip_body(db_engine, uri, tmp_path, backup, baseline, baseline_tables, config, baseline_revision, quiet_logger)
    finally:
        _wipe(uri)


def _round_trip_body(db_engine, uri, tmp_path, backup, baseline, baseline_tables, config, baseline_revision, quiet_logger):
    """Steps 1-5 of the operator path. Split out only so the wipe above can be a plain `finally`."""
    # --- 1. the schema 1.6.13 shipped, with rows in it ---------------------------------------
    _wipe(uri)
    with _engine(uri) as engine:
        baseline.create_all(engine)
        _seed_baseline(engine, baseline)
        seeded = _snapshot(engine, baseline, baseline_tables)

    # A real 1.6.13 install carries its stamp -- `entrypoint.sh` writes it on first start -- and the
    # stamp is *inside* the database, so it is inside the backup too. Backing up before stamping
    # would take a dump with no `alembic_version` table in it and quietly make the restore assertion
    # below unprovable: the revision would come back absent, which is neither what a real backup
    # holds nor what the old images can start from.
    command.stamp(config, baseline_revision)

    from Database import Database  # noqa: E402

    # --- 2. back it up the way `bwcli plugin backup save` does --------------------------------
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    db = Database(quiet_logger, sqlalchemy_string=uri, log=False)
    try:
        _, backup_file = backup.backup_database(datetime.now().astimezone(), db, backup_dir=backup_dir)
    finally:
        db.close()

    # --- 3. upgrade to the 1.7 head, exactly as entrypoint.sh does ----------------------------
    command.upgrade(config, "head")
    with _engine(uri) as engine:
        Base.metadata.create_all(engine, checkfirst=True)  # what initialization.py does next
        upgraded_tables = sorted(inspect(engine).get_table_names())
        written, write_failures = _write_seventeen_only_rows(engine)
        upgraded_revision = _alembic_revision(engine)

    # --- 4. restore, the way `bwcli plugin backup restore` does -------------------------------
    db = Database(quiet_logger, sqlalchemy_string=uri, log=False)
    restore_failure = None
    try:
        try:
            backup.restore_database(backup_file, db)
        except SystemExit as exited:
            # How `restore_database` reports a dump/restore command that failed: it logs and exits.
            restore_failure = f"exit {exited.code}"
        except Exception as error:  # noqa: BLE001
            # How it reports everything else: it does not. Nothing between the engine guard and the
            # end of the function is wrapped, so a failure in the clearing step leaves the function
            # by raising, and `bwcli plugin backup restore` turns it into a generic
            # "Error while executing backup restore command". Captured rather than propagated so the
            # assertion below names the failure instead of the whole run erroring out.
            restore_failure = f"{type(error).__name__}: {str(error).splitlines()[0]}"
    finally:
        db.close()

    # --- 5. what an operator is left holding --------------------------------------------------
    with _engine(uri) as engine:
        restored_tables = sorted(inspect(engine).get_table_names())
        restored_columns = {name: sorted(c["name"] for c in inspect(engine).get_columns(name)) for name in restored_tables}
        restored_revision = _alembic_revision(engine)
        survivors = _seventeen_only_survivors(engine, restored_tables)
        restored = _snapshot(engine, baseline, [name for name in baseline_tables if name in restored_tables]) if restore_failure is None else {}
        old_code_failures = _old_code_queries(engine, baseline, baseline_tables)

    return {
        "fail": None,
        "baseline_tables": baseline_tables,
        "seeded": seeded,
        "upgraded_tables": upgraded_tables,
        "upgraded_revision": upgraded_revision,
        "written": written,
        "write_failures": write_failures,
        "restore_failure": restore_failure,
        "restored_tables": restored_tables,
        "restored_columns": restored_columns,
        "restored_revision": restored_revision,
        "survivors": survivors,
        "restored": restored,
        "old_code_failures": old_code_failures,
    }


def _alembic_revision(engine):
    """The revision stamped in the database, or None when the table is gone.

    This is the one row that decides whether the old images start at all: `entrypoint.sh` reads it
    to pick what to stamp, and `alembic_version` is not in `Base.metadata`, so the `drop_all` in
    `restore_database` cannot touch it -- only the dump's own DROP/CREATE/INSERT puts it back.
    """
    try:
        with engine.connect() as conn:
            return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:  # noqa: BLE001 -- an absent table is an answer, not an error
        return None


def _seventeen_only_survivors(engine, restored_tables):
    """1.7-only rows still readable after the restore. Anything here is debris, not a feature."""
    survivors = {}
    with engine.connect() as conn:
        for name in SEVENTEEN_ONLY_TABLES:
            if name not in restored_tables:
                continue
            try:
                survivors[name] = conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar()  # noqa: S608 -- names are this module's constants
            except Exception as error:  # noqa: BLE001
                survivors[name] = f"unreadable: {type(error).__name__}"
    return survivors


def _old_code_queries(engine, baseline, tables):
    """Run the 1.6.13 code's own SELECTs. A restore that leaves the schema unusable is not a restore.

    The baseline metadata *is* the old code's model, so selecting its columns from every table is
    exactly the query surface the old release issues -- and the one thing a partially-restored
    schema breaks first.
    """
    failures = {}
    with engine.connect() as conn:
        for name in tables:
            table = baseline.tables[name]
            try:
                conn.execute(select(*[table.c[c.name] for c in table.columns]).limit(1)).fetchall()
            except Exception as error:  # noqa: BLE001
                failures[name] = f"{type(error).__name__}: {str(error).splitlines()[0]}"
    return failures


# One round trip per engine, shared by every assertion below. It costs an alembic run over the whole
# 1.6->1.7 chain plus two shell-outs per engine, so re-running it for each of the ten assertions
# would multiply that by ten to re-derive the same numbers. What is cached is plain data, so the
# tests stay order-independent; on PostgreSQL/MariaDB it is also the only correct choice, since the
# two engines share one database and the next parametrization wipes what a later assertion would
# have re-read.
_ROUND_TRIPS = {}


@pytest.fixture
def round_trip(db_engine, tmp_path, quiet_logger, _clean_env, monkeypatch):
    """`_clean_env` is requested for its side effects, not its value: it strips the developer's
    `DATABASE_*` knobs and sets `DATABASE_RETRY_TIMEOUT=0`, without which the `Database` constructor
    this round trip builds twice loops for ~60s and then calls `os._exit` on an unreachable engine,
    which no `pytest.skip` can catch.

    `src/common/core/backup` is not a package and the root conftest does not inject it, so it goes
    on `sys.path` here -- the same thing `tests/unit/backup/*` does, and the reason `import backup`
    inside the round trip resolves.
    """
    backup_dir = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup"
    if str(backup_dir) not in sys.path:
        sys.path.insert(0, str(backup_dir))

    if db_engine not in _ROUND_TRIPS:
        _ROUND_TRIPS[db_engine] = _run_round_trip(db_engine, tmp_path, quiet_logger, monkeypatch)
    result = _ROUND_TRIPS[db_engine]
    if result["fail"]:
        # An engine that is unconfigured or unreachable never gets here: `_product_uri` raises
        # `Skipped` from inside the round trip, which is the suite's existing treatment for one that
        # is simply absent. Reaching this line means it was present and unusable.
        pytest.fail(result["fail"])
    return result


def test_the_baseline_really_is_older_than_the_model(round_trip):
    """Anti-vacuity. If the baseline ever stops differing from 1.7 -- a tag bump, a `git show` that
    returned the working tree -- every "the 1.7-only thing is gone" assertion below passes for free.
    """
    assert set(SEVENTEEN_ONLY_TABLES) <= set(Base.metadata.tables), "the 1.7-only table list names tables the model no longer declares; it is stale"
    assert not set(SEVENTEEN_ONLY_TABLES) & set(round_trip["baseline_tables"]), "the baseline already has 1.7 tables; it is not an older schema"
    assert DROPPED_IN_17 in round_trip["baseline_tables"] and DROPPED_IN_17 not in Base.metadata.tables


def test_the_upgrade_really_happened_before_the_restore(round_trip):
    """The other half of the anti-vacuity check: a restore that undoes nothing proves nothing."""
    missing = sorted(set(SEVENTEEN_ONLY_TABLES) - set(round_trip["upgraded_tables"]))

    assert not missing, f"the upgrade did not create the 1.7 tables, so there was nothing to roll back: {missing}"
    assert round_trip["upgraded_revision"] is not None, "no alembic revision was stamped by the upgrade"


def test_the_upgraded_schema_accepts_every_1_7_only_row(round_trip, db_engine):
    """The contract: a database that has been upgraded behaves like one that was installed fresh.

    It does not, today, and the failure is the known Alembic head defect -- `bw_resources.type` is
    created as `ENUM('certificate')` where the model declares `String(64)`, so a `redirect`,
    `upstream` or `workflow` resource is rejected by an upgraded PostgreSQL/MySQL/MariaDB and
    accepted by a fresh one. Owned by the closing docs+Alembic chantier, which regenerates the
    heads; fixing it here would write a revision that chantier throws away.

    The xfail is conditional on the observed failure rather than on the engine name, so the day the
    heads are regenerated this turns green by itself instead of starting to XPASS.
    """
    failures = round_trip["write_failures"]
    rendered = "\n  ".join(f"{label}: {error}" for label, error in sorted(failures.items()))

    # Only `bw_resources` inserts can carry the ENUM defect; the child tables fail on a foreign key
    # to a resource that was never created, which is a consequence rather than a second defect.
    resource_failures = {label: error for label, error in failures.items() if label.startswith("resource:")}
    enum_rejected = sorted(label for label, error in resource_failures.items() if any(marker in error for marker in ENUM_DEFECT_MARKERS))

    # Two conditions, and the second is the one that matters. Keying on "a resource insert failed"
    # alone would let any FUTURE, unrelated defect that breaks `bw_resources` xfail under this
    # defect's name -- a permanent way to turn a red green, with the reason string actively lying
    # about the cause. So the error TEXT has to carry the ENUM signature, and EVERY failed resource
    # insert has to carry it: one that does not means something else is also broken, and that
    # belongs in the assert below with its message intact, not swallowed here.
    if enum_rejected and len(enum_rejected) == len(resource_failures):
        # Keyed on ANY rejected resource, not only the non-certificate ones, because the defect is
        # not the same size on every engine and a condition written for the smaller case would
        # mis-report the larger one:
        #
        #   * PostgreSQL refuses ALL FOUR, `certificate` included -- `DatatypeMismatch: column
        #     "type" is of type resource_types_enum but expression is of type character varying`.
        #     The model binds a varchar and PostgreSQL has no implicit cast from varchar to an enum,
        #     so on an upgraded install `bw_resources` is not partly restricted, it is *unwritable*.
        #   * MariaDB/MySQL accept `certificate` (a valid label) and TRUNCATE the other three
        #     (`DataError 1265`) rather than refusing them.
        #
        # The cascade is reported with the cause: every child row keys on a resource that was
        # refused, so `upstream`, `upstream_server`, `redirect` and `workflow` then fail on the
        # foreign key rather than on anything of their own. Rendered with their error text, because
        # a bare list of labels is exactly what would make a mislabelled xfail impossible to spot.
        pytest.xfail(
            f"1.7 alembic heads type bw_resources.type as ENUM('certificate') where the model declares String(64), "
            f"so an upgraded {db_engine} rejects {enum_rejected} and everything keyed on them "
            f"-- owned by the closing docs+Alembic chantier. All of it:\n  " + rendered
        )

    assert not failures, "rows a fresh 1.7 install accepts that an upgraded one rejects:\n  " + rendered


def test_the_restore_succeeds(round_trip):
    assert round_trip["restore_failure"] is None, f"restore_database did not complete: {round_trip['restore_failure']}"


def test_the_schema_is_back_at_the_1_6_shape(round_trip):
    """Every baseline table present, and none of the 1.7-only ones left behind.

    The second half is the one that can regress quietly: `restore_database` clears the database with
    `Base.metadata.drop_all`, which knows only what the *current* model declares, so a 1.7 table that
    ever stops being declared -- a plugin-created one, a table dropped from the model in 1.8 -- would
    survive the restore on PostgreSQL and MySQL, where the dump's own DROPs only cover what the dump
    contains.
    """
    restored = set(round_trip["restored_tables"])
    missing = sorted(set(round_trip["baseline_tables"]) - restored)
    leftover = sorted(set(SEVENTEEN_ONLY_TABLES) & restored)

    assert not missing, f"baseline tables the restore did not bring back: {missing}"
    assert not leftover, f"1.7 tables still standing after a restore to 1.6.13: {leftover}"


def test_no_1_7_only_column_survives_on_a_table_that_existed_in_1_6(round_trip):
    """A shared table restored with 1.7 columns still attached is the worst outcome of the three.

    It is neither shape: the old code's `INSERT` names the 1.6 columns and the leftover 1.7 ones are
    `NOT NULL` with no default, so the restore reads as a success and the first write fails.
    """
    leftover = []
    for table, columns in SEVENTEEN_ONLY_COLUMNS.items():
        present = set(round_trip["restored_columns"].get(table, ()))
        leftover += [f"{table}.{column}" for column in columns if column in present]

    assert not leftover, f"1.7 columns still present on restored 1.6 tables: {leftover}"


def test_the_pre_upgrade_rows_come_back_unchanged(round_trip):
    """Byte-identical, every table, including the BLOB with a NUL in it."""
    seeded, restored = round_trip["seeded"], round_trip["restored"]

    drift = {name: (seeded[name], restored.get(name)) for name in seeded if restored.get(name) != seeded[name]}

    assert not drift, "rows that did not survive the round trip:\n  " + "\n  ".join(
        f"{name}: before={before!r} after={after!r}" for name, (before, after) in sorted(drift.items())
    )


def test_the_1_7_only_data_is_gone(round_trip):
    """The loss, asserted rather than discovered.

    A restore is a downgrade by replacement: everything written after the upgrade is destroyed. That
    is the correct behaviour and the operator-visible cost of a rollback -- bans, metrics, resources,
    certificates, workflows, upstreams, redirects, resource groups, UI preferences and passkeys, all
    of it. The assertion exists so the cost is documented in the suite and so a future change that
    leaves some of it behind is a failure rather than a surprise.
    """
    assert round_trip["written"], "no 1.7-only row was written, so their disappearance proves nothing"

    survivors = {name: count for name, count in round_trip["survivors"].items() if count}
    assert not survivors, f"1.7-only data readable after a restore to 1.6.13: {survivors}"


def test_the_alembic_revision_goes_back_with_the_data(round_trip, db_engine):
    """Without this the old images will not start.

    `entrypoint.sh` stamps from the version in `bw_metadata` and then runs `alembic upgrade head`
    against the 1.6 script directory. A database whose `alembic_version` still holds the 1.7 head
    fails that with "Can't locate revision", and an empty `alembic_version` is no better -- the
    stamp is a no-op and 1.6's own migrations replay over a schema that already has them.
    """
    expected = _revision_for(BASELINE_VERSION, db_engine)

    assert (
        round_trip["restored_revision"] == expected
    ), f"alembic_version after restore is {round_trip['restored_revision']!r}, expected the {BASELINE_VERSION} revision {expected!r}"


def test_the_old_code_can_query_the_restored_database(round_trip):
    """The point of the whole exercise: 1.6.13's queries run against what the restore produced."""
    failures = round_trip["old_code_failures"]

    assert not failures, "queries the 1.6.13 code issues that fail on the restored database:\n  " + "\n  ".join(
        f"{k}: {v}" for k, v in sorted(failures.items())
    )
