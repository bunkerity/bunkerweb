"""Write paths of ``Database`` that broke the first save on a fresh install or a service creation.

* #3893: a custom config sent with ``checksum: None`` was stored without checksum, which broke the
  service creation; the checksum is computed whenever it is missing or empty.
* #3215: ``<service>_IS_DRAFT`` came back as the multisite default instead of the service's own draft flag.
* #3297: a plugin UI folder with a vanished or unreadable file aborted the plugin update instead of
  skipping the page.
* The first ``save_config`` lost to a concurrent writer inserting the same rows (duplicate key) and the
  whole batch was dropped; it now recomputes and retries once.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import Database as database_module
from common_utils import bytes_hash  # type: ignore
from fixtures.seed import add_service, add_setting, make_core_plugin, make_external_plugin, make_general_settings, seed_minimal, seed_multisite, session
from model import Global_values, Plugin_pages, Plugins


class TestMissingChecksumIsComputed:
    @pytest.mark.parametrize("checksum", [None, ""], ids=["none", "empty"])
    def test_save_custom_configs(self, db, checksum):
        seed_minimal(db)

        assert db.save_custom_configs([{"type": "http", "name": "snippet", "data": "# hello", "method": "manual", "checksum": checksum}], "manual") == ""

        assert db.get_custom_config("http", "snippet")["checksum"] == bytes_hash(b"# hello", algorithm="sha256")

    @pytest.mark.parametrize("checksum", [None, ""], ids=["none", "empty"])
    def test_upsert_custom_config_for_a_new_config(self, db, checksum):
        seed_minimal(db)

        assert (
            db.upsert_custom_config("http", "snippet", {"type": "http", "name": "snippet", "data": "# hello", "method": "ui", "checksum": checksum}, new=True)
            == ""
        )

        assert db.get_custom_config("http", "snippet")["checksum"] == bytes_hash(b"# hello", algorithm="sha256")

    def test_an_explicit_checksum_is_kept(self, db):
        seed_minimal(db)

        db.save_custom_configs([{"type": "http", "name": "snippet", "data": "# hello", "method": "manual", "checksum": "given"}], "manual")

        assert db.get_custom_config("http", "snippet")["checksum"] == "given"


class TestServiceDraftFlagIsNotOverwrittenByTheDefault:
    def test_draft_service_reads_back_as_draft(self, db):
        seed_multisite(db)
        add_setting(db, "IS_DRAFT", context="multisite", type="check", regex="^(yes|no)$", default="no")
        add_service(db, "draft.example.com", is_draft=True)

        config = db.get_config(methods=False, with_drafts=True)

        assert config["draft.example.com_IS_DRAFT"] == "yes"
        assert config["app1.example.com_IS_DRAFT"] == "no"


@pytest.fixture
def plugin_tree(db, tmp_path, monkeypatch):
    seed_minimal(db)
    monkeypatch.setattr(database_module, "sep", str(tmp_path))
    path = tmp_path / "etc/bunkerweb/plugins/extplugin"
    (path / "ui").mkdir(parents=True)
    (path / "ui/template.html").write_text("<p>page</p>")
    return path


class TestPluginPageArchiveFailure:
    @pytest.mark.parametrize("error", [FileNotFoundError("vanished"), PermissionError("denied")], ids=["vanished", "unreadable"])
    def test_plugin_is_saved_without_its_page(self, db, plugin_tree, monkeypatch, error):
        def failing_archive(*args, **kwargs):
            raise error

        monkeypatch.setattr(database_module, "create_plugin_tar_gz", failing_archive)
        plugin = make_external_plugin() | {"page": True}

        assert db.update_external_plugins([plugin]) == ""

        with session(db) as s:
            assert s.scalars(select(Plugins.id).filter_by(id="extplugin")).first() == "extplugin"
            assert s.scalars(select(Plugin_pages).filter_by(plugin_id="extplugin")).first() is None

    def test_a_readable_page_is_stored(self, db, plugin_tree):
        plugin = make_external_plugin() | {"page": True}

        assert db.update_external_plugins([plugin]) == ""

        assert db.get_plugin_page("extplugin")


class _ConflictOnFirstCommit:
    """Session proxy: a rival writer inserts the same rows, then the first commit of the save fails on the duplicate key."""

    def __init__(self, db, rival_rows):
        self._real = db._session_factory
        self._db = db
        self._rival_rows = rival_rows
        self.commits = 0

    def __getattr__(self, name):
        return getattr(self._real, name)

    def commit(self):
        self.commits += 1
        if self.commits == 1:
            self._real.rollback()
            with Session(self._db.sql_engine) as rival:
                rival.add_all(self._rival_rows)
                rival.commit()
            raise IntegrityError("INSERT INTO bw_global_values", {}, Exception("UNIQUE constraint failed: bw_global_values.setting_id"))
        return self._real.commit()


class TestFirstSaveLosesToAConcurrentWriter:
    @pytest.fixture
    def seeded(self, db):
        db.init_tables([make_general_settings(), make_core_plugin("alpha")])
        db.initialize_db("1.7.0", "Docker")
        return db

    @staticmethod
    def _values(db):
        with session(db) as s:
            return {row.setting_id: row.value for row in s.scalars(select(Global_values))}

    def test_save_recomputes_and_persists_every_setting(self, seeded):
        seeded._session_factory = _ConflictOnFirstCommit(seeded, [Global_values(setting_id="ALPHA_GLOBAL", value="rival", method="ui", suffix=0)])

        result = seeded.save_config({"ALPHA_GLOBAL": "mine", "ALPHA_MS": "kept"}, "ui", skip_service_management=True)

        assert isinstance(result, set), result
        assert self._values(seeded) == {"ALPHA_GLOBAL": "mine", "ALPHA_MS": "kept"}

    def test_without_retry_the_conflict_is_reported_and_nothing_is_lost_silently(self, seeded):
        seeded._session_factory = _ConflictOnFirstCommit(seeded, [Global_values(setting_id="ALPHA_GLOBAL", value="rival", method="ui", suffix=0)])

        result = seeded.save_config({"ALPHA_GLOBAL": "mine", "ALPHA_MS": "kept"}, "ui", skip_service_management=True, retry_on_conflict=False)

        assert isinstance(result, str) and "UNIQUE constraint failed" in result
        assert self._values(seeded) == {"ALPHA_GLOBAL": "rival"}
