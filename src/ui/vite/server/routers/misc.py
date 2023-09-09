from datetime import datetime, timedelta
from random import uniform
from typing import Annotated, Dict, List, Literal, Union
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
import requests
from config import API_URL
from utils import set_res_from_req
from models import Instance, ResponseModel

router = APIRouter(prefix="/api", tags=[""])


@router.get(
    "/version",
    response_model=ResponseModel,
    summary="Get BunkerWeb version used",
)
async def get_version():
    req = requests.get(f'{API_URL}/version')
    res = set_res_from_req(req, "GET", "Retrieve version")
    return res
