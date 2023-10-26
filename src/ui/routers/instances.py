from typing import List, Union
from fastapi import APIRouter
from utils import get_core_format_res
from models import Instance, ResponseModel
import os
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("CORE_ADDR")


router = APIRouter(prefix="/api/instances", tags=["instances"])


@router.get(
    "",
    response_model=ResponseModel,
    summary="Get BunkerWeb instances",
)
async def get_instances():
    return get_core_format_res(f"{API}/instances", "GET", "", "Retrieve instances")


@router.put(
    "",
    response_model=ResponseModel,
    summary="Upsert one or more BunkerWeb instances",
)
async def upsert_instance(
    instances: Union[Instance, List[Instance]],
    method: str = "ui",
    reload: bool = True,
):
    return get_core_format_res(f"{API}/instances?method={method}&reload={reload}", "PUT", instances, "Upsert instances")


@router.delete(
    "/{instance_hostname}",
    response_model=ResponseModel,
    summary="Delete BunkerWeb instance",
)
async def delete_instance(instance_hostname: str, method: str = "ui"):
    return get_core_format_res(f"{API}/instances/{instance_hostname}?method={method}", "DELETE", "", f"Delete instance {instance_hostname}")


@router.post(
    "/{instance_hostname}/{action}",
    response_model=ResponseModel,
    summary="Send action to a BunkerWeb instance",
)
async def send_instance_action(instance_hostname: str, action: str, method: str = "ui"):
    return get_core_format_res(f"{API}/instances/{instance_hostname}/{action}?method={method}", "POST", "", f"Send instance {instance_hostname} action : {action}")
