from typing import List, Literal, Union
from fastapi import APIRouter
import requests
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
    method: str = "manual",
    reload: bool = True,
):
    return get_core_format_res(f"{API}/instances?method={method}&reload={reload}", "PUT", instances, "Upsert instances")



@router.delete(
    "/{instance_hostname}",
    response_model=ResponseModel,
    summary="Delete BunkerWeb instance",
)
async def delete_instance(instance_hostname: str):
    return get_core_format_res(f"{API}/instances/{instance_hostname}", "DELETE", "", "Delete instance")

@router.post(
    "/{instance_hostname}/{action}",
    response_model=ResponseModel,
    summary="Send action to a BunkerWeb instance",
)
async def send_instance_action(instance_hostname: str, action: str):
    return get_core_format_res(f'{API}/instances/{instance_hostname}/{action}', "POST", "", f"Send instance {instance_hostname} action : {action}")

