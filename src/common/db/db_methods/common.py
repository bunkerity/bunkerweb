#!/usr/bin/env python3
"""Shared infrastructure for the Database core class and its domain mixins.

Everything here used to live at module level in Database.py. It is imported by
Database.py *and* by every mixin module, so it must not import Database.py
(hard rule: no mixin-side import of Database.py — that would be circular).

Import-time side effects (install_as_MySQLdb, the sqlite PRAGMA listener and
the SAWarning filter) execute exactly once on first import, which Database.py
performs before creating any engine — identical timing to the previous layout.
"""

from functools import wraps
from logging import Logger
from sqlite3 import Connection as SQLiteConnection
from threading import Lock
from time import sleep
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, TypeVar
from warnings import filterwarnings

from model import (  # type: ignore
    Bw_cli_commands,
    Jobs,
    Multiselects,
    Plugin_pages,
    Plugins,
    ResourceGroup_entries,
    ResourceGroups,
    Selects,
    Settings,
    Template_custom_configs,
    Template_settings,
    Template_steps,
    Templates,
)

from pymysql import install_as_MySQLdb
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError, OperationalError, SAWarning

install_as_MySQLdb()

LOCK = Lock()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, _):
    if isinstance(dbapi_connection, SQLiteConnection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


filterwarnings("ignore", category=SAWarning, message="DELETE statement on table .* expected to delete")

T = TypeVar("T")


# DATABASE_POOL_* env-var defaults. Exported so callers (e.g. JobScheduler.py) reuse the
# same fallback values and stay aligned if these change.
DEFAULT_POOL_SIZE = 40
DEFAULT_POOL_MAX_OVERFLOW = 20
DEFAULT_POOL_TIMEOUT = 5
DEFAULT_POOL_RECYCLE = 1800
DEFAULT_POOL_PRE_PING = True


def bulk_add_in_fk_order(session: Any, items: List[Any]) -> None:
    """Add ORM objects to the session bucketed by type, in foreign-key dependency
    order (plugins/settings first with a flush so children resolve their FKs).

    Shared by ``init_tables`` and ``update_external_plugins`` — the two used to
    carry line-for-line copies of this bucketing logic.
    """
    if not items:
        return

    buckets = {
        "plugins": [],
        "settings": [],
        "selects": [],
        "multiselects": [],
        "templates": [],
        "template_steps": [],
        "template_settings": [],
        "template_configs": [],
        "resource_groups": [],
        "resource_group_entries": [],
        "jobs": [],
        "plugin_pages": [],
        "cli_commands": [],
        "other": [],
    }

    for item in items:
        if isinstance(item, Plugins):
            buckets["plugins"].append(item)
        elif isinstance(item, Settings):
            buckets["settings"].append(item)
        elif isinstance(item, Selects):
            buckets["selects"].append(item)
        elif isinstance(item, Multiselects):
            buckets["multiselects"].append(item)
        elif isinstance(item, Templates):
            buckets["templates"].append(item)
        elif isinstance(item, Template_steps):
            buckets["template_steps"].append(item)
        elif isinstance(item, Template_settings):
            buckets["template_settings"].append(item)
        elif isinstance(item, Template_custom_configs):
            buckets["template_configs"].append(item)
        elif isinstance(item, ResourceGroups):
            buckets["resource_groups"].append(item)
        elif isinstance(item, ResourceGroup_entries):
            buckets["resource_group_entries"].append(item)
        elif isinstance(item, Jobs):
            buckets["jobs"].append(item)
        elif isinstance(item, Plugin_pages):
            buckets["plugin_pages"].append(item)
        elif isinstance(item, Bw_cli_commands):
            buckets["cli_commands"].append(item)
        else:
            buckets["other"].append(item)

    if buckets["plugins"]:
        session.add_all(buckets["plugins"])
    if buckets["settings"]:
        session.add_all(buckets["settings"])
    if buckets["plugins"] or buckets["settings"]:
        session.flush()

    if buckets["selects"]:
        session.add_all(buckets["selects"])
    if buckets["multiselects"]:
        session.add_all(buckets["multiselects"])

    if buckets["templates"]:
        session.add_all(buckets["templates"])
    if buckets["template_steps"]:
        session.add_all(buckets["template_steps"])
    if buckets["template_settings"]:
        session.add_all(buckets["template_settings"])
    if buckets["template_configs"]:
        session.add_all(buckets["template_configs"])

    if buckets["resource_groups"]:
        session.add_all(buckets["resource_groups"])
    if buckets["resource_group_entries"]:
        session.add_all(buckets["resource_group_entries"])

    if buckets["jobs"]:
        session.add_all(buckets["jobs"])
    if buckets["plugin_pages"]:
        session.add_all(buckets["plugin_pages"])
    if buckets["cli_commands"]:
        session.add_all(buckets["cli_commands"])
    if buckets["other"]:
        session.add_all(buckets["other"])


def retry_on_transient_db_errors(func: Callable[..., T]) -> Callable[..., T]:
    @wraps(func)
    def wrapper(self: "DatabaseMixinBase", *args, **kwargs) -> T:
        attempts = max(1, getattr(self, "_request_retry_attempts", 1))
        delay = max(0.0, getattr(self, "_request_retry_delay", 0.0))

        for attempt in range(1, attempts + 1):
            try:
                return func(self, *args, **kwargs)
            except (ConnectionRefusedError, OperationalError, DatabaseError) as e:
                if attempt >= attempts or not self._is_transient_connection_error(e):
                    raise

                self.logger.warning(f"Transient database error in {func.__name__} (attempt {attempt}/{attempts}), retrying in {delay:.2f}s ...")
                if delay:
                    sleep(delay)

        raise RuntimeError("retry_on_transient_db_errors: unreachable code")

    return wrapper


class DatabaseMixinBase:
    """Annotation-only base class giving the domain mixins IDE/type-checker
    visibility on the attributes and helpers the Database core class provides.

    The declarations below have no runtime effect (bare annotations create no
    class attributes; the TYPE_CHECKING block does not exist at runtime), so
    the real implementations on Database always win in the MRO.
    """

    # attributes set by Database.__init__
    logger: Logger
    readonly: bool
    last_connection_retry: Any
    sql_engine: Any
    database_uri: str
    database_uri_readonly: str
    _session_factory: Any
    _engine_kwargs: Dict[str, Any]
    _request_retry_attempts: int
    _request_retry_delay: float
    _ignore_regex_check: bool

    # class constants defined on Database
    DB_STRING_RX: Any
    READONLY_ERROR: Tuple[str, ...]
    TRANSIENT_CONNECTION_ERROR_HINTS: Tuple[str, ...]
    RESTRICTED_TEMPLATE_SETTINGS: Tuple[str, ...]
    MULTISITE_CUSTOM_CONFIG_TYPES: Tuple[str, ...]
    GLOBAL_CRS_SERVICE_SCOPED_MODSEC_CRS_ERROR: str
    SUFFIX_RX: Any

    if TYPE_CHECKING:

        def _db_session(self) -> Any:
            """Implemented on Database (Database.py)."""
            ...

        def _empty_if_none(self, value: Any) -> Any:
            """Implemented on Database (Database.py)."""
            ...

        def _split_setting_key(self, key: str) -> Tuple[str, Optional[int]]:
            """Implemented on Database (Database.py)."""
            ...

        def _normalize_template_config_reference(self, reference: str) -> Optional[str]:
            """Implemented on Database (Database.py)."""
            ...

        @staticmethod
        def _methods_are_compatible(new_method: Optional[str], current_method: Optional[str], *, allow_scheduler_override: bool = False) -> bool:
            """Implemented on Database (Database.py)."""
            ...

        def _is_transient_connection_error(self, error: BaseException) -> bool:
            """Implemented on Database (Database.py)."""
            ...

        def retry_connection(self, *, readonly: bool = False, fallback: bool = False, log: bool = True, **kwargs) -> None:
            """Implemented on Database (Database.py)."""
            ...

        def is_valid_setting(self, setting: str, **kwargs: Any) -> Tuple[bool, str]:
            """Implemented in a sibling mixin."""
            ...

        def get_config(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            """Implemented in a sibling mixin."""
            ...

        def get_non_default_settings(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            """Implemented in a sibling mixin."""
            ...

        def get_template_details(self, template_id: str) -> Dict[str, Any]:
            """Implemented in a sibling mixin."""
            ...
