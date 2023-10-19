from random import uniform
from typing import Dict, Literal, Union
from fastapi import APIRouter, BackgroundTasks, status
from fastapi.responses import JSONResponse

from ..models import ErrorMessage
from ..dependencies import CORE_CONFIG, DB, run_jobs, send_to_instances

router = APIRouter(prefix="/config", tags=["config"])


@router.get(
    "",
    response_model=Union[
        Dict[
            str,
            Union[str, Dict[Literal["value", "global", "method"], Union[str, bool]]],
        ],
        Dict[
            Literal["global", "services"],
            Dict[
                str,
                Dict[str, Union[str, Dict[Literal["value", "method"], str]]],
            ],
        ],
    ],
    summary="Get config from Database",
    response_description="BunkerWeb config",
)
async def get_config(methods: bool = False, new_format: bool = False):
    """Get config from Database"""
    return DB.get_config(methods=methods, new_format=new_format)


@router.put(
    "",
    response_model=Dict[Literal["message"], str],
    summary="Update whole config in Database",
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
async def update_config(config: Dict[str, str], method: str, background_tasks: BackgroundTasks) -> JSONResponse:
    """Update whole config in Database"""
    resp = DB.save_config(config, method)

    if "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't save config to database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        CORE_CONFIG.logger.error(f"Can't save config to database : {resp}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": resp})

    CORE_CONFIG.logger.info("✅ Config successfully saved to database")

    background_tasks.add_task(run_jobs)
    background_tasks.add_task(send_to_instances, {"config", "cache"})

    return JSONResponse(content={"message": "Config successfully saved"})


@router.put(
    "/global",
    response_model=Dict[Literal["message"], str],
    summary="Update global config in Database",
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
async def update_global_config(config: Dict[str, str], method: str, background_tasks: BackgroundTasks) -> JSONResponse:
    """Update global config in Database"""
    resp = DB.save_global_config(config, method)

    if "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't save global config to database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        CORE_CONFIG.logger.error(f"Can't save global config to database : {resp}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": resp})

    CORE_CONFIG.logger.info("✅ Global config successfully saved to database")

    background_tasks.add_task(run_jobs)
    background_tasks.add_task(send_to_instances, {"config", "cache"})

    return JSONResponse(content={"message": "Global config successfully saved"})


@router.put(
    "/service/{service_name}",
    response_model=Dict[Literal["message"], str],
    summary="Update a service config in Database",
    response_description="Message",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Service not found",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Not authorized to rename the service",
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
async def update_service_config(
    service_name: str,
    config: Dict[str, str],
    method: str,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """Update service config in Database"""
    resp = DB.save_service_config(service_name, config, method)

    if resp == "not_found":
        message = f"Service {service_name} not found"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif resp == "method_conflict":
        message = f"Can't rename service {service_name} because its method or one of its setting's method belongs to the core or the autoconf and the method isn't one of them"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't save config for service {service_name} to database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        CORE_CONFIG.logger.error(f"Can't save service {service_name} config to database : {resp}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": resp})

    CORE_CONFIG.logger.info(f"✅ Service {service_name} config successfully saved to database")

    background_tasks.add_task(run_jobs)
    background_tasks.add_task(send_to_instances, {"config", "cache"})

    return JSONResponse(content={"message": f"Service {service_name} config successfully saved"})


@router.delete(
    "/service/{service_name}",
    response_model=Dict[Literal["message"], str],
    summary="Delete a service from the config in the Database",
    response_description="Message",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Service not found",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Not authorized to delete the service",
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
async def delete_service_config(service_name: str, method: str, background_tasks: BackgroundTasks) -> JSONResponse:
    """Delete a service from the config in the Database"""
    resp = DB.remove_service(service_name, method)

    if resp == "not_found":
        message = f"Service {service_name} not found"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif resp == "method_conflict":
        message = f"Can't delete service {service_name} because it was created by either the core or the autoconf and the method isn't one of them"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't delete service {service_name} from the database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        CORE_CONFIG.logger.error(f"Can't delete service {service_name} from the database : {resp}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": resp})

    CORE_CONFIG.logger.info(f"✅ Service {service_name} successfully deleted from the database")

    background_tasks.add_task(run_jobs)
    background_tasks.add_task(send_to_instances, {"config", "cache"})

    return JSONResponse(content={"message": f"Service {service_name} successfully deleted"})
