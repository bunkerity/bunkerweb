# -*- coding: utf-8 -*-
from typing import Annotated
from fastapi import APIRouter, Body
from utils import get_core_format_res
from models import ResponseModel
import json
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR

router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.get(
    "",
    response_model=ResponseModel,
    summary="Get all actions",
)
async def get_actions():
    return get_core_format_res(f"{CORE_API}/actions", "GET", "", "Retrieve actions")


@router.post(
    "",
    response_model=ResponseModel,
    summary="Create new action",
)
async def create_action(action: Annotated[dict, Body()]):
    data = json.dumps(action, skipkeys=True, allow_nan=True, indent=6)
    return get_core_format_res(f"{CORE_API}/actions", "POST", data, "Create action")
