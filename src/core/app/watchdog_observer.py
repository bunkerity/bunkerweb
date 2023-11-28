# -*- coding: utf-8 -*-
from threading import Thread
from os import environ, sep
from os.path import join
from pathlib import Path
from sys import path as sys_path
from threading import enumerate as all_threads
from time import sleep, time
from typing import Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from watchdog.observers import Observer
from watchdog.events import FileOpenedEvent, FileClosedEvent, FileSystemEventHandler

from API import API  # type: ignore
from database import Database  # type: ignore (imported from /usr/share/bunkerweb/utils)
from .job_scheduler import JobScheduler
from .core import CONFIG_FILE, SECRETS_PATH, YAML_CONFIG_FILE, CoreConfig
from .dependencies import api_started, CORE_CONFIG, CUSTOM_CONFIGS_PATH, DB, EXTERNAL_PLUGINS_PATH, is_not_reloading, listen_for_dynamic_instances, SCHEDULER, test_and_send_to_instances  # noqa: F401
from .utils import listen_dynamic_instances, startup, update_custom_configs


class ConfigHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.__observer = WatchdogObserver()
        self.last_any_event = 0
        self.last_modified_event = 0

    def __is_config_file(self, path: str) -> bool:
        return path in (str(YAML_CONFIG_FILE.resolve()), str(CONFIG_FILE.resolve())) or path.startswith(str(SECRETS_PATH.resolve()))

    def on_any_event(self, event):
        """Catch-all event handler.

        :param event:
            The event object representing the file system event.
        :type event:
            :class:`FileSystemEvent`
        """
        if isinstance(event, (FileOpenedEvent, FileClosedEvent)) or not api_started.is_set():
            CORE_CONFIG.logger.debug(f"📝 File {event.src_path} has been modified but it's not a config file or the API is not started yet, ignoring it ...")
            return

        current_time = time()
        if current_time - self.last_any_event <= 1:
            CORE_CONFIG.logger.debug(f"📝 File {event.src_path} has been modified but the last event was less than 1 second ago, ignoring it ...")
            return
        self.last_any_event = current_time

        CORE_CONFIG.logger.info(f"📝 File {event.src_path} has been modified")
        if self.__is_config_file(event.src_path):
            CORE_CONFIG.logger.info("🐕 Reloading watchdog ...")
            self.__observer.unschedule_all()
            self.__observer.setup()
        elif event.src_path.startswith(str(CUSTOM_CONFIGS_PATH.resolve())):
            is_not_reloading.wait(timeout=60)

            db_config = "retry"
            retries = 0
            while db_config == "retry":
                db_config = DB.get_config()

                if db_config == "retry":
                    if retries >= 5:
                        CORE_CONFIG.logger.error("Can't get config from database after 5 retries, aborting ...")
                        return
                    CORE_CONFIG.logger.warning("Can't get config from database, retrying in 5 seconds ...")
                    sleep(5)
                    continue
                elif isinstance(db_config, str):
                    CORE_CONFIG.logger.error(f"Can't get config from database : {db_config}, retry later")
                    return

            assert isinstance(db_config, dict)

            CORE_CONFIG.logger.info("Reloading custom configs...")
            update_custom_configs(db_config)
            Thread(target=test_and_send_to_instances, args=(None, {"custom_configs"})).start()
            CORE_CONFIG.logger.info("✅ Custom configs reloaded successfully")

    def on_modified(self, event):
        """Called when a file or directory is modified.

        :param event:
            Event representing file/directory modification.
        :type event:
            :class:`DirModifiedEvent` or :class:`FileModifiedEvent`
        """
        if not self.__is_config_file(event.src_path) and not event.src_path.startswith(str(EXTERNAL_PLUGINS_PATH.resolve())):
            return

        global CORE_CONFIG, DB, SCHEDULER

        current_time = time()
        if current_time - self.last_modified_event <= 1:
            CORE_CONFIG.logger.debug(f"📝 File {event.src_path} has been modified but the last event was less than 1 second ago, ignoring it ...")
            return
        self.last_modified_event = current_time

        is_not_reloading.wait(timeout=60)

        CORE_CONFIG.logger.info("Reloading config ...")

        CORE_CONFIG = CoreConfig("core", **(environ if CoreConfig.get_instance() != "Linux" else {}))
        del DB
        DB = Database(CORE_CONFIG.logger, CORE_CONFIG.DATABASE_URI)  # noqa: F841
        SCHEDULER = JobScheduler(
            API(f"http://127.0.0.1:{CORE_CONFIG.LISTEN_PORT}", "bw-scheduler"), env=CORE_CONFIG.settings | {"API_ADDR": f"http://127.0.0.1:{CORE_CONFIG.LISTEN_PORT}", "CORE_TOKEN": CORE_CONFIG.core_token}, logger=CORE_CONFIG.logger
        )

        startup()

        if CORE_CONFIG.use_redis:
            running = False
            for thread in all_threads():
                if thread.name == "redis_listener":
                    running = True
                    break

            if CORE_CONFIG.REDIS_HOST:
                if not running:
                    listen_for_dynamic_instances.set()
                    Thread(target=listen_dynamic_instances, name="redis_listener").start()
            else:
                CORE_CONFIG.logger.warning("USE_REDIS is set to yes but REDIS_HOST is not defined, app will not listen for dynamic instances")
                listen_for_dynamic_instances.clear()

        CORE_CONFIG.logger.info("✅ Config reloaded successfully")

        if not CORE_CONFIG.hot_reload:
            CORE_CONFIG.logger.warning("🐕 Hot reload has been disabled, stopping watchdog ...")
            self.__observer.stop()

        is_not_reloading.set()


class WatchdogObserver(Observer):  # type: ignore
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__config_handler = ConfigHandler()
        self.setup()
        self.start()

    def stop(self):
        CORE_CONFIG.logger.debug("🐕 Stopping watchdog ...")
        self.unschedule_all()
        super().stop()

    def schedule(self, path: Union[Path, str], recursive: bool = False):
        super().schedule(self.__config_handler, path, recursive=recursive)
        CORE_CONFIG.logger.info(f"🔍 Starting to watch {path} for changes{' recursively' if recursive else ''} ...")

    def setup(self):
        """Setup watchdog observer"""

        if YAML_CONFIG_FILE.is_file():
            self.schedule(YAML_CONFIG_FILE.resolve())
        if CONFIG_FILE.is_file():
            self.schedule(CONFIG_FILE.resolve())
        if CORE_CONFIG.integration != "Linux" and SECRETS_PATH.is_dir():
            self.schedule(SECRETS_PATH.resolve(), recursive=True)

        self.schedule(CUSTOM_CONFIGS_PATH.resolve(), recursive=True)
        self.schedule(EXTERNAL_PLUGINS_PATH.resolve(), recursive=True)

        CORE_CONFIG.logger.info("🐕 Watchdog started")


__ALL__ = ("WatchdogObserver",)
