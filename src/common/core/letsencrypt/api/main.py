# -*- coding: utf-8 -*-
from os import environ
from os.path import join, sep
from sys import path as sys_path
from typing import Annotated


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from fastapi import FastAPI, Form, Request, status
from fastapi.responses import JSONResponse

from API import API  # type: ignore
from api_caller import ApiCaller  # type: ignore
from database import Database  # type: ignore

from app.core import CoreConfig  # type: ignore

CORE_CONFIG = CoreConfig("core", **environ)

DB = Database(CORE_CONFIG.logger, CORE_CONFIG.DATABASE_URI)

description = """## API's description

This API is used by Bunkerweb to handle Let's Encrypt challenges and certificates."""

app = FastAPI(
    title="Bunkerweb Let's Encrypt API",
    description=description,
    version="1.0",
)
root_path = "/lets-encrypt"

API_CALLER = ApiCaller()


def update_apis():
    global API_CALLER

    db_instances = DB.get_instances()

    if db_instances == "retry":
        CORE_CONFIG.logger.warning("Can't get instances : Database is locked or had trouble handling the request, keep using old API's")
    elif isinstance(db_instances, str):
        CORE_CONFIG.logger.error(f"Can't get instances in database : {db_instances}, keep using old API's")
    else:
        API_CALLER.apis = [
            API(
                f"http://{instance['hostname']}:{instance['port']}",
                instance["server_name"],
            )
            for instance in db_instances
        ]


@app.middleware("http")
async def middleware(request: Request, call_next):
    update_apis()
    return await call_next(request)


@app.post("/challenge")
async def post_challenge(token: Annotated[str, Form()], validation: Annotated[str, Form()]):
    failed_apis, resp = API_CALLER.send_to_apis(
        "POST",
        "/lets-encrypt/challenge",
        data={"token": token, "validation": validation},
        response=True,
    )

    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR if failed_apis else status.HTTP_200_OK, content=resp)


@app.delete("/challenge")
async def delete_challenge(token: Annotated[str, Form()]):
    failed_apis, resp = API_CALLER.send_to_apis(
        "DELETE",
        "/lets-encrypt/challenge",
        data={"token": token},
        response=True,
    )

    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR if failed_apis else status.HTTP_200_OK, content=resp)


@app.post("/certificates")
async def post_certificates(certificates: Annotated[bytes, Form()]):
    failed_apis, resp = API_CALLER.send_to_apis(
        "POST",
        "/lets-encrypt/certificates",
        files={"archive.tar.gz": certificates},
        response=True,
    )

    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR if failed_apis else status.HTTP_200_OK, content=resp)


__ALL__ = (app, root_path)
