"""The v1.6.13 baseline every migration test upgrades from.

Extracted from `test_upgrade_schema_parity.py`, which `test_certificate_migrations.py` used to
import these out of directly. A test module is not an API: importing one from another makes pytest's
collection order load it twice under two names, and it only resolved at all because the default
`prepend` import mode happens to put the test directory on `sys.path`. Both tests need the same
starting point, so the starting point lives here and neither owns the other.
"""

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


def baseline_metadata():
    """`model.py` as it was at the baseline tag, loaded under its own `Base`.

    Read out of git rather than reconstructed: the point is to start from a schema some release
    really shipped, and any hand-written approximation of it would be the same mistake as
    `create_all`-ing the current model, just less obvious.
    """
    source = run(["git", "show", f"{BASELINE_TAG}:src/common/db/model.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    module = ModuleType(f"bw_model_{BASELINE_VERSION.replace('.', '_')}")
    exec(compile(source, f"<{BASELINE_TAG}:src/common/db/model.py>", "exec"), module.__dict__)  # noqa: S102
    return module.Base.metadata


def revision_for(version, dialect):
    """The revision the product would stamp for a database recorded at `version`.

    `entrypoint.sh:107-110` finds it by filename — `*_upgrade_to_version_<version with _ for .>.py`
    — so this reads it the same way instead of naming a hash that would go stale silently.
    """
    normalised = version.replace(".", "_").replace("-", "_").replace("~", "_")
    matches = sorted((ALEMBIC / f"{dialect}_versions").glob(f"*_upgrade_to_version_{normalised}.py"))
    assert len(matches) == 1, f"expected one migration for {version} in {dialect}_versions, found {[m.name for m in matches]}"
    return matches[0].name.split("_", 1)[0]


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
