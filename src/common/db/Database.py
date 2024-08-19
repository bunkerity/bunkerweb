#!/usr/bin/env python3

from contextlib import contextmanager, suppress
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
from json import JSONDecodeError, loads
from logging import Logger
from os import _exit, getenv, sep
from os.path import join as os_join
from pathlib import Path
from re import compile as re_compile, escape, error as RegexError, search
from sys import argv, path as sys_path
from tarfile import open as tar_open
from threading import Lock
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, Union
from time import sleep
from uuid import uuid4

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
    Bw_cli_commands,
    Templates,
    Template_steps,
    Template_settings,
    Template_custom_configs,
    Metadata,
)

for deps_path in [os_join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import bytes_hash  # type: ignore

from pymysql import install_as_MySQLdb
from sqlalchemy import create_engine, event, MetaData as sql_metadata, func, join, select as db_select, text, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import (
    ArgumentError,
    DatabaseError,
    IntegrityError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.orm import scoped_session, sessionmaker
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


class Database:
    DB_STRING_RX = re_compile(r"^(?P<database>(mariadb|mysql)(\+pymysql)?|sqlite(\+pysqlite)?|postgresql(\+psycopg)?):/+(?P<path>/[^\s]+)")
    READONLY_ERROR = ("readonly", "read-only", "command denied", "Access denied")
    RESTRICTED_TEMPLATE_SETTINGS = ("USE_TEMPLATE", "IS_DRAFT")
    MULTISITE_CUSTOM_CONFIG_TYPES = ("server-http", "modsec-crs", "modsec", "server-stream", "crs-plugins-before", "crs-plugins-after")

    def __init__(
        self, logger: Logger, sqlalchemy_string: Optional[str] = None, *, ui: bool = False, pool: Optional[bool] = None, log: bool = True, **kwargs
    ) -> None:
        """Initialize the database"""
        self.logger = logger
        self.readonly = False
        self.last_connection_retry = None

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

        match = self.DB_STRING_RX.search(sqlalchemy_string)
        if not match:
            self.logger.error(f"Invalid database string provided: {sqlalchemy_string}, exiting...")
            _exit(1)

        if match.group("database").startswith("sqlite"):
            db_path = Path(match.group("path"))
            if ui:
                while not db_path.is_file():
                    if log:
                        self.logger.warning(f"Waiting for the database file to be created: {db_path}")
                    sleep(1)
            else:
                db_path.parent.mkdir(parents=True, exist_ok=True)
        elif match.group("database").startswith("m") and not match.group("database").endswith("+pymysql"):
            sqlalchemy_string = sqlalchemy_string.replace(
                match.group("database"), f"{match.group('database')}+pymysql"
            )  # ? This is strongly recommended as pymysql is the new way to connect to mariadb and mysql
        elif match.group("database").startswith("postgresql") and not match.group("database").endswith("+psycopg"):
            sqlalchemy_string = sqlalchemy_string.replace(
                match.group("database"), f"{match.group('database')}+psycopg"
            )  # ? This is strongly recommended as psycopg is the new way to connect to postgresql

        self.database_uri = sqlalchemy_string
        self.database_uri_readonly = sqlalchemy_string_readonly
        error = False

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

        current_time = datetime.now(timezone.utc)
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
                if (datetime.now(timezone.utc) - current_time).total_seconds() > DATABASE_RETRY_TIMEOUT:
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

        self.suffix_rx = re_compile(r"_\d+$")
        if log:
            self.logger.info(f"✅ Database connection established{'' if not self.readonly else ' in read-only mode'}")

    def __del__(self) -> None:
        """Close the database"""
        if self._session_factory:
            self._session_factory.close_all()

        if self.sql_engine:
            self.sql_engine.dispose()

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
        self.last_connection_retry = datetime.now(timezone.utc)

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
                with self.sql_engine.connect() as conn:
                    session_factory = sessionmaker(bind=conn, autoflush=True, expire_on_commit=False)
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
        self, setting: str, *, value: Optional[str] = None, multisite: bool = False, session: Optional[scoped_session] = None
    ) -> Tuple[bool, str]:
        """Check if the setting exists in the database, if it's valid and if the value is valid"""

        def check_setting(session: scoped_session, setting: str, value: Optional[str], multisite: bool = False) -> Tuple[bool, str]:
            try:
                multiple = False
                if self.suffix_rx.search(setting):
                    setting = setting.rsplit("_", 1)[0]
                    multiple = True

                db_setting = session.query(Settings).filter_by(id=setting).first()

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
                        if search(db_setting.regex, value) is None:
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

    def get_metadata(self) -> Dict[str, Any]:
        """Get the metadata from the database"""
        data = {
            "is_initialized": False,
            "is_pro": "no",
            "pro_license": "",
            "pro_expire": None,
            "pro_status": "invalid",
            "pro_services": 0,
            "pro_overlapped": False,
            "last_pro_check": None,
            "failover": False,
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
            "integration": "unknown",
            "version": "1.6.0-beta",
            "ui_version": "1.6.0-beta",
            "database_version": "Unknown",  # ? Extracted from the database
            "default": True,  # ? Extra field to know if the returned data is the default one
        }
        with self._db_session() as session:
            try:
                database = self.database_uri.split(":")[0].split("+")[0]
                data["database_version"] = (
                    session.execute(text("SELECT sqlite_version()" if database == "sqlite" else "SELECT VERSION()")).first() or ["unknown"]
                )[0]
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
            except BaseException as e:
                if "doesn't exist" not in str(e):
                    self.logger.debug(f"Can't get the metadata: {e}")

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
        changes = changes or ["config", "custom_configs", "external_plugins", "pro_plugins", "instances"]
        plugins_changes = plugins_changes or set()
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.query(Metadata).get(1)

                if not metadata:
                    return "The metadata are not set yet, try again"

                current_time = datetime.now(timezone.utc)

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

    def init_tables(self, default_plugins: List[dict], bunkerweb_version: str) -> Tuple[bool, str]:
        """Initialize the database tables and return the result"""

        if self.readonly:
            return False, "The database is read-only, the changes will not be saved"

        assert self.sql_engine is not None, "The database engine is not initialized"

        inspector = inspect(self.sql_engine)
        db_version = None
        db_ui_version = bunkerweb_version
        has_all_tables = True
        old_data = {}

        # ? Check if the tables exist
        if inspector and len(inspector.get_table_names()):
            metadata = self.get_metadata()
            db_version = metadata["version"]
            db_ui_version = metadata["ui_version"]
            if metadata["default"]:
                db_version = "error"

            # ? Check if the version is different from the database one
            if db_version != bunkerweb_version:
                if db_ui_version != bunkerweb_version:
                    db_ui_version = db_version

                self.logger.warning(f"Database version ({db_version}) is different from Bunkerweb version ({bunkerweb_version}), migrating ...")
                current_time = datetime.now(timezone.utc)
                error = True
                # ? Wait for the metadata to be available
                while error:
                    try:
                        metadata = sql_metadata()
                        metadata.reflect(self.sql_engine)
                        error = False
                    except BaseException as e:
                        if (datetime.now(timezone.utc) - current_time).total_seconds() > 10:
                            raise e
                        sleep(1)

                assert isinstance(metadata, sql_metadata)

                # ? Check if tables are missing
                for table_name in Base.metadata.tables.keys():
                    if not inspector.has_table(table_name):
                        self.logger.warning(f'Table "{table_name}" is missing, creating it')
                        has_all_tables = False
                        continue

                    with self._db_session() as session:
                        old_data[table_name] = session.query(metadata.tables[table_name]).all()

                # ? Rename the old tables to keep the data in case of rollback
                db_version_id = db_version.replace(".", "_")
                for table_name in metadata.tables.keys():
                    if table_name in Base.metadata.tables:
                        with self._db_session() as session:
                            if inspector.has_table(f"{table_name}_{db_version_id}"):
                                self.logger.warning(f'Table "{table_name}" already exists, dropping it to make room for the new one')
                                session.execute(text(f"DROP TABLE {table_name}_{db_version_id}"))
                            session.execute(text(f"ALTER TABLE {table_name} RENAME TO {table_name}_{db_version_id}"))
                            session.commit()

                Base.metadata.drop_all(self.sql_engine)

        if has_all_tables and db_version and db_version == bunkerweb_version:
            return False, ""

        try:
            Base.metadata.create_all(self.sql_engine, checkfirst=True)
        except BaseException as e:
            return False, str(e)

        to_put = []
        with self._db_session() as session:
            saved_settings = set()
            found_plugins = set()

            for plugins in default_plugins:
                if not isinstance(plugins, list):
                    plugins = [plugins]

                for plugin in plugins:
                    settings = {}
                    jobs = []
                    commands = {}
                    if "id" not in plugin:
                        settings = plugin
                        plugin = {
                            "id": "general",
                            "name": "General",
                            "description": "The general settings for the server",
                            "version": "0.1",
                            "stream": "partial",
                        }
                    else:
                        settings = plugin.pop("settings", {})
                        jobs = plugin.pop("jobs", [])
                        plugin.pop("page", False)
                        commands = plugin.pop("bwcli", {})
                        if not isinstance(commands, dict):
                            commands = {}

                    # ? Check if the plugin already exists and if it has changed
                    for i, db_plugin in enumerate(old_data.get("bw_plugins", [])):
                        if db_plugin.id == plugin["id"]:
                            found_plugins.add(plugin["id"])
                            if any(getattr(db_plugin, key, None) != plugin.get(key) for key in ("name", "description", "version", "stream", "type", "method")):
                                self.logger.warning(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}" already exists, updating it with the new values'
                                )
                            del old_data["bw_plugins"][i]
                            break

                    if old_data and plugin["id"] not in found_plugins:
                        self.logger.warning(f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}" does not exist, creating it')

                    to_put.append(
                        Plugins(
                            id=plugin["id"],
                            name=plugin["name"],
                            description=plugin["description"],
                            version=plugin["version"],
                            stream=plugin["stream"],
                            type=plugin.get("type", "core"),
                            method=plugin.get("method"),
                            data=plugin.get("data"),
                            checksum=plugin.get("checksum"),
                        )
                    )

                    ### * SETTINGS

                    # ? Add the settings and selects
                    order = 0
                    for setting, value in settings.items():
                        value.update({"plugin_id": plugin["id"], "name": value["id"], "id": setting})
                        select_values = value.pop("select", [])

                        # ? Check if the setting already exists and if it has changed
                        setting_found = False
                        if plugin["id"] in found_plugins:
                            for i, old_setting in enumerate(old_data.get("bw_settings", [])):
                                if old_setting.plugin_id == plugin["id"] and (old_setting.id == setting or old_setting.name == value["name"]):
                                    setting_found = True
                                    if any(getattr(old_setting, key, None) != data for key, data in value.items()):
                                        self.logger.warning(
                                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Setting "{setting}" already exists, updating it with the new values'
                                        )
                                    del old_data["bw_settings"][i]
                                    break

                            if not setting_found:
                                self.logger.warning(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Setting "{setting}" does not exist, creating it'
                                )

                        to_put.append(Settings(**value | {"order": order}))

                        for select in select_values:
                            if plugin["id"] in found_plugins and setting_found:
                                # ? Check if the select already exists and if it has changed
                                select_found = False
                                for i, db_setting_select in enumerate(old_data.get("bw_selects", [])):
                                    if db_setting_select.setting_id == value["id"] and db_setting_select.value == select:
                                        select_found = True
                                        del old_data["bw_selects"][i]
                                        break

                                if not select_found:
                                    self.logger.warning(
                                        f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Setting "{setting}"\'s Select "{select}" does not exist, creating it'
                                    )

                            to_put.append(Selects(setting_id=value["id"], value=select))

                        # ? Clear out the old selects
                        for i, old_select in enumerate(old_data.get("bw_selects", [])):
                            if old_select.setting_id == value["id"]:
                                self.logger.warning(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Setting "{setting}"\'s Select "{old_select.value}" has been removed, deleting it'
                                )
                                del old_data["bw_selects"][i]

                        order += 1
                        saved_settings.add(setting)

                    # ? Clear out the old settings and related data
                    for i, old_setting in enumerate(old_data.get("bw_settings", [])):
                        if old_setting.plugin_id == plugin["id"]:
                            self.logger.warning(
                                f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Setting "{old_setting.id}" has been removed, deleting it'
                            )

                            for j, old_select in enumerate(old_data.get("bw_selects", [])):
                                if old_select.setting_id == old_setting.id:
                                    del old_data["bw_selects"][j]

                            for j, old_global_value in enumerate(old_data.get("bw_global_values", [])):
                                if old_global_value.setting_id == old_setting.id:
                                    del old_data["bw_global_values"][j]

                            for j, old_service_setting in enumerate(old_data.get("bw_services_settings", [])):
                                if old_service_setting.setting_id == old_setting.id:
                                    del old_data["bw_services_settings"][j]

                            del old_data["bw_settings"][i]

                    ### * JOBS

                    # ? Add the jobs
                    for job in jobs:
                        job["file_name"] = job.pop("file")
                        job["reload"] = job.get("reload", False)

                        # ? Check if the job already exists and if it has changed
                        if plugin["id"] in found_plugins:
                            job_found = False
                            for i, old_job in enumerate(old_data.get("bw_jobs", [])):
                                if old_job.plugin_id == plugin["id"] and old_job.name == job["name"]:
                                    job_found = True
                                    if any(getattr(old_job, key, None) != data for key, data in job.items()):
                                        self.logger.warning(
                                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Job "{job["name"]}" already exists, updating it with the new values'
                                        )
                                    del old_data["bw_jobs"][i]
                                    break

                            if not job_found:
                                self.logger.warning(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Job "{job["name"]}" does not exist, creating it'
                                )

                        to_put.append(Jobs(plugin_id=plugin["id"], **job))

                    # ? Clear out the old jobs and related data
                    for i, old_job in enumerate(old_data.get("bw_jobs", [])):
                        if old_job.plugin_id == plugin["id"]:
                            self.logger.warning(
                                f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Job "{old_job.name}" has been removed, deleting it'
                            )

                            for j, old_cache in enumerate(old_data.get("bw_jobs_cache", [])):
                                if old_cache.job_id == old_job.id:
                                    del old_data["bw_jobs_cache"][j]

                            for j, old_run in enumerate(old_data.get("bw_jobs_runs", [])):
                                if old_run.job_id == old_job.id:
                                    del old_data["bw_jobs_runs"][j]

                            del old_data["bw_jobs"][i]

                    ### * PAGES

                    plugin_path = (
                        Path(sep, "usr", "share", "bunkerweb", "core", plugin["id"])
                        if plugin.get("type", "core") == "core"
                        else (
                            Path(sep, "etc", "bunkerweb", "plugins", plugin["id"])
                            if plugin.get("type", "core") == "external"
                            else Path(sep, "etc", "bunkerweb", "pro", "plugins", plugin["id"])
                        )
                    )
                    path_ui = plugin_path.joinpath("ui")

                    # ? Add the plugin pages
                    if path_ui.is_dir():
                        with BytesIO() as plugin_page_content:
                            with tar_open(fileobj=plugin_page_content, mode="w:gz", compresslevel=9) as tar:
                                tar.add(path_ui, arcname=path_ui.name, recursive=True)
                            plugin_page_content.seek(0)
                            checksum = bytes_hash(plugin_page_content, algorithm="sha256")

                            if plugin["id"] in found_plugins:
                                # ? Check if the page already exists and if it has changed
                                page_found = False
                                for i, plugin_page in enumerate(old_data.get("bw_plugin_pages", [])):
                                    if plugin_page.plugin_id == plugin["id"]:
                                        page_found = True
                                        if getattr(plugin_page, "checksum", None) != checksum or getattr(plugin_page, "template_file", None):
                                            self.logger.warning(
                                                f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Page already exists, updating it with the new values'
                                            )
                                        del old_data["bw_plugin_pages"][i]
                                        break

                                if not page_found:
                                    self.logger.warning(f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Page does not exist, creating it')

                            to_put.append(
                                Plugin_pages(
                                    plugin_id=plugin["id"],
                                    data=plugin_page_content.getvalue(),
                                    checksum=checksum,
                                )
                            )

                    # ? Clear out the old pages
                    for i, old_plugin_page in enumerate(old_data.get("bw_plugin_pages", [])):
                        if old_plugin_page.plugin_id == plugin["id"]:
                            self.logger.warning(f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Page has been removed, deleting it')
                            del old_data["bw_plugin_pages"][i]

                    ### * CLI COMMANDS

                    # ? Add the plugin commands
                    for command, file_name in commands.items():
                        if plugin["id"] in found_plugins:
                            # ? Check if the command already exists and if it has changed
                            command_found = False
                            for i, old_command in enumerate(old_data.get("bw_cli_commands", [])):
                                if old_command.plugin_id == plugin["id"] and old_command.name == command:
                                    command_found = True
                                    if old_command.file_name != file_name:
                                        self.logger.warning(
                                            f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Command "{command}" already exists, updating it with the new file name'
                                        )
                                    del old_data["bw_cli_commands"][i]
                                    break

                            if not command_found:
                                self.logger.warning(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Command "{command}" does not exist, creating it'
                                )

                        to_put.append(Bw_cli_commands(name=command, plugin_id=plugin["id"], file_name=file_name))

                    # ? Clear out the old commands
                    for i, old_command in enumerate(old_data.get("bw_cli_commands", [])):
                        if old_command.plugin_id == plugin["id"]:
                            self.logger.warning(
                                f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Command "{old_command.name}" has been removed, deleting it'
                            )
                            del old_data["bw_cli_commands"][i]

            # ? Add potential external/pro settings to saved_settings
            for i, old_plugin in enumerate(old_data.get("bw_plugins", [])):
                if getattr(old_plugin, "external", False) or getattr(old_plugin, "type", "core") != "core":
                    for j, old_setting in enumerate(old_data.get("bw_settings", [])):
                        if old_setting.plugin_id == old_plugin.id:
                            saved_settings.add(old_setting.id)

            for plugins in default_plugins:
                if not isinstance(plugins, list):
                    plugins = [plugins]

                for plugin in plugins:

                    ### * TEMPLATES

                    plugin_path = (
                        Path(sep, "usr", "share", "bunkerweb", "core", plugin.get("id", "general"))
                        if plugin.get("type", "core") == "core"
                        else (
                            Path(sep, "etc", "bunkerweb", "plugins", plugin.get("id", "general"))
                            if plugin.get("type", "core") == "external"
                            else Path(sep, "etc", "bunkerweb", "pro", "plugins", plugin.get("id", "general"))
                        )
                    )
                    templates_path = plugin_path.joinpath("templates")

                    if not templates_path.is_dir():
                        continue

                    # ? Add the templates
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

                        if plugin["id"] in found_plugins:
                            # ? Check if the template already exists and if it has changed
                            template_found = False
                            for i, old_template in enumerate(old_data.get("bw_templates", [])):
                                if old_template.plugin_id == plugin.get("id", "general") and old_template.id == template_id:
                                    template_found = True
                                    del old_data["bw_templates"][i]
                                    break

                            if not template_found:
                                self.logger.warning(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}" does not exist, creating it'
                                )

                        to_put.append(Templates(id=template_id, plugin_id=plugin.get("id", "general"), name=template_data.get("name", template_id)))

                        ### * TEMPLATES STEPS

                        # ? Add template steps
                        steps_settings = {}
                        steps_configs = {}
                        for step_id, step in enumerate(template_data.get("steps", []), start=1):
                            if plugin["id"] in found_plugins and template_found:
                                # ? Check if the step already exists and if it has changed
                                step_found = False
                                for i, old_step in enumerate(old_data.get("bw_template_steps", [])):
                                    if old_step.template_id == template_id and old_step.id == step_id:
                                        step_found = True
                                        if old_step.title != step["title"] or old_step.subtitle != step["subtitle"]:
                                            self.logger.warning(
                                                f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Step "{step["name"]}" already exists, updating it with the new values'
                                            )
                                        del old_data["bw_template_steps"][i]
                                        break

                                if not step_found:
                                    self.logger.warning(
                                        f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Step "{step["name"]}" does not exist, creating it'
                                    )

                            to_put.append(Template_steps(id=step_id, template_id=template_id, title=step["title"], subtitle=step["subtitle"]))

                            # ? Add step settings and configs for later
                            for setting in step.get("settings", []):
                                if step_id not in steps_settings:
                                    steps_settings[step_id] = []
                                steps_settings[step_id].append(setting)

                            for config in step.get("configs", []):
                                if step_id not in steps_configs:
                                    steps_configs[step_id] = []
                                steps_configs[step_id].append(config)

                        # ? Clear out the old steps and related data
                        for i, old_step in enumerate(old_data.get("bw_template_steps", [])):
                            if old_step.template_id == template_id:
                                self.logger.warning(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Step "{old_step.id}" has been removed, deleting it'
                                )

                                for j, old_setting in enumerate(old_data.get("bw_template_settings", [])):
                                    if old_setting.step_id == old_step.id:
                                        old_data["bw_template_settings"][j]["step_id"] = None

                                for j, old_config in enumerate(old_data.get("bw_template_configs", [])):
                                    if old_config.step_id == old_step.id:
                                        old_data["bw_template_configs"][j]["step_id"] = None

                                del old_data["bw_template_steps"][i]

                        ### * TEMPLATES SETTINGS

                        # ? Add template settings
                        for setting, default in template_data.get("settings", {}).items():
                            setting_id, suffix = setting.rsplit("_", 1) if self.suffix_rx.search(setting) else (setting, None)

                            # ? Check if the setting is restricted
                            if setting_id in self.RESTRICTED_TEMPLATE_SETTINGS:
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template {template_id} has a restricted setting: {setting}, skipping it'
                                )
                                continue
                            # ? Check if the setting exists
                            elif setting_id not in saved_settings:
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template {template_id} has an invalid setting: {setting}, skipping it'
                                )
                                continue

                            if plugin["id"] in found_plugins and template_found:
                                # ? Check if the template setting already exists and if it has changed
                                setting_found = False
                                for i, old_setting in enumerate(old_data.get("bw_template_settings", [])):
                                    if old_setting.template_id == template_id and old_setting.id == setting_id and old_setting.suffix == suffix:
                                        setting_found = True
                                        if old_setting.default != default:
                                            self.logger.warning(
                                                f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" already exists, updating it with the new default value'
                                            )
                                        del old_data["bw_template_settings"][i]
                                        break

                                if not setting_found:
                                    self.logger.warning(
                                        f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{setting}" does not exist, creating it'
                                    )

                            # ? Check if the setting is part of a step
                            step_id = None
                            for step, settings in steps_settings.items():
                                if setting in settings:
                                    step_id = step
                                    break

                            if step_id:
                                to_put.append(
                                    Template_settings(
                                        template_id=template_id,
                                        setting_id=setting_id,
                                        step_id=step_id,
                                        default=default,
                                        suffix=suffix,
                                    )
                                )
                                continue

                            to_put.append(
                                Template_settings(
                                    template_id=template_id,
                                    setting_id=setting_id,
                                    default=default,
                                    suffix=suffix,
                                )
                            )

                        # ? Clear out the old template settings
                        for i, old_setting in enumerate(old_data.get("bw_template_settings", [])):
                            if old_setting.template_id == template_id:
                                self.logger.warning(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Setting "{old_setting.id}" has been removed, deleting it'
                                )
                                del old_data["bw_template_settings"][i]

                        ### * TEMPLATES CUSTOM CONFIGS

                        # ? Add template custom configs
                        for config in template_data.get("configs", []):
                            try:
                                config_type, config_name = config.split("/", 1)
                            except ValueError:
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template {template_id} has an invalid config: {config}'
                                )
                                continue

                            # ? Check if the template custom config type is valid
                            if config_type not in self.MULTISITE_CUSTOM_CONFIG_TYPES:
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template {template_id} has an invalid config type: {config_type}'
                                )
                                continue
                            # ? Check if the template custom config exists
                            elif not templates_path.joinpath(template_id, "configs", config_type, config_name).is_file():
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template {template_id} has a missing config: {config}'
                                )
                                continue

                            content = templates_path.joinpath(template_id, "configs", config_type, config_name).read_bytes()
                            checksum = bytes_hash(content, algorithm="sha256")

                            config_name = config_name.replace(".conf", "")

                            if plugin["id"] in found_plugins and template_found:
                                # ? Check if the custom config already exists and if it has changed
                                config_found = False
                                for i, old_config in enumerate(old_data.get("bw_template_configs", [])):
                                    if old_config.template_id == template_id and old_config.name == config_name and old_config.type == config_type:
                                        config_found = True
                                        if old_config.checksum != checksum:
                                            self.logger.warning(
                                                f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" already exists, updating it with the new values'
                                            )
                                        del old_data["bw_template_configs"][i]
                                        break

                                if not config_found:
                                    self.logger.warning(
                                        f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" does not exist, creating it'
                                    )

                            # ? Check if the custom config is part of a step
                            step_id = None
                            for step, configs in steps_configs.items():
                                if config in configs:
                                    step_id = step
                                    break

                            if step_id:
                                to_put.append(
                                    Template_custom_configs(
                                        template_id=template_id,
                                        step_id=step_id,
                                        type=config_type,
                                        name=config_name,
                                        data=content,
                                        checksum=checksum,
                                    )
                                )
                                continue

                            to_put.append(
                                Template_custom_configs(
                                    template_id=template_id,
                                    type=config_type,
                                    name=config_name,
                                    data=content,
                                    checksum=checksum,
                                )
                            )

                        # ? Clear out the old template custom configs
                        for i, old_config in enumerate(old_data.get("bw_template_configs", [])):
                            if old_config.template_id == template_id:
                                self.logger.warning(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{old_config.name}" has been removed, deleting it'
                                )
                                del old_data["bw_template_configs"][i]

                    # ? Clear out the old templates and related data
                    for i, old_template in enumerate(old_data.get("bw_templates", [])):
                        if old_template.plugin_id == plugin.get("id", "general"):
                            self.logger.warning(
                                f'{plugin.get("type", "core").title()} Plugin "{plugin.get("id", "general")}"\'s Template "{old_template.id}" has been removed, deleting it'
                            )

                            for j, old_step in enumerate(old_data.get("bw_template_steps", [])):
                                if old_step.template_id == old_template.id:
                                    del old_data["bw_template_steps"][j]

                            for j, old_setting in enumerate(old_data.get("bw_template_settings", [])):
                                if old_setting.template_id == old_template.id:
                                    del old_data["bw_template_settings"][j]

                            for j, old_config in enumerate(old_data.get("bw_template_configs", [])):
                                if old_config.template_id == old_template.id:
                                    del old_data["bw_template_configs"][j]

                            del old_data["bw_templates"][i]

            # ? Clear out the old plugins and related data
            for i, old_plugin in enumerate(old_data.get("bw_plugins", [])):
                if not getattr(old_plugin, "external", False) and getattr(old_plugin, "type", "core") == "core":
                    self.logger.warning(f'Core plugin "{old_plugin.id}" has been removed, deleting it')

                    for j, old_setting in enumerate(old_data.get("bw_settings", [])):
                        if old_setting.plugin_id == old_plugin.id:
                            for k, old_select in enumerate(old_data.get("bw_selects", [])):
                                if old_select.setting_id == old_setting.id:
                                    del old_data["bw_selects"][k]

                            for k, old_global_value in enumerate(old_data.get("bw_global_values", [])):
                                if old_global_value.setting_id == old_setting.id:
                                    del old_data["bw_global_values"][k]

                            for k, old_service_setting in enumerate(old_data.get("bw_services_settings", [])):
                                if old_service_setting.setting_id == old_setting.id:
                                    del old_data["bw_services_settings"][k]

                            del old_data["bw_settings"][j]

                    for j, old_job in enumerate(old_data.get("bw_jobs", [])):
                        if old_job.plugin_id == old_plugin.id:
                            for k, old_cache in enumerate(old_data.get("bw_jobs_cache", [])):
                                if old_cache.job_id == old_job.id:
                                    del old_data["bw_jobs_cache"][k]

                            for k, old_run in enumerate(old_data.get("bw_jobs_runs", [])):
                                if old_run.job_id == old_job.id:
                                    del old_data["bw_jobs_runs"][k]

                            del old_data["bw_jobs"][j]

                    for j, old_page in enumerate(old_data.get("bw_plugin_pages", [])):
                        if old_page.plugin_id == old_plugin.id:
                            del old_data["bw_plugin_pages"][j]

                    for j, old_command in enumerate(old_data.get("bw_cli_commands", [])):
                        if old_command.plugin_id == old_plugin.id:
                            del old_data["bw_cli_commands"][j]

                    for j, old_template in enumerate(old_data.get("bw_templates", [])):
                        if old_template.plugin_id == old_plugin.id:
                            for k, old_step in enumerate(old_data.get("bw_template_steps", [])):
                                if old_step.template_id == old_template.id:
                                    del old_data["bw_template_steps"][k]

                            for k, old_setting in enumerate(old_data.get("bw_template_settings", [])):
                                if old_setting.template_id == old_template.id:
                                    del old_data["bw_template_settings"][k]

                            for k, old_config in enumerate(old_data.get("bw_template_configs", [])):
                                if old_config.template_id == old_template.id:
                                    del old_data["bw_template_configs"][k]

                            del old_data["bw_templates"][j]

                    del old_data["bw_plugins"][i]

            self.logger.debug(f"Remaining data: {old_data}")

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException as e:
                return False, str(e)

        if db_version and db_version != bunkerweb_version:
            for table_name, data in old_data.items():
                if not data:
                    continue

                self.logger.warning(f'Restoring data for table "{table_name}"')
                self.logger.debug(f"Data: {data}")
                for row in data:
                    external_column = getattr(row, "external", None)
                    row = {column: getattr(row, column) for column in Base.metadata.tables[table_name].columns.keys() if hasattr(row, column)}

                    # ? As the external column has been replaced by the type column, we need to update the data if the column exists
                    if table_name == "bw_plugins" and external_column is not None:
                        row["type"] = "external" if external_column else "core"

                    with self._db_session() as session:
                        try:
                            if table_name == "bw_metadata":
                                session.add(Metadata(**(row | {"ui_version": db_ui_version})))
                                session.commit()
                                continue

                            # Check if the row already exists in the table
                            existing_row = session.query(Base.metadata.tables[table_name]).filter_by(**row).first()
                            if not existing_row:
                                session.execute(Base.metadata.tables[table_name].insert().values(row))
                                session.commit()
                        except IntegrityError as e:
                            session.rollback()
                            if "Duplicate entry" not in str(e):
                                self.logger.error(f"Error when trying to restore data for table {table_name}: {e}")
                                continue
                            self.logger.debug(e)

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

        return True, ""

    def save_config(self, config: Dict[str, Any], method: str, changed: Optional[bool] = True) -> Union[str, Set[str]]:
        """Save the config in the database"""
        to_put = []

        db_config = {}
        if method == "autoconf":
            db_config = self.get_non_default_settings(with_drafts=True)

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            self.logger.debug(f"Saving config for method {method}")
            changed_plugins = set()
            changed_services = False

            self.logger.debug(f"Cleaning up {method} old global settings")
            for db_global_config in session.query(Global_values).filter_by(method=method).all():
                key = db_global_config.setting_id
                if db_global_config.suffix:
                    key = f"{key}_{db_global_config.suffix}"

                if key not in config and (db_global_config.suffix or f"{key}_0" not in config):
                    session.delete(db_global_config)
                    changed_plugins.add(session.query(Settings).with_entities(Settings.plugin_id).filter_by(id=db_global_config.setting_id).first().plugin_id)

                    if key == "SERVER_NAME":
                        changed_services = True

            self.logger.debug(f"Cleaning up {method} old services settings")
            for db_service_config in session.query(Services_settings).filter_by(method=method).all():
                key = f"{db_service_config.service_id}_{db_service_config.setting_id}"
                if db_service_config.suffix:
                    key = f"{key}_{db_service_config.suffix}"

                if key not in config and (db_service_config.suffix or f"{key}_0" not in config):
                    session.delete(db_service_config)
                    changed_plugins.add(session.query(Settings).with_entities(Settings.plugin_id).filter_by(id=db_service_config.setting_id).first().plugin_id)

            if config:
                config.pop("DATABASE_URI", None)

                self.logger.debug("Checking if the services have changed")
                db_services = session.query(Services).with_entities(Services.id, Services.method, Services.is_draft).all()
                db_ids: Dict[str, dict] = {service.id: {"method": service.method, "is_draft": service.is_draft} for service in db_services}
                missing_ids = []
                services = config.get("SERVER_NAME", [])

                if isinstance(services, str):
                    services = services.strip().split(" ")

                for i, service in enumerate(services):
                    if not service:
                        services.pop(i)

                if db_services:
                    missing_ids = [service.id for service in db_services if service.method == method and service.id not in services]

                    if missing_ids:
                        self.logger.debug(f"Removing {len(missing_ids)} services that are no longer in the list")
                        # Remove services that are no longer in the list
                        session.query(Services).filter(Services.id.in_(missing_ids)).delete()
                        session.query(Services_settings).filter(Services_settings.service_id.in_(missing_ids)).delete()
                        session.query(Custom_configs).filter(Custom_configs.service_id.in_(missing_ids)).delete()
                        session.query(Jobs_cache).filter(Jobs_cache.service_id.in_(missing_ids)).delete()
                        session.query(Metadata).filter_by(id=1).update(
                            {Metadata.custom_configs_changed: True, Metadata.last_custom_configs_change: datetime.now(timezone.utc)}
                        )
                        changed_services = True

                self.logger.debug("Checking if the drafts have changed")
                drafts = {service for service in services if config.pop(f"{service}_IS_DRAFT", "no") == "yes"}
                db_drafts = {service.id for service in db_services if service.is_draft}

                if db_drafts:
                    missing_drafts = [
                        service.id for service in db_services if service.method == method and service.id not in drafts and service.id not in missing_ids
                    ]

                    if missing_drafts:
                        self.logger.debug(f"Removing {len(missing_drafts)} drafts that are no longer in the list")
                        # Remove drafts that are no longer in the list
                        session.query(Services).filter(Services.id.in_(missing_drafts)).update({Services.is_draft: False})
                        changed_services = True

                for draft in drafts:
                    if draft not in db_drafts:
                        if draft not in db_ids:
                            self.logger.debug(f"Adding draft {draft}")
                            to_put.append(Services(id=draft, method=method, is_draft=True))
                            db_ids[draft] = {"method": method, "is_draft": True}
                        elif method == db_ids[draft]["method"]:
                            self.logger.debug(f"Updating draft {draft}")
                            session.query(Services).filter(Services.id == draft).update({Services.is_draft: True})
                            changed_services = True

                template = config.get("USE_TEMPLATE", "")

                if config.get("MULTISITE", "no") == "yes":
                    self.logger.debug("Checking if the multisite settings have changed")

                    service_templates = {}
                    for service in services:
                        service_templates[service] = config.get(f"{service}_USE_TEMPLATE", template)

                    global_values = []
                    for key, value in config.copy().items():
                        suffix = 0
                        original_key = deepcopy(key)
                        if self.suffix_rx.search(key):
                            suffix = int(key.split("_")[-1])
                            key = key[: -len(str(suffix)) - 1]

                        setting = session.query(Settings).with_entities(Settings.default, Settings.plugin_id).filter_by(id=key).first()

                        if not setting and services:
                            try:
                                server_name = next(service for service in services if key.startswith(f"{service}_"))
                            except StopIteration:
                                continue

                            if server_name not in db_ids:
                                self.logger.debug(f"Adding service {server_name}")
                                to_put.append(Services(id=server_name, method=method, is_draft=server_name in drafts))
                                db_ids[server_name] = {"method": method, "is_draft": server_name in drafts}
                                if server_name not in drafts:
                                    changed_services = True

                            key = key.replace(f"{server_name}_", "")
                            original_key = original_key.replace(f"{server_name}_", "")
                            setting = session.query(Settings).with_entities(Settings.default, Settings.plugin_id).filter_by(id=key).first()

                            if not setting:
                                self.logger.debug(f"Setting {key} does not exist")
                                continue

                            service_setting = (
                                session.query(Services_settings)
                                .with_entities(Services_settings.value, Services_settings.method)
                                .filter_by(service_id=server_name, setting_id=key, suffix=suffix)
                                .first()
                            )

                            template_setting = None
                            if service_templates[server_name]:
                                template_setting = (
                                    session.query(Template_settings)
                                    .with_entities(Template_settings.default)
                                    .filter_by(template_id=service_templates[server_name], setting_id=key, suffix=suffix)
                                    .first()
                                )

                            if not service_setting:
                                if key != "SERVER_NAME" and (
                                    (
                                        original_key not in config
                                        and original_key not in db_config
                                        and (
                                            (service_templates[server_name] and value == template_setting.default)
                                            or (not service_templates[server_name] and value == setting.default)
                                        )
                                    )
                                    or (original_key in config and value == config[original_key])
                                    or (original_key in db_config and value == db_config[original_key])
                                ):
                                    continue

                                self.logger.debug(f"Adding setting {key} for service {server_name}")
                                changed_plugins.add(setting.plugin_id)
                                to_put.append(Services_settings(service_id=server_name, setting_id=key, value=value, suffix=suffix, method=method))
                            elif (
                                method == service_setting.method or (service_setting.method not in ("scheduler", "autoconf") and method == "autoconf")
                            ) and service_setting.value != value:
                                changed_plugins.add(setting.plugin_id)
                                query = session.query(Services_settings).filter(
                                    Services_settings.service_id == server_name,
                                    Services_settings.setting_id == key,
                                    Services_settings.suffix == suffix,
                                )

                                if key != "SERVER_NAME" and (
                                    (
                                        original_key not in config
                                        and original_key not in db_config
                                        and (
                                            (service_templates[server_name] and value == template_setting.default)
                                            or (not service_templates[server_name] and value == setting.default)
                                        )
                                    )
                                    or (original_key in config and value == config[original_key])
                                    or (original_key in db_config and value == db_config[original_key])
                                ):
                                    self.logger.debug(f"Removing setting {key} for service {server_name}")
                                    query.delete()
                                    continue

                                self.logger.debug(f"Updating setting {key} for service {server_name}")
                                query.update({Services_settings.value: value, Services_settings.method: method})
                        elif setting and original_key not in global_values:
                            global_values.append(original_key)
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

                            if not global_value:
                                if (template_setting and value == template_setting.default) or (not template_setting and value == setting.default):
                                    continue

                                self.logger.debug(f"Adding global setting {key}")
                                changed_plugins.add(setting.plugin_id)
                                to_put.append(Global_values(setting_id=key, value=value, suffix=suffix, method=method))
                            elif (
                                method == global_value.method or (global_value.method not in ("scheduler", "autoconf") and method == "autoconf")
                            ) and global_value.value != value:
                                changed_plugins.add(setting.plugin_id)
                                query = session.query(Global_values).filter(Global_values.setting_id == key, Global_values.suffix == suffix)

                                if (template_setting and value == template_setting.default) or (not template_setting and value == setting.default):
                                    self.logger.debug(f"Removing global setting {key}")
                                    query.delete()
                                    continue

                                self.logger.debug(f"Updating global setting {key}")
                                query.update({Global_values.value: value, Global_values.method: method})
                elif method != "autoconf":
                    self.logger.debug("Checking if non multisite settings have changed")

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
                            to_put.append(Services(id=first_server, method=method))
                            changed_services = True

                    for key, value in config.items():
                        suffix = 0
                        if self.suffix_rx.search(key):
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

                        if not global_value:
                            if (template_setting and value == template_setting.default) or (not template_setting and value == setting.default):
                                continue

                            self.logger.debug(f"Adding global setting {key}")
                            changed_plugins.add(setting.plugin_id)
                            to_put.append(Global_values(setting_id=key, value=value, suffix=suffix, method=method))
                        elif (
                            method == global_value.method or (global_value.method not in ("scheduler", "autoconf") and method == "autoconf")
                        ) and global_value.value != value:
                            changed_plugins.add(setting.plugin_id)
                            query = session.query(Global_values).filter(Global_values.setting_id == key, Global_values.suffix == suffix)

                            if (template_setting and value == template_setting.default) or (not template_setting and value == setting.default):
                                self.logger.debug(f"Removing global setting {key}")
                                query.delete()
                                continue

                            self.logger.debug(f"Updating global setting {key}")
                            query.update({Global_values.value: value, Global_values.method: method})

            if changed_services:
                changed_plugins = set(plugin.id for plugin in session.query(Plugins).with_entities(Plugins.id).all())

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        if not metadata.first_config_saved:
                            metadata.first_config_saved = True

                    if changed_plugins:
                        session.query(Plugins).filter(Plugins.id.in_(changed_plugins)).update({Plugins.config_changed: True})

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException as e:
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
                    config = {"data": custom_config["value"], "method": method}

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

                custom_config["type"] = custom_config["type"].replace("-", "_").lower()  # type: ignore
                custom_config["data"] = custom_config["data"].encode("utf-8") if isinstance(custom_config["data"], str) else custom_config["data"]
                custom_config["checksum"] = bytes_hash(custom_config["data"], algorithm="sha256")  # type: ignore

                service_id = custom_config.get("service_id", None) or None
                filters = {
                    "type": custom_config["type"],
                    "name": custom_config["name"],
                }

                if service_id:
                    filters["service_id"] = service_id

                custom_conf = session.query(Custom_configs).with_entities(Custom_configs.checksum, Custom_configs.method).filter_by(**filters).first()

                if not custom_conf:
                    to_put.append(Custom_configs(**custom_config))
                elif custom_config["checksum"] != custom_conf.checksum and (
                    method == custom_conf.method or (custom_conf.method not in ("scheduler", "autoconf") and method == "autoconf")
                ):
                    custom_conf.data = custom_config["data"]
                    custom_conf.checksum = custom_config["checksum"]
                    custom_conf.method = method
            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        metadata.custom_configs_changed = True
                        metadata.last_custom_configs_change = datetime.now(timezone.utc)

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
                db_select(Settings.id.label("setting_id"), Settings.context, Settings.multiple, Global_values.value, Global_values.suffix, Global_values.method)
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
                    "value": global_value.value,
                    "global": True,
                    "method": global_value.method,
                    "template": None,
                }

                if global_value.context == "multisite":
                    multisite.add(setting_id)

            is_multisite = config.get("MULTISITE", {"value": "no"})["value"] == "yes"

            services = session.query(Services).with_entities(Services.id, Services.is_draft)

            if not with_drafts:
                services = services.filter_by(is_draft=False)

            if not global_only and is_multisite:
                servers = ""
                for service in services:
                    for key in multisite:
                        config[f"{service.id}_{key}"] = config[key]
                    config[f"{service.id}_IS_DRAFT"] = {
                        "value": "yes" if service.is_draft else "no",
                        "global": False,
                        "method": "default",
                        "template": None,
                    }
                    servers += f"{service.id} "
                servers = servers.strip()

                # Define the join operation
                j = join(Services, Services_settings, Services.id == Services_settings.service_id)
                j = j.join(Settings, Settings.id == Services_settings.setting_id)

                # Define the select statement
                stmt = (
                    db_select(
                        Services.id.label("service_id"),
                        Settings.id.label("setting_id"),
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
                    value = result.value

                    if result.setting_id == "SERVER_NAME" and not search(r"^" + escape(result.service_id) + r"( |$)", value):
                        split = set(value.split(" "))
                        split.discard(result.service_id)
                        value = result.service_id + " " + " ".join(split)

                    config[f"{result.service_id}_{result.setting_id}" + (f"_{result.suffix}" if result.multiple and result.suffix else "")] = {
                        "value": value,
                        "global": False,
                        "method": result.method,
                        "template": None,
                    }
            else:
                servers = " ".join(service.id for service in services)

            config["SERVER_NAME"] = {
                "value": servers,
                "global": True,
                "method": "scheduler",
                "template": None,
            }

            if not methods:
                for key, value in config.copy().items():
                    config[key] = value["value"]

            return config

    def get_config(
        self,
        global_only: bool = False,
        methods: bool = False,
        with_drafts: bool = False,
        filtered_settings: Optional[Union[List[str], Set[str], Tuple[str]]] = None,
    ) -> Dict[str, Any]:
        """Get the config from the database"""
        filtered_settings = set(filtered_settings or [])

        if filtered_settings and not global_only:
            filtered_settings.update(("SERVER_NAME", "MULTISITE", "USE_TEMPLATE"))

        with self._db_session() as session:
            config = {}
            multisite = set()

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
                config[setting.id] = {"value": setting.default or "", "global": True, "method": "default", "template": None}
                if setting.context == "multisite":
                    multisite.add(setting.id)

        config = self.get_non_default_settings(
            global_only=global_only,
            methods=True,
            with_drafts=with_drafts,
            filtered_settings=filtered_settings,
            original_config=config,
            original_multisite=multisite,
        )

        with self._db_session() as session:
            template_used = config.get("USE_TEMPLATE", {"value": ""})["value"]
            if template_used:
                query = (
                    session.query(Template_settings)
                    .with_entities(Template_settings.setting_id, Template_settings.default, Template_settings.suffix)
                    .filter_by(template_id=template_used)
                )

                if filtered_settings:
                    query = query.filter(Template_settings.setting_id.in_(filtered_settings))

                for template_setting in query:
                    key = template_setting.setting_id + (f"_{template_setting.suffix}" if template_setting.suffix > 0 else "")
                    if key in config and config[key]["method"] != "default":
                        continue

                    config[key] = {
                        "value": template_setting.default,
                        "global": True,
                        "method": "default",
                        "template": template_used,
                    }

            if not global_only and config["MULTISITE"]["value"] == "yes":
                for service_id in config["SERVER_NAME"]["value"].split(" "):
                    service_template_used = config.get(f"{service_id}_USE_TEMPLATE", {"value": template_used})["value"]
                    if service_template_used:
                        query = (
                            session.query(Template_settings)
                            .with_entities(Template_settings.setting_id, Template_settings.default, Template_settings.suffix)
                            .filter_by(template_id=service_template_used)
                        )

                        if filtered_settings:
                            query = query.filter(Template_settings.setting_id.in_(filtered_settings))

                        for setting in query:
                            key = f"{service_id}_{setting.setting_id}" + (f"_{setting.suffix}" if setting.suffix > 0 else "")
                            if key in config and config[key]["method"] != "default":
                                continue

                            config[key] = {
                                "value": setting.default,
                                "global": False,
                                "method": "default",
                                "template": service_template_used,
                            }

        if not methods:
            for key, value in config.copy().items():
                config[key] = value["value"]

        return config

    def get_custom_configs(self) -> List[Dict[str, Any]]:
        """Get the custom configs from the database"""
        db_config = self.get_non_default_settings(filtered_settings={"USE_TEMPLATE"})

        with self._db_session() as session:
            custom_configs = [
                {
                    "service_id": custom_config.service_id,
                    "type": custom_config.type,
                    "name": custom_config.name,
                    "data": custom_config.data,
                    "method": custom_config.method,
                    "template": None,
                }
                for custom_config in (
                    session.query(Custom_configs).with_entities(
                        Custom_configs.service_id,
                        Custom_configs.type,
                        Custom_configs.name,
                        Custom_configs.data,
                        Custom_configs.method,
                    )
                )
            ]

            if not db_config:
                return custom_configs

            for service in session.query(Services).with_entities(Services.id).all():
                for key, value in db_config.items():
                    if key.startswith(f"{service.id}_"):
                        for template_config in (
                            session.query(Template_custom_configs)
                            .with_entities(Template_custom_configs.type, Template_custom_configs.name, Template_custom_configs.data)
                            .filter_by(template_id=value)
                        ):
                            if not any(
                                custom_config["service_id"] == service.id
                                and custom_config["type"] == template_config.type
                                and custom_config["name"] == template_config.name
                                for custom_config in custom_configs
                            ):
                                custom_configs.append(
                                    {
                                        "service_id": service.id,
                                        "type": template_config.type,
                                        "name": template_config.name,
                                        "data": template_config.data,
                                        "method": "default",
                                        "template": value,
                                    }
                                )

            return custom_configs

    def get_services_settings(self, methods: bool = False, with_drafts: bool = False) -> List[Dict[str, Any]]:
        """Get the services' configs from the database"""
        services = []
        config = self.get_config(methods=methods, with_drafts=with_drafts)
        service_names = config["SERVER_NAME"]["value"].split(" ") if methods else config["SERVER_NAME"].split(" ")
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
                        {"value": value["value"], "global": value["global"], "method": value["method"], "template": value["template"]} if methods else value
                    )

            services.append(tmp_config)

        return services

    def add_job_run(self, job_name: str, success: bool, start_date: datetime, end_date: Optional[datetime] = None) -> str:
        """Add a job run."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            session.add(Jobs_runs(job_name=job_name, success=success, start_date=start_date, end_date=end_date or datetime.now(timezone.utc)))

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
                result = (
                    session.query(Jobs_runs).order_by(Jobs_runs.end_date.asc()).limit(rows_count - max_runs).with_for_update().delete(synchronize_session=False)
                )

                try:
                    session.commit()
                except BaseException as e:
                    return str(e)
        return f"Removed {result} excess jobs runs"

    def delete_job_cache(self, file_name: str, *, job_name: Optional[str] = None, service_id: Optional[str] = None) -> str:
        job_name = job_name or argv[0].replace(".py", "")
        filters = {"file_name": file_name}
        if job_name:
            filters["job_name"] = job_name
        if service_id:
            filters["service_id"] = service_id

        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                session.query(Jobs_cache).filter_by(**filters).delete()
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
                        last_update=datetime.now(timezone.utc),
                        checksum=checksum,
                    )
                )
            else:
                cache.data = data
                cache.last_update = datetime.now(timezone.utc)
                cache.checksum = checksum

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def update_external_plugins(
        self, plugins: List[Dict[str, Any]], *, _type: Literal["external", "ui", "pro"] = "external", delete_missing: bool = True
    ) -> str:
        """Update external plugins from the database"""
        to_put = []
        changes = False
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            db_plugins = session.query(Plugins).with_entities(Plugins.id).filter_by(type=_type).all()

            db_ids = []
            if delete_missing and db_plugins:
                db_ids = [plugin.id for plugin in db_plugins]
                ids = [plugin["id"] for plugin in plugins]
                missing_ids = [plugin for plugin in db_ids if plugin not in ids]

                if missing_ids:
                    changes = True
                    # Remove plugins that are no longer in the list
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

            db_settings = [setting.id for setting in session.query(Settings).with_entities(Settings.id)]

            for plugin in plugins:
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
                        Plugins.data,
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

                    if db_plugin.type not in ("external", "pro"):
                        self.logger.warning(
                            f"Plugin \"{plugin['id']}\" is not {_type}, skipping update (updating a non-external or non-pro plugin is forbidden for security reasons)",  # noqa: E501
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

                    if plugin.get("data") != db_plugin.data:
                        updates[Plugins.data] = plugin.get("data")

                    if plugin.get("checksum") != db_plugin.checksum:
                        updates[Plugins.checksum] = plugin.get("checksum")

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
                            for select in value.pop("select", []):
                                to_put.append(Selects(setting_id=value["id"], value=select))

                            to_put.append(Settings(**value | {"order": order}))
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

                            db_values = [select.value for select in session.query(Selects).with_entities(Selects.value).filter_by(setting_id=setting)]
                            select_values = value.get("select", [])
                            missing_values = [select for select in db_values if select not in select_values]

                            if missing_values:
                                changes = True
                                # Remove selects that are no longer in the list
                                session.query(Selects).filter(Selects.value.in_(missing_values)).delete()

                            for select in value.get("select", []):
                                if select not in db_values:
                                    changes = True
                                    to_put.append(Selects(setting_id=setting, value=select))

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
                            .with_entities(Jobs.file_name, Jobs.every, Jobs.reload)
                            .filter_by(name=job["name"], plugin_id=plugin["id"])
                            .first()
                        )

                        if job["name"] not in db_names or not db_job:
                            changes = True
                            job["file_name"] = job.pop("file")
                            job["reload"] = job.get("reload", False)
                            to_put.append(Jobs(plugin_id=plugin["id"], **job))
                        else:
                            updates = {}

                            if job["file"] != db_job.file_name:
                                updates[Jobs.file_name] = job["file"]

                            if job["every"] != db_job.every:
                                updates[Jobs.every] = job["every"]

                            if job.get("reload", None) != db_job.reload:
                                updates[Jobs.reload] = job.get("reload", False)

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
                            to_put.append(Plugin_pages(plugin_id=plugin["id"], data=content, checksum=checksum))
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
                            to_put.append(Bw_cli_commands(name=command, plugin_id=plugin["id"], file_name=file_name))
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

                    if not templates_path.is_dir():
                        if db_names:
                            self.logger.warning(f'Plugin "{plugin["id"]}"\'s templates directory does not exist, removing all templates')
                            for template in db_names:
                                session.query(Templates).filter_by(id=template, plugin_id=plugin["id"]).delete()
                                session.query(Template_steps).filter_by(template_id=template).delete()
                                session.query(Template_settings).filter_by(template_id=template).delete()
                                session.query(Template_custom_configs).filter_by(template_id=template).delete()
                        continue

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
                            to_put.append(Templates(id=template_id, plugin_id=plugin["id"], name=template_data.get("name", template_id)))

                        saved_templates.add(template_id)

                        db_ids = [step.id for step in session.query(Template_steps).with_entities(Template_steps.id).filter_by(template_id=template_id)]
                        missing_ids = [x for x in range(1, len(template.get("steps", [])) + 1) if x not in db_ids]

                        if missing_ids:
                            changes = True
                            session.query(Template_settings).filter(Template_settings.step_id.in_(missing_ids)).update({Template_settings.step_id: None})
                            session.query(Template_custom_configs).filter(Template_custom_configs.step_id.in_(missing_ids)).update(
                                {Template_custom_configs.step_id: None}
                            )
                            session.query(Template_steps).filter(Template_steps.id.in_(missing_ids)).delete()

                        steps_settings = {}
                        steps_configs = {}
                        for step_id, step in enumerate(template.get("steps", []), start=1):
                            db_step = session.query(Template_steps).with_entities(Template_steps.id).filter_by(id=step_id, template_id=template_id).first()
                            if not db_step:
                                changes = True
                                to_put.append(Template_steps(id=step_id, template_id=template_id, title=step["title"], subtitle=step["subtitle"]))
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
                            f"{setting.setting_id}_{setting.suffix}" if setting.suffix else setting.setting_id
                            for setting in session.query(Template_settings).with_entities(Template_settings.id).filter_by(template_id=template_id)
                        ]
                        missing_ids = [setting for setting in template.get("settings", {}) if setting not in db_template_settings]

                        if missing_ids:
                            changes = True
                            session.query(Template_settings).filter(Template_settings.id.in_(missing_ids)).delete()

                        for setting, default in template.get("settings", {}).items():
                            setting_id, suffix = setting.rsplit("_", 1) if self.suffix_rx.search(setting) else (setting, None)

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

                            template_setting = (
                                session.query(Template_settings)
                                .with_entities(Template_settings.id)
                                .filter_by(template_id=template_id, setting_id=setting_id, step_id=step_id, suffix=suffix)
                                .first()
                            )

                            if not template_setting:
                                changes = True
                                if step_id:
                                    to_put.append(
                                        Template_settings(
                                            template_id=template_id,
                                            setting_id=setting_id,
                                            step_id=step_id,
                                            suffix=suffix,
                                            default=default,
                                        )
                                    )
                                    continue

                                to_put.append(
                                    Template_settings(
                                        template_id=template_id,
                                        setting_id=setting_id,
                                        suffix=suffix,
                                        default=default,
                                    )
                                )
                            elif default != template_setting.default:
                                changes = True
                                session.query(Template_settings).filter_by(id=template_setting.id).update({Template_settings.default: default})

                        db_template_configs = [
                            f"{config.type}/{config.name}.conf"
                            for config in session.query(Template_custom_configs)
                            .with_entities(Template_custom_configs.type, Template_custom_configs.name)
                            .filter_by(template_id=template_id)
                        ]
                        missing_ids = [config for config in template.get("configs", {}) if config not in db_template_configs]

                        if missing_ids:
                            changes = True
                            session.query(Template_custom_configs).filter(Template_custom_configs.name.in_(missing_ids)).delete()

                        for config in template.get("configs", []):
                            try:
                                config_type, config_name = config.split("/", 1)
                            except ValueError:
                                self.logger.error(
                                    f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" is invalid, skipping it'
                                )
                                continue

                            if config_type not in self.MULTISITE_CUSTOM_CONFIG_TYPES:
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
                            checksum = bytes_hash(content, algorithm="sha256")

                            config_name = config_name.replace(".conf", "")

                            step_id = None
                            for step, configs in steps_configs.items():
                                if config in configs:
                                    step_id = step
                                    break

                            template_config = (
                                session.query(Template_custom_configs)
                                .with_entities(Template_custom_configs.id)
                                .filter_by(template_id=template_id, step_id=step_id, type=config_type, name=config_name)
                                .first()
                            )

                            if not template_config:
                                changes = True
                                if step_id:
                                    to_put.append(
                                        Template_custom_configs(
                                            template_id=template_id,
                                            step_id=step_id,
                                            type=config_type,
                                            name=config_name,
                                            data=content,
                                            checksum=checksum,
                                        )
                                    )
                                    continue

                                to_put.append(
                                    Template_custom_configs(
                                        template_id=template_id,
                                        type=config_type,
                                        name=config_name,
                                        data=content,
                                        checksum=checksum,
                                    )
                                )
                            elif checksum != template_config.checksum:
                                changes = True
                                session.query(Template_custom_configs).filter_by(id=template_config.id).update(
                                    {Template_custom_configs.data: content, Template_custom_configs.checksum: checksum}
                                )

                    for template in db_names:
                        if template not in saved_templates:
                            changes = True
                            session.query(Template_steps).filter_by(template_id=template).delete()
                            session.query(Template_settings).filter_by(template_id=template).delete()
                            session.query(Template_custom_configs).filter_by(template_id=template).delete()
                            session.query(Templates).filter_by(id=template, plugin_id=plugin["id"]).delete()

                    continue

                changes = True
                to_put.append(
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

                    for select in value.pop("select", []):
                        to_put.append(Selects(setting_id=value["id"], value=select))

                    to_put.append(Settings(**value | {"order": order}))
                    order += 1
                    plugin_settings.add(setting)

                for job in jobs:
                    db_job = (
                        session.query(Jobs).with_entities(Jobs.file_name, Jobs.every, Jobs.reload).filter_by(name=job["name"], plugin_id=plugin["id"]).first()
                    )

                    if db_job is not None:
                        self.logger.warning(f"A job with the name {job['name']} already exists in the database, therefore it will not be added.")
                        continue

                    job["file_name"] = job.pop("file")
                    job["reload"] = job.get("reload", False)
                    to_put.append(Jobs(plugin_id=plugin["id"], **job))

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
                    if not path_ui.is_dir():
                        with BytesIO() as plugin_page_content:
                            with tar_open(fileobj=plugin_page_content, mode="w:gz", compresslevel=9) as tar:
                                tar.add(path_ui, arcname=path_ui.name, recursive=True)
                            plugin_page_content.seek(0)
                            checksum = bytes_hash(plugin_page_content, algorithm="sha256")

                            to_put.append(Plugin_pages(plugin_id=plugin["id"], data=plugin_page_content.getvalue(), checksum=checksum))

                for command, file_name in commands.items():
                    if not plugin_path.joinpath("bwcli", file_name).is_file():
                        self.logger.warning(f'Command "{command}"\'s file "{file_name}" does not exist in the plugin directory, skipping it')
                        continue

                    to_put.append(Bw_cli_commands(name=command, plugin_id=plugin["id"], file_name=file_name))

                templates_path = plugin_path.joinpath("templates")

                if not templates_path.is_dir():
                    continue

                for template_file in plugin_path.joinpath("templates").iterdir():
                    if template_file.is_dir():
                        continue

                    try:
                        template_data = loads(template_file.read_text())
                    except JSONDecodeError:
                        self.logger.error(f'Template file "{template_file}" is not a valid JSON file')
                        continue

                    template_id = template_file.stem

                    to_put.append(Templates(id=template_id, plugin_id=plugin["id"], name=template_data.get("name", template_id)))

                    steps_settings = {}
                    steps_configs = {}
                    for step_id, step in enumerate(template_data.get("steps", []), start=1):
                        to_put.append(Template_steps(id=step_id, template_id=template_id, title=step["title"], subtitle=step["subtitle"]))

                        for setting in step.get("settings", []):
                            if step_id not in steps_settings:
                                steps_settings[step_id] = []
                            steps_settings[step_id].append(setting)

                        for config in step.get("configs", []):
                            if step_id not in steps_configs:
                                steps_configs[step_id] = []
                            steps_configs[step_id].append(config)

                    for setting, default in template_data.get("settings", {}).items():
                        setting_id, suffix = setting.rsplit("_", 1) if self.suffix_rx.search(setting) else (setting, None)

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

                        if step_id:
                            to_put.append(
                                Template_settings(
                                    template_id=template_id,
                                    setting_id=setting_id,
                                    step_id=step_id,
                                    default=default,
                                    suffix=suffix,
                                )
                            )
                            continue

                        to_put.append(
                            Template_settings(
                                template_id=template_id,
                                setting_id=setting_id,
                                default=default,
                                suffix=suffix,
                            )
                        )

                    for config in template_data.get("configs", []):
                        try:
                            config_type, config_name = config.split("/", 1)
                        except ValueError:
                            self.logger.error(
                                f'{plugin.get("type", "core").title()} Plugin "{plugin["id"]}"\'s Template "{template_id}"\'s Custom config "{config}" is invalid, skipping it'
                            )
                            continue

                        if config_type not in self.MULTISITE_CUSTOM_CONFIG_TYPES:
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
                        checksum = bytes_hash(content, algorithm="sha256")

                        config_name = config_name.replace(".conf", "")

                        step_id = None
                        for step, configs in steps_configs.items():
                            if config in configs:
                                step_id = step
                                break

                        if step_id:
                            to_put.append(
                                Template_custom_configs(
                                    template_id=template_id,
                                    step_id=step_id,
                                    type=config_type,
                                    name=config_name,
                                    data=content,
                                    checksum=checksum,
                                )
                            )
                            continue

                        to_put.append(
                            Template_custom_configs(
                                template_id=template_id,
                                type=config_type,
                                name=config_name,
                                data=content,
                                checksum=checksum,
                            )
                        )

            if changes:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        if _type == "external":
                            metadata.external_plugins_changed = True
                            metadata.last_external_plugins_change = datetime.now(timezone.utc)
                        elif _type == "pro":
                            metadata.pro_plugins_changed = True
                            metadata.last_pro_plugins_change = datetime.now(timezone.utc)

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def delete_plugin(self, plugin_id: str, method: str) -> str:
        """Delete a plugin from the database."""
        with self._db_session() as session:
            plugin = session.query(Plugins).filter_by(id=plugin_id, method=method).first()
            if not plugin:
                return f"Plugin with id {plugin_id} and method {method} not found"

            session.query(Plugins).filter_by(id=plugin_id, method=method).delete()
            session.query(Settings).filter_by(plugin_id=plugin_id).delete()
            session.query(Selects).filter(Selects.setting_id.in_(session.query(Settings).filter_by(plugin_id=plugin_id).with_entities(Settings.id))).delete()
            session.query(Jobs).filter_by(plugin_id=plugin_id).delete()
            session.query(Jobs_cache).filter_by(plugin_id=plugin_id).delete()
            session.query(Jobs_runs).filter_by(plugin_id=plugin_id).delete()
            session.query(Plugin_pages).filter_by(plugin_id=plugin_id).delete()
            session.query(Bw_cli_commands).filter_by(plugin_id=plugin_id).delete()
            session.query(Templates).filter_by(plugin_id=plugin_id).delete()
            session.query(Template_steps).filter(
                Template_steps.template_id.in_(session.query(Templates).filter_by(plugin_id=plugin_id).with_entities(Templates.id))
            ).delete()
            session.query(Template_settings).filter(
                Template_settings.template_id.in_(session.query(Templates).filter_by(plugin_id=plugin_id).with_entities(Templates.id))
            ).delete()
            session.query(Template_custom_configs).filter(
                Template_custom_configs.template_id.in_(session.query(Templates).filter_by(plugin_id=plugin_id).with_entities(Templates.id))
            ).delete()

            try:
                session.commit()
            except BaseException as e:
                return str(e)
        return ""

    def get_plugins(self, *, _type: Literal["all", "external", "pro"] = "all", with_data: bool = False) -> List[Dict[str, Any]]:
        """Get all plugins from the database."""
        plugins = []
        with self._db_session() as session:
            entities = [Plugins.id, Plugins.stream, Plugins.name, Plugins.description, Plugins.version, Plugins.type, Plugins.method, Plugins.checksum]
            if with_data:
                entities.append(Plugins.data)  # type: ignore

            db_plugins = session.query(Plugins).with_entities(*entities)
            if _type != "all":
                db_plugins = db_plugins.filter_by(type=_type)

            for plugin in db_plugins:
                page = session.query(Plugin_pages).with_entities(Plugin_pages.id).filter_by(plugin_id=plugin.id).first()
                data = {
                    "id": plugin.id,
                    "stream": plugin.stream,
                    "name": plugin.name,
                    "description": plugin.description,
                    "version": plugin.version,
                    "type": plugin.type,
                    "method": plugin.method,
                    "page": page is not None,
                    "settings": {},
                    "checksum": plugin.checksum,
                } | ({"data": plugin.data} if with_data else {})

                for setting in (
                    session.query(Settings)
                    .with_entities(
                        Settings.id,
                        Settings.context,
                        Settings.default,
                        Settings.help,
                        Settings.name,
                        Settings.label,
                        Settings.regex,
                        Settings.type,
                        Settings.multiple,
                    )
                    .filter_by(plugin_id=plugin.id)
                    .order_by(Settings.order)
                ):
                    data["settings"][setting.id] = {
                        "context": setting.context,
                        "default": setting.default,
                        "help": setting.help,
                        "id": setting.name,
                        "label": setting.label,
                        "regex": setting.regex,
                        "type": setting.type,
                    } | ({"multiple": setting.multiple} if setting.multiple else {})

                    if setting.type == "select":
                        data["settings"][setting.id]["select"] = [
                            select.value for select in session.query(Selects).with_entities(Selects.value).filter_by(setting_id=setting.id)
                        ]

                for command in session.query(Bw_cli_commands).with_entities(Bw_cli_commands.name, Bw_cli_commands.file_name).filter_by(plugin_id=plugin.id):
                    if "bwcli" not in data:
                        data["bwcli"] = {}
                    data["bwcli"][command.name] = command.file_name

                plugins.append(data)

        return plugins

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
                    "history": [
                        {
                            "start_date": job_run.start_date.strftime("%Y/%m/%d, %H:%M:%S %Z"),
                            "end_date": job_run.end_date.strftime("%Y/%m/%d, %H:%M:%S %Z"),
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
                for job in session.query(Jobs).with_entities(Jobs.name, Jobs.plugin_id, Jobs.every, Jobs.reload)
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

        filters = {"job_name": job_name, "file_name": file_name}
        if service_id:
            filters["service_id"] = service_id

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

    def get_jobs_cache_files(self, *, job_name: str = "", plugin_id: str = "") -> List[Dict[str, Any]]:
        """Get jobs cache files."""
        with self._db_session() as session:
            filters = {}
            query = session.query(Jobs_cache).with_entities(Jobs_cache.job_name, Jobs_cache.service_id, Jobs_cache.file_name, Jobs_cache.data)

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
                        "data": cache.data,
                    }
                )
            return cache_files

    def add_instance(self, hostname: str, port: int, server_name: str, method: str, changed: Optional[bool] = True, *, name: Optional[str] = None) -> str:
        """Add instance."""
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            db_instance = session.query(Instances).with_entities(Instances.hostname).filter_by(hostname=hostname).first()

            if db_instance is not None:
                return f"Instance {hostname} already exists, will not be added."

            session.add(Instances(hostname=hostname, name=name or "static instance", port=port, server_name=server_name, method=method))

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        metadata.instances_changed = True
                        metadata.last_instances_change = datetime.now(timezone.utc)

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while adding the instance {hostname} (port: {port}, server name: {server_name}, method: {method}).\n{e}"

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
                        metadata.last_instances_change = datetime.now(timezone.utc)

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

                to_put.append(
                    Instances(
                        hostname=instance["hostname"],
                        name=instance.get("name", "static instance"),
                        port=instance["env"].get("API_HTTP_PORT", 5000),
                        server_name=instance["env"].get("API_SERVER_NAME", "bwapi"),
                        type=instance.get("type", "static"),
                        status="up" if instance.get("health", True) else "down",
                        method=method,
                    )
                )

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        metadata.instances_changed = True
                        metadata.last_instances_change = datetime.now(timezone.utc)

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
            db_instance.last_seen = datetime.now(timezone.utc)

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while updating the instance {hostname}.\n{e}"

        return ""

    def get_instances(self, *, method: Optional[str] = None) -> List[Dict[str, Any]]:
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
                    "server_name": instance.server_name,
                    "type": instance.type,
                    "status": instance.status,
                    "method": instance.method,
                    "creation_date": instance.creation_date,
                    "last_seen": instance.last_seen,
                }
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
            query = session.query(Templates).with_entities(Templates.id, Templates.plugin_id, Templates.name)

            if plugin:
                query = query.filter_by(plugin_id=plugin)

            templates = {}
            for template in query:
                templates[template.id] = {"plugin_id": template.plugin_id, "name": template.name, "settings": {}, "configs": {}, "steps": []}

                steps_settings = {}
                for setting in (
                    session.query(Template_settings)
                    .with_entities(Template_settings.setting_id, Template_settings.step_id, Template_settings.default, Template_settings.suffix)
                    .filter_by(template_id=template.id)
                ):
                    key = f"{setting.setting_id}_{setting.suffix}" if setting.suffix else setting.setting_id
                    templates[template.id]["settings"][key] = setting.default

                    if setting.step_id:
                        if setting.step_id not in steps_settings:
                            steps_settings[setting.step_id] = []
                        steps_settings[setting.step_id].append(key)

                steps_configs = {}
                for config in (
                    session.query(Template_custom_configs)
                    .with_entities(Template_custom_configs.step_id, Template_custom_configs.type, Template_custom_configs.name, Template_custom_configs.data)
                    .filter_by(template_id=template.id)
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
                ):
                    templates[template.id]["steps"].append({"title": step.title, "subtitle": step.subtitle})

                    if step.id in steps_settings:
                        templates[template.id]["steps"][step.id - 1]["settings"] = steps_settings[step.id]
                    if step.id in steps_configs:
                        templates[template.id]["steps"][step.id - 1]["configs"] = steps_configs[step.id]

            return templates

    def get_template_settings(self, template_id: str) -> Dict[str, Any]:
        """Get templates settings."""
        with self._db_session() as session:
            settings = {}
            for setting in (
                session.query(Template_settings)
                .with_entities(Template_settings.setting_id, Template_settings.default, Template_settings.suffix)
                .filter_by(template_id=template_id)
            ):
                settings[f"{setting.setting_id}_{setting.suffix}" if setting.suffix else setting.setting_id] = setting.default
            return settings
