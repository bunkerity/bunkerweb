"""`bw_resources.type` and `bw_certificates.source` are open strings on an UPGRADED database too.

The July 1.7 heads created both columns as ENUMs (`resource_types_enum` with `certificate` alone,
`certificate_sources_enum` with the three core providers). The model now declares them `String(64)`
on purpose — redirects, upstreams and workflows are resources, and any plugin declaring
`extensions.certificate_source` may own certificates — and the heads were regenerated to match.
Every other resource test builds its schema with `create_all`, which reads the model and so can never
see what the migration actually created: an ENUM left behind in a head would pass them all and
break the first redirect an upgraded install saves (MariaDB/MySQL reject the value; PostgreSQL rejects
the VARCHAR bind against an ENUM column, whatever the value). This starts from the schema v1.6.13 shipped and
goes through the product's own stamp + upgrade, as `test_upgrade_schema_parity.py` does.

SQLite never enforced either ENUM (SQLAlchemy renders a non-native VARCHAR without a CHECK), so it
passes against the July heads as well; PostgreSQL, MariaDB and MySQL are where this can fail.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select

import db.alembic_baseline as baseline
from model import Base  # type: ignore

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def upgraded_uri(db_engine, tmp_path, monkeypatch):
    """A database built by v1.6.13, then stamped and upgraded to head the way `entrypoint.sh` does.

    Wiped again on teardown, whatever happened: PostgreSQL and MariaDB are one shared database for the
    whole run, and a half-upgraded 1.6.13 schema left behind is one `reset_schema` cannot drop, which
    errors every later `db` test in setup (see `test_downgrade_round_trip.py`).
    """
    uri = baseline.product_uri(db_engine, tmp_path)
    baseline.wipe(uri)
    try:
        engine = create_engine(uri)
        baseline.baseline_metadata().create_all(engine)
        engine.dispose()

        monkeypatch.setenv("DATABASE_URI", uri)
        monkeypatch.chdir(baseline.ALEMBIC)
        config = Config("alembic.ini")
        config.set_main_option("version_locations", f"{db_engine}_versions")
        command.stamp(config, baseline.revision_for(baseline.BASELINE_VERSION, db_engine))
        command.upgrade(config, "head")

        engine = create_engine(uri)
        Base.metadata.create_all(engine, checkfirst=True)  # what initialization.py does next
        engine.dispose()
        yield uri
    finally:
        baseline.wipe(uri)


def _resource(conn, resource_type):
    resource_id = str(uuid4())
    conn.execute(
        Base.metadata.tables["bw_resources"]
        .insert()
        .values(id=resource_id, type=resource_type, name=f"open-{resource_type}", creation_date=NOW, last_update=NOW)
    )
    return resource_id


@pytest.mark.parametrize("resource_type", ["redirect", "upstream", "workflow"])
def test_an_upgraded_database_accepts_every_resource_type(upgraded_uri, resource_type):
    engine = create_engine(upgraded_uri)
    try:
        with engine.connect() as conn, conn.begin() as transaction:
            resource_id = _resource(conn, resource_type)
            resources = Base.metadata.tables["bw_resources"]
            assert conn.execute(select(resources.c.type).where(resources.c.id == resource_id)).scalar() == resource_type
            transaction.rollback()
    finally:
        engine.dispose()


def test_an_upgraded_database_accepts_a_plugin_certificate_source(upgraded_uri):
    engine = create_engine(upgraded_uri)
    certificates = Base.metadata.tables["bw_certificates"]
    try:
        with engine.connect() as conn, conn.begin() as transaction:
            resource_id = _resource(conn, "certificate")
            conn.execute(
                certificates.insert().values(
                    resource_id=resource_id,
                    source="someplugin",
                    certificate_pem="pem",
                    private_key_ciphertext=b"ct",
                    private_key_nonce=b"n" * 12,
                    private_key_key_id="k",
                    common_name="example.com",
                    issuer="issuer",
                    serial_number="01",
                    fingerprint=uuid4().hex,
                    key_type="ec",
                    valid_from=NOW,
                    valid_to=NOW,
                )
            )
            assert conn.execute(select(certificates.c.source).where(certificates.c.resource_id == resource_id)).scalar() == "someplugin"
            transaction.rollback()
    finally:
        engine.dispose()
