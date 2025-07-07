from json import JSONDecodeError, loads
from re import match
from threading import Thread
from time import time
from typing import Dict, Literal, Optional
from os import getenv, sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for configs module")

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required
from werkzeug.utils import secure_filename

from app.dependencies import BW_CONFIG, DATA, DB
from app.utils import flash

from app.routes.utils import handle_error, verify_data_in_form, wait_applying


configs = Blueprint("configs", __name__)

CONFIG_TYPES = {
    "HTTP": {"context": "global", "description": "Configurations at the HTTP level of NGINX."},
    "SERVER_HTTP": {"context": "multisite", "description": "Configurations at the HTTP/Server level of NGINX."},
    "DEFAULT_SERVER_HTTP": {
        "context": "global",
        "description": 'Configurations at the Server level of NGINX, specifically for the "default server" when the supplied client name doesn\'t match any server name in SERVER_NAME.',
    },
    "MODSEC_CRS": {"context": "multisite", "description": "Configurations applied before the OWASP Core Rule Set is loaded."},
    "MODSEC": {
        "context": "multisite",
        "description": "Configurations applied after the OWASP Core Rule Set is loaded, or used when the Core Rule Set is not loaded.",
    },
    "STREAM": {"context": "global", "description": "Configurations at the Stream level of NGINX."},
    "SERVER_STREAM": {"context": "multisite", "description": "Configurations at the Stream/Server level of NGINX."},
    "CRS_PLUGINS_BEFORE": {"context": "multisite", "description": "Configurations applied before the OWASP Core Rule Set plugins are loaded."},
    "CRS_PLUGINS_AFTER": {"context": "multisite", "description": "Configurations applied after the OWASP Core Rule Set plugins are loaded."},
}


# Display comprehensive custom configurations management interface with advanced filtering.
# Renders configuration list with service-specific filtering, template management, and current
# selection state preservation while providing access to all NGINX and ModSecurity configuration types.
@configs.route("/configs", methods=["GET"])
@login_required
def configs_page():
    if DEBUG_MODE:
        logger.debug("configs_page() called - initializing configurations management interface")
        logger.debug(f"URL parameters - service filter: '{service}', type filter: '{config_type}'")
        logger.debug("Retrieving configurations, services, and templates from database")
    
    service = request.args.get("service", "")
    config_type = request.args.get("type", "")
    
    if DEBUG_MODE:
        logger.debug(f"Service filter: '{service}', Type filter: '{config_type}'")
    
    try:
        configs = DB.get_custom_configs(with_drafts=True, with_data=False)
        server_name_config = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"]
        templates = DB.get_templates()
        
        if DEBUG_MODE:
            logger.debug(f"Database query results:")
            logger.debug(f"  - Custom configurations: {len(configs)} entries")
            logger.debug(f"  - Server names configuration: '{server_name_config}'")
            logger.debug(f"  - Available templates: {[t for t in templates if t != 'ui']}")
            logger.debug(f"  - Config types available: {len(CONFIG_TYPES)} types")
            logger.debug("Rendering configs.html template with filtered data")
        
        return render_template(
            "configs.html",
            configs=configs,
            services=server_name_config,
            db_templates=" ".join([template for template in templates if template != "ui"]),
            config_service=service,
            config_type=config_type,
        )
    except Exception as e:
        logger.exception("Error retrieving configurations")
        if DEBUG_MODE:
            logger.debug(f"Failed to retrieve configs: {type(e).__name__}: {e}")
        return handle_error("Failed to retrieve configurations", "configs")


