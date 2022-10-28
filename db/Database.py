from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from logging import INFO, WARNING, Logger, getLogger
from os import _exit, getenv, listdir, path
from os.path import exists
from re import search
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import scoped_session, sessionmaker
from time import sleep
from traceback import format_exc

from model import *


class Database:
    def __init__(
        self,
        logger: Logger,
        sqlalchemy_string: str = None,
        bw_integration: str = "Local",
    ) -> None:
        """Initialize the database"""
        self.__logger = logger
        self.__sql_session = None
        self.__sql_engine = None

        getLogger("sqlalchemy.engine").setLevel(
            logger.level if logger.level != INFO else WARNING
        )

        if sqlalchemy_string is None and bw_integration != "Local":
            if bw_integration == "Kubernetes":
                from kubernetes import client as kube_client

                corev1 = kube_client.CoreV1Api()
                for pod in corev1.list_pod_for_all_namespaces(watch=False).items:
                    if (
                        pod.metadata.annotations != None
                        and "bunkerweb.io/INSTANCE" in pod.metadata.annotations
                    ):
                        for pod_env in pod.spec.containers[0].env:
                            if pod_env.name == "DATABASE_URI":
                                sqlalchemy_string = pod_env.value
                                break

                    if sqlalchemy_string:
                        break
            else:
                from docker import DockerClient

                docker_client = DockerClient(
                    base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
                )
                for instance in docker_client.containers.list(
                    filters={"label": "bunkerweb.INSTANCE"}
                ):
                    for var in instance.attrs["Config"]["Env"]:
                        if var.startswith("DATABASE_URI="):
                            sqlalchemy_string = var.replace("DATABASE_URI=", "", 1)
                            break

                    if sqlalchemy_string:
                        break

                is_swarm = True
                try:
                    docker_client.swarm.version
                except:
                    is_swarm = False

                if not sqlalchemy_string and is_swarm:
                    for instance in docker_client.services.list(
                        filters={"label": "bunkerweb.INSTANCE"}
                    ):
                        for var in instance.attrs["Spec"]["TaskTemplate"][
                            "ContainerSpec"
                        ]["Env"]:
                            if var.startswith("DATABASE_URI="):
                                sqlalchemy_string = var.replace("DATABASE_URI=", "", 1)
                                break

                        if sqlalchemy_string:
                            break

        if not sqlalchemy_string:
            sqlalchemy_string = getenv("DATABASE_URI", "sqlite:////data/db.sqlite3")

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

                    if exists(f"/opt/bunkerweb/core/{plugin['id']}/ui"):
                        if {"template.html", "actions.py"}.issubset(
                            listdir(f"/opt/bunkerweb/core/{plugin['id']}/ui")
                        ):
                            with open(
                                f"/opt/bunkerweb/core/{plugin['id']}/ui/template.html",
                                "r",
                            ) as file:
                                template = file.read().encode("utf-8")
                            with open(
                                f"/opt/bunkerweb/core/{plugin['id']}/ui/actions.py", "r"
                            ) as file:
                                actions = file.read().encode("utf-8")

                            to_put.append(
                                Plugin_pages(
                                    plugin_id=plugin["id"],
                                    template_file=template,
                                    actions_file=actions,
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
            session.execute(
                Services.__table__.delete().where(Services.method == method)
            )
            session.execute(Global_values.__table__.delete())

            if config:
                if config["MULTISITE"] == "yes":
                    global_values = []
                    for server_name in config["SERVER_NAME"].split(" "):
                        if (
                            session.query(Services)
                            .with_entities(Services.id)
                            .filter_by(id=server_name)
                            .first()
                        ):
                            continue

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
                                    session.query(Settings)
                                    .with_entities(Settings.default)
                                    .filter_by(id=key)
                                    .first()
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
                    "data": custom_config["value"].replace("\\\n", "\n").encode("utf-8")
                    if isinstance(custom_config["value"], str)
                    else custom_config["value"].replace(b"\\\n", b"\n"),
                    "method": method,
                }
                if custom_config["exploded"][0]:
                    if (
                        not session.query(Services)
                        .with_entities(Services.id)
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

    def get_config(self) -> Dict[str, Any]:
        """Get the config from the database"""
        with self.__db_session() as session:
            config = {}
            settings = (
                session.query(Settings)
                .with_entities(
                    Settings.id, Settings.context, Settings.default, Settings.multiple
                )
                .all()
            )

            for setting in settings:
                suffix = 0
                while True:
                    global_value = (
                        session.query(Global_values)
                        .with_entities(Global_values.value)
                        .filter_by(setting_id=setting.id, suffix=suffix)
                        .first()
                    )

                    if global_value is None:
                        if suffix > 0:
                            break
                        else:
                            config[setting.id] = setting.default
                    else:
                        config[
                            setting.id + (f"_{suffix}" if suffix > 0 else "")
                        ] = global_value.value

                    if not setting.multiple:
                        break

                    suffix += 1

            for service in session.query(Services).with_entities(Services.id).all():
                for setting in settings:
                    if setting.context != "multisite":
                        continue

                    suffix = 0
                    while True:
                        if suffix == 0:
                            config[f"{service.id}_{setting.id}"] = config[setting.id]
                        elif f"{setting.id}_{suffix}" in config:
                            config[f"{service.id}_{setting.id}_{suffix}"] = config[
                                f"{setting.id}_{suffix}"
                            ]

                        service_setting = (
                            session.query(Services_settings)
                            .with_entities(Services_settings.value)
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
                            ] = service_setting.value
                        elif suffix > 0:
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
                    "data": custom_config.data.decode("utf-8"),
                    "method": custom_config.method,
                }
                for custom_config in session.query(Custom_configs)
                .with_entities(
                    Custom_configs.service_id,
                    Custom_configs.type,
                    Custom_configs.name,
                    Custom_configs.data,
                    Custom_configs.method,
                )
                .all()
            ]

    def get_services(self) -> List[Dict[str, Any]]:
        """Get the services' configs from the database"""
        services = []
        with self.__db_session() as session:
            for service in (
                session.query(Services).with_entities(Services.settings).all()
            ):
                services.append(service.settings)

        return services

    def update_job(self, plugin_id: str, job_name: str) -> str:
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
                session.query(Job_cache)
                .filter_by(
                    job_name=job_name, service_id=service_id, file_name=file_name
                )
                .first()
            )

            if cache is None:
                session.add(
                    Job_cache(
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

    def update_plugins(self, plugins: List[Dict[str, Any]]) -> str:
        """Add a new plugin to the database"""
        to_put = []
        with self.__db_session() as session:
            # Delete all old plugins
            session.execute(Plugins.__table__.delete().where(Plugins.id != "default"))

            for plugin in plugins:
                settings = plugin.pop("settings", {})
                jobs = plugin.pop("jobs", [])
                pages = plugin.pop("pages", [])

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

                for page in pages:
                    to_put.append(
                        Plugin_pages(
                            plugin_id=plugin["id"],
                            template_file=page["template_file"],
                            actions_file=page["actions_file"],
                        )
                    )

            try:
                session.add_all(to_put)
                session.commit()
            except BaseException:
                return format_exc()

        return ""
