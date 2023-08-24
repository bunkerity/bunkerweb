from typing import Annotated, Dict, List, Literal, Union
from fastapi import APIRouter, BackgroundTasks, status, Path as fastapi_Path
from fastapi.responses import JSONResponse

from ..models import ErrorMessage, Instance, InstanceWithMethod
from ..dependencies import CORE_CONFIG, DB, test_and_send_to_instances
from API import API  # type: ignore

router = APIRouter(prefix="/instances", tags=["instances"])


@router.get(
    "",
    response_model=List[InstanceWithMethod],
    summary="Get BunkerWeb instances",
    response_description="BunkerWeb instances",
)
async def get_instances():
    """
    Get BunkerWeb instances with the following information:

    - **hostname**: The hostname of the instance
    - **port**: The port of the instance
    - **server_name**: The server name of the instance
    - **method**: The method of the instance
    """
    return DB.get_instances()


@router.put(
    "",
    response_model=Dict[Literal["message"], str],
    status_code=status.HTTP_201_CREATED,
    summary="Upsert a BunkerWeb instance",
    response_description="Message",
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Instance already exists",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def upsert_instance(
    instance: Instance, background_tasks: BackgroundTasks, method: str = "manual"
) -> JSONResponse:
    """
    Add a BunkerWeb instance with the following information:

    - **hostname**: The hostname of the instance
    - **port**: The port of the instance
    - **server_name**: The server name of the instance
    """
    error = DB.upsert_instance(**instance.model_dump(), method=method)

    if error == "exists":
        message = f"Instance {instance.hostname} already exists"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"message": message}
        )
    elif error not in ("created", "updated"):
        CORE_CONFIG.logger.error(f"Can't upsert instance to database : {error}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )

    CORE_CONFIG.logger.info(
        f"✅ Instance {instance.hostname} successfully {error} to database"
    )

    background_tasks.add_task(test_and_send_to_instances, "all", {instance.to_api()})

    return JSONResponse(
        status_code=status.HTTP_201_CREATED
        if error == "created"
        else status.HTTP_200_OK,
        content={"message": "Instance successfully added"},
    )


@router.get(
    "/{instance_hostname}",
    response_model=InstanceWithMethod,
    summary="Get a BunkerWeb instance",
    response_description="A BunkerWeb instance",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Instance not found",
            "model": ErrorMessage,
        }
    },
)
async def get_instance(
    instance_hostname: Annotated[
        str,
        fastapi_Path(
            title="The hostname of the instance", min_length=1, max_length=256
        ),
    ]
):
    """
    Get a BunkerWeb instance with the following information:

    - **hostname**: The hostname of the instance
    - **port**: The port of the instance
    - **server_name**: The server name of the instance
    """
    db_instance = DB.get_instance(instance_hostname)

    if not db_instance:
        message = f"Instance {instance_hostname} not found"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"message": message}
        )

    return db_instance


@router.delete(
    "/{instance_hostname}",
    response_model=Dict[Literal["message"], str],
    summary="Delete a BunkerWeb instance",
    response_description="Message",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Instance not found",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def delete_instance(instance_hostname: str) -> JSONResponse:
    """
    Delete a BunkerWeb instance
    """
    error = DB.remove_instance(instance_hostname)

    if error == "not_found":
        message = f"Instance {instance_hostname} not found"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"message": message}
        )
    elif error:
        CORE_CONFIG.logger.error(f"Can't remove instance to database : {error}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )

    CORE_CONFIG.logger.info(
        f"✅ Instance {instance_hostname} successfully removed from database"
    )

    return JSONResponse(
        content={"message": "Instance successfully removed"},
    )


@router.post(
    "/{instance_hostname}/{action}",
    response_model=Dict[Literal["message"], Union[str, dict]],
    summary="Send an action to a BunkerWeb instance",
    response_description="Message",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Instance not found",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid action",
            "model": ErrorMessage,
        },
    },
)
async def send_instance_action(
    instance_hostname: str,
    action: Literal["ping", "bans", "start", "stop", "restart", "reload"],
) -> JSONResponse:
    """
    Delete a BunkerWeb instance
    """
    db_instance = DB.get_instance(instance_hostname)

    if not db_instance:
        message = f"Instance {instance_hostname} not found"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"message": message}
        )

    instance_api = API(
        f"http://{db_instance['hostname']}:{db_instance['port']}",
        db_instance["server_name"],
    )

    sent, err, status_code, resp = instance_api.request(
        "GET" if action in ("ping", "bans") else "POST", f"/{action}", timeout=(5, 10)
    )

    if not sent:
        error = f"Can't send API request to {instance_api.endpoint}{action} : {err}"
        CORE_CONFIG.logger.error(error)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )
    else:
        if status_code != 200:
            error = f"Error while sending API request to {instance_api.endpoint}{action} : status = {resp['status']}, msg = {resp['msg']}"
            CORE_CONFIG.logger.error(error)
            return JSONResponse(status_code=status_code, content={"message": error})

    CORE_CONFIG.logger.info(
        f"Successfully sent API request to {instance_api.endpoint}{action}"
    )

    return JSONResponse(content={"message": resp})
