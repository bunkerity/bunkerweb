from fastapi import Body, APIRouter
from fastapi.responses import FileResponse
import os
from fastapi.staticfiles import StaticFiles

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/static'

router = APIRouter(prefix="/admin", tags=["admin"])

router.mount("/assets", StaticFiles(directory=f'{base}/assets'), name="")

@router.get(
    "/",
    summary="Get index",
)
async def get_index():
    return FileResponse(f'{base}/templates/home.html')

