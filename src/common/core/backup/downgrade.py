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

Nothing here performs a downgrade. Lot D builds that.
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
MANIFEST_PATH = Path(getenv("DOWNGRADE_MANIFEST", join(sep, "usr", "share", "bunkerweb", "downgrade-manifest.json")))


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


def check_irrepresentable(counts: Dict[str, Optional[int]]) -> Check:
    """1.7 data an older schema has nowhere to put."""
    data = {"counts": counts}
    unknown = sorted(name for name, count in counts.items() if count is None)
    populated = {name: count for name, count in counts.items() if count}

    if populated:
        summary = ", ".join(f"{name}={count}" for name, count in sorted(populated.items()))
        return Check("irrepresentable_data", RESTORE_ONLY, f"Data the target version cannot represent: {summary}", data)
    if unknown:
        return Check("irrepresentable_data", RESTORE_ONLY, f"Could not count {', '.join(unknown)}: what would be lost is unknown", data)

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
IRREPRESENTABLE_TABLES = ("bw_upstreams", "bw_redirects", "bw_workflows", "bw_bans")
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
    except BaseException as e:
        LOGGER.debug(f"Could not count the 1.7-only rows: {e}")
        for table in IRREPRESENTABLE_TABLES + ("bw_resources",):
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


def open_read_only(uri: str = "", readonly_uri: str = "") -> ReadOnlyConnection:
    """Open the configured database for reading.

    A read-only replica wins when one is configured: it is the correct target for a question
    about the database, and it cannot be written to even by accident.

    Raises `FileNotFoundError` for a SQLite database that does not exist rather than creating it
    -- "there is no database" is an answer the preflight must report, not a file it must make.
    """
    readonly_uri = with_recommended_driver(readonly_uri or getenv("DATABASE_URI_READONLY", "").strip())
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
        check_irrepresentable(count_irrepresentable(db)),
        check_plugins(scan_plugins(target)),
        check_writers(broker_state(client=client)),
    ]

    return {
        "target": target,
        "installed": installed,
        "engine": engine,
        "generated_at": now.isoformat(),
        "verdict": worst(checks),
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
    lines.extend(("", f"VERDICT: {result['verdict']} -- {VERDICT_MEANING.get(result['verdict'], '')}", ""))
    return "\n".join(lines)


# Exit codes, so a script can branch on the verdict. The bwcli wrapper collapses every
# non-zero code to "failed", which is the right signal for the two verdicts that are not a go.
EXIT_CODES = {IN_PLACE: 0, RESTORE_ONLY: 2, REFUSE: 3}
