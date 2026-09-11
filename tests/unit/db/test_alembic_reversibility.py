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

import ast
from json import loads
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from db.alembic_baseline import (
    ALEMBIC,
    BASELINE_VERSION,
    baseline_metadata,
    chain,
    columns_added_since_baseline,
    revision_for,
    walk_back,
)


def model_metadata():
    """The live 1.7 schema. Imported inside a function because `model` lands on `sys.path` from
    conftest, and reading `Base.metadata` is the only contact this file has with the frozen file."""
    from model import Base  # noqa: PLC0415 - conftest puts src/common/db on the path

    return Base.metadata


MANIFEST = loads((Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "backup" / "downgrade-manifest.json").read_text(encoding="utf-8"))
ROWS = MANIFEST["releases"]
SQLITE_ROW = next(row for row in ROWS if row["engine"] == "sqlite")
MANIFEST_COLUMNS = {table: sorted(names) for table, names in MANIFEST["data_loss_detail"]["columns"].items()}

# Dropped by the 1.7 head's downgrade(); `bw_ui_user_preferences` is renamed rather than dropped,
# so it is in the set that must be gone either way. DERIVED, never restated: a hand-maintained copy
# of this list is exactly what goes stale when 1.8 adds a table, and it goes stale silently.
TABLES_ADDED_BY_1_7 = set(model_metadata().tables) - set(baseline_metadata().tables)


# The same derivation one level down: what 1.7 adds to a table 1.6.14 already had. Those columns are
# what `downgrade()` drops from a table that otherwise survives, which is the loss the manifest has to
# spell out to the operator -- `bw_ui_users.totp_last_counter` was added by a head regeneration and the
# hand-written map did not move with it. It lives in `alembic_baseline` because
# `test_downgrade_round_trip.py` needs the same map for the restore path and a second copy of it
# would be the very drift this derivation exists to prevent.
COLUMNS_ADDED_BY_1_7 = columns_added_since_baseline()


# ── The migration-anchored half: what `downgrade()` itself says it drops ──────────────────────
#
# `COLUMNS_ADDED_BY_1_7` above is anchored to the MODEL, which is sound only while
# `test_upgrade_schema_parity` is green and is blind to one engine's head diverging from the other
# three -- the manifest says "dropped by the downgrade on every engine" and the model cannot see
# "every engine" at all. So the artifact is read too: the `downgrade()` bodies, parsed, and compared
# to the same manifest map. Two independent anchors, one shipped claim.
#
# EVERY revision the downgrade runs, not just the head. The manifest describes one operation --
# `from_revision` down to `to_revision` -- and alembic runs the `downgrade()` of every revision in
# between, so which of them holds a given `drop_column` is an implementation detail of the chain and
# not something the operator-facing claim depends on. Reading the head alone made that detail
# load-bearing, and it moved: `bw_ui_users.totp_last_counter` is added by `1.6.15~rc2` (port of dev
# `d10f1615a00x`) and dropped by ITS downgrade, so the head neither adds nor drops it any more while
# the column is still lost on the way to 1.6.14, exactly as the manifest says.


def _attr(func):
    return func.attr if isinstance(func, ast.Attribute) else None


def _receiver(func):
    return func.value.id if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) else None


def _literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _walk(node, table, columns, dropped):
    """`table` is the `batch_alter_table` a `batch_op.*` call is bound to, threaded down the tree."""
    if isinstance(node, ast.With):
        for item in node.items:
            call = item.context_expr
            if isinstance(call, ast.Call) and _attr(call.func) == "batch_alter_table" and call.args:
                table = _literal(call.args[0]) or table
    if isinstance(node, ast.Call):
        name, args = _attr(node.func), [_literal(arg) for arg in node.args]
        if name == "drop_table" and args and args[0]:
            dropped.add(args[0])
        elif name == "drop_column":
            # `op.drop_column("tbl", "col")` names its table; `batch_op.drop_column("col")` inherits it.
            if _receiver(node.func) == "op" and len(args) >= 2 and args[0] and args[1]:
                columns.setdefault(args[0], set()).add(args[1])
            elif args and args[0] and table:
                columns.setdefault(table, set()).add(args[0])
    for child in ast.iter_child_nodes(node):
        _walk(child, table, columns, dropped)


