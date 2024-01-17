# -*- coding: utf-8 -*-
from datetime import datetime
from os.path import join, sep
from random import uniform
from sys import path as sys_path
from typing import Dict, List, Literal, Optional

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from fastapi import APIRouter, BackgroundTasks, status
from fastapi.responses import JSONResponse

from ..dependencies import CORE_CONFIG, DB, send_to_instances
from api_models import CustomConfigDataModel, ErrorMessage, UpsertCustomConfigDataModel  # type: ignore

router = APIRouter(
    prefix="/custom_configs",
    tags=["custom_configs"],
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


@router.get("", response_model=List[CustomConfigDataModel], summary="Get all custom configs", response_description="List of custom configs")
async def get_custom_configs(background_tasks: BackgroundTasks):
    """
    Get all custom configs
    """
    custom_configs = DB.get_custom_configs()

    if custom_configs == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't get custom config : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif isinstance(custom_configs, str):
        message = f"Can't get custom configs in database : {custom_configs}"
        background_tasks.add_task(
            DB.add_action,
            {"date": datetime.now(), "api_method": "GET", "method": "unknown", "tags": ["custom_config"], "title": "Get custom configs failed", "description": message, "status": "error"},
        )
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": custom_configs},
        )

    return custom_configs


@router.put(
    "",
    response_model=Dict[Literal["message"], str],
    summary="Update one custom config",
    response_description="Message",
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": "Not authorized to update the custom config",
            "model": ErrorMessage,
        },
        status.HTTP_201_CREATED: {
            "description": "Custom config successfully created",
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
async def upsert_custom_config(custom_config: UpsertCustomConfigDataModel, background_tasks: BackgroundTasks, reload: bool = True):
    """Update one or more custom configs"""

    if custom_config.method == "static":
        message = f"Can't upsert custom config {custom_config.name} : method can't be static"
        background_tasks.add_task(
            DB.add_action,
            {"date": datetime.now(), "api_method": "PUT", "method": custom_config.method, "tags": ["custom_config"], "title": f"Tried to update custom config {custom_config.name}", "description": message, "status": "error"},
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    custom_config_data = custom_config.model_dump()
    custom_config_data["config_type"] = custom_config_data.pop("type")
    resp = DB.upsert_custom_config(**custom_config_data)

    if resp == "method_conflict":
        message = (
            f"Can't upsert custom config {custom_config.name}"
            + (f" from service {custom_config.service_id}" if custom_config.service_id else "")
            + " because it is either static or was created by the core or the autoconf and the method isn't one of them"
        )
        background_tasks.add_task(
            DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": custom_config.method, "tags": ["custom_config"], "title": f"Tried to update custom config {custom_config.name}", "description": message, "status": "error"}
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif resp == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't upsert custom config: Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp and resp not in ("created", "updated"):
        message = f"Can't upsert custom config: {resp}"
        background_tasks.add_task(
            DB.add_action,
            {"date": datetime.now(), "api_method": "PUT", "method": custom_config.method, "tags": ["custom_config"], "title": f"Tried to update custom config {custom_config.name}", "description": message, "status": "error"},
        )
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    message = f"Custom config {custom_config.name} {resp}"

    background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": custom_config.method, "tags": ["custom_config"], "title": "Updated custom configs", "description": message})
    CORE_CONFIG.logger.info(f"✅ {message} in the database")

    if reload:
        background_tasks.add_task(send_to_instances, {"custom_configs"})

    return JSONResponse(status_code=status.HTTP_200_OK if resp == "updated" else status.HTTP_201_CREATED, content={"message": message})


@router.delete(
    "/{custom_config_name}",
    response_model=Dict[Literal["message"], str],
    summary="Delete a custom config",
    response_description="Message",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Custom config not found",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Not authorized to delete the custom config",
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
async def delete_custom_config(custom_config_name: str, method: str, config_type: str, background_tasks: BackgroundTasks, service_id: Optional[str] = None):
    """Delete a custom config"""

    if method == "static":
        message = f"Can't delete custom config {custom_config_name} : method can't be static"
        background_tasks.add_task(
            DB.add_action,
            {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["custom_config"], "title": f"Tried to delete custom config {custom_config_name}", "description": message, "status": "error"},
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    resp = DB.delete_custom_config(service_id, config_type, custom_config_name, method)

    if resp == "not_found":
        message = f"Custom config {custom_config_name}{' from service ' + service_id if service_id else ''} not found"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["custom_config"], "title": f"Tried to delete custom config {custom_config_name}", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif resp == "method_conflict":
        message = (
            f"Can't delete custom config {custom_config_name}{' from service ' + service_id if service_id else ''}"
            + (f" from service {service_id}" if service_id else "")
            + " because it is either static or was created by the core or the autoconf and the method isn't one of them"
        )
        background_tasks.add_task(
            DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["custom_config"], "title": f"Trired to delete custom config {custom_config_name}", "description": message, "status": "error"}
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif resp == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't delete custom config{' from service ' + service_id if service_id else ''}: Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        message = f"Can't delete custom config {custom_config_name}{' from service ' + service_id if service_id else ''}: {resp}"
        background_tasks.add_task(
            DB.add_action,
            {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["custom_config"], "title": f"Trired to delete custom config {custom_config_name}", "description": message, "status": "error"},
        )
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    background_tasks.add_task(
        DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["custom_config"], "title": f"Delete custom config {custom_config_name}", "description": f"Delete custom config {custom_config_name}"}
    )
    CORE_CONFIG.logger.info(f"✅ Custom config {custom_config_name}{' from service ' + service_id if service_id else ''} deleted from database")

    background_tasks.add_task(send_to_instances, {"custom_configs"})

    return JSONResponse(content={"message": f"Custom config {custom_config_name}{' from service ' + service_id if service_id else ''} deleted"})