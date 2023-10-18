from fastapi import Body, APIRouter
from fastapi.responses import FileResponse
import os
from fastapi.staticfiles import StaticFiles
prefix = "/admin"
base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

router = APIRouter(prefix=prefix, tags=["admin"])


