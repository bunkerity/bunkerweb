"""The compatibility manifest lot A produces, and the rot that would silently disarm it.

The conception makes the manifest the only source of truth for "can this pair go back in place":
the CLI reads it and never infers compatibility from a version number. Two failure modes follow,
and neither announces itself at runtime -- an unmatched `from` makes every pair unclassified
(safe, but the whole in-place path quietly stops existing), and a `to_revision` that has drifted
away from the migration chain sends `alembic downgrade` at a revision that is not there.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKUP = _REPO_ROOT / "src" / "common" / "core" / "backup"
if str(_BACKUP) not in sys.path:
    sys.path.insert(0, str(_BACKUP))

import downgrade  # noqa: E402
from downgrade import (  # noqa: E402
    IN_PLACE,
    RESTORE_ONLY,
    check_irrepresentable,
    check_manifest,
    load_manifest,
    loss_classes,
    manifest_row,
    target_revision,
)  # noqa: E402

MANIFEST_FILE = _BACKUP / "downgrade-manifest.json"
ALEMBIC_DIR = _REPO_ROOT / "src" / "common" / "db" / "alembic"
SUPPORTED_ENGINES = ("sqlite", "postgresql", "mariadb", "mysql")
NOW = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)

MANIFEST = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
ROWS = MANIFEST["releases"]

# What `count_irrepresentable` actually puts in its counts dict: the module constant, plus the two
# it counts separately because it filters them (`bw_resources` by type, `bw_resource_groups` by
# `plugin_id IS NULL`). Restating a set is how it drifts, so
# `test_the_counted_set_is_the_one_the_preflight_really_produces` asserts this against the function.
_COUNTED = set(downgrade.IRREPRESENTABLE_TABLES) | {"bw_resources", "bw_resource_groups"}


def _chain(engine):
    """{revision: (down_revision, filename)} for one engine's migration directory."""
    out = {}
    for path in (ALEMBIC_DIR / f"{engine}_versions").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        rev = re.search(r'^revision: str = "(.+?)"', text, re.M)
        down = re.search(r"^down_revision: Union\[str, None\] = (.+?)$", text, re.M)
        if rev:
            out[rev.group(1)] = (down.group(1).strip().strip('"') if down else None, path.name)
    return out


class TestItShips:
    def test_the_manifest_is_shipped_next_to_the_plugin_and_found_by_default(self, monkeypatch):
        """PO-7: lot C reserved a path, lot A picked this one. The default must resolve to it."""
        monkeypatch.delenv("DOWNGRADE_MANIFEST", raising=False)
        assert downgrade.MANIFEST_PATH.is_file(), f"{downgrade.MANIFEST_PATH} is not the shipped manifest"
        assert load_manifest() is not None

    def test_an_explicit_path_is_read_instead_of_the_shipped_one(self, tmp_path):
        other = tmp_path / "elsewhere.json"
        other.write_text(json.dumps({"releases": []}), encoding="utf-8")
        assert load_manifest(other) == {"releases": []}

    def test_the_env_override_is_what_sets_the_default_path(self, tmp_path, monkeypatch):
        """`MANIFEST_PATH` is bound at import, so the override cannot be tested by setting the
        variable and calling `load_manifest()` -- the module has already read it. Re-import under
        the variable, which is what an operator setting it in the environment actually gets."""
        import importlib

        other = tmp_path / "operator-supplied.json"
        other.write_text(json.dumps({"releases": [{"from": "x", "to": "y", "engine": "sqlite"}]}), encoding="utf-8")
        monkeypatch.setenv("DOWNGRADE_MANIFEST", str(other))
        reloaded = importlib.reload(downgrade)
        try:
            assert reloaded.MANIFEST_PATH == other
            assert reloaded.load_manifest()["releases"][0]["from"] == "x"
        finally:
            monkeypatch.delenv("DOWNGRADE_MANIFEST", raising=False)
            importlib.reload(downgrade)

    def test_the_shipped_manifest_declares_what_the_preflight_reads_as_silent_losses(self):
        """`data_loss_detail.columns` and `not_counted_by_the_preflight` were dead data until the
        preflight rendered them: an installation with enrolled instances and no bans passes every
        check and still loses every stored instance credential."""
        lines = downgrade.silent_losses(MANIFEST)
        assert lines, "the manifest declares uncounted losses but silent_losses() finds none"
        joined = " ".join(lines)
        assert "bw_instances" in joined
        assert "bw_metrics_requests" in joined
        assert downgrade.silent_losses(None) == []

    def test_unreadable_json_is_ignored_rather_than_crashing(self, tmp_path):
        broken = tmp_path / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        assert load_manifest(broken) is None