def downgrade_column_drops(engine):
    """`{table: [column, ...]}` the downgrade to the manifest target drops from tables it does NOT
    drop whole.

    Every revision from `from_revision` down to -- but not including -- `to_revision`, because that
    is the set alembic executes: `walk_back` returns the stop as its last element, so it is dropped.
    A column on a table that is dropped wholesale is not a per-column loss -- the operator loses the
    table, which `data_loss_detail.tables` classifies -- so those are subtracted, exactly as
    `downgrade.py`'s renderer words it ("that otherwise survive"), and across the whole path rather
    than per file: a table dropped by one revision cannot be a surviving table for another.
    """
    row = next(row for row in ROWS if row["engine"] == engine)
    links = chain(engine)
    executed = walk_back(engine, row["alembic"]["from_revision"], stop=row["alembic"]["to_revision"])[:-1]
    assert executed, f"{engine}: no revisions between {row['alembic']['from_revision']} and {row['alembic']['to_revision']}"

    columns, dropped = {}, set()
    for revision in executed:
        tree = ast.parse(links[revision][1].read_text(encoding="utf-8"))
        body = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
        _walk(body, None, columns, dropped)
    return {table: sorted(names) for table, names in columns.items() if table not in dropped}


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


def test_the_downgrade_removes_every_column_1_7_added(tmp_path, monkeypatch):
    """The columns half, executed rather than declared.

    Both guards above read files -- the model, the baseline, the head's AST. This one runs the
    migration and looks at the database that comes out, which is the only check that can catch a
    `drop_column` that alembic emits and the engine quietly does not apply.
    """
    uri = _round_trip(tmp_path, monkeypatch)
    engine = create_engine(uri)
    try:
        inspector = inspect(engine)
        left = sorted(
            f"{table}.{column}"
            for table, columns in COLUMNS_ADDED_BY_1_7.items()
            for column in columns
            if column in {existing["name"] for existing in inspector.get_columns(table)}
        )
    finally:
        engine.dispose()
    assert not left, f"the downgrade left 1.7 columns on tables 1.6.14 still has: {left}"


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

    assert (
        MANIFEST_COLUMNS == COLUMNS_ADDED_BY_1_7
    ), f"the manifest's per-column loss map is not what 1.7 adds to surviving tables: {MANIFEST_COLUMNS} != {COLUMNS_ADDED_BY_1_7}"


@pytest.mark.parametrize("engine", sorted({row["engine"] for row in ROWS}))
def test_every_engine_really_drops_the_columns_the_manifest_declares(engine):
    """The migration-anchored guard, on all four engines, not just the one the round trip runs.

    `columns_why` claims the drop happens "on every engine". The model-anchored assertion above
    cannot check that -- there is one model and four chains -- and it is only sound while
    `test_upgrade_schema_parity` is green. This reads the artifacts the claim is about: the
    `downgrade()` bodies alembic really executes on the way to the target. The two disagree exactly
    when a migration is hand-edited, when one engine's chain diverges, or when model and migrations
    drift; all three are silent today.
    """
    assert downgrade_column_drops(engine) == MANIFEST_COLUMNS, f"{engine}: the downgrade to the manifest target does not drop what it declares"


def test_the_downgrade_walk_finds_something_to_walk():
    """Anti-vacuity: an AST walk that resolves nothing compares {} to {} and passes for free."""
    for engine in sorted({row["engine"] for row in ROWS}):
        drops = downgrade_column_drops(engine)
        expected = sum(len(names) for names in MANIFEST_COLUMNS.values())
        assert sum(len(names) for names in drops.values()) == expected, f"{engine}: expected {expected} resolved column drops, found {drops}"


def test_the_baseline_tag_and_the_manifest_target_describe_the_same_schema():
    """`alembic_baseline` starts from 1.6.13; the manifest downgrades to 1.6.14. Every assertion in
    this file and in `test_downgrade_round_trip.py` treats those as one schema, and they are -- but
    only because every migration between them is a version bump with no schema op in it. That is a
    property of today's chain, not a law, so it is asserted rather than assumed: the day a 1.6.x
    migration adds a column, this fails and names the file instead of letting a round trip land on a
    schema neither release ever shipped.
    """
    for engine in sorted({row["engine"] for row in ROWS}):
        row = next(r for r in ROWS if r["engine"] == engine)
        links = chain(engine)
        baseline_revision = revision_for(BASELINE_VERSION, engine)
        between = walk_back(engine, row["alembic"]["to_revision"], stop=baseline_revision)
        # `walk_back` runs to the root when `stop` is never reached, so a length check would pass for
        # a 1.6.13 that is not an ancestor at all. The last element IS the stop, or the walk missed it.
        assert (
            between[-1] == baseline_revision
        ), f"{engine}: the {BASELINE_VERSION} revision is not an ancestor of the manifest target {row['alembic']['to_revision']}"

        for revision in between[:-1]:  # [-1] is the 1.6.13 revision itself, which defines the baseline
            path = links[revision][1]
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or _receiver(node.func) not in ("op", "batch_op"):
                    continue
                assert _attr(node.func) == "execute", f"{path.name} calls op.{_attr(node.func)}(): 1.6.13 and {row['to']} are no longer the same schema"
                statement = (_literal(node.args[0]) or "").upper() if node.args else ""
                assert statement.startswith("UPDATE BW_METADATA"), f"{path.name} executes {statement[:60]!r}, which is not a version bump"
