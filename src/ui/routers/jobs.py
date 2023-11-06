# -*- coding: utf-8 -*-
from typing import Annotated, Optional
from fastapi import APIRouter, File, Form
from utils import get_core_format_res
from models import CacheFileModel, ResponseModel
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get(
    "",
    response_model=ResponseModel,
    summary="Get all jobs",
)
async def get_jobs():
    return get_core_format_res(f"{CORE_API}/jobs", "GET", "", "Retrieve jobs")


@router.post(
    "/{job_name}/run",
    response_model=ResponseModel,
    summary="Send to scheduler task to run a job async",
)
async def run_job(job_name: str, method: str = "ui"):
    return get_core_format_res(f"{CORE_API}/jobs/{job_name}/run?method={method}", "POST", "", f"Run job {job_name}")


@router.get(
    "/{job_name}/cache/{file_name}",
    response_model=ResponseModel,
    summary="Get a file from cache related to a job",
)
async def get_job_cache_file(job_name: str, file_name: str):
    return get_core_format_res(f"{CORE_API}/jobs/{job_name}/cache/{file_name}", "GET", "", f"Get file {file_name} from cache for job {job_name}")


@router.delete(
    "/{job_name}/cache/{file_name}",
    response_model=ResponseModel,
    summary="Delete a file from cache related to a job",
)
async def delete_jobs(job_name: str, file_name: str, data: CacheFileModel):
    return get_core_format_res(f"{CORE_API}/jobs/{job_name}/cache/{file_name}", "DELETE", "", f"Delete file {file_name} from cache for job {job_name}")


@router.put(
    "/{job_name}/cache/{file_name}",
    response_model=ResponseModel,
    summary="Upload a file from cache related to a job",
)
async def upload_job_file(
    job_name: str,
    file_name: str,
    cache_file: Optional[Annotated[bytes, File()]] = None,
    service_id: Optional[Annotated[str, Form()]] = None,
    checksum: Optional[Annotated[str, Form()]] = None,
):
    return get_core_format_res(f"{CORE_API}/jobs/{job_name}/cache/{file_name}?cache_file={cache_file}&service_id={service_id}&checksum={checksum}", "PUT", "", f"Upload file {file_name} to cache {cache_file}")
