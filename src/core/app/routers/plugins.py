# -*- coding: utf-8 -*-
from datetime import datetime
from io import BytesIO
from json import dumps
from os.path import join, sep
from random import uniform
from sys import path as sys_path
from tarfile import open as tar_open
from typing import Dict, List, Literal, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from fastapi import APIRouter, BackgroundTasks, Response, status
from fastapi.responses import JSONResponse

from ..dependencies import CORE_CONFIG, DB, EXTERNAL_PLUGINS_PATH, generate_external_plugins, run_jobs, send_to_instances, update_app_mounts
from api_models import AddedPlugin, ErrorMessage, Plugin  # type: ignore

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get(
    "",
    response_model=List[Plugin],
    summary="Get all plugins",
    response_description="Plugins",
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
async def get_plugins(background_tasks: BackgroundTasks, external: bool = False):
    """
    Get core and external plugins from the database.
    """
    plugins = DB.get_plugins(external=external)

    if plugins == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't get plugins from database : database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif isinstance(plugins, str):
        message = f"Can't get plugins from database : {plugins}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "GET", "method": "unknown", "tags": ["plugin"], "title": "Get plugins failed", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": plugins},
        )

    return plugins


@router.get(
    "/{plugin_id}/page",
    summary="Get either a plugin page file",
    response_description="File",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Plugin not found or doesn't have a page",
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
async def get_plugin_page_file(plugin_id: str, background_tasks: BackgroundTasks):
    """
    Get either a plugin page.
    """
    plugin_page = DB.get_plugin_template(plugin_id)

    if not plugin_page:
        message = f"Plugin {plugin_id} not found or doesn't have a page"
        background_tasks.add_task(
            DB.add_action,
            {
                "date": datetime.now(),
                "api_method": "GET",
                "method": "unknown",
                "tags": ["plugin"],
                "title": f"Tried to get plugin {plugin_id} page",
                "description": message,
                "status": "error",
            },
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif plugin_page == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't get plugin {plugin_id} page from database : database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif isinstance(plugin_page, str):
        message = f"Can't get plugin {plugin_id} page from database : {plugin_page}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "GET", "method": "unknown", "tags": ["plugin"], "title": f"Tried to get plugin {plugin_id} page", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": plugin_page},
        )

    return Response(
        content=plugin_page,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={plugin_id}.html"},
    )


