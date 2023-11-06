# -*- coding: utf-8 -*-
from fastapi import APIRouter
from utils import get_core_format_res
from models import AddedPlugin, ResponseModel
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

API = UiConfig.CORE_ADDR

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get(
    "",
    response_model=ResponseModel,
    summary="Get all plugins",
)
async def get_plugins():
    return get_core_format_res(f"{API}/plugins", "GET", "", "Retrieve plugins")


@router.post(
    "",
    response_model=ResponseModel,
    summary="Get all plugins",
)
async def add_plugin(plugin: AddedPlugin):
    return get_core_format_res(f"{API}/plugins", "POST", plugin, "Adding plugin")


@router.patch(
    "/{plugin_id}",
    response_model=ResponseModel,
    summary="Update a plugin",
)
async def update_plugin(plugin: AddedPlugin, plugin_id: str):
    return get_core_format_res(f"{API}/plugins/{plugin_id}", "PATCH", plugin, f"Update plugin {plugin_id}")


@router.delete(
    "/{plugin_id}",
    response_model=ResponseModel,
    summary="Delete BunkerWeb instance",
)
async def delete_instance(plugin_id: str):
    return get_core_format_res(f"{API}/plugins/{plugin_id}", "DELETE", plugin_id, f"Delete plugin {plugin_id}")


@router.get(
    "/external/files",
    response_model=ResponseModel,
    summary="Get external files with plugins",
)
async def send_instance_action():
    return get_core_format_res(f"{API}/plugins/external/files", "GET", "", "Plugin external files")
