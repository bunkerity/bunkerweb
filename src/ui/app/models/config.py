#!/usr/bin/env python3

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from operator import itemgetter
from os import getenv, sep
from os.path import join
from sys import path as sys_path
from flask import flash
from json import loads as json_loads
from pathlib import Path
from re import error as RegexError, search as re_search
from typing import List, Literal, Optional, Set, Tuple, Union

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

from app.utils import get_blacklisted_settings

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for config module")


class Config:
    # Initialize Config with database and data connections for configuration management.
    # Loads plugin settings from filesystem and sets up regex validation controls for configuration processing.
    def __init__(self, db, data) -> None:
        if DEBUG_MODE:
            logger.debug("Config.__init__() called - initializing configuration manager")
        
        self.__settings = json_loads(Path(sep, "usr", "share", "bunkerweb", "settings.json").read_text(encoding="utf-8"))
        self.__db = db
        self.__data = data
        self.__ignore_regex_check = getenv("IGNORE_REGEX_CHECK", "no").lower() == "yes"
        
        if DEBUG_MODE:
            logger.debug(f"Config initialized - loaded {len(self.__settings)} settings, ignore_regex_check: {self.__ignore_regex_check}")

    # Generates the nginx configuration file from the given configuration
    # Processes global and service configurations with multisite context handling and thread pool optimization.
    def gen_conf(
        self, global_conf: dict, services_conf: list[dict], *, check_changes: bool = True, changed_service: Optional[str] = None, override_method: str = "ui"
    ) -> Union[str, Set[str]]:
        # Generates the nginx configuration file from the given configuration
        #
        # Parameters
        # ----------
        # variables : dict
        #     The configuration to add to the file
        #
        # Raises
        # ------
        # ConfigGenerationError
        #     If an error occurred during the generation of the configuration file, raises this exception
        if DEBUG_MODE:
            logger.debug(f"gen_conf() called - global_conf keys: {len(global_conf)}, services: {len(services_conf)}, changed_service: {changed_service}")
        
        conf = global_conf.copy()

        servers = []
        plugins_settings = self.get_plugins_settings()

        if DEBUG_MODE:
            logger.debug(f"Retrieved {len(plugins_settings)} plugin settings for configuration generation")

        def process_service(service):
            server_name = service["SERVER_NAME"].split(" ")[0]
            if not server_name:
                if DEBUG_MODE:
                    logger.debug("Skipping service with empty SERVER_NAME")
                return None

            processed_settings = 0
            for k, v in service.items():
                if server_name != changed_service and f"{server_name}_{k}" in conf:
                    continue

                if plugins_settings[k.rsplit("_", 1)[0] if re_search(r"_\d+$", k) else k]["context"] == "multisite":
                    conf[f"{server_name}_{k}"] = v
                    processed_settings += 1

            if DEBUG_MODE:
                logger.debug(f"Processed service {server_name}: {processed_settings} multisite settings")
            return server_name

        with ThreadPoolExecutor() as executor:
            results = executor.map(process_service, services_conf)

        servers.extend(filter(None, results))

        if servers:
            conf["SERVER_NAME"] = " ".join(servers)
            if DEBUG_MODE:
                logger.debug(f"Set SERVER_NAME to: {conf['SERVER_NAME']}")
        conf["DATABASE_URI"] = self.__db.database_uri

        if DEBUG_MODE:
            logger.debug(f"Final configuration has {len(conf)} settings, saving with method: {override_method}")

        return self.__db.save_config(conf, override_method, changed=check_changes)

    # Get all plugin settings combined with base settings.
    # Merges plugin-specific settings with core BunkerWeb settings for comprehensive configuration validation.
    def get_plugins_settings(self) -> dict:
        if DEBUG_MODE:
            logger.debug("get_plugins_settings() called")
        
        plugins_dict = self.get_plugins()
        plugin_settings = {k: v for x in plugins_dict.values() for k, v in x["settings"].items()}
        combined_settings = {**plugin_settings, **self.__settings}
        
        if DEBUG_MODE:
            logger.debug(f"Combined {len(plugin_settings)} plugin settings with {len(self.__settings)} base settings")
        
        return combined_settings

    # Get plugins with optional filtering by type and data inclusion.
    # Retrieves plugin information from database with sorting and optional data payload for UI rendering.
    def get_plugins(self, *, _type: Literal["all", "external", "ui", "pro"] = "all", with_data: bool = False) -> dict:
        if DEBUG_MODE:
            logger.debug(f"get_plugins() called with type: {_type}, with_data: {with_data}")
        
        db_plugins = self.__db.get_plugins(_type=_type, with_data=with_data)
        db_plugins.sort(key=itemgetter("name"))

        plugins = {"general": {}}

        for plugin in db_plugins.copy():
            plugins[plugin.pop("id")] = plugin

        if DEBUG_MODE:
            logger.debug(f"Retrieved {len(plugins)} plugins from database")

        return plugins

    # Get base BunkerWeb settings dictionary.
    # Returns core settings loaded from settings.json for configuration validation and processing.
    def get_settings(self) -> dict:
        if DEBUG_MODE:
            logger.debug(f"get_settings() called - returning {len(self.__settings)} settings")
        return self.__settings

    # Get the nginx variables env file and returns it as a dict
    # Retrieves non-default configuration settings with optional filtering and draft inclusion for UI display.
    def get_config(
        self,
        global_only: bool = False,
        methods: bool = True,
        with_drafts: bool = False,
        filtered_settings: Optional[Union[List[str], Set[str], Tuple[str]]] = None,
    ) -> dict:
        # Get the nginx variables env file and returns it as a dict
        #
        # Returns
        # -------
        # dict
        #     The nginx variables env file as a dict
        if DEBUG_MODE:
            logger.debug(f"get_config() called - global_only: {global_only}, methods: {methods}, with_drafts: {with_drafts}")
        
        config = self.__db.get_non_default_settings(global_only=global_only, methods=methods, with_drafts=with_drafts, filtered_settings=filtered_settings)
        
        if DEBUG_MODE:
            logger.debug(f"Retrieved configuration with {len(config)} settings")
        
        return config

    # Get nginx's services
    # Retrieves service configurations from database with method and draft filtering for service management.
    def get_services(self, methods: bool = True, with_drafts: bool = False) -> list[dict]:
        # Get nginx's services
        #
        # Returns
        # -------
        # list
        #     The services
        if DEBUG_MODE:
            logger.debug(f"get_services() called - methods: {methods}, with_drafts: {with_drafts}")
        
        services = self.__db.get_services_settings(methods=methods, with_drafts=with_drafts)
        
        if DEBUG_MODE:
            logger.debug(f"Retrieved {len(services)} services from database")
        
        return services

    # Validate and filter variables based on allowed settings and patterns.
    # Performs comprehensive validation including blacklist checking, regex validation, and method permissions with error reporting.
    def check_variables(self, variables: dict, config: dict, to_check: dict, *, global_config: bool = False, new: bool = False, threaded: bool = False) -> dict:
        # Validate and filter variables based on allowed settings and patterns.
        #
        # This function checks each variable from 'to_check' to determine if it is editable:
        #  - Variables on the blacklist are removed.
        #  - Variables not defined in the plugin settings (or not matching the allowed multiple format)
        #    are considered invalid and removed.
        #  - Variables managed by a non-user method (i.e. not 'default' or 'ui') are not editable
        #    and are removed.
        #  - Each variable's value is validated against the regex provided in the plugin settings.
        #    A RegexError will also result in the variable being removed.
        #
        # Error messages are either flashed immediately (non-threaded) or appended to
        # self.__data["TO_FLASH"] (threaded).
        if DEBUG_MODE:
            logger.debug(f"check_variables() called - variables: {len(variables)}, to_check: {len(to_check)}, global_config: {global_config}, new: {new}")
        
        self.__data.load_from_file()
        plugins_settings = self.get_plugins_settings()
        blacklisted_settings = get_blacklisted_settings(global_config)

        if DEBUG_MODE:
            logger.debug(f"Loaded {len(blacklisted_settings)} blacklisted settings for validation")

        def report_error(message: str) -> None:
            if DEBUG_MODE:
                logger.debug(f"Validation error: {message}")
            
            if threaded:
                self.__data["TO_FLASH"].append({"content": message, "type": "error"})
            else:
                flash(message, "error")

        initial_count = len(variables)
        removed_count = 0

        # Iterate over a copy of the items to safely modify the dictionary.
        for key, value in to_check.items():
            # Remove blacklisted variables.
            if key in blacklisted_settings:
                report_error(f"Variable {key} is not editable, ignoring it.")
                variables.pop(key, None)
                removed_count += 1
                continue

            # Determine the base setting key.
            setting = key
            if key not in plugins_settings:
                if "_" not in key:
                    report_error(f"Variable {key} is not valid.")
                    variables.pop(key, None)
                    removed_count += 1
                    continue

                setting, suffix = key.rsplit("_", 1)
                if setting not in plugins_settings or "multiple" not in plugins_settings[setting] or not suffix.isdigit():
                    report_error(f"Variable {key} is not valid.")
                    variables.pop(key, None)
                    removed_count += 1
                    continue

            # Check if the variable is not editable because it is managed externally.
            if (
                not new
                and setting != "IS_DRAFT"
                and key in config
                and ((global_config or not config[key].get("global", False)) and config[key].get("method") not in ("default", "ui"))
            ):
                report_error(f"Variable {key} is not editable as it is managed by the {config[key]['method']}, ignoring it.")
                variables.pop(key, None)
                removed_count += 1
                continue

            # Validate the variable's value against the regex pattern.
            try:
                if not self.__ignore_regex_check and re_search(plugins_settings[setting]["regex"], value) is None:
                    report_error(f"Variable {key} is not valid.")
                    variables.pop(key, None)
                    removed_count += 1
            except RegexError as e:
                report_error(f"Invalid regex for setting {setting}: {plugins_settings[setting]['regex']}. Ignoring regex check: {e}")
                variables.pop(key, None)
                removed_count += 1

        if DEBUG_MODE:
            logger.debug(f"Variable validation completed - removed {removed_count}/{initial_count} invalid variables")

        return variables

    # Creates a new service from the given variables
    # Validates service uniqueness and generates configuration with draft support and change tracking.
    def new_service(self, variables: dict, is_draft: bool = False, override_method: str = "ui", check_changes: bool = True) -> Tuple[str, int]:
        # Creates a new service from the given variables
        #
        # Parameters
        # ----------
        # variables : dict
        #     The settings for the new service
        #
        # Returns
        # -------
        # str
        #     The confirmation message
        #
        # Raises
        # ------
        # Exception
        #     raise this if the service already exists
        server_name = variables.get("SERVER_NAME", "Unknown")
        if DEBUG_MODE:
            logger.debug(f"new_service() called for {server_name} - is_draft: {is_draft}, method: {override_method}")
        
        services = self.get_services(methods=False, with_drafts=True)
        server_name_splitted = variables["SERVER_NAME"].split(" ")
        for service in services:
            if service["SERVER_NAME"] == variables["SERVER_NAME"] or service["SERVER_NAME"] in server_name_splitted:
                error_msg = f"Service {service['SERVER_NAME'].split(' ')[0]} already exists."
                if DEBUG_MODE:
                    logger.debug(f"Failed to create service {server_name}: {error_msg}")
                return error_msg, 1

        services.append(variables | {"IS_DRAFT": "yes" if is_draft else "no"})
        
        if DEBUG_MODE:
            logger.debug(f"Added new service {server_name} to services list, total services: {len(services)}")
        
        ret = self.gen_conf(
            self.get_config(methods=False), services, check_changes=False if not check_changes else not is_draft, override_method=override_method
        )
        if isinstance(ret, str):
            if DEBUG_MODE:
                logger.debug(f"Failed to generate configuration for new service {server_name}: {ret}")
            return ret, 1
        
        if DEBUG_MODE:
            logger.debug(f"Successfully created service: {server_name}")
        return f"Configuration for {variables['SERVER_NAME'].split(' ')[0]} has been generated.", 0

    # Edits a service
    # Updates existing service configuration with server name changes and configuration regeneration.
    def edit_service(
        self, old_server_name: str, variables: dict, *, check_changes: bool = True, is_draft: bool = False, override_method: str = "ui"
    ) -> Tuple[str, int]:
        # Edits a service
        #
        # Parameters
        # ----------
        # old_server_name : str
        #     The old server name
        # variables : dict
        #     The settings to change for the service
        #
        # Returns
        # -------
        # str
        #     the confirmation message
        new_server_name = variables.get("SERVER_NAME", "Unknown")
        if DEBUG_MODE:
            logger.debug(f"edit_service() called - old: {old_server_name}, new: {new_server_name}, is_draft: {is_draft}")
        
        services = self.get_services(methods=False, with_drafts=True)
        changed_server_name = old_server_name != variables["SERVER_NAME"]
        server_name_splitted = variables["SERVER_NAME"].split(" ")
        old_server_name_splitted = old_server_name.split(" ")
        
        if DEBUG_MODE:
            logger.debug(f"Server name changed: {changed_server_name}, processing {len(services)} existing services")
        
        for i, service in enumerate(deepcopy(services)):
            if service["SERVER_NAME"] == variables["SERVER_NAME"] or service["SERVER_NAME"] in server_name_splitted:
                if changed_server_name and service["SERVER_NAME"].split(" ")[0] != old_server_name_splitted[0]:
                    error_msg = f"Service {service['SERVER_NAME'].split(' ')[0]} already exists."
                    if DEBUG_MODE:
                        logger.debug(f"Failed to edit service {old_server_name}: {error_msg}")
                    return error_msg, 1
                services.pop(i)
            elif changed_server_name and (service["SERVER_NAME"] == old_server_name or service["SERVER_NAME"] in old_server_name_splitted):
                services.pop(i)

        services.append(variables | {"IS_DRAFT": "yes" if is_draft else "no"})
        config = self.get_config(global_only=True, methods=False)

        if changed_server_name and server_name_splitted[0] != old_server_name_splitted[0]:
            removed_keys = 0
            for k in config.copy():
                if k.startswith(old_server_name_splitted[0]):
                    config.pop(k)
                    removed_keys += 1
            
            if DEBUG_MODE:
                logger.debug(f"Removed {removed_keys} old configuration keys for {old_server_name_splitted[0]}")

        ret = self.gen_conf(config, services, check_changes=check_changes, changed_service=server_name_splitted[0], override_method=override_method)
        if isinstance(ret, str):
            if DEBUG_MODE:
                logger.debug(f"Failed to generate configuration for edited service {old_server_name}: {ret}")
            return ret, 1
        
        if DEBUG_MODE:
            logger.debug(f"Successfully edited service: {old_server_name} -> {new_server_name}")
        return f"Configuration for {old_server_name_splitted[0]} has been edited.", 0

    # Edits the global conf
    # Updates global configuration settings and regenerates configuration with all existing services.
    def edit_global_conf(self, variables: dict, *, check_changes: bool = True, override_method: str = "ui") -> Tuple[str, int]:
        # Edits the global conf
        #
        # Parameters
        # ----------
        # variables : dict
        #     The settings to change for the conf
        #
        # Returns
        # -------
        # str
        #     the confirmation message
        if DEBUG_MODE:
            logger.debug(f"edit_global_conf() called with {len(variables)} variables, method: {override_method}")
        
        ret = self.gen_conf(variables, self.get_services(methods=False, with_drafts=True), check_changes=check_changes, override_method=override_method)
        if isinstance(ret, str):
            if DEBUG_MODE:
                logger.debug(f"Failed to generate global configuration: {ret}")
            return ret, 1
        
        if DEBUG_MODE:
            logger.debug("Successfully edited global configuration")
        return "The global configuration has been edited.", 0

    # Deletes a service
    # Removes service configuration and cleans up associated settings with configuration regeneration.
    def delete_service(self, service_name: str, *, check_changes: bool = True, override_method: str = "ui") -> Tuple[str, int]:
        # Deletes a service
        #
        # Parameters
        # ----------
        # service_name : str
        #     The name of the service to edit
        #
        # Returns
        # -------
        # str
        #     The confirmation message
        #
        # Raises
        # ------
        # Exception
        #     raises this if the service_name given isn't found
        if DEBUG_MODE:
            logger.debug(f"delete_service() called for {service_name}, method: {override_method}")
        
        service_name = service_name.split(" ")[0]
        full_env = self.get_config(methods=False)
        services = self.get_services(methods=False, with_drafts=True)
        new_services = []
        found = False

        for service in services:
            if service["SERVER_NAME"].split(" ")[0] == service_name:
                found = True
                if DEBUG_MODE:
                    logger.debug(f"Found service {service_name} for deletion")
            else:
                new_services.append(service)

        if not found:
            if DEBUG_MODE:
                logger.debug(f"Failed to delete service {service_name}: not found")
            return f"Can't delete missing {service_name} configuration.", 1

        full_env["SERVER_NAME"] = " ".join([s for s in full_env["SERVER_NAME"].split(" ") if s != service_name])

        new_env = full_env.copy()

        removed_keys = 0
        for k in full_env:
            if k.startswith(service_name):
                new_env.pop(k)
                removed_keys += 1

                for service in new_services:
                    if k in service:
                        service.pop(k)

        if DEBUG_MODE:
            logger.debug(f"Removed {removed_keys} configuration keys for service {service_name}")

        ret = self.gen_conf(new_env, new_services, check_changes=check_changes, override_method=override_method)
        if isinstance(ret, str):
            if DEBUG_MODE:
                logger.debug(f"Failed to generate configuration after deleting service {service_name}: {ret}")
            return ret, 1
        
        if DEBUG_MODE:
            logger.debug(f"Successfully deleted service: {service_name}")
        return f"Configuration for {service_name} has been deleted.", 0
