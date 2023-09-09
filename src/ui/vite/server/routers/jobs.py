from datetime import datetime, timedelta
from random import uniform
from typing import Annotated, Dict, List, Literal, Union, Optional
from fastapi import APIRouter, File, Form, BackgroundTasks, status, Path as fastapi_Path
from fastapi.responses import JSONResponse
import requests
from config import API_URL
from utils import set_res_from_req
from models import CacheFileModel, ResponseModel

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get(
    "",
    response_model=ResponseModel,
    summary="Get all jobs",
)
async def get_jobs():
    req = requests.get(f'{API_URL}/jobs')
    res = set_res_from_req(req, "GET", "Retrieve jobs")
    return res


@router.post(
    "/{job_name}/run",
    response_model=ResponseModel,
    summary="Send to scheduler task to run a job async",
)
async def run_job(job_name:str):
    req = requests.post(f'{API_URL}/jobs/{job_name}/run')
    res = set_res_from_req(req, "POST", f'Run job {job_name}')
    return res

@router.get(
    "/{job_name}/cache/{file_name}",
    response_model=ResponseModel,
    summary="Get a file from cache related to a job",
)
async def get_jobs(job_name:str, file_name:str):
    req = requests.get(f'{API_URL}/jobs/{job_name}/cache/{file_name}')
    res = set_res_from_req(req, "GET", "Get file from cache")
    return res

@router.delete(
    "/{job_name}/cache/{file_name}",
    response_model=ResponseModel,
    summary="Delete a file from cache related to a job",
)
async def delete_jobs(job_name:str, file_name:str, data: CacheFileModel):
    req = requests.delete(f'{API_URL}/jobs/{job_name}/cache/{file_name}')
    res = set_res_from_req(req, "DELETE", "Delete file from cache")
    return res

@router.put(
    "/{job_name}/cache/{file_name}",
    response_model=ResponseModel,
    summary="Upload a file from cache related to a job",
)
async def update_jobs(
    job_name:str, 
    file_name:str,    
    cache_file: Optional[Annotated[bytes, File()]] = None,
    service_id: Optional[Annotated[str, Form()]] = None,
    checksum: Optional[Annotated[str, Form()]] = None,
):
    req = requests.put(f'{API_URL}/jobs/{job_name}/cache/{file_name}?cache_file={cache_file}&service_id={service_id}&checksum={checksum}')
    res = set_res_from_req(req, "PUT", "Upload file to cache")
    return res
