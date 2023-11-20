# -*- coding: utf-8 -*-
from contextlib import suppress
from datetime import datetime, timedelta
from random import uniform
from typing import Annotated, Dict, List, Literal, Union
from fastapi import APIRouter, BackgroundTasks, status, Path as fastapi_Path
from fastapi.responses import JSONResponse

from ..models import ErrorMessage, InstanceWithInfo, InstanceWithMethod, UpsertInstance
from ..dependencies import CORE_CONFIG, DB, test_and_send_to_instances
from API import API  # type: ignore

router = APIRouter(
    prefix="/instances",
    tags=["instances"],
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


@router.get("", response_model=List[InstanceWithInfo], summary="Get BunkerWeb instances", response_description="BunkerWeb instances")
async def get_instances(background_tasks: BackgroundTasks):
    """
    Get BunkerWeb instances with the following information:

    - **hostname**: The hostname of the instance
    - **port**: The port of the instance
    - **server_name**: The server name of the instance
    - **method**: The method of the instance
    """
    db_instances = DB.get_instances()

    if db_instances == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't get instances : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif isinstance(db_instances, str):
        message = f"Can't get instances in database : {db_instances}"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "GET", "method": "unknown", "tags": ["instance"], "title": "Get instances failed", "description": message, "status": "error"})
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": db_instances},
        )

    instances = []
    for instance in db_instances:
        data = instance.copy()
        data["status"] = "down"
        with suppress(BaseException):
            sent, err, status_code, resp = API(
                f"http://{instance['hostname']}:{instance['port']}",
                instance["server_name"],
            ).request("GET", "ping", timeout=1)
            if sent and status_code == 200:
                data["status"] = "up" if instance["last_seen"] and instance["last_seen"] >= datetime.now() - timedelta(seconds=int(CORE_CONFIG.HEALTHCHECK_INTERVAL) * 2) else "down"
        instances.append(data)
    return instances


