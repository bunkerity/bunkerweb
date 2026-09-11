"""The v1.6.13 baseline every migration test upgrades from.

Extracted from `test_upgrade_schema_parity.py`, which `test_certificate_migrations.py` used to
import these out of directly. A test module is not an API: importing one from another makes pytest's
collection order load it twice under two names, and it only resolved at all because the default
`prepend` import mode happens to put the test directory on `sys.path`. Both tests need the same
starting point, so the starting point lives here and neither owns the other.
"""

import re
from pathlib import Path
from subprocess import run
from types import ModuleType

from sqlalchemy import MetaData, create_engine, text

from fixtures.db_factory import resolve_uri
from fixtures.engines import _with_driver

ROOT = Path(__file__).resolve().parents[3]
ALEMBIC = ROOT / "src" / "common" / "db" / "alembic"

# The last stable 1.6 release, and the one the 1.7 head chains off. Hardcoded on purpose: deriving
# "the newest 1.6 tag" would quietly change what these tests upgrade *from* the day a 1.6.15 lands,
# which is the opposite of what a regression test should do. The revision to stamp is not hardcoded
# — it is derived below exactly as the product derives it, so the two cannot drift apart.
BASELINE_TAG = "v1.6.13"
BASELINE_VERSION = BASELINE_TAG.lstrip("v")

# The OTHER starting point, and the older one: the release the whole migration chain roots at.
# `sqlite_versions/8bb3be426524_upgrade_to_version_1_5_0.py` has `down_revision = None` and its
# `upgrade()` drops a column from an existing `bw_plugins`, so the chain does not build the schema
# — it expects a database some 1.5.0-beta install already created, which is exactly what
# `misc/migration/create.sh` boots a 1.5.0-beta scheduler to produce. A parity run from here is the
# one that executes EVERY revision in the chain instead of stamping past most of them. Count-free
# on purpose: the number moves every time a 1.6.x release is ported in, and a stale one reads as a
# measurement. L-G follow-up 6.
LEGACY_TAG = "v1.5.0-beta"

# The THIRD starting point, and the newest: the latest 1.6 PRE-RELEASE, which is what the
# integration harness resolves dynamically as the version to upgrade *from*
# (`tests/scripts/before/upgrade.sh`) — so it is a starting point real operators and real CI runs
# both take, however short-lived the tag is.
#
# What only a start from HERE proves is the VERSION LOOKUP: `entrypoint.sh` resolves a stamped
# `bw_metadata.version` to a revision by filename and hard-exits when none matches, so a released
# version with no `*_upgrade_to_version_<v>.py` is an unbootable upgrade whatever the schema holds.
# That is `revision_for` below, and it is the whole reason this tag is here — it is what red-flagged
# the missing `1.6.15~rc2` revision. The SCHEMA half of rc2 (it adds `bw_ui_users.totp_last_counter`,
# the same column the 1.7 head used to add) is NOT unique to this start and must not be described as
# if it were: rc2 now sits below the head on every route, so the 1.6.13 start and the 1.5.0-beta
# chain execute it too, and a duplicate `add_column` reds all three.
#
# `-rc2` rather than the `~rc2` the product stores in `bw_metadata.version`: `revision_for`
# normalises `.`, `-` and `~` to `_` alike, so both spellings resolve to the same file, and the tag
# form is what `baseline_metadata` needs to read `model.py` out of git.
PRERELEASE_TAG = "v1.6.15-rc2"
PRERELEASE_VERSION = PRERELEASE_TAG.lstrip("v")


