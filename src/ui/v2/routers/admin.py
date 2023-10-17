from fastapi import Body, APIRouter
from fastapi.responses import FileResponse
import os

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/",
    summary="Get index",
)
async def get_index():
    print(base)
    return FileResponse(f'{base}/templates/home.html')

@router.get(
    "/services",
    summary="Get servoces",
)
async def get_services():
    print(base)
    return FileResponse(f'{base}/templates/services.html')