from typing import Union
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import FastAPI
import requests, json
from utils import exception_res
from config import dev_mode, API_URL, app_name, description, summary, version, contact, license_info, openapi_tags
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title=app_name,
    description=description,
    summary=summary,
    version=version,
    contact=contact,
    license_info=license_info,
    openapi_tags=openapi_tags
)

if dev_mode :

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/test")
    async def test():
        return {"test": "test"}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(exception_res(exc.status_code, request.url.path, exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(exception_res(400, request.url.path, "Invalid data send on request"))


from routers import instances, plugins, config, misc, jobs, custom_configs

app.include_router(misc.router)
app.include_router(instances.router)
app.include_router(plugins.router)
app.include_router(config.router)
app.include_router(custom_configs.router)
app.include_router(jobs.router)


