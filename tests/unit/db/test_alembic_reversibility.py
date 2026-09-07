"""Does the 1.7 head's `downgrade()` still do what the compatibility manifest says it does?

The manifest (`src/common/core/backup/downgrade-manifest.json`) is what `bwcli plugin backup
downgrade --execute` trusts before it migrates a production database in place. It was produced by
an executed measurement, but a measurement recorded in a JSON file goes stale the moment a head
moves -- and the failure is silent in the dangerous direction: the manifest would still say
`in_place_tested` for a downgrade that no longer works.

So this re-runs the claim rather than re-reading it. SQLite only, in-process, ~2 s: it is the
engine the manifest marks reversible that needs no container, and a head that breaks usually
breaks everywhere. The other three engines are measured out of suite -- see
`.cache/results-2026-09-06-wave13/dgad-probe-*.json` and `report-DG-AD.md` §1.
"""

from json import loads
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from db.alembic_baseline import ALEMBIC, BASELINE_VERSION, baseline_metadata, revision_for


def model_metadata():
    """The live 1.7 schema. Imported inside a function because `model` lands on `sys.path` from
    conftest, and reading `Base.metadata` is the only contact this file has with the frozen file."""
    from model import Base  # noqa: PLC0415 - conftest puts src/common/db on the path

    return Base.metadata


