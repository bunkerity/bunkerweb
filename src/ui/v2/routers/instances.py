from typing import List, Literal, Union
from fastapi import APIRouter
import requests
from utils import set_res
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
    req = requests.get(f"{API}/instances")
    res = set_res(req, "GET", "Retrieve instances")
    return res


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
    req = requests.put(f"{API}/instances?method={method}&reload={reload}", data=instances)
    res = set_res(req, "PUT", "Upsert instances")
    return res


@router.delete(
    "/{instance_hostname}",
    response_model=ResponseModel,
    summary="Delete BunkerWeb instance",
)
async def delete_instance(instance_hostname: str):
    req = requests.delete(f"{API}/instances/{instance_hostname}")
    res = set_res(req, "DELETE", "Delete instance")
    return res


@router.post(
    "/{instance_hostname}/{action}",
    response_model=ResponseModel,
    summary="Send action to a BunkerWeb instance",
)
async def send_instance_action(instance_hostname: str, action: str):
    req = requests.post(f'{API}/instances/{instance_hostname}/{action}')
    res = set_res(req, "POST", f"Send instance {instance_hostname} action {action}")
    return res
