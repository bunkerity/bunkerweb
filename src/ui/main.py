# -*- coding: utf-8 -*-
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import FastAPI, Request
import requests, traceback, json  # noqa: E401
from utils import exception_res
from config import app_name, description, summary, version, contact, license_info, openapi_tags
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from routers import instances, plugins, config, misc, jobs, custom_configs, actions
from pathlib import Path
from logging import Logger
from os.path import join, sep
from sys import path as sys_path
import time
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)
CORE_API = UI_CONFIG.CORE_ADDR
HEALTHY_PATH = Path(sep, "var", "tmp", "bunkerweb", "ui.healthy")

deps_path = join(sep, "usr", "share", "bunkerweb", "utils")
if deps_path not in sys_path:
  sys_path.append(deps_path)

from logger import setup_logger  # type: ignore

LOGGER: Logger = setup_logger("UI")

# Validate data to run app
if not isinstance(UI_CONFIG.WAIT_RETRY_INTERVAL, int) and (not UI_CONFIG.WAIT_RETRY_INTERVAL.isdigit() or int(UI_CONFIG.WAIT_RETRY_INTERVAL) < 1):
    LOGGER.error(f"Invalid WAIT_RETRY_INTERVAL provided: {UI_CONFIG.WAIT_RETRY_INTERVAL}, It must be a positive integer.")
    exit(1)
if not isinstance(UI_CONFIG.MAX_WAIT_RETRIES, int) and (not UI_CONFIG.MAX_WAIT_RETRIES.isdigit() or int(UI_CONFIG.MAX_WAIT_RETRIES) < 1):
    LOGGER.error(f"Invalid MAX_WAIT_RETRIES provided: {UI_CONFIG.MAX_WAIT_RETRIES}, It must be a positive integer.")
    exit(1)

# Check CORE to run UI
core_running = False

for x in range(UI_CONFIG.MAX_WAIT_RETRIES):
    if core_running :
        break
    
    try :
        req = requests.get(f"{CORE_API}/ping")
        LOGGER.info(f"PING {req} | TRY {x}")
    except:
        core_running = False
    time.sleep(UI_CONFIG.WAIT_RETRY_INTERVAL)

if(core_running == True):
    LOGGER.info("PING CORE SUCCEED")

if(core_running == False):
    LOGGER.error("PING CORE FAILED, STOP STARTING UI")
    exit(1)

# Start UI app
base = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title=app_name, description=description, summary=summary, version=version, contact=contact, license_info=license_info, openapi_tags=openapi_tags)
LOGGER.info("START RUNNING UI")

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

try :
    app.include_router(misc.router)
    app.include_router(instances.router)
    app.include_router(plugins.router)
    app.include_router(config.router)
    app.include_router(custom_configs.router)
    app.include_router(jobs.router)
    app.include_router(actions.router)
    LOGGER.info("ADDING UI ROUTES")
except:
    LOGGER.error("ADDING UI ROUTES")
    exit(1)

try :
    app.mount("/", StaticFiles(directory=f"{base}/static"), name="static")
    LOGGER.info("ADDING UI STATIC FILES")
except :
    LOGGER.error("ADDING UI STATIC FILES")
    exit(1)

# App is running
if not HEALTHY_PATH.exists():
    HEALTHY_PATH.write_text("ok", encoding="utf-8")

LOGGER.info("UI STARTED PROPERLY")