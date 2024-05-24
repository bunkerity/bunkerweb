#!/usr/bin/env python3

from contextlib import contextmanager, suppress
from copy import deepcopy
from datetime import datetime
from io import BytesIO
from logging import Logger
from os import _exit, getenv, listdir, sep
from os.path import join
from pathlib import Path
from re import compile as re_compile
from sys import argv, path as sys_path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from time import sleep
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

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
    Custom_configs,
    Selects,
    Users,
    BwcliCommands,
    Metadata,
)

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import bytes_hash  # type: ignore

from pymysql import install_as_MySQLdb
from sqlalchemy import create_engine, event, MetaData as sql_metadata, text, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import (
    ArgumentError,
    DatabaseError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool
from sqlite3 import Connection as SQLiteConnection

install_as_MySQLdb()


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, _):
    if isinstance(dbapi_connection, SQLiteConnection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


class Database:
    DB_STRING_RX = re_compile(r"^(?P<database>(mariadb|mysql)(\+pymysql)?|sqlite(\+pysqlite)?|postgresql(\+psycopg)?):/+(?P<path>/[^\s]+)")

    def __init__(
        self, logger: Logger, sqlalchemy_string: Optional[str] = None, *, ui: bool = False, pool: Optional[bool] = None, log: bool = True, **kwargs
    ) -> None:
        """Initialize the database"""
        self.logger = logger
        self.readonly = False
        self.last_fallback = None

        if pool:
            self.logger.warning("The pool parameter is deprecated, it will be removed in the next version")

        self.__session_factory = None
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

        current_time = datetime.now()
        not_connected = True

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
                if (datetime.now() - current_time).total_seconds() > DATABASE_RETRY_TIMEOUT:
                    if "readonly" in str(e) or "read-only" in str(e) or "command denied" in str(e):
                        if not self.readonly:
                            self.logger.warning("The database is read-only, trying one last time to connect in read-only mode")
                            self.readonly = True
                            self.last_fallback = datetime.now()
                        elif self.database_uri_readonly and sqlalchemy_string != self.database_uri_readonly:
                            self.logger.warning("Can't connect to the database in read-only mode, falling back to read-only one")
                            sqlalchemy_string = self.database_uri_readonly
                            self.last_fallback = datetime.now()
                        else:
                            self.logger.error(f"Can't connect to database after {DATABASE_RETRY_TIMEOUT} seconds: {e}")
                            _exit(1)
                    else:
                        self.logger.error(f"Can't connect to database after {DATABASE_RETRY_TIMEOUT} seconds: {e}")
                        _exit(1)

                if "readonly" in str(e) or "read-only" in str(e) or "command denied" in str(e):
                    if log:
                        self.logger.warning("The database is read-only, waiting for it to become writable. Retrying in 5 seconds ...")
                    self.sql_engine.dispose(close=True)
                    self.sql_engine = create_engine(sqlalchemy_string, **self._engine_kwargs)
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
        if self.__session_factory:
            self.__session_factory.close_all()

        if self.sql_engine:
            self.sql_engine.dispose()

    def test_write(self):
        """Test the write access to the database"""
        with self.__db_session() as session:
            table_name = uuid4().hex
            session.execute(text(f"CREATE TABLE IF NOT EXISTS test_{table_name} (id INT)"))
            session.execute(text(f"DROP TABLE IF EXISTS test_{table_name}"))
            session.commit()

    def retry_connection(self, *, readonly: bool = False, fallback: bool = False, **kwargs) -> None:
        """Retry the connection to the database"""

        assert self.sql_engine is not None

        if fallback and not self.database_uri_readonly:
            raise ValueError("The fallback parameter is set to True but the read-only database URI is not set")

        self.sql_engine.dispose(close=True)
        self.sql_engine = create_engine(self.database_uri_readonly if fallback else self.database_uri, **self._engine_kwargs | kwargs)

        if fallback or readonly:
            with self.sql_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return

        with self.sql_engine.connect() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS test (id INT)"))
            conn.execute(text("DROP TABLE test"))

    @contextmanager
    def __db_session(self) -> Any:
        try:
            assert self.sql_engine is not None
        except AssertionError:
            self.logger.error("The database engine is not initialized")
            _exit(1)

        if self.database_uri and self.readonly and self.last_fallback and (datetime.now() - self.last_fallback).total_seconds() > 30:
            # ? If the database is forced to be read-only, we try to connect as a non read-only user every time until the database is writable
            try:
                self.retry_connection(pool_timeout=1)
                self.readonly = False
                self.logger.info("The database is no longer read-only, defaulting to read-write mode")
            except (OperationalError, DatabaseError):
                try:
                    self.retry_connection(readonly=True, pool_timeout=1)
                except (OperationalError, DatabaseError):
                    if self.database_uri_readonly:
                        with suppress(OperationalError, DatabaseError):
                            self.retry_connection(fallback=True, pool_timeout=1)
                self.readonly = True

        session = None
        try:
            with self.sql_engine.connect() as conn:
                session_factory = sessionmaker(bind=conn, autoflush=True, expire_on_commit=False)
                session = scoped_session(session_factory)
                yield session
        except BaseException as e:
            if session:
                session.rollback()

            if "readonly" in str(e) or "read-only" in str(e) or "command denied" in str(e):
                self.logger.warning("The database is read-only, retrying in read-only mode ...")
                try:
                    self.retry_connection(readonly=True, pool_timeout=1)
                except (OperationalError, DatabaseError):
                    if self.database_uri_readonly:
                        self.logger.warning("Can't connect to the database in read-only mode, falling back to read-only one")
                        with suppress(OperationalError, DatabaseError):
                            self.retry_connection(fallback=True, pool_timeout=1)
                self.readonly = True
                self.last_fallback = datetime.now()
            elif isinstance(e, (ConnectionRefusedError, OperationalError)) and self.database_uri_readonly:
                self.logger.warning("Can't connect to the database, falling back to read-only one ...")
                with suppress(OperationalError, DatabaseError):
                    self.retry_connection(fallback=True, pool_timeout=1)
                    self.readonly = True
                    self.last_fallback = datetime.now()
            raise
        finally:
            if session:
                session.remove()

    def set_autoconf_load(self, value: bool = True) -> str:
        """Set the autoconf_loaded value"""
        with self.__db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.query(Metadata).get(1)

                if not metadata:
                    return "The metadata are not set yet, try again"

                metadata.autoconf_loaded = value
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def is_autoconf_loaded(self) -> bool:
        """Check if the autoconf is loaded"""
        with self.__db_session() as session:
            try:
                metadata = session.query(Metadata).with_entities(Metadata.autoconf_loaded).filter_by(id=1).first()
                return metadata is not None and metadata.autoconf_loaded
            except (ProgrammingError, OperationalError):
                return False

    def set_scheduler_first_start(self, value: bool = False) -> str:
        """Set the scheduler_first_start value"""
        with self.__db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.query(Metadata).get(1)

                if not metadata:
                    return "The metadata are not set yet, try again"

                metadata.scheduler_first_start = value
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def set_pro_metadata(self, data: Dict[Literal["is_pro", "pro_expire", "pro_status", "pro_overlapped", "pro_services"], Any] = {}) -> str:
        """Set the pro metadata values"""
        with self.__db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.query(Metadata).get(1)

                if not metadata:
                    return "The metadata are not set yet, try again"

                for key, value in data.items():
                    setattr(metadata, key, value)
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def is_scheduler_first_start(self) -> bool:
        """Check if it's the scheduler's first start"""
        with self.__db_session() as session:
            try:
                metadata = session.query(Metadata).with_entities(Metadata.scheduler_first_start).filter_by(id=1).first()
                return metadata is not None and metadata.scheduler_first_start
            except (ProgrammingError, OperationalError):
                return True

    def is_first_config_saved(self) -> bool:
        """Check if the first configuration has been saved"""
        with self.__db_session() as session:
            try:
                metadata = session.query(Metadata).with_entities(Metadata.first_config_saved).filter_by(id=1).first()
                return metadata is not None and metadata.first_config_saved
            except (ProgrammingError, OperationalError):
                return False

    def is_initialized(self) -> bool:
        """Check if the database is initialized"""
        with self.__db_session() as session:
            try:
                metadata = session.query(Metadata).with_entities(Metadata.is_initialized).filter_by(id=1).first()
                return metadata is not None and metadata.is_initialized
            except (ProgrammingError, OperationalError, DatabaseError):
                return False

    def initialize_db(self, version: str, integration: str = "Unknown") -> str:
        """Initialize the database"""
        with self.__db_session() as session:
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

    def get_metadata(self) -> Dict[str, str]:
        """Get the metadata from the database"""
        data = {
            "version": "1.5.7",
            "integration": "unknown",
            "database_version": "Unknown",
            "is_pro": "no",
            "pro_expire": None,
            "pro_services": 0,
            "pro_overlapped": False,
            "pro_status": "invalid",
            "last_pro_check": None,
            "default": True,
        }
        with self.__db_session() as session:
            try:
                database = self.database_uri.split(":")[0].split("+")[0]
                data["database_version"] = (
                    session.execute(text("SELECT sqlite_version()" if database == "sqlite" else "SELECT VERSION()")).first() or ["unknown"]
                )[0]
                metadata = (
                    session.query(Metadata)
                    .with_entities(
                        Metadata.version,
                        Metadata.integration,
                        Metadata.is_pro,
                        Metadata.pro_expire,
                        Metadata.pro_services,
                        Metadata.pro_overlapped,
                        Metadata.pro_status,
                        Metadata.last_pro_check,
                    )
                    .filter_by(id=1)
                    .first()
                )
                if metadata:
                    data.update(
                        {
                            "version": metadata.version,
                            "integration": metadata.integration,
                            "is_pro": metadata.is_pro,
                            "pro_expire": metadata.pro_expire,
                            "pro_services": metadata.pro_services,
                            "pro_overlapped": metadata.pro_overlapped,
                            "pro_status": metadata.pro_status,
                            "last_pro_check": metadata.last_pro_check,
                            "default": False,
                        }
                    )
            except BaseException as e:
                self.logger.debug(f"Can't get the metadata: {e}")

        return data

    def check_changes(self) -> Union[Dict[str, bool], bool, str]:
        """Check if either the config, the custom configs, plugins or instances have changed inside the database"""
        with self.__db_session() as session:
            try:
                metadata = (
                    session.query(Metadata)
                    .with_entities(
                        Metadata.custom_configs_changed,
                        Metadata.external_plugins_changed,
                        Metadata.pro_plugins_changed,
                        Metadata.config_changed,
                        Metadata.instances_changed,
                    )
                    .filter_by(id=1)
                    .first()
                )

                return dict(
                    custom_configs_changed=metadata is not None and metadata.custom_configs_changed,
                    external_plugins_changed=metadata is not None and metadata.external_plugins_changed,
                    pro_plugins_changed=metadata is not None and metadata.pro_plugins_changed,
                    config_changed=metadata is not None and metadata.config_changed,
                    instances_changed=metadata is not None and metadata.instances_changed,
                )
            except BaseException as e:
                return str(e)

    def checked_changes(self, changes: Optional[List[str]] = None, value: Optional[bool] = False) -> str:
        """Set changed bit for config, custom configs, instances and plugins"""
        changes = changes or [
            "config",
            "custom_configs",
            "external_plugins",
            "pro_plugins",
            "instances",
        ]
        with self.__db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            try:
                metadata = session.query(Metadata).get(1)

                if not metadata:
                    return "The metadata are not set yet, try again"

                if "config" in changes:
                    if not metadata.first_config_saved:
                        metadata.first_config_saved = True
                    metadata.config_changed = value
                if "custom_configs" in changes:
                    metadata.custom_configs_changed = value
                if "external_plugins" in changes:
                    metadata.external_plugins_changed = value
                if "pro_plugins" in changes:
                    metadata.pro_plugins_changed = value
                if "instances" in changes:
                    metadata.instances_changed = value
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
        has_all_tables = True
        old_data = {}

        if inspector and len(inspector.get_table_names()):
            metadata = self.get_metadata()
            db_version = metadata["version"]
            if metadata["default"]:
                db_version = "error"

            if db_version != bunkerweb_version:
                self.logger.warning(f"Database version ({db_version}) is different from Bunkerweb version ({bunkerweb_version}), migrating ...")
                metadata = sql_metadata()
                metadata.reflect(self.sql_engine)

                for table_name in Base.metadata.tables.keys():
                    if not inspector.has_table(table_name):
                        self.logger.warning(f'Table "{table_name}" is missing')
                        has_all_tables = False
                        continue

                    with self.__db_session() as session:
                        old_data[table_name] = session.query(metadata.tables[table_name]).all()

                # Rename the old tables
                db_version_id = db_version.replace(".", "_")
                for table_name in metadata.tables.keys():
                    if table_name in Base.metadata.tables:
                        with self.__db_session() as session:
                            if inspector.has_table(f"{table_name}_{db_version_id}"):
                                self.logger.warning(f'Table "{table_name}" already exists, dropping it to make room for the new one')
                                session.execute(text(f"DROP TABLE {table_name}_{db_version_id}"))
                            session.execute(text(f"ALTER TABLE {table_name} RENAME TO {table_name}_{db_version_id}"))

                Base.metadata.drop_all(self.sql_engine)

        if has_all_tables and db_version and db_version == bunkerweb_version:
            return False, ""

        try:
            Base.metadata.create_all(self.sql_engine, checkfirst=True)
        except BaseException as e:
            return False, str(e)

        if db_version and db_version != bunkerweb_version:
            with self.__db_session() as session:
                for table_name, data in old_data.items():
                    for row in data:
                        has_external_column = "external" in row
                        row = {
                            column: getattr(row, column)
                            for column in Base.metadata.tables[table_name].columns.keys() + (["external"] if has_external_column else [])
                            if hasattr(row, column)
                        }

                        # ? As the external column has been replaced by the type column, we need to update the data if the column exists
                        if table_name == "bw_plugins" and "external" in row:
                            row["type"] = "external" if row.pop("external") else "core"

                        session.execute(Base.metadata.tables[table_name].insert().values(row))
                session.commit()

        to_put = []
        with self.__db_session() as session:
            db_plugins = session.query(Plugins).with_entities(Plugins.id).all()

            db_ids = []
            if db_plugins:
                db_ids = [plugin.id for plugin in db_plugins]
                ids = [plugin["id"] for plugin in default_plugins if "id" in plugin]
                ids.append("general")
                missing_ids = [plugin for plugin in db_ids if plugin not in ids]

                if missing_ids:
                    # Remove plugins that are no longer in the list
                    session.query(Plugins).filter(Plugins.id.in_(missing_ids)).delete()
                    session.query(Plugin_pages).filter(Plugin_pages.plugin_id.in_(missing_ids)).delete()
                    session.query(BwcliCommands).filter(BwcliCommands.plugin_id.in_(missing_ids)).delete()

                    for plugin_job in session.query(Jobs).with_entities(Jobs.name).filter(Jobs.plugin_id.in_(missing_ids)):
                        session.query(Jobs_cache).filter(Jobs_cache.job_name == plugin_job.name).delete()
                        session.query(Jobs).filter(Jobs.name == plugin_job.name).delete()

                    for plugin_setting in session.query(Settings).with_entities(Settings.id).filter(Settings.plugin_id.in_(missing_ids)):
                        session.query(Selects).filter(Selects.setting_id == plugin_setting.id).delete()
                        session.query(Services_settings).filter(Services_settings.setting_id == plugin_setting.id).delete()
                        session.query(Global_values).filter(Global_values.setting_id == plugin_setting.id).delete()
                        session.query(Settings).filter(Settings.id == plugin_setting.id).delete()

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

                    db_plugin = session.query(Plugins).filter_by(id=plugin["id"]).first()
                    if db_plugin:
                        updates = {}

                        if plugin["name"] != db_plugin.name:
                            updates[Plugins.name] = plugin["name"]

                        if plugin["description"] != db_plugin.description:
                            updates[Plugins.description] = plugin["description"]

                        if plugin["version"] != db_plugin.version:
                            updates[Plugins.version] = plugin["version"]

                        if plugin["stream"] != db_plugin.stream:
                            updates[Plugins.stream] = plugin["stream"]

                        if plugin.get("type", "core") != db_plugin.type:
                            updates[Plugins.type] = plugin.get("type", "core")

                        if plugin.get("method", "manual") != db_plugin.method:
                            updates[Plugins.method] = plugin.get("method", "manual")

                        if plugin.get("data") != db_plugin.data:
                            updates[Plugins.data] = plugin.get("data")

                        if plugin.get("checksum") != db_plugin.checksum:
                            updates[Plugins.checksum] = plugin.get("checksum")

                        if updates:
                            self.logger.warning(f'Plugin "{plugin["id"]}" already exists, updating it with the new values')
                            session.query(Plugins).filter(Plugins.id == plugin["id"]).update(updates)
                    else:
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

                    order = 0
                    for setting, value in settings.items():
                        value.update(
                            {
                                "plugin_id": plugin["id"],
                                "name": value["id"],
                                "id": setting,
                            }
                        )
                        db_setting = session.query(Settings).filter_by(id=setting).first()
                        select_values = value.pop("select", [])

                        if db_setting:
                            updates = {}

                            if value["plugin_id"] != db_setting.plugin_id:
                                updates[Settings.plugin_id] = value["plugin_id"]

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
                                self.logger.warning(f'Setting "{setting}" already exists, updating it with the new values')
                                session.query(Settings).filter(Settings.id == setting).update(updates)
                        else:
                            if db_plugin:
                                self.logger.warning(f'Setting "{setting}" does not exist, creating it')
                            to_put.append(Settings(**value | {"order": order}))

                        db_values = [select.value for select in session.query(Selects).with_entities(Selects.value).filter_by(setting_id=value["id"])]
                        missing_values = [select for select in db_values if select not in select_values]

                        if select_values:
                            if missing_values:
                                # Remove selects that are no longer in the list
                                self.logger.warning(f'Removing {len(missing_values)} selects from setting "{setting}" as they are no longer in the list')
                                session.query(Selects).filter(Selects.value.in_(missing_values)).delete()

                            for select in select_values:
                                if select not in db_values:
                                    to_put.append(Selects(setting_id=value["id"], value=select))
                        else:
                            if missing_values:
                                self.logger.warning(f'Removing all selects from setting "{setting}" as there are no longer any in the list')
                            session.query(Selects).filter_by(setting_id=value["id"]).delete()

                        order += 1

                    db_names = [job.name for job in session.query(Jobs).with_entities(Jobs.name).filter_by(plugin_id=plugin["id"])]
                    job_names = [job["name"] for job in jobs]
                    missing_names = [job for job in db_names if job not in job_names]

                    if missing_names:
                        # Remove jobs that are no longer in the list
                        self.logger.warning(f'Removing {len(missing_names)} jobs from plugin "{plugin["id"]}" as they are no longer in the list')
                        session.query(Jobs).filter(Jobs.name.in_(missing_names), Jobs.plugin_id == plugin["id"]).delete()
                        session.query(Jobs_cache).filter(Jobs_cache.job_name.in_(missing_names)).delete()

                    for job in jobs:
                        db_job = (
                            session.query(Jobs)
                            .with_entities(Jobs.file_name, Jobs.every, Jobs.reload)
                            .filter_by(name=job["name"], plugin_id=plugin["id"])
                            .first()
                        )

                        if job["name"] not in db_names or not db_job:
                            job["file_name"] = job.pop("file")
                            job["reload"] = job.get("reload", False)
                            if db_plugin:
                                self.logger.warning(f'Job "{job["name"]}" does not exist, creating it')
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
                                self.logger.warning(f'Job "{job["name"]}" already exists, updating it with the new values')
                                updates[Jobs.last_run] = None
                                session.query(Jobs_cache).filter(Jobs_cache.job_name == job["name"]).delete()
                                session.query(Jobs).filter(Jobs.name == job["name"]).update(updates)

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

                    db_plugin_page = (
                        session.query(Plugin_pages)
                        .with_entities(
                            Plugin_pages.template_checksum,
                            Plugin_pages.actions_checksum,
                            Plugin_pages.obfuscation_checksum,
                        )
                        .filter_by(plugin_id=plugin["id"])
                        .first()
                    )
                    remove = not path_ui.is_dir() and db_plugin_page

                    if path_ui.is_dir():
                        remove = True
                        if {"template.html", "actions.py"}.issubset(listdir(str(path_ui))):
                            template = path_ui.joinpath("template.html").read_bytes()
                            actions = path_ui.joinpath("actions.py").read_bytes()
                            template_checksum = bytes_hash(template, algorithm="sha256")
                            actions_checksum = bytes_hash(actions, algorithm="sha256")

                            obfuscation_file = None
                            obfuscation_checksum = None
                            obfuscation_dir = path_ui.joinpath("pyarmor_runtime_000000")
                            if obfuscation_dir.is_dir():
                                obfuscation_file = BytesIO()
                                with ZipFile(obfuscation_file, "w", ZIP_DEFLATED) as zip_file:
                                    for path in obfuscation_dir.rglob("*"):
                                        if path.is_file():
                                            zip_file.write(path, path.relative_to(path_ui))
                                obfuscation_file.seek(0, 0)
                                obfuscation_file = obfuscation_file.getvalue()
                                obfuscation_checksum = bytes_hash(obfuscation_file, algorithm="sha256")

                            if db_plugin_page:
                                updates = {}
                                if template_checksum != db_plugin_page.template_checksum:
                                    updates.update(
                                        {
                                            Plugin_pages.template_file: template,
                                            Plugin_pages.template_checksum: template_checksum,
                                        }
                                    )

                                if actions_checksum != db_plugin_page.actions_checksum:
                                    updates.update(
                                        {
                                            Plugin_pages.actions_file: actions,
                                            Plugin_pages.actions_checksum: actions_checksum,
                                        }
                                    )

                                if obfuscation_checksum != db_plugin_page.obfuscation_checksum:
                                    updates.update(
                                        {
                                            Plugin_pages.obfuscation_file: obfuscation_file,
                                            Plugin_pages.obfuscation_checksum: obfuscation_checksum,
                                        }
                                    )

                                if updates:
                                    self.logger.warning(f'Page for plugin "{plugin["id"]}" already exists, updating it with the new values')
                                    session.query(Plugin_pages).filter(Plugin_pages.plugin_id == plugin["id"]).update(updates)
                                remove = False
                            else:
                                if db_plugin:
                                    self.logger.warning(f'Page for plugin "{plugin["id"]}" does not exist, creating it')

                                to_put.append(
                                    Plugin_pages(
                                        plugin_id=plugin["id"],
                                        template_file=template,
                                        template_checksum=template_checksum,
                                        actions_file=actions,
                                        actions_checksum=actions_checksum,
                                        obfuscation_file=obfuscation_file,
                                        obfuscation_checksum=obfuscation_checksum,
                                    )
                                )
                                remove = False

                    if db_plugin_page and remove:
                        self.logger.warning(f'Removing page for plugin "{plugin["id"]}" as it no longer exists')
                        session.query(Plugin_pages).filter_by(plugin_id=plugin["id"]).delete()

                    db_names = [command.name for command in session.query(BwcliCommands).with_entities(BwcliCommands.name).filter_by(plugin_id=plugin["id"])]
                    missing_names = [command for command in db_names if command not in commands]

                    if missing_names:
                        # Remove commands that are no longer in the list
                        self.logger.warning(f'Removing {len(missing_names)} commands from plugin "{plugin["id"]}" as they are no longer in the list')
                        session.query(BwcliCommands).filter(BwcliCommands.name.in_(missing_names), BwcliCommands.plugin_id == plugin["id"]).delete()

                    for command, file_name in commands.items():
                        db_command = session.query(BwcliCommands).with_entities(BwcliCommands.file_name).filter_by(name=command, plugin_id=plugin["id"]).first()
                        command_path = plugin_path.joinpath("bwcli", file_name)

                        if command not in db_names or not db_command:
                            if db_plugin:
                                self.logger.warning(f'Command "{command}" does not exist, creating it')

                            if not command_path.is_file():
                                self.logger.warning(f'Command "{command}"\'s file "{file_name}" does not exist in the plugin directory, skipping it')
                                continue

                            to_put.append(BwcliCommands(name=command, plugin_id=plugin["id"], file_name=file_name))
                        else:
                            updates = {}

                            if file_name != db_command.file_name:
                                updates[BwcliCommands.file_name] = file_name

                            if updates:
                                self.logger.warning(f'Command "{command}" already exists, updating it with the new values')
                                if not command_path.is_file():
                                    self.logger.warning(f'Command "{command}"\'s file "{file_name}" does not exist in the plugin directory, removing it')
                                    session.query(BwcliCommands).filter_by(name=command, plugin_id=plugin["id"]).delete()
                                    continue
                                session.query(BwcliCommands).filter_by(name=command, plugin_id=plugin["id"]).update(updates)

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException as e:
                return False, str(e)

        return True, ""

    def save_config(self, config: Dict[str, Any], method: str, changed: Optional[bool] = True) -> str:
        """Save the config in the database"""
        to_put = []
        with self.__db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            # Delete all the old config
            session.query(Global_values).filter(Global_values.method == method).delete()
            session.query(Services_settings).filter(Services_settings.method == method).delete()

            if config:
                config.pop("DATABASE_URI", None)
                db_services = session.query(Services).with_entities(Services.id, Services.method, Services.is_draft).all()
                db_ids: Dict[str, dict] = {service.id: {"method": service.method, "is_draft": service.is_draft} for service in db_services}
                missing_ids = []
                services = config.get("SERVER_NAME", [])

                if isinstance(services, str):
                    services = services.split(" ")

                if db_services:
                    missing_ids = [service.id for service in db_services if service.method == method and service.id not in services]

                    if missing_ids:
                        # Remove services that are no longer in the list
                        session.query(Services).filter(Services.id.in_(missing_ids)).delete()
                        session.query(Services_settings).filter(Services_settings.service_id.in_(missing_ids)).delete()
                        session.query(Custom_configs).filter(Custom_configs.service_id.in_(missing_ids)).delete()
                        session.query(Jobs_cache).filter(Jobs_cache.service_id.in_(missing_ids)).delete()

                drafts = {service for service in services if config.pop(f"{service}_IS_DRAFT", "no") == "yes"}
                db_drafts = {service.id for service in db_services if service.is_draft}

                if db_drafts:
                    missing_drafts = [
                        service.id for service in db_services if service.method == method and service.id not in drafts and service.id not in missing_ids
                    ]

                    if missing_drafts:
                        # Remove drafts that are no longer in the list
                        session.query(Services).filter(Services.id.in_(missing_drafts)).update({Services.is_draft: False})

                for draft in drafts:
                    if draft not in db_drafts:
                        if draft not in db_ids:
                            to_put.append(Services(id=draft, method=method, is_draft=True))
                            db_ids[draft] = {"method": method, "is_draft": True}
                        elif method == db_ids[draft]["method"]:
                            session.query(Services).filter(Services.id == draft).update({Services.is_draft: True})

                if config.get("MULTISITE", "no") == "yes":
                    global_values = []
                    for key, value in config.copy().items():
                        suffix = 0
                        original_key = deepcopy(key)
                        if self.suffix_rx.search(key):
                            suffix = int(key.split("_")[-1])
                            key = key[: -len(str(suffix)) - 1]

                        setting = session.query(Settings).with_entities(Settings.default).filter_by(id=key).first()

                        if not setting and services:
                            try:
                                server_name = next(service for service in services if key.startswith(f"{service}_"))
                            except StopIteration:
                                continue

                            if server_name not in db_ids:
                                to_put.append(Services(id=server_name, method=method, is_draft=server_name in drafts))
                                db_ids[server_name] = {"method": method, "is_draft": server_name in drafts}

                            key = key.replace(f"{server_name}_", "")
                            original_key = original_key.replace(f"{server_name}_", "")
                            setting = session.query(Settings).with_entities(Settings.default).filter_by(id=key).first()

                            if not setting:
                                continue

                            service_setting = (
                                session.query(Services_settings)
                                .with_entities(Services_settings.value, Services_settings.method)
                                .filter_by(
                                    service_id=server_name,
                                    setting_id=key,
                                    suffix=suffix,
                                )
                                .first()
                            )

                            if not service_setting:
                                if key != "SERVER_NAME" and (
                                    (original_key not in config and value == setting.default) or (original_key in config and value == config[original_key])
                                ):
                                    continue

                                to_put.append(
                                    Services_settings(
                                        service_id=server_name,
                                        setting_id=key,
                                        value=value,
                                        suffix=suffix,
                                        method=method,
                                    )
                                )
                            elif method in (service_setting.method, "autoconf") and service_setting.value != value:
                                if key != "SERVER_NAME" and (
                                    (original_key not in config and value == setting.default) or (original_key in config and value == config[original_key])
                                ):
                                    session.query(Services_settings).filter(
                                        Services_settings.service_id == server_name,
                                        Services_settings.setting_id == key,
                                        Services_settings.suffix == suffix,
                                    ).delete()
                                    continue

                                session.query(Services_settings).filter(
                                    Services_settings.service_id == server_name,
                                    Services_settings.setting_id == key,
                                    Services_settings.suffix == suffix,
                                ).update(
                                    {
                                        Services_settings.value: value,
                                        Services_settings.method: method,
                                    }
                                )
                        elif setting and original_key not in global_values:
                            global_values.append(original_key)
                            global_value = (
                                session.query(Global_values)
                                .with_entities(Global_values.value, Global_values.method)
                                .filter_by(
                                    setting_id=key,
                                    suffix=suffix,
                                )
                                .first()
                            )

                            if not global_value:
                                if value == setting.default:
                                    continue

                                to_put.append(
                                    Global_values(
                                        setting_id=key,
                                        value=value,
                                        suffix=suffix,
                                        method=method,
                                    )
                                )
                            elif method in (global_value.method, "autoconf") and global_value.value != value:
                                if value == setting.default:
                                    session.query(Global_values).filter(
                                        Global_values.setting_id == key,
                                        Global_values.suffix == suffix,
                                    ).delete()
                                    continue

                                session.query(Global_values).filter(
                                    Global_values.setting_id == key,
                                    Global_values.suffix == suffix,
                                ).update(
                                    {
                                        Global_values.value: value,
                                        Global_values.method: method,
                                    }
                                )
                else:
                    if (
                        config.get("SERVER_NAME", "www.example.com")
                        and not session.query(Services)
                        .with_entities(Services.id)
                        .filter_by(id=config.get("SERVER_NAME", "www.example.com").split(" ")[0])
                        .first()
                    ):
                        to_put.append(Services(id=config.get("SERVER_NAME", "www.example.com").split(" ")[0], method=method))

                    for key, value in config.items():
                        suffix = 0
                        if self.suffix_rx.search(key):
                            suffix = int(key.split("_")[-1])
                            key = key[: -len(str(suffix)) - 1]

                        setting = session.query(Settings).with_entities(Settings.default).filter_by(id=key).first()

                        if not setting:
                            continue

                        global_value = (
                            session.query(Global_values)
                            .with_entities(Global_values.value, Global_values.method)
                            .filter_by(setting_id=key, suffix=suffix)
                            .first()
                        )

                        if not global_value:
                            if value == setting.default:
                                continue

                            to_put.append(
                                Global_values(
                                    setting_id=key,
                                    value=value,
                                    suffix=suffix,
                                    method=method,
                                )
                            )
                        elif global_value.method == method and value != global_value.value:
                            if value == setting.default:
                                session.query(Global_values).filter(
                                    Global_values.setting_id == key,
                                    Global_values.suffix == suffix,
                                ).delete()
                                continue

                            session.query(Global_values).filter(
                                Global_values.setting_id == key,
                                Global_values.suffix == suffix,
                            ).update({Global_values.value: value})

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        if not metadata.first_config_saved:
                            metadata.first_config_saved = True
                        metadata.config_changed = True

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

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
        with self.__db_session() as session:
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
                elif custom_config["checksum"] != custom_conf.checksum and method in (custom_conf.method, "autoconf"):
                    custom_conf.data = custom_config["data"]
                    custom_conf.checksum = custom_config["checksum"]

                    if method == "autoconf":
                        custom_conf.method = method
            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        metadata.custom_configs_changed = True

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException as e:
                return f"{f'{message}{endl}' if message else ''}{e}"

        return message

    def get_config(self, methods: bool = False, with_drafts: bool = False) -> Dict[str, Any]:
        """Get the config from the database"""
        with self.__db_session() as session:
            config = {}
            multisite = []
            for setting in (
                session.query(Settings)
                .with_entities(
                    Settings.id,
                    Settings.context,
                    Settings.default,
                    Settings.multiple,
                )
                .order_by(Settings.order)
            ):
                default = setting.default or ""
                config[setting.id] = default if not methods else {"value": default, "global": True, "method": "default"}

                for global_value in (
                    session.query(Global_values).with_entities(Global_values.value, Global_values.suffix, Global_values.method).filter_by(setting_id=setting.id)
                ):
                    config[setting.id + (f"_{global_value.suffix}" if setting.multiple and global_value.suffix > 0 else "")] = (
                        global_value.value
                        if not methods
                        else {
                            "value": global_value.value,
                            "global": True,
                            "method": global_value.method,
                        }
                    )

                if setting.context == "multisite":
                    multisite.append(setting.id)

            is_multisite = config.get("MULTISITE", {"value": "no"})["value"] == "yes" if methods else config.get("MULTISITE", "no") == "yes"

            services = session.query(Services).with_entities(Services.id, Services.is_draft)
            if not with_drafts:
                services = services.filter_by(is_draft=False)

            if is_multisite:
                for service in services:
                    config[f"{service.id}_IS_DRAFT"] = "yes" if service.is_draft else "no"
                    if methods:
                        config[f"{service.id}_IS_DRAFT"] = {"value": config[f"{service.id}_IS_DRAFT"], "global": False, "method": "default"}

                    checked_settings = []
                    for key, value in config.copy().items():
                        original_key = key
                        if self.suffix_rx.search(key):
                            key = key[: -len(str(key.split("_")[-1])) - 1]

                        if key not in multisite:
                            continue
                        elif f"{service.id}_{original_key}" not in config:
                            config[f"{service.id}_{original_key}"] = value

                        if original_key not in checked_settings:
                            checked_settings.append(original_key)
                        else:
                            continue

                        for service_setting in (
                            session.query(Services_settings)
                            .with_entities(
                                Services_settings.value,
                                Services_settings.suffix,
                                Services_settings.method,
                            )
                            .filter_by(service_id=service.id, setting_id=key)
                        ):
                            value = service_setting.value
                            if key == "SERVER_NAME" and service.id not in value.split(" "):
                                value = f"{service.id} {value}".strip()

                            config[f"{service.id}_{key}" + (f"_{service_setting.suffix}" if service_setting.suffix > 0 else "")] = (
                                value
                                if not methods
                                else {
                                    "value": value,
                                    "global": False,
                                    "method": service_setting.method,
                                }
                            )

            servers = " ".join(service.id for service in services)
            config["SERVER_NAME"] = servers if not methods else {"value": servers, "global": True, "method": "default"}

            return config

    def get_custom_configs(self) -> List[Dict[str, Any]]:
        """Get the custom configs from the database"""
        with self.__db_session() as session:
            return [
                {
                    "service_id": custom_config.service_id,
                    "type": custom_config.type,
                    "name": custom_config.name,
                    "data": custom_config.data,
                    "method": custom_config.method,
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
                    tmp_config[key] = {"value": value["value"], "global": value["global"], "method": value["method"]} if methods else value

            services.append(tmp_config)

        return services

    def update_job(self, plugin_id: str, job_name: str, success: bool) -> str:
        """Update the job last_run in the database"""
        with self.__db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            job = session.query(Jobs).filter_by(plugin_id=plugin_id, name=job_name).first()

            if not job:
                return "Job not found"

            job.last_run = datetime.now()
            job.success = success

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def delete_job_cache(self, file_name: str, *, job_name: Optional[str] = None, service_id: Optional[str] = None) -> str:
        job_name = job_name or argv[0].replace(".py", "")
        filters = {"file_name": file_name}
        if job_name:
            filters["job_name"] = job_name
        if service_id:
            filters["service_id"] = service_id

        with self.__db_session() as session:
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
        with self.__db_session() as session:
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
                        last_update=datetime.now(),
                        checksum=checksum,
                    )
                )
            else:
                cache.data = data
                cache.last_update = datetime.now()
                cache.checksum = checksum

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def update_external_plugins(self, plugins: List[Dict[str, Any]], *, _type: Literal["external", "pro"] = "external", delete_missing: bool = True) -> str:
        """Update external plugins from the database"""
        to_put = []
        changes = False
        with self.__db_session() as session:
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
                    session.query(BwcliCommands).filter(BwcliCommands.plugin_id.in_(missing_ids)).delete()

                    for plugin_job in session.query(Jobs).with_entities(Jobs.name).filter(Jobs.plugin_id.in_(missing_ids)):
                        session.query(Jobs_cache).filter(Jobs_cache.job_name == plugin_job.name).delete()
                        session.query(Jobs).filter(Jobs.name == plugin_job.name).delete()

                    for plugin_setting in session.query(Settings).with_entities(Settings.id).filter(Settings.plugin_id.in_(missing_ids)):
                        session.query(Selects).filter(Selects.setting_id == plugin_setting.id).delete()
                        session.query(Services_settings).filter(Services_settings.setting_id == plugin_setting.id).delete()
                        session.query(Global_values).filter(Global_values.setting_id == plugin_setting.id).delete()
                        session.query(Settings).filter(Settings.id == plugin_setting.id).delete()

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

                    order = 0
                    for setting, value in settings.items():
                        value.update({"plugin_id": plugin["id"], "name": value["id"], "id": setting})
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

                    db_plugin_page = (
                        session.query(Plugin_pages)
                        .with_entities(
                            Plugin_pages.template_checksum,
                            Plugin_pages.actions_checksum,
                            Plugin_pages.obfuscation_checksum,
                        )
                        .filter_by(plugin_id=plugin["id"])
                        .first()
                    )
                    remove = not path_ui.is_dir() and db_plugin_page

                    if path_ui.is_dir():
                        remove = True
                        if {"template.html", "actions.py"}.issubset(listdir(str(path_ui))):
                            template = path_ui.joinpath("template.html").read_bytes()
                            actions = path_ui.joinpath("actions.py").read_bytes()
                            template_checksum = bytes_hash(template, algorithm="sha256")
                            actions_checksum = bytes_hash(actions, algorithm="sha256")

                            obfuscation_file = None
                            obfuscation_checksum = None
                            obfuscation_dir = path_ui.joinpath("pyarmor_runtime_000000")
                            if obfuscation_dir.is_dir():
                                obfuscation_file = BytesIO()
                                with ZipFile(obfuscation_file, "w", ZIP_DEFLATED) as zip_file:
                                    for path in obfuscation_dir.rglob("*"):
                                        if path.is_file():
                                            zip_file.write(path, path.relative_to(path_ui))
                                obfuscation_file.seek(0, 0)
                                obfuscation_file = obfuscation_file.getvalue()
                                obfuscation_checksum = bytes_hash(obfuscation_file, algorithm="sha256")

                            if not db_plugin_page:
                                changes = True

                                to_put.append(
                                    Plugin_pages(
                                        plugin_id=plugin["id"],
                                        template_file=template,
                                        template_checksum=template_checksum,
                                        actions_file=actions,
                                        actions_checksum=actions_checksum,
                                        obfuscation_file=obfuscation_file,
                                        obfuscation_checksum=obfuscation_checksum,
                                    )
                                )
                                remove = False
                            else:
                                updates = {}

                                if template_checksum != db_plugin_page.template_checksum:
                                    updates.update(
                                        {
                                            Plugin_pages.template_file: template,
                                            Plugin_pages.template_checksum: template_checksum,
                                        }
                                    )

                                if actions_checksum != db_plugin_page.actions_checksum:
                                    updates.update(
                                        {
                                            Plugin_pages.actions_file: actions,
                                            Plugin_pages.actions_checksum: actions_checksum,
                                        }
                                    )

                                if obfuscation_checksum != db_plugin_page.obfuscation_checksum:
                                    updates.update(
                                        {
                                            Plugin_pages.obfuscation_file: obfuscation_file,
                                            Plugin_pages.obfuscation_checksum: obfuscation_checksum,
                                        }
                                    )

                                if updates:
                                    changes = True
                                    session.query(Plugin_pages).filter(Plugin_pages.plugin_id == plugin["id"]).update(updates)

                                remove = False

                    if db_plugin_page and remove:
                        changes = True
                        session.query(Plugin_pages).filter(Plugin_pages.plugin_id == plugin["id"]).delete()

                    db_names = [command.name for command in session.query(BwcliCommands).with_entities(BwcliCommands.name).filter_by(plugin_id=plugin["id"])]
                    missing_names = [command for command in db_names if command not in commands]

                    if missing_names:
                        # Remove commands that are no longer in the list
                        session.query(BwcliCommands).filter(BwcliCommands.name.in_(missing_names), BwcliCommands.plugin_id == plugin["id"]).delete()

                    for command, file_name in commands.items():
                        db_command = session.query(BwcliCommands).with_entities(BwcliCommands.file_name).filter_by(name=command, plugin_id=plugin["id"]).first()
                        command_path = plugin_path.joinpath("bwcli", file_name)

                        if command not in db_names or not db_command:
                            if not command_path.is_file():
                                self.logger.warning(f'Command "{command}"\'s file "{file_name}" does not exist in the plugin directory, skipping it')
                                continue

                            changes = True
                            to_put.append(BwcliCommands(name=command, plugin_id=plugin["id"], file_name=file_name))
                        else:
                            updates = {}

                            if file_name != db_command.file_name:
                                updates[BwcliCommands.file_name] = file_name

                            if updates:
                                changes = True
                                if not command_path.is_file():
                                    session.query(BwcliCommands).filter_by(name=command, plugin_id=plugin["id"]).delete()
                                    continue
                                session.query(BwcliCommands).filter_by(name=command, plugin_id=plugin["id"]).update(updates)

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
                    if path_ui.exists():
                        if {"template.html", "actions.py"}.issubset(listdir(str(path_ui))):
                            db_plugin_page = (
                                session.query(Plugin_pages)
                                .with_entities(
                                    Plugin_pages.template_checksum,
                                    Plugin_pages.actions_checksum,
                                    Plugin_pages.obfuscation_checksum,
                                )
                                .filter_by(plugin_id=plugin["id"])
                                .first()
                            )
                            template = path_ui.joinpath("template.html").read_bytes()
                            actions = path_ui.joinpath("actions.py").read_bytes()
                            template_checksum = bytes_hash(template, algorithm="sha256")
                            actions_checksum = bytes_hash(actions, algorithm="sha256")

                            obfuscation_file = None
                            obfuscation_checksum = None
                            obfuscation_dir = path_ui.joinpath("pyarmor_runtime_000000")
                            if obfuscation_dir.is_dir():
                                obfuscation_file = BytesIO()
                                with ZipFile(obfuscation_file, "w", ZIP_DEFLATED) as zip_file:
                                    for path in obfuscation_dir.rglob("*"):
                                        if path.is_file():
                                            zip_file.write(path, path.relative_to(path_ui))
                                obfuscation_file.seek(0, 0)
                                obfuscation_file = obfuscation_file.getvalue()
                                obfuscation_checksum = bytes_hash(obfuscation_file, algorithm="sha256")

                            if not db_plugin_page:

                                to_put.append(
                                    Plugin_pages(
                                        plugin_id=plugin["id"],
                                        template_file=template,
                                        template_checksum=template_checksum,
                                        actions_file=actions,
                                        actions_checksum=actions_checksum,
                                        obfuscation_file=obfuscation_file,
                                        obfuscation_checksum=obfuscation_checksum,
                                    )
                                )
                            else:
                                updates = {}

                                if template_checksum != db_plugin_page.template_checksum:
                                    updates.update(
                                        {
                                            Plugin_pages.template_file: template,
                                            Plugin_pages.template_checksum: template_checksum,
                                        }
                                    )

                                if actions_checksum != db_plugin_page.actions_checksum:
                                    updates.update(
                                        {
                                            Plugin_pages.actions_file: actions,
                                            Plugin_pages.actions_checksum: actions_checksum,
                                        }
                                    )

                                if obfuscation_checksum != db_plugin_page.obfuscation_checksum:
                                    updates.update(
                                        {
                                            Plugin_pages.obfuscation_file: obfuscation_file,
                                            Plugin_pages.obfuscation_checksum: obfuscation_checksum,
                                        }
                                    )

                                if updates:
                                    session.query(Plugin_pages).filter(Plugin_pages.plugin_id == plugin["id"]).update(updates)

                for command, file_name in commands.items():
                    if not plugin_path.joinpath("bwcli", file_name).is_file():
                        self.logger.warning(f'Command "{command}"\'s file "{file_name}" does not exist in the plugin directory, skipping it')
                        continue

                    to_put.append(BwcliCommands(name=command, plugin_id=plugin["id"], file_name=file_name))

            if changes:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        if _type == "external":
                            metadata.external_plugins_changed = True
                        elif _type == "pro":
                            metadata.pro_plugins_changed = True

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def get_plugins(self, *, _type: Literal["all", "external", "pro"] = "all", with_data: bool = False) -> List[Dict[str, Any]]:
        """Get all plugins from the database."""
        plugins = []
        with self.__db_session() as session:
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

                for command in session.query(BwcliCommands).with_entities(BwcliCommands.name, BwcliCommands.file_name).filter_by(plugin_id=plugin.id):
                    if "bwcli" not in data:
                        data["bwcli"] = {}
                    data["bwcli"][command.name] = command.file_name

                plugins.append(data)

        return plugins

    def get_plugins_errors(self) -> int:
        """Get plugins errors."""
        with self.__db_session() as session:
            return session.query(Jobs).filter(Jobs.success == False).count()  # noqa: E712

    def get_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Get jobs."""
        with self.__db_session() as session:
            return {
                job.name: {
                    "plugin_id": job.plugin_id,
                    "every": job.every,
                    "reload": job.reload,
                    "success": job.success,
                    "last_run": job.last_run.strftime("%Y/%m/%d, %I:%M:%S %p") if job.last_run is not None else "Never",
                    "cache": [
                        {
                            "service_id": cache.service_id,
                            "file_name": cache.file_name,
                            "last_update": cache.last_update.strftime("%Y/%m/%d, %I:%M:%S %p") if cache.last_update is not None else "Never",
                        }
                        for cache in session.query(Jobs_cache)
                        .with_entities(
                            Jobs_cache.service_id,
                            Jobs_cache.file_name,
                            Jobs_cache.last_update,
                        )
                        .filter_by(job_name=job.name)
                    ],
                }
                for job in (
                    session.query(Jobs).with_entities(
                        Jobs.name,
                        Jobs.plugin_id,
                        Jobs.every,
                        Jobs.reload,
                        Jobs.success,
                        Jobs.last_run,
                    )
                )
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

        with self.__db_session() as session:
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
        with self.__db_session() as session:
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

    def add_instance(self, hostname: str, port: int, server_name: str, changed: Optional[bool] = True) -> str:
        """Add instance."""
        with self.__db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            db_instance = session.query(Instances).with_entities(Instances.hostname).filter_by(hostname=hostname).first()

            if db_instance is not None:
                return f"Instance {hostname} already exists, will not be added."

            session.add(Instances(hostname=hostname, port=port, server_name=server_name))

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        metadata.instances_changed = True

            try:
                session.commit()
            except BaseException as e:
                return f"An error occurred while adding the instance {hostname} (port: {port}, server name: {server_name}).\n{e}"

        return ""

    def update_instances(self, instances: List[Dict[str, Any]], changed: Optional[bool] = True) -> str:
        """Update instances."""
        to_put = []
        with self.__db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            session.query(Instances).delete()

            for instance in instances:
                to_put.append(
                    Instances(
                        hostname=instance["hostname"],
                        port=instance["env"].get("API_HTTP_PORT", 5000),
                        server_name=instance["env"].get("API_SERVER_NAME", "bwapi"),
                    )
                )

            if changed:
                with suppress(ProgrammingError, OperationalError):
                    metadata = session.query(Metadata).get(1)
                    if metadata is not None:
                        metadata.instances_changed = True

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def get_instances(self) -> List[Dict[str, Any]]:
        """Get instances."""
        with self.__db_session() as session:
            return [
                {
                    "hostname": instance.hostname,
                    "port": instance.port,
                    "server_name": instance.server_name,
                }
                for instance in (session.query(Instances).with_entities(Instances.hostname, Instances.port, Instances.server_name))
            ]

    def get_plugin_actions(self, plugin: str) -> Optional[Any]:
        """get actions file for the plugin"""
        with self.__db_session() as session:
            page = session.query(Plugin_pages).with_entities(Plugin_pages.actions_file).filter_by(plugin_id=plugin).first()

            if not page:
                return None

            return page.actions_file

    def get_plugin_template(self, plugin: str) -> Optional[Any]:
        """get template file for the plugin"""
        with self.__db_session() as session:
            page = session.query(Plugin_pages).with_entities(Plugin_pages.template_file).filter_by(plugin_id=plugin).first()

            if not page:
                return None

            return page.template_file

    def get_plugin_obfuscation(self, plugin: str) -> Optional[Any]:
        """get obfuscation file for the plugin"""
        with self.__db_session() as session:
            page = session.query(Plugin_pages).with_entities(Plugin_pages.obfuscation_file).filter_by(plugin_id=plugin).first()

            if not page:
                return None

            return page.obfuscation_file

    def get_ui_user(self) -> Optional[dict]:
        """Get ui user."""
        with self.__db_session() as session:
            user = (
                session.query(Users)
                .with_entities(Users.username, Users.password, Users.is_two_factor_enabled, Users.secret_token, Users.method)
                .filter_by(id=1)
                .first()
            )
            if not user:
                return None
            return {
                "username": user.username,
                "password_hash": user.password.encode("utf-8"),
                "is_two_factor_enabled": user.is_two_factor_enabled,
                "secret_token": user.secret_token,
                "method": user.method,
            }

    def create_ui_user(self, username: str, password: bytes, *, secret_token: Optional[str] = None, method: str = "manual") -> str:
        """Create ui user."""
        with self.__db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.query(Users).filter_by(id=1).first()
            if user:
                return "User already exists"

            session.add(Users(id=1, username=username, password=password.decode("utf-8"), secret_token=secret_token, method=method))

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""

    def update_ui_user(
        self, username: str, password: bytes, is_two_factor_enabled: bool = False, secret_token: Optional[str] = None, method: str = "ui"
    ) -> str:
        """Update ui user."""
        with self.__db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"

            user = session.query(Users).filter_by(id=1).first()
            if not user:
                return "User not found"

            user.username = username
            user.password = password.decode("utf-8")
            user.is_two_factor_enabled = is_two_factor_enabled
            user.secret_token = secret_token
            user.method = method

            try:
                session.commit()
            except BaseException as e:
                return str(e)

        return ""
