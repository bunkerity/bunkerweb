#!/usr/bin/python3

from contextlib import contextmanager, suppress
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from logging import Logger
from os import _exit, getenv, listdir, sep
from os.path import dirname, join
from pathlib import Path
from re import compile as re_compile
from sys import path as sys_path
from typing import Any, Dict, List, Optional, Tuple
from time import sleep
from traceback import format_exc

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
    Metadata,
)

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("utils",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from jobs import file_hash  # type: ignore

from pymysql import install_as_MySQLdb
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import (
    ArgumentError,
    DatabaseError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.orm import scoped_session, sessionmaker

install_as_MySQLdb()


class Database:
    def __init__(self, logger: Logger, sqlalchemy_string: str = None) -> None:
        """Initialize the database"""
        self.__logger = logger
        self.__sql_session = None
        self.__sql_engine = None

        if not sqlalchemy_string:
            sqlalchemy_string = getenv(
                "DATABASE_URI", "sqlite:////var/lib/bunkerweb/db.sqlite3"
            )

        if sqlalchemy_string.startswith("sqlite"):
            with suppress(FileExistsError):
                Path(dirname(sqlalchemy_string.split("///")[1])).mkdir(
                    parents=True, exist_ok=True
                )
        elif "+" in sqlalchemy_string and "+pymysql" not in sqlalchemy_string:
            splitted = sqlalchemy_string.split("+")
            sqlalchemy_string = f"{splitted[0]}:{':'.join(splitted[1].split(':')[1:])}"

        self.database_uri = sqlalchemy_string
        error = False

        try:
            self.__sql_engine = create_engine(
                sqlalchemy_string,
                future=True,
            )
        except ArgumentError:
            self.__logger.error(f"Invalid database URI: {sqlalchemy_string}")
            error = True
        except SQLAlchemyError:
            self.__logger.error(
                f"Error when trying to create the engine: {format_exc()}"
            )
            error = True
        finally:
            if error:
                _exit(1)

        try:
            assert self.__sql_engine is not None
        except AssertionError:
            self.__logger.error("The database engine is not initialized")
            _exit(1)

        not_connected = True
        retries = 15

        while not_connected:
            try:
                with self.__sql_engine.connect() as conn:
                    conn.execute(text("CREATE TABLE IF NOT EXISTS test (id INT)"))
                    conn.execute(text("DROP TABLE test"))
                not_connected = False
            except (OperationalError, DatabaseError) as e:
                if retries <= 0:
                    self.__logger.error(
                        f"Can't connect to database : {format_exc()}",
                    )
                    _exit(1)

                if "attempt to write a readonly database" in str(e):
                    self.__logger.warning(
                        "The database is read-only, waiting for it to become writable. Retrying in 5 seconds ..."
                    )
                    self.__sql_engine.dispose(close=True)
                    self.__sql_engine = create_engine(
                        sqlalchemy_string,
                        future=True,
                    )
                if "Unknown table" in str(e):
                    not_connected = False
                    continue
                else:
                    self.__logger.warning(
                        "Can't connect to database, retrying in 5 seconds ...",
                    )
                retries -= 1
                sleep(5)
            except BaseException:
                self.__logger.error(
                    f"Error when trying to connect to the database: {format_exc()}"
                )
                exit(1)

        self.__logger.info("Database connection established")

        self.__session = sessionmaker()
        self.__sql_session = scoped_session(self.__session)
        self.__sql_session.remove()
        self.__sql_session.configure(
            bind=self.__sql_engine, autoflush=False, expire_on_commit=False
        )
        self.suffix_rx = re_compile(r"_\d+$")

    def get_database_uri(self) -> str:
        return self.database_uri

    def __del__(self) -> None:
        """Close the database"""
        if self.__sql_session:
            self.__sql_session.remove()

        if self.__sql_engine:
            self.__sql_engine.dispose()

    @contextmanager
    def __db_session(self):
        try:
            assert self.__sql_session is not None
        except AssertionError:
            self.__logger.error("The database session is not initialized")
            _exit(1)

        session = self.__sql_session()
        session.expire_on_commit = False

        try:
            yield session
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    def set_autoconf_load(self, value: bool = True) -> str:
        """Set the autoconf_loaded value"""
        with self.__db_session() as session:
            try:
                metadata = session.query(Metadata).get(1)

                if not metadata:
                    return "The metadata are not set yet, try again"

                metadata.autoconf_loaded = value
                session.commit()
            except BaseException:
                return format_exc()

        return ""

    def is_autoconf_loaded(self) -> bool:
        """Check if the autoconf is loaded"""
        with self.__db_session() as session:
            try:
                metadata = (
                    session.query(Metadata)
                    .with_entities(Metadata.autoconf_loaded)
                    .filter_by(id=1)
                    .first()
                )
                return metadata is not None and metadata.autoconf_loaded
            except (ProgrammingError, OperationalError):
                return False

    def is_first_config_saved(self) -> bool:
        """Check if the first configuration has been saved"""
        with self.__db_session() as session:
            try:
                metadata = (
                    session.query(Metadata)
                    .with_entities(Metadata.first_config_saved)
                    .filter_by(id=1)
                    .first()
                )
                return metadata is not None and metadata.first_config_saved
            except (ProgrammingError, OperationalError):
                return False

    def is_initialized(self) -> bool:
        """Check if the database is initialized"""
        with self.__db_session() as session:
            try:
                metadata = (
                    session.query(Metadata)
                    .with_entities(Metadata.is_initialized)
                    .filter_by(id=1)
                    .first()
                )
                return metadata is not None and metadata.is_initialized
            except (ProgrammingError, OperationalError, DatabaseError):
                return False

    def initialize_db(self, version: str, integration: str = "Unknown") -> str:
        """Initialize the database"""
        with self.__db_session() as session:
            try:
                session.add(
                    Metadata(
                        is_initialized=True,
                        first_config_saved=False,
                        version=version,
                        integration=integration,
                    )
                )
                session.commit()
            except BaseException:
                return format_exc()

        return ""

    def init_tables(self, default_plugins: List[dict]) -> Tuple[bool, str]:
        """Initialize the database tables and return the result"""
        inspector = inspect(self.__sql_engine)
        if len(Base.metadata.tables.keys()) <= len(inspector.get_table_names()):
            has_all_tables = True

            for table in Base.metadata.tables:
                if not inspector.has_table(table):
                    has_all_tables = False
                    break

            if has_all_tables:
                return False, ""

        Base.metadata.create_all(self.__sql_engine, checkfirst=True)

        to_put = []
        with self.__db_session() as session:
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
                            "name": "General",
                            "description": "The general settings for the server",
                            "version": "0.1",
                            "stream": "partial",
                            "external": False,
                        }
                    else:
                        settings = plugin.pop("settings", {})
                        jobs = plugin.pop("jobs", [])
                        page = plugin.pop("page", False)

                    to_put.append(
                        Plugins(
                            id=plugin["id"],
                            name=plugin["name"],
                            description=plugin["description"],
                            version=plugin["version"],
                            stream=plugin["stream"],
                            external=plugin.get("external", False),
                            method=plugin.get("method"),
                        )
                    )

                    for setting, value in settings.items():
                        value.update(
                            {
                                "plugin_id": plugin["id"],
                                "name": value["id"],
                                "id": setting,
                            }
                        )

                        for select in value.pop("select", []):
                            to_put.append(Selects(setting_id=value["id"], value=select))

                        to_put.append(Settings(**value))

                    for job in jobs:
                        job["file_name"] = job.pop("file")
                        to_put.append(Jobs(plugin_id=plugin["id"], **job))

                    if page:
                        core_ui_path = Path(
                            sep, "usr", "share", "bunkerweb", "core", plugin["id"], "ui"
                        )
                        path_ui = (
                            core_ui_path
                            if core_ui_path.exists()
                            else Path(
                                sep, "etc", "bunkerweb", "plugins", plugin["id"], "ui"
                            )
                        )

                        if path_ui.exists():
                            if {"template.html", "actions.py"}.issubset(
                                listdir(str(path_ui))
                            ):
                                template = path_ui.joinpath(
                                    "template.html"
                                ).read_bytes()
                                actions = path_ui.joinpath("actions.py").read_bytes()

                                to_put.append(
                                    Plugin_pages(
                                        plugin_id=plugin["id"],
                                        template_file=template,
                                        template_checksum=sha256(template).hexdigest(),
                                        actions_file=actions,
                                        actions_checksum=sha256(actions).hexdigest(),
                                    )
                                )

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException:
                return False, format_exc()

        return True, ""

    def save_config(self, config: Dict[str, Any], method: str) -> str:
        """Save the config in the database"""
        to_put = []
        with self.__db_session() as session:
            # Delete all the old config
            session.query(Global_values).filter(Global_values.method == method).delete()
            session.query(Services_settings).filter(
                Services_settings.method == method
            ).delete()

            if config:
                if config.get("MULTISITE", "no") == "yes":
                    global_values = []
                    db_services = (
                        session.query(Services)
                        .with_entities(Services.id, Services.method)
                        .all()
                    )
                    db_ids = [service.id for service in db_services]
                    services = config.pop("SERVER_NAME", [])

                    if isinstance(services, str):
                        services = services.split(" ")

                    if db_services:
                        missing_ids = [
                            service.id
                            for service in db_services
                            if (service.method == method) and service.id not in services
                        ]

                        if missing_ids:
                            # Remove services that are no longer in the list
                            session.query(Services).filter(
                                Services.id.in_(missing_ids)
                            ).delete()

                    for key, value in deepcopy(config).items():
                        suffix = 0
                        original_key = deepcopy(key)
                        if self.suffix_rx.search(key):
                            suffix = int(key.split("_")[-1])
                            key = key[: -len(str(suffix)) - 1]

                        setting = (
                            session.query(Settings)
                            .with_entities(Settings.default)
                            .filter_by(id=key)
                            .first()
                        )

                        if not setting and services:
                            try:
                                server_name = next(
                                    service
                                    for service in services
                                    if key.startswith(f"{service}_")
                                )
                            except StopIteration:
                                continue

                            if server_name not in db_ids:
                                to_put.append(Services(id=server_name, method=method))
                                db_ids.append(server_name)

                            key = key.replace(f"{server_name}_", "")
                            setting = (
                                session.query(Settings)
                                .with_entities(Settings.default)
                                .filter_by(id=key)
                                .first()
                            )

                            if not setting:
                                continue

                            service_setting = (
                                session.query(Services_settings)
                                .with_entities(
                                    Services_settings.value, Services_settings.method
                                )
                                .filter_by(
                                    service_id=server_name,
                                    setting_id=key,
                                    suffix=suffix,
                                )
                                .first()
                            )

                            if not service_setting:
                                if key != "SERVER_NAME" and (
                                    (key not in config and value == setting.default)
                                    or (key in config and value == config[key])
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
                            elif (
                                method in (service_setting.method, "autoconf")
                                and service_setting.value != value
                            ):
                                if key != "SERVER_NAME" and (
                                    (key not in config and value == setting.default)
                                    or (key in config and value == config[key])
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
                                .with_entities(
                                    Global_values.value, Global_values.method
                                )
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
                            elif (
                                method in (global_value.method, "autoconf")
                                and global_value.value != value
                            ):
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
                        "SERVER_NAME" in config
                        and config["SERVER_NAME"] != ""
                        and not (
                            session.query(Services)
                            .with_entities(Services.id)
                            .filter_by(id=config["SERVER_NAME"].split(" ")[0])
                            .first()
                        )
                    ):
                        to_put.append(
                            Services(
                                id=config["SERVER_NAME"].split(" ")[0], method=method
                            )
                        )

                    config.pop("SERVER_NAME")

                    for key, value in config.items():
                        suffix = 0
                        if self.suffix_rx.search(key):
                            suffix = int(key.split("_")[-1])
                            key = key[: -len(str(suffix)) - 1]

                        setting = (
                            session.query(Settings)
                            .with_entities(Settings.default)
                            .filter_by(id=key)
                            .first()
                        )

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
                        elif (
                            global_value.method == method
                            and value != global_value.value
                        ):
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

            with suppress(ProgrammingError, OperationalError):
                metadata = session.query(Metadata).get(1)
                if metadata is not None and not metadata.first_config_saved:
                    metadata.first_config_saved = True

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException:
                return format_exc()

        return ""

    def save_custom_configs(
        self, custom_configs: List[Dict[str, Tuple[str, List[str]]]], method: str
    ) -> str:
        """Save the custom configs in the database"""
        message = ""
        with self.__db_session() as session:
            # Delete all the old config
            session.query(Custom_configs).filter(
                Custom_configs.method == method
            ).delete()

            to_put = []
            endl = "\n"
            for custom_config in custom_configs:
                config = {
                    "data": custom_config["value"].encode("utf-8")
                    if isinstance(custom_config["value"], str)
                    else custom_config["value"],
                    "method": method,
                }
                config["checksum"] = sha256(config["data"]).hexdigest()

                if custom_config["exploded"][0]:
                    if (
                        not session.query(Services)
                        .with_entities(Services.id)
                        .filter_by(id=custom_config["exploded"][0])
                        .first()
                    ):
                        message += f"{endl if message else ''}Service {custom_config['exploded'][0]} not found, please check your config"

                    config.update(
                        {
                            "service_id": custom_config["exploded"][0],
                            "type": custom_config["exploded"][1]
                            .replace("-", "_")
                            .lower(),
                            "name": custom_config["exploded"][2],
                        }
                    )
                else:
                    config.update(
                        {
                            "type": custom_config["exploded"][1]
                            .replace("-", "_")
                            .lower(),
                            "name": custom_config["exploded"][2],
                        }
                    )

                custom_conf = (
                    session.query(Custom_configs)
                    .with_entities(Custom_configs.checksum, Custom_configs.method)
                    .filter_by(
                        service_id=config.get("service_id", None),
                        type=config["type"],
                        name=config["name"],
                    )
                    .first()
                )

                if not custom_conf:
                    to_put.append(Custom_configs(**config))
                elif config["checksum"] != custom_conf.checksum and method in (
                    custom_conf.method,
                    "autoconf",
                ):
                    session.query(Custom_configs).filter(
                        Custom_configs.service_id == config.get("service_id", None),
                        Custom_configs.type == config["type"],
                        Custom_configs.name == config["name"],
                    ).update(
                        {
                            Custom_configs.data: config["data"],
                            Custom_configs.checksum: config["checksum"],
                        }
                        | (
                            {Custom_configs.method: "autoconf"}
                            if method == "autoconf"
                            else {}
                        )
                    )

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException:
                return f"{f'{message}{endl}' if message else ''}{format_exc()}"

        return message

    def get_config(self, methods: bool = False) -> Dict[str, Any]:
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
                .all()
            ):
                default = setting.default or ""
                config[setting.id] = (
                    default
                    if methods is False
                    else {"value": default, "global": True, "method": "default"}
                )

                global_values = (
                    session.query(Global_values)
                    .with_entities(
                        Global_values.value, Global_values.suffix, Global_values.method
                    )
                    .filter_by(setting_id=setting.id)
                    .all()
                )

                for global_value in global_values:
                    config[
                        setting.id
                        + (
                            f"_{global_value.suffix}"
                            if setting.multiple and global_value.suffix > 0
                            else ""
                        )
                    ] = (
                        global_value.value
                        if methods is False
                        else {
                            "value": global_value.value,
                            "global": True,
                            "method": global_value.method,
                        }
                    )

                if setting.context == "multisite":
                    multisite.append(setting.id)

            for service in session.query(Services).with_entities(Services.id).all():
                checked_settings = []
                for key, value in deepcopy(config).items():
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
                        config[
                            f"{service.id}_{key}"
                            + (
                                f"_{service_setting.suffix}"
                                if service_setting.suffix > 0
                                else ""
                            )
                        ] = (
                            service_setting.value
                            if methods is False
                            else {
                                "value": service_setting.value,
                                "global": False,
                                "method": service_setting.method,
                            }
                        )

            servers = " ".join(service.id for service in session.query(Services).all())
            config["SERVER_NAME"] = (
                servers
                if methods is False
                else {"value": servers, "global": True, "method": "default"}
            )

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

    def get_services_settings(self, methods: bool = False) -> List[Dict[str, Any]]:
        """Get the services' configs from the database"""
        services = []
        config = self.get_config(methods=methods)
        with self.__db_session() as session:
            service_names = [
                service.id
                for service in session.query(Services).with_entities(Services.id).all()
            ]
            for service in service_names:
                tmp_config = deepcopy(config)

                for key, value in deepcopy(tmp_config).items():
                    if key.startswith(f"{service}_"):
                        tmp_config[key.replace(f"{service}_", "")] = tmp_config.pop(key)
                    elif any(key.startswith(f"{s}_") for s in service_names):
                        tmp_config.pop(key)
                    else:
                        tmp_config[key] = (
                            {
                                "value": value["value"],
                                "global": True,
                                "method": "default",
                            }
                            if methods is True
                            else value
                        )

                services.append(tmp_config)

        return services

    def update_job(self, plugin_id: str, job_name: str, success: bool) -> str:
        """Update the job last_run in the database"""
        with self.__db_session() as session:
            job = (
                session.query(Jobs)
                .filter_by(plugin_id=plugin_id, name=job_name)
                .first()
            )

            if not job:
                return "Job not found"

            job.last_run = datetime.now()
            job.success = success

            try:
                session.commit()
            except BaseException:
                return format_exc()

        return ""

    def delete_job_cache(self, job_name: str, file_name: str):
        with self.__db_session() as session:
            session.query(Jobs_cache).filter_by(
                job_name=job_name, file_name=file_name
            ).delete()

    def update_job_cache(
        self,
        job_name: str,
        service_id: Optional[str],
        file_name: str,
        data: bytes,
        *,
        checksum: Optional[str] = None,
    ) -> str:
        """Update the plugin cache in the database"""
        with self.__db_session() as session:
            cache = (
                session.query(Jobs_cache)
                .filter_by(
                    job_name=job_name, service_id=service_id, file_name=file_name
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
            else:
                cache.data = data
                cache.last_update = datetime.now()
                cache.checksum = checksum

            try:
                session.commit()
            except BaseException:
                return format_exc()

        return ""

    def update_external_plugins(
        self, plugins: List[Dict[str, Any]], *, delete_missing: bool = True
    ) -> str:
        """Update external plugins from the database"""
        to_put = []
        with self.__db_session() as session:
            db_plugins = (
                session.query(Plugins)
                .with_entities(Plugins.id)
                .filter_by(external=True)
                .all()
            )

            db_ids = []
            if delete_missing and db_plugins:
                db_ids = [plugin.id for plugin in db_plugins]
                ids = [plugin["id"] for plugin in plugins]
                missing_ids = [plugin for plugin in db_ids if plugin not in ids]

                if missing_ids:
                    # Remove plugins that are no longer in the list
                    session.query(Plugins).filter(Plugins.id.in_(missing_ids)).delete()

            for plugin in plugins:
                settings = plugin.pop("settings", {})
                jobs = plugin.pop("jobs", [])
                page = plugin.pop("page", False)
                plugin["external"] = True
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
                        Plugins.external,
                    )
                    .filter_by(id=plugin["id"])
                    .first()
                )

                if db_plugin is not None:
                    if db_plugin.external is False:
                        self.__logger.warning(
                            f"Plugin \"{plugin['id']}\" is not external, skipping update (updating a non-external plugin is forbidden for security reasons)",
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
                        updates[Plugins.data] = plugin["data"]

                    if plugin.get("checksum") != db_plugin.checksum:
                        updates[Plugins.checksum] = plugin["checksum"]

                    if updates:
                        session.query(Plugins).filter(
                            Plugins.id == plugin["id"]
                        ).update(updates)

                    db_plugin_settings = (
                        session.query(Settings)
                        .with_entities(Settings.id)
                        .filter_by(plugin_id=plugin["id"])
                        .all()
                    )
                    db_ids = [setting.id for setting in db_plugin_settings]
                    setting_ids = [setting["id"] for setting in settings.values()]
                    missing_ids = [
                        setting for setting in db_ids if setting not in setting_ids
                    ]

                    if missing_ids:
                        # Remove settings that are no longer in the list
                        session.query(Settings).filter(
                            Settings.id.in_(missing_ids)
                        ).delete()

                    for setting, value in settings.items():
                        value.update(
                            {
                                "plugin_id": plugin["id"],
                                "name": value["id"],
                                "id": setting,
                            }
                        )
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
                            )
                            .filter_by(id=setting)
                            .first()
                        )

                        if setting not in db_ids or not db_setting:
                            for select in value.pop("select", []):
                                to_put.append(
                                    Selects(setting_id=value["id"], value=select)
                                )

                            to_put.append(
                                Settings(
                                    **value,
                                )
                            )
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

                            if value["multiple"] != db_setting.multiple:
                                updates[Settings.multiple] = value["multiple"]

                            if updates:
                                session.query(Settings).filter(
                                    Settings.id == setting
                                ).update(updates)

                            db_selects = (
                                session.query(Selects)
                                .with_entities(Selects.value)
                                .filter_by(setting_id=setting)
                                .all()
                            )
                            db_values = [select.value for select in db_selects]
                            select_values = [
                                select["value"] for select in value.get("select", [])
                            ]
                            missing_values = [
                                select
                                for select in db_values
                                if select not in select_values
                            ]

                            if missing_values:
                                # Remove selects that are no longer in the list
                                session.query(Selects).filter(
                                    Selects.value.in_(missing_values)
                                ).delete()

                            for select in value.get("select", []):
                                if select not in db_values:
                                    to_put.append(
                                        Selects(setting_id=setting, value=select)
                                    )

                    db_jobs = (
                        session.query(Jobs)
                        .with_entities(Jobs.name)
                        .filter_by(plugin_id=plugin["id"])
                        .all()
                    )
                    db_names = [job.name for job in db_jobs]
                    job_names = [job["name"] for job in jobs]
                    missing_names = [job for job in db_names if job not in job_names]

                    if missing_names:
                        # Remove jobs that are no longer in the list
                        session.query(Jobs).filter(
                            Jobs.name.in_(missing_names)
                        ).delete()

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
                            to_put.append(
                                Jobs(
                                    plugin_id=plugin["id"],
                                    **job,
                                )
                            )
                        else:
                            updates = {}

                            if job["file"] != db_job.file_name:
                                updates[Jobs.file_name] = job["file"]

                            if job["every"] != db_job.every:
                                updates[Jobs.every] = job["every"]

                            if job.get("reload", None) != db_job.reload:
                                updates[Jobs.reload] = job.get("reload", False)

                            if updates:
                                updates[Jobs.last_run] = None
                                session.query(Jobs_cache).filter(
                                    Jobs_cache.job_name == job["name"]
                                ).delete()
                                session.query(Jobs).filter(
                                    Jobs.name == job["name"]
                                ).update(updates)

                    tmp_ui_path = Path(
                        sep, "var", "tmp", "bunkerweb", "ui", plugin["id"], "ui"
                    )
                    path_ui = (
                        tmp_ui_path
                        if tmp_ui_path.exists()
                        else Path(
                            sep, "etc", "bunkerweb", "plugins", plugin["id"], "ui"
                        )
                    )

                    if path_ui.exists():
                        if {"template.html", "actions.py"}.issubset(
                            listdir(str(path_ui))
                        ):
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
                                template = path_ui.joinpath(
                                    "template.html"
                                ).read_bytes()
                                actions = path_ui.joinpath("actions.py").read_bytes()

                                to_put.append(
                                    Plugin_pages(
                                        plugin_id=plugin["id"],
                                        template_file=template,
                                        template_checksum=sha256(template).hexdigest(),
                                        actions_file=actions,
                                        actions_checksum=sha256(actions).hexdigest(),
                                    )
                                )
                            else:
                                updates = {}
                                template_path = path_ui.joinpath("template.html")
                                actions_path = path_ui.joinpath("actions.py")
                                template_checksum = file_hash(str(template_path))
                                actions_checksum = file_hash(str(actions_path))

                                if (
                                    template_checksum
                                    != db_plugin_page.template_checksum
                                ):
                                    updates.update(
                                        {
                                            Plugin_pages.template_file: template_path.read_bytes(),
                                            Plugin_pages.template_checksum: template_checksum,
                                        }
                                    )

                                if actions_checksum != db_plugin_page.actions_checksum:
                                    updates.update(
                                        {
                                            Plugin_pages.actions_file: actions_path.read_bytes(),
                                            Plugin_pages.actions_checksum: actions_checksum,
                                        }
                                    )

                                if updates:
                                    session.query(Plugin_pages).filter(
                                        Plugin_pages.plugin_id == plugin["id"]
                                    ).update(updates)

                    continue

                to_put.append(
                    Plugins(
                        id=plugin["id"],
                        name=plugin["name"],
                        description=plugin["description"],
                        version=plugin["version"],
                        stream=plugin["stream"],
                        external=True,
                        method=plugin["method"],
                        data=plugin.get("data"),
                        checksum=plugin.get("checksum"),
                    )
                )

                for setting, value in settings.items():
                    db_setting = session.query(Settings).filter_by(id=setting).first()

                    if db_setting is not None:
                        self.__logger.warning(
                            f"A setting with id {setting} already exists, therefore it will not be added."
                        )
                        continue

                    value.update(
                        {
                            "plugin_id": plugin["id"],
                            "name": value["id"],
                            "id": setting,
                        }
                    )

                    for select in value.pop("select", []):
                        to_put.append(Selects(setting_id=value["id"], value=select))

                    to_put.append(
                        Settings(
                            **value,
                        )
                    )

                for job in jobs:
                    db_job = (
                        session.query(Jobs)
                        .with_entities(Jobs.file_name, Jobs.every, Jobs.reload)
                        .filter_by(name=job["name"], plugin_id=plugin["id"])
                        .first()
                    )

                    if db_job is not None:
                        self.__logger.warning(
                            f"A job with the name {job['name']} already exists in the database, therefore it will not be added."
                        )
                        continue

                    job["file_name"] = job.pop("file")
                    job["reload"] = job.get("reload", False)
                    to_put.append(Jobs(plugin_id=plugin["id"], **job))

                if page:
                    tmp_ui_path = Path(
                        sep, "var", "tmp", "bunkerweb", "ui", plugin["id"], "ui"
                    )
                    path_ui = (
                        tmp_ui_path
                        if tmp_ui_path.exists()
                        else Path(
                            sep, "etc", "bunkerweb", "plugins", plugin["id"], "ui"
                        )
                    )

                    if path_ui.exists():
                        if {"template.html", "actions.py"}.issubset(
                            listdir(str(path_ui))
                        ):
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
                                template = path_ui.joinpath(
                                    "template.html"
                                ).read_bytes()
                                actions = path_ui.joinpath("actions.py").read_bytes()

                                to_put.append(
                                    Plugin_pages(
                                        plugin_id=plugin["id"],
                                        template_file=template,
                                        template_checksum=sha256(template).hexdigest(),
                                        actions_file=actions,
                                        actions_checksum=sha256(actions).hexdigest(),
                                    )
                                )
                            else:
                                updates = {}
                                template_path = path_ui.joinpath("template.html")
                                actions_path = path_ui.joinpath("actions.py")
                                template_checksum = file_hash(str(template_path))
                                actions_checksum = file_hash(str(actions_path))

                                if (
                                    template_checksum
                                    != db_plugin_page.template_checksum
                                ):
                                    updates.update(
                                        {
                                            Plugin_pages.template_file: template_path.read_bytes(),
                                            Plugin_pages.template_checksum: template_checksum,
                                        }
                                    )

                                if actions_checksum != db_plugin_page.actions_checksum:
                                    updates.update(
                                        {
                                            Plugin_pages.actions_file: actions_path.read_bytes(),
                                            Plugin_pages.actions_checksum: actions_checksum,
                                        }
                                    )

                                if updates:
                                    session.query(Plugin_pages).filter(
                                        Plugin_pages.plugin_id == plugin["id"]
                                    ).update(updates)
            try:
                session.add_all(to_put)
                session.commit()
            except BaseException:
                return format_exc()

        return ""

    def get_plugins(
        self, *, external: bool = False, with_data: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all plugins from the database."""
        plugins = []
        with self.__db_session() as session:
            for plugin in (
                session.query(Plugins)
                .with_entities(
                    Plugins.id,
                    Plugins.stream,
                    Plugins.name,
                    Plugins.description,
                    Plugins.version,
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
                    Plugins.stream,
                    Plugins.name,
                    Plugins.description,
                    Plugins.version,
                    Plugins.external,
                    Plugins.method,
                )
                .all()
            ):
                if external and not plugin.external:
                    continue

                page = (
                    session.query(Plugin_pages)
                    .with_entities(Plugin_pages.id)
                    .filter_by(plugin_id=plugin.id)
                    .first()
                )
                data = {
                    "id": plugin.id,
                    "stream": plugin.stream,
                    "name": plugin.name,
                    "description": plugin.description,
                    "version": plugin.version,
                    "external": plugin.external,
                    "method": plugin.method,
                    "page": page is not None,
                    "settings": {},
                } | (
                    {"data": plugin.data, "checksum": plugin.checksum}
                    if with_data
                    else {}
                )

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
                    .all()
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
                            select.value
                            for select in session.query(Selects)
                            .with_entities(Selects.value)
                            .filter_by(setting_id=setting.id)
                            .all()
                        ]

                plugins.append(data)

        return plugins

    def get_plugins_errors(self) -> int:
        """Get plugins errors."""
        with self.__db_session() as session:
            return session.query(Jobs).filter(Jobs.success == False).count()

    def get_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Get jobs."""
        with self.__db_session() as session:
            return {
                job.name: {
                    "every": job.every,
                    "reload": job.reload,
                    "success": job.success,
                    "last_run": job.last_run.strftime("%Y/%m/%d, %I:%M:%S %p")
                    if job.last_run is not None
                    else "Never",
                    "cache": [
                        {
                            "service_id": cache.service_id,
                            "file_name": cache.file_name,
                            "last_update": cache.last_update.strftime(
                                "%Y/%m/%d, %I:%M:%S %p"
                            )
                            if cache.last_update is not None
                            else "Never",
                        }
                        for cache in session.query(Jobs_cache)
                        .with_entities(
                            Jobs_cache.service_id,
                            Jobs_cache.file_name,
                            Jobs_cache.last_update,
                        )
                        .filter_by(job_name=job.name)
                        .all()
                    ],
                }
                for job in (
                    session.query(Jobs)
                    .with_entities(
                        Jobs.name,
                        Jobs.every,
                        Jobs.reload,
                        Jobs.success,
                        Jobs.last_run,
                    )
                    .all()
                )
            }

    def get_job_cache_file(
        self,
        job_name: str,
        file_name: str,
        *,
        with_info: bool = False,
        with_data: bool = True,
    ) -> Optional[Any]:
        """Get job cache file."""
        entities = []
        if with_info:
            entities.extend([Jobs_cache.last_update, Jobs_cache.checksum])
        if with_data:
            entities.append(Jobs_cache.data)

        with self.__db_session() as session:
            return (
                session.query(Jobs_cache)
                .with_entities(*entities)
                .filter_by(job_name=job_name, file_name=file_name)
                .first()
            )

    def get_jobs_cache_files(self) -> List[Dict[str, Any]]:
        """Get jobs cache files."""
        with self.__db_session() as session:
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

    def add_instance(self, hostname: str, port: int, server_name: str) -> str:
        """Add instance."""
        with self.__db_session() as session:
            db_instance = (
                session.query(Instances)
                .with_entities(Instances.hostname)
                .filter_by(hostname=hostname)
                .first()
            )

            if db_instance is not None:
                return f"Instance {hostname} already exists, will not be added."

            session.add(
                Instances(hostname=hostname, port=port, server_name=server_name)
            )

            try:
                session.commit()
            except BaseException:
                return f"An error occurred while adding the instance {hostname} (port: {port}, server name: {server_name}).\n{format_exc()}"

        return ""

    def update_instances(self, instances: List[Dict[str, Any]]) -> str:
        """Update instances."""
        to_put = []
        with self.__db_session() as session:
            session.query(Instances).delete()

            for instance in instances:
                to_put.append(
                    Instances(
                        hostname=instance["hostname"],
                        port=instance["env"].get("API_HTTP_PORT", 5000),
                        server_name=instance["env"].get("API_SERVER_NAME", "bwapi"),
                    )
                )

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException:
                return format_exc()

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
                for instance in (
                    session.query(Instances)
                    .with_entities(
                        Instances.hostname, Instances.port, Instances.server_name
                    )
                    .all()
                )
            ]

    def get_plugin_actions(self, plugin: str) -> Optional[Any]:
        """get actions file for the plugin"""
        with self.__db_session() as session:
            page = (
                session.query(Plugin_pages)
                .with_entities(Plugin_pages.actions_file)
                .filter_by(plugin_id=plugin)
                .first()
            )

            if not page:
                return None

            return page.actions_file

    def get_plugin_template(self, plugin: str) -> Optional[Any]:
        """get template file for the plugin"""
        with self.__db_session() as session:
            page = (
                session.query(Plugin_pages)
                .with_entities(Plugin_pages.template_file)
                .filter_by(plugin_id=plugin)
                .first()
            )

            if not page:
                return None

            return page.template_file
