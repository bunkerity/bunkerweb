from io import BytesIO
from tarfile import open as tar_open
from typing import Dict, List, Literal
from fastapi import APIRouter, BackgroundTasks, Response, status
from fastapi.responses import JSONResponse

from ..core import AddedPlugin, ErrorMessage, Plugin
from ..dependencies import (
    DB,
    LOGGER,
    EXTERNAL_PLUGINS_PATH,
    generate_external_plugins,
    inform_scheduler,
    update_app_mounts,
)

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get(
    "",
    response_model=List[Plugin],
    summary="Get all plugins",
    response_description="Plugins",
)
async def get_plugins():
    """
    Get core and external plugins from the database.
    """
    return DB.get_plugins()


@router.post(
    "",
    response_model=Dict[Literal["message"], str],
    status_code=status.HTTP_201_CREATED,
    summary="Add a plugin",
    response_description="Message",
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Plugin already exists",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def add_plugin(
    plugin: AddedPlugin, background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Add a plugin to the database.
    """
    error = DB.add_external_plugin(plugin.to_dict())

    if error == "exists":
        message = f"Plugin {plugin.id} already exists"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"message": message}
        )
    elif error:
        LOGGER.error(f"Can't add plugin to database : {error}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )

    background_tasks.add_task(inform_scheduler, {"type": "run_once"})
    background_tasks.add_task(
        generate_external_plugins, LOGGER, None, DB, original_path=EXTERNAL_PLUGINS_PATH
    )
    background_tasks.add_task(update_app_mounts, router)

    LOGGER.info(f"✅ Plugin {plugin.id} successfully added to database")

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"message": "Plugin successfully added"},
    )


@router.patch(
    "/{plugin_id}",
    response_model=Dict[Literal["message"], str],
    summary="Update a plugin",
    response_description="Message",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Plugin not found",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Can't update a core plugin",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def update_plugin(
    plugin_id: str, plugin: AddedPlugin, background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Update a plugin from the database.
    """
    error = DB.update_external_plugin(plugin_id, plugin.to_dict())

    if error == "not_found":
        message = f"Plugin {plugin.id} not found"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"message": message}
        )
    elif error == "not_external":
        message = f"Can't update a core plugin ({plugin.id})"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN, content={"message": message}
        )
    elif error:
        LOGGER.error(f"Can't update plugin to database : {error}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )

    background_tasks.add_task(inform_scheduler, {"type": "run_once"})
    background_tasks.add_task(
        generate_external_plugins, LOGGER, None, DB, original_path=EXTERNAL_PLUGINS_PATH
    )
    background_tasks.add_task(update_app_mounts, router)

    LOGGER.info(f"✅ Plugin {plugin.id} successfully updated to database")

    return JSONResponse(content={"message": "Plugin successfully updated"})


@router.delete(
    "/{plugin_id}",
    response_model=Dict[Literal["message"], str],
    summary="Delete a plugin",
    response_description="Message",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Plugin not found",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Can't delete a core plugin",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def delete_plugin(
    plugin_id: str, background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Delete a plugin from the database.
    """
    error = DB.remove_external_plugin(plugin_id)

    if error == "not_found":
        message = f"Plugin {plugin_id} not found"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"message": message}
        )
    elif error == "not_external":
        message = f"Can't delete a core plugin ({plugin_id})"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN, content={"message": message}
        )
    elif error:
        LOGGER.error(f"Can't delete plugin to database : {error}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )

    background_tasks.add_task(inform_scheduler, {"type": "run_once"})
    background_tasks.add_task(
        generate_external_plugins, LOGGER, None, DB, original_path=EXTERNAL_PLUGINS_PATH
    )
    background_tasks.add_task(update_app_mounts, router)

    LOGGER.info(f"✅ Plugin {plugin_id} successfully deleted from database")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Plugin successfully deleted"},
    )


@router.get(
    "/external/files",
    summary="Get all external plugins files in a tar archive",
    response_description="Tar archive containing all external plugins files",
)
async def get_plugins_files():
    """
    Get all external plugins files in a tar archive.
    """
    plugins_files = BytesIO()
    with tar_open(
        fileobj=plugins_files, mode="w:gz", compresslevel=9, dereference=True
    ) as tar:
        tar.add(
            str(EXTERNAL_PLUGINS_PATH),
            arcname=".",
            recursive=True,
        )
    plugins_files.seek(0, 0)

    return Response(
        content=plugins_files.getvalue(),
        media_type="application/x-tar",
        headers={"Content-Disposition": "attachment; filename=plugins.tar.gz"},
    )
