from typing import Annotated, Optional
from fastapi import APIRouter, File, Form
import requests
from utils import set_res
from models import CacheFileModel, ResponseModel
import os
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("CORE_ADDR") 

router = APIRouter(prefix="/api/logs", tags=["jobs"])


@router.get(
    "/ui",
    response_model=ResponseModel,
    summary="Get ui logs",
)
async def get_logs_ui():
    req = requests.get(f"{API}/logs/ui")
    res = set_res(req, "GET", "Retrieve ui logs")
    return res

@router.get(
    "/core",
    response_model=ResponseModel,
    summary="Get core logs",
)
async def get_logs_ui():
    req = requests.get(f"{API}/logs/core")
    res = set_res(req, "GET", "Retrieve core logs")
    return res