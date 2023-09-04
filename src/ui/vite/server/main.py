from typing import Union
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import FastAPI
import requests
from utils import set_res_from_req
from config import API_URL, app_name, description, summary, version, contact, license_info, openapi_tags

app = FastAPI(
    title=app_name,
    description=description,
    summary=summary,
    version=version,
    contact=contact,
    license_info=license_info,
    openapi_tags=openapi_tags
)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    print(request, exc)
    return PlainTextResponse(str({"type" : "error", "status" : exc.status_code, "message": exc.detail, "data" : {}}), status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return PlainTextResponse(str({"type" : "error", "status" : 400, "message": "Invalid data send on request", "data" : {}}), status_code=400)

from routers import instances, plugins, config

app.include_router(instances.router)
app.include_router(plugins.router)
app.include_router(config.router)


