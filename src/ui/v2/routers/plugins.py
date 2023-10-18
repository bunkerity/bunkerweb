from fastapi import APIRouter
import requests
from utils import set_res
from models import AddedPlugin, ResponseModel
import os
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("CORE_ADDR") 

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get(
    "",
    response_model=ResponseModel,
    summary="Get all plugins",
)
async def get_plugins():
    req = requests.get(f"{API}/plugins")
    res = set_res(req, "GET", "Retrieve plugins")
    return res


@router.post(
    "",
    response_model=ResponseModel,
    summary="Get all plugins",
)
async def add_plugin(plugin: AddedPlugin):
    req = requests.post(f"{API}/plugins", data=plugin)
    res = set_res(req, "POST", "Adding plugin")
    return res


@router.patch(
    "/{plugin_id}",
    response_model=ResponseModel,
    summary="Update a plugin",
)
async def update_plugin(plugin: AddedPlugin, plugin_id: str):
    req = requests.patch(f"{API}/plugins/{plugin_id}", data=plugin)
    res = set_res(req, "PATCH", f"Update plugin {plugin_id}")
    return res


@router.delete(
    "/{plugin_id}",
    response_model=ResponseModel,
    summary="Delete BunkerWeb instance",
)
async def delete_instance(plugin_id: str):
    req = requests.delete(f"{API}/plugin/{plugin_id}")
    res = set_res(req, "DELETE", f"Delete plugin {plugin_id}")
    return res


@router.get(
    "/external/files",
    response_model=ResponseModel,
    summary="Get external files with plugins",
)
async def send_instance_action():
    req = requests.post(f"{API}/plugins/external/files")
    res = set_res(req, "GET", "Plugin external files")
    return res
