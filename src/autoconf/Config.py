#!/usr/bin/env python3

from datetime import datetime
from os import getenv
from time import sleep
from typing import Any, Dict, List, Literal, Optional, Union

from api_client import ApiUnavailableError  # type: ignore
from common_utils import normalize_check_value, normalize_list_value, normalize_select_value, trim_scalar_value  # type: ignore
from unit_parser import normalize_unit  # type: ignore
from logger import getLogger  # type: ignore


class Config:
    def __init__(self, ctrl_type: Union[Literal["docker"], Literal["swarm"], Literal["kubernetes"]], *, api_client):
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

        self._api = api_client
        self._api_available = True
        self._api_error_timeout = int(getenv("API_ERROR_TIMEOUT", "60"))

    def _update_settings(self):
        plugins = self._api.get_plugins()
        if not plugins:
            self.__logger.error("No plugins from API, can't update settings...")
            return
        self._settings = {}
        for plugin in plugins:
            self._settings.update(plugin.get("settings", {}))

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

        api_services = []
        for api_service in self._api.get_services():
            server_name = api_service.get("id", "")
            if not server_name:
                continue
            api_services.append(server_name)

        for service in self.__services:
            server_name = service["SERVER_NAME"].split(" ")[0]
            if not server_name:
                continue
            for variable, value in service.items():
                if variable == "NAMESPACE" or variable.startswith("CUSTOM_CONF"):
                    continue

                is_global = False
                success, err = self._api.validate_setting(
                    variable,
                    value=value,
                    multisite=True,
                    extra_services=config["SERVER_NAME"].split() + api_services,
                )
                if not success:
                    if self._type == "kubernetes":
                        success, err = self._api.validate_setting(variable, value=value)
                        if success:
                            is_global = True
                            self.__logger.warning(f"Variable {variable} is a global value and will be applied globally")
                    if not success:
                        self.__logger.warning(f"Variable {variable}: {value} is not a valid autoconf setting ({err}), ignoring it")
                        continue

                # Canonicalize the value to its stored form (boolean aliases -> yes/no,
                # size/duration -> NGINX unit form, list items trimmed) so it matches the
                # value the DB persists — otherwise apply()'s env diff vs self.__config
                # would differ every cycle (perpetual reconfigure loop).
                schema = self._settings.get(variable, {})
                stype = schema.get("type")
                value = trim_scalar_value(stype, value)
                if stype == "check":
                    value = normalize_check_value(value)
                elif stype in ("size", "duration"):
                    canonical = normalize_unit(stype, value)
                    if canonical is not None:
                        value = canonical
                elif stype == "select":
                    value = normalize_select_value(value, schema.get("select", []), case_insensitive=schema.get("case_insensitive", False))
                elif stype in ("multiselect", "multivalue"):
                    separator = schema.get("separator", " ")
                    value = normalize_list_value(value, separator)
                    if stype == "multiselect":
                        options = [o.get("value", "") for o in schema.get("multiselect", []) if isinstance(o, dict)]
                        value = normalize_select_value(value, options, multi=True, separator=separator, case_insensitive=schema.get("case_insensitive", False))

                if is_global or variable.startswith(f"{server_name}_"):
                    if variable == "SERVER_NAME":
                        self.__logger.warning("Global variable SERVER_NAME can't be set via annotations, ignoring it")
                        continue
                    config[variable] = value
                    continue
                config[f"{server_name}_{variable}"] = value
        config["SERVER_NAME"] = config["SERVER_NAME"].strip()
        return config

    def update_needed(
        self,
        instances: List[Dict[str, Any]],
        services: List[Dict[str, str]],
        configs: Optional[Dict[str, Dict[str, bytes]]] = None,
        extra_config: Optional[Dict[str, str]] = None,
    ) -> bool:
        configs = configs or {}
        extra_config = extra_config or {}

        # Every comparison here is the SAME one apply() makes on the same value a few lines down,
        # and that is the whole requirement: a difference update_needed can see but apply() cannot
        # act on never converges. apply() is what stores the new value, so when it declines to
        # store, self.__instances / __services / __configs keep the OLD content and the next poll
        # reports the identical difference again, forever.
        #
        # `set(map(str, ...))` was that kind of difference. It stringifies each dict, and str() of
        # a dict follows its INSERTION order -- so the same services, rebuilt from a container's
        # labels dict that the daemon happened to serialise in another order (see
        # DockerController._to_services, which iterates `controller_service.labels.items()`), read
        # as a change while apply()'s `!=` compared them by value and found them equal.
        if self.__instances != instances:
            self.__logger.debug(f"Instances changed: {self.__instances} -> {instances}")
            return True

        if self.__services != services:
            self.__logger.debug(f"Services changed: {self.__services} -> {services}")
            return True

        # Same story for the custom configs, and this is the one the Autoconf CI arm actually
        # tripped over: the identical set of configs, enumerated in another order, read as a change
        # on every poll and the controller re-applied on every poll.
        if self.__configs != configs:
            self.__logger.debug(f"Configs changed: {self.__configs} -> {configs}")
            return True

        if set(map(str, self.__extra_config.items())) != set(map(str, extra_config.items())):
            self.__logger.debug(f"Extra config changed: {self.__extra_config} -> {extra_config}")
            return True

        return False

    def have_to_wait(self) -> bool:
        metadata = self._api.get_metadata()
        return (
            isinstance(metadata, str)
            or not metadata.get("is_initialized")
            or any(
                v
                for k, v in metadata.items()
                if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
            )
        )

    def wait_applying(self):
        # Ready when DB is initialized and no scheduler apply is in flight.
        current_time = datetime.now().astimezone()
        ready = False
        waited = False
        error_since = None
        with self._api.expect_errors():
            while not ready and (datetime.now().astimezone() - current_time).seconds < 240:
                metadata = self._api.get_metadata()
                if isinstance(metadata, str):
                    if error_since is None:
                        error_since = datetime.now().astimezone()
                    elapsed = (datetime.now().astimezone() - error_since).seconds
                    if elapsed >= self._api_error_timeout:
                        self._api._expect_errors = False  # Escalate to real errors now
                        self.__logger.error(f"API has been failing for {elapsed}s ({metadata})")
                    else:
                        self.__logger.warning(f"Could not check metadata via API ({metadata}), will retry ...")
                elif (
                    metadata.get("is_initialized")
                    and metadata.get("first_config_saved")
                    and not any(
                        v
                        for k, v in metadata.items()
                        if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
                    )
                ):
                    ready = True
                    continue
                else:
                    error_since = None  # API is responding, just not ready yet
                waited = True
                self.__logger.warning("Scheduler is already applying a configuration, retrying in 5 seconds ...")
                sleep(5)

        if not ready:
            # Deliberately not fatal. The flags above are now held until the job that applies a
            # change acknowledges it, rather than being cleared the moment the scheduler
            # dispatched that job -- which is what makes a lost configuration recoverable. The
            # cost is that they legitimately stay set for as long as the push takes, and
            # push-configs shares one worker with certbot and the blocklist downloads on the
            # heavy lane. Raising here would turn "the worker is busy, or down" into an autoconf
            # outage. Proceeding is what the 240s timeout already meant; the only question was
            # whether giving up should be loud or fatal.
            self.__logger.warning("Scheduler has not finished applying the configuration after 240s; proceeding anyway")

        if waited:
            self.__logger.info("Scheduler is ready, proceeding")

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

        if not self._check_api_available():
            return False

        self.wait_applying()

        configs = configs or {}
        extra_config = extra_config or {}

        changes = []
        if instances != self.__instances or first:
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
                    # Ensure data is a string (Swarm's b64decode returns bytes which can't be JSON-serialized)
                    config_value = data.decode("utf-8") if isinstance(data, bytes) else data
                    custom_configs.append({"value": config_value, "exploded": [site, config_type, name.replace(".conf", "")]})

        # update instances via API
        if "instances" in changes:
            self.__logger.debug(f"Updating instances via API: {self.__instances}")
            err = self._api.update_instances(self.__instances, "autoconf", changed=False)
            if err:
                self.__logger.error(f"Failed to update instances: {err}")

        # save config via API
        changed_plugins = []
        if "config" in changes:
            self.__logger.debug(f"Saving config via API: {self.__config}")
            err = self._api.save_config(self.__config, "autoconf", changed=False, disable_cleanup=self._disable_cleanup)
            if isinstance(err, str):
                success = False
                self.__logger.error(f"Can't save config via API: {err}, config may not work as expected")
            else:
                changed_plugins = err

        # save custom configs via API
        if "custom_configs" in changes:
            self.__logger.debug(f"Saving custom configs via API: {custom_configs}")
            err = self._api.save_custom_configs(custom_configs, "autoconf", changed=False, disable_cleanup=self._disable_cleanup)
            if err:
                success = False
                self.__logger.error(f"Can't save autoconf custom configs via API: {err}, custom configs may not work as expected")

        # signal changes via API -- only when there is something to signal. An EMPTY list is not
        # "no changes" by the time it reaches the database: Database.checked_changes() starts with
        # `changes = changes or [<all seven>]` so that callers passing None mean "everything", and
        # an empty list is falsy too. Signalling [] therefore set all seven bw_metadata *_changed
        # flags, which makes the scheduler re-dispatch its whole job batch -- turning "nothing
        # happened" into the most expensive possible outcome. The `or [...]` default is right for
        # its other callers, so the guard belongs here, at the one call site that can produce [].
        if changes:
            ret = self._api.checked_changes(changes, plugins_changes=changed_plugins, value=True)
            if ret:
                self.__logger.error(f"An error occurred when setting the changes to checked via API : {ret}")

            self.__logger.info("Successfully saved new configuration 🚀")

        if success:
            # Record the settings baseline so the recheck worker only re-fires when the valid
            # settings set actually changes again (not after every normal apply).
            self._applied_settings_signature = frozenset(self._settings)

        return success

    def _check_api_available(self) -> bool:
        """Check if API is available and not readonly. Implements hybrid degraded mode.

        The readonly property on BaseApiClient catches ApiUnavailableError internally
        and returns True. So when readonly returns True, we ping() to distinguish
        'DB is genuinely read-only' from 'API is unreachable'.
        """
        if not self._api_available:
            try:
                self._api.ping()
                self._api_available = True
                self.__logger.info("API connection recovered, resuming normal operation")
            except ApiUnavailableError:
                self.__logger.warning("API is still unavailable, configuration will not be saved")
                return False

        if self._api.readonly:
            # readonly returns True either because DB is read-only OR because API is unreachable.
            # Use ping() to distinguish the two cases.
            try:
                self._api.ping()
                # API is up but DB is genuinely read-only
                self.__logger.error("API reports read-only mode, configuration will not be saved")
            except ApiUnavailableError:
                # API is actually down — enter degraded mode
                self._api_available = False
                self.__logger.error("API became unavailable, entering degraded mode")
            return False

        return True
