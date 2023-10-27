from datetime import datetime
from random import uniform
from typing import Dict, List, Literal
from fastapi import APIRouter, BackgroundTasks, status
from fastapi.responses import JSONResponse

from ..models import CustomConfigModel, CustomConfigDataModel, ErrorMessage
from ..dependencies import CORE_CONFIG, DB, send_to_instances

router = APIRouter(prefix="/custom_configs", tags=["custom_configs"])


@router.get("", response_model=List[CustomConfigDataModel], summary="Get all custom configs", response_description="List of custom configs")
async def get_custom_configs():
    """
    Get all custom configs
    """
    return DB.get_custom_configs()


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
async def upsert_custom_config(custom_config: CustomConfigDataModel, method: str, background_tasks: BackgroundTasks, reload: bool = True):
    """Update one or more custom configs"""

    if method == "static":
        message = f"Can't upsert custom config {custom_config.name} : method can't be static"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    custom_config_data = custom_config.model_dump() | {"method": method}
    custom_config_data["config_type"] = custom_config_data.pop("type")
    resp = DB.upsert_custom_config(**custom_config_data)

    if resp == "method_conflict":
        message = (
            f"Can't upsert custom config {custom_config.name}"
            + (f" from service {custom_config.service_id}" if custom_config.service_id else "")
            + " because it is either static or was created by the core or the autoconf and the method isn't one of them"
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't upsert custom config: Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp and resp not in ("created", "updated"):
        CORE_CONFIG.logger.error(f"Can't upsert custom config: {resp}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    message = f"Custom config {custom_config.name} {resp}"

    background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["custom_config"], "title": "Updated custom configs", "description": message})
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
async def delete_custom_config(custom_config_name: str, custom_config: CustomConfigModel, method: str, background_tasks: BackgroundTasks):
    """Update a custom config"""

    if method == "static":
        message = f"Can't delete custom config {custom_config_name} : method can't be static"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    resp = DB.delete_custom_config(custom_config.service_id, custom_config.type, custom_config_name, method)

    if resp == "not_found":
        message = f"Custom config {custom_config_name} not found"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif resp == "method_conflict":
        message = (
            f"Can't delete custom config {custom_config_name}"
            + (f" from service {custom_config.service_id}" if custom_config.service_id else "")
            + " because it is either static or was created by the core or the autoconf and the method isn't one of them"
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't delete custom config: Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        CORE_CONFIG.logger.error(f"Can't delete custom config: {resp}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    background_tasks.add_task(
        DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["custom_config"], "title": f"Delete custom config {custom_config_name}", "description": f"Delete custom config {custom_config_name}"}
    )
    CORE_CONFIG.logger.info(f"✅ Custom config {custom_config_name} deleted from database")

    background_tasks.add_task(send_to_instances, {"custom_configs"})

    return JSONResponse(content={"message": f"Custom config {custom_config_name} deleted"})