# Delete selected custom configurations with comprehensive validation and secure processing.
# Processes JSON configuration list, validates UI-managed status, and removes configurations
# asynchronously while preserving non-UI configurations and providing detailed user feedback.
@configs.route("/configs/delete", methods=["POST"])
@login_required
def configs_delete():
    if DEBUG_MODE:
        logger.debug("configs_delete() called - processing configuration deletion request")
        logger.debug(f"Request method: POST, Form fields: {list(request.form.keys())}")
        logger.debug("Validating database access and configuration parameters")
    
    if DB.readonly:
        if DEBUG_MODE:
            logger.debug("Database is in read-only mode")
        return handle_error("Database is in read-only mode", "configs")

    verify_data_in_form(
        data={"configs": None},
        err_message="Missing configs parameter on /configs/delete.",
        redirect_url="configs",
        next=True,
    )
    
    configs = request.form["configs"]
    if DEBUG_MODE:
        logger.debug(f"Raw configs parameter: '{configs[:100]}{'...' if len(configs) > 100 else ''}'")
    
    if not configs:
        if DEBUG_MODE:
            logger.debug("Empty configs parameter")
        return handle_error("No configs selected.", "configs", True)
    
    try:
        configs = loads(configs)
        if DEBUG_MODE:
            logger.debug(f"Successfully parsed JSON configuration data:")
            logger.debug(f"  - Number of configurations: {len(configs)}")
            logger.debug(f"  - Configuration types: {set(c.get('type', 'unknown') for c in configs)}")
            logger.debug(f"  - Services involved: {set(c.get('service', 'unknown') for c in configs)}")
    except JSONDecodeError as e:
        logger.exception("Critical JSON parsing failure in configuration deletion")
        if DEBUG_MODE:
            logger.debug(f"JSON parsing error details: {e}")
            logger.debug(f"Error position: line {e.lineno}, column {e.colno}")
        return handle_error("Invalid configs parameter on /configs/delete.", "configs", True)
    
    DATA.load_from_file()
    if DEBUG_MODE:
        logger.debug("Successfully loaded application DATA for background processing")
        logger.debug("Initiating background thread for secure configuration deletion")

    # Execute comprehensive configuration deletion with UI validation and database integrity.
    # Filters UI-managed configurations, validates permissions, maintains non-UI configurations,
    # and provides detailed feedback through flash messaging system for user awareness.
    def delete_configs(configs: Dict[str, str]):
        if DEBUG_MODE:
            logger.debug(f"delete_configs() background thread initiated")
            logger.debug(f"Processing deletion request for {len(configs)} configurations")
            logger.debug("Waiting for application state synchronization")

        wait_applying()

        # Retrieve all custom configurations including drafts for comprehensive analysis
        db_configs = DB.get_custom_configs(with_drafts=True)
        new_db_configs = []
        configs_to_delete = set()
        non_ui_configs = set()
        
        if DEBUG_MODE:
            logger.debug(f"Database state analysis:")
            logger.debug(f"  - Total configurations in database: {len(db_configs)}")
            logger.debug(f"  - Configurations to process: {len(configs)}")
            logger.debug("Beginning configuration matching and validation process")

        # Process each database configuration against deletion requests with security validation
        for db_config in db_configs:
            # Generate unique configuration identifier for tracking and user feedback
            key = f"{(db_config['service_id'] + '/') if db_config['service_id'] else ''}{db_config['type']}/{db_config['name']}"
            keep = True
            
            # Match against deletion requests with normalized service comparison
            for config in configs:
                # Normalize service comparison: treat "global" string as None for consistency
                config_service = config["service"] if config["service"] != "global" else None
                if db_config["name"] == config["name"] and db_config["service_id"] == config_service and db_config["type"] == config["type"]:
                    if DEBUG_MODE:
                        logger.debug(f"Configuration match found for deletion analysis:")
                        logger.debug(f"  - Key: {key}")
                        logger.debug(f"  - Method: {db_config['method']}")
                        logger.debug(f"  - Service: {db_config['service_id'] or 'global'}")
                    
                    # Validate UI management status to prevent deletion of system configurations
                    if db_config["method"] != "ui":
                        non_ui_configs.add(key)
                        if DEBUG_MODE:
                            logger.debug(f"Configuration {key} is system-managed - preserving for security")
                        continue
                    
                    configs_to_delete.add(key)
                    keep = False
                    if DEBUG_MODE:
                        logger.debug(f"Configuration {key} approved for deletion")
                    break
            
            # Preserve configurations that are not templates and not marked for deletion
            if db_config.pop("template", None) or not keep:
                continue
            new_db_configs.append(db_config)

        # Generate user notifications for non-UI configurations that cannot be deleted
        for non_ui_config in non_ui_configs:
            DATA["TO_FLASH"].append(
                {
                    "content": f"Custom config {non_ui_config} is not a UI custom config and will not be deleted.",
                    "type": "error",
                }
            )

        # Validate deletion operation and handle edge cases
        if not configs_to_delete:
            DATA["TO_FLASH"].append({"content": "All selected custom configs could not be found or are not UI custom configs.", "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            if DEBUG_MODE:
                logger.debug("Deletion operation cancelled - no valid configurations found:")
                logger.debug(f"  - Non-UI configs: {len(non_ui_configs)}")
                logger.debug(f"  - Requested configs: {len(configs)}")
                logger.debug("Returning without database modifications")
            return

        if DEBUG_MODE:
            logger.debug(f"Deletion validation completed:")
            logger.debug(f"  - Configurations to delete: {len(configs_to_delete)}")
            logger.debug(f"  - Configurations to preserve: {len(new_db_configs)}")
            logger.debug(f"  - Non-UI configurations protected: {len(non_ui_configs)}")
            logger.debug("Proceeding with database update operation")

        # Execute database update with remaining configurations
        error = DB.save_custom_configs(new_db_configs, "ui")
        if error:
            DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {error}", "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            logger.exception("Critical database error during configuration deletion")
            if DEBUG_MODE:
                logger.debug(f"Database save operation failed: {error}")
            return
        
        DATA["TO_FLASH"].append({"content": f"Deleted config{'s' if len(configs_to_delete) > 1 else ''}: {', '.join(configs_to_delete)}", "type": "success"})
        DATA["RELOADING"] = False
        
        if DEBUG_MODE:
            logger.debug(f"Configuration deletion completed successfully:")
            logger.debug(f"  - Deleted configurations: {list(configs_to_delete)}")
            logger.debug(f"  - Database consistency maintained")
            logger.debug("Background thread processing completed")

    DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
    Thread(target=delete_configs, args=(configs,)).start()
    
    if DEBUG_MODE:
        logger.debug("Background deletion thread started successfully")
        logger.debug("Redirecting to loading page with operation status")

    return redirect(
        url_for(
            "loading",
            next=url_for("configs.configs_page"),
            message=f"Deleting selected config{'s' if len(configs) > 1 else ''}",
        )
    )


# Create new custom configuration with validation and service assignment.
# Handles GET for form display and POST for configuration creation and validation.
@configs.route("/configs/new", methods=["GET", "POST"])
@login_required
def configs_new():
    if DEBUG_MODE:
        logger.debug(f"configs_new() called with method: {request.method}")
    
    if request.method == "POST":
        if DEBUG_MODE:
            logger.debug("Processing POST request for new config creation")
            logger.debug(f"Form fields: {list(request.form.keys())}")
        
        if DB.readonly:
            if DEBUG_MODE:
                logger.debug("Database is in read-only mode")
            return handle_error("Database is in read-only mode", "configs")

        verify_data_in_form(
            data={"service": None},
            err_message="Missing service parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        service = request.form["service"]
        if DEBUG_MODE:
            logger.debug(f"Service: {service}")
        
        services = BW_CONFIG.get_config(global_only=True, with_drafts=True, methods=False, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(" ")
        if service != "global" and service not in services:
            if DEBUG_MODE:
                logger.debug(f"Invalid service: {service} not in {services}")
            return handle_error(f"Service {service} does not exist.", "configs.configs_new", True)

        verify_data_in_form(
            data={"type": None},
            err_message="Missing type parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        config_type = request.form["type"]
        if DEBUG_MODE:
            logger.debug(f"Config type: {config_type}")
        
        if config_type not in CONFIG_TYPES:
            if DEBUG_MODE:
                logger.debug(f"Invalid config type: {config_type}")
            return handle_error("Invalid type parameter on /configs/new.", "configs.configs_new", True)

        verify_data_in_form(
            data={"name": None},
            err_message="Missing name parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        config_name = request.form["name"]
        if DEBUG_MODE:
            logger.debug(f"Config name: {config_name}")
        
        if not match(r"^[\w_-]{1,64}$", config_name):
            if DEBUG_MODE:
                logger.debug(f"Invalid config name format: {config_name}")
            return handle_error("Invalid name parameter on /configs/new.", "configs.configs_new", True)

        verify_data_in_form(
            data={"value": None},
            err_message="Missing value parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        config_value = request.form["value"].replace("\r\n", "\n").strip()
        if DEBUG_MODE:
            logger.debug(f"Config value length: {len(config_value)} characters")
        
        DATA.load_from_file()

        # Create new custom configuration with type validation and database storage.
        # Handles service assignment and provides user feedback through flash messages.
        def create_config(
            service: Optional[str],
            config_type: Literal[
                "HTTP", "SERVER_HTTP", "DEFAULT_SERVER_HTTP", "MODSEC_CRS", "MODSEC", "STREAM", "SERVER_STREAM", "CRS_PLUGINS_BEFORE", "CRS_PLUGINS_AFTER"
            ],
            config_name: str,
            config_value: str,
        ):
            if DEBUG_MODE:
                logger.debug(f"create_config() thread started: {config_type}/{config_name}")
            
            wait_applying()
            config_type = config_type.lower()

            new_config = {
                "type": config_type,
                "name": config_name,
                "data": config_value,
                "method": "ui",
            }
            if service != "global":
                new_config["service_id"] = service
            
            if DEBUG_MODE:
                logger.debug(f"New config structure: {list(new_config.keys())}")

            error = DB.upsert_custom_config(config_type, config_name, new_config, service_id=new_config.get("service_id"), new=True)
            if error:
                if error == "The custom config already exists":
                    DATA["TO_FLASH"].append(
                        {
                            "content": f"Config {config_type}/{config_name}{' for service ' + service if service else ''} already exists",
                            "type": "error",
                        }
                    )
                    DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                    if DEBUG_MODE:
                        logger.debug("Config already exists - operation cancelled")
                    return
                
                logger.exception("Failed to create custom config")
                DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {error}", "type": "error"})
                return
            
            DATA["TO_FLASH"].append(
                {
                    "content": f"Created custom configuration {config_type}/{config_name}{' for service ' + service if service else ''}",
                    "type": "success",
                }
            )
            DATA["RELOADING"] = False
            
            if DEBUG_MODE:
                logger.debug("Config created successfully")

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        Thread(target=create_config, args=(service if service != "global" else None, config_type, config_name, config_value)).start()
        
        if DEBUG_MODE:
            logger.debug("Started background creation thread")

        return redirect(
            url_for(
                "loading",
                next=url_for("configs.configs_edit", service="global" if service == "global" else service, config_type=config_type.lower(), name=config_name),
                message=f"Creating custom configuration {config_type}/{config_name}{' for service' + service if service != 'global' else ''}",
            )
        )

    # Handle GET request for new config form with optional cloning
    clone = request.args.get("clone", "")
    config_service = ""
    config_type = ""
    config_name = ""

    if clone:
        if DEBUG_MODE:
            logger.debug(f"Cloning config: {clone}")
        
        config_service, config_type, config_name = clone.split("/")
        db_custom_config = DB.get_custom_config(config_type, config_name, service_id=config_service if config_service != "global" else None, with_data=True)
        clone = db_custom_config.get("data", b"").decode("utf-8")
        
        if DEBUG_MODE:
            logger.debug(f"Cloned config data length: {len(clone)} characters")
    
    return render_template(
        "config_edit.html",
        config_types=CONFIG_TYPES,
        config_value=clone,
        config_service=config_service,
        type=config_type.upper(),
        name=config_name,
        services=BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(" "),
    )


# Edit existing custom configuration with validation and change detection.
# Handles GET for form display and POST for configuration updates and validation.
@configs.route("/configs/<string:service>/<string:config_type>/<string:name>", methods=["GET", "POST"])
@login_required
def configs_edit(service: str, config_type: str, name: str):
    if DEBUG_MODE:
        logger.debug(f"configs_edit() called: service={service}, type={config_type}, name={name}, method={request.method}")
    
    if service == "global":
        service = None
    name = secure_filename(name)
    
    if DEBUG_MODE:
        logger.debug(f"Normalized parameters: service={service}, name={name}")

    db_config = DB.get_custom_config(config_type, name, service_id=service, with_data=True)
    if not db_config:
        if DEBUG_MODE:
            logger.debug("Config not found in database")
        return handle_error(f"Config {config_type}/{name}{' for service ' + service if service else ''} does not exist.", "configs", True)

    if DEBUG_MODE:
        logger.debug(f"Retrieved config: method={db_config['method']}, template={db_config.get('template', False)}")

    if request.method == "POST":
        if DEBUG_MODE:
            logger.debug("Processing POST request for config update")
        
        if DB.readonly:
            if DEBUG_MODE:
                logger.debug("Database is in read-only mode")
            return handle_error("Database is in read-only mode", "configs")

        if not db_config["template"] and db_config["method"] != "ui":
            if DEBUG_MODE:
                logger.debug("Config is not UI-managed and cannot be edited")
            return handle_error(
                f"Config {config_type}/{name}{' for service ' + service if service else ''} is not a UI custom config and cannot be edited.", "configs", True
            )

        verify_data_in_form(
            data={"service": None},
            err_message="Missing service parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        new_service = request.form["service"]
        services = BW_CONFIG.get_config(global_only=True, with_drafts=True, methods=False, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(" ")
        if new_service != "global" and new_service not in services:
            if DEBUG_MODE:
                logger.debug(f"Invalid new service: {new_service}")
            return handle_error(f"Service {new_service} does not exist.", "configs.configs_new", True)

        if new_service == "global":
            new_service = None

        verify_data_in_form(
            data={"type": None},
            err_message="Missing type parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        new_type = request.form["type"]
        if new_type not in CONFIG_TYPES:
            if DEBUG_MODE:
                logger.debug(f"Invalid new type: {new_type}")
            return handle_error("Invalid type parameter on /configs/new.", "configs.configs_new", True)
        new_type = new_type.lower()

        verify_data_in_form(
            data={"name": None},
            err_message="Missing name parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        new_name = secure_filename(request.form["name"])
        if not match(r"^[\w_-]{1,64}$", new_name):
            if DEBUG_MODE:
                logger.debug(f"Invalid new name format: {new_name}")
            return handle_error("Invalid name parameter on /configs/new.", "configs.configs_new", True)

        verify_data_in_form(
            data={"value": None},
            err_message="Missing value parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        config_value = request.form["value"].replace("\r\n", "\n").strip()
        DATA.load_from_file()

        # Check for changes to avoid unnecessary database operations
        if (
            db_config["type"] == new_type
            and db_config["name"] == new_name
            and db_config["service_id"] == new_service
            and db_config["data"].decode("utf-8") == config_value
        ):
            if DEBUG_MODE:
                logger.debug("No changes detected in config update")
            return handle_error("No values were changed.", "configs", True)

        if DEBUG_MODE:
            logger.debug(f"Updating config: {config_type}/{name} -> {new_type}/{new_name}")

        error = DB.upsert_custom_config(
            config_type,
            name,
            {
                "service_id": new_service,
                "type": new_type,
                "name": new_name,
                "data": config_value,
                "method": "ui",
            },
            service_id=service,
        )
        if error:
            logger.exception("Failed to update custom config")
            flash(f"An error occurred while saving the custom configs: {error}", "error")
        else:
            if DEBUG_MODE:
                logger.debug("Config updated successfully")
            flash(f"Saved custom configuration {new_type}/{new_name}{' for service ' + new_service if new_service else ''}")

        return redirect(
            url_for(
                "configs.configs_edit",
                service=new_service or "global",
                config_type=new_type,
                name=new_name,
            )
        )

    return render_template(
        "config_edit.html",
        config_types=CONFIG_TYPES,
        config_value=db_config["data"].decode("utf-8"),
        config_service=db_config.get("service_id"),
        type=db_config["type"].upper(),
        name=db_config["name"],
        config_method=db_config["method"],
        config_template=db_config.get("template"),
        services=BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(" "),
    )
