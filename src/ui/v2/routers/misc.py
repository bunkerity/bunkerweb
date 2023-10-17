from fastapi import APIRouter
import requests
from config import API_URL
from utils import set_res
from models import ResponseModel

router = APIRouter(prefix="/api", tags=[""])


@router.get(
    "/version",
    response_model=ResponseModel,
    summary="Get BunkerWeb version used",
)
async def get_version():
    req = requests.get(f"{API_URL}/version")
    res = set_res(req, "GET", "Retrieve version")
    return res