class TestEveryRowIsComplete:
    @pytest.mark.parametrize("engine", SUPPORTED_ENGINES)
    def test_every_supported_engine_has_a_row(self, engine):
        assert [r for r in ROWS if r["engine"] == engine], f"no manifest row for {engine}: it can never go back in place"

    @pytest.mark.parametrize("row", ROWS, ids=lambda r: f"{r['engine']}:{r['mode']}")
    def test_the_conception_s_fields_are_all_there(self, row):
        for field in ("from", "to", "engine", "mode", "data_loss", "required_backup", "plugin_api_target", "artifacts"):
            assert field in row, f"{row['engine']}: the conception's manifest shape requires {field}"
        assert row["mode"] in ("restore_only", "in_place_tested")
        assert row["data_loss"] in ("none", "conditional", "certain")
        assert row["required_backup"] is True, "a downgrade without a restorable backup is not a supported path"
        assert set(row["artifacts"].values()) <= {"compatible", "rebuild", "conditional"}

    @pytest.mark.parametrize("row", [r for r in ROWS if r["mode"] == "restore_only"], ids=lambda r: r["engine"])
    def test_a_restore_only_row_says_why(self, row):
        assert len(row.get("reason", "")) > 80, f"{row['engine']}: restore_only with no measured reason is an opinion, not a classification"


class TestItTracksTheProduct:
    def test_the_from_version_is_the_installed_one(self):
        """The rot-catcher. A `from` that no longer matches src/VERSION silently unclassifies every pair."""
        version = (_REPO_ROOT / "src" / "VERSION").read_text(encoding="utf-8").strip()
        assert {r["from"] for r in ROWS} == {version}, f"the manifest describes {sorted({r['from'] for r in ROWS})} but this tree is {version}"

    @pytest.mark.parametrize("row", ROWS, ids=lambda r: r["engine"])
    def test_the_alembic_revisions_are_the_real_ones(self, row):
        chain = _chain(row["engine"])
        head, target = row["alembic"]["from_revision"], row["alembic"]["to_revision"]
        assert head in chain, f"{row['engine']}: from_revision {head} is not in the migration chain"
        assert target in chain, f"{row['engine']}: to_revision {target} is not in the migration chain"
        assert chain[head][1].endswith("_upgrade_to_version_1_7_0_beta.py")
        assert chain[target][1].endswith(f"_upgrade_to_version_{row['to'].replace('.', '_')}.py")

    @pytest.mark.parametrize("row", ROWS, ids=lambda r: r["engine"])
    def test_from_revision_is_the_head_of_its_chain(self, row):
        chain = _chain(row["engine"])
        children = {down for down, _ in chain.values()}
        assert row["alembic"]["from_revision"] not in children, f"{row['engine']}: from_revision is no longer the head, the manifest describes an older release"

    @pytest.mark.parametrize("row", ROWS, ids=lambda r: r["engine"])
    def test_the_target_is_reachable_by_walking_back_from_the_head(self, row):
        chain = _chain(row["engine"])
        seen, cursor = [], row["alembic"]["from_revision"]
        while cursor and cursor in chain and len(seen) < 200:
            seen.append(cursor)
            cursor = chain[cursor][0]
        assert row["alembic"]["to_revision"] in seen, f"{row['engine']}: to_revision is not an ancestor of the head"


