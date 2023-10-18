from fastapi import APIRouter
import requests
from utils import set_res
from models import ResponseModel
import os
from dotenv import load_dotenv

load_dotenv()
API = os.getenv("CORE_ADDR") 

router = APIRouter(prefix="/api", tags=[""])


@router.get(
    "/version",
    response_model=ResponseModel,
    summary="Get BunkerWeb version used",
)
async def get_version():
    req = requests.get(f"{API}/version")
    res = set_res(req, "GET", "Retrieve version")
    return res
