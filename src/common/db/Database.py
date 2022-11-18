from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from logging import (
    NOTSET,
    Logger,
    _levelToName,
    _nameToLevel,
)
import oracledb
from os import _exit, getenv, listdir, makedirs
from os.path import dirname, exists
from pymysql import install_as_MySQLdb
from re import search
from sys import modules, path as sys_path
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import (
    ArgumentError,
    DatabaseError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.orm import scoped_session, sessionmaker
from time import sleep
from traceback import format_exc

from model import (
    Base,
    Instances,
    Logs,
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

if "/usr/share/bunkerweb/utils" not in sys_path:
    sys_path.append("/usr/share/bunkerweb/utils")

from jobs import file_hash

oracledb.version = "8.3.0"
modules["cx_Oracle"] = oracledb

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
            makedirs(dirname(sqlalchemy_string.split("///")[1]), exist_ok=True)
        elif "+" in sqlalchemy_string and "+pymysql" not in sqlalchemy_string:
            splitted = sqlalchemy_string.split("+")
            sqlalchemy_string = f"{splitted[0]}:{':'.join(splitted[1].split(':')[1:])}"

        self.database_uri = sqlalchemy_string

        try:
            self.__sql_engine = create_engine(
                sqlalchemy_string,
                encoding="utf-8",
                future=True,
            )
        except ArgumentError:
            self.__logger.error(f"Invalid database URI: {sqlalchemy_string}")
        except SQLAlchemyError:
            self.__logger.error(
                f"Error when trying to create the engine: {format_exc()}"
            )

        not_connected = True
        retries = 5

        while not_connected:
            try:
                self.__sql_engine.connect()
                not_connected = False
            except (OperationalError, DatabaseError):
                if retries <= 0:
                    self.__logger.error(
                        f"Can't connect to database : {format_exc()}",
                    )
                    _exit(1)
                else:
                    self.__logger.warning(
                        "Can't connect to database, retrying in 5 seconds ...",
                    )
                    retries -= 1
                    sleep(5)
            except SQLAlchemyError:
                self.__logger.error(
                    f"Error when trying to connect to the database: {format_exc()}"
                )

        self.__session = sessionmaker()
        self.__sql_session = scoped_session(self.__session)
        self.__sql_session.remove()
        self.__sql_session.configure(
            bind=self.__sql_engine, autoflush=False, expire_on_commit=False
        )

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

                if metadata is None:
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

    def init_tables(self, default_settings: List[Dict[str, str]]) -> Tuple[bool, str]:
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
            for plugins in default_settings:
                if not isinstance(plugins, list):
                    plugins = [plugins]

                for plugin in plugins:
                    settings = {}
                    jobs = []
                    if "id" not in plugin:
                        settings = plugin
                        plugin = {
                            "id": "default",
                            "order": 999,
                            "name": "Default",
                            "description": "Default settings",
                            "version": "0.1",
                        }
                    else:
                        settings = plugin.pop("settings", {})
                        jobs = plugin.pop("jobs", [])

                    to_put.append(Plugins(**plugin))

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

                        to_put.append(
                            Settings(
                                **value,
                            )
                        )

                    for job in jobs:
                        job["file_name"] = job.pop("file")
                        to_put.append(Jobs(plugin_id=plugin["id"], **job))

                    if exists(f"/usr/share/bunkerweb/core/{plugin['id']}/ui"):
                        if {"template.html", "actions.py"}.issubset(
                            listdir(f"/usr/share/bunkerweb/core/{plugin['id']}/ui")
                        ):
                            with open(
                                f"/usr/share/bunkerweb/core/{plugin['id']}/ui/template.html",
                                "r",
                            ) as file:
                                template = file.read().encode("utf-8")
                            with open(
                                f"/usr/share/bunkerweb/core/{plugin['id']}/ui/actions.py",
                                "r",
                            ) as file:
                                actions = file.read().encode("utf-8")

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
                        .with_entities(Services.id)
                        .filter_by(method=method)
                        .all()
                    )
                    services = config.get("SERVER_NAME", "").split(" ")

                    if db_services:
                        db_services = [service.id for service in db_services]
                        missing_ids = [
                            service
                            for service in db_services
                            if service not in services
                        ]

                        if missing_ids:
                            # Remove plugins that are no longer in the list
                            session.query(Services).filter(
                                Services.id.in_(missing_ids)
                            ).delete()

                    for key, value in deepcopy(config).items():
                        suffix = 0
                        if search(r"_\d+$", key):
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

                            if server_name not in db_services:
                                to_put.append(Services(id=server_name, method=method))
                                db_services.append(server_name)

                            key = key.replace(f"{server_name}_", "")
                            setting = (
                                session.query(Settings)
                                .with_entities(Settings.default)
                                .filter_by(id=key)
                                .first()
                            )
                            service_setting = (
                                session.query(Services_settings)
                                .with_entities(Services_settings.value)
                                .filter_by(
                                    service_id=server_name,
                                    setting_id=key,
                                    suffix=suffix,
                                )
                                .first()
                            )

                            if service_setting is None:
                                if key != "SERVER_NAME" and (
                                    value == setting.default
                                    or (value == "" and setting.default is None)
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
                                method == "autoconf"
                                and value != setting.default
                                and service_setting.value != value
                            ):
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
                        elif key not in global_values:
                            global_values.append(key)
                            global_value = (
                                session.query(Global_values)
                                .with_entities(Global_values.value)
                                .filter_by(
                                    setting_id=key,
                                    suffix=suffix,
                                )
                                .first()
                            )

                            if global_value is None:
                                if (
                                    not setting
                                    or value == setting.default
                                    or (value == "" and setting.default is None)
                                ):
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
                                setting
                                and method == "autoconf"
                                and value != setting.default
                                and global_value.value != value
                            ):
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
                    if "SERVER_NAME" in config and config["SERVER_NAME"] != "":
                        to_put.append(
                            Services(
                                id=config["SERVER_NAME"].split(" ")[0], method=method
                            )
                        )

                    for key, value in config.items():
                        suffix = 0
                        if search(r"_\d+$", key):
                            suffix = int(key.split("_")[-1])
                            key = key[: -len(str(suffix)) - 1]

                        setting = (
                            session.query(Settings)
                            .with_entities(Settings.default)
                            .filter_by(id=key)
                            .first()
                        )

                        if (
                            not setting
                            or value == setting.default
                            or (value == "" and setting.default is None)
                        ):
                            continue

                        global_value = (
                            session.query(Global_values)
                            .with_entities(Global_values.method)
                            .filter_by(setting_id=key, suffix=suffix)
                            .first()
                        )

                        if global_value is None:
                            to_put.append(
                                Global_values(
                                    setting_id=key,
                                    value=value,
                                    suffix=suffix,
                                    method=method,
                                )
                            )
                        elif global_value.method == method:
                            session.query(Global_values).filter(
                                Global_values.setting_id == key,
                                Global_values.suffix == suffix,
                            ).update({Global_values.value: value})

            try:
                metadata = session.query(Metadata).get(1)
                if metadata is not None and not metadata.first_config_saved:
                    metadata.first_config_saved = True
            except (ProgrammingError, OperationalError):
                pass

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
                    "data": custom_config["value"].replace("\\\n", "\n").encode("utf-8")
                    if isinstance(custom_config["value"], str)
                    else custom_config["value"].replace(b"\\\n", b"\n"),
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

                if custom_conf is None:
                    to_put.append(Custom_configs(**config))
                elif config["checksum"] != custom_conf.checksum and (
                    method == custom_conf.method or method == "autoconf"
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
            db_services = session.query(Services).with_entities(Services.id).all()
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
                suffix = 0
                while True:
                    global_value = (
                        session.query(Global_values)
                        .with_entities(Global_values.value, Global_values.method)
                        .filter_by(setting_id=setting.id, suffix=suffix)
                        .first()
                    )

                    if global_value is None:
                        if suffix == 0:
                            default = setting.default or ""
                            config[setting.id] = (
                                default
                                if methods is False
                                else {"value": default, "method": "default"}
                            )
                        elif setting.context != "multisite":
                            break
                    else:
                        config[setting.id + (f"_{suffix}" if suffix > 0 else "")] = (
                            global_value.value
                            if methods is False
                            else {
                                "value": global_value.value,
                                "method": global_value.method,
                            }
                        )

                    if setting.context == "multisite":
                        changed = False
                        for service in db_services:
                            if suffix == 0:
                                config[f"{service.id}_{setting.id}"] = (
                                    config[setting.id]
                                    if methods is False
                                    else {
                                        "value": config[setting.id]["value"],
                                        "method": "default",
                                    }
                                )
                                changed = True
                            elif f"{setting.id}_{suffix}" in config:
                                config[f"{service.id}_{setting.id}_{suffix}"] = (
                                    config[f"{setting.id}_{suffix}"]
                                    if methods is False
                                    else {
                                        "value": config[f"{setting.id}_{suffix}"][
                                            "value"
                                        ],
                                        "method": "default",
                                    }
                                )
                                changed = True

                            service_setting = (
                                session.query(Services_settings)
                                .with_entities(
                                    Services_settings.value, Services_settings.method
                                )
                                .filter_by(
                                    service_id=service.id,
                                    setting_id=setting.id,
                                    suffix=suffix,
                                )
                                .first()
                            )

                            if service_setting is not None:
                                config[
                                    f"{service.id}_{setting.id}"
                                    + (f"_{suffix}" if suffix > 0 else "")
                                ] = (
                                    service_setting.value
                                    if methods is False
                                    else {
                                        "value": service_setting.value,
                                        "method": service_setting.method,
                                    }
                                )
                                changed = True

                        if global_value is None and changed is False:
                            break

                    if not setting.multiple:
                        break

                    suffix += 1

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
                        tmp_config[key.replace(f"{service}_", "")] = value
                        del tmp_config[key]
                    elif any(key.startswith(f"{s}_") for s in service_names):
                        del tmp_config[key]

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

            if job is None:
                return "Job not found"

            job.last_run = datetime.now()
            job.success = success

            try:
                session.commit()
            except BaseException:
                return format_exc()

        return ""

    def update_job_cache(
        self,
        job_name: str,
        service_id: Optional[str],
        file_name: str,
        data: bytes,
        *,
        checksum: str = None,
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

            if cache is None:
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

    def update_external_plugins(self, plugins: List[Dict[str, Any]]) -> str:
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
            if db_plugins:
                db_ids = [plugin.id for plugin in db_plugins]
                ids = [plugin["id"] for plugin in plugins]
                missing_ids = [plugin for plugin in db_ids if plugin not in ids]

                if missing_ids:
                    # Remove plugins that are no longer in the list
                    session.query(Plugins).filter(Plugins.id.in_(missing_ids)).delete()

            for plugin in plugins:
                settings = plugin.pop("settings", {})
                jobs = plugin.pop("jobs", [])
                pages = plugin.pop("pages", [])
                plugin["external"] = True
                db_plugin = (
                    session.query(Plugins)
                    .with_entities(
                        Plugins.order,
                        Plugins.name,
                        Plugins.description,
                        Plugins.version,
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

                    if plugin["order"] != db_plugin.order:
                        updates[Plugins.order] = plugin["order"]

                    if plugin["name"] != db_plugin.name:
                        updates[Plugins.name] = plugin["name"]

                    if plugin["description"] != db_plugin.description:
                        updates[Plugins.description] = plugin["description"]

                    if plugin["version"] != db_plugin.version:
                        updates[Plugins.version] = plugin["version"]

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

                        if setting not in db_ids or db_setting is None:
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

                        if job["name"] not in db_names or db_job is None:
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

                    if exists(f"/usr/share/bunkerweb/core/{plugin['id']}/ui"):
                        if {"template.html", "actions.py"}.issubset(
                            listdir(f"/usr/share/bunkerweb/core/{plugin['id']}/ui")
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

                            if db_plugin_page is None:
                                with open(
                                    f"/usr/share/bunkerweb/core/{plugin['id']}/ui/template.html",
                                    "r",
                                ) as file:
                                    template = file.read().encode("utf-8")
                                with open(
                                    f"/usr/share/bunkerweb/core/{plugin['id']}/ui/actions.py",
                                    "r",
                                ) as file:
                                    actions = file.read().encode("utf-8")

                                to_put.append(
                                    Plugin_pages(
                                        plugin_id=plugin["id"],
                                        template_file=template,
                                        template_checksum=sha256(template).hexdigest(),
                                        actions_file=actions,
                                        actions_checksum=sha256(actions).hexdigest(),
                                    )
                                )
                            else:  # TODO test this
                                updates = {}
                                template_checksum = file_hash(
                                    f"/usr/share/bunkerweb/core/{plugin['id']}/ui/template.html"
                                )
                                actions_checksum = file_hash(
                                    f"/usr/share/bunkerweb/core/{plugin['id']}/ui/actions.py"
                                )

                                if (
                                    template_checksum
                                    != db_plugin_page.template_checksum
                                ):
                                    with open(
                                        f"/usr/share/bunkerweb/core/{plugin['id']}/ui/template.html",
                                        "r",
                                    ) as file:
                                        updates.update(
                                            {
                                                Plugin_pages.template_file: file.read().encode(
                                                    "utf-8"
                                                ),
                                                Plugin_pages.template_checksum: template_checksum,
                                            }
                                        )

                                if actions_checksum != db_plugin_page.actions_checksum:
                                    with open(
                                        f"/usr/share/bunkerweb/core/{plugin['id']}/ui/actions.py",
                                        "r",
                                    ) as file:
                                        updates.update(
                                            {
                                                Plugin_pages.actions_file: file.read().encode(
                                                    "utf-8"
                                                ),
                                                Plugin_pages.actions_checksum: actions_checksum,
                                            }
                                        )

                                if updates:
                                    session.query(Plugin_pages).filter(
                                        Plugin_pages.plugin_id == plugin["id"]
                                    ).update(updates)

                    continue

                to_put.append(Plugins(**plugin))

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

                for page in pages:
                    to_put.append(
                        Plugin_pages(
                            plugin_id=plugin["id"],
                            template_file=page["template_file"],
                            template_checksum=sha256(page["template_file"]).hexdigest(),
                            actions_file=page["actions_file"],
                            actions_checksum=sha256(page["actions_file"]).hexdigest(),
                        )
                    )

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException:
                return format_exc()

        return ""

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
                    "last_run": job.last_run.strftime("%Y/%m/%d, %I:%M:%S %p"),
                    "cache": [
                        {
                            "service_id": cache.service_id,
                            "file_name": cache.file_name,
                            "data": cache.data,
                            "last_update": cache.last_update.strftime(
                                "%Y/%m/%d, %I:%M:%S %p"
                            ),
                        }
                        for cache in session.query(Jobs_cache)
                        .with_entities(
                            Jobs_cache.service_id,
                            Jobs_cache.file_name,
                            Jobs_cache.data,
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

    def save_log(
        self,
        log: str,
        level: Tuple[str, int],
        component: str,
    ) -> str:
        """Save log."""
        with self.__db_session() as session:
            session.add(
                Logs(
                    id=int(datetime.now().timestamp()),
                    message=log,
                    level=str(_levelToName[_nameToLevel.get(level, NOTSET)])
                    if isinstance(level, str)
                    else _levelToName.get(level, "NOTSET"),
                    component=component,
                )
            )

            try:
                session.commit()
            except BaseException:
                return format_exc()

        return ""

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
                return "An instance with the same hostname already exists."

            session.add(
                Instances(hostname=hostname, port=int(port), server_name=server_name)
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
