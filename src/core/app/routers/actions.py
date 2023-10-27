from datetime import datetime
from typing import List
from fastapi import APIRouter, status
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
    "",
    response_model=ErrorMessage,
    summary="Creates a new action",
    response_description="Message",
    responses={status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error", "model": ErrorMessage}},
)
async def post_action(action: Action):
    """
    Creates a new action.
    """
    resp = DB.add_action(**action.model_dump() | {"date": action.date or datetime.now()})

    if resp:
        CORE_CONFIG.logger.error(f"Can't add action : {resp}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    return JSONResponse(content={"message": "Action added"})
