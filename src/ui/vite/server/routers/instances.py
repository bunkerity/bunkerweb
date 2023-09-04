from datetime import datetime, timedelta
from random import uniform
from typing import Annotated, Dict, List, Literal, Union
from fastapi import APIRouter, BackgroundTasks, status, Path as fastapi_Path
from fastapi.responses import JSONResponse
import requests
from config import API_URL
from utils import set_res_from_req
from models import Instance, ResponseModel

router = APIRouter(prefix="/api/instances", tags=["instances"])


@router.get(
    "",
    response_model=ResponseModel,
    summary="Get BunkerWeb instances",
)
async def get_instances():
    req = requests.get(f'{API_URL}/instances')
    res = set_res_from_req(req, "GET", "Retrieve instances")
    return res


@router.put(
    "",    
    response_model=ResponseModel,
    summary="Upsert one or more BunkerWeb instances",
)
async def upsert_instance(instances: Union[Instance, List[Instance]], method: str = "manual", reload: bool = True,):
    req = requests.put(f'{API_URL}/instances?method={method}&reload={reload}', data=instances)
    res = set_res_from_req(req, "PUT", "Upsert instances")
    return res


@router.delete(
    "/{instance_hostname}",
    response_model=ResponseModel,
    summary="Delete BunkerWeb instance",
)
async def delete_instance(instance_hostname: str):
    req = requests.delete(f'{API_URL}/{instance_hostname}')
    res = set_res_from_req(req, "DELETE", "Delete instance")
    return res


@router.post(
    "/{instance_hostname}/{action}",
    response_model=ResponseModel,
    summary="Send action to a BunkerWeb instance",
)
async def send_instance_action(instances_hostname: str, action: Literal["ping", "bans", "start", "stop", "restart", "reload"]):
    req = requests.post(f'{API_URL}/instances?method={method}&reload={reload}')
    res = set_res_from_req(req, "POST", "Send instance action")
    return res
