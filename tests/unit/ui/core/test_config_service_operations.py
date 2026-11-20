"""app/models/config.py: service CRUD, configuration generation and the plugin catalog cache.

The database is a mock whose ``save_config`` records what the UI would persist, so each assertion
reads the exact flat configuration, ``changed`` flag and rename the UI hands to the database.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.models.config import Config, server_name_conflict

SETTINGS = {
    "SERVER_NAME": {"context": "multisite", "regex": ".*", "type": "text"},
    "USE_X": {"context": "multisite", "regex": "^(yes|no)$", "type": "check"},
    "REVERSE_PROXY_HOST": {"context": "multisite", "regex": ".*", "type": "text", "multiple": "reverse-proxy"},
    "LOG_LEVEL": {"context": "global", "regex": ".*", "type": "text"},
    "IS_DRAFT": {"context": "multisite", "regex": "^(yes|no)$", "type": "check"},
}


@pytest.fixture
def cfg(monkeypatch):
    db = MagicMock(name="db")
    db.database_uri = "sqlite:///db"
    db.save_config.return_value = set()
    db.get_plugins.return_value = [{"id": "general", "settings": {}}]
    config = Config.__new__(Config)
    config._Config__settings = dict(SETTINGS)
    config._Config__db = db
    config._Config__data = {}
    config._Config__ignore_regex_check = False
    config._Config__plugins_cache = {}
    config.db = db
    return config


def svc(name, **extra):
    return {"SERVER_NAME": name, **extra}


class TestServerNameConflict:
    def test_same_first_name_is_a_duplicate(self):
        assert server_name_conflict([svc("a.com")], "a.com") == "Service a.com already exists."

    def test_shared_secondary_name_is_reported(self):
        message = server_name_conflict([svc("a.com b.com")], "c.com b.com")
        assert message == "Server name b.com is already used by service a.com, remove it from one of the two services."

    def test_ignored_service_and_empty_names_never_conflict(self):
        assert server_name_conflict([svc("a.com")], "a.com", ignore="a.com") is None
        assert server_name_conflict([svc("")], "a.com") is None
        assert server_name_conflict([svc("a.com")], "") is None


class TestInit:
    def test_loads_settings_from_the_install_dir_and_reads_the_regex_switch(self, monkeypatch):
        reads = []
        real = Path.read_text

        def fake_read_text(self, *args, **kwargs):
            if self == Path("/usr/share/bunkerweb/settings.json"):
                reads.append(self)
                return '{"A": {"context": "global"}}'
            return real(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fake_read_text)
        monkeypatch.setenv("IGNORE_REGEX_CHECK", "YES")
        config = Config(MagicMock(), {})
        assert config.get_settings() == {"A": {"context": "global"}} and len(reads) == 1
        assert config._Config__ignore_regex_check is True


class TestPluginCatalog:
    META = {"last_external_plugins_change": "t1", "last_pro_plugins_change": "t2", "plugins_config_changed": {"x": 1}}

    def test_catalog_is_cached_until_the_version_changes(self, cfg):
        cfg.db.get_metadata.return_value = dict(self.META)
        cfg.db.get_plugins.return_value = [{"id": "p", "settings": {"S": {}}}]
        first = cfg.get_plugins()
        assert first == {"general": {}, "p": {"settings": {"S": {}}}}
        cfg.get_plugins()
        assert cfg.db.get_plugins.call_count == 1

        cfg.db.get_metadata.return_value = {**self.META, "last_external_plugins_change": "t9"}
        cfg.get_plugins()
        assert cfg.db.get_plugins.call_count == 2

    def test_callers_get_an_unaliased_catalog(self, cfg):
        cfg.db.get_metadata.return_value = dict(self.META)
        cfg.db.get_plugins.return_value = [{"id": "p", "name": "P"}]
        cfg.get_plugins()["p"]["name"] = "mutated"
        assert cfg.get_plugins()["p"]["name"] == "P"

    def test_with_data_never_touches_the_cache(self, cfg):
        cfg.db.get_metadata.return_value = dict(self.META)
        cfg.get_plugins(with_data=True)
        cfg.get_plugins(with_data=True)
        assert cfg.db.get_plugins.call_count == 2
        cfg.db.get_plugins.assert_called_with(_type="all", with_data=True)
        assert cfg._Config__plugins_cache == {}

    @pytest.mark.parametrize("metadata", [{"default": True}, RuntimeError("db down")])
    def test_unreliable_metadata_skips_the_cache(self, cfg, metadata):
        if isinstance(metadata, Exception):
            cfg.db.get_metadata.side_effect = metadata
        else:
            cfg.db.get_metadata.return_value = metadata
        cfg.get_plugins()
        cfg.get_plugins()
        assert cfg.db.get_plugins.call_count == 2

    def test_explicit_metadata_is_used_without_a_query(self, cfg):
        cfg.get_plugins(metadata=dict(self.META))
        cfg.db.get_metadata.assert_not_called()

    def test_each_type_is_cached_separately(self, cfg):
        cfg.db.get_metadata.return_value = dict(self.META)
        cfg.get_plugins(_type="pro")
        cfg.get_plugins(_type="external")
        cfg.get_plugins(_type="pro")
        assert cfg.db.get_plugins.call_count == 2

    def test_plugin_settings_merge_with_core_settings_core_winning(self, cfg):
        cfg.db.get_metadata.return_value = dict(self.META)
        cfg.db.get_plugins.return_value = [
            {"id": "general", "settings": {}},
            {"id": "p", "settings": {"LOG_LEVEL": {"context": "multisite"}, "EXTRA": {"context": "global"}}},
        ]
        merged = cfg.get_plugins_settings()
        assert merged["LOG_LEVEL"] == SETTINGS["LOG_LEVEL"] and merged["EXTRA"] == {"context": "global"}


class TestReads:
    def test_get_config_forwards_every_filter(self, cfg):
        cfg.db.get_non_default_settings.return_value = {"A": 1}
        assert cfg.get_config(True, False, True, ("A",), with_setting_drafts=True) == {"A": 1}
        cfg.db.get_non_default_settings.assert_called_once_with(
            global_only=True, methods=False, with_drafts=True, filtered_settings=("A",), with_setting_drafts=True
        )

    def test_get_services_forwards_flags(self, cfg):
        cfg.db.get_services_settings.return_value = [svc("a.com")]
        assert cfg.get_services(methods=False, with_drafts=True) == [svc("a.com")]
        cfg.db.get_services_settings.assert_called_once_with(methods=False, with_drafts=True)


class TestGenConf:
    def test_multisite_settings_are_prefixed_and_server_names_joined(self, cfg):
        cfg.db.get_metadata.return_value = {"default": True}
        assert (
            cfg.gen_conf({"LOG_LEVEL": "debug"}, [svc("a.com", USE_X="yes", LOG_LEVEL="x"), svc("b.com", REVERSE_PROXY_HOST_1="h")], check_changes=False)
            == set()
        )
        conf, method = cfg.db.save_config.call_args.args[:2]
        assert method == "ui"
        assert conf == {
            "LOG_LEVEL": "debug",
            "a.com_SERVER_NAME": "a.com",
            "a.com_USE_X": "yes",
            "b.com_SERVER_NAME": "b.com",
            "b.com_REVERSE_PROXY_HOST_1": "h",
            "SERVER_NAME": "a.com b.com",
            "DATABASE_URI": "sqlite:///db",
        }
        assert cfg.db.save_config.call_args.kwargs == {"changed": False, "file_names": None}

    def test_existing_prefixed_value_wins_unless_the_service_is_the_edited_one(self, cfg):
        services = [svc("a.com", USE_X="no")]
        cfg.gen_conf({"a.com_USE_X": "yes"}, services)
        assert cfg.db.save_config.call_args.args[0]["a.com_USE_X"] == "yes"
        cfg.gen_conf({"a.com_USE_X": "yes"}, services, changed_service="a.com")
        assert cfg.db.save_config.call_args.args[0]["a.com_USE_X"] == "no"

    def test_service_without_a_name_is_skipped(self, cfg):
        cfg.gen_conf({}, [svc("")])
        conf = cfg.db.save_config.call_args.args[0]
        assert "SERVER_NAME" not in conf

    def test_optional_save_arguments_are_forwarded_only_when_given(self, cfg):
        cfg.gen_conf({}, [], override_method="api", file_name_map={"a": "b"}, draft_settings={"X": True}, rename=("a", "b"), custom_config_changes=[{"k": 1}])
        assert cfg.db.save_config.call_args.args[1] == "api"
        assert cfg.db.save_config.call_args.kwargs == {
            "changed": True,
            "file_names": {"a": "b"},
            "draft_settings": {"X": True},
            "rename": ("a", "b"),
            "custom_config_changes": [{"k": 1}],
        }


class TestServiceOperations:
    def test_new_service_refuses_a_duplicate(self, cfg):
        cfg.db.get_services_settings.return_value = [svc("a.com")]
        assert cfg.new_service(svc("a.com")) == ("Service a.com already exists.", 1)
        cfg.db.save_config.assert_not_called()

    def test_new_service_saves_with_the_draft_flag(self, cfg):
        cfg.db.get_services_settings.return_value = []
        cfg.db.get_non_default_settings.return_value = {"LOG_LEVEL": "debug"}
        assert cfg.new_service(svc("new.com"), is_draft=True) == ("Configuration for new.com has been generated.", 0)
        conf = cfg.db.save_config.call_args.args[0]
        assert conf["new.com_IS_DRAFT"] == "yes" and conf["LOG_LEVEL"] == "debug"
        assert cfg.db.save_config.call_args.kwargs["changed"] is False  # drafts never trigger a reload
        cfg.new_service(svc("live.com"))
        assert cfg.db.save_config.call_args.kwargs["changed"] is True
        cfg.new_service(svc("quiet.com"), check_changes=False)
        assert cfg.db.save_config.call_args.kwargs["changed"] is False

    def test_new_service_surfaces_a_save_error(self, cfg):
        cfg.db.get_services_settings.return_value = []
        cfg.db.get_non_default_settings.return_value = {}
        cfg.db.save_config.return_value = "database is locked"
        assert cfg.new_service(svc("x.com")) == ("database is locked", 1)

    def test_edit_service_replaces_the_old_entry(self, cfg):
        cfg.db.get_services_settings.return_value = [svc("a.com", USE_X="no"), svc("b.com")]
        cfg.db.get_non_default_settings.return_value = {"a.com_USE_X": "no", "LOG_LEVEL": "info"}
        assert cfg.edit_service("a.com", svc("a.com", USE_X="yes")) == ("Configuration for a.com has been edited.", 0)
        args, kwargs = cfg.db.save_config.call_args
        assert args[0]["a.com_USE_X"] == "yes" and args[0]["SERVER_NAME"] == "b.com a.com"
        assert "rename" not in kwargs

    def test_rename_drops_the_old_prefixed_keys_and_passes_the_rename(self, cfg):
        cfg.db.get_services_settings.return_value = [svc("old.com", USE_X="yes")]
        cfg.db.get_non_default_settings.return_value = {"old.com_USE_X": "yes", "LOG_LEVEL": "info"}
        cfg.edit_service("old.com", svc("new.com", USE_X="yes"))
        args, kwargs = cfg.db.save_config.call_args
        assert "old.com_USE_X" not in args[0] and args[0]["new.com_SERVER_NAME"] == "new.com"
        assert kwargs["rename"] == ("old.com", "new.com")

    def test_adding_an_alias_is_not_a_rename(self, cfg):
        cfg.db.get_services_settings.return_value = [svc("a.com")]
        cfg.db.get_non_default_settings.return_value = {}
        cfg.edit_service("a.com", svc("a.com b.com"))
        assert "rename" not in cfg.db.save_config.call_args.kwargs

    def test_edit_service_refuses_a_name_used_by_another_service(self, cfg):
        cfg.db.get_services_settings.return_value = [svc("a.com"), svc("b.com")]
        message, status = cfg.edit_service("a.com", svc("b.com"))
        assert status == 1 and message == "Service b.com already exists."

    def test_edit_service_surfaces_a_save_error(self, cfg):
        cfg.db.get_services_settings.return_value = [svc("a.com")]
        cfg.db.get_non_default_settings.return_value = {}
        cfg.db.save_config.return_value = "boom"
        assert cfg.edit_service("a.com", svc("a.com")) == ("boom", 1)

    def test_edit_global_conf(self, cfg):
        cfg.db.get_services_settings.return_value = [svc("a.com")]
        assert cfg.edit_global_conf({"LOG_LEVEL": "debug"}) == ("The global settings have been edited.", 0)
        assert cfg.db.save_config.call_args.args[0]["LOG_LEVEL"] == "debug"
        cfg.db.save_config.return_value = "nope"
        assert cfg.edit_global_conf({}) == ("nope", 1)

    def test_delete_service_removes_its_keys_everywhere(self, cfg):
        cfg.db.get_services_settings.return_value = [svc("a.com", USE_X="yes"), svc("b.com", USE_X="no")]
        cfg.db.get_non_default_settings.return_value = {"SERVER_NAME": "a.com b.com", "a.com_USE_X": "yes", "b.com_USE_X": "no", "LOG_LEVEL": "info"}
        assert cfg.delete_service("a.com extra") == ("Configuration for a.com has been deleted.", 0)
        conf = cfg.db.save_config.call_args.args[0]
        assert conf["SERVER_NAME"] == "b.com" and "a.com_USE_X" not in conf and conf["b.com_USE_X"] == "no"
        assert "a.com_SERVER_NAME" not in conf

    def test_delete_missing_service(self, cfg):
        cfg.db.get_services_settings.return_value = [svc("b.com")]
        cfg.db.get_non_default_settings.return_value = {"SERVER_NAME": "b.com"}
        assert cfg.delete_service("a.com") == ("Can't delete missing a.com configuration.", 1)
        cfg.db.save_config.assert_not_called()

    def test_delete_service_surfaces_a_save_error(self, cfg):
        cfg.db.get_services_settings.return_value = [svc("a.com")]
        cfg.db.get_non_default_settings.return_value = {"SERVER_NAME": "a.com"}
        cfg.db.save_config.return_value = "locked"
        assert cfg.delete_service("a.com") == ("locked", 1)
