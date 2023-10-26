from copy import deepcopy
from datetime import datetime
from functools import wraps
from json import dumps
from random import uniform
from re import match
from typing import Callable, Dict, List, Literal, Optional, Tuple, Union
from fastapi import APIRouter, BackgroundTasks, status
from fastapi.responses import JSONResponse

from ..models import ErrorMessage
from ..dependencies import CORE_CONFIG, DB, run_jobs, send_to_instances

router = APIRouter(prefix="/config", tags=["config"])
PLUGINS = DB.get_plugins()


def update_plugins(function: Optional[Callable] = None):
    """A decorator that also can be used as a context manager to update plugins"""

    @wraps(function)  # type: ignore (if function is None, no error is raised)
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


def parse_config(config: Dict[str, str]) -> Tuple[List[Dict[Literal["setting", "error"], str]], Dict[str, str]]:
    conflicts = []
    for setting, value in deepcopy(config.items()):
        found = False
        error = ""
        multiple = False
        raw_setting = setting
        if match("_[0-9]+$", setting):
            raw_setting = setting.rsplit("_", 1)[0]
            multiple = True
        for plugin in PLUGINS:
            for plugin_setting, data in PLUGINS[plugin]["settings"].items():
                if setting != plugin_setting:
                    continue
                found = True
                if multiple and "multiple" not in data:
                    error = f"Setting {setting} is not multiple"
                    break
                if not match(data["regex"], value):
                    error = f"Value {value} for setting {setting} doesn't match regex {data['regex']}"
                    break
            if error or found:
                break
        if not found:
            error = f"Setting {setting} not found"
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
async def get_config(methods: bool = False, new_format: bool = False):
    """Get config from Database"""
    return DB.get_config(methods=methods, new_format=new_format)


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
        message = "Can't update config : method can't be static"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    conflicts, config = parse_config(config)

    if conflicts and not config:
        CORE_CONFIG.logger.warning(f"Can't save config to database : {dumps(conflicts)}")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": {"data": {"settings": conflicts, "message": "Can't save config to database"}}})

    resp = DB.save_config(config, method)

    if "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't save config to database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        CORE_CONFIG.logger.error(f"Can't save config to database : {resp}")
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
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    conflicts, config = parse_config(config)

    if conflicts and not config:
        CORE_CONFIG.logger.warning(f"Can't save global config to database : {dumps(conflicts)}")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": {"data": {"settings": conflicts, "message": "Can't save global config to database"}}})

    resp = DB.save_global_config(config, method)

    if "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't save global config to database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        CORE_CONFIG.logger.error(f"Can't save global config to database : {resp}")
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
        status.HTTP_404_NOT_FOUND: {
            "description": "Service not found",
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
async def update_service_config(
    service_name: str,
    config: Dict[str, str],
    method: str,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """Update service config in Database"""

    if method == "static":
        message = f"Can't update {service_name} config : method can't be static"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    conflicts, config = parse_config(config)

    if conflicts and not config:
        CORE_CONFIG.logger.warning(f"Can't save {service_name} service config to database : {dumps(conflicts)}")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": {"data": {"settings": conflicts, "message": f"Can't save {service_name} service config to database"}}})

    resp = DB.save_service_config(service_name, config, method)

    if resp == "not_found":
        message = f"Service {service_name} not found"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif resp == "method_conflict":
        message = f"Can't rename service {service_name} because its method or one of its setting's method belongs to the core or the autoconf and the method isn't one of them"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't save config for service {service_name} to database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        CORE_CONFIG.logger.error(f"Can't save service {service_name} config to database : {resp}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": resp})

    background_tasks.add_task(
        DB.add_action,
        {
            "date": datetime.now(),
            "api_method": "PUT",
            "method": method,
            "tags": ["config"],
            "title": "Update service config",
            "description": f"Service {service_name} Config updated with these data : {dumps(config)} and these conflicts : {dumps(conflicts)}",
        },
    )
    CORE_CONFIG.logger.info(f"✅ Service {service_name} config successfully saved to database")
    if conflicts:
        CORE_CONFIG.logger.warning(f"Conflicts : {dumps(conflicts)}")

    background_tasks.add_task(run_jobs)
    background_tasks.add_task(send_to_instances, {"config", "cache"})

    return JSONResponse(content={"message": {"data": {"settings": conflicts, "message": f"Service {service_name} config successfully saved"}}})


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
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    resp = DB.remove_service(service_name, method)

    if resp == "not_found":
        message = f"Service {service_name} not found"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif resp == "method_conflict":
        message = f"Can't delete service {service_name} because it is either static or was created by the core or the autoconf and the method isn't one of them"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't delete service {service_name} from the database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        CORE_CONFIG.logger.error(f"Can't delete service {service_name} from the database : {resp}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": resp})

    background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["config"], "title": "Delete service", "description": f"Delete service {service_name}"})
    CORE_CONFIG.logger.info(f"✅ Service {service_name} successfully deleted from the database")

    background_tasks.add_task(run_jobs)
    background_tasks.add_task(send_to_instances, {"config", "cache"})

    return JSONResponse(content={"message": f"Service {service_name} successfully deleted"})
