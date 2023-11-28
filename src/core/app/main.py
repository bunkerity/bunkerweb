#!/usr/bin/python3
# -*- coding: utf-8 -*-

from gc import collect as gc_collect
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address
from threading import Event, Thread
from os import sep
from os.path import join
from signal import SIGINT, SIGTERM, signal
from sys import path as sys_path
from time import sleep


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from fastapi import FastAPI, Request, status
from fastapi.datastructures import Address
from fastapi.responses import JSONResponse

from API import API  # type: ignore
from .core import BUNKERWEB_VERSION, description, tags_metadata
from .dependencies import CORE_CONFIG, DB, HEALTHY_PATH, listen_for_dynamic_instances, SCHEDULER, seen_instance, stop, stop_event, update_app_mounts
from .utils import listen_dynamic_instances, run_repeatedly, startup
from .watchdog_observer import WatchdogObserver

scheduler_initialized = Event()
database_initialized = Event()

observer = None


def stop_app(status):
    stop_event.set()
    if observer:
        observer.stop()
    stop(status)


def exit_handler(signum, frame):
    CORE_CONFIG.logger.info("Stop signal received, exiting...")
    stop_app(0)


signal(SIGINT, exit_handler)
signal(SIGTERM, exit_handler)


# ? APP
app = FastAPI(
    title="BunkerWeb API",
    description=description,
    summary="The API used by BunkerWeb to communicate with the database and the instances",
    version=BUNKERWEB_VERSION,
    contact={"name": "BunkerWeb Team", "url": "https://www.bunkerweb.io", "email": "contact@bunkerity.com"},
    license_info={"name": "GNU Affero General Public License v3.0", "url": "https://github.com/bunkerity/bunkerweb/blob/master/LICENSE.md"},
    openapi_tags=tags_metadata,
)


def run_pending_jobs() -> None:
    if not scheduler_initialized.is_set():
        while not DB.is_scheduler_initialized():
            CORE_CONFIG.logger.warning(f"run_pending_jobs - Scheduler is not initialized yet, retrying in {CORE_CONFIG.WAIT_RETRY_INTERVAL} seconds ...")
            sleep(float(CORE_CONFIG.WAIT_RETRY_INTERVAL))
        scheduler_initialized.set()

    SCHEDULER.run_pending()


def instances_healthcheck() -> None:
    if not database_initialized.is_set():
        if not DB or not DB.is_initialized():
            return
        database_initialized.set()

    instance_apis = DB.get_instances()

    if not instance_apis:
        CORE_CONFIG.logger.warning("instances_healthcheck - No instances found in database, skipping healthcheck ...")
        return
    elif isinstance(instance_apis, str):
        CORE_CONFIG.logger.error(f"instances_healthcheck - Can't get instances from database : {instance_apis}, skipping healthcheck ...")
        return

    for instance in instance_apis:
        instance_api = API(f"http://{instance['hostname']}:{instance['port']}", instance["server_name"])
        sent, err, status, resp = instance_api.request("GET", "ping")
        if not sent:
            CORE_CONFIG.logger.warning(f"instances_healthcheck - Can't send API request to {instance_api.endpoint}ping : {err}, healthcheck will be retried in 30 seconds ...")
            continue
        else:
            if status != 200:
                CORE_CONFIG.logger.warning(f"instances_healthcheck - Error while sending API request to {instance_api.endpoint}ping : status = {resp['status']}, msg = {resp['msg']}, healthcheck will be retried in 30 seconds ...")
                continue
            else:
                CORE_CONFIG.logger.info(f"instances_healthcheck - Successfully sent API request to {instance_api.endpoint}ping, marking instance as seen ...")

                Thread(target=seen_instance, args=(instance["hostname"],)).start()


@app.middleware("http")
async def validate_request(request: Request, call_next):
    try:
        assert isinstance(request.client, Address)
    except AssertionError:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"result": "ko"})

    if CORE_CONFIG.check_whitelist and (request.client.host != "127.0.0.1" if CORE_CONFIG.integration != "Linux" else True):
        if not CORE_CONFIG.whitelist:
            CORE_CONFIG.logger.warning(f'Unauthorized access attempt from {request.client.host} (whitelist check is set to "yes" but the whitelist is empty), aborting...')
            return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"result": "ko"})

        remote_ip = ip_address(request.client.host)
        for whitelist in CORE_CONFIG.whitelist:
            if isinstance(whitelist, (IPv4Network, IPv6Network)):
                if remote_ip in whitelist:
                    break
            elif isinstance(whitelist, (IPv4Address, IPv6Address)):
                if remote_ip == whitelist:
                    break
        else:
            CORE_CONFIG.logger.warning(f"Unauthorized access attempt from {remote_ip} (not in whitelist), aborting...")
            return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"result": "ko"})

    if CORE_CONFIG.check_token:
        if "Authorization" not in request.headers:
            CORE_CONFIG.logger.warning(f"Unauthorized access attempt from {request.client.host} (missing token), aborting...")
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"result": "ko"})
        elif request.headers["Authorization"] != f"Bearer {CORE_CONFIG.core_token}":
            CORE_CONFIG.logger.warning(f"Unauthorized access attempt from {request.client.host} (invalid token), aborting...")
            return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"result": "ko"})

    return await call_next(request)


@app.get("/ping", tags=["misc"])
async def get_ping() -> JSONResponse:
    """Get BunkerWeb API ping"""
    return JSONResponse(content={"message": "pong"})


@app.get("/version", tags=["misc"])
async def get_version() -> JSONResponse:
    """Get BunkerWeb API version"""
    return JSONResponse(content={"message": BUNKERWEB_VERSION})


if CORE_CONFIG.hot_reload:
    CORE_CONFIG.logger.info("🐕 Hot reload is enabled, starting watchdog ...")
    observer = WatchdogObserver()

startup()

# Include the routers to the main app

from .routers import actions, config, custom_configs, instances, jobs, plugins

app.include_router(actions.router)
app.include_router(config.router)
app.include_router(custom_configs.router)
app.include_router(instances.router)
app.include_router(jobs.router)
app.include_router(plugins.router)

update_app_mounts(app)

if CORE_CONFIG.use_redis:
    if CORE_CONFIG.REDIS_HOST:
        listen_for_dynamic_instances.set()
        Thread(target=listen_dynamic_instances, name="redis_listener").start()
    else:
        CORE_CONFIG.logger.warning("USE_REDIS is set to yes but REDIS_HOST is not defined, app will not listen for dynamic instances")

Thread(target=run_repeatedly, args=(int(CORE_CONFIG.HEALTHCHECK_INTERVAL), instances_healthcheck), kwargs={"wait_first": True}, name="instances_healthcheck").start()
Thread(target=run_repeatedly, args=(1, run_pending_jobs), name="run_pending_jobs").start()

if not HEALTHY_PATH.exists():
    HEALTHY_PATH.write_text("ok", encoding="utf-8")

gc_collect()

if __name__ == "__main__":
    from uvicorn import run

    run(app, host=CORE_CONFIG.LISTEN_ADDR, port=int(CORE_CONFIG.LISTEN_PORT), reload=True, log_level=CORE_CONFIG.log_level, proxy_headers=False, server_header=False, date_header=False)
