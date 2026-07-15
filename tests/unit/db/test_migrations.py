"""1.6.12 databases can move to and from the 1.7 schema."""

from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from fixtures.engines import reset_schema
from model import Metadata

ALEMBIC = Path(__file__).resolve().parents[3] / "src" / "common" / "db" / "alembic"
OLD_HEAD = "f9c3d7b2dba8"


def migration_config(engine: str, uri: str, output_buffer=None) -> Config:
    config = Config(str(ALEMBIC / "alembic.ini"), output_buffer=output_buffer)
    config.set_main_option("script_location", str(ALEMBIC))
    config.set_main_option("version_locations", str(ALEMBIC / f"{engine}_versions"))
    config.set_main_option("sqlalchemy.url", uri)
    return config


def test_sqlite_upgrade_accepts_web_cache_permission(tmp_path, _clean_env):
    uri = f"sqlite:///{tmp_path / 'upgrade.sqlite3'}"
    config = migration_config("sqlite", uri)

    reset_schema(uri)
    engine = create_engine(uri)
    with Session(engine) as session:
        session.add(Metadata(is_initialized=True, first_config_saved=True, version="1.6.12"))
        session.commit()
    command.stamp(config, OLD_HEAD)
    command.upgrade(config, "head")

    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT version FROM bw_metadata WHERE id = 1")) == "1.7.0~beta"
        connection.execute(
            text(
                "INSERT INTO bw_api_users "
                "(username, password, method, admin, creation_date, update_date) "
                "VALUES ('upgrade-test', 'hash', 'manual', 0, :now, :now)"
            ),
            {"now": now},
        )
        connection.execute(
            text(
                "INSERT INTO bw_api_user_permissions "
                "(api_user, resource_type, resource_id, permission, granted, created_at, updated_at) "
                "VALUES ('upgrade-test', 'web_cache', NULL, 'web_cache_read', 1, :now, :now)"
            ),
            {"now": now},
        )

    command.downgrade(config, OLD_HEAD)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version FROM bw_metadata WHERE id = 1")) == "1.6.12"
        assert connection.scalar(text("SELECT count(*) FROM bw_api_user_permissions WHERE resource_type = 'web_cache'")) == 0
    engine.dispose()


@pytest.mark.parametrize(
    ("engine", "uri", "old_head", "new_head", "upgrade_fragment", "downgrade_fragment"),
    (
        (
            "mariadb",
            "mariadb://user:pass@localhost/bunkerweb",
            "0fe0711317f9",
            "a63f4c9d2e17",
            "ENUM('instances','global_config','services','configs','plugins','cache','web_cache','bans','jobs')",
            "ENUM('instances','global_config','services','configs','plugins','cache','bans','jobs')",
        ),
        (
            "mysql",
            "mysql://user:pass@localhost/bunkerweb",
            "8c6516301ef6",
            "d8b14e6c3f20",
            "ENUM('instances','global_config','services','configs','plugins','cache','web_cache','bans','jobs')",
            "ENUM('instances','global_config','services','configs','plugins','cache','bans','jobs')",
        ),
        (
            "postgresql",
            "postgresql://user:pass@localhost/bunkerweb",
            "b4e0d05e52e7",
            "e2c7a91b5d64",
            "ALTER TYPE api_resource_enum ADD VALUE IF NOT EXISTS 'web_cache'",
            "DROP TYPE api_resource_enum_old",
        ),
    ),
)
def test_native_enum_upgrade_and_downgrade_sql(engine, uri, old_head, new_head, upgrade_fragment, downgrade_fragment, _clean_env):
    upgrade_output = StringIO()
    command.upgrade(
        migration_config(engine, uri, upgrade_output),
        f"{old_head}:{new_head}",
        sql=True,
    )
    upgrade_sql = upgrade_output.getvalue()
    assert upgrade_fragment in upgrade_sql
    assert "UPDATE bw_metadata SET version = '1.7.0~beta' WHERE id = 1" in upgrade_sql

    downgrade_output = StringIO()
    command.downgrade(
        migration_config(engine, uri, downgrade_output),
        f"{new_head}:{old_head}",
        sql=True,
    )
    downgrade_sql = downgrade_output.getvalue()
    assert "DELETE FROM bw_api_user_permissions WHERE resource_type = 'web_cache'" in downgrade_sql
    assert downgrade_fragment in downgrade_sql
    assert "UPDATE bw_metadata SET version = '1.6.12' WHERE id = 1" in downgrade_sql
