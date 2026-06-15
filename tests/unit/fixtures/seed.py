"""Composable, FK-valid seed builders for DB-layer tests.

All inserts go through a short-lived ``Session`` bound to the Database's engine (not
its scoped_session), with fixed, timezone-aware datetimes for determinism. Seeds build
a complete foreign-key-valid graph so they pass on PostgreSQL/MariaDB (which enforce
FKs) as well as SQLite (which does not).
"""

from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from common_utils import bytes_hash  # type: ignore
from model import (  # type: ignore
    Custom_configs,
    Global_values,
    Jobs,
    Jobs_cache,
    Plugin_pages,
    Plugins,
    RolesUsers,
    Services,
    Services_settings,
    Settings,
    Users,
)

# Deterministic timestamp for every seeded row.
FIXED_DT = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@contextmanager
def session(db):
    """A committing session bound to the Database's engine (independent of its
    scoped_session, which the Database methods manage themselves)."""
    s = Session(db.sql_engine)
    try:
        yield s
        s.commit()
    finally:
        s.close()


def seed_minimal(db) -> dict:
    """Insert the minimum FK-valid graph used by most DB tests and initialize the
    singleton Metadata row. Returns a dict of handles (ids) for the seeded rows.

    Graph: 1 plugin ``general`` -> a few settings (global + multisite + a ``multiple``
    one + USE_TEMPLATE/SECURITY_MODE) -> 1 job ``testjob`` -> 1 service ``app1.example.com``.
    """
    with session(db) as s:
        s.add(Plugins(id="general", name="General", description="Core settings", version="1.0"))
        s.flush()
        s.add_all(
            [
                Settings(id="MULTISITE", name="MULTISITE", plugin_id="general", context="global", help="h", regex="^(yes|no)$", type="check", default="no"),
                Settings(id="SERVER_NAME", name="SERVER_NAME", plugin_id="general", context="multisite", help="h", regex="^.*$", type="text", default=""),
                Settings(
                    id="USE_REVERSE_PROXY",
                    name="USE_REVERSE_PROXY",
                    plugin_id="general",
                    context="multisite",
                    help="h",
                    regex="^(yes|no)$",
                    type="check",
                    default="no",
                ),
                Settings(
                    id="REVERSE_PROXY_URL",
                    name="REVERSE_PROXY_URL",
                    plugin_id="general",
                    context="multisite",
                    help="h",
                    regex="^.*$",
                    type="text",
                    default="",
                    multiple="reverse-proxy",
                ),
                Settings(id="USE_TEMPLATE", name="USE_TEMPLATE", plugin_id="general", context="multisite", help="h", regex="^.*$", type="text", default=""),
                Settings(
                    id="SECURITY_MODE", name="SECURITY_MODE", plugin_id="general", context="multisite", help="h", regex="^.*$", type="text", default="block"
                ),
            ]
        )
        s.add(Jobs(name="testjob", plugin_id="general", file_name="testjob.py", every="hour"))
        s.add(Services(id="app1.example.com", method="manual", is_draft=False, creation_date=FIXED_DT, last_update=FIXED_DT))
        s.flush()

    db.initialize_db("1.7.0", "Docker")
    return {
        "plugin_id": "general",
        "service_id": "app1.example.com",
        "job_name": "testjob",
        "settings": ["MULTISITE", "SERVER_NAME", "USE_REVERSE_PROXY", "REVERSE_PROXY_URL", "USE_TEMPLATE", "SECURITY_MODE"],
    }


def add_service(db, service_id, *, is_draft=False, method="manual") -> None:
    with session(db) as s:
        s.add(Services(id=service_id, method=method, is_draft=is_draft, creation_date=FIXED_DT, last_update=FIXED_DT))


def add_service_setting(db, *, service_id, setting_id, value, method="manual", suffix=0) -> None:
    with session(db) as s:
        s.add(Services_settings(service_id=service_id, setting_id=setting_id, value=value, method=method, suffix=suffix))


def add_custom_config_row(db, *, service_id=None, type="http", name="cfg", data=b"# snippet", method="manual") -> None:
    with session(db) as s:
        s.add(
            Custom_configs(
                service_id=service_id,
                type=type,
                name=name,
                data=data,
                checksum=bytes_hash(data, algorithm="sha256"),
                method=method,
            )
        )


def add_jobs_cache_row(db, *, job_name="testjob", service_id=None, file_name="cache.txt", data=b"x") -> None:
    with session(db) as s:
        s.add(Jobs_cache(job_name=job_name, service_id=service_id, file_name=file_name, data=data, last_update=FIXED_DT, checksum="seedsum"))


def add_global_value(db, *, setting_id, value, method="scheduler", suffix=0) -> None:
    with session(db) as s:
        s.add(Global_values(setting_id=setting_id, value=value, method=method, suffix=suffix))


def add_setting(db, setting_id, *, plugin_id="general", context="global", type="text", regex="^.*$", multiple=None, default="") -> None:
    with session(db) as s:
        s.add(
            Settings(
                id=setting_id,
                name=setting_id,
                plugin_id=plugin_id,
                context=context,
                help="h",
                regex=regex,
                type=type,
                multiple=multiple,
                default=default,
            )
        )


def seed_multisite(db) -> dict:
    """Build a realistic multisite scenario on top of ``seed_minimal``: two services,
    a global multisite flag, a multisite global default, and per-service overrides
    (incl. a suffixed ``multiple`` value). Mirrors the shape of misc/refactor/fixture.env.
    """
    handles = seed_minimal(db)  # plugin + settings + app1 + Metadata
    add_service(db, "app2.example.com")
    add_global_value(db, setting_id="MULTISITE", value="yes")  # global context -> enables multisite
    add_global_value(db, setting_id="SECURITY_MODE", value="detect")  # multisite default -> propagates to all services
    add_service_setting(db, service_id="app1.example.com", setting_id="USE_REVERSE_PROXY", value="yes")
    add_service_setting(db, service_id="app1.example.com", setting_id="REVERSE_PROXY_URL", value="http://backend1", suffix=1)
    add_service_setting(db, service_id="app1.example.com", setting_id="SECURITY_MODE", value="block")  # overrides the global default
    handles["services"] = ["app1.example.com", "app2.example.com"]
    return handles


def add_ui_user(db, username, *, admin=False, method="manual") -> None:
    """Insert a bw_ui_users row directly (UiUsers maps the same table, so RBAC queries see it)."""
    with session(db) as s:
        s.add(Users(username=username, password="x", method=method, admin=admin, creation_date=FIXED_DT, update_date=FIXED_DT))


def add_role_user(db, username, role_name) -> None:
    with session(db) as s:
        s.add(RolesUsers(user_name=username, role_name=role_name))


def add_plugin(db, plugin_id, *, type="core", method="manual", version="1.0", name=None, description="d", checksum=None) -> None:
    with session(db) as s:
        s.add(Plugins(id=plugin_id, name=name or plugin_id, description=description, version=version, type=type, method=method, checksum=checksum))


def add_plugin_page(db, plugin_id, *, data=b"<page>", checksum="pagesum") -> None:
    with session(db) as s:
        s.add(Plugin_pages(plugin_id=plugin_id, data=data, checksum=checksum))