def baseline_metadata(tag=None):
    """`model.py` as it was at `tag` (the 1.6.13 baseline by default), loaded under its own `Base`.

    Read out of git rather than reconstructed: the point is to start from a schema some release
    really shipped, and any hand-written approximation of it would be the same mistake as
    `create_all`-ing the current model, just less obvious.
    """
    tag = tag or BASELINE_TAG
    source = run(["git", "show", f"{tag}:src/common/db/model.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    module = ModuleType(f"bw_model_{tag.lstrip('v').replace('.', '_').replace('-', '_')}")
    exec(compile(source, f"<{tag}:src/common/db/model.py>", "exec"), module.__dict__)  # noqa: S102
    return module.Base.metadata


def columns_added_since_baseline():
    """`{table: [column, ...]}` -- what 1.7 adds to a table the baseline release already had.

    DERIVED from the two schemas, never restated: a hand-written copy of this map is exactly what
    goes stale when a head regeneration adds a column, and it goes stale silently.
    `bw_ui_users.totp_last_counter` is the one that proved it -- it was added by the wave-13
    regeneration and no hand-maintained list moved with it.

    These are the columns a downgrade has to remove from a table that otherwise survives, which is
    both what the manifest's `data_loss_detail.columns` declares and what a restore from a baseline
    dump must leave behind.
    """
    from model import Base  # noqa: PLC0415 - conftest puts src/common/db on the path

    baseline = baseline_metadata().tables
    added = {}
    for name, table in Base.metadata.tables.items():
        if name not in baseline:
            continue
        new_columns = {column.name for column in table.columns} - {column.name for column in baseline[name].columns}
        if new_columns:
            added[name] = sorted(new_columns)
    return added


def revision_for(version, dialect):
    """The revision the product would stamp for a database recorded at `version`.

    `entrypoint.sh:107-110` finds it by filename — `*_upgrade_to_version_<version with _ for .>.py`
    — so this reads it the same way instead of naming a hash that would go stale silently.
    """
    normalised = version.replace(".", "_").replace("-", "_").replace("~", "_")
    matches = sorted((ALEMBIC / f"{dialect}_versions").glob(f"*_upgrade_to_version_{normalised}.py"))
    assert len(matches) == 1, f"expected one migration for {version} in {dialect}_versions, found {[m.name for m in matches]}"
    return matches[0].name.split("_", 1)[0]


# Alembic's own template writes `revision: str = "abc123"`, and `black` keeps the double quotes --
# but a head that has not been through the formatter yet, which is exactly what
# `misc/migration/create.sh` emits, carries single ones. A pattern that only accepts double quotes
# does not report a bad head, it reports NO head: the revision drops out of the chain entirely and
# every guard anchored to it fails as "the manifest drifted" while the manifest is fine. Both quote
# styles are accepted here, and in the `down_revision` strip below.
_REVISION_RX = re.compile(r"""^revision: str = ["'](.+?)["']""", re.M)
_DOWN_REVISION_RX = re.compile(r"^down_revision: Union\[str, None\] = (.+?)$", re.M)


def chain(dialect, versions_dir=None):
    """`{revision: (down_revision, path)}` for one dialect's migration directory.

    Read out of the files rather than through alembic's `ScriptDirectory` on purpose: the guards
    that use this have to be able to see a head that alembic itself would refuse to load, and
    `version_locations` would need the whole config machinery to point at one dialect.
    """
    found = {}
    for path in sorted((versions_dir or ALEMBIC / f"{dialect}_versions").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        revision = _REVISION_RX.search(text)
        if not revision:
            continue
        down = _DOWN_REVISION_RX.search(text)
        found[revision.group(1)] = (down.group(1).strip().strip("\"'") if down else None, path)
    return found


def walk_back(dialect, head, stop=None):
    """The revisions from `head` down to `stop` (inclusive), newest first.

    Stops at `stop`, at the root, or after 200 hops -- a chain that loops is a corrupt directory,
    not a reason to hang the suite.
    """
    links = chain(dialect)
    seen, cursor = [], head
    while cursor and cursor in links and len(seen) < 200:
        seen.append(cursor)
        if cursor == stop:
            break
        cursor = links[cursor][0]
    return seen


def product_uri(db_engine, tmp_path):
    """The URI the product would hand alembic, driver and all.

    `scheduler/entrypoint.sh:83-99` writes `db.database_uri` — the string *after*
    `Database.py:184-196` injected `+psycopg`/`+pymysql` — and re-exports that as `DATABASE_URI`
    before alembic runs. The operator's bare `postgresql://` or `mariadb://` never reaches alembic,
    which matters: SQLAlchemy defaults those to psycopg2 and MySQLdb, neither of which BunkerWeb
    ships. `_with_driver` is the same mapping, already mirrored for the fixtures.
    """
    return _with_driver(resolve_uri(db_engine, tmp_path)).render_as_string(hide_password=False)


def wipe(uri):
    """Drop everything, not just what the current model declares.

    `fixtures.engines.reset_schema` uses `Base.metadata.drop_all`, which leaves behind anything the
    1.7 model does not name — `alembic_version` above all, whose leftover row would silently make
    the next `stamp` a no-op. PostgreSQL additionally needs its ENUM *types* gone, and those are not
    tables; `DROP SCHEMA public CASCADE` is the only wipe that takes both.
    """
    engine = create_engine(uri)
    try:
        with engine.begin() as conn:
            if engine.dialect.name == "postgresql":
                conn.execute(text("DROP SCHEMA public CASCADE"))
                conn.execute(text("CREATE SCHEMA public"))
            elif engine.dialect.name in ("mysql", "mariadb"):
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                for (table,) in conn.execute(text("SHOW TABLES")).fetchall():
                    conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            else:
                leftovers = MetaData()
                leftovers.reflect(bind=conn)
                leftovers.drop_all(bind=conn)
    finally:
        engine.dispose()