@router.post(
    "",
    response_model=Dict[Literal["message"], str],
    status_code=status.HTTP_201_CREATED,
    summary="Add one or more plugins",
    response_description="Message",
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Plugin already exists",
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
async def add_plugin(plugin: Union[AddedPlugin, List[AddedPlugin]], background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Add one or more plugins to the database.
    """
    if isinstance(plugin, list):
        resp = DB.update_external_plugins([plugin.model_dump() for plugin in plugin], delete_missing=False)
    else:
        plugin_dict = plugin.model_dump()
        resp = DB.upsert_external_plugin(plugin_dict.copy(), return_if_exists=True)
        plugin_dict.pop("data", None)
        plugin_dict.pop("template_file", None)
        plugin_dict.pop("actions_file", None)

        if resp == "exists":
            message = f"Plugin {plugin.id} already exists"
            background_tasks.add_task(
                DB.add_action,
                {
                    "date": datetime.now(),
                    "api_method": "POST",
                    "method": plugin.method,
                    "tags": ["plugin"],
                    "title": f"Tried to add plugin {plugin.id}",
                    "description": f"Tried to add plugin {plugin.id} with data {dumps(plugin_dict)} but it already exists",
                    "status": "error",
                },
            )
            CORE_CONFIG.logger.warning(message)
            return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"message": message})
        elif resp == "retry":
            retry_in = str(uniform(1.0, 5.0))
            CORE_CONFIG.logger.warning(f"Can't add plugin {plugin.id} to database : database is locked or had trouble handling the request, retry in {retry_in} seconds")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
                headers={"Retry-After": retry_in},
            )
        elif resp:
            message = f"Can't add plugin to database : {resp}"
            background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "POST", "method": plugin.method, "tags": ["plugin"], "title": f"Tried to add plugin {plugin.id}", "description": message, "status": "error"})
            CORE_CONFIG.logger.error(message)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message": resp},
            )

        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "POST", "method": plugin.method, "tags": ["plugin"], "title": f"Add plugin {plugin.id}", "description": f"Add plugin {plugin.id} with data {dumps(plugin_dict)}"})
        CORE_CONFIG.logger.info(f"✅ Plugin {plugin.id} successfully added to database")

    background_tasks.add_task(generate_external_plugins, None, original_path=EXTERNAL_PLUGINS_PATH)
    background_tasks.add_task(run_jobs)
    background_tasks.add_task(send_to_instances, {"plugins", "cache"})
    background_tasks.add_task(update_app_mounts, router)

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
async def update_plugin(plugin_id: str, plugin: AddedPlugin, background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Update a plugin from the database.
    """
    plugin_dict = plugin.model_dump()
    resp = DB.upsert_external_plugin(plugin_dict, plugin_id=plugin_id)

    if resp == "not_found":
        message = f"Plugin {plugin.id} not found"
        background_tasks.add_task(
            DB.add_action,
            {
                "date": datetime.now(),
                "api_method": "PATCH",
                "method": plugin.method,
                "tags": ["plugin"],
                "title": f"Tried to update plugin {plugin.id}",
                "description": f"Tried to update plugin {plugin.id} with data {dumps(plugin_dict)} but it doesn't exist",
                "status": "error",
            },
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif resp == "not_external":
        message = f"Can't update a core plugin ({plugin.id})"
        background_tasks.add_task(
            DB.add_action,
            {
                "date": datetime.now(),
                "api_method": "PATCH",
                "method": plugin.method,
                "tags": ["plugin"],
                "title": f"Tried to update plugin {plugin.id}",
                "description": f"Tried to update plugin {plugin.id} with data {dumps(plugin_dict)} but it is a core plugin",
                "status": "error",
            },
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif resp == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't update plugin {plugin.id} to database : database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        message = f"Can't update plugin to database : {resp}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "PATCH", "method": plugin.method, "tags": ["plugin"], "title": f"Tried to update plugin {plugin.id}", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    background_tasks.add_task(
        DB.add_action, {"date": datetime.now(), "api_method": "PATCH", "method": plugin.method, "tags": ["plugin"], "title": f"Update plugin {plugin.id}", "description": f"Update plugin {plugin.id} with data {dumps(plugin_dict)}"}
    )
    background_tasks.add_task(
        generate_external_plugins,
        None,
        original_path=EXTERNAL_PLUGINS_PATH,
    )
    background_tasks.add_task(run_jobs)
    background_tasks.add_task(send_to_instances, {"plugins", "cache"})
    background_tasks.add_task(update_app_mounts, router)

    CORE_CONFIG.logger.info(f"✅ Plugin {plugin.id} successfully updated to database")

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
            "description": "Can't delete the plugin because it is either not external, static or was created by the core or the autoconf and the method isn't one of them",
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
async def delete_plugin(plugin_id: str, method: str, background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Delete a plugin from the database.
    """

    if method == "static":
        message = f"Can't delete plugin {plugin_id} : method can't be static"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["plugin"], "title": f"Tried to delete plugin {plugin_id}", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    resp = DB.remove_external_plugin(plugin_id, method=method)

    if resp == "not_found":
        message = f"Plugin {plugin_id} not found"
        background_tasks.add_task(
            DB.add_action,
            {
                "date": datetime.now(),
                "api_method": "DELETE",
                "method": method,
                "tags": ["plugin"],
                "title": f"Tried to delete plugin {plugin_id}",
                "description": f"Tried to delete plugin {plugin_id} but it doesn't exist",
                "status": "error",
            },
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif resp == "not_external":
        message = f"Can't delete a core plugin ({plugin_id})"
        background_tasks.add_task(
            DB.add_action,
            {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["plugin"], "title": f"Tried to delete plugin {plugin_id}", "description": f"Tried to delete plugin {plugin_id} but it is a core plugin", "status": "error"},
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif resp == "method_conflict":
        message = f"Can't delete plugin {plugin_id} because it is either static or was created by the core or the autoconf and the method isn't one of them"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["plugin"], "title": f"Tried to delete plugin {plugin_id}", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif resp == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't delete plugin {plugin_id} to database : database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        message = f"Can't delete plugin {plugin_id} to database : {resp}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["plugin"], "title": f"Tried to delete plugin {plugin_id}", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["plugin"], "title": f"Delete plugin {plugin_id}", "description": f"Delete plugin {plugin_id}"})
    background_tasks.add_task(
        generate_external_plugins,
        None,
        original_path=EXTERNAL_PLUGINS_PATH,
    )
    background_tasks.add_task(run_jobs)
    background_tasks.add_task(send_to_instances, {"plugins", "cache"})
    background_tasks.add_task(update_app_mounts, router)

    CORE_CONFIG.logger.info(f"✅ Plugin {plugin_id} successfully deleted from database")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Plugin successfully deleted"},
    )


@router.get("/external/files", summary="Get all external plugins files in a tar archive", response_description="Tar archive containing all external plugins files", responses={})
async def get_plugins_files():
    """
    Get all external plugins files in a tar archive.
    """
    plugins_files = BytesIO()
    with tar_open(fileobj=plugins_files, mode="w:gz", compresslevel=9, dereference=True) as tar:
        tar.add(str(EXTERNAL_PLUGINS_PATH), arcname=".", recursive=True)
    plugins_files.seek(0, 0)

    return Response(
        content=plugins_files.getvalue(),
        media_type="application/x-tar",
        headers={"Content-Disposition": "attachment; filename=plugins.tar.gz"},
    )