class TestOperatorBuiltResourceGroups:
    """`bw_resource_groups` is STANDALONE -- no foreign key to `bw_resources` -- and never empty:
    17 core groups ship as seeds. Counting it wholesale would pin every installation to
    `restore_only`, so the preflight counts only the groups an operator built, using the product's
    own discriminator (`db_methods/initialization.py` treats a group with a `plugin_id` as managed,
    and only the API and UI creation paths leave it NULL)."""

    def test_a_seeded_group_does_not_block_an_in_place_downgrade(self, db):
        from model import Plugins, ResourceGroups  # noqa: PLC0415 - conftest puts src/common/db on the path

        with db._db_session() as session:
            session.add(Plugins(id="country", name="Country", description="", version="1.0"))
            session.add(ResourceGroups(id="g-seeded", name="seeded", description="", method="manual", plugin_id="country", creation_date=NOW, last_update=NOW))
            session.commit()

        counts = downgrade.count_irrepresentable(db)
        assert counts["bw_resource_groups"] == 0, "a shipped seed was counted; every installation would be restore_only"
        assert check_irrepresentable(counts, loss_classes(MANIFEST)).verdict == IN_PLACE

    def test_a_hand_built_group_refuses_the_in_place_downgrade(self, db):
        """The gap Criticos round 3 found: an operator whose only 1.7 data is a resource group used
        to get `in_place_possible` from the command whose whole purpose is refusing exactly that."""
        from model import ResourceGroups  # noqa: PLC0415 - conftest puts src/common/db on the path

        with db._db_session() as session:
            session.add(ResourceGroups(id="g-mine", name="mine", description="", method="ui", plugin_id=None, creation_date=NOW, last_update=NOW))
            session.commit()

        counts = downgrade.count_irrepresentable(db)
        assert counts["bw_resource_groups"] == 1
        assert check_irrepresentable(counts, loss_classes(MANIFEST)).verdict == RESTORE_ONLY


class TestTheLossMap:
    def test_every_table_the_preflight_counts_is_classified(self):
        classes = loss_classes(MANIFEST)
        for table in downgrade.IRREPRESENTABLE_TABLES:
            assert table in classes, f"{table} is counted by the preflight but the manifest never says what losing it costs"

    def test_bans_are_the_only_conditional_loss_among_the_counted_tables(self):
        """PO ruling 2026-09-02: bans are regenerable by sync-bans; everything else keeps its measured class."""
        classes = loss_classes(MANIFEST)
        conditional = {t for t in downgrade.IRREPRESENTABLE_TABLES if classes.get(t) == "conditional"}
        assert conditional == {"bw_bans"}

    def test_every_classified_loss_is_either_counted_or_documented_as_uncounted(self):
        """The drift guard. `silent_losses()` renders a block headed "not counted by any check
        above, and destroyed all the same" — which is a claim of completeness. A table that is
        classified as lost, not counted by the preflight, and not listed as deliberately uncounted
        falls through both and is destroyed with nothing anywhere saying so."""
        classified = set(loss_classes(MANIFEST))
        documented = set((MANIFEST["data_loss_detail"].get("not_counted_by_the_preflight") or {}))
        fell_through = classified - _COUNTED - documented
        assert not fell_through, f"destroyed, uncounted and undocumented: {sorted(fell_through)}"

    def test_the_counted_set_is_the_one_the_preflight_really_produces(self, db):
        """`_COUNTED` is what both drift guards subtract, so a stale copy of it disarms them
        silently: a table dropped from `count_irrepresentable` would still look counted here."""
        assert set(downgrade.count_irrepresentable(db)) == _COUNTED

    def test_nothing_is_documented_as_uncounted_while_also_being_counted(self):
        """The other direction: a table in both lists means the report contradicts the verdict."""
        documented = set((MANIFEST["data_loss_detail"].get("not_counted_by_the_preflight") or {}))
        assert not (_COUNTED & documented), f"both counted and declared uncounted: {sorted(_COUNTED & documented)}"

    def test_an_absent_manifest_classifies_nothing(self):
        assert loss_classes(None) == {}
        assert loss_classes({}) == {}


