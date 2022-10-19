from contextlib import contextmanager
from copy import deepcopy
from logging import INFO, WARNING, Logger, getLogger
from os import _exit, environ, path
from re import search
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import scoped_session, sessionmaker
from time import sleep
from traceback import format_exc

from model import *


class Database:
    def __init__(self, logger: Logger, sqlalchemy_string: str = None) -> None:
        """Initialize the database"""
        self.__logger = logger
        getLogger("sqlalchemy.engine").setLevel(
            logger.level if logger.level != INFO else WARNING
        )

        if not sqlalchemy_string:
            sqlalchemy_string = environ.get(
                "DATABASE_URI", "sqlite:////data/db.sqlite3"
            )

        if sqlalchemy_string.startswith("sqlite"):
            if not path.exists(sqlalchemy_string.split("///")[1]):
                open(sqlalchemy_string.split("///")[1], "w").close()

        self.__sql_engine = create_engine(
            sqlalchemy_string,
            encoding="utf-8",
            future=True,
            logging_name="sqlalchemy.engine",
        )
        not_connected = True
        retries = 5

        while not_connected:
            try:
                self.__sql_engine.connect()
                not_connected = False
            except SQLAlchemyError:
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

        self.__session = sessionmaker()
        self.__sql_session = scoped_session(self.__session)
        self.__sql_session.remove()
        self.__sql_session.configure(
            bind=self.__sql_engine, autoflush=False, expire_on_commit=False
        )

    def __del__(self) -> None:
        """Close the database"""
        self.__sql_session.remove()
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

    def is_first_config_saved(self) -> bool:
        """Check if the first configuration has been saved"""
        with self.__db_session() as session:
            try:
                metadata = session.query(Metadata).get(1)
                return metadata is not None and metadata.first_config_saved
            except (ProgrammingError, OperationalError):
                return False

    def is_initialized(self) -> bool:
        """Check if the database is initialized"""
        with self.__db_session() as session:
            try:
                metadata = session.query(Metadata).get(1)
                return metadata is not None and metadata.is_initialized
            except (ProgrammingError, OperationalError):
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

        with self.__db_session() as session:
            to_put = []
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
                            "version": "1.0.0",
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
                        to_put.append(Jobs(plugin_id=plugin["id"], **job))

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
            session.execute(
                Services.__table__.delete().where(Services.method == method)
            )
            session.execute(Global_values.__table__.delete())

            if config:
                if config["MULTISITE"] == "yes":
                    global_values = []
                    for server_name in config["SERVER_NAME"].split(" "):
                        if server_name:
                            to_put.append(Services(id=server_name, method=method))

                        for key, value in deepcopy(config).items():
                            suffix = None
                            if search(r"_\d+$", key):
                                suffix = int(key.split("_")[-1])
                                key = key[: -len(str(suffix)) - 1]

                            if server_name and key.startswith(server_name):
                                key = key.replace(f"{server_name}_", "")

                                to_put.append(
                                    Services_settings(
                                        service_id=server_name,
                                        setting_id=key,
                                        value=value,
                                        suffix=suffix,
                                    )
                                )
                            elif key not in global_values:
                                setting = (
                                    session.query(Settings).filter_by(id=key).first()
                                )

                                if setting and value != setting.default:
                                    global_values.append(key)
                                    to_put.append(
                                        Global_values(
                                            setting_id=key, value=value, suffix=suffix
                                        )
                                    )
                else:
                    primary_server_name = config["SERVER_NAME"].split(" ")[0]
                    to_put.append(Services(id=primary_server_name, method=method))

                    for key, value in config.items():
                        suffix = None
                        if search(r"_\d+$", key):
                            suffix = int(key.split("_")[-1])
                            key = key[: -len(str(suffix)) - 1]

                        to_put.append(
                            Services_settings(
                                service_id=primary_server_name,
                                setting_id=key,
                                value=value,
                                suffix=suffix,
                            )
                        )

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
        with self.__db_session() as session:
            # Delete all the old config
            session.execute(
                Custom_configs.__table__.delete().where(Custom_configs.method == method)
            )

            to_put = []
            for custom_config in custom_configs:
                config = {
                    "data": custom_config["value"]
                    .replace("\\\n", "\n")
                    .encode("utf-8"),
                    "method": method,
                }
                if custom_config["exploded"][0]:
                    if (
                        not session.query(Services)
                        .filter_by(id=custom_config["exploded"][0])
                        .first()
                    ):
                        return f"Service {custom_config['exploded'][0]} not found, please check your config"

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
                to_put.append(Custom_configs(**config))

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException:
                return format_exc()

        return ""

    def __get_setting_value(
        self,
        session: scoped_session,
        service: Any,
        setting: Any,
        suffix: int,
    ) -> Optional[dict]:
        tmp_config = {}
        global_value = (
            session.query(Global_values)
            .filter_by(setting_id=setting.id, suffix=suffix)
            .first()
        )

        if global_value is None:
            if suffix:
                if setting.context != "multisite":
                    return None

                tmp_config[f"{setting.id}_{suffix}"] = setting.default
            else:
                tmp_config[setting.id] = setting.default
        else:
            tmp_config[
                setting.id + (f"_{suffix}" if suffix else "")
            ] = global_value.value

        if setting.context == "multisite":
            try:
                tmp_config[
                    f"{service.id}_{setting.id}" + (f"_{suffix}" if suffix else "")
                ] = next(
                    s
                    for s in service.settings
                    if s.setting_id == setting.id and s.suffix == suffix
                ).value
            except StopIteration:
                if global_value is None and suffix:
                    return None
                elif suffix:
                    if tmp_config[f"{setting.id}_{suffix}"] == setting.default:
                        return tmp_config

                    tmp_config[f"{service.id}_{setting.id}_{suffix}"] = tmp_config[
                        f"{setting.id}_{suffix}"
                    ]
                else:
                    if tmp_config[setting.id] == setting.default:
                        return tmp_config

                    tmp_config[f"{service.id}_{setting.id}"] = tmp_config[setting.id]

        return tmp_config

    def get_config(self) -> Dict[str, Any]:
        """Get the config from the database"""
        with self.__db_session() as session:
            config = {}
            settings = session.query(Settings).all()
            for service in session.query(Services).all():
                for setting in settings:
                    if setting.multiple:
                        i = 0
                        while True:
                            tmp_config = self.__get_setting_value(
                                session, service, setting, i
                            )

                            if tmp_config is None:
                                break

                            config.update(tmp_config)
                            i += 1
                    else:
                        config.update(
                            self.__get_setting_value(session, service, setting, 0)
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
                    "data": custom_config.data.decode("utf-8"),
                }
                for custom_config in session.query(Custom_configs).all()
            ]
