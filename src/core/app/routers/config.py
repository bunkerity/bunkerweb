# -*- coding: utf-8 -*-
from copy import deepcopy
from datetime import datetime
from functools import wraps
from json import dumps
from os.path import join, sep
from random import uniform
from re import match
from sys import path as sys_path
from typing import Callable, Dict, List, Literal, Optional, Tuple, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from fastapi import APIRouter, BackgroundTasks, status
from fastapi.responses import JSONResponse

from ..dependencies import CORE_CONFIG, DB, run_jobs, send_to_instances
from api_models import ErrorMessage  # type: ignore

router = APIRouter(
    prefix="/config",
    tags=["config"],
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is locked or had trouble handling the request",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
PLUGINS = DB.get_plugins()


def update_plugins(function: Optional[Callable] = None):
    """A decorator that also can be used as a context manager to update plugins"""

    @wraps(function)  # type: ignore
    def wrap(*args, **kwargs):
        global PLUGINS
        assert DB

        plugins = DB.get_plugins()

        if isinstance(plugins, str):
            CORE_CONFIG.logger.error(f"Can't get plugins from database : {plugins}, using old plugins")
        else:
            PLUGINS = plugins

        if function:
            return function(*args, **kwargs)

    if function:
        return wrap
    wrap()


def parse_config(config: Dict[str, str], *, whole: bool = False) -> Tuple[List[Dict[Literal["setting", "error"], str]], Dict[str, str]]:
    conflicts = []
    servers = []
    if whole:
        for server_name in config["SERVER_NAME"].strip().split(" "):
            if not match(r"^(?! )( ?((?=[^ ]{1,255}( |$))[^ ]+)(?!.* \2))*$", server_name):
                continue
            servers.append(server_name)

    for setting, value in deepcopy(config).items():
        found = False
        error = ""
        multiple = False
        raw_setting = setting
        for server_name in servers:
            if setting.startswith(server_name + "_"):
                setting = setting.replace(f"{server_name}_", "", 1)
                break
        if match("_[0-9]+$", setting):
            setting = setting.rsplit("_", 1)[0]
            multiple = True
        for plugin in PLUGINS:
            for plugin_setting, data in plugin["settings"].items():
                if plugin_setting == raw_setting:
                    multiple = False
                elif plugin_setting != setting:
                    continue
                found = True
                if multiple and "multiple" not in data:
                    error = f"Setting {raw_setting} is not multiple"
                    break
                if not match(data["regex"], value):
                    error = f"Value {value} for setting {raw_setting} doesn't match regex {data['regex']}"
                    break
            if error or found:
                break
        if not found:
            error = f"Setting {raw_setting} not found"
        if error:
            config.pop(raw_setting, None)
            conflicts.append({"setting": setting, "error": error})
    return conflicts, config


@router.get(
    "",
    response_model=Union[
        Dict[
            str,
            Union[str, Dict[Literal["value", "global", "method"], Union[str, bool]]],
        ],
        Dict[
            Literal["global", "services"],
            Dict[
                str,
                Dict[str, Union[str, Dict[Literal["value", "method"], str]]],
            ],
        ],
    ],
    summary="Get config from Database",
    response_description="BunkerWeb config",
)
async def get_config(background_tasks: BackgroundTasks, methods: bool = False, new_format: bool = False):
    """Get config from Database"""
    config = DB.get_config(methods=methods, new_format=new_format)

    if config == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't get config : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif isinstance(config, str):
        message = f"Can't get config : {config}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "GET", "method": "unknown", "tags": ["config"], "title": "Get config failed", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": config})

    return config


@update_plugins
@router.put(
    "",
    response_model=Dict[Literal["message"], Dict[Literal["data"], Dict[Literal["settings", "message"], Union[List[Dict[Literal["setting", "error"], str]], str]]]],
    summary="Update whole config in Database",
    response_description="Message",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Can't save config to database",
            "model": ErrorMessage,
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is locked or had trouble handling the request",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def update_config(config: Dict[str, str], method: str, background_tasks: BackgroundTasks) -> JSONResponse:
    """Update whole config in Database"""

    if method == "static":
        message = "Can't save config : method can't be static"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["config"], "title": "Trired to save config", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    conflicts, config = parse_config(config, whole=True)

    if conflicts and not config:
        message = f"Can't save config to database : {dumps(conflicts)}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["config"], "title": "Tried to save config", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": {"data": {"settings": conflicts, "message": "Can't save config to database"}}})

    resp = DB.save_config(config, method)

    if resp == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't save config to database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        message = f"Can't save config to database : {resp}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["config"], "title": "Tried to save config", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": resp})

    background_tasks.add_task(
        DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["config"], "title": "Config updated", "description": "Whole Config updated" + (f" with these conflicts : {dumps(conflicts)}" if conflicts else "")}
    )
    CORE_CONFIG.logger.info("✅ Config successfully saved to database")
    if conflicts:
        CORE_CONFIG.logger.warning(f"Conflicts : {dumps(conflicts)}")

    background_tasks.add_task(run_jobs)
    background_tasks.add_task(send_to_instances, {"config", "cache"})

    return JSONResponse(content={"message": {"data": {"settings": conflicts, "message": "Config successfully saved"}}})


