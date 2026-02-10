#!/usr/bin/env python3

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager, suppress
from copy import deepcopy
from datetime import datetime, timedelta
from io import BytesIO
from json import JSONDecodeError, loads
from logging import Logger
from os import _exit, getenv, sep
from os.path import join as os_join
from pathlib import Path
from re import Match, compile as re_compile, escape, error as RegexError, search
from sys import argv, path as sys_path
from tarfile import open as tar_open
from threading import Lock
from traceback import format_exc
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, Union
from time import sleep
from uuid import uuid4
from warnings import filterwarnings

from model import (
    Base,
    Instances,
    Plugins,
    Settings,
    Global_values,
    Services,
    Services_settings,
    Jobs,
    Plugin_pages,
    Jobs_cache,
    Jobs_runs,
    Custom_configs,
    Selects,
    Multiselects,
    Bw_cli_commands,
    Templates,
    Template_steps,
    Template_settings,
    Template_custom_configs,
    Metadata,
    Users,
    UserSessions,
)

for deps_path in [os_join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import bytes_hash  # type: ignore

from pymysql import install_as_MySQLdb
from sqlalchemy import case, create_engine, event, MetaData as sql_metadata, func, join, select as db_select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import (
    ArgumentError,
    DatabaseError,
    OperationalError,
    ProgrammingError,
    SAWarning,
    SQLAlchemyError,
)
from sqlalchemy.orm import joinedload, scoped_session, sessionmaker, aliased
from sqlalchemy.pool import QueuePool
from sqlite3 import Connection as SQLiteConnection

install_as_MySQLdb()

LOCK = Lock()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, _):
    if isinstance(dbapi_connection, SQLiteConnection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


filterwarnings("ignore", category=SAWarning, message="DELETE statement on table .* expected to delete")


class Database:
    DB_STRING_RX = re_compile(r"^(?P<database>(mariadb|mysql)(\+pymysql)?|sqlite(\+pysqlite)?|postgresql(\+psycopg)?|oracle(\+oracledb)?):/+(?P<path>/[^\s]+)")
    READONLY_ERROR = ("readonly", "read-only", "command denied", "Access denied")
    RESTRICTED_TEMPLATE_SETTINGS = ("USE_TEMPLATE", "IS_DRAFT")
    MULTISITE_CUSTOM_CONFIG_TYPES = ("server_http", "modsec_crs", "modsec", "server_stream", "crs_plugins_before", "crs_plugins_after")
    SUFFIX_RX = re_compile(r"(?P<setting>.+)_(?P<suffix>\d+)$")

    def __init__(
        self, logger: Logger, sqlalchemy_string: Optional[str] = None, *, external: bool = False, pool: Optional[bool] = None, log: bool = True, **kwargs
    ) -> None:
        """Initialize the database"""
        self.logger = logger
        self.readonly = False
        self.last_connection_retry = None
        self.__ignore_regex_check = getenv("IGNORE_REGEX_CHECK", "no").lower() == "yes"

        if pool:
            self.logger.warning("The pool parameter is deprecated, it will be removed in the next version")

        self._session_factory = None
        self.sql_engine = None

        if not sqlalchemy_string:
            sqlalchemy_string = getenv("DATABASE_URI", "sqlite:////var/lib/bunkerweb/db.sqlite3")

        sqlalchemy_string_readonly = getenv("DATABASE_URI_READONLY", "")

        if not sqlalchemy_string:
            sqlalchemy_string = sqlalchemy_string_readonly or "sqlite:////var/lib/bunkerweb/db.sqlite3"

            if sqlalchemy_string == sqlalchemy_string_readonly:
                self.readonly = True
                if log:
                    self.logger.warning("The database connection is set to read-only, the changes will not be saved")

        def validate_and_update_db_string(db_string: str) -> Tuple[str, Optional[Match]]:
            """Validate and update database connection string."""
            if not db_string:
                return db_string, None

            match = self.DB_STRING_RX.search(db_string)
            if not match:
                self.logger.error(f"Invalid database string provided: {db_string}, exiting...")
                _exit(1)

            db_type = match.group("database")
            db_path = match.group("path")

            # Handle SQLite database
            if db_type.startswith("sqlite"):
                path = Path(db_path)
                if external:
                    while not path.is_file():
                        if log:
                            self.logger.warning(f"Waiting for the database file to be created: {path}")
                        sleep(1)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                return db_string, match

            # Add recommended drivers for MySQL/MariaDB and PostgreSQL
            if db_type.startswith("m") and not db_type.endswith("+pymysql"):
                return db_string.replace(db_type, f"{db_type}+pymysql"), match
            elif db_type.startswith("postgresql") and not db_type.endswith("+psycopg"):
                return db_string.replace(db_type, f"{db_type}+psycopg"), match
            elif db_type.startswith("oracle") and not db_type.endswith("+oracledb"):
                return db_string.replace(db_type, f"{db_type}+oracledb"), match

            return db_string, match

        # Validate and update both connection strings
        sqlalchemy_string, main_match = validate_and_update_db_string(sqlalchemy_string)
        sqlalchemy_string_readonly, readonly_match = validate_and_update_db_string(sqlalchemy_string_readonly)

        self.database_uri = "" if sqlalchemy_string == sqlalchemy_string_readonly else sqlalchemy_string
        self.database_uri_readonly = sqlalchemy_string_readonly
        error = False

        match = main_match
        if self.database_uri_readonly and not self.database_uri and readonly_match:
            match = readonly_match

        if main_match and main_match.group("database") == "oracle":
            self.logger.error("Oracle database is not supported yet")
            _exit(1)

        if readonly_match and readonly_match.group("database") == "oracle":
            self.logger.error("Oracle database is not supported yet")
            _exit(1)

        self._engine_kwargs = {
            "future": True,
            "poolclass": QueuePool,
            "pool_pre_ping": True,
            "pool_recycle": 1800,
            "pool_size": 40,
            "max_overflow": 20,
            "pool_timeout": 5,
        } | kwargs

        try:
            self.sql_engine = create_engine(sqlalchemy_string, **self._engine_kwargs)
        except ArgumentError:
            self.logger.error(f"Invalid database URI: {sqlalchemy_string}")
            error = True
        except SQLAlchemyError as e:
            self.logger.error(f"Error when trying to create the engine: {e}")
            error = True
        finally:
            if error:
                _exit(1)

        try:
            assert self.sql_engine is not None
        except AssertionError:
            self.logger.error("The database engine is not initialized")
            _exit(1)

        DATABASE_RETRY_TIMEOUT = getenv("DATABASE_RETRY_TIMEOUT", "60")
        if not DATABASE_RETRY_TIMEOUT.isdigit():
            self.logger.warning(f"Invalid DATABASE_RETRY_TIMEOUT value: {DATABASE_RETRY_TIMEOUT}, using default value (60)")
            DATABASE_RETRY_TIMEOUT = "60"

        DATABASE_RETRY_TIMEOUT = int(DATABASE_RETRY_TIMEOUT)

        current_time = datetime.now().astimezone()
        not_connected = True
        fallback = False

        while not_connected:
            try:
                if self.readonly:
                    with self.sql_engine.connect() as conn:
                        conn.execute(text("SELECT 1"))
                else:
                    with self.sql_engine.connect() as conn:
                        table_name = uuid4().hex
                        conn.execute(text(f"CREATE TABLE IF NOT EXISTS test_{table_name} (id INT)"))
                        conn.execute(text(f"DROP TABLE IF EXISTS test_{table_name}"))

                not_connected = False
            except (OperationalError, DatabaseError) as e:
                if (datetime.now().astimezone() - current_time).total_seconds() > DATABASE_RETRY_TIMEOUT:
                    if not fallback and self.database_uri_readonly:
                        self.logger.error(f"Can't connect to database after {DATABASE_RETRY_TIMEOUT} seconds. Falling back to read-only database connection")
                        self.sql_engine.dispose(close=True)
                        self.sql_engine = create_engine(self.database_uri_readonly, **self._engine_kwargs)
                        self.readonly = True
                        fallback = True
                        continue
                    self.logger.error(f"Can't connect to database after {DATABASE_RETRY_TIMEOUT} seconds: {e}")
                    _exit(1)

                if any(error in str(e) for error in self.READONLY_ERROR):
                    if log:
                        self.logger.warning("The database is read-only. Retrying in read-only mode in 5 seconds ...")
                    self.sql_engine.dispose(close=True)
                    self.sql_engine = create_engine(sqlalchemy_string, **self._engine_kwargs)
                    self.readonly = True
                if "Unknown table" in str(e):
                    not_connected = False
                    continue
                elif log:
                    self.logger.warning("Can't connect to database, retrying in 5 seconds ...")
                sleep(5)
            except BaseException as e:
                self.logger.error(f"Error when trying to connect to the database: {e}")
                exit(1)

        if log:
            self.logger.info(f"✅ Database connection established{'' if not self.readonly else ' in read-only mode'}")

        if match.group("database").startswith("sqlite"):
            db_path = Path(match.group("path"))
            try:
                current_mode = db_path.stat().st_mode & 0o777
                if current_mode != 0o660:
                    db_path.chmod(0o660)
            except (OSError, IOError) as e:
                self.logger.warning(f"Could not set file permissions on {db_path}: {e}")

    def __del__(self) -> None:
        """Close the database"""
        if self._session_factory:
            self._session_factory.close_all()

        if self.sql_engine:
            self.sql_engine.dispose()

    def _empty_if_none(self, value: Any) -> Any:
        """Return an empty string if the value is None or convert None values in collections"""
        if value is None:
            return ""
        elif isinstance(value, dict):
            return {k: self._empty_if_none(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._empty_if_none(item) for item in value]
        elif isinstance(value, tuple):
            return tuple(self._empty_if_none(item) for item in value)
        return value

    def _split_setting_key(self, key: str) -> Tuple[str, Optional[int]]:
        """Split a setting key into its base id and optional numeric suffix."""
        match = self.SUFFIX_RX.search(key)
        if match:
            return match.group("setting"), int(match.group("suffix"))
        return key, None

    def _normalize_template_config_reference(self, reference: str) -> Optional[str]:
        """Normalize a config reference to the canonical type/name.conf representation."""
        if not reference:
            return None
        ref = reference.strip()
        if not ref:
            return None
        if "/" not in ref:
            return None
        cfg_type_raw, cfg_name_raw = ref.split("/", 1)
        cfg_type = cfg_type_raw.strip().replace("-", "_").lower()
        if cfg_type not in self.MULTISITE_CUSTOM_CONFIG_TYPES:
            return None
        cfg_name = cfg_name_raw.strip().removesuffix(".conf")
        if not cfg_name:
            return None
        return f"{cfg_type}/{cfg_name}.conf"

    @staticmethod
    def _methods_are_compatible(new_method: Optional[str], current_method: Optional[str]) -> bool:
        """
        Determine whether two configuration methods should be considered compatible for updates.

        UI and API updates are treated as interchangeable, while autoconf keeps its special behavior.
        """
        if new_method is None:
            return True
        if current_method is None:
            return True
        if new_method == "autoconf":
            return True
        if current_method == "autoconf":
            return new_method == "autoconf"
        if {new_method, current_method} <= {"ui", "api"}:
            return True
        return new_method == current_method

    def test_read(self):
        """Test the read access to the database"""
        self.logger.debug("Testing read access to the database ...")
        with self._db_session() as session:
            session.execute(text("SELECT 1"))

    def test_write(self):
        """Test the write access to the database"""
        self.logger.debug("Testing write access to the database ...")
        with self._db_session() as session:
            table_name = uuid4().hex
            session.execute(text(f"CREATE TABLE IF NOT EXISTS test_{table_name} (id INT)"))
            session.execute(text(f"DROP TABLE IF EXISTS test_{table_name}"))
            session.commit()

    def retry_connection(self, *, readonly: bool = False, fallback: bool = False, log: bool = True, **kwargs) -> None:
        """Retry the connection to the database"""
        self.last_connection_retry = datetime.now().astimezone()

        if log:
            self.logger.debug(f"Retrying the connection to the database{' in read-only mode' if readonly else ''}{' with fallback' if fallback else ''} ...")

        assert self.sql_engine is not None

        if fallback and not self.database_uri_readonly:
            raise ValueError("The fallback parameter is set to True but the read-only database URI is not set")

        self.sql_engine.dispose(close=True)
        self.sql_engine = create_engine(self.database_uri_readonly if fallback else self.database_uri, **self._engine_kwargs | kwargs)

        if fallback or readonly:
            with self.sql_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return

        table_name = uuid4().hex
        with self.sql_engine.connect() as conn:
            conn.execute(text(f"CREATE TABLE IF NOT EXISTS test_{table_name} (id INT)"))
            conn.execute(text(f"DROP TABLE IF EXISTS test_{table_name}"))

    @contextmanager
    def _db_session(self) -> Any:
        try:
            assert self.sql_engine is not None
        except AssertionError:
            self.logger.error("The database engine is not initialized")
            _exit(1)

        with LOCK:
            session = None
            try:
                session_factory = sessionmaker(bind=self.sql_engine, autoflush=True, expire_on_commit=False)
                session = scoped_session(session_factory)
                yield session
            except BaseException as e:
                if session:
                    session.rollback()

                if any(error in str(e) for error in self.READONLY_ERROR):
                    self.logger.warning("The database is read-only, retrying in read-only mode ...")
                    try:
                        self.retry_connection(readonly=True, pool_timeout=1)
                        self.retry_connection(readonly=True, log=False)
                    except (OperationalError, DatabaseError):
                        if self.database_uri_readonly:
                            self.logger.warning("Can't connect to the database in read-only mode, falling back to read-only one")
                            with suppress(OperationalError, DatabaseError):
                                self.retry_connection(fallback=True, pool_timeout=1)
                            self.retry_connection(fallback=True, log=False)
                    self.readonly = True
                elif isinstance(e, (ConnectionRefusedError, OperationalError)) and self.database_uri_readonly:
                    self.logger.warning("Can't connect to the database, falling back to read-only one ...")
                    with suppress(OperationalError, DatabaseError):
                        self.retry_connection(fallback=True, pool_timeout=1)
                        self.retry_connection(fallback=True, log=False)
                        self.readonly = True
                raise
            finally:
                if session:
                    session.remove()

    def is_valid_setting(
        self,
        setting: str,
        *,
        value: Optional[str] = None,
        multisite: bool = False,
        session: Optional[scoped_session] = None,
        extra_services: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """Check if the setting exists in the database, if it's valid and if the value is valid"""

        def check_setting(session: scoped_session, setting: str, value: Optional[str], multisite: bool = False) -> Tuple[bool, str]:
            try:
                multiple = False
                if self.SUFFIX_RX.search(setting):
                    setting = setting.rsplit("_", 1)[0]
                    multiple = True

                db_setting = session.query(Settings).filter_by(id=setting).first()

                if not db_setting:
                    for service in extra_services or []:
                        if setting.startswith(f"{service}_"):
                            db_setting = session.query(Settings).filter_by(id=setting.replace(f"{service}_", "")).first()
                            break

                    if not db_setting:
                        for service in session.query(Services).with_entities(Services.id):
                            if setting.startswith(f"{service.id}_"):
                                db_setting = session.query(Settings).filter_by(id=setting.replace(f"{service.id}_", "")).first()
                                multisite = True
                                break

                if not db_setting:
                    return False, "missing"

                if multisite and db_setting.context != "multisite":
                    return False, "not multisite"
                elif multiple and db_setting.multiple is None:
                    return False, "not multiple"

                if value is not None:
                    try:
                        if not self.__ignore_regex_check and search(db_setting.regex, value) is None:
                            return False, f"not matching regex: {db_setting.regex!r}"
                    except RegexError:
                        return False, f"invalid regex: {db_setting.regex!r}"

                return True, ""
            except (ProgrammingError, OperationalError) as e:
                return False, str(e)

        if session:
            return check_setting(session, setting, value, multisite)

        with self._db_session() as session:
            return check_setting(session, setting, value, multisite)

    def initialize_db(self, version: str, integration: str = "Unknown") -> str:
        """Initialize the database"""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.query(Metadata).get(1)

                if metadata:
                    metadata.version = version
                    metadata.integration = integration
                else:
                    session.add(
                        Metadata(
                            is_initialized=True,
                            first_config_saved=False,
                            scheduler_first_start=True,
                            version=version,
                            integration=integration,
                        )
                    )
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def get_version(self) -> str:
        """Get the database version"""
        with self._db_session() as session:
            try:
                metadata = session.query(Metadata).with_entities(Metadata.version).filter_by(id=1).first()
                if metadata:
                    return metadata.version
                return "1.6.8"
            except BaseException as e:
                return f"Error: {e}"

    def get_metadata(self) -> Dict[str, Any]:
        """Get the metadata from the database"""
        data = {
            "is_initialized": False,
            "is_pro": False,
            "pro_license": "",
            "pro_expire": None,
            "pro_status": "invalid",
            "pro_services": 0,
            "non_draft_services": 0,
            "pro_overlapped": False,
            "last_pro_check": None,
            "force_pro_update": False,
            "failover": False,
            "failover_message": "",
            "first_config_saved": False,
            "autoconf_loaded": False,
            "scheduler_first_start": True,
            "custom_configs_changed": False,
            "external_plugins_changed": False,
            "pro_plugins_changed": False,
            "instances_changed": False,
            "plugins_config_changed": {},
            "last_custom_configs_change": None,
            "last_external_plugins_change": None,
            "last_pro_plugins_change": None,
            "last_instances_change": None,
            "reload_ui_plugins": False,
            "integration": "unknown",
            "version": "1.6.8",
            "database_version": "Unknown",  # ? Extracted from the database
            "default": True,  # ? Extra field to know if the returned data is the default one
        }
        with self._db_session() as session:
            with suppress(BaseException):
                database = self.database_uri.split(":")[0].split("+")[0]
                if database == "sqlite":
                    sql_query = text("SELECT sqlite_version()")
                elif database == "oracle":
                    # Use PRODUCT_COMPONENT_VERSION which is more accessible than v$instance
                    sql_query = text("SELECT version FROM PRODUCT_COMPONENT_VERSION WHERE PRODUCT LIKE 'Oracle%' AND ROWNUM = 1")
                else:
                    sql_query = text("SELECT VERSION()")

                try:
                    data["database_version"] = (session.execute(sql_query).first() or ["unknown"])[0]
                except Exception:
                    data["database_version"] = "Unknown (access restricted)"
                metadata = session.query(Metadata).filter_by(id=1).first()
                if metadata:
                    for key in data.copy():
                        if hasattr(metadata, key) and key not in ("database_version", "default"):
                            data[key] = getattr(metadata, key)
                    data["default"] = False

                data["plugins_config_changed"] = {
                    plugin.id: plugin.last_config_change
                    for plugin in session.query(Plugins).with_entities(Plugins.id, Plugins.last_config_change).filter_by(config_changed=True).all()
                }

        return data

    def set_metadata(self, data: Dict[str, Any]) -> str:
        """Set the metadata values"""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.query(Metadata).get(1)

                if not metadata:
                    return "The metadata are not set yet, try again"

                for key, value in data.items():
                    if not hasattr(metadata, key):
                        self.logger.warning(f"Metadata key {key} does not exist")
                        continue

                    setattr(metadata, key, value)
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def checked_changes(
        self,
        changes: Optional[List[str]] = None,
        plugins_changes: Optional[Union[Literal["all"], Set[str], List[str], Tuple[str]]] = None,
        value: Optional[bool] = False,
    ) -> str:
        """Set changed bit for config, custom configs, instances and plugins"""
        changes = changes or ["config", "custom_configs", "external_plugins", "pro_plugins", "instances", "ui_plugins"]
        plugins_changes = plugins_changes or set()
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.query(Metadata).get(1)

                if not metadata:
                    return "The metadata are not set yet, try again"

                current_time = datetime.now().astimezone()

                if "config" in changes:
                    if not metadata.first_config_saved:
                        metadata.first_config_saved = True
                if "custom_configs" in changes:
                    metadata.custom_configs_changed = value
                    metadata.last_custom_configs_change = current_time
                if "external_plugins" in changes:
                    metadata.external_plugins_changed = value
                    metadata.last_external_plugins_change = current_time
                if "pro_plugins" in changes:
                    metadata.pro_plugins_changed = value
                    metadata.last_pro_plugins_change = current_time
                if "instances" in changes:
                    metadata.instances_changed = value
                    metadata.last_instances_change = current_time
                if "ui_plugins" in changes:
                    metadata.reload_ui_plugins = value

                if plugins_changes:
                    if plugins_changes == "all":
                        session.query(Plugins).update({Plugins.config_changed: value, Plugins.last_config_change: current_time})
                    else:
                        session.query(Plugins).filter(Plugins.id.in_(plugins_changes)).update(
                            {Plugins.config_changed: value, Plugins.last_config_change: current_time}
                        )

                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def init_tables(self, default_plugins: List[dict]) -> Tuple[bool, str]:
        """Initialize the database tables and return the result"""

        if self.readonly:
            return False, "The database is read-only, the changes will not be saved"

        assert self.sql_engine is not None, "The database engine is not initialized"

        try:
            Base.metadata.create_all(self.sql_engine, checkfirst=True)
        except Exception as e:
            return False, str(e)

        # Reflecting the metadata with a timeout
        current_time = datetime.now().astimezone()
        timeout_seconds = 10
        error = True
        while error:
            try:
                meta_cls = sql_metadata()
                meta_cls.reflect(self.sql_engine)
                error = False
            except Exception as e:
                if (datetime.now().astimezone() - current_time).total_seconds() > timeout_seconds:
                    raise e
                sleep(1)

        assert isinstance(meta_cls, sql_metadata)

        # Fetch old data
        old_data = {}
        with self._db_session() as session:
            for table_name in Base.metadata.tables.keys():
                old_data[table_name] = session.query(meta_cls.tables[table_name]).all()

        # Prepare structures to track changes
        to_put = []
        to_update = []
        to_delete = []

        with self._db_session() as session:
            # Convert old_data into dicts keyed by IDs or relevant unique keys.
            # For plugins:
            old_plugins = {p.id: p for p in old_data.get("bw_plugins", [])}

            # For settings:
            old_settings = {}
            for s in old_data.get("bw_settings", []):
                old_settings[(s.plugin_id, s.id)] = s

            # For selects:
            old_selects = {}
            for sel in old_data.get("bw_selects", []):
                old_selects[(sel.setting_id, self._empty_if_none(sel.value), sel.order)] = sel

            # For multiselects:
            old_multiselects = {}
            for msel in old_data.get("bw_multiselects", []):
                old_multiselects[(msel.setting_id, msel.option_id, msel.label, self._empty_if_none(msel.value), msel.order)] = msel

            # For jobs:
            old_jobs = {}
            for j in old_data.get("bw_jobs", []):
                old_jobs[(j.plugin_id, j.name)] = j

            # For plugin pages:
            old_plugin_pages = {pp.plugin_id: pp for pp in old_data.get("bw_plugin_pages", [])}

            # For CLI commands:
            old_cli_commands = {}
            for c in old_data.get("bw_cli_commands", []):
                old_cli_commands[(c.plugin_id, c.name)] = c

            # For templates:
            managed_template_ids = {t.id for t in old_data.get("bw_templates", []) if t.plugin_id}
            old_templates = {(t.plugin_id, t.id): t for t in old_data.get("bw_templates", []) if t.plugin_id}
            old_template_steps = {}
            for st in old_data.get("bw_template_steps", []):
                if st.template_id in managed_template_ids:
                    old_template_steps[(st.template_id, st.id)] = st

            old_template_settings = {}
            for ts in old_data.get("bw_template_settings", []):
                if ts.template_id in managed_template_ids:
                    old_template_settings[(ts.template_id, ts.setting_id, ts.suffix, ts.step_id, ts.order)] = ts.default

            old_template_configs = {}
            for tc in old_data.get("bw_template_custom_configs", []):
                if tc.template_id in managed_template_ids:
                    old_template_configs[(tc.template_id, tc.type, tc.name, tc.step_id, tc.order)] = tc

            # Build desired data from default_plugins
            # The following logic is similar to the original code but uses dicts/sets for comparisons.

            # Desired plugins, settings, jobs, pages, etc.
            desired_plugins = {}
            desired_settings = {}
            desired_selects = set()
            desired_multiselects = set()
            desired_jobs = {}
            desired_plugin_pages = {}
            desired_cli_commands = {}
            desired_templates = {}
            desired_template_steps = {}
            desired_template_settings = {}
            desired_template_configs = {}

            saved_settings = set()

            # Process default plugins
            for plugins in default_plugins:
                if not isinstance(plugins, list):
                    plugins = [plugins]

                for plugin in plugins:
                    if "id" not in plugin:
                        # General plugin
                        base_plugin = {
                            "id": "general",
                            "name": "General",
                            "description": "The general settings for the server",
                            "version": "0.1",
                            "stream": "partial",
                            "type": "core",
                            "method": "manual",
                            "data": None,
                            "checksum": None,
                        }
                        settings = plugin
                        jobs = []
                        commands = {}
                    else:
                        # Extract plugin details
                        settings = plugin.pop("settings", {})
                        jobs = plugin.pop("jobs", [])
                        plugin.pop("page", False)
                        commands = plugin.pop("bwcli", {})
                        if not isinstance(commands, dict):
                            commands = {}

                        base_plugin = {
                            "id": plugin["id"],
                            "name": plugin["name"],
                            "description": plugin["description"],
                            "version": plugin["version"],
                            "stream": plugin["stream"],
                            "type": plugin.get("type", "core"),
                            "method": plugin.get("method", "manual"),
                            "data": plugin.get("data"),
                            "checksum": plugin.get("checksum"),
                        }

                    # Skip unsupported plugin
                    if base_plugin["id"] == "letsencrypt_dns":
                        self.logger.warning(f'Plugin {base_plugin["id"]} is no longer supported, skipping it')
                        continue

                    # Track desired plugin
                    desired_plugins[base_plugin["id"]] = base_plugin

                    # Identify if this plugin existed before
                    plugin_found = base_plugin["id"] in old_plugins
                    if not plugin_found and old_plugins:
                        self.logger.warning(f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}" does not exist, creating it')

                    # SETTINGS
                    order = 0
                    plugin_saved_settings = set()
                    for setting_key, value in settings.items():
                        # setting_key is e.g. "my_setting"
                        # value should contain "id", "select", "multiselect", etc.
                        select_values = value.pop("select", [])
                        multiselect_values = value.pop("multiselect", [])
                        # The main setting id:
                        setting_id = setting_key
                        # Ensure plugin_id and name in the value
                        value["plugin_id"] = base_plugin["id"]
                        value["name"] = value["id"]
                        value["id"] = setting_id
                        value["order"] = order

                        desired_settings[(base_plugin["id"], setting_id)] = value
                        desired_selects.update(
                            (setting_id, self._empty_if_none(sel_val), sel_order) for sel_order, sel_val in enumerate(select_values, start=1)
                        )
                        desired_multiselects.update(
                            (setting_id, msel_val.get("id", ""), msel_val.get("label", ""), self._empty_if_none(msel_val.get("value", "")), msel_order)
                            for msel_order, msel_val in enumerate(multiselect_values, start=1)
                            if isinstance(msel_val, dict)
                        )
                        plugin_saved_settings.add(setting_id)
                        order += 1

                    saved_settings |= plugin_saved_settings

                    # JOBS
                    for job in jobs:
                        job["file_name"] = job.pop("file")
                        job["reload"] = job.get("reload", False)
                        job["run_async"] = job.pop("async", False)
                        desired_jobs[(base_plugin["id"], job["name"])] = job

                    # COMMANDS
                    for command, file_name in commands.items():
                        desired_cli_commands[(base_plugin["id"], command)] = file_name

                    # PAGES
                    plugin_path = (
                        Path("/", "usr", "share", "bunkerweb", "core", base_plugin["id"])
                        if base_plugin.get("type", "core") == "core"
                        else (
                            Path("/", "etc", "bunkerweb", "plugins", base_plugin["id"])
                            if base_plugin.get("type", "core") == "external"
                            else Path("/", "etc", "bunkerweb", "pro", "plugins", base_plugin["id"])
                        )
                    )
                    path_ui = plugin_path.joinpath("ui")
                    if path_ui.is_dir():
                        with BytesIO() as plugin_page_content:
                            with tar_open(fileobj=plugin_page_content, mode="w:gz", compresslevel=9) as tar:
                                tar.add(path_ui, arcname=path_ui.name, recursive=True)
                            plugin_page_content.seek(0)
                            checksum = bytes_hash(plugin_page_content, algorithm="sha256")
                            desired_plugin_pages[base_plugin["id"]] = {
                                "data": plugin_page_content.getvalue(),
                                "checksum": checksum,
                            }

            for plugins in default_plugins:
                if not isinstance(plugins, list):
                    plugins = [plugins]

                for plugin in plugins:
                    if "id" not in plugin:
                        # General plugin
                        base_plugin = {"id": "general", "type": "core"}
                    else:
                        base_plugin = {"id": plugin["id"], "type": plugin.get("type", "core")}

                    # Skip unsupported plugin
                    if base_plugin["id"] == "letsencrypt_dns":
                        continue

                    # TEMPLATES
                    plugin_path = (
                        Path("/", "usr", "share", "bunkerweb", "core", base_plugin["id"])
                        if base_plugin.get("type", "core") == "core"
                        else (
                            Path("/", "etc", "bunkerweb", "plugins", base_plugin["id"])
                            if base_plugin.get("type", "core") == "external"
                            else Path("/", "etc", "bunkerweb", "pro", "plugins", base_plugin["id"])
                        )
                    )
                    templates_path = plugin_path.joinpath("templates")
                    if templates_path.is_dir():
                        for template_file in templates_path.iterdir():
                            if template_file.is_dir():
                                continue
                            try:
                                template_data = loads(template_file.read_text())
                            except JSONDecodeError:
                                self.logger.error(
                                    f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template file "{template_file}" is not valid JSON'
                                )
                                continue

                            template_id = template_file.stem
                            desired_templates[(base_plugin["id"], template_id)] = {
                                "name": template_data.get("name", template_id),
                                "method": plugin.get("method", "manual"),
                            }

                            # Steps
                            found_steps = set()
                            steps_settings = {}
                            steps_configs = {}
                            for step_id, step in enumerate(template_data.get("steps", []), start=1):
                                desired_template_steps[(template_id, step_id)] = {"title": step["title"], "subtitle": step["subtitle"]}
                                found_steps.add(step_id)
                                for sett in step.get("settings", []):
                                    if step_id not in steps_settings:
                                        steps_settings[step_id] = []
                                    steps_settings[step_id].append(sett)
                                for conf in step.get("configs", []):
                                    if step_id not in steps_configs:
                                        steps_configs[step_id] = []
                                    steps_configs[step_id].append(conf)

                            # Template-level settings
                            order = 0
                            for setting, default in template_data.get("settings", {}).items():
                                # Check restrictions and existence
                                if setting in getattr(self, "RESTRICTED_TEMPLATE_SETTINGS", []):
                                    self.logger.error(
                                        f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id} has restricted setting "{setting}", skipping'
                                    )
                                    continue
                                # Check if setting exists globally
                                setting_id = setting
                                suffix = 0
                                if self.SUFFIX_RX.search(setting):
                                    setting_id, suffix = setting.rsplit("_", 1)
                                    suffix = int(suffix)  # noqa: FURB123
                                if setting_id not in saved_settings:
                                    self.logger.error(
                                        f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id} has invalid setting "{setting}", skipping'
                                    )
                                    continue

                                # Check if belongs to a step
                                step_id = None
                                for sid, step_set_list in steps_settings.items():
                                    if setting in step_set_list:
                                        step_id = sid
                                        break

                                if not step_id:
                                    self.logger.error(
                                        f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id}`s setting "{setting}" doesn\'t belong to a step, skipping'
                                    )
                                    continue

                                desired_template_settings[(template_id, setting_id, suffix, step_id, order)] = default
                                order += 1

                            # Template-level configs
                            order = 0
                            for config in template_data.get("configs", []):
                                try:
                                    config_type, config_name = config.split("/", 1)
                                except ValueError:
                                    self.logger.error(
                                        f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id} has invalid config "{config}"'
                                    )
                                    continue
                                if config_type.replace("-", "_") not in self.MULTISITE_CUSTOM_CONFIG_TYPES:
                                    self.logger.error(
                                        f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id} has invalid config type "{config_type}"'
                                    )
                                    continue

                                config_file = templates_path.joinpath(template_id, "configs", config_type, config_name)
                                if not config_file.is_file():
                                    self.logger.error(
                                        f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id} missing config "{config}"'
                                    )
                                    continue

                                content = config_file.read_bytes()
                                config_type = config_type.strip().replace("-", "_").lower()
                                checksum = bytes_hash(content, algorithm="sha256")
                                config_name_clean = config_name.removesuffix(".conf")

                                # Check if belongs to a step
                                step_id = None
                                for sid, step_conf_list in steps_configs.items():
                                    if config in step_conf_list:
                                        step_id = sid
                                        break

                                if not step_id:
                                    self.logger.error(
                                        f'{base_plugin.get("type", "core").title()} Plugin "{base_plugin["id"]}"\'s Template {template_id}`s config "{config}" doesn\'t belong to a step, skipping'
                                    )
                                    continue

                                desired_template_configs[(template_id, config_type, config_name_clean, step_id, order)] = {
                                    "data": content,
                                    "checksum": checksum,
                                }
                                order += 1

            # Compute differences for PLUGINS
            old_plugin_ids = set(old_plugins.keys())
            new_plugin_ids = set(desired_plugins.keys())

            # Plugins to create
            for pid in new_plugin_ids - old_plugin_ids:
                p = desired_plugins[pid]
                to_put.append(Plugins(**p))

            # Plugins to update
            for pid in old_plugin_ids & new_plugin_ids:
                old_p = old_plugins[pid]
                new_p = desired_plugins[pid]
                attrs_to_check = ("name", "description", "version", "stream", "type", "method", "data", "checksum")
                if any(getattr(old_p, attr, None) != new_p.get(attr) for attr in attrs_to_check) and old_p.method == new_p.get("method", "manual"):
                    to_update.append({"type": "plugin", "filter": {"id": pid}, "data": {k: new_p[k] for k in attrs_to_check if k in new_p}})

            # Plugins to delete
            for pid in old_plugin_ids - new_plugin_ids:
                old_p = old_plugins[pid]
                if old_p.method == "manual":
                    self.logger.warning(f'{old_p.type.title()} plugin "{pid}" has been removed, deleting it')
                    to_delete.append({"type": "plugin", "filter": {"id": pid}})

            # SETTINGS
            old_setting_keys = set(old_settings.keys())
            new_setting_keys = set(desired_settings.keys())
            for sk in new_setting_keys - old_setting_keys:
                to_put.append(Settings(**desired_settings[sk]))

            for sk in old_setting_keys & new_setting_keys:
                old_s = old_settings[sk]
                new_s = desired_settings[sk]
                # Check changes excluding order since we always set order
                changed = any(getattr(old_s, k, None) != new_s.get(k) for k in new_s.keys())
                if changed:
                    to_update.append({"type": "setting", "filter": {"plugin_id": sk[0], "id": sk[1]}, "data": new_s})

            # Settings to delete
            for sk in old_setting_keys - new_setting_keys:
                to_delete.append({"type": "setting", "filter": {"plugin_id": sk[0], "id": sk[1]}})
                if sk[1] == "MODSECURITY_CRS_PLUGIN_URLS":
                    self.logger.warning("MODSECURITY_CRS_PLUGIN_URLS setting has been renamed to MODSECURITY_CRS_PLUGINS, migrating data")
                    to_update.extend(
                        [
                            {
                                "type": "global_value",
                                "filter": {"setting_id": "MODSECURITY_CRS_PLUGIN_URLS"},
                                "data": {"setting_id": "MODSECURITY_CRS_PLUGINS"},
                            },
                            {
                                "type": "service_setting",
                                "filter": {"setting_id": "MODSECURITY_CRS_PLUGIN_URLS"},
                                "data": {"setting_id": "MODSECURITY_CRS_PLUGINS"},
                            },
                        ]
                    )

            # SELECTS
            old_select_keys = set(old_selects.keys())
            # desired_selects is a set of (setting_id, value, order)
            # We must correlate with known settings. If setting_id belongs to a plugin_id?
            # Original code just handled removing selects not present. We'll trust that logic:

            # First delete all selects for setting_ids that are being updated
            settings_being_updated = set()
            settings_being_updated.update({sel[0] for sel in desired_selects})

            for setting_id in settings_being_updated:
                to_delete.append({"type": "select", "filter": {"setting_id": setting_id}})

            # Now insert all new selects
            for sel in desired_selects:
                to_put.append(Selects(setting_id=sel[0], value=self._empty_if_none(sel[1]), order=sel[2]))

            # Handle multiselects similar to selects
            settings_being_updated_multiselects = set()
            settings_being_updated_multiselects.update({msel[0] for msel in desired_multiselects})

            for setting_id in settings_being_updated_multiselects:
                to_delete.append({"type": "multiselect", "filter": {"setting_id": setting_id}})

            # Now insert all new multiselects
            for msel in desired_multiselects:
                to_put.append(Multiselects(setting_id=msel[0], option_id=msel[1], label=msel[2], value=self._empty_if_none(msel[3]), order=msel[4]))

            # Delete old selects not needed (for settings not in our updated list)
            for sel in old_select_keys - desired_selects:
                if sel[0] not in settings_being_updated:  # Only delete if not already handled above
                    to_delete.append({"type": "select", "filter": {"setting_id": sel[0], "value": self._empty_if_none(sel[1]), "order": sel[2]}})

            # JOBS
            old_job_keys = set(old_jobs.keys())
            new_job_keys = set(desired_jobs.keys())

            for jk in new_job_keys - old_job_keys:
                job = desired_jobs[jk]
                to_put.append(Jobs(plugin_id=jk[0], **job))

            for jk in old_job_keys & new_job_keys:
                old_j = old_jobs[jk]
                new_j = desired_jobs[jk]
                changed = any(getattr(old_j, k, None) != new_j.get(k) for k in new_j.keys())
                if changed:
                    to_update.append({"type": "job", "filter": {"plugin_id": jk[0], "name": jk[1]}, "data": new_j})

            for jk in old_job_keys - new_job_keys:
                to_delete.append({"type": "job", "filter": {"plugin_id": jk[0], "name": jk[1]}})

            # PLUGIN PAGES
            old_page_ids = set(old_plugin_pages.keys())
            new_page_ids = set(desired_plugin_pages.keys())

            for pid in new_page_ids - old_page_ids:
                pp = desired_plugin_pages[pid]
                to_put.append(Plugin_pages(plugin_id=pid, data=pp["data"], checksum=pp["checksum"]))

            for pid in old_page_ids & new_page_ids:
                old_pp = old_plugin_pages[pid]
                new_pp = desired_plugin_pages[pid]
                if old_pp.checksum != new_pp["checksum"]:
                    to_update.append({"type": "plugin_page", "filter": {"plugin_id": pid}, "data": {"data": new_pp["data"], "checksum": new_pp["checksum"]}})

            for pid in old_page_ids - new_page_ids:
                to_delete.append({"type": "plugin_page", "filter": {"plugin_id": pid}})

            # CLI COMMANDS
            old_command_keys = set(old_cli_commands.keys())
            new_command_keys = set(desired_cli_commands.keys())

            for ck in new_command_keys - old_command_keys:
                to_put.append(Bw_cli_commands(name=ck[1], plugin_id=ck[0], file_name=desired_cli_commands[ck]))

            for ck in old_command_keys & new_command_keys:
                old_c = old_cli_commands[ck]
                new_file = desired_cli_commands[ck]
                if old_c.file_name != new_file:
                    to_update.append({"type": "cli_command", "filter": {"plugin_id": ck[0], "name": ck[1]}, "data": {"file_name": new_file}})

            for ck in old_command_keys - new_command_keys:
                to_delete.append({"type": "cli_command", "filter": {"plugin_id": ck[0], "name": ck[1]}})

            # TEMPLATES
            old_tmpl_keys = set(old_templates.keys())
            new_tmpl_keys = set(desired_templates.keys())

            for tk in new_tmpl_keys - old_tmpl_keys:
                current_time = datetime.now().astimezone()
                to_put.append(
                    Templates(
                        id=tk[1],
                        plugin_id=tk[0],
                        name=desired_templates[tk]["name"],
                        method=desired_templates[tk]["method"],
                        creation_date=current_time,
                        last_update=current_time,
                    )
                )

            for tk in old_tmpl_keys & new_tmpl_keys:
                old_t = old_templates[tk]
                new_t = desired_templates[tk]
                if old_t.name != new_t["name"]:
                    to_update.append(
                        {
                            "type": "template",
                            "filter": {"plugin_id": tk[0], "id": tk[1]},
                            "data": {"name": new_t["name"], "method": new_t["method"], "last_update": datetime.now().astimezone()},
                        }
                    )

            for tk in old_tmpl_keys - new_tmpl_keys:
                to_delete.append({"type": "template", "filter": {"plugin_id": tk[0], "id": tk[1]}})

            # TEMPLATE STEPS
            old_step_keys = set(old_template_steps.keys())
            new_step_keys = set(desired_template_steps.keys())

            for st in new_step_keys - old_step_keys:
                to_put.append(Template_steps(id=st[1], template_id=st[0], **desired_template_steps[st]))

            for st in old_step_keys & new_step_keys:
                old_stp = old_template_steps[st]
                new_stp = desired_template_steps[st]
                if old_stp.title != new_stp["title"] or old_stp.subtitle != new_stp["subtitle"]:
                    to_update.append(
                        {
                            "type": "template_step",
                            "filter": {"template_id": st[0], "id": st[1]},
                            "data": {"title": new_stp["title"], "subtitle": new_stp["subtitle"]},
                        }
                    )

            for st in old_step_keys - new_step_keys:
                to_delete.append({"type": "template_step", "filter": {"template_id": st[0], "id": st[1]}})

            # TEMPLATE SETTINGS
            old_ts_keys = set(old_template_settings.keys())
            new_ts_keys = set(desired_template_settings.keys())

            for tsk in new_ts_keys - old_ts_keys:
                template_id, setting_id, suffix, step_id, order = tsk
                default = desired_template_settings[tsk]
                to_put.append(
                    Template_settings(
                        template_id=template_id,
                        setting_id=setting_id,
                        suffix=suffix,
                        step_id=step_id,
                        default=default,
                        order=order,
                    )
                )

            for tsk in old_ts_keys & new_ts_keys:
                old_ts_val = old_template_settings[tsk]
                new_default = desired_template_settings[tsk]
                if old_ts_val != new_default:
                    template_id, setting_id, suffix, step_id, order = tsk
                    filter_data = {"template_id": template_id, "setting_id": setting_id, "step_id": step_id}
                    if suffix is not None:
                        # Not all queries handle suffix well. If suffix is defined, add to filter:
                        filter_data["suffix"] = suffix
                    to_update.append(
                        {
                            "type": "template_setting",
                            "filter": filter_data,
                            "data": {"default": self._empty_if_none(new_default), "suffix": suffix},
                        }
                    )

            for tsk in old_ts_keys - new_ts_keys:
                template_id, setting_id, suffix, step_id, order = tsk
                filter_data = {"template_id": template_id, "setting_id": setting_id, "step_id": step_id}
                if suffix is not None:
                    filter_data["suffix"] = suffix
                to_delete.append({"type": "template_setting", "filter": filter_data})

            # TEMPLATE CONFIGS
            old_tc_keys = set(old_template_configs.keys())
            new_tc_keys = set(desired_template_configs.keys())

            for tck in new_tc_keys - old_tc_keys:
                template_id, ctype, cname, step_id, order = tck
                conf_data = desired_template_configs[tck]
                to_put.append(
                    Template_custom_configs(
                        template_id=template_id,
                        type=ctype,
                        name=cname,
                        data=conf_data["data"],
                        checksum=conf_data["checksum"],
                        step_id=step_id,
                        order=order,
                    )
                )

            for tck in old_tc_keys & new_tc_keys:
                old_tc_obj = old_template_configs[tck]
                new_tc_obj = desired_template_configs[tck]
                if old_tc_obj.checksum != new_tc_obj["checksum"]:
                    template_id, ctype, cname, step_id, order = tck
                    filter_data = {"template_id": template_id, "name": cname, "type": ctype, "step_id": step_id}
                    to_update.append(
                        {
                            "type": "template_config",
                            "filter": filter_data,
                            "data": {"data": new_tc_obj["data"], "checksum": new_tc_obj["checksum"]},
                        }
                    )

            for tck in old_tc_keys - new_tc_keys:
                template_id, ctype, cname, step_id, order = tck
                filter_data = {"template_id": template_id, "name": cname, "type": ctype, "step_id": step_id}
                to_delete.append({"type": "template_config", "filter": filter_data})

            # APPLY CHANGES
            try:
                # Apply deletes
                for delete in to_delete:
                    t = delete["type"]
                    if t == "setting":
                        session.query(Settings).filter_by(**delete["filter"]).delete()
                    elif t == "global_value":
                        session.query(Global_values).filter_by(**delete["filter"]).delete()
                    elif t == "service_setting":
                        session.query(Services_settings).filter_by(**delete["filter"]).delete()
                    elif t == "job":
                        session.query(Jobs).filter_by(**delete["filter"]).delete()
                    elif t == "job_cache":
                        session.query(Jobs_cache).filter_by(**delete["filter"]).delete()
                    elif t == "job_run":
                        session.query(Jobs_runs).filter_by(**delete["filter"]).delete()
                    elif t == "plugin_page":
                        session.query(Plugin_pages).filter_by(**delete["filter"]).delete()
                    elif t == "cli_command":
                        session.query(Bw_cli_commands).filter_by(**delete["filter"]).delete()
                    elif t == "template":
                        session.query(Templates).filter_by(**delete["filter"]).delete()
                    elif t == "template_step":
                        session.query(Template_steps).filter_by(**delete["filter"]).delete()
                    elif t == "template_setting":
                        session.query(Template_settings).filter_by(**delete["filter"]).delete()
                    elif t == "template_config":
                        session.query(Template_custom_configs).filter_by(**delete["filter"]).delete()
                    elif t == "select":
                        session.query(Selects).filter_by(**delete["filter"]).delete()
                    elif t == "multiselect":
                        session.query(Multiselects).filter_by(**delete["filter"]).delete()
                    elif t == "plugin":
                        session.query(Plugins).filter_by(**delete["filter"]).delete()

                # Insert parents before children to avoid FK errors on some DBs.
                to_put_by_type = {
                    "plugins": [],
                    "settings": [],
                    "selects": [],
                    "multiselects": [],
                    "templates": [],
                    "template_steps": [],
                    "template_settings": [],
                    "template_configs": [],
                    "jobs": [],
                    "plugin_pages": [],
                    "cli_commands": [],
                    "other": [],
                }

                for item in to_put:
                    if isinstance(item, Plugins):
                        to_put_by_type["plugins"].append(item)
                    elif isinstance(item, Settings):
                        to_put_by_type["settings"].append(item)
                    elif isinstance(item, Selects):
                        to_put_by_type["selects"].append(item)
                    elif isinstance(item, Multiselects):
                        to_put_by_type["multiselects"].append(item)
                    elif isinstance(item, Templates):
                        to_put_by_type["templates"].append(item)
                    elif isinstance(item, Template_steps):
                        to_put_by_type["template_steps"].append(item)
                    elif isinstance(item, Template_settings):
                        to_put_by_type["template_settings"].append(item)
                    elif isinstance(item, Template_custom_configs):
                        to_put_by_type["template_configs"].append(item)
                    elif isinstance(item, Jobs):
                        to_put_by_type["jobs"].append(item)
                    elif isinstance(item, Plugin_pages):
                        to_put_by_type["plugin_pages"].append(item)
                    elif isinstance(item, Bw_cli_commands):
                        to_put_by_type["cli_commands"].append(item)
                    else:
                        to_put_by_type["other"].append(item)

                if to_put_by_type["plugins"]:
                    session.add_all(to_put_by_type["plugins"])
                if to_put_by_type["settings"]:
                    session.add_all(to_put_by_type["settings"])
                if to_put_by_type["plugins"] or to_put_by_type["settings"]:
                    session.flush()

                if to_put_by_type["selects"]:
                    session.add_all(to_put_by_type["selects"])
                if to_put_by_type["multiselects"]:
                    session.add_all(to_put_by_type["multiselects"])

                if to_put_by_type["templates"]:
                    session.add_all(to_put_by_type["templates"])
                if to_put_by_type["template_steps"]:
                    session.add_all(to_put_by_type["template_steps"])
                if to_put_by_type["template_settings"]:
                    session.add_all(to_put_by_type["template_settings"])
                if to_put_by_type["template_configs"]:
                    session.add_all(to_put_by_type["template_configs"])

                if to_put_by_type["jobs"]:
                    session.add_all(to_put_by_type["jobs"])
                if to_put_by_type["plugin_pages"]:
                    session.add_all(to_put_by_type["plugin_pages"])
                if to_put_by_type["cli_commands"]:
                    session.add_all(to_put_by_type["cli_commands"])
                if to_put_by_type["other"]:
                    session.add_all(to_put_by_type["other"])

                # Apply updates
                for update in to_update:
                    t = update["type"]
                    if t == "setting":
                        session.query(Settings).filter_by(**update["filter"]).update(update["data"])
                    elif t == "job":
                        session.query(Jobs).filter_by(**update["filter"]).update(update["data"])
                    elif t == "plugin_page":
                        session.query(Plugin_pages).filter_by(**update["filter"]).update(update["data"])
                    elif t == "cli_command":
                        session.query(Bw_cli_commands).filter_by(**update["filter"]).update(update["data"])
                    elif t == "template_step":
                        session.query(Template_steps).filter_by(**update["filter"]).update(update["data"])
                    elif t == "template_setting":
                        session.query(Template_settings).filter_by(**update["filter"]).update(update["data"])
                    elif t == "template_config":
                        session.query(Template_custom_configs).filter_by(**update["filter"]).update(update["data"])
                    elif t == "plugin":
                        session.query(Plugins).filter_by(**update["filter"]).update(update["data"])
                    elif t == "template":
                        session.query(Templates).filter_by(**update["filter"]).update(update["data"])
                    elif t == "global_value":
                        session.query(Global_values).filter_by(**update["filter"]).update(update["data"])
                    elif t == "service_setting":
                        session.query(Services_settings).filter_by(**update["filter"]).update(update["data"])

                session.commit()
            except SQLAlchemyError as e:
                self.logger.debug(format_exc())
                session.rollback()
                return False, str(e)

        # ? Check if all templates settings are valid
        with self._db_session() as session:
            for template_setting in session.query(Template_settings):
                success, err = self.is_valid_setting(
                    f"{template_setting.setting_id}_{template_setting.suffix}" if template_setting.suffix else template_setting.setting_id,
                    value=template_setting.default,
                    multisite=True,
                    session=session,
                )

                if not success:
                    self.logger.warning(
                        f'Template "{template_setting.template_id}"\'s Setting "{template_setting.setting_id}" isn\'t a valid template setting ({err}), deleting it'
                    )
                    session.query(Template_settings).filter_by(id=template_setting.id).delete()

            try:
                session.commit()
            except BaseException as e:
                return False, str(e)

        if not to_put and not to_update and not to_delete:
            return False, ""
        return True, ""

    def save_config(self, config: Dict[str, Any], method: str, changed: Optional[bool] = True) -> Union[str, Set[str]]:
        """Save the config in the database"""
        to_put = []
        to_update = []
        to_delete = []
        changed_plugins = set()
        changed_services = False
        service_template_change = False

        db_config = {}
        if method == "autoconf":
            db_config = self.get_non_default_settings(with_drafts=True)

        def is_default_value(val: str, key: str, setting: dict, template_default: Optional[str] = None, suffix: int = 0, is_global: bool = False) -> bool:
            """
            Determines whether the provided value is considered the default value.
            This function checks the value 'val' against an expected default based on several conditions:
            1. If a 'template_default' is provided (i.e., not None), then the expected default is
                this template value, and the function returns True only if 'val' exactly matches it.
            2. If 'template_default' is None:
                - If the configuration key 'key' is not present in both 'config' and 'db_config',
                  then the expected default is defined by setting["default"].
                - Otherwise, the expected default should be one of the values associated with 'key'
                  in either 'config' or 'db_config'.
            """
            if template_default is not None:
                return val == template_default

            if (is_global and not suffix) or (key not in config and key not in db_config):
                return val == setting["default"]

            if is_global:
                return False

            # Acceptable values are the ones from either config or db_config.
            return val in (config.get(key), db_config.get(key)) if not suffix else val in (config.get(f"{key}_{suffix}"), db_config.get(f"{key}_{suffix}"))

        def check_value(key: str, value: str, setting: dict, template_default: Optional[str], suffix: int, is_global: bool = False) -> bool:
            """
            Determine if a configuration value should be considered default.

            Immediately returns False for the key "SERVER_NAME". For non-suffix values, if a template default
            is provided, the value must match it; otherwise, the value must satisfy is_default_value using the
            original key. For suffix values, if the base value (using key) is not default, the check passes;
            otherwise, the suffix value must also be default (using original_key).
            """
            if key == "SERVER_NAME":
                return False

            return is_default_value(value, key, setting, template_default, suffix, is_global)

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            self.logger.debug(f"Saving config for method {method}")

            self.logger.debug(f"Cleaning up {method} old global settings")
            # Collect global settings to delete
            global_settings_to_delete = []
            for db_global_config in session.query(Global_values).filter_by(method=method).all():
                key = db_global_config.setting_id
                if db_global_config.suffix:
                    key = f"{key}_{db_global_config.suffix}"

                try:
                    # Check if the setting should be deleted based on key presence
                    should_delete = key not in config and (db_global_config.suffix or f"{key}_0" not in config)

                    if should_delete:
                        global_settings_to_delete.append(db_global_config)
                        # Get plugin ID with safer query and null checking
                        plugin_query = session.query(Settings).with_entities(Settings.plugin_id).filter_by(id=db_global_config.setting_id).first()
                        if plugin_query:
                            plugin_id = plugin_query.plugin_id
                            if plugin_id:
                                changed_plugins.add(plugin_id)

                        # Handle special SERVER_NAME case
                        if key == "SERVER_NAME":
                            changed_services = True
                except Exception as e:
                    self.logger.warning(f"Error processing global config {db_global_config.setting_id}: {e}")
                    continue

            self.logger.debug(f"Cleaning up {method} old services settings")
            # Collect service settings to delete
            service_settings_to_delete = []
            for db_service_config in session.query(Services_settings).filter_by(method=method).all():
                key = f"{db_service_config.service_id}_{db_service_config.setting_id}"
                if db_service_config.suffix:
                    key = f"{key}_{db_service_config.suffix}"

                try:
                    # Check if the setting should be deleted based on key presence
                    should_delete = key not in config and (db_service_config.suffix or f"{key}_0" not in config)

                    if should_delete:
                        service_settings_to_delete.append(db_service_config)
                        # Get plugin ID with safer query and null checking
                        plugin_query = session.query(Settings).with_entities(Settings.plugin_id).filter_by(id=db_service_config.setting_id).first()
                        if plugin_query:
                            plugin_id = plugin_query.plugin_id
                            if plugin_id:
                                changed_plugins.add(plugin_id)

                        # Handle special SERVER_NAME case
                        if key in ("SERVER_NAME", f"{db_service_config.service_id}_SERVER_NAME"):
                            changed_services = True
                        elif key in ("USE_TEMPLATE", f"{db_service_config.service_id}_USE_TEMPLATE"):
                            service_template_change = True
                except Exception as e:
                    self.logger.warning(f"Error processing service config {db_service_config.setting_id}: {e}")
                    continue

            if config:
                config.pop("DATABASE_URI", None)

                self.logger.debug("Checking if the services have changed")
                db_services = session.query(Services).with_entities(Services.id, Services.method, Services.is_draft).all()
                db_ids: Dict[str, dict] = {service.id: {"method": service.method, "is_draft": service.is_draft} for service in db_services}
                missing_ids = []
                services = config.get("SERVER_NAME", [])

                if isinstance(services, str):
                    services = services.strip().split()

                services = [service for service in services if service]  # Clean up empty strings

                if db_services:
                    missing_ids = [
                        service.id
                        for service in db_services
                        if (service.method == method or (service.method in ("ui", "api") and method in ("ui", "api"))) and service.id not in services
                    ]

                    if missing_ids:
                        self.logger.debug(f"Removing {len(missing_ids)} services that are no longer in the list")
                        # Remove services that are no longer in the list
                        session.query(Services).filter(Services.id.in_(missing_ids)).delete(synchronize_session=False)
                        session.query(Services_settings).filter(Services_settings.service_id.in_(missing_ids)).delete(synchronize_session=False)
                        session.query(Custom_configs).filter(Custom_configs.service_id.in_(missing_ids)).delete(synchronize_session=False)
                        session.query(Jobs_cache).filter(Jobs_cache.service_id.in_(missing_ids)).delete(synchronize_session=False)
                        session.query(Metadata).filter_by(id=1).update(
                            {Metadata.custom_configs_changed: True, Metadata.last_custom_configs_change: datetime.now().astimezone()}
                        )
                        changed_services = True
                        if any(config.get(f"{sid}_USE_TEMPLATE", "") for sid in missing_ids):
                            service_template_change = True

                self.logger.debug("Checking if the drafts have changed")
                drafts = {service for service in services if config.pop(f"{service}_IS_DRAFT", "no") == "yes"}
                db_drafts = {service.id for service in db_services if service.is_draft}

                if db_drafts:
                    missing_drafts = [
                        service.id
                        for service in db_services
                        if (service.method == method or (service.method in ("ui", "api") and method in ("ui", "api")))
                        and service.id not in drafts
                        and service.id not in missing_ids
                    ]

                    if missing_drafts:
                        self.logger.debug(f"Removing {len(missing_drafts)} drafts that are no longer in the list")
                        # Update services to remove draft status
                        session.query(Services).filter(Services.id.in_(missing_drafts)).update({Services.is_draft: False}, synchronize_session=False)
                        changed_services = True

                for draft in drafts:
                    if draft not in db_drafts:
                        current_time = datetime.now().astimezone()
                        if draft not in db_ids:
                            self.logger.debug(f"Adding draft {draft}")
                            to_put.append(Services(id=draft, method=method, is_draft=True, creation_date=current_time, last_update=current_time))
                            db_ids[draft] = {"method": method, "is_draft": True}
                        elif db_ids[draft]["method"] == method or (db_ids[draft]["method"] in ("ui", "api") and method in ("ui", "api")):
                            self.logger.debug(f"Updating draft {draft}")
                            to_update.append({"model": Services, "filter": {"id": draft}, "values": {"is_draft": True, "last_update": current_time}})
                            changed_services = True

                template = config.get("USE_TEMPLATE", "")

                if config.get("MULTISITE", "no") == "yes":
                    self.logger.debug("Checking if the multisite settings have changed")

                    service_configs = defaultdict(dict)
                    global_config = {}

                    services_set = set(services)

                    for key, value in config.items():
                        matched = False
                        underscore_pos = 0
                        while True:
                            underscore_pos = key.find("_", underscore_pos)
                            if underscore_pos == -1:
                                break
                            potential_service = key[:underscore_pos]
                            if potential_service in services_set:
                                stripped_key = key[underscore_pos + 1 :]  # noqa: E203
                                service_configs[potential_service][stripped_key] = value
                                matched = True
                                break
                            underscore_pos += 1
                        if not matched:
                            global_config[key] = value

                    # Collect necessary data before threading
                    settings_data = session.query(Settings.id, Settings.default, Settings.plugin_id).all()
                    settings_dict = {s.id: {"default": self._empty_if_none(s.default), "plugin_id": s.plugin_id} for s in settings_data}

                    # Collect existing service settings
                    existing_service_settings = session.query(
                        Services_settings.service_id, Services_settings.setting_id, Services_settings.suffix, Services_settings.value, Services_settings.method
                    ).all()
                    existing_service_settings_dict = {
                        (s.service_id, s.setting_id, s.suffix or 0): {"value": self._empty_if_none(s.value), "method": s.method}
                        for s in existing_service_settings
                    }

                    # Collect template settings
                    templates = {}
                    for template in (
                        session.query(Template_settings)
                        .with_entities(Template_settings.template_id, Template_settings.setting_id, Template_settings.suffix, Template_settings.default)
                        .order_by(Template_settings.order)
                    ):
                        if template.template_id not in templates:
                            templates[template.template_id] = {}
                        templates[template.template_id][(template.setting_id, template.suffix or 0)] = template.default

                    def process_service(server_name: str, service_config: Dict[str, str], db_ids: Dict[str, dict]):
                        local_to_put = []
                        local_to_update = []
                        local_to_delete = []
                        local_changed_plugins = set()
                        local_changed_services = False
                        local_service_template_change = False

                        service_template = service_config.get("USE_TEMPLATE", template)

                        for original_key, value in service_config.items():
                            suffix = 0
                            key = deepcopy(original_key)
                            if self.SUFFIX_RX.search(key):
                                suffix = int(key.split("_")[-1])
                                key = key[: -len(str(suffix)) - 1]

                            setting = settings_dict.get(key)
                            if not setting:
                                self.logger.debug(f"Setting {key} does not exist")
                                continue

                            if server_name not in db_ids:
                                self.logger.debug(f"Adding service {server_name}")
                                current_time = datetime.now().astimezone()
                                local_to_put.append(
                                    Services(
                                        id=server_name, method=method, is_draft=server_name in drafts, creation_date=current_time, last_update=current_time
                                    )
                                )
                                db_ids[server_name] = {"method": method, "is_draft": server_name in drafts}
                                if server_name not in drafts:
                                    local_changed_services = True

                            service_setting = existing_service_settings_dict.get((server_name, key, suffix))

                            template_setting_default = None
                            if service_template:
                                template_setting_default = templates.get(service_template, {}).get((key, suffix))
                                local_service_template_change = True

                            # Determine if we need to add, update, or delete
                            if not service_setting:
                                if check_value(key, value, setting, template_setting_default, suffix):
                                    continue

                                self.logger.debug(f"Adding setting {key} for service {server_name}")
                                local_changed_plugins.add(setting["plugin_id"])
                                local_to_put.append(Services_settings(service_id=server_name, setting_id=key, value=value, suffix=suffix, method=method))
                                # Update Services.last_update
                                local_to_update.append(
                                    {"model": Services, "filter": {"id": server_name}, "values": {"last_update": datetime.now().astimezone()}}
                                )
                                if key == "SERVER_NAME":
                                    local_changed_services = True
                            elif (service_setting["value"] != value and self._methods_are_compatible(method, service_setting["method"])) or (
                                method == "autoconf" and service_setting["method"] != "autoconf"
                            ):
                                local_changed_plugins.add(setting["plugin_id"])

                                if check_value(key, value, setting, template_setting_default, suffix):
                                    self.logger.debug(f"Removing setting {key} for service {server_name}")
                                    local_to_delete.append(
                                        {"model": Services_settings, "filter": {"service_id": server_name, "setting_id": key, "suffix": suffix}}
                                    )
                                    continue

                                self.logger.debug(f"Updating setting {key} for service {server_name}")
                                local_to_update.extend(
                                    [
                                        {
                                            "model": Services_settings,
                                            "filter": {"service_id": server_name, "setting_id": key, "suffix": suffix},
                                            "values": {"value": self._empty_if_none(value), "method": method},
                                        },
                                        {"model": Services, "filter": {"id": server_name}, "values": {"last_update": datetime.now().astimezone()}},
                                    ]
                                )
                                if key == "SERVER_NAME":
                                    local_changed_services = True

                        return local_to_put, local_to_update, local_to_delete, local_changed_plugins, local_changed_services, local_service_template_change

                    def process_global_settings(global_config: Dict[str, str]):
                        local_to_put = []
                        local_to_update = []
                        local_to_delete = []
                        local_changed_plugins = set()
                        local_service_template_change = False

                        for original_key, value in global_config.items():
                            suffix = 0
                            key = deepcopy(original_key)
                            if self.SUFFIX_RX.search(key):
                                suffix = int(key.split("_")[-1])
                                key = key[: -len(str(suffix)) - 1]

                            setting = settings_dict.get(key)
                            if not setting:
                                self.logger.debug(f"Setting {key} does not exist")
                                continue

                            global_value = session.query(Global_values.value, Global_values.method).filter_by(setting_id=key, suffix=suffix).first()

                            template_setting_default = None
                            if template:
                                template_setting_default = templates.get(template, {}).get((key, suffix))
                                local_service_template_change = True

                            if not global_value:
                                if check_value(key, value, setting, template_setting_default, suffix, True):
                                    continue

                                self.logger.debug(f"Adding global setting {key}")
                                local_changed_plugins.add(setting["plugin_id"])
                                local_to_put.append(Global_values(setting_id=key, value=value, suffix=suffix, method=method))
                            elif (global_value.value != value and self._methods_are_compatible(method, global_value.method)) or (
                                method == "autoconf" and global_value.method != "autoconf"
                            ):
                                local_changed_plugins.add(setting["plugin_id"])

                                if check_value(key, value, setting, template_setting_default, suffix, True):
                                    self.logger.debug(f"Removing global setting {key}")
                                    local_to_delete.append({"model": Global_values, "filter": {"setting_id": key, "suffix": suffix}})
                                    continue

                                self.logger.debug(f"Updating global setting {key}")
                                local_to_update.append(
                                    {
                                        "model": Global_values,
                                        "filter": {"setting_id": key, "suffix": suffix},
                                        "values": {"value": self._empty_if_none(value), "method": method},
                                    }
                                )

                        return local_to_put, local_to_update, local_to_delete, local_changed_plugins, False, local_service_template_change

                    # Use ThreadPoolExecutor to process services in parallel
                    with ThreadPoolExecutor() as executor:
                        futures = [
                            executor.submit(process_service, service_name, service_config, db_ids) for service_name, service_config in service_configs.items()
                        ]

                        # Process global settings in another thread or the main thread
                        futures.append(executor.submit(process_global_settings, global_config))

                        # Collect results from threads
                        for future in as_completed(futures):
                            try:
                                ret_to_put, ret_to_update, ret_to_delete, ret_changed_plugins, ret_changed_services, ret_service_template_change = (
                                    future.result()
                                )
                                to_put.extend(ret_to_put)
                                to_update.extend(ret_to_update)
                                to_delete.extend(ret_to_delete)
                                changed_plugins.update(ret_changed_plugins)
                                if not changed_services:
                                    changed_services = ret_changed_services
                                if not service_template_change:
                                    service_template_change = ret_service_template_change
                            except Exception as e:
                                self.logger.error(f"Thread raised an exception: {e}")

                else:
                    # Non-multisite configuration
                    self.logger.debug("Checking if non-multisite settings have changed")

                    server_name = config.get("SERVER_NAME", None)
                    if template and server_name is None:
                        server_name = (
                            session.query(Template_settings)
                            .with_entities(Template_settings.value)
                            .filter_by(template_id=template, setting_id="SERVER_NAME")
                            .first()
                        )

                    if server_name is None or server_name:
                        server_name = server_name or "www.example.com"
                        first_server = server_name.split(" ")[0]

                        if not session.query(Services).with_entities(Services.id).filter_by(id=first_server).first():
                            self.logger.debug(f"Adding service {first_server}")
                            current_time = datetime.now().astimezone()
                            to_put.append(
                                Services(id=first_server, method=method, is_draft=first_server in drafts, creation_date=current_time, last_update=current_time)
                            )
                            changed_services = True

                    for key, value in config.items():
                        suffix = 0
                        if self.SUFFIX_RX.search(key):
                            suffix = int(key.split("_")[-1])
                            key = key[: -len(str(suffix)) - 1]

                        setting = session.query(Settings).with_entities(Settings.default, Settings.plugin_id).filter_by(id=key).first()

                        if not setting:
                            continue

                        global_value = (
                            session.query(Global_values)
                            .with_entities(Global_values.value, Global_values.method)
                            .filter_by(setting_id=key, suffix=suffix)
                            .first()
                        )

                        template_setting = None
                        if template:
                            template_setting = (
                                session.query(Template_settings)
                                .with_entities(Template_settings.default)
                                .filter_by(template_id=template, setting_id=key, suffix=suffix)
                                .first()
                            )
                            service_template_change = True

                        if not global_value:
                            if value == (template_setting.default if template_setting is not None else setting.default):
                                continue

                            self.logger.debug(f"Adding global setting {key}")
                            changed_plugins.add(setting.plugin_id)
                            to_put.append(Global_values(setting_id=key, value=value, suffix=suffix, method=method))
                        elif self._methods_are_compatible(method, global_value.method) and global_value.value != value:
                            changed_plugins.add(setting.plugin_id)

                            if value == (template_setting.default if template_setting is not None else setting.default):
                                self.logger.debug(f"Removing global setting {key}")
                                to_delete.append({"model": Global_values, "filter": {"setting_id": key, "suffix": suffix}})
                                continue

                            self.logger.debug(f"Updating global setting {key}")
                            to_update.append(
                                {
                                    "model": Global_values,
                                    "filter": {"setting_id": key, "suffix": suffix},
                                    "values": {"value": self._empty_if_none(value), "method": method},
                                }
                            )

            if changed_services:
                changed_plugins = set(plugin.id for plugin in session.query(Plugins).with_entities(Plugins.id).all())

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        if not metadata.first_config_saved:
                            metadata.first_config_saved = True
                        if service_template_change:
                            metadata.custom_configs_changed = True
                            metadata.last_custom_configs_change = datetime.now().astimezone()

                    if changed_plugins:
                        session.query(Plugins).filter(Plugins.id.in_(changed_plugins)).update({Plugins.config_changed: True}, synchronize_session=False)

            try:
                # Apply collected deletions
                for delete_item in to_delete:
                    session.query(delete_item["model"]).filter_by(**delete_item["filter"]).delete(synchronize_session=False)

                # Apply collected updates
                for update_item in to_update:
                    session.query(update_item["model"]).filter_by(**update_item["filter"]).update(update_item["values"], synchronize_session=False)

                # Add new objects
                session.add_all(to_put)

                # Delete old global settings
                for global_setting in global_settings_to_delete:
                    session.delete(global_setting)

                # Delete old service settings
                for service_setting in service_settings_to_delete:
                    session.delete(service_setting)

                session.commit()
            except BaseException as e:
                session.rollback()
                return str(e)

        return changed_plugins

    def save_custom_configs(
        self,
        custom_configs: List[
            Dict[
                Literal[
                    "service_id",
                    "type",
                    "name",
                    "data",
                    "value",
                    "checksum",
                    "method",
                    "exploded",
                ],
                Union[str, bytes, List[str]],
            ]
        ],
        method: str,
        changed: Optional[bool] = True,
    ) -> str:
        """Save the custom configs in the database"""
        message = ""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            # Delete all the old config
            session.query(Custom_configs).filter(Custom_configs.method == method).delete()

            to_put = []
            endl = "\n"
            for custom_config in custom_configs:
                if "exploded" in custom_config:
                    config = {"data": custom_config["value"], "method": method, "is_draft": bool(custom_config.get("is_draft", False))}

                    if custom_config["exploded"][0]:
                        if not session.query(Services).with_entities(Services.id).filter_by(id=custom_config["exploded"][0]).first():
                            message += f"{endl if message else ''}Service {custom_config['exploded'][0]} not found, please check your config"

                        config.update(
                            {
                                "service_id": custom_config["exploded"][0],
                                "type": custom_config["exploded"][1],
                                "name": custom_config["exploded"][2],
                            }
                        )
                    else:
                        config.update(
                            {
                                "type": custom_config["exploded"][1],
                                "name": custom_config["exploded"][2],
                            }
                        )

                    custom_config = config

                custom_config["type"] = custom_config["type"].strip().replace("-", "_").lower()  # type: ignore
                custom_config["is_draft"] = bool(custom_config.get("is_draft", False))
                custom_config["data"] = custom_config["data"].encode("utf-8") if isinstance(custom_config["data"], str) else custom_config["data"]
                custom_config["checksum"] = custom_config.get("checksum", bytes_hash(custom_config["data"], algorithm="sha256"))  # type: ignore

                service_id = custom_config.get("service_id") or None
                filters = {
                    "type": custom_config["type"],
                    "name": custom_config["name"],
                    "service_id": service_id,
                }

                custom_conf = session.query(Custom_configs).filter_by(**filters).first()

                if not custom_conf:
                    to_put.append(Custom_configs(**custom_config))
                elif method == "manual" and custom_conf.method in {"manual", "ui", "api"}:
                    should_update_data = custom_config["checksum"] != custom_conf.checksum
                    if should_update_data:
                        custom_conf.data = custom_config["data"]
                        custom_conf.checksum = custom_config["checksum"]
                    if custom_conf.is_draft != custom_config["is_draft"] or should_update_data:
                        custom_conf.is_draft = custom_config["is_draft"]
                elif self._methods_are_compatible(method, custom_conf.method):
                    should_update_data = custom_config["checksum"] != custom_conf.checksum
                    if should_update_data:
                        custom_conf.data = custom_config["data"]
                        custom_conf.checksum = custom_config["checksum"]
                    if custom_conf.is_draft != custom_config["is_draft"] or should_update_data:
                        custom_conf.is_draft = custom_config["is_draft"]
                        custom_conf.method = method
                    custom_conf.is_draft = custom_config["is_draft"]
            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        metadata.custom_configs_changed = True
                        metadata.last_custom_configs_change = datetime.now().astimezone()

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException as e:
                return f"{f'{message}{endl}' if message else ''}{e}"

        return message

    def get_non_default_settings(
        self,
        global_only: bool = False,
        methods: bool = False,
        with_drafts: bool = False,
        filtered_settings: Optional[Union[List[str], Set[str], Tuple[str]]] = None,
        *,
        service: Optional[str] = None,
        original_config: Optional[Dict[str, Any]] = None,
        original_multisite: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Get the config from the database"""
        filtered_settings = set(filtered_settings or [])

        if filtered_settings and not global_only:
            filtered_settings.update(("SERVER_NAME", "MULTISITE"))

        with self._db_session() as session:
            config = original_config or {}
            multisite = original_multisite or set()

            # Define the join operation
            j = join(Settings, Global_values, Settings.id == Global_values.setting_id)

            # Define the select statement
            stmt = (
                db_select(
                    Settings.id.label("setting_id"),
                    Settings.context,
                    Settings.default,
                    Settings.multiple,
                    Global_values.value,
                    Global_values.suffix,
                    Global_values.method,
                )
                .select_from(j)
                .order_by(Settings.order)
            )

            if filtered_settings:
                stmt = stmt.where(Settings.id.in_(filtered_settings))

            # Execute the query and fetch all results
            results = session.execute(stmt).fetchall()

            for global_value in results:
                setting_id = global_value.setting_id + (f"_{global_value.suffix}" if global_value.multiple and global_value.suffix > 0 else "")
                config[setting_id] = {
                    "value": self._empty_if_none(global_value.value),
                    "global": True,
                    "method": global_value.method,
                    "default": self._empty_if_none(global_value.default),
                    "template": None,
                }

                if global_value.context == "multisite":
                    multisite.add(setting_id)

            is_multisite = config.get("MULTISITE", {"value": "no"})["value"] == "yes"

            services = session.query(Services).with_entities(Services.id, Services.is_draft)

            if not with_drafts:
                services = services.filter_by(is_draft=False)

            if not global_only and is_multisite:
                # Build list of service IDs and their draft status efficiently
                service_list = []
                is_draft_default = self._empty_if_none(config.get("IS_DRAFT", {"value": "no"})["value"])
                for db_service in services:
                    if service and db_service.id != service:
                        continue
                    service_list.append((db_service.id, db_service.is_draft))
                    config[f"{db_service.id}_IS_DRAFT"] = {
                        "value": "yes" if db_service.is_draft else "no",
                        "global": False,
                        "method": "default",
                        "default": is_draft_default,
                        "template": None,
                    }

                servers = " ".join(s[0] for s in service_list)

                # Pre-build multisite defaults mapping for efficient lookup
                # Share the same dictionary objects instead of creating copies
                multisite_defaults = {key: config[key] for key in multisite if key in config}

                # Populate service-specific entries using shared references
                # This is still O(services * multisite_settings) but avoids deepcopy overhead
                for service_id, _ in service_list:
                    for key, value in multisite_defaults.items():
                        config[f"{service_id}_{key}"] = value

                # Define the join operation
                j = join(Services, Services_settings, Services.id == Services_settings.service_id)
                j = j.join(Settings, Settings.id == Services_settings.setting_id)

                # Define the select statement
                stmt = (
                    db_select(
                        Services.id.label("service_id"),
                        Settings.id.label("setting_id"),
                        Settings.default,
                        Settings.multiple,
                        Services_settings.value,
                        Services_settings.suffix,
                        Services_settings.method,
                    )
                    .select_from(j)
                    .order_by(Services.id, Settings.order)
                )

                if not with_drafts:
                    stmt = stmt.where(Services.is_draft == False)  # noqa: E712

                if filtered_settings:
                    stmt = stmt.where(Settings.id.in_(filtered_settings))

                # Execute the query and fetch all results
                results = session.execute(stmt).fetchall()

                for result in results:
                    if service and result.service_id != service:
                        continue
                    value = self._empty_if_none(result.value)

                    if result.setting_id == "SERVER_NAME" and search(r"^" + escape(result.service_id) + r"( |$)", value) is None:
                        split = set(value.split())
                        split.discard(result.service_id)
                        value = result.service_id + " " + " ".join(split)

                    config[f"{result.service_id}_{result.setting_id}" + (f"_{result.suffix}" if result.multiple and result.suffix else "")] = {
                        "value": self._empty_if_none(value),
                        "global": False,
                        "method": result.method,
                        "default": self._empty_if_none(config.get(result.setting_id, {"value": self._empty_if_none(result.default)})["value"]),
                        "template": None,
                    }
            else:
                servers = " ".join(db_service.id for db_service in services)

            config["SERVER_NAME"] = {
                "value": servers,
                "global": True,
                "method": "scheduler",
                "default": "",
                "template": None,
            }

            if service:
                # Use list() to avoid modifying dict during iteration, more efficient than copy()
                for key in list(config.keys()):
                    if (original_config is None or key not in ("SERVER_NAME", "MULTISITE", "USE_TEMPLATE")) and not key.startswith(f"{service}_"):
                        del config[key]
                        continue
                    if original_config is None:
                        config[key.replace(f"{service}_", "")] = config.pop(key)

            if not methods:
                # Avoid full dictionary copy - iterate over keys and update in place
                for key in list(config.keys()):
                    config[key] = config[key]["value"]

            return config

    def get_config(
        self,
        global_only: bool = False,
        methods: bool = False,
        with_drafts: bool = False,
        filtered_settings: Optional[Union[List[str], Set[str], Tuple[str]]] = None,
        *,
        service: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get the config from the database"""
        filtered_settings = set(filtered_settings or [])

        if filtered_settings and not global_only:
            filtered_settings.update(("SERVER_NAME", "MULTISITE", "USE_TEMPLATE"))

        config = {}
        multisite = set()
        multiple_groups = {}
        with self._db_session() as session:
            query = (
                session.query(Settings)
                .with_entities(
                    Settings.id,
                    Settings.context,
                    Settings.default,
                    Settings.multiple,
                )
                .order_by(Settings.order)
            )

            if filtered_settings:
                query = query.filter(Settings.id.in_(filtered_settings))

            for setting in query:
                config[setting.id] = {
                    "value": self._empty_if_none(setting.default),
                    "global": True,
                    "method": "default",
                    "default": self._empty_if_none(setting.default),
                    "template": None,
                }
                if setting.context == "multisite":
                    multisite.add(setting.id)
                if setting.multiple:
                    multiple_groups[setting.id] = setting.multiple

        config = self.get_non_default_settings(
            global_only=global_only,
            methods=True,
            with_drafts=with_drafts,
            filtered_settings=filtered_settings,
            service=service,
            original_config=config,
            original_multisite=multisite,
        )

        template_used = config.get("USE_TEMPLATE", {"value": ""})["value"]
        templates = {"global": template_used} if template_used else {}
        with self._db_session() as session:
            if template_used:
                query = (
                    session.query(Template_settings)
                    .with_entities(Template_settings.setting_id, Template_settings.default, Template_settings.suffix)
                    .filter_by(template_id=template_used)
                    .order_by(Template_settings.order)
                )

                if filtered_settings:
                    query = query.filter(Template_settings.setting_id.in_(filtered_settings))

                for template_setting in query:
                    key = template_setting.setting_id + (f"_{template_setting.suffix}" if template_setting.suffix > 0 else "")
                    if key in config and config[key]["method"] != "default":
                        continue

                    config[key] = {
                        "value": self._empty_if_none(template_setting.default),
                        "global": True,
                        "method": "default",
                        "default": self._empty_if_none(template_setting.default),
                        "template": template_used,
                    }

            if not global_only and config["MULTISITE"]["value"] == "yes":
                server_names = config["SERVER_NAME"]["value"].split()

                # Collect all unique templates used by services
                service_templates = {}
                for service_id in server_names:
                    service_template_used = config.get(f"{service_id}_USE_TEMPLATE", {"value": self._empty_if_none(template_used)})["value"]
                    if service_template_used:
                        templates[service_id] = service_template_used
                        service_templates.setdefault(service_template_used, []).append(service_id)

                # Batch query: fetch all template settings for all used templates at once
                if service_templates:
                    template_ids = list(service_templates.keys())
                    query = (
                        session.query(Template_settings)
                        .with_entities(Template_settings.template_id, Template_settings.setting_id, Template_settings.default, Template_settings.suffix)
                        .filter(Template_settings.template_id.in_(template_ids))
                        .order_by(Template_settings.order)
                    )

                    if filtered_settings:
                        query = query.filter(Template_settings.setting_id.in_(filtered_settings))

                    # Group template settings by template_id for efficient lookup
                    template_settings_map = {}
                    for setting in query:
                        template_settings_map.setdefault(setting.template_id, []).append(setting)

                    # Apply template settings to each service that uses them
                    for tmpl_id, service_ids in service_templates.items():
                        tmpl_settings = template_settings_map.get(tmpl_id, [])
                        for service_id in service_ids:
                            for setting in tmpl_settings:
                                key = f"{service_id}_{setting.setting_id}" + (f"_{setting.suffix}" if setting.suffix > 0 else "")
                                if key in config and config[key]["method"] != "default" and not config[key]["global"]:
                                    continue

                                config[key] = {
                                    "value": self._empty_if_none(setting.default),
                                    "global": False,
                                    "method": "default",
                                    "default": self._empty_if_none(setting.default),
                                    "template": tmpl_id,
                                }

        multiple = {}
        services = config["SERVER_NAME"]["value"].split()
        services_set = set(services)  # O(1) lookup for service prefix matching

        # Process config items - use list(items()) which is more memory efficient than copy().items()
        # for large dicts since it creates a list of tuples, not a full dict copy
        for key, data in list(config.items()):
            new_value = None
            if service:
                data = config.pop(key)
                if not key.startswith(f"{service}_"):
                    continue
                key = key.replace(f"{service}_", "")
                new_value = data

            if not methods:
                new_value = data["value"]

            match = self.SUFFIX_RX.search(key)
            if match:
                window = "global"
                matched_group = multiple_groups.get(match.group("setting"), None)
                if matched_group is None:
                    # Use set lookup and underscore scanning instead of O(n) service iteration
                    underscore_pos = 0
                    while True:
                        underscore_pos = key.find("_", underscore_pos)
                        if underscore_pos == -1:
                            break
                        potential_service = key[:underscore_pos]
                        if potential_service in services_set:
                            window = potential_service
                            matched_group = multiple_groups.get(match.group("setting").replace(f"{potential_service}_", ""), None)
                            break
                        underscore_pos += 1

                if matched_group is not None:
                    multiple.setdefault(matched_group, {}).setdefault(window, set()).add(int(match.group("suffix")))

            if new_value is not None:
                config[key] = new_value

        if multiple:
            with self._db_session() as session:
                query = session.query(Settings).with_entities(Settings.id, Settings.default).filter(Settings.multiple.in_(multiple.keys()))

                for setting in query:
                    group_key = multiple_groups.get(setting.id)
                    if group_key is None or group_key not in multiple:
                        continue

                    for window, suffixes in multiple[group_key].items():
                        template = templates.get(window, "") or templates.get("global", "")
                        for suffix in map(int, suffixes):
                            if window == "global" or service:
                                key = f"{setting.id}_{suffix}"
                            else:
                                key = f"{window}_{setting.id}_{suffix}"

                            default = self._empty_if_none(setting.default)
                            value = deepcopy(default)
                            if template:
                                template_setting = (
                                    session.query(Template_settings).filter_by(template_id=template, setting_id=setting.id, suffix=suffix).first()
                                )
                                if template_setting is not None:
                                    value = self._empty_if_none(template_setting.default)

                            if key not in config:
                                config[key] = (
                                    {
                                        "value": value,
                                        "global": True,
                                        "method": "default",
                                        "default": default,
                                        "template": template,
                                    }
                                    if methods
                                    else value
                                )

        return config

    def get_custom_configs(self, *, with_drafts: bool = False, with_data: bool = True, as_dict: bool = False) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Get the custom configs from the database"""
        db_config = self.get_non_default_settings(with_drafts=with_drafts, filtered_settings=("USE_TEMPLATE",))

        with self._db_session() as session:
            services = session.query(Services).with_entities(Services.id, Services.is_draft).all()
            allowed_services = {srv.id for srv in services if with_drafts or not srv.is_draft}

            entities = [
                Custom_configs.service_id,
                Custom_configs.type,
                Custom_configs.name,
                Custom_configs.checksum,
                Custom_configs.method,
                Custom_configs.is_draft,
            ]
            if with_data:
                entities.append(Custom_configs.data)

            custom_configs = []
            for custom_config in session.query(Custom_configs).with_entities(*entities):
                if custom_config.service_id and custom_config.service_id not in allowed_services:
                    continue
                if custom_config.is_draft and not with_drafts:
                    continue

                data = {
                    "service_id": custom_config.service_id,
                    "type": custom_config.type,
                    "name": custom_config.name,
                    "checksum": custom_config.checksum,
                    "method": custom_config.method,
                    "template": None,
                    "is_draft": custom_config.is_draft,
                }
                if with_data:
                    data["data"] = custom_config.data
                custom_configs.append(data)

            if not db_config:
                if as_dict:
                    dict_custom_configs = {}
                    for custom_config in custom_configs:
                        dict_custom_configs[
                            (f"{custom_config['service_id']}_" if custom_config["service_id"] else "") + f"{custom_config['type']}_{custom_config['name']}"
                        ] = custom_config
                    return dict_custom_configs
                return custom_configs

            template_entities = [Template_custom_configs.type, Template_custom_configs.name, Template_custom_configs.checksum]
            if with_data:
                template_entities.append(Template_custom_configs.data)

            for service_id in allowed_services:
                for key, value in db_config.items():
                    if key.startswith(f"{service_id}_"):
                        for template_config in (
                            session.query(Template_custom_configs)
                            .with_entities(*template_entities)
                            .filter_by(template_id=value)
                            .order_by(Template_custom_configs.order)
                        ):
                            config_type = template_config.type.replace("_", "-").replace(".conf", "").strip()
                            if not any(
                                custom_config["service_id"] == service_id
                                and custom_config["type"] == config_type
                                and custom_config["name"] == template_config.name
                                for custom_config in custom_configs
                            ):
                                custom_config = {
                                    "service_id": service_id,
                                    "type": config_type,
                                    "name": template_config.name,
                                    "checksum": template_config.checksum,
                                    "method": "default",
                                    "template": value,
                                    "is_draft": False,
                                }
                                if with_data:
                                    custom_config["data"] = template_config.data
                                custom_configs.append(custom_config)

            if as_dict:
                dict_custom_configs = {}
                for custom_config in custom_configs:
                    dict_custom_configs[
                        (f"{custom_config['service_id']}_" if custom_config["service_id"] else "") + f"{custom_config['type']}_{custom_config['name']}"
                    ] = custom_config
                return dict_custom_configs
            return custom_configs

    def get_custom_config(self, config_type: str, name: str, *, service_id: Optional[str] = None, with_data: bool = True) -> Dict[str, Any]:
        """Get a custom config from the database"""
        config_type = config_type.strip().replace("-", "_").lower()
        with self._db_session() as session:
            entities = [
                Custom_configs.service_id,
                Custom_configs.type,
                Custom_configs.name,
                Custom_configs.checksum,
                Custom_configs.method,
                Custom_configs.is_draft,
            ]
            if with_data:
                entities.append(Custom_configs.data)

            db_config = session.query(Custom_configs).with_entities(*entities).filter_by(service_id=service_id, type=config_type, name=name).first()

        if not db_config:
            if service_id:
                service_config = self.get_non_default_settings(with_drafts=True, filtered_settings=("USE_TEMPLATE",))
                if service_config.get(f"{service_id}_USE_TEMPLATE"):
                    with self._db_session() as session:
                        template_config = (
                            session.query(Template_custom_configs)
                            .filter_by(template_id=service_config.get(f"{service_id}_USE_TEMPLATE"), type=config_type, name=name)
                            .first()
                        )
                        if template_config:
                            custom_config = {
                                "service_id": service_id,
                                "type": config_type,
                                "name": name,
                                "checksum": template_config.checksum,
                                "method": "default",
                                "template": service_config.get(f"{service_id}_USE_TEMPLATE"),
                                "is_draft": False,
                            }
                            if with_data:
                                custom_config["data"] = template_config.data
                            return custom_config
            return {}

        custom_config = {
            "service_id": service_id,
            "type": config_type,
            "name": name,
            "checksum": db_config.checksum,
            "method": db_config.method,
            "template": None,
            "is_draft": getattr(db_config, "is_draft", False),
        }
        if with_data:
            custom_config["data"] = db_config.data

        return custom_config

    def upsert_custom_config(self, config_type: str, name: str, config: Dict[str, Any], *, service_id: Optional[str] = None, new: bool = False) -> str:
        """Update or insert a custom config in the database"""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            filters = {
                "type": config_type,
                "name": name,
                "service_id": service_id or None,
            }

            custom_config = session.query(Custom_configs).filter_by(**filters).first()

            data = config["data"].encode("utf-8") if isinstance(config["data"], str) else config["data"]
            checksum = config.get("checksum", bytes_hash(data, algorithm="sha256"))
            is_draft = bool(config.get("is_draft", False))

            if not custom_config:
                session.add(
                    Custom_configs(
                        service_id=config.get("service_id"),
                        type=config["type"],
                        name=config["name"],
                        data=data,
                        checksum=checksum,
                        method=config["method"],
                        is_draft=is_draft,
                    )
                )
            else:
                if new:
                    return "The custom config already exists"
                custom_config.service_id = config.get("service_id")
                custom_config.data = data
                custom_config.checksum = checksum
                custom_config.is_draft = is_draft
                for key in ("type", "name", "method"):
                    if key in config:
                        setattr(custom_config, key, config[key])

            with suppress(ProgrammingError, OperationalError):
                metadata = session.query(Metadata).get(1)
                if metadata is not None:
                    metadata.custom_configs_changed = True
                    metadata.last_custom_configs_change = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def get_services_settings(self, methods: bool = False, with_drafts: bool = False) -> List[Dict[str, Any]]:
        """Get the services' configs from the database"""
        services = []
        config = self.get_config(methods=methods, with_drafts=with_drafts)
        service_names = config["SERVER_NAME"]["value"].split() if methods else config["SERVER_NAME"].split()
        for service in service_names:
            service_settings = []
            tmp_config = config.copy()

            for key, value in tmp_config.copy().items():
                if key.startswith(f"{service}_"):
                    setting = key.replace(f"{service}_", "")
                    service_settings.append(setting)
                    tmp_config[setting] = tmp_config.pop(key)
                elif any(key.startswith(f"{s}_") for s in service_names):
                    tmp_config.pop(key)
                elif key not in service_settings:
                    tmp_config[key] = (
                        {
                            "value": self._empty_if_none(value["value"]),
                            "global": value["global"],
                            "method": value["method"],
                            "default": self._empty_if_none(value["default"]),
                            "template": value["template"],
                        }
                        if methods
                        else value
                    )

            services.append(tmp_config)

        return services

    def get_services(self, *, with_drafts: bool = False) -> List[Dict[str, Any]]:
        """Get the services from the database"""
        services = []
        with self._db_session() as session:
            # Fetch all services with their USE_TEMPLATE and SECURITY_MODE settings in a single optimized query
            # This avoids N+1 query problem when loading many services
            template_alias = aliased(Services_settings)
            security_mode_alias = aliased(Services_settings)

            query = (
                session.query(Services)
                .outerjoin(template_alias, (Services.id == template_alias.service_id) & (template_alias.setting_id == "USE_TEMPLATE"))
                .outerjoin(security_mode_alias, (Services.id == security_mode_alias.service_id) & (security_mode_alias.setting_id == "SECURITY_MODE"))
                .with_entities(
                    Services.id,
                    Services.method,
                    Services.is_draft,
                    Services.creation_date,
                    Services.last_update,
                    template_alias.value.label("template"),
                    security_mode_alias.value.label("security_mode"),
                )
            )

            if not with_drafts:
                query = query.filter(Services.is_draft == False)  # noqa: E712

            db_services = query.all()

        for service in db_services:
            services.append(
                {
                    "id": service.id,
                    "method": service.method,
                    "is_draft": service.is_draft,
                    "creation_date": service.creation_date,
                    "last_update": service.last_update,
                    "template": service.template or "",
                    "security_mode": service.security_mode or "block",
                }
            )

        return services

    def add_job_run(self, job_name: str, success: bool, start_date: datetime, end_date: Optional[datetime] = None) -> str:
        """Add a job run."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            session.add(Jobs_runs(job_name=job_name, success=success, start_date=start_date, end_date=end_date or datetime.now().astimezone()))

            try:
                session.commit()
            except BaseException as e:
                return str(e)
        return ""

    def cleanup_jobs_runs_excess(self, max_runs: int) -> str:
        """Remove excess jobs runs."""
        result = 0
        with self._db_session() as session:
            rows_count = session.query(Jobs_runs).count()
            if rows_count > max_runs:
                records_to_delete = session.query(Jobs_runs.id).order_by(Jobs_runs.end_date.asc()).limit(rows_count - max_runs).all()
                ids_to_delete = [record.id for record in records_to_delete]
                if ids_to_delete:
                    result = session.query(Jobs_runs).filter(Jobs_runs.id.in_(ids_to_delete)).delete(synchronize_session=False)

                try:
                    session.commit()
                except BaseException as e:
                    return str(e)
        return f"Removed {result} excess jobs runs"

    def cleanup_expired_ui_sessions(self, max_age_days: int) -> str:
        """Remove UI sessions older than the provided age threshold."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            cutoff = datetime.now().astimezone() - timedelta(days=max_age_days)

            deleted = session.query(UserSessions).filter(UserSessions.last_activity < cutoff).delete(synchronize_session=False)

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return f"Removed {deleted} expired UI user sessions"

    def delete_job_cache(self, file_name: str, *, job_name: Optional[str] = None, service_id: Optional[str] = None) -> str:
        job_name = job_name or argv[0].replace(".py", "")
        filters = {"file_name": file_name, "service_id": service_id or None}
        if job_name:
            filters["job_name"] = job_name

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            session.query(Jobs_cache).filter_by(**filters).delete(synchronize_session=False)

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def upsert_job_cache(
        self,
        service_id: Optional[str],
        file_name: str,
        data: bytes,
        *,
        job_name: Optional[str] = None,
        checksum: Optional[str] = None,
    ) -> str:
        """Update the plugin cache in the database"""
        job_name = job_name or argv[0].replace(".py", "")
        service_id = service_id or None
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            cache = session.query(Jobs_cache).filter_by(job_name=job_name, service_id=service_id, file_name=file_name).first()

            if not cache:
                session.add(
                    Jobs_cache(
                        job_name=job_name,
                        service_id=service_id,
                        file_name=file_name,
                        data=data,
                        last_update=datetime.now().astimezone(),
                        checksum=checksum,
                    )
                )
            else:
                cache.data = data
                cache.last_update = datetime.now().astimezone()
                cache.checksum = checksum

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def update_external_plugins(
        self,
        plugins: List[Dict[str, Any]],
        *,
        _type: Literal["external", "ui", "pro"] = "external",
        delete_missing: bool = True,
        only_clear_metadata: bool = False,
        per_plugin_commit: bool = True,
    ) -> str:
        """Update external plugins from the database"""
        to_put = []
        changes = False
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            def _add_ordered(items: List[Any]) -> None:
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

                if buckets["jobs"]:
                    session.add_all(buckets["jobs"])
                if buckets["plugin_pages"]:
                    session.add_all(buckets["plugin_pages"])
                if buckets["cli_commands"]:
                    session.add_all(buckets["cli_commands"])
                if buckets["other"]:
                    session.add_all(buckets["other"])

            db_plugins = session.query(Plugins).with_entities(Plugins.id).filter_by(type=_type).all()

            db_ids = []
            if delete_missing and db_plugins:
                db_ids = [plugin.id for plugin in db_plugins]
                ids = [plugin["id"] for plugin in plugins]
                missing_ids = [plugin for plugin in db_ids if plugin not in ids]

                if missing_ids:
                    changes = True
                    # Remove plugins that are no longer in the list
                    if not only_clear_metadata:
                        session.query(Plugins).filter(Plugins.id.in_(missing_ids)).delete()

                        session.query(Plugin_pages).filter(Plugin_pages.plugin_id.in_(missing_ids)).delete()
                        session.query(Bw_cli_commands).filter(Bw_cli_commands.plugin_id.in_(missing_ids)).delete()

                        for plugin_job in session.query(Jobs).with_entities(Jobs.name).filter(Jobs.plugin_id.in_(missing_ids)):
                            session.query(Jobs_runs).filter(Jobs_runs.job_name == plugin_job.name).delete()
                            session.query(Jobs_cache).filter(Jobs_cache.job_name == plugin_job.name).delete()
                            session.query(Jobs).filter(Jobs.name == plugin_job.name).delete()

                        for plugin_setting in session.query(Settings).with_entities(Settings.id).filter(Settings.plugin_id.in_(missing_ids)):
                            session.query(Selects).filter(Selects.setting_id == plugin_setting.id).delete()
                            session.query(Services_settings).filter(Services_settings.setting_id == plugin_setting.id).delete()
                            session.query(Global_values).filter(Global_values.setting_id == plugin_setting.id).delete()
                            session.query(Settings).filter(Settings.id == plugin_setting.id).delete()

                        for plugin_template in session.query(Templates).with_entities(Templates.id).filter(Templates.plugin_id.in_(missing_ids)):
                            session.query(Template_steps).filter(Template_steps.template_id == plugin_template.id).delete()
                            session.query(Template_settings).filter(Template_settings.template_id == plugin_template.id).delete()
                            session.query(Template_custom_configs).filter(Template_custom_configs.template_id == plugin_template.id).delete()
                            session.query(Templates).filter(Templates.id == plugin_template.id).delete()
                    else:
                        session.query(Plugins).filter(Plugins.id.in_(missing_ids)).update({Plugins.data: None, Plugins.checksum: None})

                    try:
                        session.commit()
                    except BaseException as e:
                        return str(e)

            db_settings = [setting.id for setting in session.query(Settings).with_entities(Settings.id)]

            for plugin in plugins:
                local_to_put = []
                settings = plugin.pop("settings", {})
                jobs = plugin.pop("jobs", [])
                page = plugin.pop("page", False)
                commands = plugin.pop("bwcli", {})
                if not isinstance(commands, dict):
                    commands = {}
                plugin["type"] = _type
                db_plugin = (
                    session.query(Plugins)
                    .with_entities(
                        Plugins.name,
                        Plugins.stream,
                        Plugins.description,
                        Plugins.version,
                        Plugins.method,
                        Plugins.checksum,
                        Plugins.type,
                    )
                    .filter_by(id=plugin["id"])
                    .first()
                )

                if db_plugin:
                    if plugin["method"] not in (db_plugin.method, "autoconf"):
                        self.logger.warning(f'Plugin "{plugin["id"]}" already exists, but the method is different, skipping update')
                        continue

                    if db_plugin.type not in ("external", "ui", "pro"):
                        self.logger.warning(
                            f"Plugin \"{plugin['id']}\" is not {_type}, skipping update (updating a non-external, non-ui or non-pro plugin is forbidden for security reasons)",  # noqa: E501
                        )
                        continue

                    updates = {}

                    if plugin["stream"] != db_plugin.stream:
                        updates[Plugins.stream] = plugin["stream"]

                    if plugin["name"] != db_plugin.name:
                        updates[Plugins.name] = plugin["name"]

                    if plugin["description"] != db_plugin.description:
                        updates[Plugins.description] = plugin["description"]

                    if plugin["version"] != db_plugin.version:
                        updates[Plugins.version] = plugin["version"]

                    if plugin["method"] != db_plugin.method:
                        updates[Plugins.method] = plugin["method"]

                    if plugin.get("checksum") != db_plugin.checksum:
                        updates[Plugins.checksum] = plugin.get("checksum")
                        updates[Plugins.data] = plugin.get("data")

                    if plugin.get("type") != db_plugin.type:
                        updates[Plugins.type] = plugin.get("type")

                    if updates:
                        changes = True
                        session.query(Plugins).filter(Plugins.id == plugin["id"]).update(updates)

                    db_ids = [setting.id for setting in session.query(Settings).with_entities(Settings.id).filter_by(plugin_id=plugin["id"])]
                    setting_ids = [setting for setting in settings]
                    missing_ids = [setting for setting in db_ids if setting not in setting_ids]

                    if missing_ids:
                        changes = True
                        # Remove settings that are no longer in the list
                        session.query(Settings).filter(Settings.id.in_(missing_ids)).delete()
                        session.query(Selects).filter(Selects.setting_id.in_(missing_ids)).delete()
                        session.query(Multiselects).filter(Multiselects.setting_id.in_(missing_ids)).delete()
                        session.query(Services_settings).filter(Services_settings.setting_id.in_(missing_ids)).delete()
                        session.query(Global_values).filter(Global_values.setting_id.in_(missing_ids)).delete()
                        session.query(Template_settings).filter(Template_settings.setting_id.in_(missing_ids)).delete()

                    order = 0
                    plugin_settings = set()
                    for setting, value in settings.items():
                        value.update({"plugin_id": plugin["id"], "name": value["id"], "id": setting})
                        plugin_settings.add(setting)

                        db_setting = (
                            session.query(Settings)
                            .with_entities(
                                Settings.name,
                                Settings.context,
                                Settings.default,
                                Settings.help,
                                Settings.label,
                                Settings.regex,
                                Settings.type,
                                Settings.multiple,
                                Settings.order,
                            )
                            .filter_by(id=setting)
                            .first()
                        )

                        if setting not in db_ids or not db_setting:
                            changes = True
                            for sel_order, select in enumerate(value.pop("select", []), start=1):
                                local_to_put.append(Selects(setting_id=value["id"], value=self._empty_if_none(select), order=sel_order))

                            for msel_order, multiselect in enumerate(value.pop("multiselect", []), start=1):
                                if isinstance(multiselect, dict):
                                    local_to_put.append(
                                        Multiselects(
                                            setting_id=setting,
                                            option_id=multiselect.get("id", ""),
                                            label=multiselect.get("label", ""),
                                            value=self._empty_if_none(multiselect.get("value", "")),
                                            order=msel_order,
                                        )
                                    )

                            local_to_put.append(Settings(**value | {"order": order}))
                        else:
                            updates = {}

                            if value["name"] != db_setting.name:
                                updates[Settings.name] = value["name"]

                            if value["context"] != db_setting.context:
                                updates[Settings.context] = value["context"]

                            if value["default"] != db_setting.default:
                                updates[Settings.default] = value["default"]

                            if value["help"] != db_setting.help:
                                updates[Settings.help] = value["help"]

                            if value["label"] != db_setting.label:
                                updates[Settings.label] = value["label"]

                            if value["regex"] != db_setting.regex:
                                updates[Settings.regex] = value["regex"]

                            if value["type"] != db_setting.type:
                                updates[Settings.type] = value["type"]

                            if value.get("multiple") != db_setting.multiple:
                                updates[Settings.multiple] = value.get("multiple")

                            if order != db_setting.order:
                                updates[Settings.order] = order

                            if updates:
                                changes = True
                                session.query(Settings).filter(Settings.id == setting).update(updates)

                            db_values = [
                                (self._empty_if_none(select.value), select.order)
                                for select in session.query(Selects).with_entities(Selects.value, Selects.order).filter_by(setting_id=setting)
                            ]
                            select_values = enumerate(value.get("select", []), start=1)
                            different_values = any(db_value != (value, order) for db_value, (value, order) in zip(db_values, select_values))

                            if different_values:
                                changes = True
                                # Remove old selects
                                session.query(Selects).filter(Selects.setting_id == setting).delete()
                                # Add new selects with the new values
                                for sel_order, select in enumerate(value.get("select", []), start=1):
                                    local_to_put.append(Selects(setting_id=setting, value=self._empty_if_none(select), order=sel_order))

                            # Handle multiselects
                            db_multiselect_values = [
                                (msel.option_id, msel.label, self._empty_if_none(msel.value), msel.order)
                                for msel in session.query(Multiselects)
                                .with_entities(Multiselects.option_id, Multiselects.label, Multiselects.value, Multiselects.order)
                                .filter_by(setting_id=setting)
                            ]
                            multiselect_values = [
                                (msel.get("id", ""), msel.get("label", ""), self._empty_if_none(msel.get("value", "")), order)
                                for order, msel in enumerate(value.get("multiselect", []), start=1)
                                if isinstance(msel, dict)
                            ]
                            different_multiselect_values = db_multiselect_values != multiselect_values

                            if different_multiselect_values:
                                changes = True
                                # Remove old multiselects
                                session.query(Multiselects).filter(Multiselects.setting_id == setting).delete()
                                # Add new multiselects with the new values
                                for msel_order, multiselect in enumerate(value.get("multiselect", []), start=1):
                                    if isinstance(multiselect, dict):
                                        local_to_put.append(
                                            Multiselects(
                                                setting_id=setting,
                                                option_id=multiselect.get("id", ""),
                                                label=multiselect.get("label", ""),
                                                value=self._empty_if_none(multiselect.get("value", "")),
                                                order=msel_order,
                                            )
                                        )

                        order += 1

                    db_names = [job.name for job in session.query(Jobs).with_entities(Jobs.name).filter_by(plugin_id=plugin["id"])]
                    job_names = [job["name"] for job in jobs]
                    missing_names = [job for job in db_names if job not in job_names]

                    if missing_names:
                        changes = True
                        # Remove jobs that are no longer in the list
                        session.query(Jobs).filter(Jobs.name.in_(missing_names)).delete()
                        session.query(Jobs_cache).filter(Jobs_cache.job_name.in_(missing_names)).delete()
                        session.query(Jobs_runs).filter(Jobs_runs.job_name.in_(missing_names)).delete()

                    for job in jobs:
                        db_job = (
                            session.query(Jobs)
                            .with_entities(Jobs.file_name, Jobs.every, Jobs.reload, Jobs.run_async)
                            .filter_by(name=job["name"], plugin_id=plugin["id"])
                            .first()
                        )

                        if job["name"] not in db_names or not db_job:
                            changes = True
                            job["file_name"] = job.pop("file")
                            job["reload"] = job.get("reload", False)
                            job["run_async"] = job.pop("async", False)
                            local_to_put.append(Jobs(plugin_id=plugin["id"], **job))
                        else:
                            updates = {}

                            if job["file"] != db_job.file_name:
                                updates[Jobs.file_name] = job["file"]

                            if job["every"] != db_job.every:
                                updates[Jobs.every] = job["every"]

                            if job.get("reload", False) != db_job.reload:
                                updates[Jobs.reload] = job.get("reload", False)

                            if job.get("async", False) != db_job.run_async:
                                updates[Jobs.run_async] = job.get("async", False)

                            if updates:
                                changes = True
                                updates[Jobs.last_run] = None
                                session.query(Jobs_runs).filter(Jobs_runs.job_name == job["name"]).delete()
                                session.query(Jobs_cache).filter(Jobs_cache.job_name == job["name"]).delete()
                                session.query(Jobs).filter(Jobs.name == job["name"]).update(updates)

                    plugin_path = Path(sep, "var", "tmp", "bunkerweb", "ui", plugin["id"])
                    plugin_path = (
                        plugin_path
                        if plugin_path.is_dir()
                        else (
                            Path(sep, "etc", "bunkerweb", "plugins", plugin["id"])
                            if _type == "external"
                            else Path(sep, "etc", "bunkerweb", "pro", "plugins", plugin["id"])
                        )
                    )

                    path_ui = plugin_path.joinpath("ui")

                    db_plugin_page = session.query(Plugin_pages).with_entities(Plugin_pages.checksum).filter_by(plugin_id=plugin["id"]).first()
                    remove = not path_ui.is_dir() and db_plugin_page

                    if path_ui.is_dir():
                        remove = True
                        with BytesIO() as plugin_page_content:
                            with tar_open(fileobj=plugin_page_content, mode="w:gz", compresslevel=9) as tar:
                                tar.add(path_ui, arcname=path_ui.name, recursive=True)
                            plugin_page_content.seek(0)
                            checksum = bytes_hash(plugin_page_content, algorithm="sha256")
                            content = plugin_page_content.getvalue()

                        if not db_plugin_page:
                            changes = True
                            local_to_put.append(Plugin_pages(plugin_id=plugin["id"], data=content, checksum=checksum))
                            remove = False
                        elif checksum != db_plugin_page.checksum:
                            changes = True
                            session.query(Plugin_pages).filter(Plugin_pages.plugin_id == plugin["id"]).update(
                                {Plugin_pages.data: content, Plugin_pages.checksum: checksum}
                            )
                            remove = False

                    if db_plugin_page and remove:
                        changes = True
                        session.query(Plugin_pages).filter(Plugin_pages.plugin_id == plugin["id"]).delete()

                    db_names = [
                        command.name for command in session.query(Bw_cli_commands).with_entities(Bw_cli_commands.name).filter_by(plugin_id=plugin["id"])
                    ]
                    missing_names = [command for command in db_names if command not in commands]

                    if missing_names:
                        # Remove commands that are no longer in the list
                        session.query(Bw_cli_commands).filter(Bw_cli_commands.name.in_(missing_names), Bw_cli_commands.plugin_id == plugin["id"]).delete()

                    for command, file_name in commands.items():
                        db_command = (
                            session.query(Bw_cli_commands).with_entities(Bw_cli_commands.file_name).filter_by(name=command, plugin_id=plugin["id"]).first()
                        )
                        command_path = plugin_path.joinpath("bwcli", file_name)

                        if command not in db_names or not db_command:
                            if not command_path.is_file():
                                self.logger.warning(
                                    f'Plugin "{plugin["id"]}"\'s Command "{command}"\'s file "{file_name}" does not exist in the plugin directory, skipping it'
                                )
                                continue

                            changes = True
                            local_to_put.append(Bw_cli_commands(name=command, plugin_id=plugin["id"], file_name=file_name))
                        else:
                            updates = {}

                            if file_name != db_command.file_name:
                                updates[Bw_cli_commands.file_name] = file_name

                            if updates:
                                changes = True
                                if not command_path.is_file():
                                    session.query(Bw_cli_commands).filter_by(name=command, plugin_id=plugin["id"]).delete()
                                    continue
                                session.query(Bw_cli_commands).filter_by(name=command, plugin_id=plugin["id"]).update(updates)

                    db_names = [template.id for template in session.query(Templates).with_entities(Templates.id).filter_by(plugin_id=plugin["id"])]
                    templates_path = plugin_path.joinpath("templates")

                    if templates_path.is_dir():
                        saved_templates = set()
                        for template_file in templates_path.iterdir():
                            if template_file.is_dir():
                                continue

                            try:
                                template_data = loads(template_file.read_text())
                            except JSONDecodeError:
                                self.logger.error(
                                    f"{plugin.get('type', 'core').title()} Plugin \"{plugin['id']}\"'s Template file \"{template_file}\" is not a valid JSON file"
                                )
                                continue

                            template_id = template_file.stem

                            db_template = session.query(Templates).with_entities(Templates.id).filter_by(id=template_id, plugin_id=plugin["id"]).first()

                            if not db_template:
                                changes = True
                                current_time = datetime.now().astimezone()
                                local_to_put.append(
                                    Templates(
                                        id=template_id,
                                        plugin_id=plugin["id"],
                                        name=template_data.get("name", template_id),
                                        method=plugin["method"],
                                        creation_date=current_time,
                                        last_update=current_time,
                                    )
                                )

                            saved_templates.add(template_id)

                            db_ids = [step.id for step in session.query(Template_steps).with_entities(Template_steps.id).filter_by(template_id=template_id)]
                            missing_ids = [x for x in range(1, len(template_data.get("steps", [])) + 1) if x not in db_ids]

                            if missing_ids:
                                changes = True
                                session.query(Template_settings).filter(Template_settings.step_id.in_(missing_ids)).delete()
                                session.query(Template_custom_configs).filter(Template_custom_configs.step_id.in_(missing_ids)).delete()
                                session.query(Template_steps).filter(Template_steps.id.in_(missing_ids)).delete()

                            steps_settings = {}
                            steps_configs = {}
                            for step_id, step in enumerate(template_data.get("steps", []), start=1):
                                db_step = (
                                    session.query(Template_steps)
                                    .with_entities(Template_steps.id, Template_steps.title, Template_steps.subtitle)
                                    .filter_by(id=step_id, template_id=template_id)
                                    .first()
                                )
                                if not db_step:
                                    changes = True
                                    local_to_put.append(Template_steps(id=step_id, template_id=template_id, title=step["title"], subtitle=step["subtitle"]))
                                else:
                                    updates = {}

                                    if step["title"] != db_step.title:
                                        updates[Template_steps.title] = step["title"]

                                    if step["subtitle"] != db_step.subtitle:
                                        updates[Template_steps.subtitle] = step["subtitle"]

                                    if updates:
                                        changes = True
                                        session.query(Template_steps).filter(Template_steps.id == db_step.id).update(updates)

                                for setting in step.get("settings", []):
                                    if step_id not in steps_settings:
                                        steps_settings[step_id] = []
                                    steps_settings[step_id].append(setting)

                                for config in step.get("configs", []):
                                    if step_id not in steps_configs:
                                        steps_configs[step_id] = []
                                    steps_configs[step_id].append(config)

                            db_template_settings = [
                                f"{template_setting.setting_id}_{template_setting.suffix}" if template_setting.suffix else template_setting.setting_id
                                for template_setting in session.query(Template_settings)
                                .with_entities(Template_settings.id, Template_settings.setting_id, Template_settings.suffix)
                                .filter_by(template_id=template_id)
                                .order_by(Template_settings.order)
                            ]
                            missing_ids = [setting for setting in template_data.get("settings", {}) if setting not in db_template_settings]

                            if missing_ids:
                                changes = True
                                session.query(Template_settings).filter(Template_settings.id.in_(missing_ids)).delete()

                            order = 0
                            for setting, default in template_data.get("settings", {}).items():
                                setting_id, suffix = setting.rsplit("_", 1) if self.SUFFIX_RX.search(setting) else (setting, None)
                                if suffix is not None:
                                    suffix = int(suffix)
                                else:
                                    suffix = 0

                                if setting_id in self.RESTRICTED_TEMPLATE_SETTINGS:
                                    self.logger.error(
                                        f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" is restricted, skipping it'
                                    )
                                    session.query(Template_settings).filter_by(template_id=template_id, setting_id=setting_id, suffix=suffix).delete()
                                    continue
                                elif setting_id not in plugin_settings and setting_id not in db_settings:
                                    self.logger.error(
                                        f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" does not exist, skipping it'
                                    )
                                    session.query(Template_settings).filter_by(template_id=template_id, setting_id=setting_id, suffix=suffix).delete()
                                    continue

                                success, err = self.is_valid_setting(setting_id, value=default, multisite=True, session=session)
                                if not success:
                                    self.logger.error(
                                        f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" is not a valid template setting ({err}), skipping it'
                                    )
                                    session.query(Template_settings).filter_by(template_id=template_id, setting_id=setting_id, suffix=suffix).delete()
                                    continue

                                step_id = None
                                for step, settings in steps_settings.items():
                                    if setting in settings:
                                        step_id = step
                                        break

                                if not step_id:
                                    self.logger.error(
                                        f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" doesn\'t belong to a step, skipping it'
                                    )
                                    continue

                                template_setting = (
                                    session.query(Template_settings)
                                    .with_entities(
                                        Template_settings.id,
                                        Template_settings.step_id,
                                        Template_settings.default,
                                        Template_settings.order,
                                    )
                                    .filter_by(template_id=template_id, setting_id=setting_id, step_id=step_id, suffix=suffix)
                                    .first()
                                )

                                if not template_setting:
                                    changes = True
                                    local_to_put.append(
                                        Template_settings(
                                            template_id=template_id,
                                            setting_id=setting_id,
                                            step_id=step_id,
                                            suffix=suffix,
                                            default=default,
                                            order=order,
                                        )
                                    )
                                elif step_id != template_setting.step_id or default != template_setting.default or order != template_setting.order:
                                    changes = True
                                    session.query(Template_settings).filter_by(id=template_setting.id).update(
                                        {
                                            Template_settings.step_id: step_id,
                                            Template_settings.default: default,
                                            Template_settings.order: order,
                                        }
                                    )

                                order += 1

                            db_template_configs = [
                                f"{config.type.replace('_', '-')}/{config.name}.conf"
                                for config in session.query(Template_custom_configs)
                                .with_entities(Template_custom_configs.type, Template_custom_configs.name)
                                .filter_by(template_id=template_id)
                                .order_by(Template_custom_configs.order)
                            ]
                            missing_ids = [config for config in template_data.get("configs", {}) if config not in db_template_configs]

                            if missing_ids:
                                changes = True
                                session.query(Template_custom_configs).filter(Template_custom_configs.name.in_(missing_ids)).delete()

                            order = 0
                            for config in template_data.get("configs", []):
                                try:
                                    config_type, config_name = config.split("/", 1)
                                except ValueError:
                                    self.logger.error(
                                        f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" is invalid, skipping it'
                                    )
                                    continue

                                if config_type.replace("-", "_") not in self.MULTISITE_CUSTOM_CONFIG_TYPES:
                                    self.logger.error(
                                        f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" is not a valid type, skipping it'
                                    )
                                    continue

                                if not templates_path.joinpath(template_id, "configs", config_type, config_name).is_file():
                                    self.logger.error(
                                        f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" does not exist, skipping it'
                                    )
                                    continue

                                content = templates_path.joinpath(template_id, "configs", config_type, config_name).read_bytes()
                                config_type = config_type.strip().replace("-", "_").lower()
                                checksum = bytes_hash(content, algorithm="sha256")
                                config_name = config_name.removesuffix(".conf")

                                step_id = None
                                for step, configs in steps_configs.items():
                                    if config in configs:
                                        step_id = step
                                        break

                                if not step_id:
                                    self.logger.error(
                                        f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" doesn\'t belong to a step, skipping it'
                                    )
                                    continue

                                template_config = (
                                    session.query(Template_custom_configs)
                                    .with_entities(
                                        Template_custom_configs.id,
                                        Template_custom_configs.step_id,
                                        Template_custom_configs.checksum,
                                        Template_custom_configs.order,
                                    )
                                    .filter_by(template_id=template_id, step_id=step_id, type=config_type, name=config_name)
                                    .first()
                                )

                                if not template_config:
                                    changes = True
                                    local_to_put.append(
                                        Template_custom_configs(
                                            template_id=template_id,
                                            step_id=step_id,
                                            type=config_type,
                                            name=config_name,
                                            data=content,
                                            checksum=checksum,
                                            order=order,
                                        )
                                    )
                                elif step_id != template_config.step_id or checksum != template_config.checksum or order != template_config.order:
                                    changes = True
                                    session.query(Template_custom_configs).filter_by(id=template_config.id).update(
                                        {
                                            Template_custom_configs.step_id: step_id,
                                            Template_custom_configs.data: content,
                                            Template_custom_configs.checksum: checksum,
                                            Template_custom_configs.order: order,
                                        }
                                    )

                                order += 1

                        for template in db_names:
                            if template not in saved_templates:
                                changes = True
                                session.query(Template_steps).filter_by(template_id=template).delete()
                                session.query(Template_settings).filter_by(template_id=template).delete()
                                session.query(Template_custom_configs).filter_by(template_id=template).delete()
                                session.query(Templates).filter_by(id=template, plugin_id=plugin["id"]).delete()

                    elif db_names:
                        self.logger.warning(f'Plugin "{plugin["id"]}"\'s templates directory does not exist, removing all templates')
                        for template in db_names:
                            session.query(Templates).filter_by(id=template, plugin_id=plugin["id"]).delete()
                            session.query(Template_steps).filter_by(template_id=template).delete()
                            session.query(Template_settings).filter_by(template_id=template).delete()
                            session.query(Template_custom_configs).filter_by(template_id=template).delete()

                    try:
                        if per_plugin_commit:
                            if local_to_put:
                                _add_ordered(local_to_put)
                            # Commit also captures any .update() / .delete() executed above.
                            session.commit()
                        else:
                            to_put.extend(local_to_put)
                    except BaseException as e:
                        session.rollback()
                        return str(e)

                    continue

                changes = True
                local_to_put.append(
                    Plugins(
                        id=plugin["id"],
                        name=plugin["name"],
                        description=plugin["description"],
                        version=plugin["version"],
                        stream=plugin["stream"],
                        type=_type,
                        method=plugin["method"],
                        data=plugin.get("data"),
                        checksum=plugin.get("checksum"),
                    )
                )

                order = 0
                plugin_settings = set()
                for setting, value in settings.items():
                    db_setting = session.query(Settings).filter_by(id=setting).first()

                    if db_setting is not None:
                        self.logger.warning(f"A setting with id {setting} already exists, therefore it will not be added.")
                        continue

                    value.update({"plugin_id": plugin["id"], "name": value["id"], "id": setting})

                    for sel_order, select in enumerate(value.pop("select", []), start=1):
                        local_to_put.append(Selects(setting_id=value["id"], value=self._empty_if_none(select), order=sel_order))

                    for msel_order, multiselect in enumerate(value.pop("multiselect", []), start=1):
                        if isinstance(multiselect, dict):
                            local_to_put.append(
                                Multiselects(
                                    setting_id=value["id"],
                                    option_id=multiselect.get("id", ""),
                                    label=multiselect.get("label", ""),
                                    value=self._empty_if_none(multiselect.get("value", "")),
                                    order=msel_order,
                                )
                            )

                    local_to_put.append(Settings(**value | {"order": order}))
                    order += 1
                    plugin_settings.add(setting)

                for job in jobs:
                    db_job = session.query(Jobs).filter_by(name=job["name"], plugin_id=plugin["id"]).first()

                    if db_job is not None:
                        self.logger.warning(f"A job with the name {job['name']} already exists in the database, therefore it will not be added.")
                        continue

                    job["file_name"] = job.pop("file")
                    job["reload"] = job.get("reload", False)
                    job["run_async"] = job.pop("async", False)
                    local_to_put.append(Jobs(plugin_id=plugin["id"], **job))

                plugin_path = Path(sep, "var", "tmp", "bunkerweb", "ui", plugin["id"])
                plugin_path = (
                    plugin_path
                    if plugin_path.is_dir()
                    else (
                        Path(sep, "etc", "bunkerweb", "plugins", plugin["id"])
                        if _type == "external"
                        else Path(sep, "etc", "bunkerweb", "pro", "plugins", plugin["id"])
                    )
                )

                if page:
                    path_ui = plugin_path.joinpath("ui")
                    if path_ui.is_dir():
                        with BytesIO() as plugin_page_content:
                            with tar_open(fileobj=plugin_page_content, mode="w:gz", compresslevel=9) as tar:
                                tar.add(path_ui, arcname=path_ui.name, recursive=True)
                            plugin_page_content.seek(0)
                            checksum = bytes_hash(plugin_page_content, algorithm="sha256")

                            local_to_put.append(Plugin_pages(plugin_id=plugin["id"], data=plugin_page_content.getvalue(), checksum=checksum))

                for command, file_name in commands.items():
                    if not plugin_path.joinpath("bwcli", file_name).is_file():
                        self.logger.warning(f'Command "{command}"\'s file "{file_name}" does not exist in the plugin directory, skipping it')
                        continue

                    local_to_put.append(Bw_cli_commands(name=command, plugin_id=plugin["id"], file_name=file_name))

                templates_path = plugin_path.joinpath("templates")

                if templates_path.is_dir():
                    for template_file in plugin_path.joinpath("templates").iterdir():
                        if template_file.is_dir():
                            continue

                        try:
                            template_data = loads(template_file.read_text())
                        except JSONDecodeError:
                            self.logger.error(f'Template file "{template_file}" is not a valid JSON file')
                            continue

                        template_id = template_file.stem
                        current_time = datetime.now().astimezone()

                        local_to_put.append(
                            Templates(
                                id=template_id,
                                plugin_id=plugin["id"],
                                name=template_data.get("name", template_id),
                                method=plugin["method"],
                                creation_date=current_time,
                                last_update=current_time,
                            )
                        )

                        steps_settings = {}
                        steps_configs = {}
                        for step_id, step in enumerate(template_data.get("steps", []), start=1):
                            local_to_put.append(Template_steps(id=step_id, template_id=template_id, title=step["title"], subtitle=step["subtitle"]))

                            for setting in step.get("settings", []):
                                if step_id not in steps_settings:
                                    steps_settings[step_id] = []
                                steps_settings[step_id].append(setting)

                            for config in step.get("configs", []):
                                if step_id not in steps_configs:
                                    steps_configs[step_id] = []
                                steps_configs[step_id].append(config)

                        order = 0
                        for setting, default in template_data.get("settings", {}).items():
                            setting_id, suffix = setting.rsplit("_", 1) if self.SUFFIX_RX.search(setting) else (setting, None)
                            if suffix is not None:
                                suffix = int(suffix)
                            else:
                                suffix = 0

                            if setting_id in self.RESTRICTED_TEMPLATE_SETTINGS:
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" is restricted, skipping it'
                                )
                                continue
                            elif setting_id not in plugin_settings and setting_id not in db_settings:
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" does not exist, skipping it'
                                )
                                continue

                            success, err = self.is_valid_setting(setting_id, value=default, multisite=True, session=session)
                            if not success:
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" is not a valid template setting ({err}), skipping it'
                                )
                                continue

                            step_id = None
                            for step, settings in steps_settings.items():
                                if setting in settings:
                                    step_id = step
                                    break

                            if not step_id:
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" doesn\'t belong to a step, skipping it'
                                )
                                continue

                            local_to_put.append(
                                Template_settings(
                                    template_id=template_id,
                                    setting_id=setting_id,
                                    step_id=step_id,
                                    default=default,
                                    suffix=suffix,
                                    order=order,
                                )
                            )
                            order += 1

                        order = 0
                        for config in template_data.get("configs", []):
                            try:
                                config_type, config_name = config.split("/", 1)
                            except ValueError:
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" is invalid, skipping it'
                                )
                                continue

                            if config_type.replace("-", "_") not in self.MULTISITE_CUSTOM_CONFIG_TYPES:
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" is not a valid type, skipping it'
                                )
                                continue

                            if not templates_path.joinpath(template_id, "configs", config_type, config_name).is_file():
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" does not exist, skipping it'
                                )
                                continue

                            content = templates_path.joinpath(template_id, "configs", config_type, config_name).read_bytes()
                            config_type = config_type.strip().replace("-", "_").lower()
                            checksum = bytes_hash(content, algorithm="sha256")
                            config_name = config_name.removesuffix(".conf")

                            step_id = None
                            for step, configs in steps_configs.items():
                                if config in configs:
                                    step_id = step
                                    break

                            if not step_id:
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" doesn\'t belong to a step, skipping it'
                                )
                                continue

                            local_to_put.append(
                                Template_custom_configs(
                                    template_id=template_id,
                                    step_id=step_id,
                                    type=config_type,
                                    name=config_name,
                                    data=content,
                                    checksum=checksum,
                                    order=order,
                                )
                            )
                            order += 1

                try:
                    if per_plugin_commit:
                        if local_to_put:
                            _add_ordered(local_to_put)
                        # Commit also captures any .update() / .delete() executed above.
                        session.commit()
                    else:
                        to_put.extend(local_to_put)
                except BaseException as e:
                    session.rollback()
                    return str(e)

            if changes:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        if _type in ("external", "ui"):
                            metadata.external_plugins_changed = True
                            metadata.last_external_plugins_change = datetime.now().astimezone()
                            metadata.reload_ui_plugins = True
                        elif _type == "pro":
                            metadata.pro_plugins_changed = True
                            metadata.last_pro_plugins_change = datetime.now().astimezone()
                            metadata.reload_ui_plugins = True

            try:
                if not per_plugin_commit and to_put:
                    _add_ordered(to_put)
                session.commit()
            except BaseException as e:
                session.rollback()
                return str(e)

        return ""

    def delete_plugin(self, plugin_id: str, method: str, *, changes: bool = True) -> str:
        """Delete a plugin from the database."""
        with self._db_session() as session:
            plugin = session.query(Plugins).filter_by(id=plugin_id, method=method).first()
            if not plugin:
                return f"Plugin with id {plugin_id} and method {method} not found"

            session.query(Plugins).filter_by(id=plugin_id, method=method).delete()
            for db_setting in session.query(Settings).filter_by(plugin_id=plugin_id).all():
                session.query(Selects).filter_by(setting_id=db_setting.id).delete()
                session.query(Multiselects).filter_by(setting_id=db_setting.id).delete()
                session.query(Services_settings).filter_by(setting_id=db_setting.id).delete()
                session.query(Global_values).filter_by(setting_id=db_setting.id).delete()
                session.query(Template_settings).filter_by(setting_id=db_setting.id).delete()
                session.query(Settings).filter_by(id=db_setting.id).delete()

            for db_job in session.query(Jobs).filter_by(plugin_id=plugin_id).all():
                session.query(Jobs_cache).filter_by(job_name=db_job.name).delete()
                session.query(Jobs_runs).filter_by(job_name=db_job.name).delete()
                session.query(Jobs).filter_by(name=db_job.name).delete()

            session.query(Plugin_pages).filter_by(plugin_id=plugin_id).delete()
            session.query(Bw_cli_commands).filter_by(plugin_id=plugin_id).delete()

            for db_template in session.query(Templates).filter_by(plugin_id=plugin_id).all():
                session.query(Template_steps).filter_by(template_id=db_template.id).delete()
                session.query(Template_settings).filter_by(template_id=db_template.id).delete()
                session.query(Template_custom_configs).filter_by(template_id=db_template.id).delete()
                session.query(Templates).filter_by(id=db_template.id).delete()

            if changes:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        if method in ("external", "ui"):
                            metadata.external_plugins_changed = True
                            metadata.last_external_plugins_change = datetime.now().astimezone()
                            metadata.reload_ui_plugins = True
                        elif method == "pro":
                            metadata.pro_plugins_changed = True
                            metadata.last_pro_plugins_change = datetime.now().astimezone()
                            metadata.reload_ui_plugins = True

            try:
                session.commit()
            except BaseException as e:
                return str(e)
        return ""

    def get_plugins(self, *, _type: Literal["all", "external", "ui", "pro"] = "all", with_data: bool = False) -> List[Dict[str, Any]]:
        """Get all plugins from the database using batched queries to avoid N+1 issues."""
        with self._db_session() as session:
            # Build the base query.
            entities = [
                Plugins.id,
                Plugins.stream,
                Plugins.name,
                Plugins.description,
                Plugins.version,
                Plugins.type,
                Plugins.method,
                Plugins.checksum,
            ]
            if with_data:
                entities.append(Plugins.data)

            query = session.query(Plugins).with_entities(*entities)
            if _type == "external":
                query = query.filter(Plugins.type.in_(["external", "ui"]))
            elif _type != "all":
                query = query.filter_by(type=_type)

            plugins_list = query.all()
            plugin_ids = [plugin.id for plugin in plugins_list]

            # Pre-fetch plugin pages.
            pages = session.query(Plugin_pages.plugin_id).filter(Plugin_pages.plugin_id.in_(plugin_ids)).all()
            pages_map = {page.plugin_id: True for page in pages}

            # Pre-fetch settings.
            settings_rows = session.query(Settings).filter(Settings.plugin_id.in_(plugin_ids)).order_by(Settings.order).all()
            settings_map = {}
            # Also, collect setting IDs for select-type settings.
            select_setting_ids = [s.id for s in settings_rows if s.type == "select"]

            for setting in settings_rows:
                settings_map.setdefault(setting.plugin_id, []).append(setting)

            # Pre-fetch selects for settings of type "select".
            selects_map: Dict[str, List[Any]] = {}
            if select_setting_ids:
                selects = session.query(Selects).filter(Selects.setting_id.in_(select_setting_ids)).order_by(Selects.order).all()
                for sel in selects:
                    selects_map.setdefault(sel.setting_id, []).append(self._empty_if_none(sel.value))

            # Pre-fetch multiselects for settings of type "multiselect".
            multiselect_setting_ids = [s.id for s in settings_rows if s.type == "multiselect"]
            multiselects_map: Dict[str, List[Dict[str, Any]]] = {}
            if multiselect_setting_ids:
                multiselects = session.query(Multiselects).filter(Multiselects.setting_id.in_(multiselect_setting_ids)).order_by(Multiselects.order).all()
                for msel in multiselects:
                    multiselects_map.setdefault(msel.setting_id, []).append(
                        {"id": msel.option_id, "label": msel.label, "value": self._empty_if_none(msel.value)}
                    )

            # Pre-fetch bw_cli commands.
            commands_rows = session.query(Bw_cli_commands).filter(Bw_cli_commands.plugin_id.in_(plugin_ids)).all()
            commands_map: Dict[str, Dict[str, Any]] = {}
            for cmd in commands_rows:
                commands_map.setdefault(cmd.plugin_id, {})[cmd.name] = cmd.file_name

            # Assemble the plugin data.
            result = []
            for plugin in plugins_list:
                plugin_data: Dict[str, Any] = {
                    "id": plugin.id,
                    "stream": plugin.stream,
                    "name": plugin.name,
                    "description": plugin.description,
                    "version": plugin.version,
                    "type": plugin.type,
                    "method": plugin.method,
                    "page": pages_map.get(plugin.id, False),
                    "settings": {},
                    "checksum": plugin.checksum,
                }
                if with_data:
                    plugin_data["data"] = plugin.data

                for setting in settings_map.get(plugin.id, []):
                    setting_data = {
                        "context": setting.context,
                        "default": self._empty_if_none(setting.default),
                        "help": setting.help,
                        "id": setting.name,
                        "label": setting.label,
                        "regex": setting.regex,
                        "type": setting.type,
                    }
                    if setting.multiple:
                        setting_data["multiple"] = setting.multiple
                    if setting.type == "select":
                        setting_data["select"] = selects_map.get(setting.id, [])
                    elif setting.type == "multiselect":
                        setting_data["multiselect"] = multiselects_map.get(setting.id, [])
                    elif setting.type == "multivalue":
                        setting_data["separator"] = getattr(setting, "separator", " ")
                    plugin_data["settings"][setting.id] = setting_data

                if plugin.id in commands_map:
                    plugin_data["bwcli"] = commands_map[plugin.id]

                result.append(plugin_data)

            return result

    def get_plugins_errors(self) -> int:
        """Get plugins errors."""
        with self._db_session() as session:
            # Subquery to get the latest run for each job
            latest_runs_subquery = (
                session.query(Jobs_runs.job_name, func.max(Jobs_runs.end_date).label("latest_end_date")).group_by(Jobs_runs.job_name).subquery()
            )

            # Main query to fetch latest job runs and count errors
            latest_job_runs = (
                session.query(Jobs_runs.job_name, Jobs_runs.success)
                .join(
                    latest_runs_subquery,
                    (Jobs_runs.job_name == latest_runs_subquery.c.job_name) & (Jobs_runs.end_date == latest_runs_subquery.c.latest_end_date),
                )
                .all()
            )

            return sum(1 for job_run in latest_job_runs if not job_run.success)

    def get_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Get jobs."""
        with self._db_session() as session:
            return {
                job.name: {
                    "plugin_id": job.plugin_id,
                    "every": job.every,
                    "reload": job.reload,
                    "async": job.run_async,
                    "history": [
                        {
                            "start_date": job_run.start_date.astimezone().isoformat(),
                            "end_date": job_run.end_date.astimezone().isoformat(),
                            "success": job_run.success,
                        }
                        for job_run in session.query(Jobs_runs)
                        .with_entities(Jobs_runs.success, Jobs_runs.start_date, Jobs_runs.end_date)
                        .filter_by(job_name=job.name)
                        .order_by(Jobs_runs.end_date.desc())
                        .limit(10)
                    ],
                    "cache": [
                        {
                            "service_id": cache.service_id,
                            "file_name": cache.file_name,
                            "last_update": cache.last_update.strftime("%Y/%m/%d, %H:%M:%S %Z") if cache.last_update else "Never",
                            "checksum": cache.checksum,
                        }
                        for cache in session.query(Jobs_cache)
                        .with_entities(Jobs_cache.service_id, Jobs_cache.file_name, Jobs_cache.last_update, Jobs_cache.checksum)
                        .filter_by(job_name=job.name)
                    ],
                }
                for job in session.query(Jobs).with_entities(Jobs.name, Jobs.plugin_id, Jobs.every, Jobs.reload, Jobs.run_async)
            }

    def get_job_cache_file(
        self, job_name: str, file_name: str, *, service_id: str = "", plugin_id: str = "", with_info: bool = False, with_data: bool = True
    ) -> Optional[Union[Dict[str, Any], bytes]]:
        """Get job cache file."""
        entities = []
        if with_info:
            entities.extend([Jobs_cache.last_update, Jobs_cache.checksum])
        if with_data:
            entities.append(Jobs_cache.data)

        filters = {"job_name": job_name, "file_name": file_name, "service_id": service_id or None}

        with self._db_session() as session:
            if plugin_id:
                job = session.query(Jobs).filter_by(name=job_name, plugin_id=plugin_id).first()
                if not job:
                    return None
            data = session.query(Jobs_cache).with_entities(*entities).filter_by(**filters).first()

        if not data:
            return None
        elif with_data and not with_info:
            return data.data

        ret_data = {}
        if with_info:
            ret_data["last_update"] = data.last_update.timestamp() if data.last_update is not None else "Never"
            ret_data["checksum"] = data.checksum
        if with_data:
            ret_data["data"] = data.data
        return ret_data

    def get_jobs_cache_files(self, *, with_data: bool = True, job_name: str = "", plugin_id: str = "") -> List[Dict[str, Any]]:
        """Get jobs cache files."""
        with self._db_session() as session:
            filters = {}
            entities = [Jobs_cache.job_name, Jobs_cache.service_id, Jobs_cache.file_name, Jobs_cache.last_update, Jobs_cache.checksum]
            if with_data:
                entities.append(Jobs_cache.data)
            query = session.query(Jobs_cache).with_entities(*entities)

            if job_name:
                query = query.filter_by(job_name=job_name)
                filters["name"] = job_name

            db_cache = query.all()

            if not db_cache:
                return []

            if plugin_id:
                filters["plugin_id"] = plugin_id

            query = session.query(Jobs).with_entities(Jobs.name, Jobs.plugin_id)

            if filters:
                query = query.filter_by(**filters)

            jobs = {}
            for job in query:
                jobs[job.name] = job.plugin_id

            if not jobs:
                return []

            cache_files = []
            for cache in db_cache:
                if cache.job_name not in jobs:
                    continue
                cache_files.append(
                    {
                        "plugin_id": jobs[cache.job_name],
                        "job_name": cache.job_name,
                        "service_id": cache.service_id,
                        "file_name": cache.file_name,
                        "last_update": cache.last_update if cache.last_update is not None else "Never",
                        "checksum": cache.checksum,
                    }
                )
                if with_data:
                    cache_files[-1]["data"] = cache.data

            return cache_files

    def add_instance(
        self,
        hostname: str,
        port: int,
        server_name: str,
        method: str,
        changed: Optional[bool] = True,
        *,
        name: Optional[str] = None,
        listen_https: bool = False,
        https_port: int = 5443,
    ) -> str:
        """Add instance."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            db_instance = session.query(Instances).with_entities(Instances.hostname).filter_by(hostname=hostname).first()

            if db_instance is not None:
                return f"Instance {hostname} already exists, will not be added."

            current_time = datetime.now().astimezone()
            session.add(
                Instances(
                    hostname=hostname,
                    name=name or "manual instance",
                    port=port,
                    listen_https=listen_https,
                    https_port=https_port,
                    server_name=server_name,
                    method=method,
                    creation_date=current_time,
                    last_seen=current_time,
                )
            )

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        metadata.instances_changed = True
                        metadata.last_instances_change = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while adding the instance {hostname} (port: {port}, server name: {server_name}, method: {method}).\n{e}"

        return ""

    def delete_instances(self, hostnames: List[str], changed: Optional[bool] = True) -> str:
        """Delete instances."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            db_instances = session.query(Instances).filter(Instances.hostname.in_(hostnames)).all()

            if not db_instances:
                return "No instances found to delete."

            for db_instance in db_instances:
                session.delete(db_instance)

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        metadata.instances_changed = True
                        metadata.last_instances_change = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while deleting the instances {', '.join(hostnames)}.\n{e}"

        return ""

    def delete_instance(self, hostname: str, changed: Optional[bool] = True) -> str:
        """Delete instance."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            db_instance = session.query(Instances).filter_by(hostname=hostname).first()

            if db_instance is None:
                return f"Instance {hostname} does not exist, will not be deleted."

            session.delete(db_instance)

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        metadata.instances_changed = True
                        metadata.last_instances_change = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while deleting the instance {hostname}.\n{e}"

        return ""

    def update_instances(self, instances: List[Dict[str, Any]], method: str, changed: Optional[bool] = True) -> str:
        """Update instances."""
        to_put = []
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            session.query(Instances).filter(Instances.method == method).delete()

            for instance in instances:
                if instance.get("hostname") is None:
                    continue

                current_time = datetime.now().astimezone()

                db_instance = session.query(Instances).filter_by(hostname=instance["hostname"]).first()
                if db_instance is not None:
                    db_instance.name = instance.get("name", "manual instance")
                    db_instance.port = instance["env"].get("API_HTTP_PORT", 5000)
                    db_instance.listen_https = instance["env"].get("API_LISTEN_HTTPS", "no") == "yes"
                    db_instance.https_port = instance["env"].get("API_HTTPS_PORT", 5443)
                    db_instance.server_name = instance["env"].get("API_SERVER_NAME", "bwapi")
                    db_instance.type = instance.get("type", "static")
                    db_instance.status = instance.get("status", "up" if instance.get("health", True) else "down")
                    db_instance.method = instance.get("method", method)
                    db_instance.last_seen = instance.get("last_seen", current_time)
                    to_put.append(db_instance)
                    continue

                to_put.append(
                    Instances(
                        hostname=instance["hostname"],
                        name=instance.get("name", "manual instance"),
                        port=instance["env"].get("API_HTTP_PORT", 5000),
                        listen_https=instance["env"].get("API_LISTEN_HTTPS", "no") == "yes",
                        https_port=instance["env"].get("API_HTTPS_PORT", 5443),
                        server_name=instance["env"].get("API_SERVER_NAME", "bwapi"),
                        type=instance.get("type", "static"),
                        status="up" if instance.get("health", True) else "down",
                        method=instance.get("method", method),
                        creation_date=instance.get("creation_date", current_time),
                        last_seen=instance.get("last_seen", current_time),
                    )
                )

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        metadata.instances_changed = True
                        metadata.last_instances_change = datetime.now().astimezone()

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def update_instance(self, hostname: str, status: str) -> str:
        """Update instance."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            db_instance = session.query(Instances).filter_by(hostname=hostname).first()

            if db_instance is None:
                return f"Instance {hostname} does not exist, will not be updated."

            db_instance.status = status
            if status != "down":
                db_instance.last_seen = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while updating the instance {hostname}.\n{e}"

        return ""

    def update_instance_fields(
        self,
        hostname: str,
        *,
        name: Optional[str] = None,
        port: Optional[int] = None,
        listen_https: Optional[bool] = None,
        https_port: Optional[int] = None,
        server_name: Optional[str] = None,
        method: Optional[str] = None,
        changed: Optional[bool] = True,
    ) -> str:
        """Update instance metadata fields (name, port, server_name, method)."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            db_instance = session.query(Instances).filter_by(hostname=hostname).first()
            if db_instance is None:
                return f"Instance {hostname} does not exist, will not be updated."

            if name is not None:
                db_instance.name = name
            if port is not None:
                db_instance.port = port
            if listen_https is not None:
                db_instance.listen_https = listen_https
            if https_port is not None:
                db_instance.https_port = https_port
            if server_name is not None:
                db_instance.server_name = server_name
            if method is not None:
                db_instance.method = method

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        metadata.instances_changed = True
                        metadata.last_instances_change = datetime.now().astimezone()

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while updating the instance {hostname}.\n{e}"

        return ""

    def get_instances(self, *, method: Optional[str] = None, autoconf: bool = False) -> List[Dict[str, Any]]:
        """Get instances."""
        with self._db_session() as session:
            query = session.query(Instances)
            if method:
                query = query.filter_by(method=method)

            return [
                {
                    "hostname": instance.hostname,
                    "name": instance.name,
                    "port": instance.port,
                    "listen_https": instance.listen_https,
                    "https_port": instance.https_port,
                    "server_name": instance.server_name,
                    "type": instance.type,
                    "status": instance.status,
                    "method": instance.method,
                    "creation_date": instance.creation_date,
                    "last_seen": instance.last_seen,
                }
                | ({"health": instance.status == "up", "env": {}} if autoconf else {})
                for instance in query
            ]

    def get_instance(self, hostname: str, *, method: Optional[str] = None) -> Dict[str, Any]:
        """Get instance."""
        with self._db_session() as session:
            query = session.query(Instances).filter_by(hostname=hostname)
            if method:
                query = query.filter_by(method=method)

            instance = query.first()

            if not instance:
                return {}

            return {
                "hostname": instance.hostname,
                "name": instance.name,
                "port": instance.port,
                "listen_https": instance.listen_https,
                "https_port": instance.https_port,
                "server_name": instance.server_name,
                "type": instance.type,
                "status": instance.status,
                "method": instance.method,
                "creation_date": instance.creation_date,
                "last_seen": instance.last_seen,
            }

    def get_plugin_page(self, plugin_id: str) -> Optional[bytes]:
        """Get plugin page."""
        with self._db_session() as session:
            page = session.query(Plugin_pages).with_entities(Plugin_pages.data).filter_by(plugin_id=plugin_id).first()

            if not page:
                return None

            return page.data

    def get_templates(self, plugin: Optional[str] = None) -> Dict[str, dict]:
        """Get templates."""
        with self._db_session() as session:
            query = (
                session.query(Templates)
                .with_entities(Templates.id, Templates.plugin_id, Templates.name, Templates.method, Templates.creation_date, Templates.last_update)
                .order_by(case((Templates.id == "low", 1), (Templates.id == "medium", 2), (Templates.id == "high", 3), else_=4), Templates.name)
            )

            if plugin:
                query = query.filter_by(plugin_id=plugin)

            templates = {}
            for template in query:
                templates[template.id] = {
                    "plugin_id": template.plugin_id,
                    "name": template.name,
                    "method": template.method,
                    "creation_date": template.creation_date,
                    "last_update": template.last_update,
                    "settings": {},
                    "configs": {},
                    "steps": [],
                }

                steps_settings = {}
                for setting in (
                    session.query(Template_settings)
                    .with_entities(Template_settings.setting_id, Template_settings.step_id, Template_settings.default, Template_settings.suffix)
                    .filter_by(template_id=template.id)
                    .order_by(Template_settings.order)
                ):
                    key = f"{setting.setting_id}_{setting.suffix}" if setting.suffix else setting.setting_id
                    templates[template.id]["settings"][key] = self._empty_if_none(setting.default)

                    if setting.step_id:
                        if setting.step_id not in steps_settings:
                            steps_settings[setting.step_id] = []
                        steps_settings[setting.step_id].append(key)

                steps_configs = {}
                for config in (
                    session.query(Template_custom_configs)
                    .with_entities(Template_custom_configs.step_id, Template_custom_configs.type, Template_custom_configs.name, Template_custom_configs.data)
                    .filter_by(template_id=template.id)
                    .order_by(Template_custom_configs.order)
                ):
                    key = f"{config.type}/{config.name}.conf"
                    templates[template.id]["configs"][key] = config.data.decode("utf-8")

                    if config.step_id:
                        if config.step_id not in steps_configs:
                            steps_configs[config.step_id] = []
                        steps_configs[config.step_id].append(key)

                for step in (
                    session.query(Template_steps)
                    .with_entities(Template_steps.id, Template_steps.title, Template_steps.subtitle)
                    .filter_by(template_id=template.id)
                    .order_by(Template_steps.id)
                ):
                    step_data = {"title": step.title, "subtitle": self._empty_if_none(step.subtitle)}
                    if step.id in steps_settings:
                        step_data["settings"] = steps_settings[step.id]
                    if step.id in steps_configs:
                        step_data["configs"] = steps_configs[step.id]
                    templates[template.id]["steps"].append(step_data)

            return templates

    def get_template_details(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a template with full metadata for edition."""
        with self._db_session() as session:
            template = session.query(Templates).filter_by(id=template_id).first()
            if not template:
                return None

            steps: List[Dict[str, Any]] = []
            step_lookup: Dict[int, Dict[str, Any]] = {}
            for step in (
                session.query(Template_steps)
                .with_entities(Template_steps.id, Template_steps.title, Template_steps.subtitle)
                .filter_by(template_id=template_id)
                .order_by(Template_steps.id)
            ):
                data = {
                    "id": step.id,
                    "title": step.title,
                    "subtitle": self._empty_if_none(step.subtitle),
                    "settings": [],
                    "configs": [],
                }
                steps.append(data)
                step_lookup[step.id] = data

            settings_payload: List[Dict[str, Any]] = []
            for setting in (
                session.query(Template_settings)
                .with_entities(
                    Template_settings.setting_id,
                    Template_settings.step_id,
                    Template_settings.default,
                    Template_settings.suffix,
                    Template_settings.order,
                )
                .filter_by(template_id=template_id)
                .order_by(Template_settings.order)
            ):
                key = f"{setting.setting_id}_{setting.suffix}" if setting.suffix else setting.setting_id
                payload = {
                    "key": key,
                    "setting_id": setting.setting_id,
                    "suffix": setting.suffix or 0,
                    "default": self._empty_if_none(setting.default),
                    "step_id": setting.step_id,
                    "order": setting.order,
                }
                settings_payload.append(payload)
                if setting.step_id in step_lookup:
                    step_lookup[setting.step_id]["settings"].append(key)

            configs_payload: List[Dict[str, Any]] = []
            for config in (
                session.query(Template_custom_configs)
                .with_entities(
                    Template_custom_configs.type,
                    Template_custom_configs.name,
                    Template_custom_configs.step_id,
                    Template_custom_configs.data,
                    Template_custom_configs.order,
                )
                .filter_by(template_id=template_id)
                .order_by(Template_custom_configs.order)
            ):
                key = f"{config.type}/{config.name}.conf"
                payload = {
                    "key": key,
                    "type": config.type,
                    "name": config.name,
                    "step_id": config.step_id,
                    "data": config.data.decode("utf-8", errors="replace"),
                    "order": config.order,
                }
                configs_payload.append(payload)
                if config.step_id in step_lookup:
                    step_lookup[config.step_id]["configs"].append(key)

            return {
                "id": template.id,
                "name": template.name,
                "plugin_id": template.plugin_id,
                "method": template.method,
                "creation_date": template.creation_date,
                "last_update": template.last_update,
                "steps": steps,
                "settings": settings_payload,
                "configs": configs_payload,
            }

    def get_template_settings(self, template_id: str) -> Dict[str, Any]:
        """Get templates settings."""
        with self._db_session() as session:
            settings = {}
            for setting in (
                session.query(Template_settings)
                .with_entities(Template_settings.setting_id, Template_settings.default, Template_settings.suffix)
                .filter_by(template_id=template_id)
                .order_by(Template_settings.order)
            ):
                settings[f"{setting.setting_id}_{setting.suffix}" if setting.suffix else setting.setting_id] = self._empty_if_none(setting.default)
            return settings

    def _prepare_template_entities(
        self,
        session,
        template_id: str,
        settings: Dict[str, Any],
        steps: List[Dict[str, Any]],
        configs: Optional[List[Dict[str, Any]]],
    ) -> Tuple[Optional[str], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Validate the incoming template payload and prepare ORM-ready entity dictionaries."""

        if not steps:
            return "A template must contain at least one step", [], [], []

        normalized_settings: Dict[str, str] = {}
        for raw_key, raw_value in settings.items():
            if not isinstance(raw_key, str) or not raw_key.strip():
                return "Template settings keys must be non-empty strings", [], [], []
            normalized_settings[raw_key.strip()] = "" if raw_value is None else str(raw_value)

        step_entities: List[Dict[str, Any]] = []
        step_assignments: Dict[str, int] = {}
        ordered_setting_keys: List[str] = []
        config_step_map: Dict[str, int] = {}

        for index, step in enumerate(steps, start=1):
            title = str(step.get("title", "")).strip()
            if not title:
                return f"Step {index} must have a title", [], [], []

            subtitle_value = step.get("subtitle")
            subtitle = None
            if subtitle_value is not None:
                subtitle = str(subtitle_value).strip() or None

            step_entities.append(
                {
                    "id": index,
                    "template_id": template_id,
                    "title": title,
                    "subtitle": subtitle,
                }
            )

            step_settings = step.get("settings") or []
            if not isinstance(step_settings, list):
                return f"Step {index} settings must be a list", [], [], []

            for setting_ref_raw in step_settings:
                if not isinstance(setting_ref_raw, str):
                    return f"Step {index} contains an invalid setting reference", [], [], []
                setting_ref = setting_ref_raw.strip()
                if setting_ref not in normalized_settings:
                    return f"Step {index} references unknown setting {setting_ref}", [], [], []
                if setting_ref in step_assignments:
                    return f"Setting {setting_ref} is assigned to multiple steps", [], [], []
                step_assignments[setting_ref] = index
                ordered_setting_keys.append(setting_ref)

            step_configs = step.get("configs") or []
            if step_configs is None:
                step_configs = []
            if not isinstance(step_configs, list):
                return f"Step {index} configs must be a list", [], [], []

            for config_ref_raw in step_configs:
                if not isinstance(config_ref_raw, str):
                    return f"Step {index} contains an invalid config reference", [], [], []
                normalized_ref = self._normalize_template_config_reference(config_ref_raw)
                if not normalized_ref:
                    return f"Step {index} contains an invalid config reference", [], [], []
                if normalized_ref in config_step_map:
                    return f"Config {normalized_ref} is assigned to multiple steps", [], [], []
                config_step_map[normalized_ref] = index

        missing_settings = [key for key in normalized_settings.keys() if key not in step_assignments]
        if missing_settings:
            return f"Settings {', '.join(missing_settings)} are not assigned to any step", [], [], []

        base_setting_ids: Set[str] = set()
        setting_entities: List[Dict[str, Any]] = []
        for order, setting_key in enumerate(ordered_setting_keys, start=1):
            setting_id, suffix = self._split_setting_key(setting_key)
            if setting_id in self.RESTRICTED_TEMPLATE_SETTINGS:
                return f"Setting {setting_id} cannot be part of a template", [], [], []
            base_setting_ids.add(setting_id)
            setting_entities.append(
                {
                    "template_id": template_id,
                    "setting_id": setting_id,
                    "suffix": suffix,
                    "step_id": step_assignments[setting_key],
                    "default": self._empty_if_none(normalized_settings[setting_key]),
                    "order": order,
                }
            )

        if base_setting_ids:
            existing_settings = {row[0] for row in session.query(Settings.id).filter(Settings.id.in_(base_setting_ids))}
            missing_base_ids = sorted(base_setting_ids - existing_settings)
            if missing_base_ids:
                return f"Unknown settings: {', '.join(missing_base_ids)}", [], [], []

        configs = configs or []
        config_map: Dict[str, Tuple[Dict[str, Any], int]] = {}
        for index, config in enumerate(configs):
            if not isinstance(config, dict):
                return "Config entries must be objects", [], [], []
            raw_type = str(config.get("type", "")).strip()
            normalized_type = raw_type.replace("-", "_").lower()
            raw_name = str(config.get("name", "")).strip()
            normalized_ref = self._normalize_template_config_reference(f"{normalized_type}/{raw_name}")
            if not normalized_ref:
                return f"Invalid config definition at index {index + 1}", [], [], []
            ref = normalized_ref
            if ref in config_map:
                return f"Duplicate config {ref}", [], [], []
            data_raw = config.get("data", "")
            data_str = data_raw if isinstance(data_raw, str) else str(data_raw)
            cfg_type, cfg_name_conf = ref.split("/", 1)
            cfg_name = cfg_name_conf.replace(".conf", "")
            config_map[ref] = (config | {"type": cfg_type, "name": cfg_name, "data": data_str}, index)

        for ref in config_step_map:
            if ref not in config_map:
                return f"Step references unknown config {ref}", [], [], []

        for ref in config_map:
            if ref not in config_step_map:
                return f"Config {ref} is not assigned to any step", [], [], []

        ordered_configs: List[Tuple[int, int, str]] = []
        for ref, (config, original_index) in config_map.items():
            provided_order = config.get("order")
            sort_key = provided_order if isinstance(provided_order, int) else original_index
            ordered_configs.append((sort_key, original_index, ref))

        ordered_configs.sort()

        config_entities: List[Dict[str, Any]] = []
        for order, (_, _, ref) in enumerate(ordered_configs, start=1):
            config, _ = config_map[ref]
            data_bytes = config["data"].encode("utf-8")
            checksum = bytes_hash(data_bytes, algorithm="sha256")
            cfg_type, cfg_name_conf = ref.split("/", 1)
            cfg_name = cfg_name_conf.replace(".conf", "")
            config_entities.append(
                {
                    "template_id": template_id,
                    "step_id": config_step_map[ref],
                    "type": cfg_type,
                    "name": cfg_name,
                    "data": data_bytes,
                    "checksum": checksum,
                    "order": order,
                }
            )

        return None, step_entities, setting_entities, config_entities

    def create_template(
        self,
        template_id: str,
        *,
        plugin_id: Optional[str] = None,
        name: str,
        settings: Dict[str, Any],
        steps: List[Dict[str, Any]],
        configs: Optional[List[Dict[str, Any]]] = None,
        method: str = "ui",
    ) -> str:
        """Create a new template."""

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            template_id = template_id.strip()
            if not template_id:
                return "Template id is required"

            normalized_name = name.strip()
            if not normalized_name:
                return "Template name cannot be empty"

            normalized_plugin = None
            if isinstance(plugin_id, str):
                normalized_value = plugin_id.strip()
                normalized_plugin = normalized_value or None

            if session.query(Templates.id).filter_by(id=template_id).first():
                return f"Template {template_id} already exists"

            if session.query(Templates.id).filter(Templates.name == normalized_name).first():
                return f"Template name {normalized_name} already exists"

            if normalized_plugin:
                if session.query(Plugins.id).filter_by(id=normalized_plugin).first() is None:
                    return f"Plugin {normalized_plugin} does not exist"

            error, step_entities, setting_entities, config_entities = self._prepare_template_entities(session, template_id, settings, steps, configs)
            if error:
                return error

            current_time = datetime.now().astimezone()
            session.add(
                Templates(
                    id=template_id,
                    plugin_id=normalized_plugin,
                    name=normalized_name,
                    method=method or "ui",
                    creation_date=current_time,
                    last_update=current_time,
                )
            )

            for step in step_entities:
                session.add(Template_steps(**step))

            for setting in setting_entities:
                session.add(Template_settings(**setting))

            for config_row in config_entities:
                config_row["type"] = config_row["type"].strip().replace("-", "_").lower()
                session.add(Template_custom_configs(**config_row))

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while creating template {template_id}.\n{e}"

        return ""

    def update_template(
        self,
        template_id: str,
        *,
        plugin_id: Optional[str] = None,
        name: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None,
        steps: Optional[List[Dict[str, Any]]] = None,
        configs: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Update an existing template."""

        current_details = self.get_template_details(template_id)
        if not current_details:
            return "Template not found"

        current_settings = {item["key"]: item.get("default", "") for item in current_details.get("settings", [])}
        current_steps = [
            {
                "title": step.get("title", ""),
                "subtitle": step.get("subtitle"),
                "settings": step.get("settings", []),
                "configs": step.get("configs", []),
            }
            for step in current_details.get("steps", [])
        ]
        current_configs = [
            {
                "type": cfg.get("type", ""),
                "name": cfg.get("name", ""),
                "data": cfg.get("data", ""),
                "order": cfg.get("order"),
            }
            for cfg in current_details.get("configs", [])
        ]

        effective_settings = settings if settings is not None else current_settings
        effective_steps = steps if steps is not None else current_steps
        effective_configs = configs if configs is not None else current_configs

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            template = session.query(Templates).filter_by(id=template_id).first()
            if template is None:
                return "Template not found"

            if plugin_id is not None:
                normalized_plugin = None
                if isinstance(plugin_id, str):
                    normalized_value = plugin_id.strip()
                    normalized_plugin = normalized_value or None
                else:
                    normalized_plugin = str(plugin_id) or None

                if normalized_plugin != template.plugin_id:
                    if normalized_plugin and session.query(Plugins.id).filter_by(id=normalized_plugin).first() is None:
                        return f"Plugin {normalized_plugin} does not exist"
                    template.plugin_id = normalized_plugin

            if name is not None:
                normalized_name = name.strip()
                if not normalized_name:
                    return "Template name cannot be empty"
                conflict = session.query(Templates.id).filter(Templates.name == normalized_name, Templates.id != template_id).first()
                if conflict:
                    return f"Template name {normalized_name} already exists"

                template.name = normalized_name

            template.method = "ui"
            template.last_update = datetime.now().astimezone()

            error, step_entities, setting_entities, config_entities = self._prepare_template_entities(
                session, template_id, effective_settings, effective_steps, effective_configs
            )
            if error:
                return error

            session.query(Template_custom_configs).filter_by(template_id=template_id).delete(synchronize_session=False)
            session.query(Template_settings).filter_by(template_id=template_id).delete(synchronize_session=False)
            session.query(Template_steps).filter_by(template_id=template_id).delete(synchronize_session=False)

            for step in step_entities:
                session.add(Template_steps(**step))

            for setting in setting_entities:
                session.add(Template_settings(**setting))

            for config_row in config_entities:
                config_row["type"] = config_row["type"].strip().replace("-", "_").lower()
                session.add(Template_custom_configs(**config_row))

            session.query(Plugins).filter(Plugins.id.in_(set(plugin.id for plugin in session.query(Plugins).with_entities(Plugins.id).all()))).update(
                {Plugins.config_changed: True}, synchronize_session=False
            )

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while updating template {template_id}.\n{e}"

        return ""

    def delete_template(self, template_id: str) -> str:
        """Delete a template when it is not referenced by any configuration."""

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            template = session.query(Templates).filter_by(id=template_id).first()
            if template is None:
                return "Template not found"

            global_reference = session.query(Global_values.id).filter_by(setting_id="USE_TEMPLATE", value=template_id).first()
            if global_reference:
                return "Template is currently used by the global settings"

            service_reference = session.query(Services_settings.id).filter_by(setting_id="USE_TEMPLATE", value=template_id).first()
            if service_reference:
                return "Template is currently used by a service"

            session.delete(template)
            session.query(Plugins).filter(Plugins.id.in_(set(plugin.id for plugin in session.query(Plugins).with_entities(Plugins.id).all()))).update(
                {Plugins.config_changed: True}, synchronize_session=False
            )

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while deleting template {template_id}.\n{e}"

        return ""

    def get_ui_users(self, *, as_dict: bool = False) -> Union[str, List[Union[Users, dict]]]:
        """Get ui users."""
        with self._db_session() as session:
            try:
                users = session.query(Users).options(joinedload(Users.roles), joinedload(Users.recovery_codes), joinedload(Users.columns_preferences)).all()
                if not as_dict:
                    return users

                users_data = []
                for user in users:
                    user_data = {
                        "username": user.username,
                        "email": user.email,
                        "password": user.password.encode("utf-8"),
                        "method": user.method,
                        "admin": user.admin,
                        "theme": user.theme,
                        "totp_secret": user.totp_secret,
                        "creation_date": user.creation_date.astimezone(),
                        "update_date": user.update_date.astimezone(),
                        "roles": [role.role_name for role in user.roles],
                        "recovery_codes": [recovery_code.code for recovery_code in user.recovery_codes],
                    }

                    users_data.append(user_data)

                return users_data
            except BaseException as e:
                return str(e)

    def get_ui_user_sessions(self, username: str, current_session_id: Optional[str] = None) -> List[dict]:
        """Get ui user sessions."""
        with self._db_session() as session:
            sessions = []
            if current_session_id:
                current_session = session.query(UserSessions).filter_by(user_name=username, id=current_session_id).all()
                other_sessions = (
                    session.query(UserSessions)
                    .filter_by(user_name=username)
                    .filter(UserSessions.id != current_session_id)
                    .order_by(UserSessions.creation_date.desc())
                    .all()
                )
                query = current_session + other_sessions
            else:
                query = session.query(UserSessions).filter_by(user_name=username).order_by(UserSessions.creation_date.desc())

            for session_data in query:
                sessions.append(
                    {
                        "id": session_data.id,
                        "ip": session_data.ip,
                        "user_agent": self._empty_if_none(session_data.user_agent),
                        "creation_date": session_data.creation_date,
                        "last_activity": session_data.last_activity,
                    }
                )

            return sessions
