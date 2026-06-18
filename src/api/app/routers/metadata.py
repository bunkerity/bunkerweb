from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..auth.guard import guard
from ..utils import get_db

router = APIRouter(prefix="/metadata", tags=["metadata"])


class MetadataUpdateRequest(BaseModel):
    data: Dict[str, Any]


@router.get("", dependencies=[Depends(guard)])
def get_metadata() -> JSONResponse:
    """Get all metadata."""
    metadata = get_db().get_metadata()

    # Serialize datetime fields for JSON (including nested dicts like plugins_config_changed)
    for key, value in metadata.items():
        if isinstance(value, datetime):
            metadata[key] = value.isoformat()
        elif isinstance(value, dict):
            metadata[key] = {k: v.isoformat() if isinstance(v, datetime) else v for k, v in value.items()}

    return JSONResponse(status_code=200, content={"status": "success", "metadata": metadata})


@router.patch("", dependencies=[Depends(guard)])
def update_metadata(req: MetadataUpdateRequest) -> JSONResponse:
    """Update metadata key-value pairs."""
    ret = get_db().set_metadata(req.data)
    if ret:
        code = 400 if "read-only" in ret else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success"})
