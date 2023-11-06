# -*- coding: utf-8 -*-
from fastapi import APIRouter
from utils import get_core_format_res
from models import ResponseModel
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

API = UiConfig.CORE_ADDR

router = APIRouter(prefix="/api", tags=[""])


@router.get(
    "/version",
    response_model=ResponseModel,
    summary="Get BunkerWeb version used",
)
async def get_version():
    return get_core_format_res(f"{API}/version", "GET", "", "Retrieve version")
