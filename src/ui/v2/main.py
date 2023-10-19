from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import FastAPI, Request
from utils import exception_res
from config import app_name, description, summary, version, contact, license_info, openapi_tags
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv
from routers import instances, plugins, config, misc, jobs, custom_configs, admin

load_dotenv()
DEV_MODE = os.getenv("DEV_MODE")

base = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title=app_name, description=description, summary=summary, version=version, contact=contact, license_info=license_info, openapi_tags=openapi_tags)


if DEV_MODE:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )



# For futur log UI
@app.middleware("http")
async def get_ui_req(request: Request, call_next):
    response = await call_next(request)
    return response
    


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(exception_res(exc.status_code, request.url.path, exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(exception_res(400, request.url.path, "Invalid data send on request"))

app.include_router(misc.router)
app.include_router(instances.router)
app.include_router(plugins.router)
app.include_router(config.router)
app.include_router(custom_configs.router)
app.include_router(jobs.router)
app.include_router(admin.router)

app.mount("/", StaticFiles(directory=f'{base}/static'), name="static")
