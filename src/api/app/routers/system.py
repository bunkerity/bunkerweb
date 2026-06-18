from typing import List, Optional, Union

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..auth.guard import guard
from ..utils import get_db

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/readonly", dependencies=[Depends(guard)])
def check_readonly() -> JSONResponse:
    """Check if the database is in read-only mode."""
    db = get_db()
    return JSONResponse(status_code=200, content={"status": "success", "readonly": db.readonly})


class CheckedChangesRequest(BaseModel):
    changes: Optional[List[str]] = None
    plugins_changes: Optional[Union[str, List[str]]] = None
    value: bool = False


@router.post("/checked-changes", dependencies=[Depends(guard)])
def checked_changes(payload: CheckedChangesRequest) -> JSONResponse:
    """Mark changes in the database.

    Args:
        payload.changes: List of change keys (e.g. ["config", "custom_configs", "ui_plugins"])
        payload.plugins_changes: Plugin IDs to mark, or "all" for all plugins
        payload.value: True to mark as changed, False to mark as checked (default: False)
    """
    db = get_db()
    if ret := db.checked_changes(payload.changes, plugins_changes=payload.plugins_changes, value=payload.value):
        return JSONResponse(status_code=500, content={"status": "error", "message": str(ret)})
    return JSONResponse(status_code=200, content={"status": "success"})
