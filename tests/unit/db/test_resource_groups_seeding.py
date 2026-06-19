"""DatabaseInitTablesMixin — core resource-group seeding from disk + clone.

Drives the real ``init_tables`` end-to-end: temp ``<plugin>/resource-groups/*.json`` on
disk, with the hardcoded ``/usr/share/bunkerweb/core`` base redirected to the tmp dir so
the disk-scan finds them. Covers seed -> idempotent re-run -> user-group untouched
(delete-guard) -> prune-on-removal -> entry re-sync -> expansion -> clone.
"""

import json

import pytest

from db_methods import initialization  # the mixin module (on sys.path via conftest)
from fixtures.seed import make_core_plugin

pytestmark = pytest.mark.slow

_CORE_PREFIX = "/usr/share/bunkerweb/core"
EU_DOC = {
    "name": "EU",
    "description": "European Union",
    "entries": [{"kind": "country", "value": "FR"}, {"kind": "country", "value": "DE"}],
}


def _setup_disk(tmp_path, monkeypatch, plugin_id, groups):
    """Create <tmp>/core/<plugin_id>/resource-groups/*.json and redirect the hardcoded
    core base used by the seeding disk-scan to <tmp>/core."""
    base = tmp_path / "core"
    rg_dir = base / plugin_id / "resource-groups"
    rg_dir.mkdir(parents=True, exist_ok=True)
    for gid, doc in groups.items():
        (rg_dir / f"{gid}.json").write_text(json.dumps(doc))

    real_path = initialization.Path

    def fake_path(*parts):
        p = real_path(*parts)
        s = str(p)
        if s == _CORE_PREFIX or s.startswith(_CORE_PREFIX + "/"):
            return real_path(str(base) + s[len(_CORE_PREFIX) :])
        return p

    monkeypatch.setattr(initialization, "Path", fake_path)
    return rg_dir


class TestResourceGroupSeeding:
    def test_seeds_core_group(self, db, tmp_path, monkeypatch):
        _setup_disk(tmp_path, monkeypatch, "country", {"eu": EU_DOC})
        assert db.init_tables([make_core_plugin("country")]) == (True, "")
        g = db.get_resource_groups()["eu"]
        assert g["name"] == "EU"
        assert g["method"] == "manual"
        assert g["plugin_id"] == "country"
        assert g["description"] == "European Union"
        assert {(e["kind"], e["value"]) for e in g["entries"]} == {("country", "FR"), ("country", "DE")}

    def test_idempotent_rerun(self, db, tmp_path, monkeypatch):
        _setup_disk(tmp_path, monkeypatch, "country", {"eu": EU_DOC})
        assert db.init_tables([make_core_plugin("country")])[0] is True
        # second identical run is a no-op (no churn)
        assert db.init_tables([make_core_plugin("country")]) == (False, "")
        assert len(db.get_resource_groups()["eu"]["entries"]) == 2

    def test_user_group_untouched_by_reseed(self, db, tmp_path, monkeypatch):
        _setup_disk(tmp_path, monkeypatch, "country", {"eu": EU_DOC})
        db.init_tables([make_core_plugin("country")])
        assert db.create_resource_group("mine", name="mine", entries=[{"kind": "ip", "value": "1.2.3.4"}]) == ""
        db.init_tables([make_core_plugin("country")])  # re-seed
        groups = db.get_resource_groups()
        assert groups["mine"]["method"] == "ui"  # user group survives the delete-guard
        assert "eu" in groups

    def test_core_group_pruned_when_removed_from_disk(self, db, tmp_path, monkeypatch):
        rg_dir = _setup_disk(
            tmp_path,
            monkeypatch,
            "country",
            {"eu": EU_DOC, "dach": {"name": "DACH", "entries": [{"kind": "country", "value": "DE"}]}},
        )
        db.init_tables([make_core_plugin("country")])
        assert {"eu", "dach"} <= set(db.get_resource_groups())
        (rg_dir / "dach.json").unlink()  # removed from disk
        db.init_tables([make_core_plugin("country")])
        groups = db.get_resource_groups()
        assert "eu" in groups and "dach" not in groups

    def test_entry_change_resynced(self, db, tmp_path, monkeypatch):
        rg_dir = _setup_disk(tmp_path, monkeypatch, "country", {"eu": EU_DOC})
        db.init_tables([make_core_plugin("country")])
        (rg_dir / "eu.json").write_text(json.dumps({"name": "EU", "entries": [{"kind": "country", "value": "FR"}, {"kind": "country", "value": "IT"}]}))
        db.init_tables([make_core_plugin("country")])
        g = db.get_resource_groups()["eu"]
        assert {(e["kind"], e["value"]) for e in g["entries"]} == {("country", "FR"), ("country", "IT")}

    def test_seeded_group_expands_in_config(self, db, tmp_path, monkeypatch):
        from resource_group_resolver import expand_config_groups  # noqa: E402

        _setup_disk(tmp_path, monkeypatch, "country", {"eu": EU_DOC})
        db.init_tables([make_core_plugin("country")])
        out = expand_config_groups({"BLACKLIST_COUNTRY": "@EU US"}, db)
        assert out["BLACKLIST_COUNTRY"] == "FR DE US"


class TestClone:
    def test_clone_core_to_user(self, db, tmp_path, monkeypatch):
        _setup_disk(tmp_path, monkeypatch, "country", {"eu": EU_DOC})
        db.init_tables([make_core_plugin("country")])
        # core group is immutable
        assert "cannot be modified" in db.update_resource_group("eu", name="x")
        # clone -> editable user copy
        assert db.clone_resource_group("eu", "my-eu", name="my-eu") == ""
        clone = db.get_resource_groups()["my-eu"]
        assert clone["method"] == "ui"
        assert {(e["kind"], e["value"]) for e in clone["entries"]} == {("country", "FR"), ("country", "DE")}
        # the clone is editable; the core original is untouched
        assert db.update_resource_group("my-eu", entries=[{"kind": "country", "value": "ES"}]) == ""
        assert {(e["kind"], e["value"]) for e in db.get_resource_groups()["eu"]["entries"]} == {("country", "FR"), ("country", "DE")}

    def test_clone_missing_source(self, db):
        assert db.clone_resource_group("ghost", "x", name="x") == "Resource group not found"
