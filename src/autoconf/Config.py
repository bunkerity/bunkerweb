#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime
from os import getenv
from time import sleep
from typing import Any, Dict, List, Literal, Optional, Union

from Database import Database  # type: ignore
from logger import getLogger  # type: ignore

# Substrings (matched against the upper-cased setting name) of settings whose value is a secret.
# Every autoconf log line that prints a setting value goes through redact_secrets()/is_sensitive_key(),
# so the list is the one place to extend when a plugin adds a secret-bearing setting.
SENSITIVE_KEY_SUBSTRINGS = (
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "API_KEY",
    "PRIVATE_KEY",
    "_KEY_DATA",
    "CREDENTIAL",
    "LICENSE",
    "DATABASE_URI",
    "AUTH_BASIC",
    "HEADER_VALUE",
)

REDACTED = "<redacted>"


def is_sensitive_key(key: Any) -> bool:
    upper_key = str(key).upper()
    return any(marker in upper_key for marker in SENSITIVE_KEY_SUBSTRINGS)


def redact_secrets(value: Any, key: Any = "") -> Any:
    """Return a copy of ``value`` that is safe to log: the value of every sensitive key is replaced.

    ``key`` is the name the value is stored under; containers are walked so an instance dict holding
    an ``API_TOKEN`` or a service dict holding ``*_KEY_DATA`` never reaches a log in clear.
    """
    if is_sensitive_key(key):
        return REDACTED
    if isinstance(value, dict):
        return {k: redact_secrets(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_secrets(v, key) for v in value]
    return value


class Config:
    def __init__(self, ctrl_type: Union[Literal["docker"], Literal["swarm"], Literal["kubernetes"]]):
        self._type = ctrl_type
        self.__logger = getLogger("CONFIG")
        self._settings = {}
        self.__instances = []
        self.__services = []
        self._supported_config_types = (
            "http",
            "stream",
            "server-http",
            "server-stream",
            "default-server-http",
            "modsec",
            "modsec-crs",
            "crs-plugins-before",
            "crs-plugins-after",
        )
        self.__configs = {config_type: {} for config_type in self._supported_config_types}
        self.__config = {}
        self.__extra_config = {}

        # Signature (set of valid setting ids) as of the last successful apply. Used to detect when
        # the available settings change out-of-band (e.g. a PRO license became valid and its
        # settings landed in the DB, an external plugin was added, or PRO expired) so labels that
        # were previously dropped as invalid can be re-evaluated. None until the first apply.
        self._applied_settings_signature = None

        # When enabled, services / custom configs removed from the orchestrator are converted
        # to draft in the DB instead of being hard-deleted, so they can be republished later.
        self._disable_cleanup = getenv("AUTOCONF_DISABLE_CLEANUP", "no").strip().lower() == "yes"

        self._db = Database(self.__logger)

    def _update_settings(self):
        plugins = self._db.get_plugins()
        if not plugins:
            self.__logger.error("No plugins in database, can't update settings...")
            return
        self._settings = {}
        for plugin in plugins:
            self._settings.update(plugin["settings"])

    def settings_changed(self) -> bool:
        """Whether the set of valid setting ids differs from the last successful apply.

        Returns False until the first apply has recorded a baseline (signature is None), so the
        recheck worker never fires before initial_apply has run.
        """
        return self._applied_settings_signature is not None and frozenset(self._settings) != self._applied_settings_signature

    def __get_full_env(self) -> dict:
        config = {"SERVER_NAME": "", "MULTISITE": "yes"}
        for service in self.__services:
            server_name = service["SERVER_NAME"].split(" ")[0]
            if not server_name:
                continue
            config["SERVER_NAME"] += f" {server_name}"

        db_services = []
        for db_service in self._db.get_services():
            server_name = db_service.get("id", "")
            if not server_name:
                continue
            db_services.append(server_name)

        for service in self.__services:
            server_name = service["SERVER_NAME"].split(" ")[0]
            if not server_name:
                continue
            for variable, value in service.items():
                if variable == "NAMESPACE" or variable.startswith("CUSTOM_CONF"):
                    continue

                is_global = False
                success, err = self._db.is_valid_setting(
                    variable,
                    value=value,
                    multisite=True,
                    extra_services=config["SERVER_NAME"].split() + db_services,
                )
                if not success:
                    if self._type == "kubernetes":
                        success, err = self._db.is_valid_setting(variable, value=value)
                        if success:
                            is_global = True
                            self.__logger.warning(f"Variable {variable} is a global value and will be applied globally")
                    if not success:
                        self.__logger.warning(f"Variable {variable} is not a valid autoconf setting ({err}), ignoring it")
                        continue

                if is_global or variable.startswith(f"{server_name}_"):
                    if variable == "SERVER_NAME":
                        self.__logger.warning("Global variable SERVER_NAME can't be set via annotations, ignoring it")
                        continue
                    config[variable] = value
                    continue
                config[f"{server_name}_{variable}"] = value
        config["SERVER_NAME"] = config["SERVER_NAME"].strip()
        return config

    @staticmethod
    def _instance_targets(instances: List[Dict[str, Any]]) -> list:
        # Match Database.update_instances: health and discovery metadata do not change push targets.
        return sorted(
            (
                instance.get("hostname", ""),
                str(instance.get("env", {}).get("API_HTTP_PORT", 5000)),
                instance.get("env", {}).get("API_LISTEN_HTTPS", "no") == "yes",
                str(instance.get("env", {}).get("API_HTTPS_PORT", 5443)),
                instance.get("env", {}).get("API_SERVER_NAME", "bwapi"),
            )
            for instance in instances
        )

    def update_needed(
        self,
        instances: List[Dict[str, Any]],
        services: List[Dict[str, str]],
        configs: Optional[Dict[str, Dict[str, bytes]]] = None,
        extra_config: Optional[Dict[str, str]] = None,
    ) -> bool:
        configs = configs or {}
        extra_config = extra_config or {}

        # Each comparison is the same one apply() makes on the same value. A difference update_needed
        # sees but apply() cannot act on never converges: apply() is what stores the new value, so when
        # it finds no change the stored content stays old and the next poll reports it again, forever.
        # str() of a dict follows its insertion order, so the same services or configs rebuilt in another
        # order (labels serialised differently by the daemon) read as a change through set(map(str, ...)).
        if self._instance_targets(self.__instances) != self._instance_targets(instances):
            self.__logger.debug(f"Instances changed: {redact_secrets(self.__instances)} -> {redact_secrets(instances)}")
            return True

        if self.__services != services:
            self.__logger.debug(f"Services changed: {redact_secrets(self.__services)} -> {redact_secrets(services)}")
            return True

        if self.__configs != configs:
            self.__logger.debug(f"Configs changed: {self.__log_configs(self.__configs)} -> {self.__log_configs(configs)}")
            return True

        if set(map(str, self.__extra_config.items())) != set(map(str, extra_config.items())):
            self.__logger.debug(f"Extra config changed: {redact_secrets(self.__extra_config)} -> {redact_secrets(extra_config)}")
            return True

        return False

    @staticmethod
    def __log_configs(configs: Dict[str, Dict[str, bytes]]) -> Dict[str, List[str]]:
        # Custom config bodies can hold anything (keys, tokens): log which files exist, never their content.
        return {config_type: sorted(files) for config_type, files in configs.items()}

    def have_to_wait(self) -> bool:
        db_metadata = self._db.get_metadata()
        return (
            isinstance(db_metadata, str)
            or not db_metadata["is_initialized"]
            or any(
                v
                for k, v in db_metadata.items()
                if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
            )
        )

    def wait_applying(self):
        # Ready when DB is initialized and no scheduler apply is in flight.
        current_time = datetime.now().astimezone()
        ready = False
        while not ready and (datetime.now().astimezone() - current_time).seconds < 240:
            db_metadata = self._db.get_metadata()
            if isinstance(db_metadata, str):
                self.__logger.error(f"An error occurred when checking for changes in the database : {db_metadata}")
            elif db_metadata["is_initialized"] and not any(
                v
                for k, v in db_metadata.items()
                if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
            ):
                ready = True
                continue
            self.__logger.warning("Scheduler is already applying a configuration, retrying in 5 seconds ...")
            sleep(5)

        if not ready:
            raise Exception("Too many retries while waiting for scheduler to apply configuration...")

    def apply(
        self,
        instances: List[Dict[str, Any]],
        services: List[Dict[str, str]],
        configs: Optional[Dict[str, Dict[str, bytes]]] = None,
        first: bool = False,
        extra_config: Optional[Dict[str, str]] = None,
        force: bool = False,
    ) -> bool:
        success = True

        err = self._try_database_readonly()
        if err:
            return False

        self.wait_applying()

        configs = configs or {}
        extra_config = extra_config or {}

        changes = []
        if first or self._instance_targets(instances) != self._instance_targets(self.__instances):
            self.__instances = instances
            changes.append("instances")
        if services != self.__services or first:
            self.__services = services
            changes.append("services")
        if configs != self.__configs or first:
            self.__configs = configs
            changes.append("custom_configs")
        if extra_config != self.__extra_config or first:
            changes.append("extra_config")
        # force=True re-validates labels even when instances/services are unchanged: this is how a
        # now-valid PRO label (or any label that became valid after the settings set changed) gets
        # picked up, since __get_full_env() re-checks every label against the current DB settings.
        if "instances" in changes or "services" in changes or "extra_config" in changes or force:
            old_env = self.__config.copy()
            new_env = self.__get_full_env() | extra_config
            if old_env != new_env or first:
                self.__config = new_env
                changes.append("config")
            if "extra_config" in changes:
                self.__extra_config = extra_config.copy()

        custom_configs = []
        if "custom_configs" in changes:
            for config_type in self.__configs:
                if config_type not in self._supported_config_types:
                    self.__logger.warning(f"Unsupported custom config type: {config_type}")
                    continue

                for file, data in self.__configs[config_type].items():
                    site = None
                    name = file
                    if "/" in file:
                        exploded = file.split("/")
                        site = exploded[0]
                        name = exploded[1]
                    custom_configs.append({"value": data, "exploded": [site, config_type, name.replace(".conf", "")]})

        # update instances in database
        if "instances" in changes:
            self.__logger.debug(f"Updating instances in database: {redact_secrets(self.__instances)}")
            err = self._db.update_instances(self.__instances, "autoconf", changed=False)
            if err:
                self.__logger.error(f"Failed to update instances: {err}")

        # save config to database
        changed_plugins = []
        if "config" in changes:
            self.__logger.debug(f"Saving config in database: {redact_secrets(self.__config)}")
            err = self._db.save_config(self.__config, "autoconf", changed=False, disable_cleanup=self._disable_cleanup)
            if isinstance(err, str):
                success = False
                self.__logger.error(f"Can't save config in database: {err}, config may not work as expected")
            changed_plugins = err

        # save custom configs to database
        if "custom_configs" in changes:
            self.__logger.debug(f"Saving custom configs in database: {[config['exploded'] for config in custom_configs]}")
            err = self._db.save_custom_configs(custom_configs, "autoconf", changed=False, disable_cleanup=self._disable_cleanup)
            if err:
                success = False
                self.__logger.error(f"Can't save autoconf custom configs in database: {err}, custom configs may not work as expected")

        # update changes in db, only when there is something to signal: Database.checked_changes() reads an
        # empty list like None, i.e. every *_changed flag, which makes the scheduler redo its whole job batch
        if changes:
            ret = self._db.checked_changes(changes, plugins_changes=changed_plugins, value=True)
            if ret:
                self.__logger.error(f"An error occurred when setting the changes to checked in the database : {ret}")

            self.__logger.info("Successfully saved new configuration 🚀")

        if success:
            # Record the settings baseline so the recheck worker only re-fires when the valid
            # settings set actually changes again (not after every normal apply).
            self._applied_settings_signature = frozenset(self._settings)

        return success

    def _try_database_readonly(self) -> bool:
        if not self._db.readonly:
            try:
                self._db.test_write()
            except BaseException:
                self._db.readonly = True
                return True

        if self._db.database_uri and self._db.readonly:
            try:
                self._db.retry_connection(pool_timeout=1)
                self._db.retry_connection(log=False)
                self._db.readonly = False
                self.__logger.info("The database is no longer read-only, defaulting to read-write mode")
            except BaseException:
                try:
                    self._db.retry_connection(readonly=True, pool_timeout=1)
                    self._db.retry_connection(readonly=True, log=False)
                except BaseException:
                    if self._db.database_uri_readonly:
                        with suppress(BaseException):
                            self._db.retry_connection(fallback=True, pool_timeout=1)
                            self._db.retry_connection(fallback=True, log=False)
                self._db.readonly = True

            if self._db.readonly:
                self.__logger.error("Database is in read-only mode, configuration will not be saved")

        return self._db.readonly
