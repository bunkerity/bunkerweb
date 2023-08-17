from typing import Dict, Literal
from fastapi import APIRouter, BackgroundTasks, status
from fastapi.responses import JSONResponse

from ..core import ErrorMessage
from ..dependencies import DB, LOGGER, inform_scheduler

router = APIRouter(prefix="/config", tags=["config"])


@router.get(
    "",
    response_model=Dict[str, str],
    summary="Get config from Database",
    response_description="BunkerWeb config",
)
async def get_config() -> JSONResponse:
    """Get config from Database"""
    return JSONResponse(content=DB.get_config())


@router.put(
    "/global",
    response_model=Dict[Literal["message"], str],
    summary="Update global config in Database",
    response_description="Message",
)
async def update_global_config(
    config: Dict[str, str], method: str, background_tasks: BackgroundTasks
) -> JSONResponse:
    """Update global config in Database"""
    err = DB.save_global_config(config, method)

    if err:
        LOGGER.error(f"Can't save global config to database : {err}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": err}
        )

    background_tasks.add_task(inform_scheduler, {"type": "run_once"})

    LOGGER.info("✅ Global config successfully saved to database")

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
    },
)
async def update_service_config(
    service_name: str,
    config: Dict[str, str],
    method: str,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """Update service config in Database"""
    err = DB.save_service_config(service_name, config, method)

    if err == "not_found":
        message = f"Service {service_name} not found"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"message": message}
        )
    elif err == "method_conflict":
        message = f"Can't rename service {service_name} because its method or one of its setting's method belongs to the core or the autoconf and the method isn't one of them"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN, content={"message": message}
        )
    elif err:
        LOGGER.error(f"Can't save service {service_name} config to database : {err}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": err}
        )

    background_tasks.add_task(inform_scheduler, {"type": "run_once"})

    LOGGER.info(f"✅ Service {service_name} config successfully saved to database")

    return JSONResponse(
        content={"message": f"Service {service_name} config successfully saved"}
    )


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
    },
)
async def delete_service_config(
    service_name: str, method: str, background_tasks: BackgroundTasks
) -> JSONResponse:
    """Delete a service from the config in the Database"""
    err = DB.remove_service(service_name, method)

    if err == "not_found":
        message = f"Service {service_name} not found"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"message": message}
        )
    elif err == "method_conflict":
        message = f"Can't delete service {service_name} because it was created by either the core or the autoconf and the method isn't one of them"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN, content={"message": message}
        )
    elif err:
        LOGGER.error(f"Can't delete service {service_name} from the database : {err}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"message": err}
        )

    background_tasks.add_task(inform_scheduler, {"type": "run_once"})

    LOGGER.info(f"✅ Service {service_name} successfully deleted from the database")

    return JSONResponse(
        content={"message": f"Service {service_name} successfully deleted"}
    )
