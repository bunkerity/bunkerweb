"""Upgrade manifests must move operator values before deleting renamed settings."""

from unittest.mock import patch

import pytest
from sqlalchemy import event, select

from fixtures.seed import add_service, make_core_plugin, session
from model import Global_values, Services_settings, Settings, Template_settings, Templates

RENAMES = [
    ("modsecurity", "MODSECURITY_CRS_PLUGIN_URLS", "MODSECURITY_CRS_PLUGINS"),
    ("reverseproxy", "REVERSE_PROXY_SSL_CERT", "REVERSE_PROXY_SSL_CLIENT_CERT"),
    ("reverseproxy", "REVERSE_PROXY_SSL_CERT_DATA", "REVERSE_PROXY_SSL_CLIENT_CERT_DATA"),
    ("reverseproxy", "REVERSE_PROXY_SSL_CERT_PRIORITY", "REVERSE_PROXY_SSL_CLIENT_CERT_PRIORITY"),
    ("reverseproxy", "REVERSE_PROXY_SSL_KEY", "REVERSE_PROXY_SSL_CLIENT_KEY"),
    ("reverseproxy", "REVERSE_PROXY_SSL_KEY_DATA", "REVERSE_PROXY_SSL_CLIENT_KEY_DATA"),
    ("grpc", "GRPC_SSL_CERT", "GRPC_SSL_CLIENT_CERT"),
    ("grpc", "GRPC_SSL_CERT_DATA", "GRPC_SSL_CLIENT_CERT_DATA"),
    ("grpc", "GRPC_SSL_CERT_PRIORITY", "GRPC_SSL_CLIENT_CERT_PRIORITY"),
    ("grpc", "GRPC_SSL_KEY", "GRPC_SSL_CLIENT_KEY"),
    ("grpc", "GRPC_SSL_KEY_DATA", "GRPC_SSL_CLIENT_KEY_DATA"),
]


def manifest(plugin_id, *setting_ids):
    settings = {
        setting_id: {
            "id": setting_id.lower().replace("_", "-"),
            "context": "multisite",
            "default": "",
            "help": "Upgrade regression",
            "label": "Value",
            "regex": "^.*$",
            "type": "text",
            "multiple": "values",
        }
        for setting_id in setting_ids
    }
    # Existing select options are deleted and reinserted during every init. The
    # rename fix must preserve that order to avoid unique-key conflicts.
    settings["UNCHANGED_PICK"] = {
        **settings[setting_ids[0]],
        "id": "unchanged-pick",
        "type": "select",
        "select": ["file", "data"],
    }
    return [make_core_plugin(plugin_id, settings=settings)]


def assert_rename_preserves_values(db, plugin_id, old_id, new_id):
    assert db.init_tables(manifest(plugin_id, old_id)) == (True, "")
    add_service(db, "rename.example.com")
    with session(db) as s:
        for model in (Global_values, Services_settings):
            for suffix in (0, 2):
                kwargs = {"service_id": "rename.example.com"} if model is Services_settings else {}
                s.add(model(setting_id=old_id, value=f"operator-{suffix}", file_name="operator.pem", method="ui", suffix=suffix, **kwargs))

    with patch.object(db.logger, "warning") as warning:
        assert db.init_tables(manifest(plugin_id, new_id)) == (True, "")

    with session(db) as s:
        assert s.get(Settings, old_id) is None
        assert s.get(Settings, new_id) is not None
        for model in (Global_values, Services_settings):
            rows = s.scalars(select(model).order_by(model.suffix)).all()
            assert [(r.setting_id, r.value, r.file_name, r.method, r.suffix) for r in rows] == [
                (new_id, f"operator-{suffix}", "operator.pem", "ui", suffix) for suffix in (0, 2)
            ]
            if model is Services_settings:
                assert all(r.service_id == "rename.example.com" for r in rows)

    warning.assert_called_once_with(f"{old_id} setting has been renamed to {new_id}, migrating data")
    with patch.object(db.logger, "warning") as warning:
        assert db.init_tables(manifest(plugin_id, new_id)) == (True, "")
        warning.assert_not_called()


@pytest.mark.parametrize("plugin_id,old_id,new_id", RENAMES)
def test_setting_rename_preserves_operator_values(db, plugin_id, old_id, new_id):
    assert_rename_preserves_values(db, plugin_id, old_id, new_id)


def test_setting_rename_with_sqlite_foreign_keys(db, db_engine):
    if db_engine != "sqlite":
        pytest.skip("SQLite-specific FK enforcement; server engines enforce FKs by default")

    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    db.sql_engine.dispose()
    event.listen(db.sql_engine, "connect", enable_foreign_keys)
    with db.sql_engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    assert_rename_preserves_values(db, *RENAMES[0])


def test_setting_rename_preserves_ui_template_setting(db):
    plugin_id, old_id, new_id = RENAMES[1]
    assert db.init_tables(manifest(plugin_id, old_id)) == (True, "")
    assert (
        db.create_template(
            "rename-template",
            name="Rename template",
            settings={old_id: "certificate"},
            steps=[{"title": "Certificate", "settings": [old_id]}],
        )
        == ""
    )

    with session(db) as s:
        assert s.get(Templates, "rename-template").plugin_id is None
        assert s.scalar(select(Template_settings.setting_id).filter_by(template_id="rename-template")) == old_id

    assert db.init_tables(manifest(plugin_id, new_id)) == (True, "")

    with session(db) as s:
        assert s.scalar(select(Template_settings.setting_id).filter_by(template_id="rename-template")) == new_id


@pytest.mark.parametrize("plugin_id,new_id", [("modsecurity", "UNRELATED_SETTING"), ("unrelated", "MODSECURITY_CRS_PLUGINS")])
def test_setting_removal_is_not_reported_as_a_rename(db, plugin_id, new_id):
    assert db.init_tables(manifest(plugin_id, "MODSECURITY_CRS_PLUGIN_URLS")) == (True, "")
    with patch.object(db.logger, "warning") as warning:
        assert db.init_tables(manifest(plugin_id, new_id)) == (True, "")
        warning.assert_not_called()
