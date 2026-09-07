#!/usr/bin/env python3
"""Read-only downgrade preflight, and the reversible writer hold that precedes a downgrade.

Two halves, deliberately kept apart:

* :func:`preflight` answers "can this installation go back to version X?" and **mutates
  nothing**. Every check returns its own verdict; the overall verdict is the worst of them.
  The rule the conception makes absolute is that an unvalidated combination is refused
  *before* any mutation, never discovered halfway through -- so an answer this module cannot
  prove degrades the verdict, it never gets assumed away.
* :func:`acquire_hold` / :func:`release_hold` / :func:`drain` hold the writers still while a
  downgrade runs. The hold is one key in the job broker, and it is bounded (a TTL), single
  (``SET NX`` -- a second attempt refuses instead of interleaving) and reversible (the holder
  deletes it, and a holder that dies lets it expire).

* :func:`execute_downgrade` is the one thing here that mutates. It runs only for a pair the
  manifest marks ``in_place_tested``, only while a quiescence hold is held, only after the
  read-only preflight it re-runs itself has come back clean -- and it takes its own backup
  immediately before mutating so that any failure has somewhere to fall back to.
"""

from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from json import JSONDecodeError, dumps, loads
from os import getenv, sep
from os.path import join
from pathlib import Path
from shutil import disk_usage
from sys import path as sys_path
from time import monotonic, sleep
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

import sqlalchemy as sa
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import NullPool

from Database import mask_db_uri, scrub_db_secret  # type: ignore
from logger import getLogger  # type: ignore

LOGGER = getLogger("DOWNGRADE")

# The same default `Database.__init__` falls back to.
SQLITE_DEFAULT_URI = "sqlite:////var/lib/bunkerweb/db.sqlite3"

# ── Verdicts ────────────────────────────────────────────────────────────────────────────────

IN_PLACE = "in_place_possible"
RESTORE_ONLY = "restore_only"
REFUSE = "refuse"

# Ordered worst-last: the overall verdict is the worst any single check reached, so a check
# that cannot prove its answer degrades the whole report instead of being silently dropped.
_RANK = {IN_PLACE: 0, RESTORE_ONLY: 1, REFUSE: 2}


@dataclass(frozen=True)
class Check:
    """One preflight answer: what was looked at, what it means, and the numbers behind it."""

    name: str
    verdict: str
    detail: str
    data: Dict[str, Any] = field(default_factory=dict)


def worst(checks: List[Check]) -> str:
    """The overall verdict. No checks at all is a refusal, not a pass."""
    if not checks:
        return REFUSE
    return max((check.verdict for check in checks), key=lambda verdict: _RANK.get(verdict, _RANK[REFUSE]))


# ── Version ordering ────────────────────────────────────────────────────────────────────────


# BunkerWeb versions are Debian-flavoured, not PEP 440: `1.7.0~beta` precedes `1.7.0`. Parsing
# them with a PEP 440 parser gets that backwards, and getting it backwards here would let a
# preflight call an upgrade a downgrade.
def version_key(version: str) -> Tuple[Tuple[int, ...], int, str]:
    """Sort key for a BunkerWeb version string.

    `1.6.12` -> ((1, 6, 12), 1, ""), `1.7.0~beta` -> ((1, 7, 0), 0, "beta"): the tilde suffix
    sorts *before* the bare release, exactly as dpkg orders it. Non-numeric components are
    dropped rather than raising -- an unparsable version is compared on what could be read,
    and the caller's own "are these two comparable" check is what refuses.
    """
    release, _, suffix = version.strip().partition("~")
    numbers: List[int] = []
    for part in release.split("."):
        digits = "".join(c for c in part if c.isdigit())
        if not digits:
            break
        numbers.append(int(digits))
    return tuple(numbers), 0 if suffix else 1, suffix


def is_downgrade(installed: str, target: str) -> bool:
    """True when `target` is strictly older than `installed`."""
    return version_key(target) < version_key(installed)


# ── Compatibility manifest ──────────────────────────────────────────────────────────────────

# Produced by lot A, consumed here. The conception is explicit that the CLI reads the manifest
# and never infers compatibility from the version number, so its absence is not a soft warning:
# with no row for this (from, to, engine) there is nothing proving an in-place downgrade is
# lossless, and the verdict can be no better than restore_only.
# Lot C reserved `/usr/share/bunkerweb/downgrade-manifest.json` while the file did not exist yet
# (its PO-7 asked lot A to confirm the home). Lot A ships it next to this module instead, so it
# travels with the plugin -- every image and package already copies `core/backup/` wholesale and
# no Dockerfile, fpm recipe or entrypoint had to learn a new path. `DOWNGRADE_MANIFEST` still
# overrides it, which is how the tests and an operator experiment point somewhere else.
MANIFEST_PATH = Path(getenv("DOWNGRADE_MANIFEST") or Path(__file__).resolve().parent.joinpath("downgrade-manifest.json"))


def load_manifest(path: Path = MANIFEST_PATH) -> Optional[dict]:
    """The compatibility manifest, or None when there is none to read."""
    if not path.is_file():
        return None
    with suppress(OSError, JSONDecodeError, UnicodeDecodeError):
        manifest = loads(path.read_text(encoding="utf-8"))
        if isinstance(manifest, dict):
            return manifest
    LOGGER.warning(f"Ignoring the downgrade manifest at {path}: it is not readable JSON")
    return None


def manifest_row(manifest: Optional[dict], installed: str, target: str, engine: str) -> Optional[dict]:
    """The manifest entry for this exact (from, to, engine), or None."""
    if not manifest:
        return None
    for row in manifest.get("releases") or ():
        if not isinstance(row, dict):
            continue
        if row.get("from") == installed and row.get("to") == target and row.get("engine") == engine:
            return row
    return None


def silent_losses(manifest: Optional[dict]) -> List[str]:
    """What an in-place downgrade destroys that no check counts, in the operator's words.

    Two kinds, and both are invisible to `check_irrepresentable` by construction: columns dropped
    from tables that survive (a table's row count does not move when it loses a column), and the
    tables the manifest deliberately excludes from the count because they are never empty. An
    installation with enrolled instances and no bans passes every check and still loses every
    stored instance credential, so this has to be said out loud rather than left in the manifest.
    """
    detail = (manifest or {}).get("data_loss_detail") or {}
    lines: List[str] = []

    columns = detail.get("columns")
    if isinstance(columns, dict) and columns:
        total = sum(len(v) for v in columns.values() if isinstance(v, list))
        lines.append(f"{total} column(s) dropped from {len(columns)} table(s) that otherwise survive: " + ", ".join(sorted(columns)))
        why = detail.get("columns_why")
        if isinstance(why, str) and why:
            lines.append(why)

    uncounted = detail.get("not_counted_by_the_preflight")
    if isinstance(uncounted, dict) and uncounted:
        lines.append("Destroyed but deliberately not counted above: " + ", ".join(f"{name} ({reason})" for name, reason in sorted(uncounted.items())))

    return lines


