from typing import Annotated, Optional
from fastapi import APIRouter, File, Form
import requests
from utils import get_core_format_res
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
    return get_core_format_res(f"{API}/logs/ui", "GET", "", "Retrieve ui logs")

@router.get(
    "/core",
    response_model=ResponseModel,
    summary="Get core logs",
)
async def get_logs_ui():
    return get_core_format_res(f"{API}/logs/core", "GET", "", "Retrieve core logs")
