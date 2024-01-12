#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from contextlib import contextmanager, suppress
from copy import deepcopy
from datetime import datetime
from logging import Logger
from os import _exit, getenv, getpid, listdir, sep
from os.path import normpath, join
from pathlib import Path
from re import compile as re_compile
from subprocess import DEVNULL, PIPE, STDOUT, run as subprocess_run
from sys import path as sys_path
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
from time import sleep
from traceback import format_exc


from models import (
    Actions,
    Actions_tags,
    Base,
    Custom_configs,
    Global_values,
    Instances,
    Jobs,
    Jobs_cache,
    Jobs_runs,
    Metadata,
    Plugin_pages,
    Plugins,
    Plugins_translations,
    Selects,
    Services,
    Services_settings,
    Settings,
    Settings_translations,
    Tags,
    Users,
)

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from jobs import bytes_hash  # type: ignore

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import (
    ArgumentError,
    DatabaseError,
    IntegrityError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import SingletonThreadPool


class Database:
    DB_STRING_RX = re_compile(r"^(?P<database>(mariadb|mysql)(\+pymysql)?|sqlite(\+pysqlite)?|postgresql(\+psycopg)?|oracle(\+oracledb)?):/+(?P<path>/[^\s]+)")
    ALEMBIC_FILE_PATH = Path(sep, "var", "lib", "bunkerweb", "alembic.ini")
    ALEMBIC_DIR = Path(sep, "var", "lib", "bunkerweb", "alembic")

    def __init__(self, logger: Logger, sqlalchemy_string: Optional[str] = None) -> None:
        """Initialize the database"""
        self._logger = logger
        self._session_factory = None
        self._sql_engine = None
        self._exceptions = {}
        self.__sqlite_database = False
        self.lock = Lock()

        if not sqlalchemy_string:
            sqlalchemy_string = getenv("DATABASE_URI", "sqlite:////var/lib/bunkerweb/db.sqlite3")

        match = self.DB_STRING_RX.search(sqlalchemy_string)
        if not match:
            self._logger.error(f"Invalid database string provided: {sqlalchemy_string}, exiting...")
            _exit(1)

        if match.group("database").startswith("sqlite"):
            Path(normpath(match.group("path"))).parent.mkdir(parents=True, exist_ok=True)
        elif match.group("database").startswith("m") and not match.group("database").endswith("+pymysql"):
            sqlalchemy_string = sqlalchemy_string.replace(match.group("database"), f"{match.group('database')}+pymysql")  # ? This is mandatory for alemic to work with mariadb and mysql
        elif match.group("database").startswith("postgresql") and not match.group("database").endswith("+psycopg"):
            sqlalchemy_string = sqlalchemy_string.replace(match.group("database"), f"{match.group('database')}+psycopg")  # ? This is strongly recommended as psycopg is the new way to connect to postgresql
        elif match.group("database").startswith("oracle") and not match.group("database").endswith("+oracledb"):
            sqlalchemy_string = sqlalchemy_string.replace(match.group("database"), f"{match.group('database')}+oracledb")  # ? This is mandatory as cx_oracle is deprecated and oracledb is the new way to connect to oracle

        if not self.ALEMBIC_DIR.exists():
            self.ALEMBIC_DIR.mkdir(parents=True, exist_ok=True)

        if not Path(self.ALEMBIC_FILE_PATH).is_file():
            proc = subprocess_run(
                ["python3", "-m", "alembic", "init", str(self.ALEMBIC_DIR)],
                cwd=str(self.ALEMBIC_FILE_PATH.parent),
                stdout=DEVNULL,
                stderr=STDOUT,
                check=False,
            )
            if proc.returncode != 0:
                self._logger.error(f"Error when trying to initialize alembic: {proc.stdout.decode()}")
                _exit(1)

            # Update the alembic.ini file to use the correct database URI
            config = self.ALEMBIC_FILE_PATH.read_text()
            line_to_replace = next(line for line in config.splitlines() if line.startswith("sqlalchemy.url"))
            config = config.replace(line_to_replace, f"sqlalchemy.url = {sqlalchemy_string}")
            self.ALEMBIC_FILE_PATH.write_text(config)

            # Update the alembic/env.py file to use the correct database model
            env_file = self.ALEMBIC_DIR.joinpath("env.py").read_text()
            line_to_replace = next(line for line in env_file.splitlines() if line.startswith("target_metadata"))
            env_file = env_file.replace(
                line_to_replace,
                f"from sys import path as sys_path\nfrom os.path import join\n\nsys_path.append(join('{sep}', 'usr', 'share', 'bunkerweb', 'db'))\n\nfrom models import Base\n\ntarget_metadata = Base.metadata",
            )
            self.ALEMBIC_DIR.joinpath("env.py").write_text(env_file)

        self.database_uri = sqlalchemy_string
        error = False

        engine_kwargs = {"future": True, "poolclass": SingletonThreadPool, "pool_pre_ping": True, "pool_recycle": 1800}

        try:
            self._sql_engine = create_engine(sqlalchemy_string, **engine_kwargs)
        except ArgumentError:
            self._logger.error(f"Invalid database URI: {sqlalchemy_string}")
            error = True
        except SQLAlchemyError:
            self._logger.error(f"Error when trying to create the engine: {format_exc()}")
            error = True
        finally:
            if error:
                _exit(1)

        try:
            assert self._sql_engine is not None
        except AssertionError:
            self._logger.error("The database engine is not initialized")
            _exit(1)

        not_connected = True
        retries = 15

        while not_connected:
            try:
                with self._sql_engine.connect() as conn:
                    conn.execute(text("CREATE TABLE IF NOT EXISTS test (id INT)"))
                    conn.execute(text("DROP TABLE test"))
                not_connected = False
            except (OperationalError, DatabaseError) as e:
                if retries <= 0:
                    self._logger.error(
                        f"Can't connect to database : {format_exc()}",
                    )
                    _exit(1)

                if "attempt to write a readonly database" in str(e):
                    self._logger.warning("The database is read-only, waiting for it to become writable. Retrying in 5 seconds ...")
                    self._sql_engine.dispose(close=True)
                    self._sql_engine = create_engine(sqlalchemy_string, **engine_kwargs)
                if "Unknown table" in str(e):
                    not_connected = False
                    continue
                else:
                    self._logger.warning(
                        "Can't connect to database, retrying in 5 seconds ...",
                    )
                retries -= 1
                sleep(5)
            except BaseException:
                self._logger.error(f"Error when trying to connect to the database: {format_exc()}")
                exit(1)

        self._logger.info("✅ Database connection established")

        self._session_factory = sessionmaker(bind=self._sql_engine, autoflush=True, expire_on_commit=False)
        self.suffix_rx = re_compile(r"_\d+$")

        if match.group("database").startswith("sqlite"):
            self.__sqlite_database = True
            with self._db_session() as session:
                session.execute(text("PRAGMA journal_mode=WAL"))
                session.commit()

    def __del__(self) -> None:
        """Close the database"""
        if self._session_factory:
            self._session_factory.close_all()

        if self._sql_engine:
            self._sql_engine.dispose()

    @contextmanager
    def _db_session(self):
        try:
            assert self._session_factory is not None
        except AssertionError:
            self._logger.error("The database session is not initialized")
            _exit(1)

        session = scoped_session(self._session_factory)

        try:
            if self.__sqlite_database:
                self.lock.acquire(timeout=10)
            yield session
        except BaseException as e:
            session.rollback()
            self._logger.debug(f"Error when trying to execute a database query: {format_exc()}")
            error = str(e)
            if any(
                msg in error
                for msg in (
                    "disk I/O error",  # ? Sqlite potential errors
                    "database is locked",
                    "file is not a database",
                    "Cannot operate on a closed database",
                    "Lost connection",  # ? Mysql and MariaDB potential errors
                    "Command Out of Sync",
                    "can't change 'autocommit' now",  # ? Postgresql potential errors
                    "It has been closed automatically.",
                    "server closed the connection unexpectedly",
                    "cursor number is invalid or does not exist",  # ? OracleDB potential errors
                    "User requested cancel of current operation.",
                    "the database or network closed the connection",
                    "InternalError",  # ? Misc errors
                    "InterfaceError",
                )  # ? I know this is ugly but I don't know how to do it better
            ):
                self._exceptions[getpid()] = ["retry"]
            else:
                self._exceptions[getpid()] = [error]
            raise
        finally:
            session.remove()
            if self.__sqlite_database:
                self.lock.release()

    def set_scheduler_initialized(self, value: bool = True) -> str:
        """Set the scheduler_initialized value"""
        with suppress(BaseException), self._db_session() as session:
            metadata = session.query(Metadata).get(1)

            if not metadata:
                return "The metadata are not set yet, try again"

            metadata.scheduler_initialized = value
            session.commit()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def is_scheduler_initialized(self) -> bool:
        """Check if it's the scheduler is initialized"""
        with suppress(BaseException), self._db_session() as session:
            try:
                metadata = session.query(Metadata).with_entities(Metadata.scheduler_initialized).filter_by(id=1).first()
                return metadata is not None and metadata.scheduler_initialized
            except (ProgrammingError, OperationalError):
                return False
        return False

    def is_initialized(self) -> bool:
        """Check if the database is initialized"""
        with suppress(BaseException), self._db_session() as session:
            try:
                metadata = session.query(Metadata).with_entities(Metadata.is_initialized).filter_by(id=1).first()
                return metadata is not None and metadata.is_initialized
            except (ProgrammingError, OperationalError, DatabaseError):
                return False
        return False

    def initialize_db(self, version: str, integration: str = "Unknown") -> str:
        """Initialize the database"""
        with suppress(BaseException), self._db_session() as session:
            if session.query(Metadata).get(1):
                session.query(Metadata).filter_by(id=1).update({Metadata.version: version, Metadata.integration: integration})
            else:
                session.add(
                    Metadata(
                        is_initialized=True,
                        version=version,
                        integration=integration,
                    )
                )
            session.commit()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def get_metadata(self) -> Dict[str, str]:
        """Get the metadata from the database"""
        data = {"version": "1.5.4", "integration": "unknown"}
        with suppress(BaseException), self._db_session() as session:
            with suppress(ProgrammingError, OperationalError):
                metadata = session.query(Metadata).with_entities(Metadata.version, Metadata.integration).filter_by(id=1).first()
                if metadata:
                    data = {"version": metadata.version, "integration": metadata.integration}

        return (self._exceptions.get(getpid()) or [data]).pop()

    def update_db_schema(self, version: str) -> Tuple[bool, str]:
        ret = True
        with suppress(BaseException), self._db_session() as session:
            metadata = session.query(Metadata).get(1)

            if not metadata:
                return False, "The metadata are not set yet, try again"
            elif metadata.version == version:
                return False, "The database is already up to date"

            proc = subprocess_run(
                ["python3", "-m", "alembic", "revision", "--autogenerate", "-m", f'"Update to version v{version}"'],
                cwd=str(self.ALEMBIC_FILE_PATH.parent),
                stdout=DEVNULL,
                stderr=STDOUT,
                check=False,
            )
            if proc.returncode != 0:
                session.rollback()
                return True, "Error when trying to generate the migration script"

            proc = subprocess_run(
                [
                    "python3",
                    "-m",
                    "alembic",
                    "upgrade",
                    "head",
                ],
                cwd=str(self.ALEMBIC_FILE_PATH.parent),
                stdout=DEVNULL,
                stderr=STDOUT,
                check=False,
            )
            if proc.returncode != 0:
                session.rollback()
                return True, "Error when trying to apply the migration script"

            metadata.version = version
            session.commit()
            ret = False

        return ret, (self._exceptions.get(getpid()) or [""]).pop()

    def init_tables(self, default_plugins: List[dict], bunkerweb_version: str, *, init: bool = True) -> Tuple[bool, str]:
        """Initialize the database tables and return the result"""
        inspector = inspect(self._sql_engine)
        db_version = None
        has_all_tables = True
        if inspector and len(inspector.get_table_names()):
            db_version = self.get_metadata()["version"]

            if db_version != bunkerweb_version:
                self._logger.warning(f"Database version ({db_version}) is different from Bunkerweb version ({bunkerweb_version}), checking if it needs to be updated")
                for table in Base.metadata.tables:
                    if not inspector.has_table(table):
                        has_all_tables = False
                    else:
                        missing_columns = []

                        db_columns = inspector.get_columns(table)
                        for column in Base.metadata.tables[table].columns:
                            if not any(db_column["name"] == column.name for db_column in db_columns):
                                missing_columns.append(column)

                        with suppress(BaseException), self._db_session() as session:
                            if missing_columns:
                                for column in missing_columns:
                                    session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column.name} {column.type}"))
                            session.commit()

                        if self._exceptions.get(getpid()):
                            return False, self._exceptions[getpid()]

        if has_all_tables and db_version and db_version == bunkerweb_version:
            return False, ""

        try:
            Base.metadata.create_all(self._sql_engine, checkfirst=True)
        except BaseException:
            return False, format_exc()

        to_put = []
        with suppress(BaseException), self._db_session() as session:
            for plugins in default_plugins:
                if not isinstance(plugins, list):
                    plugins = [plugins]

                for plugin in plugins:
                    settings = {}
                    jobs = []
                    page = False
                    if "id" not in plugin:
                        settings = plugin
                        plugin = {
                            "id": "general",
                            "name": {
                                "en": "General",
                                "fr": "Général",
                            },
                            "description": {
                                "en": "The general settings for the server",
                                "fr": "Les paramètres généraux du serveur",
                            },
                            "version": bunkerweb_version,
                            "stream": "partial",
                            "external": False,
                        }
                    else:
                        settings = plugin.pop("settings", {})
                        jobs = plugin.pop("jobs", [])
                        page = plugin.pop("page", False)

                    if isinstance(plugin["name"], str):
                        plugin["name"] = {"en": plugin["name"]}
                    if isinstance(plugin["description"], str):
                        plugin["description"] = {"en": plugin["description"]}

                    plugin_translations = set(plugin["name"].keys()).union(plugin["description"].keys())
                    if "en" not in plugin_translations:
                        self._logger.error(f"Plugin {plugin['id']} doesn't have an english translation, defaulting them")
                        plugin["name"]["en"] = f"No english translation for {plugin['id']}'s name"
                        plugin["description"]["en"] = f"No english translation for {plugin['id']}'s description"
                        plugin_translations = set(plugin["name"].keys()).union(plugin["description"].keys())

                    db_plugin = session.query(Plugins).filter_by(id=plugin["id"]).first()
                    if db_plugin:
                        updates = {}

                        if plugin["version"] != db_plugin.version:
                            updates[Plugins.version] = plugin["version"]

                        if plugin["stream"] != db_plugin.stream:
                            updates[Plugins.stream] = plugin["stream"]

                        if plugin.get("external", False) != db_plugin.external:
                            updates[Plugins.external] = plugin.get("external", False)

                        if plugin.get("method", "manual") != db_plugin.method:
                            updates[Plugins.method] = plugin.get("method", "manual")

                        if plugin.get("data") != db_plugin.data:
                            updates[Plugins.data] = plugin.get("data")

                        if plugin.get("checksum") != db_plugin.checksum:
                            updates[Plugins.checksum] = plugin.get("checksum")

                        if updates:
                            self._logger.warning(f'Plugin "{plugin["id"]}" already exists, updating it with the new values')
                            session.query(Plugins).filter(Plugins.id == plugin["id"]).update(updates)

                        db_plugin_translations = session.query(Plugins_translations).with_entities(Plugins_translations.name, Plugins_translations.description).filter_by(plugin_id=plugin["id"]).all()
                        db_names = {translation.language: translation.name for translation in db_plugin_translations}
                        db_descriptions = {translation.language: translation.description for translation in db_plugin_translations}

                        if plugin["name"] != db_names or plugin["description"] != db_descriptions:
                            self._logger.warning(f'Plugin "{plugin["id"]}" translations changed, updating them with the new values')
                            session.query(Plugins_translations).filter(Plugins_translations.plugin_id == plugin["id"]).delete()
                            for language in plugin_translations:
                                to_put.append(
                                    Plugins_translations(
                                        plugin_id=plugin["id"],
                                        language=language,
                                        name=plugin["name"].get(language, plugin["name"]["en"]),
                                        description=plugin["description"].get(language, plugin["description"]["en"]),
                                    )
                                )
                    else:
                        to_put.append(
                            Plugins(
                                id=plugin["id"],
                                version=plugin["version"],
                                stream=plugin["stream"],
                                external=plugin.get("external", False),
                                method=plugin.get("method"),
                                data=plugin.get("data"),
                                checksum=plugin.get("checksum"),
                            )
                        )

                        for translation in plugin_translations:
                            to_put.append(
                                Plugins_translations(
                                    plugin_id=plugin["id"],
                                    language=translation,
                                    name=plugin["name"].get(translation, plugin["name"]["en"]),
                                    description=plugin["description"].get(translation, plugin["description"]["en"]),
                                )
                            )

                    for setting, value in settings.items():
                        if isinstance(value["help"], str):
                            value["help"] = {"en": value["help"]}
                        if isinstance(value["label"], str):
                            value["label"] = {"en": value["label"]}
                        setting_translations = set(value["help"].keys()).union(value["label"].keys())

                        if "en" not in setting_translations:
                            self._logger.warning(f"Setting {setting} doesn't have an english translation, defaulting them")
                            value["help"]["en"] = f"No english translation for {setting}'s help"
                            value["label"]["en"] = f"No english translation for {setting}'s label"
                            setting_translations = set(value["help"].keys()).union(value["label"].keys())

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

                            if value["name"] != db_setting.name:
                                updates[Settings.name] = value["name"]

                            if value["context"] != db_setting.context:
                                updates[Settings.context] = value["context"]

                            if value["default"] != db_setting.default:
                                updates[Settings.default] = value["default"]

                            if value["regex"] != db_setting.regex:
                                updates[Settings.regex] = value["regex"]

                            if value["type"] != db_setting.type:
                                updates[Settings.type] = value["type"]

                            if value.get("multiple") != db_setting.multiple:
                                updates[Settings.multiple] = value.get("multiple")

                            if updates:
                                self._logger.warning(f'Setting "{setting}" already exists, updating it with the new values')
                                session.query(Settings).filter(Settings.id == setting).update(updates)

                            db_setting_translations = (
                                session.query(Settings_translations)
                                .with_entities(
                                    Settings_translations.help,
                                    Settings_translations.label,
                                )
                                .filter_by(setting_id=setting)
                                .all()
                            )
                            db_help = {translation.language: translation.help for translation in db_setting_translations}
                            db_label = {translation.language: translation.label for translation in db_setting_translations}

                            if value["help"] != db_help or value["label"] != db_label:
                                self._logger.warning(f'Setting "{setting}" translations changed, updating them with the new values')
                                session.query(Settings_translations).filter(Settings_translations.setting_id == setting).delete()
                                for translation in setting_translations:
                                    to_put.append(
                                        Settings_translations(
                                            setting_id=setting,
                                            language=translation,
                                            label=value["label"].get(translation, value["label"]["en"]),
                                            help=value["help"].get(translation, value["help"]["en"]),
                                        )
                                    )
                        else:
                            if db_plugin:
                                self._logger.warning(f'Setting "{setting}" does not exist, creating it')

                            for translation in setting_translations:
                                to_put.append(
                                    Settings_translations(
                                        setting_id=setting,
                                        language=translation,
                                        label=value["label"].get(translation, value["label"]["en"]),
                                        help=value["help"].get(translation, value["help"]["en"]),
                                    )
                                )

                            del value["label"]
                            del value["help"]

                            to_put.append(Settings(**value))

                        db_selects = session.query(Selects).with_entities(Selects.value).filter_by(setting_id=value["id"]).all()
                        db_values = [select.value for select in db_selects]
                        missing_values = [select for select in db_values if select not in select_values]

                        if select_values:
                            if missing_values:
                                # Remove selects that are no longer in the list
                                self._logger.warning(f'Removing {len(missing_values)} selects from setting "{setting}" as they are no longer in the list')
                                session.query(Selects).filter(Selects.value.in_(missing_values)).delete()

                            for select in select_values:
                                if select not in db_values:
                                    to_put.append(Selects(setting_id=value["id"], value=select))
                        else:
                            if missing_values:
                                self._logger.warning(f'Removing all selects from setting "{setting}" as there are no longer any in the list')
                            session.query(Selects).filter_by(setting_id=value["id"]).delete()

                    db_jobs = session.query(Jobs).with_entities(Jobs.name).filter_by(plugin_id=plugin["id"]).all()
                    db_names = [job.name for job in db_jobs]
                    job_names = [job["name"] for job in jobs]
                    missing_names = [job for job in db_names if job not in job_names]

                    if missing_names:
                        # Remove jobs that are no longer in the list
                        self._logger.warning(f'Removing {len(missing_names)} jobs from plugin "{plugin["id"]}" as they are no longer in the list')
                        session.query(Jobs).filter(Jobs.name.in_(missing_names)).delete()

                    for job in jobs:
                        db_job = session.query(Jobs).with_entities(Jobs.file_name, Jobs.every, Jobs.reload).filter_by(name=job["name"], plugin_id=plugin["id"]).first()

                        if job["name"] not in db_names or not db_job:
                            job["file_name"] = job.pop("file")
                            job["reload"] = job.get("reload", False)
                            if db_plugin:
                                self._logger.warning(f'Job "{job["name"]}" does not exist, creating it')
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
                                self._logger.warning(f'Job "{job["name"]}" already exists, updating it with the new values')
                                updates[Jobs.last_run] = None
                                session.query(Jobs_cache).filter(Jobs_cache.job_name == job["name"]).delete()
                                session.query(Jobs).filter(Jobs.name == job["name"]).update(updates)

                    if page:
                        core_ui_path = Path(sep, "usr", "share", "bunkerweb", "core", plugin["id"], "ui")
                        path_ui = core_ui_path if core_ui_path.exists() else Path(sep, "etc", "bunkerweb", "plugins", plugin["id"], "ui")

                        if path_ui.exists():
                            if {"template.html", "actions.py"}.issubset(listdir(str(path_ui))):
                                template_file = path_ui.joinpath("template.html").read_bytes()
                                actions_file = path_ui.joinpath("actions.py").read_bytes()
                                template_checksum = bytes_hash(template_file)
                                actions_checksum = bytes_hash(actions_file)

                                db_plugin_page = (
                                    session.query(Plugin_pages)
                                    .with_entities(
                                        Plugin_pages.template_checksum,
                                        Plugin_pages.actions_checksum,
                                    )
                                    .filter_by(plugin_id=plugin["id"])
                                    .first()
                                )

                                if not db_plugin_page:
                                    to_put.append(
                                        Plugin_pages(
                                            plugin_id=plugin["id"],
                                            template_file=template_file,
                                            template_checksum=template_checksum,
                                            actions_file=actions_file,
                                            actions_checksum=actions_checksum,
                                        )
                                    )
                                else:
                                    updates = {}

                                    if template_checksum != db_plugin_page.template_checksum:
                                        updates.update(
                                            {
                                                Plugin_pages.template_file: template_file,
                                                Plugin_pages.template_checksum: template_checksum,
                                            }
                                        )

                                    if actions_checksum != db_plugin_page.actions_checksum:
                                        updates.update(
                                            {
                                                Plugin_pages.actions_file: actions_file,
                                                Plugin_pages.actions_checksum: actions_checksum,
                                            }
                                        )

                                    if updates:
                                        session.query(Plugin_pages).filter(Plugin_pages.plugin_id == plugin["id"]).update(updates)
                        else:
                            self._logger.warning(f'Page for plugin "{plugin["id"]}" does not exist, deleting existing one')
                            session.query(Plugin_pages).filter(Plugin_pages.plugin_id == plugin["id"]).delete()

            session.add_all(to_put)
            session.commit()

        if self._exceptions.get(getpid()):
            return False, self._exceptions[getpid()]

        if init:
            proc = subprocess_run(
                ["python3", "-m", "alembic", "revision", "--autogenerate", "-m", '"init"'],
                cwd=str(self.ALEMBIC_FILE_PATH.parent),
                stdout=DEVNULL,
                stderr=PIPE,
                check=False,
            )
            if proc.returncode != 0:
                return (
                    False,
                    f"Error when trying to generate the migration script: {proc.stderr.decode()}",
                )

            proc = subprocess_run(
                ["python3", "-m", "alembic", "upgrade", "head"],
                cwd=str(self.ALEMBIC_FILE_PATH.parent),
                stdout=DEVNULL,
                stderr=PIPE,
                check=False,
            )
            if proc.returncode != 0:
                return (
                    False,
                    f"Error when trying to apply the migration script: {proc.stderr.decode()}",
                )

        return True, ""

    def save_config(self, config: Dict[str, Any], method: str, *, clear: bool = True) -> str:
        """Save the config in the database"""
        to_put = []
        with suppress(BaseException), self._db_session() as session:
            if clear:
                # Delete all the old config
                session.query(Global_values).filter(Global_values.method == method).delete()
                session.query(Services_settings).filter(Services_settings.method == method).delete()

            if config:
                config.pop("DATABASE_URI", None)
                db_services = session.query(Services).with_entities(Services.id, Services.method).all()
                db_ids = [service.id for service in db_services]
                services = config.get("SERVER_NAME", [])

                if isinstance(services, str):
                    services = services.split(" ")

                if clear and db_services:
                    missing_ids = [service.id for service in db_services if (service.method == method) and service.id not in services]

                    if missing_ids:
                        # Remove services that are no longer in the list
                        session.query(Services).filter(Services.id.in_(missing_ids)).delete()

                if config.get("MULTISITE", "yes") == "yes":
                    global_values = []

                    for key, value in deepcopy(config).items():
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
                                self._logger.debug(f"Adding service {server_name} to the database")
                                to_put.append(Services(id=server_name, method=method))
                                db_ids.append(server_name)

                            key = key.replace(f"{server_name}_", "")
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
                                if key != "SERVER_NAME" and ((key not in config and value == setting.default) or (key in config and value == config[key])):
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
                                if key != "SERVER_NAME" and ((key not in config and value == setting.default) or (key in config and value == config[key])):
                                    if clear:
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
                                if key == "SERVER_NAME" or value == setting.default:
                                    continue

                                to_put.append(
                                    Global_values(
                                        setting_id=key,
                                        value=value,
                                        suffix=suffix,
                                        method=method,
                                    )
                                )
                            elif method in (global_value.method, "core") and global_value.value != value:
                                if key == "SERVER_NAME" or value == setting.default:
                                    if clear:
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
                    if config.get("SERVER_NAME", "www.example.com") and not session.query(Services).with_entities(Services.id).filter_by(id=config.get("SERVER_NAME", "www.example.com").split(" ")[0]).first():
                        to_put.append(Services(id=config["SERVER_NAME"].split()[0], method=method))

                    config.pop("SERVER_NAME", None)

                    for key, value in config.items():
                        suffix = 0
                        if self.suffix_rx.search(key):
                            suffix = int(key.split("_")[-1])
                            key = key[: -len(str(suffix)) - 1]

                        setting = session.query(Settings).with_entities(Settings.default).filter_by(id=key).first()

                        if not setting:
                            continue

                        global_value = session.query(Global_values).with_entities(Global_values.value, Global_values.method).filter_by(setting_id=key, suffix=suffix).first()

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
                        elif method in (global_value.method, "core") and value != global_value.value:
                            if value == setting.default:
                                if clear:
                                    session.query(Global_values).filter(
                                        Global_values.setting_id == key,
                                        Global_values.suffix == suffix,
                                    ).delete()
                                continue

                            session.query(Global_values).filter(
                                Global_values.setting_id == key,
                                Global_values.suffix == suffix,
                            ).update({Global_values.value: value})

            session.add_all(to_put)
            session.commit()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def save_global_config(self, config: Dict[str, Any], method: str) -> str:
        """Save the global config in the database"""
        ret = ""
        with suppress(BaseException), self._db_session() as session:
            # Delete all the old global config
            session.query(Global_values).filter(Global_values.method == method).delete()

            session.commit()

            ret = self.save_config(config, method, clear=False)

        return (self._exceptions.get(getpid()) or [ret]).pop()

    def save_service_config(self, service_name: str, config: Dict[str, Any], method: str) -> str:
        """Save the service config in the database"""
        to_put = []
        ret = "updated"
        new_ret = ""
        with suppress(BaseException), self._db_session() as session:
            # Delete all the old service config
            db_service = session.query(Services).with_entities(Services.id, Services.method).filter_by(id=service_name).first()

            if "SERVER_NAME" not in config:
                config["SERVER_NAME"] = service_name

            first_server_name: str = config["SERVER_NAME"].split(" ")[0]

            if db_service:
                if first_server_name != service_name:
                    if method not in (db_service.method, "autoconf"):
                        return "method_conflict"

                    service_settings = session.query(Services_settings).with_entities(Services_settings.method).filter_by(service_id=service_name).all()

                    if method != "autoconf" and not all(setting.method == method for setting in service_settings):
                        return "method_conflict"

                    session.query(Services).filter(Services.id == service_name).update({Services.id: first_server_name, Services.method: method})

                session.query(Services_settings).filter(
                    Services_settings.method == method,
                    Services_settings.service_id == first_server_name,
                ).delete()
            else:
                to_put.append(Services(id=first_server_name, method=method))
                ret = "created"

            service_name = first_server_name

            for key in config.copy():
                if key.startswith(f"{service_name}_"):
                    continue
                config[f"{service_name}_{key}"] = config.pop(key)

            config["MULTISITE"] = "yes"

            session.add_all(to_put)
            session.commit()

            config["SERVER_NAME"] = " ".join(set(sorted(str(service.id) for service in session.query(Services).all())))

            new_ret = self.save_config(config, method, clear=False)

        return (self._exceptions.get(getpid()) or [new_ret or ret]).pop()

    def remove_service(self, service_name: str, method: str) -> str:
        """Remove a service from the database"""
        with suppress(BaseException), self._db_session() as session:
            # Delete all the old service config
            db_service = session.query(Services).with_entities(Services.id, Services.method).filter_by(id=service_name).first()

            if not db_service:
                return "not_found"
            elif method not in (db_service.method, "autoconf"):
                return "method_conflict"

            session.query(Services).filter(Services.id == service_name).delete()
            session.commit()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def save_custom_configs(self, custom_configs: List[Dict[str, Tuple[str, List[str]]]], method: str) -> List[str]:
        """Save the custom configs in the database"""
        messages = []
        with suppress(BaseException), self._db_session() as session:
            # Delete all the old config
            session.query(Custom_configs).filter(Custom_configs.method == method).delete()

            to_put = []
            for custom_config in custom_configs:
                config = {
                    "data": custom_config["value"].encode("utf-8") if isinstance(custom_config["value"], str) else custom_config["value"],
                    "method": method,
                }
                config["checksum"] = bytes_hash(config["data"])

                if custom_config["exploded"][0]:
                    if not session.query(Services).with_entities(Services.id).filter_by(id=custom_config["exploded"][0]).first():
                        messages.append(f"Couldn't find service {custom_config['exploded'][0]}, custom config \"{custom_config['exploded'][0]}_{custom_config['exploded'][1]}_{custom_config['exploded'][2]}\" will not be saved")  # type: ignore
                        continue

                    config.update({"service_id": custom_config["exploded"][0], "type": custom_config["exploded"][1].replace("-", "_").lower(), "name": custom_config["exploded"][2]})  # type: ignore
                else:
                    config.update({"type": custom_config["exploded"][1].replace("-", "_").lower(), "name": custom_config["exploded"][2]})  # type: ignore

                custom_conf = session.query(Custom_configs).with_entities(Custom_configs.checksum, Custom_configs.method).filter_by(service_id=config.get("service_id", None), type=config["type"], name=config["name"]).first()

                if not custom_conf:
                    to_put.append(Custom_configs(**config))
                elif method in (custom_conf.method, "autoconf"):
                    session.query(Custom_configs).filter(Custom_configs.service_id == config.get("service_id", None), Custom_configs.type == config["type"], Custom_configs.name == config["name"]).update(
                        {Custom_configs.data: config["data"], Custom_configs.checksum: config["checksum"], Custom_configs.method: method}
                    )

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException:
                session.rollback()
                return [format_exc()]

        return (self._exceptions.get(getpid()) or [messages]).pop()

    def get_config(self, methods: bool = False, *, new_format: bool = False) -> Dict[str, Dict[str, Union[str, bool]]]:
        """Get the config from the database"""
        config: dict = {}
        global_config = config
        if new_format:
            del global_config
            config = {"global": {}, "services": {}}
            global_config = config["global"]
        with suppress(BaseException), self._db_session() as session:
            multisite = []
            for setting in (
                session.query(Settings)
                .with_entities(
                    Settings.id,
                    Settings.context,
                    Settings.default,
                    Settings.multiple,
                )
                .all()
            ):
                default = setting.default or ""
                global_config[setting.id] = {"value": default, "method": "default"} | ({"global": True} if not new_format else {}) if methods else default

                for global_value in session.query(Global_values).with_entities(Global_values.value, Global_values.suffix, Global_values.method).filter_by(setting_id=setting.id).all():
                    setting_key = setting.id + (f"_{global_value.suffix}" if setting.multiple and global_value.suffix > 0 else "")
                    global_config[setting_key] = {"value": global_value.value or "", "method": global_value.method} | ({"global": True} if not new_format else {}) if methods else (global_value.value or "")

                if setting.context == "multisite":
                    multisite.append(setting.id)

            is_multisite = global_config.get("MULTISITE", {"value": "yes"})["value"] == "yes" if methods else global_config.get("MULTISITE", "yes") == "yes"

            if is_multisite:
                for service in session.query(Services).with_entities(Services.id).all():
                    if new_format and service not in config["services"]:
                        config["services"][service.id] = {}
                    for key, value in deepcopy(global_config).items():
                        original_key = key
                        if self.suffix_rx.search(key):
                            key = key[: -len(str(key.split("_")[-1])) - 1]

                        if key not in multisite:
                            continue
                        elif new_format and original_key not in config["services"][service.id]:
                            config["services"][service.id][original_key] = value or ""
                        elif f"{service.id}_{original_key}" not in config:
                            config[f"{service.id}_{original_key}"] = value or ""

                        service_settings = (
                            session.query(Services_settings)
                            .with_entities(
                                Services_settings.value,
                                Services_settings.suffix,
                                Services_settings.method,
                            )
                            .filter_by(service_id=service.id, setting_id=key)
                            .all()
                        )

                        for service_setting in service_settings:
                            setting_key = key + (f"_{service_setting.suffix}" if service_setting.suffix > 0 else "")
                            if new_format:
                                config["services"][service.id][setting_key] = (
                                    {
                                        "value": service_setting.value or "",
                                        "method": service_setting.method,
                                    }
                                    if methods
                                    else (service_setting.value or "")
                                )
                            else:
                                config[f"{service.id}_{setting_key}"] = (
                                    {
                                        "value": service_setting.value or "",
                                        "global": False,
                                        "method": service_setting.method,
                                    }
                                    if methods
                                    else (service_setting.value or "")
                                )

            servers = " ".join(set(sorted(str(service.id) for service in session.query(Services).all())))
            global_config["SERVER_NAME"] = {"value": servers, "method": "default"} | ({"global": True} if not new_format else {}) if methods else servers

        return (self._exceptions.get(getpid()) or [config]).pop()

    def get_custom_configs(self) -> Union[str, List[Dict[str, Any]]]:
        """Get the custom configs from the database"""
        with suppress(BaseException), self._db_session() as session:
            return [
                {
                    "service_id": custom_config.service_id,
                    "type": custom_config.type,
                    "name": custom_config.name,
                    "data": custom_config.data,
                    "method": custom_config.method,
                }
                for custom_config in (
                    session.query(Custom_configs)
                    .with_entities(
                        Custom_configs.service_id,
                        Custom_configs.type,
                        Custom_configs.name,
                        Custom_configs.data,
                        Custom_configs.method,
                    )
                    .all()
                )
            ]
        return (self._exceptions.get(getpid()) or ["An error occurred, couldn't fetch the traceback"]).pop()

    def upsert_custom_config(
        self,
        service_id: str,
        config_type: str,
        name: str,
        data: bytes,
        method: str,
        *,
        checksum: Optional[str] = None,
        old_name: Optional[str] = None,
    ) -> str:
        """Add or update a custom config in the database"""
        old_name = old_name or name
        ret = ""
        with suppress(BaseException), self._db_session() as session:
            config = {
                "data": data,
                "method": method,
                "checksum": checksum or bytes_hash(data),
                "service_id": service_id,
                "type": config_type.replace("-", "_").lower(),
                "name": name,
            }

            custom_conf = (
                session.query(Custom_configs)
                .with_entities(Custom_configs.checksum, Custom_configs.method)
                .filter_by(
                    service_id=config["service_id"],
                    type=config["type"],
                    name=old_name,
                )
                .first()
            )

            if not custom_conf:
                session.add(Custom_configs(**config))
                ret = "created"
            elif method not in (custom_conf.method, "autoconf"):
                ret = "method_conflict"
            else:
                session.query(Custom_configs).filter(
                    Custom_configs.service_id == config["service_id"],
                    Custom_configs.type == config["type"],
                    Custom_configs.name == old_name,
                ).update(
                    {
                        Custom_configs.name: config["name"],
                        Custom_configs.data: config["data"],
                        Custom_configs.checksum: config["checksum"],
                        Custom_configs.method: method,
                    }
                )
                ret = "updated"
            session.commit()

        return (self._exceptions.get(getpid()) or [ret]).pop()

    def delete_custom_config(self, service_id: str, config_type: str, name: str, method: str) -> str:
        """Delete a custom config from the database"""
        with suppress(BaseException), self._db_session() as session:
            custom_conf = (
                session.query(Custom_configs)
                .with_entities(Custom_configs.method)
                .filter_by(
                    service_id=service_id,
                    type=config_type.replace("-", "_").lower(),
                    name=name,
                )
                .first()
            )

            if not custom_conf:
                return "not_found"
            elif method not in (custom_conf.method, "autoconf"):
                return "method_conflict"

            session.query(Custom_configs).filter(
                Custom_configs.service_id == service_id,
                Custom_configs.type == config_type.replace("-", "_").lower(),
                Custom_configs.name == name,
            ).delete()
            session.commit()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def get_services_settings(self, methods: bool = False) -> List[Dict[str, Any]]:
        """Get the services' configs from the database"""
        services = []
        config = self.get_config(methods=methods)
        with suppress(BaseException), self._db_session() as session:
            service_names = [service.id for service in session.query(Services).with_entities(Services.id).all()]
            for service in service_names:
                tmp_config = deepcopy(config)

                for key, value in deepcopy(tmp_config).items():
                    if key.startswith(f"{service}_"):
                        tmp_config[key.replace(f"{service}_", "")] = tmp_config.pop(key)
                    elif any(key.startswith(f"{s}_") for s in service_names):
                        tmp_config.pop(key)
                    else:
                        tmp_config[key] = {"value": value["value"], "global": True, "method": "default"} if methods else value

                services.append(tmp_config)

        return services

    def upsert_external_plugin(self, plugin_data: Dict[str, Any], *, plugin_id: Optional[str] = None, return_if_exists: bool = False, passed_session: Optional[scoped_session] = None) -> str:
        """Upsert an external plugin from the database."""
        to_put = []
        with suppress(BaseException), self._db_session() as session:
            db_plugin = (
                (passed_session or session)
                .query(Plugins)
                .with_entities(
                    Plugins.id,
                    Plugins.version,
                    Plugins.stream,
                    Plugins.external,
                    Plugins.method,
                    Plugins.data,
                    Plugins.checksum,
                )
                .filter_by(id=plugin_id or plugin_data["id"])
                .first()
            )

            settings = plugin_data.pop("settings", {})
            jobs = plugin_data.pop("jobs", [])
            page = plugin_data.pop("page", False)
            template_file: Optional[bytes] = plugin_data.pop("template_file", None)
            actions_file: Optional[bytes] = plugin_data.pop("actions_file", None)

            if plugin_id and db_plugin is None:
                return "not_found"

            if isinstance(plugin_data["name"], str):
                plugin_data["name"] = {"en": plugin_data["name"]}
            if isinstance(plugin_data["description"], str):
                plugin_data["description"] = {"en": plugin_data["description"]}

            plugin_translations = set(plugin_data["name"].keys()).union(plugin_data["description"].keys())

            if "en" not in plugin_translations:
                return "no_en_translation"

            if db_plugin:
                if return_if_exists:
                    return "exists"
                if db_plugin.external is False:
                    return "not_external"

                updates = {}

                if plugin_data["id"] != db_plugin.id:
                    updates[Plugins.id] = plugin_data["id"]

                if plugin_data["version"] != db_plugin.version:
                    updates[Plugins.version] = plugin_data["version"]

                if plugin_data["stream"] != db_plugin.stream:
                    updates[Plugins.stream] = plugin_data["stream"]

                if plugin_data["method"] != db_plugin.method:
                    updates[Plugins.method] = plugin_data["method"]

                if plugin_data.get("data") != db_plugin.data:
                    updates[Plugins.data] = plugin_data.get("data")

                if plugin_data.get("checksum") != db_plugin.checksum:
                    updates[Plugins.checksum] = plugin_data.get("checksum")

                if updates:
                    (passed_session or session).query(Plugins).filter(Plugins.id == plugin_id).update(updates)

                db_plugin_translations = (passed_session or session).query(Plugins_translations).with_entities(Plugins_translations.name, Plugins_translations.description).filter_by(plugin_id=plugin_data["id"]).all()
                db_names = {translation.language: translation.name for translation in db_plugin_translations}
                db_descriptions = {translation.language: translation.description for translation in db_plugin_translations}

                if plugin_data["id"] != db_plugin.id or plugin_data["name"] != db_names or plugin_data["description"] != db_descriptions:
                    (passed_session or session).query(Plugins_translations).filter(Plugins_translations.plugin_id == plugin_id).delete()
                    for language in plugin_translations:
                        to_put.append(
                            Plugins_translations(
                                plugin_id=plugin_data["id"],
                                language=language,
                                name=plugin_data["name"].get(language, plugin_data["name"]["en"]),
                                description=plugin_data["description"].get(language, plugin_data["description"]["en"]),
                            )
                        )

                db_plugin_settings = (passed_session or session).query(Settings).with_entities(Settings.id).filter_by(plugin_id=plugin_id).all()
                db_ids = [setting.id for setting in db_plugin_settings]
                setting_ids = [setting for setting in settings]
                missing_ids = [setting for setting in db_ids if setting not in setting_ids]

                if missing_ids:
                    # Remove settings that are no longer in the list
                    (passed_session or session).query(Settings).filter(Settings.id.in_(missing_ids)).delete()

                for setting, value in settings.items():
                    if isinstance(value["help"], str):
                        value["help"] = {"en": value["help"]}
                    if isinstance(value["label"], str):
                        value["label"] = {"en": value["label"]}
                    translations = set(value["help"].keys()).union(value["label"].keys())

                    if "en" not in translations:
                        self._logger.error(f"Setting {setting} doesn't have an english translation, skipping it")
                        continue

                    value.update(
                        {
                            "plugin_id": plugin_data["id"],
                            "name": value["id"],
                            "id": setting,
                        }
                    )
                    db_setting = (
                        (passed_session or session)
                        .query(Settings)
                        .with_entities(
                            Settings.name,
                            Settings.context,
                            Settings.default,
                            Settings.regex,
                            Settings.type,
                            Settings.multiple,
                        )
                        .filter_by(id=setting)
                        .first()
                    )

                    if setting not in db_ids or not db_setting:
                        for select in value.pop("select", []):
                            to_put.append(Selects(setting_id=value["id"], value=select))

                        for translation in translations:
                            to_put.append(
                                Settings_translations(
                                    setting_id=setting,
                                    language=translation,
                                    label=value["label"].get(translation, value["label"]["en"]),
                                    help=value["help"].get(translation, value["help"]["en"]),
                                )
                            )

                        del value["label"]
                        del value["help"]

                        to_put.append(Settings(**value))
                    else:
                        updates = {}

                        if plugin_data["id"] != db_plugin.id:
                            updates[Settings.plugin_id] = plugin_data["id"]

                        if value["name"] != db_setting.name:
                            updates[Settings.name] = value["name"]

                        if value["context"] != db_setting.context:
                            updates[Settings.context] = value["context"]

                        if value["default"] != db_setting.default:
                            updates[Settings.default] = value["default"]

                        if value["regex"] != db_setting.regex:
                            updates[Settings.regex] = value["regex"]

                        if value["type"] != db_setting.type:
                            updates[Settings.type] = value["type"]

                        if value.get("multiple") != db_setting.multiple:
                            updates[Settings.multiple] = value.get("multiple")

                        if updates:
                            (passed_session or session).query(Settings).filter(Settings.id == setting).update(updates)

                        db_setting_translations = (
                            (passed_session or session)
                            .query(Settings_translations)
                            .with_entities(
                                Settings_translations.help,
                                Settings_translations.label,
                            )
                            .filter_by(setting_id=setting)
                            .all()
                        )
                        db_help = {translation.language: translation.help for translation in db_setting_translations}
                        db_label = {translation.language: translation.label for translation in db_setting_translations}

                        if value["help"] != db_help or value["label"] != db_label:
                            (passed_session or session).query(Settings_translations).filter(Settings_translations.setting_id == setting).delete()
                            for translation in translations:
                                to_put.append(
                                    Settings_translations(
                                        setting_id=setting,
                                        language=translation,
                                        label=value["label"].get(translation, value["label"]["en"]),
                                        help=value["help"].get(translation, value["help"]["en"]),
                                    )
                                )

                        db_selects = (passed_session or session).query(Selects).with_entities(Selects.value).filter_by(setting_id=setting).all()
                        db_values = [select.value for select in db_selects]
                        select_values = value.get("select", [])
                        missing_values = [select for select in db_values if select not in select_values]

                        if missing_values:
                            # Remove selects that are no longer in the list
                            (passed_session or session).query(Selects).filter(Selects.value.in_(missing_values)).delete()

                        for select in value.get("select", []):
                            if select not in db_values:
                                to_put.append(Selects(setting_id=setting, value=select))

                db_jobs = (passed_session or session).query(Jobs).with_entities(Jobs.name).filter_by(plugin_id=plugin_id).all()
                db_names = [job.name for job in db_jobs]
                job_names = [job["name"] for job in jobs]
                missing_names = [job for job in db_names if job not in job_names]

                if missing_names:
                    # Remove jobs that are no longer in the list
                    (passed_session or session).query(Jobs).filter(Jobs.name.in_(missing_names)).delete()

                for job in jobs:
                    db_job = (passed_session or session).query(Jobs).with_entities(Jobs.file_name, Jobs.every, Jobs.reload).filter_by(name=job["name"], plugin_id=plugin_id).first()

                    if job["name"] not in db_names or not db_job:
                        job["file_name"] = job.pop("file")
                        job["reload"] = job.get("reload", False)
                        to_put.append(Jobs(plugin_id=plugin_id, **job))
                    else:
                        updates = {}

                        if plugin_data["id"] != db_plugin.id:
                            updates[Jobs.plugin_id] = plugin_data["id"]

                        if job["file"] != db_job.file_name:
                            updates[Jobs.file_name] = job["file"]

                        if job["every"] != db_job.every:
                            updates[Jobs.every] = job["every"]

                        if job.get("reload", None) != db_job.reload:
                            updates[Jobs.reload] = job.get("reload", False)

                        if updates:
                            updates[Jobs.last_run] = None
                            (passed_session or session).query(Jobs_cache).filter(Jobs_cache.job_name == job["name"]).delete()
                            (passed_session or session).query(Jobs).filter(Jobs.name == job["name"]).update(updates)

                ui_path = Path(sep, "var", "tmp", "bunkerweb", "ui", plugin_data["id"], "ui")
                if plugin_id and not ui_path.exists():
                    ui_path = Path(sep, "etc", "bunkerweb", "plugins", plugin_id, "ui")
                if not ui_path.exists():
                    ui_path = Path(sep, "etc", "bunkerweb", "plugins", plugin_data["id"], "ui")

                if page or ui_path.exists():
                    if template_file and actions_file or {"template.html", "actions.py"}.issubset(listdir(str(ui_path))):
                        if not template_file:
                            template_file = ui_path.joinpath("template.html").read_bytes()
                        if not actions_file:
                            actions_file = ui_path.joinpath("actions.py").read_bytes()

                        template_checksum = plugin_data.pop("template_checksum", bytes_hash(template_file))
                        actions_checksum = plugin_data.pop("actions_checksum", bytes_hash(actions_file))
                        db_plugin_page = (
                            (passed_session or session)
                            .query(Plugin_pages)
                            .with_entities(
                                Plugin_pages.template_checksum,
                                Plugin_pages.actions_checksum,
                            )
                            .filter_by(plugin_id=plugin_id)
                            .first()
                        )

                        if not db_plugin_page:
                            to_put.append(
                                Plugin_pages(
                                    plugin_id=plugin_data["id"],
                                    template_file=template_file,
                                    template_checksum=template_checksum,
                                    actions_file=actions_file,
                                    actions_checksum=actions_checksum,
                                )
                            )
                        else:
                            updates = {}

                            if plugin_data["id"] != db_plugin.id:
                                updates[Plugin_pages.plugin_id] = plugin_data["id"]

                            if template_checksum != db_plugin_page.template_checksum:
                                updates.update(
                                    {
                                        Plugin_pages.template_file: template_file,
                                        Plugin_pages.template_checksum: template_checksum,
                                    }
                                )

                            if actions_checksum != db_plugin_page.actions_checksum:
                                updates.update(
                                    {
                                        Plugin_pages.actions_file: actions_file,
                                        Plugin_pages.actions_checksum: actions_checksum,
                                    }
                                )

                            if updates:
                                (passed_session or session).query(Plugin_pages).filter(Plugin_pages.plugin_id == plugin_id).update(updates)

                    else:
                        (passed_session or session).query(Plugin_pages).filter(Plugin_pages.plugin_id == plugin_id).delete()

                        self._logger.warning(
                            f'Plugin "{plugin_id}" has a page but no template or actions file, skipping page addition and removing existing page.',
                        )
            else:
                to_put.append(
                    Plugins(
                        id=plugin_data["id"],
                        version=plugin_data["version"],
                        stream=plugin_data["stream"],
                        external=True,
                        method=plugin_data["method"],
                        data=plugin_data.get("data"),
                        checksum=plugin_data.get("checksum"),
                    )
                )

                for translation in plugin_translations:
                    to_put.append(
                        Plugins_translations(
                            plugin_id=plugin_data["id"],
                            language=translation,
                            name=plugin_data["name"].get(translation, plugin_data["name"]["en"]),
                            description=plugin_data["description"].get(translation, plugin_data["description"]["en"]),
                        )
                    )

                for setting, value in settings.items():
                    db_setting = (passed_session or session).query(Settings).filter_by(id=setting).first()

                    if db_setting is not None:
                        self._logger.warning(f"A setting with id {setting} already exists, therefore it will not be added.")
                        continue

                    if isinstance(value["help"], str):
                        value["help"] = {"en": value["help"]}
                    if isinstance(value["label"], str):
                        value["label"] = {"en": value["label"]}

                    translations = set(value["help"].keys()).union(value["label"].keys())

                    if "en" not in translations:
                        self._logger.error(f"Setting {setting} doesn't have an english translation, skipping it")
                        continue

                    value.update(
                        {
                            "plugin_id": plugin_data["id"],
                            "name": value["id"],
                            "id": setting,
                        }
                    )

                    for select in value.pop("select", []):
                        to_put.append(Selects(setting_id=value["id"], value=select))

                    for translation in translations:
                        to_put.append(
                            Settings_translations(
                                setting_id=setting,
                                language=translation,
                                label=value["label"].get(translation, value["label"]["en"]),
                                help=value["help"].get(translation, value["help"]["en"]),
                            )
                        )

                    del value["label"]
                    del value["help"]

                    to_put.append(Settings(**value))

                for job in jobs:
                    db_job = (passed_session or session).query(Jobs).with_entities(Jobs.file_name, Jobs.every, Jobs.reload).filter_by(name=job["name"], plugin_id=plugin_data["id"]).first()

                    if db_job is not None:
                        self._logger.warning(f"A job with the name {job['name']} already exists in the database, therefore it will not be added.")
                        continue

                    job["file_name"] = job.pop("file")
                    job["reload"] = job.get("reload", False)
                    to_put.append(Jobs(plugin_id=plugin_data["id"], **job))

                ui_path = Path(sep, "var", "tmp", "bunkerweb", "ui", plugin_data["id"], "ui")
                if plugin_id and not ui_path.exists():
                    ui_path = Path(sep, "etc", "bunkerweb", "plugins", plugin_id, "ui")
                if not ui_path.exists():
                    ui_path = Path(sep, "etc", "bunkerweb", "plugins", plugin_data["id"], "ui")

                if page or ui_path.exists() and (template_file and actions_file or {"template.html", "actions.py"}.issubset(listdir(str(ui_path)))):
                    if not template_file:
                        template_file = ui_path.joinpath("template.html").read_bytes()
                    if not actions_file:
                        actions_file = ui_path.joinpath("actions.py").read_bytes()

                    (passed_session or session).query(Plugin_pages).filter(Plugin_pages.plugin_id == plugin_id).delete()

                    to_put.append(
                        Plugin_pages(
                            plugin_id=plugin_data["id"],
                            template_file=template_file,
                            template_checksum=plugin_data.pop("template_checksum", bytes_hash(template_file)),
                            actions_file=actions_file,
                            actions_checksum=plugin_data.pop("actions_checksum", bytes_hash(actions_file)),
                        )
                    )

            (passed_session or session).add_all(to_put)
            if not passed_session:
                session.commit()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def update_external_plugins(self, plugins: List[Dict[str, Any]], *, delete_missing: bool = True) -> str:
        """Update external plugins from the database"""
        with suppress(BaseException), self._db_session() as session:
            db_plugins = session.query(Plugins).with_entities(Plugins.id).filter_by(external=True).all()

            db_ids = []
            if delete_missing and db_plugins:
                db_ids = [plugin.id for plugin in db_plugins]
                ids = [plugin["id"] for plugin in plugins]
                missing_ids = [plugin for plugin in db_ids if plugin not in ids]

                if missing_ids:
                    # Remove plugins that are no longer in the list
                    session.query(Plugins).filter(Plugins.id.in_(missing_ids)).delete()

            for plugin in plugins:
                ret = self.upsert_external_plugin(plugin, return_if_exists=not delete_missing, passed_session=session)
                if ret == "retry":
                    session.rollback()
                    return ret
                elif ret == "exists":
                    self._logger.warning(f"Plugin {plugin['id']} already exists, skipping it")
                elif ret == "no_en_translation":
                    self._logger.warning(f"Plugin {plugin['id']} doesn't have an english translation, skipping it")
                elif ret:
                    self._logger.error(f"An error occurred while updating plugin {plugin['id']}: {ret}")

            session.commit()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def get_plugins(self, *, external: bool = False, with_data: bool = False) -> List[Dict[str, Any]]:
        """Get all plugins from the database."""
        plugins = []
        with suppress(BaseException), self._db_session() as session:
            for plugin in (
                session.query(Plugins)
                .with_entities(
                    Plugins.id,
                    Plugins.version,
                    Plugins.stream,
                    Plugins.external,
                    Plugins.method,
                    Plugins.data,
                    Plugins.checksum,
                )
                .all()
                if with_data
                else session.query(Plugins)
                .with_entities(
                    Plugins.id,
                    Plugins.version,
                    Plugins.stream,
                    Plugins.external,
                    Plugins.method,
                )
                .all()
            ):
                if external and not plugin.external:
                    continue

                page = session.query(Plugin_pages).with_entities(Plugin_pages.id).filter_by(plugin_id=plugin.id).first()
                data = {
                    "id": plugin.id,
                    "stream": plugin.stream,
                    "name": {},
                    "description": {},
                    "version": plugin.version,
                    "external": plugin.external,
                    "method": plugin.method,
                    "page": page is not None,
                    "settings": {},
                } | ({"data": plugin.data, "checksum": plugin.checksum} if with_data else {})

                for translation in session.query(Plugins_translations).with_entities(Plugins_translations.language, Plugins_translations.name, Plugins_translations.description).filter_by(plugin_id=plugin.id).all():
                    data["name"][translation.language] = translation.name
                    data["description"][translation.language] = translation.description

                for setting in (
                    session.query(Settings)
                    .with_entities(
                        Settings.id,
                        Settings.name,
                        Settings.context,
                        Settings.default,
                        Settings.regex,
                        Settings.type,
                        Settings.multiple,
                    )
                    .filter_by(plugin_id=plugin.id)
                    .all()
                ):
                    data["settings"][setting.id] = {"context": setting.context, "default": setting.default or "", "id": setting.name, "regex": setting.regex, "type": setting.type, "help": {}, "label": {}} | (
                        {"multiple": setting.multiple} if setting.multiple else {}
                    )

                    for translation in session.query(Settings_translations).with_entities(Settings_translations.language, Settings_translations.label, Settings_translations.help).filter_by(setting_id=setting.id).all():
                        data["settings"][setting.id]["help"][translation.language] = translation.help
                        data["settings"][setting.id]["label"][translation.language] = translation.label

                    if setting.type == "select":
                        data["settings"][setting.id]["select"] = [select.value or "" for select in session.query(Selects).with_entities(Selects.value).filter_by(setting_id=setting.id).all()]

                plugins.append(data)

        return plugins

    def remove_external_plugin(self, plugin_id: str, *, method: str = "core") -> str:
        """Delete an external plugin from the database."""
        with suppress(BaseException), self._db_session() as session:
            db_plugin = session.query(Plugins).with_entities(Plugins.external).filter_by(id=plugin_id).first()

            if db_plugin is None:
                return "not_found"
            elif db_plugin.external is False:
                return "not_external"
            elif method not in (db_plugin.method, "autoconf"):
                return "method_conflict"

            session.query(Plugins).filter(Plugins.id == plugin_id).delete()
            session.commit()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def get_plugins_errors(self) -> int:
        """Get plugins errors."""
        with suppress(BaseException), self._db_session() as session:
            return session.query(Jobs_runs).with_entities(Jobs_runs.success).filter_by(success=False).count()

        if self._exceptions.get(getpid()):
            self._logger.error(self._exceptions[getpid()].pop())
        return 0

    def get_job(self, job_name: str) -> Dict[str, Any]:
        """Get job."""
        with suppress(BaseException), self._db_session() as session:
            job = session.query(Jobs).with_entities(Jobs.name, Jobs.every, Jobs.reload).filter_by(name=job_name).first()

            if job is None:
                return {}

            return {
                "every": job.every,
                "reload": job.reload,
                "history": [
                    {
                        "start_date": job_run.start_date.strftime("%Y/%m/%d, %I:%M:%S %p"),
                        "end_date": job_run.end_date.strftime("%Y/%m/%d, %I:%M:%S %p"),
                        "success": job_run.success,
                    }
                    for job_run in session.query(Jobs_runs).with_entities(Jobs_runs.success, Jobs_runs.start_date, Jobs_runs.end_date).filter_by(job_name=job.name).order_by(Jobs_runs.end_date.desc()).limit(10).all()
                ],
                "cache": [
                    {
                        "service_id": cache.service_id,
                        "file_name": cache.file_name,
                        "last_update": cache.last_update.strftime("%Y/%m/%d, %I:%M:%S %p") if cache.last_update is not None else "Never",
                        "checksum": cache.checksum,
                    }
                    for cache in session.query(Jobs_cache)
                    .with_entities(
                        Jobs_cache.service_id,
                        Jobs_cache.file_name,
                        Jobs_cache.last_update,
                        Jobs_cache.checksum,
                    )
                    .filter_by(job_name=job.name)
                    .all()
                ],
            }

        if self._exceptions.get(getpid()):
            self._logger.error(self._exceptions[getpid()].pop())
        return {}

    def get_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Get jobs."""
        with suppress(BaseException), self._db_session() as session:
            return {
                job.name: {
                    "every": job.every,
                    "reload": job.reload,
                    "history": [
                        {
                            "start_date": job_run.start_date.strftime("%Y/%m/%d, %I:%M:%S %p"),
                            "end_date": job_run.end_date.strftime("%Y/%m/%d, %I:%M:%S %p"),
                            "success": job_run.success,
                        }
                        for job_run in session.query(Jobs_runs).with_entities(Jobs_runs.success, Jobs_runs.start_date, Jobs_runs.end_date).filter_by(job_name=job.name).order_by(Jobs_runs.end_date.desc()).limit(10).all()
                    ],
                    "cache": [
                        {
                            "service_id": cache.service_id,
                            "file_name": cache.file_name,
                            "last_update": cache.last_update.strftime("%Y/%m/%d, %I:%M:%S %p") if cache.last_update else "Never",
                            "checksum": cache.checksum,
                        }
                        for cache in session.query(Jobs_cache).with_entities(Jobs_cache.service_id, Jobs_cache.file_name, Jobs_cache.last_update, Jobs_cache.checksum).filter_by(job_name=job.name).all()
                    ],
                }
                for job in session.query(Jobs).with_entities(Jobs.name, Jobs.every, Jobs.reload).all()
            }

        if self._exceptions.get(getpid()):
            self._logger.error(self._exceptions[getpid()].pop())
        return {}

    def add_job_run(
        self,
        job_name: str,
        success: bool,
        start_date: datetime,
        end_date: Optional[datetime] = None,
    ) -> str:
        """Add a job run."""
        with suppress(BaseException), self._db_session() as session:
            session.add(
                Jobs_runs(
                    job_name=job_name,
                    success=success,
                    start_date=start_date,
                    end_date=end_date or datetime.now(),
                )
            )
            session.commit()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def delete_job_cache(self, job_name: str, file_name: str, *, service_id: Optional[str] = None) -> Union[str, int]:
        deleted = 0
        with suppress(BaseException), self._db_session() as session:
            deleted = (
                session.query(Jobs_cache)
                .filter(
                    Jobs_cache.job_name == job_name,
                    Jobs_cache.service_id == service_id,
                    Jobs_cache.file_name == file_name,
                )
                .delete()
            )
            session.commit()

        return (self._exceptions.get(getpid()) or [deleted]).pop()

    def upsert_job_cache(
        self,
        job_name: str,
        file_name: str,
        data: Optional[bytes] = None,
        *,
        service_id: Optional[str] = None,
        checksum: Optional[str] = None,
    ) -> str:
        """Update the plugin cache in the database"""
        resp = ""
        with suppress(BaseException), self._db_session() as session:
            cache = (
                session.query(Jobs_cache)
                .filter_by(
                    job_name=job_name,
                    service_id=service_id,
                    file_name=file_name,
                )
                .first()
            )

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
                resp = "created"
            else:
                if data:
                    cache.data = data

                if checksum:
                    cache.checksum = checksum

                cache.last_update = datetime.now()
                resp = "updated"
            session.commit()

        return (self._exceptions.get(getpid()) or [resp]).pop()

    def get_job_cache(
        self,
        job_name: str,
        file_name: Optional[str] = None,
        *,
        service_id: Optional[str] = None,
        with_info: bool = False,
        with_data: bool = True,
    ) -> Optional[Any]:
        """Get job cache file."""
        entities = [Jobs_cache.file_name]
        if with_info:
            entities.extend([Jobs_cache.last_update, Jobs_cache.checksum])
        if with_data:
            entities.append(Jobs_cache.data)

        with suppress(BaseException), self._db_session() as session:
            if file_name:
                return session.query(Jobs_cache).with_entities(*entities).filter_by(job_name=job_name, service_id=service_id, file_name=file_name).first()
            if service_id:
                return session.query(Jobs_cache).with_entities(*entities).filter_by(job_name=job_name, service_id=service_id).all()
            return session.query(Jobs_cache).with_entities(*entities).filter_by(job_name=job_name).all()
        return (self._exceptions.get(getpid()) or [None]).pop()

    def get_jobs_cache_files(self) -> List[Dict[str, Any]]:
        """Get jobs cache files."""
        with suppress(BaseException), self._db_session() as session:
            return [
                {
                    "job_name": cache.job_name,
                    "service_id": cache.service_id,
                    "file_name": cache.file_name,
                    "data": "Download file to view content",
                }
                for cache in (
                    session.query(Jobs_cache)
                    .with_entities(
                        Jobs_cache.job_name,
                        Jobs_cache.service_id,
                        Jobs_cache.file_name,
                    )
                    .all()
                )
            ]

        if self._exceptions.get(getpid()):
            self._logger.error(self._exceptions[getpid()].pop())
        return []

    def add_instance(self, hostname: str, port: int, server_name: str, method: str) -> str:
        """Add instance."""
        with suppress(BaseException), self._db_session() as session:
            db_instance = session.query(Instances).with_entities(Instances.hostname).filter_by(hostname=hostname).first()

            if db_instance is not None:
                return "exists"

            try:
                session.add(
                    Instances(
                        hostname=hostname,
                        port=port,
                        server_name=server_name,
                        method=method,
                    )
                )
                session.commit()
            except BaseException:
                session.rollback()
                return f"An error occurred while adding the instance {hostname} (port: {port}, server name: {server_name}).\n{format_exc()}"

        return (self._exceptions.get(getpid()) or [""]).pop()

    def refresh_instances(self, instances: Iterable[Dict[str, Any]], method: str) -> str:
        """Update instances."""
        to_put = []
        with suppress(BaseException), self._db_session() as session:
            session.query(Instances).filter(Instances.method == method).delete()

            for instance in instances:
                to_put.append(Instances(**instance | {"method": method}))

            session.add_all(to_put)
            session.commit()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def upsert_instance(self, hostname: str, port: int, server_name: str, method: str, *, old_hostname: Optional[str] = None) -> str:
        """Update instance."""
        old_hostname = old_hostname or hostname
        ret = ""
        with suppress(BaseException), self._db_session() as session:
            db_instance = session.query(Instances).with_entities(Instances.hostname, Instances.method).filter_by(hostname=old_hostname).first()

            if db_instance is None:
                session.add(
                    Instances(
                        hostname=hostname,
                        port=port,
                        server_name=server_name,
                        method=method,
                    )
                )
                ret = "created"
            elif method not in (db_instance.method, "autoconf"):
                ret = "method_conflict"
            else:
                session.query(Instances).filter_by(hostname=old_hostname).update(
                    {
                        Instances.hostname: hostname,
                        Instances.port: port,
                        Instances.server_name: server_name,
                        Instances.method: method,
                    }
                )
                ret = "updated"
            session.commit()

        return (self._exceptions.get(getpid()) or [ret]).pop()

    def get_instances(self) -> List[Dict[str, Any]]:
        """Get instances."""
        with suppress(BaseException), self._db_session() as session:
            return [
                {
                    "hostname": instance.hostname,
                    "port": instance.port,
                    "server_name": instance.server_name,
                    "last_seen": instance.last_seen,
                    "method": instance.method,
                }
                for instance in (
                    session.query(Instances)
                    .with_entities(
                        Instances.hostname,
                        Instances.port,
                        Instances.server_name,
                        Instances.last_seen,
                        Instances.method,
                    )
                    .all()
                )
            ]

        if self._exceptions.get(getpid()):
            self._logger.error(self._exceptions[getpid()].pop())
        return []

    def get_instance(self, instance_hostname: str) -> Dict[str, Any]:
        """Get an instance."""
        with suppress(BaseException), self._db_session() as session:
            instance = session.query(Instances).filter_by(hostname=instance_hostname).first()

            if not instance:
                return {}

            return {
                "hostname": instance.hostname,
                "port": instance.port,
                "server_name": instance.server_name,
                "method": instance.method,
            }

        if self._exceptions.get(getpid()):
            self._logger.error(self._exceptions[getpid()].pop())
        return {}

    def remove_instance(self, instance_hostname: str, *, method: str = "core") -> str:
        """Remove an instance."""
        with suppress(BaseException), self._db_session() as session:
            db_instance = session.query(Instances).with_entities(Instances.hostname, Instances.method).filter_by(hostname=instance_hostname).first()

            if db_instance is None:
                return "not_found"
            elif method not in (db_instance.method, "autoconf"):
                return "method_conflict"

            session.query(Instances).filter(Instances.hostname == instance_hostname).delete()
            session.commit()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def seen_instance(self, instance_hostname: str) -> str:
        """Update last_seen for an instance."""
        with suppress(BaseException), self._db_session() as session:
            db_instance = session.query(Instances).with_entities(Instances.hostname).filter_by(hostname=instance_hostname).first()

            if db_instance is None:
                return "not_found"

            session.query(Instances).filter(Instances.hostname == instance_hostname).update({Instances.last_seen: datetime.now()})
            session.commit()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def get_plugin_actions(self, plugin: str) -> Optional[Any]:
        """get actions file for the plugin"""
        with suppress(BaseException), self._db_session() as session:
            page = session.query(Plugin_pages).with_entities(Plugin_pages.actions_file).filter_by(plugin_id=plugin).first()

            if not page:
                return None

            return page.actions_file

        if self._exceptions.get(getpid()):
            self._logger.error(self._exceptions[getpid()].pop())

    def get_plugin_template(self, plugin: str) -> Optional[Any]:
        """get template file for the plugin"""
        with suppress(BaseException), self._db_session() as session:
            page = session.query(Plugin_pages).with_entities(Plugin_pages.template_file).filter_by(plugin_id=plugin).first()

            if not page:
                return None

            return page.template_file

        if self._exceptions.get(getpid()):
            self._logger.error(self._exceptions[getpid()].pop())

    def add_action(self, action: Dict[str, Any]) -> str:
        """Add an action to the database."""
        with suppress(BaseException), self._db_session() as session:
            db_action = Actions(
                date=action["date"],
                api_method=action["api_method"],
                method=action["method"],
                title=action["title"],
                description=action["description"].encode(),
                status=action.get("status", "success"),
            )
            session.add(db_action)
            session.commit()

            tags = action.get("tags", [])
            if tags:
                session.refresh(db_action)
                db_tags = [tag.id for tag in session.query(Tags).with_entities(Tags.id).all()]
                for tag in tags:
                    if tag not in db_tags:
                        session.add(Tags(id=tag))
                    session.add(Actions_tags(action_id=db_action.id, tag_id=tag))
                try:
                    session.commit()
                except OperationalError:
                    session.rollback()
                except IntegrityError:
                    session.rollback()
                    for tag in tags:
                        if tag not in db_tags:
                            session.add(Tags(id=tag))
                        session.add(Actions_tags(action_id=db_action.id, tag_id=tag))
                    session.commit()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def get_actions(self) -> List[Dict[str, Any]]:
        """Get actions."""
        with suppress(BaseException), self._db_session() as session:
            return [
                {
                    "date": action.date,
                    "api_method": action.api_method,
                    "method": action.method,
                    "title": action.title,
                    "description": action.description.decode(),
                    "tags": [action_tag.tag_id for action_tag in session.query(Actions_tags).with_entities(Actions_tags.tag_id).filter_by(action_id=action.id).all()],
                }
                for action in (
                    session.query(Actions)
                    .with_entities(
                        Actions.id,
                        Actions.date,
                        Actions.api_method,
                        Actions.method,
                        Actions.title,
                        Actions.description,
                    )
                    .all()
                )
            ]

        if self._exceptions.get(getpid()):
            self._logger.error(self._exceptions[getpid()].pop())
        return []

    def get_ui_user(self) -> Optional[dict]:
        """Get ui user."""
        with suppress(BaseException), self._db_session() as session:
            user = session.query(Users).with_entities(Users.username, Users.password, Users.is_two_factor_enabled, Users.secret_token, Users.method).filter_by(id=1).first()
            if not user:
                return None
            return {
                "username": user.username,
                "password_hash": user.password.encode("utf-8"),
                "is_two_factor_enabled": user.is_two_factor_enabled,
                "secret_token": user.secret_token,
                "method": user.method,
            }

        return (self._exceptions.get(getpid()) or [{}]).pop()

    def create_ui_user(self, username: str, password: bytes, *, secret_token: Optional[str] = None, method: str = "manual") -> str:
        """Create ui user."""
        with suppress(BaseException), self._db_session() as session:
            if self.get_ui_user():
                return "User already exists"

            session.add(Users(id=1, username=username, password=password.decode("utf-8"), secret_token=secret_token, method=method))

            try:
                session.commit()
            except BaseException:
                return format_exc()

        return (self._exceptions.get(getpid()) or [""]).pop()

    def update_ui_user(self, username: str, password: bytes, is_two_factor_enabled: bool = False, secret_token: Optional[str] = None, method: str = "ui") -> str:
        """Update ui user."""
        with suppress(BaseException), self._db_session() as session:
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
            except BaseException:
                return format_exc()

        return (self._exceptions.get(getpid()) or [""]).pop()
