# -*- coding: utf-8 -*-
from datetime import datetime
from os.path import join, sep
from random import uniform
from sys import path as sys_path
from typing import Annotated, Dict, Literal, Optional

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from fastapi import APIRouter, BackgroundTasks, File, Form, Response, status
from fastapi.responses import JSONResponse

from ..dependencies import CORE_CONFIG, DB, run_job, run_jobs as deps_run_jobs
from api_models import CacheFileModel, ErrorMessage, Job, JobCache, JobRun  # type: ignore

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is locked or had trouble handling the request",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)


@router.get("", response_model=Dict[str, Job], summary="Get all jobs", response_description="Jobs")
async def get_jobs(background_tasks: BackgroundTasks):
    """
    Get all jobs from the database.
    """
    jobs = DB.get_jobs()

    if jobs == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't get jobs in database : database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif isinstance(jobs, str):
        message = f"Can't get jobs from database : {jobs}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "GET", "method": "unknown", "tags": ["job"], "title": "Get jobs failed", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": jobs},
        )

    return jobs


@router.post("/{job_name}/status", response_model=Dict[Literal["message"], str], summary="Adds a new job run status to the database", response_description="Message")
async def add_job_run(job_name: str, job_run: JobRun, method: str, background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Update a job run status in the database.
    """
    resp = DB.add_job_run(job_name, **job_run.model_dump())

    if resp == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't add job {job_name} run in database : database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        message = f"Can't add job {job_name} run in database : {resp}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "POST", "method": method, "tags": ["job"], "title": f"Tried to add job {job_name} run", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "POST", "method": method, "tags": ["job"], "title": f"Job {job_name} run", "description": f"Job {job_name} run {'succeeded' if job_run.success else 'failed'}"})
    CORE_CONFIG.logger.info(f"✅ Job {job_name} run successfully added to database with run status: {'✅' if job_run.success else '❌'}")

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"message": "Job run successfully added to database"},
    )


@router.post(
    "/run",
    response_model=Dict[Literal["message"], str],
    summary="Send a task to the scheduler to run a single job or all jobs asynchronously",
    response_description="Job",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Job not found",
            "model": ErrorMessage,
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is locked or had trouble handling the request",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def run_jobs(method: str, background_tasks: BackgroundTasks, job_name: Optional[str] = None):
    """
    Run a job(s).
    """
    title = ""
    description = ""
    if job_name:
        job = DB.get_job(job_name)

        if not job:
            message = f"Job {job_name} not found"
            background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "POST", "method": method, "tags": ["job"], "title": f"Tried to run job {job_name}", "description": message, "status": "error"})
            CORE_CONFIG.logger.warning(message)
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
        elif job == "retry":
            retry_in = str(uniform(1.0, 5.0))
            CORE_CONFIG.logger.warning(f"Can't get job {job_name} in database : database is locked or had trouble handling the request, retry in {retry_in} seconds")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
                headers={"Retry-After": retry_in},
            )
        elif isinstance(job, str):
            message = f"Can't get job {job_name} from database : {job}"
            background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "POST", "method": method, "tags": ["job"], "title": f"Tried to run job {job_name}", "description": message, "status": "error"})
            CORE_CONFIG.logger.error(message)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message": job},
            )

        title = f"Job {job_name} run"
        description = f"Job {job_name} run scheduled"
        background_tasks.add_task(run_job, job_name)
    else:
        title = "Jobs run"
        description = "Jobs run scheduled"
        background_tasks.add_task(deps_run_jobs)

    background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "POST", "method": method, "tags": ["job"], "title": title, "description": description})

    return JSONResponse(content={"message": "Successfully sent task to scheduler"})


@router.get(
    "/{job_name}/cache/{file_name}",
    response_model=JobCache,
    summary="Get a file from the cache",
    response_description="Job cache data",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "File not found",
            "model": ErrorMessage,
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is locked or had trouble handling the request",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def get_cache(job_name: str, file_name: str, background_tasks: BackgroundTasks, service_id: Optional[str] = None, with_info: bool = False, with_data: bool = True):
    """
    Get a file from the cache.
    """
    cached_file = DB.get_job_cache(job_name, file_name, service_id=service_id, with_info=with_info, with_data=with_data)

    if not cached_file:
        message = f"Job {job_name} cache file {file_name} not found"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "GET", "method": "unknown", "tags": ["job"], "title": f"Tried to get job {job_name} cache file {file_name}", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif cached_file == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't get job {job_name} cache file {file_name} in database : database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif isinstance(cached_file, str):
        message = f"Can't get job {job_name} cache file {file_name} from database : {cached_file}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "GET", "method": "unknown", "tags": ["job"], "title": f"Tried to get job {job_name} cache file {file_name}", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": cached_file},
        )

    if with_data or not with_info:
        return Response(content=cached_file.data, media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename={file_name}"})

    return {
        "last_update": cached_file.last_update.timestamp() if cached_file.last_update else None,
        "checksum": cached_file.checksum,
    }


@router.put("/{job_name}/cache/{file_name}", response_model=Dict[Literal["message"], str], summary="Upload a file to the cache", response_description="Message")
async def upsert_cache(
    job_name: str,
    file_name: str,
    method: str,
    background_tasks: BackgroundTasks,
    cache_file: Annotated[Optional[bytes], File()] = None,
    service_id: Annotated[Optional[str], Form()] = None,
    checksum: Annotated[Optional[str], Form()] = None,
):
    """
    Upload a file to the cache.
    """
    # TODO add a background task that sends a request to the instances to update the cache when soft reload will be available
    resp = DB.upsert_job_cache(
        job_name,
        file_name,
        cache_file,
        service_id=service_id,
        checksum=checksum,
    )

    if resp == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't upsert job {job_name} cache file {file_name} in database : database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp not in ("created", "updated"):
        message = f"Can't upsert job {job_name} cache file {file_name} in database : {resp}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["job"], "title": f"Tried to upsert job {job_name} cache file {file_name}", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    background_tasks.add_task(
        DB.add_action,
        {
            "date": datetime.now(),
            "api_method": "PUT",
            "method": method,
            "tags": ["job"],
            "title": f"Job {job_name} cache file {file_name} {resp}",
            "description": f"Job {job_name} cache file {file_name} {resp}"
            + (f" for service {service_id}" if service_id else "")
            + (f" with checksum {checksum}" if checksum else "")
            + (f" with a file data length of {len(cache_file)} bytes" if cache_file else ""),
        },
    )
    CORE_CONFIG.logger.info(f"✅ Job {job_name} cache successfully updated in database")

    return JSONResponse(
        status_code=status.HTTP_200_OK if resp == "updated" else status.HTTP_201_CREATED,
        content={"message": "File successfully uploaded to cache"},
    )


@router.delete(
    "/{job_name}/cache/{file_name}",
    response_model=Dict[Literal["message"], str],
    summary="Delete a file from the cache",
    response_description="Message",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Job cache file not found",
            "model": ErrorMessage,
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is locked or had trouble handling the request",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def delete_cache(job_name: str, file_name: str, method: str, data: CacheFileModel, background_tasks: BackgroundTasks):
    """
    Delete a file from the cache.
    """
    # TODO add a background task that sends a request to the instances to delete the cache when soft reload will be available
    resp = DB.delete_job_cache(job_name, file_name, service_id=data.service_id)

    if not resp:
        message = f"Job {job_name} cache file {file_name} not found"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["job"], "title": f"Tried to delete job {job_name} cache file {file_name}", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif resp == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't delete job {job_name} cache file {file_name} in database : database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif not isinstance(resp, str):
        message = f"Can't delete job {job_name} cache file {file_name} from database : {resp}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["job"], "title": f"Tried to delete job {job_name} cache file {file_name}", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    background_tasks.add_task(
        DB.add_action,
        {
            "date": datetime.now(),
            "api_method": "DELETE",
            "method": method,
            "tags": ["job"],
            "title": f"Job {job_name} cache file {file_name} deleted",
            "description": f"Job {job_name} cache file {file_name} deleted" + (f" for service {data.service_id}" if data.service_id else ""),
        },
    )
    CORE_CONFIG.logger.info(f"✅ Job {job_name} cache successfully deleted from database")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "File successfully deleted from cache"},
    )