class TestWhatTheChecksMakeOfIt:
    def test_the_shipped_rows_are_found_by_the_preflight_s_own_lookup(self):
        for row in ROWS:
            found = manifest_row(MANIFEST, row["from"], row["to"], row["engine"])
            assert found is not None and found["mode"] == row["mode"]

    def test_an_unknown_pair_refuses_in_place_before_anything_is_mutated(self):
        assert manifest_row(MANIFEST, "1.7.0~beta", "1.5.0", "sqlite") is None
        assert check_manifest(None, "1.7.0~beta", "1.5.0", "sqlite").verdict == RESTORE_ONLY

    @pytest.mark.parametrize("row", ROWS, ids=lambda r: f"{r['engine']}:{r['mode']}")
    def test_the_check_agrees_with_the_row_s_own_mode(self, row):
        verdict = check_manifest(row, row["from"], row["to"], row["engine"]).verdict
        assert verdict == (IN_PLACE if row["mode"] == "in_place_tested" else RESTORE_ONLY)

    @pytest.mark.parametrize("row", [r for r in ROWS if r["mode"] == "in_place_tested"], ids=lambda r: r["engine"])
    def test_an_in_place_row_names_the_revision_the_executor_needs(self, row):
        assert target_revision(row), f"{row['engine']}: in_place_tested with no to_revision -- the executor would refuse"

    def test_a_ban_alone_no_longer_pins_the_installation_to_restore_only(self):
        """PO-3's whole point: the manifest classifies, the preflight counts, and the two are compared."""
        counts = {table: 0 for table in downgrade.IRREPRESENTABLE_TABLES}
        counts["bw_bans"] = 12
        assert check_irrepresentable(counts).verdict == RESTORE_ONLY, "without a manifest, unclassified loss must still refuse"
        check = check_irrepresentable(counts, loss_classes(MANIFEST))
        assert check.verdict == IN_PLACE
        assert "bw_bans=12" in check.detail, "the operator must still be told the bans are going"

    def test_a_certificate_still_pins_it(self):
        counts = {table: 0 for table in downgrade.IRREPRESENTABLE_TABLES}
        counts["bw_certificates"] = 1
        assert check_irrepresentable(counts, loss_classes(MANIFEST)).verdict == RESTORE_ONLY

    def test_the_uncounted_losses_reach_the_operator_s_report(self):
        """Declaring them in the manifest is not telling anyone. An installation with enrolled
        instances and no bans passes every check and still loses every stored instance credential,
        so the report has to say so where the verdict is read."""
        rendered = downgrade.render_report(
            {
                "installed": "1.7.0~beta",
                "target": "1.6.14",
                "generated_at": "2026-09-06T12:00:00+02:00",
                "verdict": IN_PLACE,
                "checks": [{"name": "manifest", "verdict": IN_PLACE, "detail": "ok", "data": {}}],
                "silent_losses": downgrade.silent_losses(MANIFEST),
            }
        )
        assert "bw_instances" in rendered, "the dropped instance-credential columns are never shown"
        assert "bw_metrics_requests" in rendered, "the deliberately uncounted tables are never shown"
        assert "destroyed all the same" in rendered

    def test_they_are_not_claimed_under_a_refusal(self):
        """ "Destroyed all the same" is about a downgrade that will happen. A refused one will not."""
        rendered = downgrade.render_report(
            {
                "installed": "1.7.0~beta",
                "target": "1.6.14",
                "generated_at": "x",
                "verdict": downgrade.REFUSE,
                "checks": [],
                "silent_losses": downgrade.silent_losses(MANIFEST),
            }
        )
        assert "destroyed all the same" not in rendered

    def test_a_report_without_them_still_renders(self):
        """Old callers and a missing manifest must not crash the report."""
        assert "VERDICT" in downgrade.render_report({"installed": "1.7.0~beta", "target": "1.6.14", "generated_at": "x", "verdict": IN_PLACE, "checks": []})

    def test_a_table_the_manifest_forgot_is_treated_as_certain(self):
        """Safe default: silence in the manifest is not permission."""
        assert check_irrepresentable({"bw_something_new": 1}, loss_classes(MANIFEST)).verdict == RESTORE_ONLY