@update_plugins
@router.put(
    "/global",
    response_model=Dict[Literal["message"], Dict[Literal["data"], Dict[Literal["settings", "message"], Union[List[Dict[Literal["setting", "error"], str]], str]]]],
    summary="Update global config in Database",
    response_description="Message",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Can't save global config to database",
            "model": ErrorMessage,
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is locked or had trouble handling the request",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def update_global_config(config: Dict[str, str], method: str, background_tasks: BackgroundTasks) -> JSONResponse:
    """Update global config in Database"""

    if method == "static":
        message = "Can't update global config : method can't be static"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["config"], "title": "Tried to update global config", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    conflicts, config = parse_config(config)

    if conflicts and not config:
        message = f"Can't save global config to database : {dumps(conflicts)}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["config"], "title": "Tried to update global config", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": {"data": {"settings": conflicts, "message": "Can't save global config to database"}}})

    resp = DB.save_global_config(config, method)

    if resp == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't save global config to database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        message = f"Can't save global config to database : {resp}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["config"], "title": "Tried to update global config", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": resp})

    background_tasks.add_task(
        DB.add_action,
        {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["config"], "title": "Global config updated", "description": f"Global Config updated with these data : {dumps(config)} and these conflicts : {dumps(conflicts)}"},
    )
    CORE_CONFIG.logger.info("✅ Global config successfully saved to database")
    if conflicts:
        CORE_CONFIG.logger.warning(f"Conflicts : {dumps(conflicts)}")

    background_tasks.add_task(run_jobs)
    background_tasks.add_task(send_to_instances, {"config", "cache"})

    return JSONResponse(content={"message": {"data": {"settings": conflicts, "message": "Global config successfully saved"}}})


@update_plugins
@router.put(
    "/service/{service_name}",
    response_model=Dict[Literal["message"], Dict[Literal["data"], Dict[Literal["settings", "message"], Union[List[Dict[Literal["setting", "error"], str]], str]]]],
    summary="Update a service config in Database",
    response_description="Message",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Can't save service config to database",
            "model": ErrorMessage,
        },
        status.HTTP_201_CREATED: {
            "description": "Service successfully created",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Not authorized to rename the service",
            "model": ErrorMessage,
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is locked or had trouble handling the request",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def update_service_config(service_name: str, config: Dict[str, str], method: str, background_tasks: BackgroundTasks) -> JSONResponse:
    """Update service config in Database"""

    if method == "static":
        message = f"Can't update {service_name} config : method can't be static"
        background_tasks.add_task(
            DB.add_action,
            {
                "date": datetime.now(),
                "api_method": "PUT",
                "method": method,
                "tags": ["config"],
                "title": f"Tried to update {service_name} service config",
                "description": f"Can't update {service_name} service config : method can't be static",
                "status": "error",
            },
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    conflicts, config = parse_config(config)

    if conflicts and not config:
        message = f"Can't save {service_name} service config to database : {dumps(conflicts)}"
        background_tasks.add_task(
            DB.add_action,
            {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["config"], "title": f"Tried to update {service_name} config", "description": message, "status": "error"},
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": {"data": {"settings": conflicts, "message": f"Can't save {service_name} service config to database"}}})

    resp = DB.save_service_config(service_name, config, method)

    if resp == "method_conflict":
        message = f"Can't rename service {service_name} because its method or one of its setting's method belongs to the core or the autoconf and the method isn't one of them"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["config"], "title": f"Tried to update {service_name} config", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif resp == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't save config for service {service_name} to database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp not in ("created", "updated"):
        message = f"Can't save service {service_name} config to database : {resp}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["config"], "title": f"Tried to update {service_name} config", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": resp})

    background_tasks.add_task(
        DB.add_action,
        {
            "date": datetime.now(),
            "api_method": "PUT",
            "method": method,
            "tags": ["config"],
            "title": "Upsert service config",
            "description": f"Service {service_name} Config {resp} with these data : {dumps(config)}" + (f"and these conflicts : {dumps(conflicts)}" if conflicts else ""),
        },
    )
    CORE_CONFIG.logger.info(f"✅ Service {service_name} config successfully {resp} to database")
    if conflicts:
        CORE_CONFIG.logger.warning(f"Conflicts : {dumps(conflicts)}")

    background_tasks.add_task(run_jobs)
    background_tasks.add_task(send_to_instances, {"config", "cache"})

    return JSONResponse(
        content={"message": {"data": {"settings": conflicts, "message": f"Service {service_name} config successfully {resp}"}}},
        status_code=200 if resp == "updated" else 201,
    )


@router.delete(
    "/service/{service_name}",
    response_model=Dict[Literal["message"], str],
    summary="Delete a service from the config in the Database",
    response_description="Message",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Service not found",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Not authorized to delete the service",
            "model": ErrorMessage,
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is locked or had trouble handling the request",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def delete_service_config(service_name: str, method: str, background_tasks: BackgroundTasks) -> JSONResponse:
    """Delete a service from the config in the Database"""

    if method == "static":
        message = f"Can't delete {service_name} config : method can't be static"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["config"], "title": f"Tried to delete {service_name} config", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    resp = DB.remove_service(service_name, method)

    if resp == "not_found":
        message = f"Can't delete {service_name} config : Service {service_name} not found"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["config"], "title": f"Tried to delete {service_name} config", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif resp == "method_conflict":
        message = f"Can't delete service {service_name} because it is either static or was created by the core or the autoconf and the method isn't one of them"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["config"], "title": f"Tried to delete {service_name} config", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif resp == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't delete service {service_name} from the database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        message = f"Can't delete service {service_name} from the database : {resp}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["config"], "title": f"Tried to delete {service_name} config", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": resp})

    background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["config"], "title": "Delete service", "description": f"Delete service {service_name}"})
    CORE_CONFIG.logger.info(f"✅ Service {service_name} successfully deleted from the database")

    background_tasks.add_task(run_jobs)
    background_tasks.add_task(send_to_instances, {"config", "cache"})

    return JSONResponse(content={"message": f"Service {service_name} successfully deleted"})
