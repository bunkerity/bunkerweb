"""A 1.6.15 setting draft must still be a draft after the upgrade to 1.7.

1.6.15-rc3 added ``is_draft`` to ``bw_global_values`` / ``bw_services_settings``; the RAW editor
set it and every reader filtered it. 1.7 carried the rc3 migration but not the feature, so on
every engine an upgraded draft value went LIVE (wave 23, CLOSE-E2 §4, cases c and d). This builds
the database the way an operator has it -- the real ``v1.6.15`` schema holding draft rows,
stamped and upgraded by the product's own path (``entrypoint.sh``: stamp, ``upgrade head``, then
``create_all(checkfirst=True)``) -- and reads it with 1.7's ``get_config``, the call
``gen/main.py`` renders from.
"""

from datetime import datetime, timezone

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, insert, text

from db.alembic_baseline import ALEMBIC, FINAL_1_6_15_TAG, FINAL_1_6_15_VERSION, baseline_metadata, product_uri, revision_for, wipe
from model import Base  # type: ignore

pytestmark = pytest.mark.slow

LIVE = "live.example.com"
NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)


def _seed_1_6_15(engine):
    """What a 1.6.15 RAW editor leaves behind: a standalone global draft and a per-setting draft
    on a LIVE service, beside ordinary live values."""
    tables = baseline_metadata(FINAL_1_6_15_TAG).tables
    setting = {"context": "multisite", "help": "h", "regex": "^.*$", "type": "text", "plugin_id": "general"}
    with engine.begin() as conn:
        conn.execute(insert(tables["bw_plugins"]), [{"id": "general", "name": "General", "description": "d", "version": "1.0"}])
        conn.execute(
            insert(tables["bw_settings"]),
            [
                setting | {"id": "MULTISITE", "name": "multisite", "context": "global", "default": "no", "order": 0},
                setting | {"id": "SERVER_NAME", "name": "server-name", "default": "www.example.com", "order": 1},
                setting | {"id": "USE_GZIP", "name": "use-gzip", "default": "no", "order": 2},
                setting | {"id": "USE_CORS", "name": "use-cors", "default": "no", "order": 3},
                setting | {"id": "USE_ANTIBOT", "name": "use-antibot", "default": "no", "order": 4},
            ],
        )
        conn.execute(insert(tables["bw_services"]), [{"id": LIVE, "method": "ui", "is_draft": False, "creation_date": NOW, "last_update": NOW}])
        conn.execute(
            insert(tables["bw_global_values"]),
            [
                {"setting_id": "MULTISITE", "value": "yes", "suffix": 0, "method": "ui", "is_draft": False},
                {"setting_id": "SERVER_NAME", "value": LIVE, "suffix": 0, "method": "ui", "is_draft": False},
                {"setting_id": "USE_GZIP", "value": "yes", "suffix": 0, "method": "ui", "is_draft": True},
            ],
        )
        conn.execute(
            insert(tables["bw_services_settings"]),
            [
                {"service_id": LIVE, "setting_id": "SERVER_NAME", "value": LIVE, "suffix": 0, "method": "ui", "is_draft": False},
                {"service_id": LIVE, "setting_id": "USE_ANTIBOT", "value": "captcha", "suffix": 0, "method": "ui", "is_draft": False},
                {"service_id": LIVE, "setting_id": "USE_CORS", "value": "yes", "suffix": 0, "method": "ui", "is_draft": True},
            ],
        )
        conn.execute(
            insert(tables["bw_metadata"]),
            [{"id": 1, "is_initialized": True, "first_config_saved": True, "integration": "Docker", "version": FINAL_1_6_15_VERSION}],
        )


@pytest.fixture
def upgraded(db_engine, tmp_path, monkeypatch, quiet_logger):
    uri = product_uri(db_engine, tmp_path)
    monkeypatch.setenv("DATABASE_URI", uri)
    monkeypatch.chdir(ALEMBIC)

    wipe(uri)
    engine = create_engine(uri)
    baseline_metadata(FINAL_1_6_15_TAG).create_all(engine)
    _seed_1_6_15(engine)
    engine.dispose()

    # Same two steps as entrypoint.sh, `version_locations` set before the stamp for the reason
    # test_upgrade_schema_parity.py gives.
    config = Config("alembic.ini")
    config.set_main_option("version_locations", f"{db_engine}_versions")
    command.stamp(config, revision_for(FINAL_1_6_15_VERSION, db_engine))
    command.upgrade(config, "head")

    engine = create_engine(uri)
    Base.metadata.create_all(engine, checkfirst=True)  # what initialization.py does next
    engine.dispose()

    from Database import Database  # noqa: E402 -- imported after sys.path injection

    database = Database(quiet_logger, sqlalchemy_string=uri, log=False)
    try:
        yield database
    finally:
        database.sql_engine.dispose()
        wipe(uri)


def test_upgraded_drafts_render_their_fallback_value(upgraded):
    config = upgraded.get_config()

    # The live values are untouched...
    assert config[f"{LIVE}_USE_ANTIBOT"] == "captcha"
    # ...and neither draft reaches the renderer: the default applies, as it did under 1.6.15.
    assert config["USE_GZIP"] == "no"
    assert config[f"{LIVE}_USE_GZIP"] == "no"
    assert config[f"{LIVE}_USE_CORS"] == "no"


def test_upgraded_drafts_are_still_drafts_for_the_raw_editor(upgraded):
    raw = upgraded.get_config(methods=True, with_setting_drafts=True)

    assert raw["USE_GZIP"]["value"] == "yes" and raw["USE_GZIP"]["is_draft"] is True
    assert raw[f"{LIVE}_USE_CORS"]["value"] == "yes" and raw[f"{LIVE}_USE_CORS"]["is_draft"] is True

    with upgraded.sql_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM bw_global_values WHERE is_draft")).scalar() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM bw_services_settings WHERE is_draft")).scalar() == 1


def test_a_1_7_save_after_the_upgrade_keeps_the_drafts(upgraded):
    """The first save after the upgrade -- the scheduler's env pass or a UI composition save --
    carries no draft map and must not activate or delete the operator's drafts."""
    result = upgraded.save_config({"MULTISITE": "yes", "SERVER_NAME": LIVE, f"{LIVE}_USE_ANTIBOT": "captcha"}, "ui")
    assert isinstance(result, set), result

    with upgraded.sql_engine.connect() as conn:
        assert conn.execute(text("SELECT value FROM bw_global_values WHERE is_draft")).scalars().all() == ["yes"]
        assert conn.execute(text("SELECT value FROM bw_services_settings WHERE is_draft")).scalars().all() == ["yes"]
    assert upgraded.get_config()[f"{LIVE}_USE_CORS"] == "no"
