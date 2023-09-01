from datetime import datetime
from random import uniform
from typing import Annotated, Dict, Literal, Optional, Union
from fastapi import APIRouter, BackgroundTasks, File, Form, status
from fastapi.responses import JSONResponse

from ..models import CacheFileDataModel, CacheFileModel, ErrorMessage, Job, Job_cache
from ..dependencies import CORE_CONFIG, DB, run_job as deps_run_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "",
    response_model=Dict[str, Job],
    summary="Get all jobs",
    response_description="Jobs",
)
async def get_jobs():
    """
    Get all jobs from the database.
    """
    return DB.get_jobs()


@router.post(
    "/{job_name}/status",
    response_model=Dict[Literal["message"], str],
    summary="Adds a new job run status to the database",
    response_description="Message",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Missing start_date",
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
async def add_job_run(
    job_name: str,
    data: Dict[Literal["success", "start_date", "end_date"], Union[bool, float]],
) -> JSONResponse:
    """
    Update a job run status in the database.
    """
    start_date = data.get("start_date")

    if not start_date:
        CORE_CONFIG.logger.error("Missing start_date")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Missing start_date"},
        )

    start_date = datetime.fromtimestamp(start_date)
    end_date = data.get("end_date")

    if end_date:
        end_date = datetime.fromtimestamp(end_date)

    resp = DB.add_job_run(job_name, data.get("success", False), start_date, end_date)

    CORE_CONFIG.logger.warning(resp)

    if "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(
            f"Can't add job {job_name} run in database : database is locked or had trouble handling the request, retry in {retry_in} seconds"
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"
            },
            headers={"Retry-After": retry_in},
        )
    elif resp:
        CORE_CONFIG.logger.error(f"Can't add job {job_name} run in database : {resp}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    CORE_CONFIG.logger.info(
        f"✅ Job {job_name} run successfully added to database with run status: {'✅' if data.get('success', False) else '❌'}"
    )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"message": "Job run successfully added to database"},
    )


@router.post(
    "/{job_name}/run",
    response_model=Dict[Literal["message"], str],
    summary="Send a task to the scheduler to run a job asynchronously",
    response_description="Job",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Job not found",
            "model": ErrorMessage,
        }
    },
)
async def run_job(job_name: str, background_tasks: BackgroundTasks):
    """
    Run a job.
    """
    job = DB.get_job(job_name)

    if not job:
        CORE_CONFIG.logger.warning(f"Job {job_name} not found")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": f"Job {job_name} not found"},
        )

    background_tasks.add_task(deps_run_job, job_name)

    return JSONResponse(content={"message": "Successfully sent task to scheduler"})


@router.get(
    "/{job_name}/cache/{file_name}",
    response_model=Job_cache,
    summary="Get a file from the cache",
    response_description="Job cache data",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "File not found",
            "model": ErrorMessage,
        }
    },
)
async def get_cache(
    job_name: str,
    file_name: str,
    data: CacheFileDataModel,
):
    """
    Get a file from the cache.
    """
    cached_file = DB.get_job_cache(
        job_name,
        file_name,
        service_id=data.service_id,
        with_info=data.with_info,
        with_data=data.with_data,
    )

    if not cached_file:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "File not found"},
        )

    return (
        {}
        | (
            {
                "last_update": cached_file.last_update.timestamp()
                if cached_file.last_update
                else None,
                "checksum": cached_file.checksum,
            }
            if data.with_info
            else {}
        )
        | ({"data": cached_file.data} if data.with_data else {})
    )


@router.put(
    "/{job_name}/cache/{file_name}",
    response_model=Dict[Literal["message"], str],
    summary="Upload a file to the cache",
    response_description="Message",
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
async def update_cache(
    job_name: str,
    file_name: str,
    cache_file: Optional[Annotated[bytes, File()]] = None,
    service_id: Optional[Annotated[str, Form()]] = None,
    checksum: Optional[Annotated[str, Form()]] = None,
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

    CORE_CONFIG.logger.warning(resp)

    if "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(
            f"Can't update job {job_name} cache in database : database is locked or had trouble handling the request, retry in {retry_in} seconds"
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"
            },
            headers={"Retry-After": retry_in},
        )
    elif resp not in ("created", "updated"):
        CORE_CONFIG.logger.error(
            f"Can't update job {job_name} cache in database : {resp}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    CORE_CONFIG.logger.info(f"✅ Job {job_name} cache successfully updated in database")

    return JSONResponse(
        status_code=status.HTTP_200_OK
        if resp == "updated"
        else status.HTTP_201_CREATED,
        content={"message": "File successfully uploaded to cache"},
    )


@router.delete(
    "/{job_name}/cache/{file_name}",
    response_model=Dict[Literal["message"], str],
    summary="Delete a file from the cache",
    response_description="Message",
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
async def delete_cache(job_name: str, file_name: str, data: CacheFileModel):
    """
    Delete a file from the cache.
    """
    # TODO add a background task that sends a request to the instances to delete the cache when soft reload will be available
    resp = DB.delete_job_cache(job_name, file_name, service_id=data.service_id)

    if "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(
            f"Can't delete job {job_name} cache in database : database is locked or had trouble handling the request, retry in {retry_in} seconds"
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"
            },
            headers={"Retry-After": retry_in},
        )
    elif resp:
        CORE_CONFIG.logger.error(
            f"Can't delete job {job_name} cache in database : {resp}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    CORE_CONFIG.logger.info(
        f"✅ Job {job_name} cache successfully deleted from database"
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "File successfully deleted from cache"},
    )