@router.put(
    "",
    response_model=Dict[Literal["message"], str],
    summary="Upsert one BunkerWeb instance",
    response_description="Message",
    responses={
        status.HTTP_201_CREATED: {
            "description": "Instance(s) successfully created",
            "model": ErrorMessage,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "All instances failed to be upserted",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Not authorized to update the instance",
            "model": ErrorMessage,
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is locked or had trouble handling the request",
            "model": ErrorMessage,
        },
    },
)
async def upsert_instance(instances: Union[UpsertInstance, List[UpsertInstance]], background_tasks: BackgroundTasks, method: str, reload: bool = True) -> JSONResponse:
    """
    Upsert one or more BunkerWeb instances with the following information:

    - **hostname**: The hostname of the instance
    - **port**: The port of the instance
    - **server_name**: The server name of the instance
    """

    if method == "static":
        message = "Can't upsert instance(s) : method can't be static"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "PUT", "method": method, "tags": ["instance"], "title": "Upsert instance(s) failed", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    decisions = {"created": [], "updated": [], "failed": {}}
    status_code = None

    if not isinstance(instances, list):
        resp = DB.upsert_instance(**instances.model_dump(exclude=("last_seen",)), method=method)  # type: ignore

        if resp == "method_conflict":
            message = f"Can't upsert instance {instances.hostname} because it is either static or was created by the core or the autoconf and the method isn't one of them"
            CORE_CONFIG.logger.warning(message)
            decisions["failed"][instances.hostname] = message
        elif resp == "retry":
            retry_in = str(uniform(1.0, 5.0))
            CORE_CONFIG.logger.warning(f"Can't upsert instance to database : {resp}, retry in {retry_in} seconds")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
                headers={"Retry-After": retry_in},
            )
        elif resp not in ("created", "updated"):
            CORE_CONFIG.logger.error(f"Can't upsert instance to database : {resp}")
            decisions["failed"][instances.hostname] = resp
        else:
            decisions[resp].append(instances)
    else:
        for instance in instances:
            resp = DB.upsert_instance(**instance.model_dump(exclude=("last_seen",)), method=method)  # type: ignore

            if resp == "method_conflict":
                message = f"Can't upsert instance {instance.hostname} because it is either static or was created by the core or the autoconf and the method isn't one of them"
                CORE_CONFIG.logger.warning(message)
                decisions["failed"][instance.hostname] = message
                continue
            elif resp == "retry":
                retry_in = str(uniform(1.0, 5.0))
                CORE_CONFIG.logger.warning(f"Can't upsert instance {instance.hostname} to database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
                    headers={"Retry-After": retry_in},
                )
            elif resp not in ("created", "updated"):
                CORE_CONFIG.logger.error(f"Can't upsert instance {instance.hostname} to database : {resp}")
                decisions["failed"][instance.hostname] = resp
                continue
            decisions[resp].append(instance)

    message = "Instance(s) "

    if decisions["created"]:
        message += f"{', '.join(instance.hostname for instance in decisions['created'])} successfully created"
    if decisions["updated"]:
        if decisions["created"]:
            message += "and "
        message += f"{', '.join(instance.hostname for instance in decisions['updated'])} successfully updated"
    if decisions["failed"]:
        if decisions["created"] or decisions["updated"]:
            message += " but "
        if not decisions["created"] and not decisions["updated"]:
            status_code = status.HTTP_400_BAD_REQUEST
        message += f"{', '.join(f'{hostname} ({reason})' for hostname, reason in decisions['failed'].items())} failed to be upserted"

    background_tasks.add_task(
        DB.add_action,
        {
            "date": datetime.now(),
            "api_method": "PUT",
            "method": method,
            "tags": ["instance"],
            "title": "Upsert instance(s)",
            "description": message,
            "status": "error" if decisions["failed"] and not decisions["created"] and not decisions["updated"] else "success",
        },
    )
    CORE_CONFIG.logger.info(f"{'✅' if not decisions['failed'] else '⚠️'} {message} in the database")

    if reload:
        if decisions["created"]:
            background_tasks.add_task(test_and_send_to_instances, {instance.to_api() for instance in decisions["created"]}, "all")
        if decisions["updated"]:
            CORE_CONFIG.logger.info(
                f"Skipping sending data to instance{'s' if len(decisions) > 1 else ''} : {', '.join(instance.hostname for instance in decisions['updated'])}, as {'all' if len(decisions) > 1 else 'this'}"
                + f" instance{'s' if len(decisions) > 1 else ''} {'were' if len(decisions) > 1 else 'was'} already in the database"
            )

    return JSONResponse(status_code=status_code or (status.HTTP_201_CREATED if not decisions["updated"] else status.HTTP_200_OK), content={"message": message})


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
async def get_instance(instance_hostname: Annotated[str, fastapi_Path(title="The hostname of the instance", min_length=1, max_length=256)], background_tasks: BackgroundTasks):
    """
    Get a BunkerWeb instance with the following information:

    - **hostname**: The hostname of the instance
    - **port**: The port of the instance
    - **server_name**: The server name of the instance
    """
    db_instance = DB.get_instance(instance_hostname)

    if not db_instance:
        message = f"Instance {instance_hostname} not found"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "GET", "method": "unknown", "tags": ["instance"], "title": f"Tried to get instance {instance_hostname}", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif db_instance == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't get instance {instance_hostname} : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif isinstance(db_instance, str):
        message = f"Can't get instance {instance_hostname} in database : {db_instance}"
        background_tasks.add_task(
            DB.add_action,
            {"date": datetime.now(), "api_method": "GET", "method": "unknown", "tags": ["instance"], "title": f"Tried to get instance {instance_hostname}", "description": message, "status": "error"},
        )
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": db_instance},
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
async def delete_instance(instance_hostname: str, method: str, background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Delete a BunkerWeb instance
    """

    if method == "static":
        message = f"Can't delete instance {instance_hostname} : method can't be static"
        background_tasks.add_task(
            DB.add_action,
            {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["instance"], "title": f"Tried to delete instance {instance_hostname}", "description": message, "status": "error"},
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})

    resp = DB.remove_instance(instance_hostname, method=method)

    if resp == "not_found":
        message = f"Instance {instance_hostname} not found"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["instance"], "title": f"Tried to delete instance {instance_hostname}", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif resp == "method_conflict":
        message = f"Can't delete instance {instance_hostname} because it is either static or was created by the core or the autoconf and the method isn't one of them"
        background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["instance"], "title": f"Tried to delete instance {instance_hostname}", "description": message, "status": "error"})
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"message": message})
    elif resp == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't remove instance to database : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif resp:
        message = f"Can't remove instance to database : {resp}"
        background_tasks.add_task(
            DB.add_action,
            {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["instance"], "title": "Delete instance failed", "description": message, "status": "error"},
        )
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": resp},
        )

    background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "DELETE", "method": method, "tags": ["instance"], "title": "Delete instance", "description": f"Delete instance {instance_hostname}"})
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
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database is locked or had trouble handling the request",
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
async def send_instance_action(instance_hostname: str, action: Literal["ping", "bans", "stop", "reload"], method: str, background_tasks: BackgroundTasks) -> JSONResponse:  # TODO: maybe add a "start" action
    """
    Delete a BunkerWeb instance
    """
    db_instance = DB.get_instance(instance_hostname)

    if not db_instance:
        message = f"Instance {instance_hostname} not found"
        background_tasks.add_task(
            DB.add_action, {"date": datetime.now(), "api_method": "POST", "method": method, "tags": ["instance"], "title": f"Tried to send action {action} to instance {instance_hostname}", "description": message, "status": "error"}
        )
        CORE_CONFIG.logger.warning(message)
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": message})
    elif db_instance == "retry":
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't get instance {instance_hostname} : Database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif isinstance(db_instance, str):
        message = f"Can't get instance {instance_hostname} in database : {db_instance}"
        background_tasks.add_task(
            DB.add_action,
            {"date": datetime.now(), "api_method": "POST", "method": method, "tags": ["instance"], "title": f"Tried to send action {action} to instance {instance_hostname}", "description": message, "status": "error"},
        )
        CORE_CONFIG.logger.error(message)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": db_instance},
        )

    instance_api = API(
        f"http://{db_instance['hostname']}:{db_instance['port']}",
        db_instance["server_name"],
    )

    sent, err, status_code, resp = instance_api.request("GET" if action in ("ping", "bans") else "POST", f"/{action}", timeout=(5, 10))

    if not sent:
        error = f"Can't send API request to {instance_api.endpoint}{action} : {err}"
        background_tasks.add_task(
            DB.add_action,
            {"date": datetime.now(), "api_method": "POST", "method": method, "tags": ["instance"], "title": f"Send instance action {action} failed to instance {instance_hostname}", "description": error, "status": "error"},
        )
        CORE_CONFIG.logger.error(error)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )
    else:
        if status_code != 200:
            resp = resp.json()
            error = f"Error while sending API request to {instance_api.endpoint}{action} : status = {resp['status']}, msg = {resp['msg']}"
            background_tasks.add_task(
                DB.add_action,
                {"date": datetime.now(), "api_method": "POST", "method": method, "tags": ["instance"], "title": f"Send instance action {action} failed to instance {instance_hostname}", "description": error, "status": "error"},
            )
            CORE_CONFIG.logger.error(error)
            return JSONResponse(status_code=status_code, content={"message": error})

    background_tasks.add_task(
        DB.add_action,
        {
            "date": datetime.now(),
            "api_method": "POST",
            "method": method,
            "tags": ["instance"],
            "title": f"Send instance action {action} to instance {instance_hostname}",
            "description": f"Successfully sent API request to {instance_api.endpoint}{action}",
        },
    )
    CORE_CONFIG.logger.info(f"Successfully sent API request to {instance_api.endpoint}{action}")

    return JSONResponse(content={"message": resp.json()})
