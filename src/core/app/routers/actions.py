# -*- coding: utf-8 -*-
from datetime import datetime
from random import uniform
from typing import List
from fastapi import APIRouter, BackgroundTasks, status
from fastapi.responses import JSONResponse

from ..models import Action, ErrorMessage
from ..dependencies import CORE_CONFIG, DB

router = APIRouter(
    prefix="/actions",
    tags=["actions"],
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is locked or had trouble handling the request",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)


@router.get("", response_model=List[Action], summary="Get all actions", response_description="Actions")
async def get_actions(background_tasks: BackgroundTasks):
    """
    Get all jobs from the database.
    """
    actions = DB.get_actions()

    if actions == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't get actions in database : database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif isinstance(actions, str):
        message = f"Can't get actions in database : {actions}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "GET", "method": "unknown", "tags": ["action"], "title": "Get actions failed", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": actions},
        )

    return actions


@router.post("", response_model=ErrorMessage, summary="Creates a new action", response_description="Message")
async def post_action(action: Action, background_tasks: BackgroundTasks):
    """
    Creates a new action.
    """
    resp = DB.add_action(action.model_dump() | {"date": action.date or datetime.now()})

    if resp == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't create action: Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        message = f"Can't add action : {resp}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "POST", "method": action.method, "tags": ["action"], "title": "Add action failed", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    return JSONResponse(content={"message": "Action added"})
