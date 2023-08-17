from typing import Annotated, Dict, List, Literal
from fastapi import APIRouter, status, Path as fastapi_Path
from fastapi.responses import JSONResponse

from ..core import ErrorMessage, Instance
from ..dependencies import DB, LOGGER
from API import API  # type: ignore

router = APIRouter(prefix="/custom_configs", tags=["custom_configs"])
