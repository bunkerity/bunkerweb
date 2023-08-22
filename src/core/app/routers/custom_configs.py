from typing import Dict, List, Literal
from fastapi import APIRouter, BackgroundTasks, status
from fastapi.responses import JSONResponse

from ..models import (
    CustomConfigModel,
    CustomConfigDataModel,
    CustomConfigNameModel,
    ErrorMessage,
)
from ..dependencies import DB, LOGGER, send_to_instances

router = APIRouter(prefix="/custom_configs", tags=["custom_configs"])


@router.get(
    "",
    response_model=List[CustomConfigDataModel],
    summary="Get all custom configs",
    response_description="List of custom configs",
)
async def get_custom_configs():
    """
    Get all custom configs
    """
    return DB.get_custom_configs()


@router.put(
    "",
    response_model=Dict[Literal["message"], str],
    summary="Update a custom config",
    response_description="Message",
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": "Can't update a custom config created by the core or the autoconf if the method isn't one of them",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def update_custom_config(
    custom_config: CustomConfigNameModel, method: str, background_tasks: BackgroundTasks
):
    """Update a custom config"""
    err = DB.upsert_custom_config(custom_config.model_dump() | {"method": method})

    if err == "method_conflict":
        message = (
            f"Can't upsert custom config {custom_config.name}"
            + (
                f" from service {custom_config.service_id}"
                if custom_config.service_id
                else ""
            )
            + " because it was created by either the core or the autoconf and the method isn't one of them"
        )
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN, content={"message": message}
        )
    elif err and err not in ("created", "updated"):
        LOGGER.error(f"Can't upsert custom config: {err}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": err},
        )

    LOGGER.info(f"✅ Custom config {custom_config.name} {err} to database")

    background_tasks.add_task(send_to_instances, {"custom_configs"})

    return JSONResponse(
        status_code=status.HTTP_200_OK if err == "updated" else status.HTTP_201_CREATED,
        content={"message": f"Custom config {custom_config.name} {err}"},
    )


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
            "description": "Can't delete a custom config created by the core or the autoconf if the method isn't one of them",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def delete_custom_config(
    custom_config_name: str,
    custom_config: CustomConfigModel,
    method: str,
    background_tasks: BackgroundTasks,
):
    """Update a custom config"""
    err = DB.delete_custom_config(
        custom_config.service_id, custom_config.type, custom_config_name, method
    )

    if err == "not_found":
        message = f"Custom config {custom_config_name} not found"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"message": message}
        )
    elif err == "method_conflict":
        message = (
            f"Can't delete custom config {custom_config_name}"
            + (
                f" from service {custom_config.service_id}"
                if custom_config.service_id
                else ""
            )
            + " because it was created by either the core or the autoconf and the method isn't one of them"
        )
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN, content={"message": message}
        )
    elif err:
        LOGGER.error(f"Can't upsert custom config: {err}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": err},
        )

    LOGGER.info(f"✅ Custom config {custom_config_name} deleted from database")

    background_tasks.add_task(send_to_instances, {"custom_configs"})

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": f"Custom config {custom_config_name} deleted"},
    )
