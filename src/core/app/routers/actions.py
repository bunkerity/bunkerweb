from datetime import datetime
from random import uniform
from typing import Annotated, Dict, List, Literal
from fastapi import APIRouter, BackgroundTasks, Form, status
from fastapi.responses import JSONResponse

from ..models import Action, ErrorMessage
from ..dependencies import CORE_CONFIG, DB

router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("", response_model=List[Action], summary="Get all actions", response_description="Actions")
async def get_actions():
    """
    Get all jobs from the database.
    """
    return DB.get_actions()


@router.post(
    "/cleanup",
    response_model=Dict[Literal["message"], str],
    summary="Cleanup the oldest actions that are over the limit",
    response_description="Cleanup result",
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
async def cleanup_actions(method: str, background_tasks: BackgroundTasks, limit: Annotated[int, Form()] = 10000):
    """
    Cleanup the oldest actions that are older than the limit.
    """
    actions_cleaned = DB.cleanup_actions_excess(limit)

    if "database is locked" in actions_cleaned or "file is not a database" in actions_cleaned:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't cleanup actions : database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif not actions_cleaned.isdigit():
        return JSONResponse(content={"message": actions_cleaned}, status_code=500)

    message = f"Cleaned {actions_cleaned} actions from the database."
    background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "POST", "method": method, "tags": ["action"], "title": "Cleanup actions", "description": message})
    return JSONResponse(content={"message": message})
