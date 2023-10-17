from datetime import datetime, timedelta
from random import uniform
from typing import Annotated, Dict, List, Literal, Union
from fastapi import APIRouter, BackgroundTasks, status, Path as fastapi_Path
from fastapi.responses import JSONResponse

from ..models import ErrorMessage, Instance, InstanceWithInfo, InstanceWithMethod
from ..dependencies import CORE_CONFIG, DB, test_and_send_to_instances
from API import API  # type: ignore

router = APIRouter(prefix="/instances", tags=["instances"])


@router.get(
    "",
    response_model=List[InstanceWithInfo],
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
    tmp_instances = DB.get_instances()
    instances = []
    for instance in tmp_instances:
        last_seen = instance.pop("last_seen")
        data = instance.copy()
        data["status"] = "up" if last_seen and last_seen >= datetime.now() - timedelta(seconds=int(CORE_CONFIG.HEALTHCHECK_INTERVAL) * 2) else "down"
        instances.append(data)
    return instances


@router.put(
    "",
    response_model=Dict[Literal["message"], str],
    summary="Upsert one or more BunkerWeb instances",
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
async def upsert_instance(
    instances: Union[Instance, List[Instance]],
    background_tasks: BackgroundTasks,
    method: str = "static",
    reload: bool = True,
) -> JSONResponse:
    """
    Upsert one or more BunkerWeb instances with the following information:

    - **hostname**: The hostname of the instance
    - **port**: The port of the instance
    - **server_name**: The server name of the instance
    """
    decisions = {"created": [], "updated": []}
    status_code = None

    if isinstance(instances, Instance):
        resp = DB.upsert_instance(**instances.model_dump(), method=method)

        if "database is locked" in resp or "file is not a database" in resp:
            retry_in = str(uniform(1.0, 5.0))
            CORE_CONFIG.logger.warning(f"Can't upsert instance to database : {resp}, retry in {retry_in} seconds")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
                headers={"Retry-After": retry_in},
            )
        elif resp not in ("created", "updated"):
            CORE_CONFIG.logger.error(f"Can't upsert instance to database : {resp}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message": resp},
            )

        decisions[resp].append(instances)
    else:
        resp = DB.refresh_instances([instance.model_dump() for instance in instances], method=method)

        if "database is locked" in resp or "file is not a database" in resp:
            retry_in = str(uniform(1.0, 5.0))
            CORE_CONFIG.logger.warning(f"Can't upsert instances to database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
                headers={"Retry-After": retry_in},
            )
        elif resp:
            CORE_CONFIG.logger.error(f"Can't refresh instances to database : {resp}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message": resp},
            )

        decisions["created"] = instances
        status_code = status.HTTP_200_OK

    message = "✅ Instance(s) "

    if decisions["created"]:
        message += f"{', '.join(instance.hostname for instance in decisions['created'])} successfully created"
    if decisions["updated"]:
        if decisions["created"]:
            message += "and "
        message += f"{', '.join(instance.hostname for instance in decisions['updated'])} successfully updated"
    CORE_CONFIG.logger.info(f"{message} in the database")

    if decisions["created"] and reload:
        background_tasks.add_task(
            test_and_send_to_instances,
            "all",
            {instance.to_api() for instance in decisions["created"]},
        )

    if decisions["updated"]:
        CORE_CONFIG.logger.info(
            f"Skipping sending data to instance{'s' if len(decisions) > 1 else ''} : {', '.join(instance.hostname for instance in decisions['updated'])}, as {'all' if len(decisions) > 1 else 'this'}"
            + f" instance{'s' if len(decisions) > 1 else ''} was/were already in the database"
        )

    return JSONResponse(
        status_code=status_code or (status.HTTP_201_CREATED if not decisions["updated"] else status.HTTP_200_OK),
        content={"message": message},
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
        },
    },
)
async def get_instance(
    instance_hostname: Annotated[
        str,
        fastapi_Path(title="The hostname of the instance", min_length=1, max_length=256),
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
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})

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
async def delete_instance(instance_hostname: str) -> JSONResponse:
    """
    Delete a BunkerWeb instance
    """
    resp = DB.remove_instance(instance_hostname)

    if resp == "not_found":
        message = f"Instance {instance_hostname} not found"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif "database is locked" in resp or "file is not a database" in resp:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't remove instance to database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        CORE_CONFIG.logger.error(f"Can't remove instance to database : {resp}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    CORE_CONFIG.logger.info(f"✅ Instance {instance_hostname} successfully removed from database")

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
        status.HTTP_400_BAD_REQUEST: {  # ? BunkerWeb instances sometimes may return 400
            "description": "Invalid action",
            "model": ErrorMessage,
        },
    },
)
async def send_instance_action(
    instance_hostname: str,
    action: Literal["ping", "bans", "stop", "reload"],  # TODO: maybe add a "start" action
) -> JSONResponse:
    """
    Delete a BunkerWeb instance
    """
    db_instance = DB.get_instance(instance_hostname)

    if not db_instance:
        message = f"Instance {instance_hostname} not found"
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})

    instance_api = API(
        f"http://{db_instance['hostname']}:{db_instance['port']}",
        db_instance["server_name"],
    )

    sent, err, status_code, resp = instance_api.request("GET" if action in ("ping", "bans") else "POST", f"/{action}", timeout=(5, 10))

    if not sent:
        error = f"Can't send API request to {instance_api.endpoint}{action} : {err}"
        CORE_CONFIG.logger.error(error)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )
    else:
        if status_code != 200:
            resp = resp.json()
            error = f"Error while sending API request to {instance_api.endpoint}{action} : status = {resp['status']}, msg = {resp['msg']}"
            CORE_CONFIG.logger.error(error)
            return JSONResponse(status_code=status_code, content={"message": error})

    CORE_CONFIG.logger.info(f"Successfully sent API request to {instance_api.endpoint}{action}")

    return JSONResponse(content={"message": resp.json()})
