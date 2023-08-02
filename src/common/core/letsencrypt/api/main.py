from os import environ
from os.path import join, sep
from sys import path as sys_path
from typing import Annotated

from fastapi.responses import JSONResponse

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("api",), ("utils",), ("db",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from fastapi import FastAPI, Form, Request

from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from database import Database  # type: ignore
from logger import setup_logger  # type: ignore

from core import ApiConfig

API_CONFIG = ApiConfig("core", **environ)
LOGGER = setup_logger("CORE", API_CONFIG.log_level)

DB = Database(LOGGER, API_CONFIG.DATABASE_URI)

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
    apis = []

    for instance in DB.get_instances():
        apis.append(
            API(
                f"http://{instance['hostname']}:{instance['port']}",
                instance["server_name"],
            )
        )

    API_CALLER.apis = apis


@app.middleware("http")
async def middleware(request: Request, call_next):
    update_apis()
    return await call_next(request)


@app.post("/challenge")
async def post_challenge(
    token: Annotated[str, Form()], validation: Annotated[str, Form()]
):
    _, resp = API_CALLER.send_to_apis(
        "POST",
        "/lets-encrypt/challenge",
        data={"token": token, "validation": validation},
        response=True,
    )

    return JSONResponse(status_code=int(resp["status"]), content=resp)


@app.delete("/challenge")
async def delete_challenge(token: Annotated[str, Form()]):
    _, resp = API_CALLER.send_to_apis(
        "DELETE",
        "/lets-encrypt/challenge",
        data={"token": token},
        response=True,
    )

    return JSONResponse(status_code=int(resp["status"]), content=resp)


@app.post("/certificates")
async def post_certificates(certificates: Annotated[bytes, Form()]):
    _, resp = API_CALLER.send_to_apis(
        "POST",
        "/lets-encrypt/certificates",
        files={"archive.tar.gz": certificates},
        response=True,
    )

    return JSONResponse(status_code=int(resp["status"]), content=resp)


__ALL__ = (app, root_path)
