from json import JSONDecodeError, loads
from re import match
from threading import Thread
from time import time
from typing import Dict, Literal, Optional
from os import sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-configs",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-configs")

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


@configs.route("/configs", methods=["GET"])
@login_required
def configs_page():
    logger.debug("configs_page() called")
    
    service = request.args.get("service", "")
    config_type = request.args.get("type", "")
    logger.debug(f"Loading configs page with service='{service}', type='{config_type}'")
    
    configs_list = DB.get_custom_configs(with_drafts=True, with_data=False)
    services_config = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"]
    db_templates = DB.get_templates()
    
    logger.debug(f"Retrieved {len(configs_list)} custom configs, {len(db_templates)} templates")
    
    return render_template(
        "configs.html",
        configs=configs_list,
        services=services_config,
        db_templates=" ".join([template for template in db_templates if template != "ui"]),
        config_service=service,
        config_type=config_type,
    )


@configs.route("/configs/delete", methods=["POST"])
@login_required
def configs_delete():
    logger.debug("configs_delete() called")
    
    if DB.readonly:
        logger.debug("Database is in read-only mode, blocking config deletion")
        return handle_error("Database is in read-only mode", "configs")

    verify_data_in_form(
        data={"configs": None},
        err_message="Missing configs parameter on /configs/delete.",
        redirect_url="configs",
        next=True,
    )
    
    configs_param = request.form["configs"]
    if not configs_param:
        logger.debug("No configs selected for deletion")
        return handle_error("No configs selected.", "configs", True)
    
    try:
        configs = loads(configs_param)
        logger.debug(f"Parsed {len(configs)} configs for deletion")
    except JSONDecodeError:
        logger.exception("Invalid JSON in configs parameter")
        return handle_error("Invalid configs parameter on /configs/delete.", "configs", True)
    
    DATA.load_from_file()

    # Delete specified custom configurations with validation and error handling.
    # Filters UI configs from non-UI configs and provides appropriate feedback.
    def delete_configs(configs: Dict[str, str]):
        logger.debug("Starting config deletion in background thread")
        wait_applying()

        db_configs = DB.get_custom_configs(with_drafts=True)
        new_db_configs = []
        configs_to_delete = set()
        non_ui_configs = set()

        logger.debug(f"Processing {len(db_configs)} existing configs for deletion")

        for db_config in db_configs:
            key = f"{(db_config['service_id'] + '/') if db_config['service_id'] else ''}{db_config['type']}/{db_config['name']}"
            keep = True
            for config in configs:
                # Normalize service comparison: treat "global" string as None
                config_service = config["service"] if config["service"] != "global" else None
                if db_config["name"] == config["name"] and db_config["service_id"] == config_service and db_config["type"] == config["type"]:
                    if db_config["method"] != "ui":
                        non_ui_configs.add(key)
                        logger.debug(f"Skipping non-UI config: {key}")
                        continue
                    configs_to_delete.add(key)
                    logger.debug(f"Marking config for deletion: {key}")
                    keep = False
                    break
            if db_config.pop("template", None) or not keep:
                continue
            new_db_configs.append(db_config)

        for non_ui_config in non_ui_configs:
            DATA["TO_FLASH"].append(
                {
                    "content": f"Custom config {non_ui_config} is not a UI custom config and will not be deleted.",
                    "type": "error",
                }
            )

        if not configs_to_delete:
            logger.debug("No valid UI configs found for deletion")
            DATA["TO_FLASH"].append({"content": "All selected custom configs could not be found or are not UI custom configs.", "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            return

        logger.debug(f"Deleting {len(configs_to_delete)} configs: {configs_to_delete}")
        error = DB.save_custom_configs(new_db_configs, "ui")
        if error:
            logger.exception(f"Failed to save configs after deletion: {error}")
            DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {error}", "type": "error"})
            DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
            return
        
        logger.info(f"Successfully deleted configs: {configs_to_delete}")
        DATA["TO_FLASH"].append({"content": f"Deleted config{'s' if len(configs_to_delete) > 1 else ''}: {', '.join(configs_to_delete)}", "type": "success"})
        DATA["RELOADING"] = False
        logger.debug("Config deletion thread completed")

    DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
    Thread(target=delete_configs, args=(configs,)).start()

    return redirect(
        url_for(
            "loading",
            next=url_for("configs.configs_page"),
            message=f"Deleting selected config{'s' if len(configs) > 1 else ''}",
        )
    )


@configs.route("/configs/new", methods=["GET", "POST"])
@login_required
def configs_new():
    logger.debug(f"configs_new() called with method: {request.method}")
    
    if request.method == "POST":
        logger.debug("Processing new config creation")
        
        if DB.readonly:
            logger.debug("Database is in read-only mode, blocking config creation")
            return handle_error("Database is in read-only mode", "configs")

        verify_data_in_form(
            data={"service": None},
            err_message="Missing service parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        service = request.form["service"]
        services = BW_CONFIG.get_config(global_only=True, with_drafts=True, methods=False, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(" ")
        if service != "global" and service not in services:
            logger.debug(f"Invalid service specified: {service}")
            return handle_error(f"Service {service} does not exist.", "configs.configs_new", True)

        verify_data_in_form(
            data={"type": None},
            err_message="Missing type parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        config_type = request.form["type"]
        if config_type not in CONFIG_TYPES:
            logger.debug(f"Invalid config type: {config_type}")
            return handle_error("Invalid type parameter on /configs/new.", "configs.configs_new", True)

        verify_data_in_form(
            data={"name": None},
            err_message="Missing name parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        config_name = request.form["name"]
        if not match(r"^[\w_-]{1,64}$", config_name):
            logger.debug(f"Invalid config name format: {config_name}")
            return handle_error("Invalid name parameter on /configs/new.", "configs.configs_new", True)

        verify_data_in_form(
            data={"value": None},
            err_message="Missing value parameter on /configs/new.",
            redirect_url="configs.configs_new",
            next=True,
        )
        config_value = request.form["value"].replace("\r\n", "\n").strip()
        
        logger.debug(f"Creating config: service={service}, type={config_type}, name={config_name}, value_length={len(config_value)}")
        DATA.load_from_file()

        # Create new custom configuration with validation and conflict checking.
        # Handles service-specific and global configurations with proper error handling.
        def create_config(
            service: Optional[str],
            config_type: Literal[
                "HTTP", "SERVER_HTTP", "DEFAULT_SERVER_HTTP", "MODSEC_CRS", "MODSEC", "STREAM", "SERVER_STREAM", "CRS_PLUGINS_BEFORE", "CRS_PLUGINS_AFTER"
            ],
            config_name: str,
            config_value: str,
        ):
            logger.debug("Starting config creation in background thread")
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

            logger.debug(f"Upserting config: {config_type}/{config_name}")
            error = DB.upsert_custom_config(config_type, config_name, new_config, service_id=new_config.get("service_id"), new=True)
            if error:
                if error == "The custom config already exists":
                    logger.debug(f"Config already exists: {config_type}/{config_name}")
                    DATA["TO_FLASH"].append(
                        {
                            "content": f"Config {config_type}/{config_name}{' for service ' + service if service else ''} already exists",
                            "type": "error",
                        }
                    )
                    DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                    return
                logger.exception(f"Failed to create config: {error}")
                DATA["TO_FLASH"].append({"content": f"An error occurred while saving the custom configs: {error}", "type": "error"})
                return
            
            logger.info(f"Created custom configuration {config_type}/{config_name}{' for service ' + service if service else ''}")
            DATA["TO_FLASH"].append(
                {
                    "content": f"Created custom configuration {config_type}/{config_name}{' for service ' + service if service else ''}",
                    "type": "success",
                }
            )
            DATA["RELOADING"] = False
            logger.debug("Config creation thread completed")

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        Thread(target=create_config, args=(service if service != "global" else None, config_type, config_name, config_value)).start()

        return redirect(
            url_for(
                "loading",
                next=url_for("configs.configs_edit", service="global" if service == "global" else service, config_type=config_type.lower(), name=config_name),
                message=f"Creating custom configuration {config_type}/{config_name}{' for service' + service if service != 'global' else ''}",
            )
        )

    # GET request - display new config form
    clone = request.args.get("clone", "")
    config_service = ""
    config_type = ""
    config_name = ""

    if clone:
        logger.debug(f"Cloning config from: {clone}")
        config_service, config_type, config_name = clone.split("/")
        db_custom_config = DB.get_custom_config(config_type, config_name, service_id=config_service if config_service != "global" else None, with_data=True)
        clone = db_custom_config.get("data", b"").decode("utf-8")
        logger.debug(f"Cloned config data length: {len(clone)}")
    
    return render_template(
        "config_edit.html",
        config_types=CONFIG_TYPES,
        config_value=clone,
        config_service=config_service,
        type=config_type.upper(),
        name=config_name,
        services=BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"].split(" "),
    )


@configs.route("/configs/<string:service>/<string:config_type>/<string:name>", methods=["GET", "POST"])
@login_required
def configs_edit(service: str, config_type: str, name: str):
    logger.debug(f"configs_edit() called: service={service}, type={config_type}, name={name}, method={request.method}")
    
    if service == "global":
        service = None
    name = secure_filename(name)

    db_config = DB.get_custom_config(config_type, name, service_id=service, with_data=True)
    if not db_config:
        logger.debug(f"Config not found: {config_type}/{name} for service {service}")
        return handle_error(f"Config {config_type}/{name}{' for service ' + service if service else ''} does not exist.", "configs", True)

    if request.method == "POST":
        logger.debug("Processing config edit")
        
        if DB.readonly:
            logger.debug("Database is in read-only mode, blocking config edit")
            return handle_error("Database is in read-only mode", "configs")

        if not db_config["template"] and db_config["method"] != "ui":
            logger.debug(f"Attempting to edit non-UI config: {config_type}/{name}")
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

        # Check for changes
        if (
            db_config["type"] == new_type
            and db_config["name"] == new_name
            and db_config["service_id"] == new_service
            and db_config["data"].decode("utf-8") == config_value
        ):
            logger.debug("No changes detected in config edit")
            return handle_error("No values were changed.", "configs", True)

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
            logger.exception(f"Failed to update config: {error}")
            flash(f"An error occurred while saving the custom configs: {error}", "error")
        else:
            logger.info(f"Saved custom configuration {new_type}/{new_name}{' for service ' + new_service if new_service else ''}")
            flash(f"Saved custom configuration {new_type}/{new_name}{' for service ' + new_service if new_service else ''}")

        return redirect(
            url_for(
                "configs.configs_edit",
                service=new_service or "global",
                config_type=new_type,
                name=new_name,
            )
        )

    # GET request - display edit form
    logger.debug(f"Loading config edit form for {config_type}/{name}")
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