def loss_classes(manifest: Optional[dict]) -> Dict[str, str]:
    """`{table: "certain"|"conditional"}` -- what each 1.7-only table costs on an in-place downgrade.

    Declared once at the top level rather than per row because it is a property of the schema
    delta, not of the engine. An empty map is the honest answer when there is no manifest, and
    it is what makes :func:`check_irrepresentable` keep its pre-manifest behaviour.
    """
    detail = (manifest or {}).get("data_loss_detail") or {}
    tables = detail.get("tables")
    return {k: v for k, v in tables.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(tables, dict) else {}


def target_revision(row: Optional[dict]) -> str:
    """The Alembic revision an in-place downgrade for this pair has to land on."""
    return ((row or {}).get("alembic") or {}).get("to_revision") or ""


# ── Checks (pure: facts in, verdict out) ────────────────────────────────────────────────────


def check_versions(installed: str, db_version: Optional[str], alembic_revision: Optional[str], target: str) -> Check:
    """Installed version vs the one recorded in bw_metadata vs the revision actually stamped."""
    data = {"installed": installed, "database": db_version, "alembic_revision": alembic_revision, "target": target}

    if not target:
        return Check("versions", REFUSE, "No target version given", data)
    if not installed:
        return Check("versions", REFUSE, "The installed version could not be read", data)
    if not db_version:
        return Check("versions", REFUSE, "bw_metadata carries no version: this installation has never been initialised", data)
    if db_version != installed:
        # Either an upgrade is half-done or an older codebase is looking at a newer database.
        # Both are states a downgrade must not be layered on top of.
        return Check(
            "versions",
            REFUSE,
            f"The database says {db_version} and the installed code says {installed}: finish or roll back that migration first",
            data,
        )
    if target == installed:
        return Check("versions", REFUSE, f"{target} is the installed version, there is nothing to go back to", data)
    if not is_downgrade(installed, target):
        return Check("versions", REFUSE, f"{target} is not older than {installed}: this is an upgrade, not a downgrade", data)
    if not alembic_revision:
        # Without a stamp there is no way to tell which migrations actually ran, and the
        # downgrade path is chosen from exactly that.
        return Check("versions", RESTORE_ONLY, "No Alembic revision is stamped: where the schema actually stands cannot be proven", data)

    return Check("versions", IN_PLACE, f"{installed} (stamped {alembic_revision}) -> {target}", data)


def check_manifest(row: Optional[dict], installed: str, target: str, engine: str) -> Check:
    """What the compatibility manifest says about this exact version/engine pair."""
    data = {"row": row, "from": installed, "to": target, "engine": engine}

    if row is None:
        return Check(
            "manifest",
            RESTORE_ONLY,
            f"No manifest entry for {installed} -> {target} on {engine or 'an unidentified engine'}: restore from backup is the only proven path",
            data,
        )
    if row.get("mode") != "in_place_tested":
        return Check("manifest", RESTORE_ONLY, f"The manifest marks {installed} -> {target} on {engine} as {row.get('mode') or 'unclassified'}", data)
    if row.get("data_loss") == "certain":
        return Check("manifest", RESTORE_ONLY, f"The manifest records certain data loss for {installed} -> {target} on {engine}", data)
    if row.get("data_loss") not in ("none", "conditional"):
        return Check("manifest", RESTORE_ONLY, f"The manifest does not state the data loss for {installed} -> {target} on {engine}", data)

    return Check("manifest", IN_PLACE, f"The manifest marks {installed} -> {target} on {engine} as tested in place (data loss: {row['data_loss']})", data)


def check_engine(engine: str, server_version: Optional[str], masked_uri: str) -> Check:
    """Which database this is. Informational, except that an unidentified one is a refusal."""
    data = {"engine": engine, "server_version": server_version, "uri": masked_uri}
    if not engine:
        return Check("engine", REFUSE, "The database engine could not be identified from DATABASE_URI", data)
    return Check("engine", IN_PLACE, f"{engine} {server_version or '(server version unknown)'} at {masked_uri}", data)


def check_disk(database_bytes: Optional[int], free_bytes: Optional[int], backup_dir: str) -> Check:
    """Room for the mandatory backup, on the filesystem the backup is written to."""
    data = {"database_bytes": database_bytes, "free_bytes": free_bytes, "backup_dir": backup_dir}

    if free_bytes is None:
        return Check("disk", REFUSE, f"Free space on {backup_dir} could not be read", data)
    if database_bytes is None:
        return Check("disk", RESTORE_ONLY, f"The database size could not be measured; {_human(free_bytes)} free on {backup_dir}", data)
    # A compressed dump is smaller than the live database, so requiring the full size is the
    # conservative floor rather than an estimate of the archive.
    if free_bytes < database_bytes:
        return Check("disk", REFUSE, f"{_human(free_bytes)} free on {backup_dir} for a {_human(database_bytes)} database: the backup would not fit", data)
    if free_bytes < database_bytes * 2:
        return Check(
            "disk", RESTORE_ONLY, f"{_human(free_bytes)} free on {backup_dir} for a {_human(database_bytes)} database: tight, no room to keep two", data
        )

    return Check("disk", IN_PLACE, f"{_human(free_bytes)} free on {backup_dir} for a {_human(database_bytes)} database", data)


def check_backup(newest: Optional[Tuple[str, datetime]], now: datetime, max_age_hours: float = 24.0) -> Check:
    """Whether a restorable backup exists, and how old it is.

    The conception makes a backup mandatory whichever path is taken. What this cannot do is
    prove the archive restores: that costs a restore, which is a mutation. It reports the
    evidence it has and says so.
    """
    if not newest:
        return Check("backup", REFUSE, "No backup found: a downgrade without one has no way back", {"newest": None})

    name, taken = newest
    age_hours = (now - taken).total_seconds() / 3600
    data = {"newest": name, "taken": taken.isoformat(), "age_hours": round(age_hours, 2), "restorability": "unverified"}

    if age_hours < 0:
        # Either the clock moved or the stamp is wrong; both make "how old is the backup"
        # unanswerable, and the age is the only freshness evidence there is.
        return Check("backup", RESTORE_ONLY, f"The newest backup ({name}) is dated in the future: its age cannot be trusted", data)
    if age_hours > max_age_hours:
        return Check("backup", RESTORE_ONLY, f"The newest backup ({name}) is {age_hours:.1f} h old: take a fresh one before going back", data)

    return Check("backup", IN_PLACE, f"Newest backup {name}, {age_hours:.1f} h old (restorability not verified: that would need a restore)", data)


def check_irrepresentable(counts: Dict[str, Optional[int]], classes: Optional[Dict[str, str]] = None) -> Check:
    """1.7 data an older schema has nowhere to put, weighed against the manifest's classification.

    Without a manifest every populated table is a refusal to go in place -- there is nothing
    saying the loss is acceptable, so it is not assumed to be. With one, a table the manifest
    calls `conditional` is reported and survived rather than treated as a blocker: that is the
    whole point of PO-3's "the preflight compares live counts against the manifest's data_loss
    classification", and without it a single ban would pin every installation to restore_only.
    A table the manifest does not classify is treated as `certain`, which is the safe default.
    """
    classes = classes or {}
    data = {"counts": counts, "classes": {name: classes.get(name, "certain") for name in counts}}
    unknown = sorted(name for name, count in counts.items() if count is None)
    populated = {name: count for name, count in counts.items() if count}

    certain = {name: count for name, count in populated.items() if classes.get(name, "certain") != "conditional"}
    conditional = {name: count for name, count in populated.items() if classes.get(name) == "conditional"}

    if certain:
        summary = ", ".join(f"{name}={count}" for name, count in sorted(certain.items()))
        return Check("irrepresentable_data", RESTORE_ONLY, f"Data the target version cannot represent: {summary}", data)
    if unknown:
        return Check("irrepresentable_data", RESTORE_ONLY, f"Could not count {', '.join(unknown)}: what would be lost is unknown", data)
    if conditional:
        summary = ", ".join(f"{name}={count}" for name, count in sorted(conditional.items()))
        return Check("irrepresentable_data", IN_PLACE, f"Regenerable 1.7 data WILL be destroyed: {summary}", data)

    return Check("irrepresentable_data", IN_PLACE, "No 1.7-only rows found", data)


def check_plugins(plugins: List[dict]) -> Check:
    """Plugins whose declared API range excludes the target, and plugins with no manifest.

    Core plugins are exempt: they ship with the release, so the release manifest already covers
    them and a per-plugin contract would be the same statement written twice. Everything else --
    external, ui, pro -- carries its own contract or is treated as `restore_only`, which is the
    conception's rule for a plugin nobody has classified.
    """
    data = {"plugins": plugins}
    third_party = [plugin for plugin in plugins if plugin.get("type") != "core"]

    excluded = sorted(plugin["id"] for plugin in third_party if plugin.get("compatible") is False)
    if excluded:
        return Check("plugins", RESTORE_ONLY, f"Plugins that exclude the target version: {', '.join(excluded)}", data)

    unmanifested = sorted(plugin["id"] for plugin in third_party if not plugin.get("manifest"))
    if unmanifested:
        return Check("plugins", RESTORE_ONLY, f"Plugins with no downgrade manifest (unclassified is restore-only): {', '.join(unmanifested)}", data)

    return Check("plugins", IN_PLACE, f"{len(third_party)} external/pro plugin(s), all declaring a compatible range", data)


def check_writers(state: dict) -> Check:
    """Jobs in flight, and whether a reload is mid-flight.

    A downgrade started on top of a running job or an undelivered configuration push is the
    "discovered halfway through" case the conception refuses, so anything in flight is a
    refusal *now* -- it becomes a pass a minute later, once the queue is empty.
    """
    if not state.get("reachable"):
        return Check(
            "writers",
            RESTORE_ONLY,
            f"The job broker could not be reached ({state.get('error') or 'no broker configured'}): writers cannot be proven idle",
            state,
        )

    queued = state.get("queued")
    unacked = state.get("unacked")
    pending_acks = state.get("pending_acks") or 0

    if queued is None or unacked is None:
        return Check("writers", RESTORE_ONLY, "The broker answered but its queue depth could not be read: writers cannot be proven idle", state)
    if queued or unacked:
        return Check("writers", REFUSE, f"{queued} job(s) queued and {unacked} in flight: wait for the queue to drain", state)
    if state.get("reload_pending"):
        return Check("writers", REFUSE, "A reload of the instances is in flight", state)
    if pending_acks:
        # A deferred acknowledgement means material a job wrote has NOT reached the instances
        # yet. Downgrading now loses the change and clears nothing.
        return Check("writers", REFUSE, f"{pending_acks} change(s) written but not yet delivered to the instances", state)

    return Check("writers", IN_PLACE, "No jobs queued or in flight, no reload pending", state)


def _human(size: Optional[int]) -> str:
    if size is None:
        return "unknown"
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TiB"


# ── Collectors (read the installation; every one of them is read-only) ──────────────────────

# 1.7 tables an older schema has nowhere to put. Data, not code, so lot A/D can extend the set
# without touching the check. Names are module constants and never come from input: they are
# interpolated into SQL because a table name cannot be a bind parameter.
# `bw_certificates` and `bw_ui_user_webauthn_credentials` were added by lot A: an in-place
# downgrade destroys every centrally stored certificate and every registered passkey, and neither
# was being counted, so neither reached the operator before the mutation. Metrics are deliberately
# NOT here -- they are observability rather than configuration and are never empty, so counting
# them would pin every installation to restore_only forever (`not_counted_by_the_preflight` in
# the manifest records that as a decision rather than an oversight).
IRREPRESENTABLE_TABLES = ("bw_upstreams", "bw_redirects", "bw_workflows", "bw_bans", "bw_certificates", "bw_ui_user_webauthn_credentials")
# `bw_resources` also holds certificates, which 1.6.x does have somewhere to put, so it is
# counted per type rather than wholesale.
IRREPRESENTABLE_RESOURCE_TYPES = ("redirect", "upstream", "workflow")

CORE_PLUGINS_ROOT = Path(sep, "usr", "share", "bunkerweb", "core")
EXTERNAL_PLUGINS_ROOT = Path(sep, "etc", "bunkerweb", "plugins")
PRO_PLUGINS_ROOT = Path(sep, "etc", "bunkerweb", "pro", "plugins")


def installed_version() -> str:
    """The version of the code that is installed.

    `common_utils.get_version()` owns where that file lives; this only refuses to raise when it
    is missing, because a preflight has to be able to report "unknown" and let the verdict
    degrade rather than crash on a machine where the package layout is not there.
    """
    with suppress(BaseException):
        from common_utils import get_version  # type: ignore # noqa: PLC0415 - utils lands on sys.path via the bootstrap above

        return get_version().strip()
    return ""


def engine_name(database_uri: str) -> str:
    """`postgresql`, `mariadb`, `sqlite`... from a SQLAlchemy URI, driver suffix stripped."""
    with suppress(BaseException):
        return make_url(database_uri).drivername.split("+")[0]
    return ""


def read_metadata_version(db) -> Optional[str]:
    with suppress(BaseException):
        with db.sql_engine.connect() as conn:
            if sa.inspect(db.sql_engine).has_table("bw_metadata"):
                row = conn.execute(sa.text("SELECT version FROM bw_metadata WHERE id = 1")).first()
                return row[0] if row else None
    return None


def read_alembic_revision(db) -> Optional[str]:
    """The revision Alembic actually stamped, which is not necessarily the version recorded."""
    with suppress(BaseException):
        with db.sql_engine.connect() as conn:
            if sa.inspect(db.sql_engine).has_table("alembic_version"):
                row = conn.execute(sa.text("SELECT version_num FROM alembic_version")).first()
                return row[0] if row else None
    return None


def read_server_version(db) -> Optional[str]:
    with suppress(BaseException):
        info = db.sql_engine.dialect.server_version_info
        if info:
            return ".".join(str(part) for part in info)
    return None


def database_size(db, engine: str) -> Optional[int]:
    """On-disk size of the database, in bytes. None when it cannot be measured."""
    with suppress(BaseException):
        if engine == "sqlite":
            path = Path(make_url(db.database_uri).database or "")
            if path.is_file():
                # The WAL is part of the database until it is checkpointed.
                return path.stat().st_size + sum(sidecar.stat().st_size for sidecar in (Path(f"{path}-wal"), Path(f"{path}-shm")) if sidecar.is_file())
            return None
        with db.sql_engine.connect() as conn:
            if engine == "postgresql":
                return int(conn.execute(sa.text("SELECT pg_database_size(current_database())")).scalar_one())
            if engine in ("mysql", "mariadb"):
                return int(
                    conn.execute(
                        sa.text("SELECT COALESCE(SUM(data_length + index_length), 0) FROM information_schema.tables WHERE table_schema = DATABASE()")
                    ).scalar_one()
                )
    return None


def free_space(directory: Path) -> Optional[int]:
    """Free bytes on the filesystem holding `directory`, walking up to one that exists."""
    probe = directory
    for _ in range(len(probe.parts)):
        if probe.is_dir():
            with suppress(OSError):
                return disk_usage(probe.as_posix()).free
            return None
        probe = probe.parent
    return None


def count_irrepresentable(db) -> Dict[str, Optional[int]]:
    """Row counts for the 1.7-only data. A table that cannot be counted maps to None."""
    counts: Dict[str, Optional[int]] = {}
    try:
        inspector = sa.inspect(db.sql_engine)
        with db.sql_engine.connect() as conn:
            for table in IRREPRESENTABLE_TABLES:
                if not inspector.has_table(table):
                    # An absent table holds nothing; that is a real zero, not an unknown.
                    counts[table] = 0
                    continue
                counts[table] = int(conn.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one())  # noqa: S608 - fixed module constant
            if inspector.has_table("bw_resources"):
                row = conn.execute(
                    sa.text("SELECT COUNT(*) FROM bw_resources WHERE type IN :types").bindparams(sa.bindparam("types", expanding=True)),
                    {"types": list(IRREPRESENTABLE_RESOURCE_TYPES)},
                ).scalar_one()
                counts["bw_resources"] = int(row)
            else:
                counts["bw_resources"] = 0
            if inspector.has_table("bw_resource_groups"):
                # 17 core groups ship as seeds, so a wholesale count would pin every installation
                # to `restore_only` forever. `plugin_id` is the product's own discriminator between
                # a seeded group and a hand-built one (`db_methods/initialization.py`'s
                # `managed_rg_ids`, and the seeder always sets it), and only the operator paths --
                # the API and UI routers -- can leave it NULL. So this counts what a downgrade
                # really destroys and nothing the next upgrade re-seeds.
                counts["bw_resource_groups"] = int(conn.execute(sa.text("SELECT COUNT(*) FROM bw_resource_groups WHERE plugin_id IS NULL")).scalar_one())
            else:
                counts["bw_resource_groups"] = 0
    except BaseException as e:
        LOGGER.debug(f"Could not count the 1.7-only rows: {e}")
        for table in IRREPRESENTABLE_TABLES + ("bw_resources", "bw_resource_groups"):
            counts.setdefault(table, None)
    return counts


def scan_plugins(
    target: str,
    core_root: Path = CORE_PLUGINS_ROOT,
    external_root: Path = EXTERNAL_PLUGINS_ROOT,
    pro_root: Path = PRO_PLUGINS_ROOT,
) -> List[dict]:
    """Every installed plugin, with whatever downgrade contract it declares.

    The contract lives under ``extensions.downgrade`` in plugin.json: ``{"min_version": ...,
    "max_version": ...}``. A plugin with no such block gets ``manifest: False``, which
    :func:`check_plugins` reads as restore-only.
    """
    plugins: List[dict] = []
    for plugin_type, root in (("core", core_root), ("external", external_root), ("pro", pro_root)):
        if not root.is_dir():
            continue
        for manifest_file in sorted(root.glob("*/plugin.json")):
            entry = {"id": manifest_file.parent.name, "type": plugin_type, "manifest": False, "compatible": None}
            with suppress(OSError, JSONDecodeError, UnicodeDecodeError):
                declared = loads(manifest_file.read_text(encoding="utf-8"))
                entry["id"] = declared.get("id") or entry["id"]
                contract = (declared.get("extensions") or {}).get("downgrade")
                if isinstance(contract, dict):
                    entry["manifest"] = True
                    entry["compatible"] = _in_range(target, contract.get("min_version"), contract.get("max_version"))
            plugins.append(entry)
    return plugins


def _in_range(target: str, minimum: Optional[str], maximum: Optional[str]) -> bool:
    key = version_key(target)
    if minimum and key < version_key(minimum):
        return False
    if maximum and key > version_key(maximum):
        return False
    return True


# ── The job broker: what is in flight, and the writer hold ──────────────────────────────────

# The two queues declared in src/worker/app.py. With the Redis transport Kombu stores each
# queue as a list under its own name, so their depth is one LLEN away and needs no Celery --
# which is not installed in the scheduler image, where bwcli runs.
BROKER_QUEUES = ("default", "heavy")
# Kombu's own bookkeeping for messages delivered but not yet acknowledged. An implementation
# detail of the transport, so its absence is reported as "unknown", never as "nothing running".
UNACKED_KEY = "unacked"
# Mirrors RELOAD_LOCK_KEY in src/worker/tasks.py, which cannot be imported here: that module
# imports Celery.
RELOAD_LOCK_KEY = "bw:reload_pending"

from jobs import RELOAD_ACK_PENDING_KEY  # type: ignore # noqa: E402 - after the sys.path bootstrap above

# One key, in the broker every writer already shares. A file would not do: the API that has to
# honour the hold runs in another container.
HOLD_KEY = "bw:downgrade_hold"
# Bounded by construction. A holder that dies -- killed terminal, severed SSH -- releases the
# system on its own instead of leaving it frozen; a live holder refreshes well inside this.
DEFAULT_HOLD_TTL = 900

# Delete only our own hold. Without the token compare, a holder whose TTL expired while it was
# blocked would come back and delete the hold a *second* operator legitimately took.
_RELEASE_IF_MINE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""
_REFRESH_IF_MINE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""


# The same default `src/worker/app.py:17` and `src/worker/tasks.py:382` use. Without it the Linux
# packages could never quiesce at all: `src/linux/scripts/bunkerweb-scheduler.sh` sets API_URL but
# never CELERY_BROKER_URL, and `bwcli` runs from a plain shell, so an empty default made
# `check_writers` degrade to restore_only on every Linux install, forever.
DEFAULT_BROKER_URL = "redis://127.0.0.1:6379/0"

# bwcli's own convention comes first (`src/common/cli/CLI.py:62,257`), then the one the scheduler
# and the Linux unit export. The fallback is the Linux socket; Docker sets API_URL in the
# environment of the container bwcli runs in.
DEFAULT_API_URL = "http://127.0.0.1:8888"


def broker_url() -> str:
    return getenv("CELERY_BROKER_URL", "").strip() or DEFAULT_BROKER_URL


def api_url() -> str:
    return (getenv("BWCLI_API_URL", "").strip() or getenv("API_URL", "").strip() or DEFAULT_API_URL).rstrip("/")


def broker_client(url: str = ""):
    """Redis client for the broker, with timeouts.

    Never `from_url` bare: the failures that matter here (a fenced node, a dropped security
    group) black-hole the connection rather than refusing it, and redis-py defaults to no
    socket timeout, so a bare client makes a *read-only* preflight hang forever.
    """
    import redis  # noqa: PLC0415 - not a scheduler dependency, absence must stay non-fatal

    return redis.Redis.from_url(url or broker_url(), socket_timeout=2, socket_connect_timeout=2)


def broker_state(client=None, url: str = "") -> dict:
    """Queue depth, in-flight count and reload state. Never raises."""
    url = url or broker_url()
    state: Dict[str, Any] = {"reachable": False, "queued": None, "unacked": None, "reload_pending": None, "pending_acks": None, "error": ""}

    if client is None and not url:
        state["error"] = "no broker URL to connect to"
        return state

    try:
        client = client if client is not None else broker_client(url)
        client.ping()
        state["reachable"] = True
        state["queued"] = sum(int(client.llen(queue) or 0) for queue in BROKER_QUEUES)
        state["unacked"] = int(client.hlen(UNACKED_KEY) or 0)
        state["reload_pending"] = bool(client.exists(RELOAD_LOCK_KEY))
        state["pending_acks"] = int(client.scard(RELOAD_ACK_PENDING_KEY) or 0)
    except BaseException as e:
        # The broker URL carries credentials and drivers echo it back inside their errors.
        state["error"] = scrub_db_secret(str(e), url) if url else str(e)
        state["reachable"] = False
    return state


def acquire_hold(client, target: str, ttl: int = DEFAULT_HOLD_TTL, token: str = "") -> Tuple[str, Optional[dict]]:
    """Take the downgrade hold. Returns (handle, existing) -- an empty handle means refused.

    `SET NX` is the whole concurrency story: a second attempt sees the key and refuses instead
    of interleaving with the first. The handle returned is the stored value verbatim, and it is
    what :func:`refresh_hold` and :func:`release_hold` compare against -- byte equality, so a
    holder cannot act on a hold that expired underneath it and was retaken by someone else.
    """
    payload = dumps(
        {"token": token or uuid4().hex, "target": target, "started_at": datetime.now().astimezone().isoformat()},
        sort_keys=True,
    )
    if client.set(HOLD_KEY, payload, nx=True, ex=ttl):
        return payload, None
    return "", hold_status(client)


def refresh_hold(client, handle: str, ttl: int = DEFAULT_HOLD_TTL) -> bool:
    """Push the TTL out, but only while the hold is still ours."""
    if not handle:
        return False
    return bool(client.eval(_REFRESH_IF_MINE, 1, HOLD_KEY, handle, ttl))


def release_hold(client, handle: str, force: bool = False) -> bool:
    """Give the system back. `force` releases a hold whose holder is gone."""
    if force:
        return bool(client.delete(HOLD_KEY))
    if not handle:
        return False
    return bool(client.eval(_RELEASE_IF_MINE, 1, HOLD_KEY, handle))


def hold_ttl(client) -> int:
    """Seconds left on the hold. -2 when there is none, -1 when it carries no expiry."""
    with suppress(BaseException):
        return int(client.ttl(HOLD_KEY))
    return -2


def hold_status(client) -> Optional[dict]:
    """Who holds the downgrade hold, and since when. None when nobody does."""
    raw = client.get(HOLD_KEY)
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    with suppress(JSONDecodeError, TypeError):
        parsed = loads(raw)
        if isinstance(parsed, dict):
            return parsed
    return {"raw": raw}


def hold_observed_by_api(timeout: float = 15.0, poll: float = 1.0, client=None, sleeper=sleep, clock=monotonic) -> Tuple[bool, str]:
    """Does the API actually report the fleet read-only? Returns (observed, reason if not).

    The hold key is inert on its own: what stops the writers is `GET /system/readonly`, which
    the scheduler, the autoconf, the UI and the API itself all consult. That endpoint fails
    OPEN on a broker it cannot read -- a blip must not freeze a fleet -- so the refusal has to
    live here instead, and this is it.

    `BaseApiClient.readonly` is deliberately not used: it answers True when the API is
    *unreachable*, which is exactly the case that must refuse.
    """
    if client is None:
        from base_api_client import BaseApiClient  # type: ignore # noqa: PLC0415 - utils lands on sys.path via the bootstrap above

        client = BaseApiClient(api_url(), getenv("API_TOKEN", ""), logger_name="DOWNGRADE")

    deadline = clock() + timeout
    reason = ""
    while True:
        try:
            reason = "" if bool(client._get("/system/readonly").get("readonly")) else "the API reports the fleet is still writable"
        except BaseException as e:
            reason = f"the API could not be asked: {e}"
        if not reason or clock() >= deadline:
            return not reason, reason
        sleeper(poll)


def drain(client, timeout: float = 120.0, poll: float = 2.0, sleeper=sleep, clock=monotonic) -> Tuple[bool, dict]:
    """Wait for the writers to go idle. Returns (drained, last observed state).

    Bounded on purpose: a drain that waits forever is a freeze, and the caller has to be able
    to give the system back rather than sit on it.
    """
    deadline = clock() + timeout
    state = broker_state(client=client)
    while True:
        # `pending_acks` belongs here for the same reason `check_writers` refuses on it: a deferred
        # acknowledgement is material a job WROTE that has not reached the instances yet. Calling
        # the fleet idle with acks outstanding is exactly the "discovered halfway through" case.
        idle = (
            bool(state.get("reachable"))
            and not state.get("queued")
            and not state.get("unacked")
            and not state.get("reload_pending")
            and not state.get("pending_acks")
        )
        if idle or clock() >= deadline:
            return idle, state
        sleeper(poll)
        state = broker_state(client=client)


# ── Connecting without writing ──────────────────────────────────────────────────────────────

# Mirrors the map inside `Database.__init__`'s `validate_and_update_db_string`, which is a closure
# and cannot be imported. It matters: `create_engine("postgresql://...")` picks psycopg2, which is
# not installed -- psycopg (v3) is.
RECOMMENDED_DRIVERS = {"postgresql": "psycopg", "mysql": "pymysql", "mariadb": "pymysql", "oracle": "oracledb"}


class ReadOnlyConnection:
    """The three attributes the preflight reads off a `Database`, without its write probe.

    `Database.__init__` is not usable here. Its connection check issues
    `CREATE TABLE IF NOT EXISTS test_<hex>` + `DROP TABLE` on every construction where
    `self.readonly` is False (`src/common/db/Database.py:373-377`), which it is unless
    DATABASE_URI_READONLY is set -- there is no kwarg to turn it off. On MariaDB/MySQL that DDL
    commits implicitly server-side and cannot be rolled back, and on SQLite the same construction
    creates the database file when it is missing. A command that reports whether it is safe to
    downgrade must not be the thing that writes to the database it is judging.

    What this issues instead: SELECTs and inspector reads, nothing else. The one caveat worth
    stating rather than hiding is SQLite's own bookkeeping -- opening a WAL database touches its
    `-wal`/`-shm` sidecars, as any read of one does, including `sqlite3 .dump`.
    """

    def __init__(self, database_uri: str, database_uri_readonly: str = ""):
        self.database_uri = database_uri
        self.database_uri_readonly = database_uri_readonly
        # NullPool: one short-lived command, and a pool would hold connections open against a
        # database an operator is about to take down.
        self.sql_engine = sa.create_engine(database_uri or database_uri_readonly, poolclass=NullPool)

    def close(self) -> None:
        self.sql_engine.dispose(close=True)


def with_recommended_driver(uri: str) -> str:
    """`postgresql://` -> `postgresql+psycopg://`, leaving an explicit driver alone."""
    if not uri:
        return uri
    with suppress(BaseException):
        url = make_url(uri)
        driver = RECOMMENDED_DRIVERS.get(url.drivername)
        if driver and "+" not in url.drivername:
            return url.set(drivername=f"{url.drivername}+{driver}").render_as_string(hide_password=False)
    return uri


def open_read_only(uri: str = "", readonly_uri: str = "", prefer_replica: bool = True) -> ReadOnlyConnection:
    """Open the configured database for reading.

    A read-only replica wins when one is configured: it is the correct target for a question
    about the database, and it cannot be written to even by accident. `prefer_replica=False`
    pins the connection to the primary instead, which is what a gate in front of a mutation has
    to read -- see `execute_downgrade`.

    Raises `FileNotFoundError` for a SQLite database that does not exist rather than creating it
    -- "there is no database" is an answer the preflight must report, not a file it must make.
    """
    readonly_uri = with_recommended_driver(readonly_uri or (getenv("DATABASE_URI_READONLY", "").strip() if prefer_replica else ""))
    # `bwcli` hands the plugin an already-resolved DATABASE_URI (CLI.py sets it from the
    # Database it built), so this default is only ever reached by a direct invocation.
    uri = with_recommended_driver(uri or getenv("DATABASE_URI", "").strip() or readonly_uri or SQLITE_DEFAULT_URI)

    # Parsing is what may fail here, not the check -- keep the raise OUTSIDE the suppress, or the
    # refusal swallows itself and the caller gets an engine pointed at nothing.
    sqlite_path = ""
    with suppress(BaseException):
        url = make_url(readonly_uri or uri)
        if url.drivername.split("+")[0] == "sqlite" and url.database:
            sqlite_path = url.database
    if sqlite_path and not Path(sqlite_path).is_file():
        raise FileNotFoundError(f"SQLite database {sqlite_path} does not exist")

    return ReadOnlyConnection("" if readonly_uri else uri, readonly_uri)


# ── The preflight itself ────────────────────────────────────────────────────────────────────


def preflight(target: str, db=None, backup_dir: Optional[Path] = None, now: Optional[datetime] = None, client=None) -> dict:
    """Answer "can this installation go back to `target`?".

    Issues no DDL and no INSERT/UPDATE/DELETE, creates no database, and never writes to the
    broker -- see :class:`ReadOnlyConnection` for the one caveat (SQLite's own `-wal`/`-shm`
    bookkeeping, which any read of a WAL database performs).

    Every check is asked, even after one has already refused: an operator who is going to be
    told no deserves the whole list of reasons, not the first one.
    """
    from backup import BACKUP_DIR  # noqa: PLC0415 - sibling module, imported here to keep this one importable on its own

    now = now or datetime.now().astimezone()
    backup_dir = backup_dir or BACKUP_DIR

    opened = None
    if db is None:
        db = opened = open_read_only()

    try:
        return _preflight(target, db, backup_dir, now, client)
    finally:
        if opened is not None:
            opened.close()


def _preflight(target: str, db, backup_dir: Path, now: datetime, client) -> dict:
    """The checks themselves, with the connection already open and owned by the caller."""
    from backup import backup_time, sorted_backups  # noqa: PLC0415 - sibling module, see preflight()

    installed = installed_version()
    engine = engine_name(db.database_uri or db.database_uri_readonly)
    db_version = read_metadata_version(db)
    revision = read_alembic_revision(db)
    manifest = load_manifest()

    backups = sorted_backups(backup_dir) if backup_dir.is_dir() else []
    newest = (backups[-1].name, backup_time(backups[-1])) if backups else None

    checks = [
        check_versions(installed, db_version, revision, target),
        check_engine(engine, read_server_version(db), mask_db_uri(db.database_uri or db.database_uri_readonly)),
        check_manifest(manifest_row(manifest, installed, target, engine), installed, target, engine),
        check_disk(database_size(db, engine), free_space(backup_dir), backup_dir.as_posix()),
        check_backup(newest, now),
        check_irrepresentable(count_irrepresentable(db), loss_classes(manifest)),
        check_plugins(scan_plugins(target)),
        check_writers(broker_state(client=client)),
    ]

    return {
        "target": target,
        "installed": installed,
        "engine": engine,
        "generated_at": now.isoformat(),
        "verdict": worst(checks),
        "manifest_row": manifest_row(manifest, installed, target, engine),
        "silent_losses": silent_losses(manifest),
        "checks": [{"name": c.name, "verdict": c.verdict, "detail": c.detail, "data": c.data} for c in checks],
    }


VERDICT_MARK = {IN_PLACE: "✅", RESTORE_ONLY: "⚠️", REFUSE: "❌"}

VERDICT_MEANING = {
    IN_PLACE: "every check passed: an in-place downgrade is possible (a backup is still mandatory)",
    RESTORE_ONLY: "an in-place downgrade is not proven safe; restore from a backup instead",
    REFUSE: "this downgrade is refused -- fix what is marked ❌ and run the preflight again",
}


def render_report(result: dict) -> str:
    """The operator-facing report. Contains no secrets: the only URI in it is masked."""
    lines = [
        "",
        f"Downgrade preflight: {result['installed'] or 'unknown'} -> {result['target']}",
        f"Generated {result['generated_at']} (read-only: no schema or data was modified)",
        "",
    ]
    width = max((len(check["name"]) for check in result["checks"]), default=0)
    for check in result["checks"]:
        lines.append(f"  {VERDICT_MARK.get(check['verdict'], '?')} {check['name']:<{width}}  {check['detail']}")
    # Not under a refusal: "destroyed all the same" is a statement about a downgrade that is going
    # to happen, and a refused one is not.
    if result.get("silent_losses") and result.get("verdict") != REFUSE:
        lines.extend(("", "  Not counted by any check above, and destroyed all the same:"))
        lines.extend(f"    - {line}" for line in result["silent_losses"])
    lines.extend(("", f"VERDICT: {result['verdict']} -- {VERDICT_MEANING.get(result['verdict'], '')}", ""))
    return "\n".join(lines)


# Exit codes, so a script can branch on the verdict. The bwcli wrapper collapses every
# non-zero code to "failed", which is the right signal for the two verdicts that are not a go.
EXIT_CODES = {IN_PLACE: 0, RESTORE_ONLY: 2, REFUSE: 3}


# ── Lot D: the in-place downgrade itself ────────────────────────────────────────────────────

# Where the migration scripts live in an installed image or package. `src/scheduler/entrypoint.sh`
# hard-codes the same path.
ALEMBIC_DIR = Path(getenv("BWCLI_ALEMBIC_DIR") or join(sep, "usr", "share", "bunkerweb", "db", "alembic"))

# End states, in the order of how much is left for a human to do.
DOWNGRADED = "downgraded"
RESTORED = "restored_to_pre_downgrade"
MANUAL = "manual_recovery_required"
REFUSED = "refused"

# alembic.ini ships with `version_locations = versions`, and env.py's own `set_main_option` lands
# after ScriptDirectory is already built -- which is why `src/scheduler/entrypoint.sh:105` sed-patches
# the ini before running alembic. bwcli cannot do that: the image copies /usr/share/bunkerweb with
# mode 550 and bwcli does not run as root. Building the Config in memory reaches the same
# configuration and writes nothing. A subprocess, so that importing `model` and the whole migration
# chain cannot leave anything behind in the bwcli process, and so a hard abort is an exit code.
_ALEMBIC_DRIVER = """
import sys
from alembic import command
from alembic.config import Config

alembic_dir, engine, revision = sys.argv[1:4]
cfg = Config(alembic_dir + "/alembic.ini")
cfg.set_main_option("script_location", alembic_dir)
cfg.set_main_option("version_locations", alembic_dir + "/" + engine + "_versions")
command.downgrade(cfg, revision)
"""


def run_alembic_downgrade(engine: str, uri: str, revision: str, alembic_dir: Optional[Path] = None, timeout: float = 1800.0) -> Tuple[int, str]:
    """`alembic downgrade <revision>`, the way the scheduler entrypoint runs alembic. Never raises."""
    from os import environ  # noqa: PLC0415 - only this function needs the whole environment
    from subprocess import run as run_process  # noqa: PLC0415 - not needed by the read-only half
    from sys import executable  # noqa: PLC0415 - same

    directory = Path(alembic_dir or ALEMBIC_DIR)
    env = environ.copy()
    env["DATABASE_URI"] = uri
    # env.py does `from model import Base`, and model.py lives in the directory holding `alembic/`.
    # The scheduler image happens to put it on PYTHONPATH already; saying so here rather than
    # inheriting it means this works from any process that can reach the migration scripts.
    env["PYTHONPATH"] = ":".join(p for p in (directory.parent.as_posix(), env.get("PYTHONPATH", "")) if p)
    try:
        proc = run_process(
            [executable, "-c", _ALEMBIC_DRIVER, directory.as_posix(), engine, revision],
            cwd=directory.as_posix(),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except BaseException as e:
        return 1, scrub_db_secret(f"{type(e).__name__}: {e}", uri)
    return proc.returncode, scrub_db_secret((proc.stdout or "") + (proc.stderr or ""), uri)


def table_counts(db, tables) -> Dict[str, Optional[int]]:
    """Row count per table. `None` means the table is not there; "unreadable" that it would not answer.

    This is the live half of PO-3's fingerprint: taken before the mutation and again after it, so
    "nothing was lost" is a measurement in the operator's own database rather than a claim
    inherited from the manifest.
    """
    counts: Dict[str, Optional[int]] = {}
    present = set()
    with suppress(BaseException):
        present = set(sa.inspect(db.sql_engine).get_table_names())
    # The connect is under the same suppress as the inspection, and for the same reason: this is a
    # cosmetic measurement taken once before the migration and once after it has already committed
    # and been verified. A connection that cannot be opened here has to cost the operator the
    # fingerprint, never the report -- an exception escaping the post-migration call would land at
    # the CLI as a bare error with no `end_state` at all, for a downgrade that in fact succeeded,
    # and the natural response to that is to restore the backup and undo it.
    with suppress(BaseException), db.sql_engine.connect() as conn:
        for name in sorted(tables):
            if name not in present:
                counts[name] = None
                continue
            try:
                counts[name] = int(conn.execute(sa.text(f"SELECT COUNT(*) FROM {name}")).scalar() or 0)  # noqa: S608 - module constant, never input
            except BaseException:
                counts[name] = "unreadable"  # type: ignore[assignment]
    return counts


def _step(result: dict, name: str, ok: bool, detail: str, **extra) -> bool:
    result["steps"].append({"step": name, "ok": ok, "detail": detail} | extra)
    if not ok:
        LOGGER.error(detail)
    else:
        LOGGER.info(detail)
    return ok


def execute_downgrade(
    target: str,
    client=None,
    confirmed: bool = False,
    db=None,
    alembic_dir: Optional[Path] = None,
    backup_dir: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> dict:
    """Take this installation back to `target` in place. The only mutating entry point here.

    Everything before the `alembic downgrade` call is a gate, and every gate refuses rather than
    warns. In order: the operator confirmed; a quiescence hold is held *for this target*; the
    read-only preflight -- re-run here rather than trusted from an earlier shell -- returns
    `in_place_possible`; the manifest marks this exact (from, to, engine) `in_place_tested` and
    names the revision to land on. Then, and only then, a backup is taken of the database as it
    stands, and the migration runs.

    Any failure after that point restores that backup. The contract the conception asks for is
    that every outcome leaves a startable installation, so the result always carries an
    `end_state`: `downgraded`, `restored_to_pre_downgrade`, or -- if even the restore failed --
    `manual_recovery_required`, with the backup file named so a human can finish by hand.
    """
    from backup import BACKUP_DIR, backup_database, restore_database  # noqa: PLC0415 - sibling module, see preflight()

    now = now or datetime.now().astimezone()
    result: dict = {"target": target, "generated_at": now.isoformat(), "end_state": REFUSED, "steps": [], "safety_backup": None}

    if not confirmed:
        _step(result, "confirmation", False, "Refusing to downgrade without an explicit confirmation")
        return result

    # 1. the hold. `quiesce` is a separate, foreground command on purpose: this one refuses to run
    #    unless that one is already holding the writers still, for this same target.
    try:
        client = client if client is not None else broker_client()
        held = hold_status(client)
    except BaseException as e:
        # `broker_client()` is inside the try on purpose: it imports redis, which is not a
        # scheduler dependency, and `from_url` parses. Either can raise, and a gate that raises
        # instead of refusing is a gate that reports "error" where it means "no".
        _step(result, "hold", False, f"The job broker could not be asked who holds the downgrade hold: {e}")
        return result
    if not held:
        _step(result, "hold", False, f"No downgrade hold is in place: run `bwcli plugin backup quiesce {target}` in another shell first")
        return result
    if (held.get("target") or "") != target:
        _step(
            result, "hold", False, f"The downgrade hold in place is for {held.get('target')!r}, not {target!r}: refusing to downgrade under someone else's hold"
        )
        return result
    _step(result, "hold", True, f"Downgrade hold held for {target} since {held.get('started_at')}")

    # 2. the preflight, re-run here. An operator may have run it an hour ago, or not at all.
    #
    #    On the PRIMARY, explicitly. Left to itself `preflight()` opens `open_read_only()`, which
    #    prefers `DATABASE_URI_READONLY` -- the right target for a question about the database, and
    #    the wrong one for the gate in front of a migration that writes the primary. A replica that
    #    lags, or has stopped replicating, answers "no 1.7-only rows" for rows that are on the
    #    primary and that the downgrade is about to destroy, and nothing afterwards notices: the
    #    run ends `downgraded`, exit 0. The check has to read the database the mutation will write.
    #    The same connection decides `check_manifest`'s engine, so a primary/replica engine
    #    mismatch stops gating this on the wrong engine's manifest row too.
    primary = None
    try:
        primary = open_read_only(uri=getattr(db, "database_uri", "") or getenv("DATABASE_URI", "").strip(), prefer_replica=False)
        report = preflight(target, db=primary, client=client, now=now)
    except BaseException as e:
        # It raises on a database it cannot even open -- a missing SQLite file, for one, which it
        # refuses to create. "I could not tell" has to come out as a refusal, not a traceback.
        _step(result, "preflight", False, f"The preflight could not run, so nothing about this downgrade is proven: {e}")
        return result
    finally:
        if primary is not None:
            primary.close()
    result["preflight"] = report
    if report["verdict"] != IN_PLACE:
        _step(result, "preflight", False, f"The preflight says {report['verdict']}, not {IN_PLACE}:\n{render_report(report)}")
        return result
    _step(result, "preflight", True, f"The preflight says {IN_PLACE} for {report['installed']} -> {target} on {report['engine']}")

    # 3. the manifest, asserted again rather than inherited. check_manifest already refused
    #    anything but `in_place_tested`, and this says so a second time next to the mutation --
    #    the brief makes it the hard gate, and a gate that only exists three functions away is
    #    one refactor from not existing.
    row = report.get("manifest_row") or {}
    revision = target_revision(row)
    if row.get("mode") != "in_place_tested":
        _step(
            result,
            "manifest",
            False,
            f"The manifest does not mark {report['installed']} -> {target} on {report['engine']} as in_place_tested: {row.get('reason') or row.get('mode') or 'no entry'}",
        )
        return result
    if not revision:
        _step(result, "manifest", False, "The manifest marks this pair in_place_tested but names no alembic.to_revision to land on")
        return result
    _step(result, "manifest", True, f"The manifest marks this pair in_place_tested; landing on Alembic revision {revision}", revision=revision)

    # 4. the backup this operation falls back to. Taken NOW, under the hold, with the database
    #    still fully 1.7 -- an older backup would restore a state that predates whatever happened
    #    since, and the preflight cannot tell whether the newest one predates the upgrade.
    backup_dir = backup_dir or BACKUP_DIR
    try:
        db, safety_backup = backup_database(now, db=db, backup_dir=backup_dir)
    except BaseException as e:
        _step(result, "backup", False, f"Could not take the pre-downgrade backup, refusing to mutate anything: {e}")
        return result
    result["safety_backup"] = getattr(safety_backup, "as_posix", lambda: str(safety_backup))()
    _step(result, "backup", True, f"Pre-downgrade backup taken: {result['safety_backup']}")

    engine = engine_name(db.database_uri)
    # Where the database stands right now. This is what "the fallback worked" is measured against
    # further down -- `restore_database` finishes with a `checked_changes` call that is 1.7 code
    # running against a freshly-restored schema (lot B §3), so "it raised" and "it did not restore"
    # are genuinely different things and only the second one is a manual-recovery situation.
    stamp_before = read_alembic_revision(db)
    version_before = read_metadata_version(db)
    baseline = sorted(loss_classes(load_manifest())) or list(IRREPRESENTABLE_TABLES)
    before = table_counts(db, set(baseline) | {"bw_metadata", "bw_plugins", "bw_services", "bw_settings", "bw_custom_configs", "bw_instances"})
    result["fingerprint_before"] = before

    # 5. the mutation.
    code, log = run_alembic_downgrade(engine, db.database_uri, revision, alembic_dir=alembic_dir)
    result["alembic_log"] = log[-4000:]
    failure = "" if code == 0 else f"`alembic downgrade {revision}` failed with exit code {code}"

    # 6. and the proof that it landed where it said it would. A downgrade that reports success and
    #    leaves the stamp or the recorded version somewhere else is the half-finished state the
    #    preflight refuses to start from, so it is treated exactly like an outright failure.
    if not failure:
        with suppress(BaseException):
            stamped = read_alembic_revision(db)
            recorded = read_metadata_version(db)
            result["alembic_version_after"] = stamped
            result["bw_metadata_version_after"] = recorded
            if stamped != revision:
                failure = f"The downgrade reported success but the database is stamped {stamped!r}, not {revision!r}"
            elif recorded != target:
                failure = f"The downgrade reported success but bw_metadata records {recorded!r}, not {target!r}"

    if failure:
        _step(result, "downgrade", False, f"{failure}\n{log[-2000:]}")
        raised = ""
        try:
            restore_database(Path(result["safety_backup"]), db)
        except BaseException as e:
            raised = f"{type(e).__name__}: {e}"

        # Asked, not assumed -- and asked with two questions, not one.
        #
        # The stamp alone is not enough. On MariaDB/MySQL the measured partial failure leaves
        # `alembic_version` at the 1.7 head (unchanged) while `bw_metadata.version` has already
        # committed to `1.6.15~rc1` under non-transactional DDL, so a stamp-only comparison calls
        # that hybrid schema "restored" before any restore has run. `bw_metadata.version` is the
        # discriminator, so both have to come back.
        #
        # And both reads have to have SUCCEEDED. `read_alembic_revision` swallows its errors and
        # answers None, so on a database the restore emptied, `None == None` would report success
        # for a database that no longer has the table to read.
        landed = False
        with suppress(BaseException):
            stamp_after, version_after = read_alembic_revision(db), read_metadata_version(db)
            landed = bool(stamp_before) and stamp_after == stamp_before and version_after == version_before
        if not landed:
            result["end_state"] = MANUAL
            _step(
                result,
                "fallback",
                False,
                f"The fallback restore did not put the database back{f' ({raised})' if raised else ''}. It is half-downgraded and this cannot be fixed from here. "
                f"Restore {result['safety_backup']} by hand -- `bwcli plugin backup restore {result['safety_backup']}` -- before starting anything.",
            )
            return result
        result["end_state"] = RESTORED
        if raised:
            LOGGER.warning(f"The restore reported an error but the database is back at {stamp_before} / {version_before}: {raised}")
        _step(
            result,
            "fallback",
            True,
            f"Restored {result['safety_backup']}: the installation is back where it started, still on {report['installed']}. "
            "Start the 1.7 images again; then use the restore path (a backup taken before the upgrade) if you still need to go back.",
        )
        return result

    # `end_state` first: the migration is done and verified by this point, so the outcome is
    # already decided and the fingerprint below is only a measurement of it.
    result["end_state"] = DOWNGRADED
    result["fingerprint_after"] = table_counts(db, before.keys())
    _step(
        result,
        "downgrade",
        True,
        f"Downgraded to {target} (Alembic {revision}). Release the quiescence hold, then start the {target} images or packages.",
    )
    return result


def render_execute_report(result: dict) -> str:
    """The operator-facing summary of an execution attempt. No secrets: the log is scrubbed."""
    lines = ["", f"Downgrade to {result['target']} -- {result['end_state']}", ""]
    for step in result["steps"]:
        lines.append(f"  {'✅' if step['ok'] else '❌'} {step['step']:<13}  {step['detail']}")
    if result.get("safety_backup"):
        lines.append(f"\n  Pre-downgrade backup: {result['safety_backup']}")
    before, after = result.get("fingerprint_before"), result.get("fingerprint_after")
    if before and after:
        drift = {name: (before[name], after.get(name)) for name in before if before[name] != after.get(name)}
        lines.append(
            f"  Row fingerprint: {len(before)} tables measured, {len(drift)} changed{': ' + ', '.join(f'{k} {v[0]}->{v[1]}' for k, v in sorted(drift.items())) if drift else ''}"
        )
    lines.append("")
    return "\n".join(lines)


EXECUTE_EXIT_CODES = {DOWNGRADED: 0, RESTORED: 2, REFUSED: 3, MANUAL: 4}