MANIFEST = loads((Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup" / "downgrade-manifest.json").read_text(encoding="utf-8"))
SQLITE_ROW = next(row for row in MANIFEST["releases"] if row["engine"] == "sqlite")

# Dropped by the 1.7 head's downgrade(); `bw_ui_user_preferences` is renamed rather than dropped,
# so it is in the set that must be gone either way. DERIVED, never restated: a hand-maintained copy
# of this list is exactly what goes stale when 1.8 adds a table, and it goes stale silently.
TABLES_ADDED_BY_1_7 = set(model_metadata().tables) - set(baseline_metadata().tables)


# The same derivation one level down: what 1.7 adds to a table 1.6.14 already had. Those columns are
# what `downgrade()` drops from a table that otherwise survives, which is the loss the manifest has to
# spell out to the operator -- `bw_ui_users.totp_last_counter` was added by a head regeneration and the
# hand-written map did not move with it.
def _columns_added_by_1_7():
    baseline = baseline_metadata().tables
    added = {}
    for name, table in model_metadata().tables.items():
        if name in baseline:
            new_columns = {column.name for column in table.columns} - {column.name for column in baseline[name].columns}
            if new_columns:
                added[name] = sorted(new_columns)
    return added


COLUMNS_ADDED_BY_1_7 = _columns_added_by_1_7()


def _placeholder(column):
    """A type-appropriate value for a NOT NULL column with no default. Content is irrelevant here:
    only the row's existence is."""
    python_type = None
    try:
        python_type = column.type.python_type
    except (NotImplementedError, AttributeError):
        pass
    if python_type is bool:
        return False
    if python_type is int:
        return 0
    if python_type is bytes:
        return b""
    return "x"


def _round_trip(tmp_path, monkeypatch):
    """1.6.13 baseline -> stamp -> upgrade to head -> downgrade to the manifest's target."""
    uri = f"sqlite:///{tmp_path / 'reversibility.sqlite3'}"
    metadata = baseline_metadata()
    engine = create_engine(uri)
    metadata.create_all(engine)
    # `create_all` leaves bw_metadata empty, and every version bump in the chain is an UPDATE --
    # with no row they all affect zero rows and the recorded version is never written or read.
    # A real installation always has this row; seeding it is what makes that assertion mean
    # something instead of comparing None to None.
    table = metadata.tables["bw_metadata"]
    values = {column.name: _placeholder(column) for column in table.columns if not column.nullable and column.server_default is None and column.default is None}
    values.update({"id": 1, "version": BASELINE_VERSION, "is_initialized": True})
    with engine.begin() as conn:
        conn.execute(table.insert().values(**values))
    engine.dispose()

    monkeypatch.setenv("DATABASE_URI", uri)
    monkeypatch.chdir(ALEMBIC)
    config = Config("alembic.ini")
    config.set_main_option("version_locations", "sqlite_versions")
    command.stamp(config, revision_for(BASELINE_VERSION, "sqlite"))
    command.upgrade(config, "head")
    command.downgrade(config, SQLITE_ROW["alembic"]["to_revision"])
    return uri


def test_the_manifest_still_claims_sqlite_is_reversible():
    """If this ever flips, the test below stops being the right assertion -- fail loudly instead
    of silently proving something nobody claims any more."""
    assert SQLITE_ROW["mode"] == "in_place_tested"
    assert SQLITE_ROW["to"] == "1.6.14"
    assert SQLITE_ROW["alembic"]["to_revision"]


def test_the_1_7_head_downgrades_to_the_revision_the_manifest_names(tmp_path, monkeypatch):
    uri = _round_trip(tmp_path, monkeypatch)
    engine = create_engine(uri)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == SQLITE_ROW["alembic"]["to_revision"]
    finally:
        engine.dispose()


def test_the_downgrade_removes_every_table_1_7_added(tmp_path, monkeypatch):
    uri = _round_trip(tmp_path, monkeypatch)
    engine = create_engine(uri)
    try:
        left = TABLES_ADDED_BY_1_7 & set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert not left, f"the downgrade left 1.7 tables behind: {sorted(left)}"


def test_the_downgrade_records_the_version_it_landed_on(tmp_path, monkeypatch):
    """`bw_metadata.version` is what the scheduler entrypoint stamps from on the next boot, so a
    downgrade that moves the schema and not the recorded version is the half-finished state the
    preflight refuses to start from."""
    uri = _round_trip(tmp_path, monkeypatch)
    engine = create_engine(uri)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version FROM bw_metadata WHERE id = 1")).scalar() == SQLITE_ROW["to"]
    finally:
        engine.dispose()


def test_the_schema_comes_back_to_what_the_target_release_declares(tmp_path, monkeypatch):
    """The 1.6.13 baseline plus the 1.6.14 migration is what a 1.6.14 install has; the round trip
    has to land on the same table set, with nothing missing and nothing extra."""
    expected = set(baseline_metadata().tables)
    uri = _round_trip(tmp_path, monkeypatch)
    engine = create_engine(uri)
    try:
        actual = {name for name in inspect(engine).get_table_names() if name != "alembic_version"}
    finally:
        engine.dispose()
    assert not expected - actual, f"tables 1.6.14 declares are missing after the downgrade: {sorted(expected - actual)}"
    assert not actual - expected, f"tables left behind that 1.6.14 does not declare: {sorted(actual - expected)}"


def test_the_manifest_classifies_every_table_1_7_adds():
    """The loss map is anchored to the schema, not to itself.

    `test_downgrade_manifest.py`'s drift guards compare the manifest's `data_loss_detail.tables`
    against the manifest's own `not_counted_by_the_preflight`, which cannot see a table that was
    never classified in the first place. Criticos round 3 proved it: deleting a table from *both*
    maps leaves it destroyed, uncounted, unclassified and undocumented, and the whole suite stays
    green. This is the assertion that closes it -- the model and the 1.6.14 baseline decide what
    1.7 adds, and every one of those has to carry a measured loss class.
    """
    classified = set(MANIFEST["data_loss_detail"]["tables"])
    assert not TABLES_ADDED_BY_1_7 - classified, f"1.7 adds tables the manifest never classifies: {sorted(TABLES_ADDED_BY_1_7 - classified)}"
    assert not classified - TABLES_ADDED_BY_1_7, f"the manifest classifies tables 1.7 does not add: {sorted(classified - TABLES_ADDED_BY_1_7)}"

    columns = {table: sorted(names) for table, names in MANIFEST["data_loss_detail"]["columns"].items()}
    assert columns == COLUMNS_ADDED_BY_1_7, f"the manifest's per-column loss map is not what 1.7 adds to surviving tables: {columns} != {COLUMNS_ADDED_BY_1_7}"
