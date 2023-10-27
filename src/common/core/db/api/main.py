from contextlib import suppress
from datetime import datetime
from os import environ, getpid
from os.path import join, sep
from random import uniform
from sys import path as sys_path
from typing import Annotated, Dict, Literal

from fastapi.responses import JSONResponse
from pydantic import BaseModel


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from fastapi import BackgroundTasks, FastAPI, Form, status

from database import Database  # type: ignore
from models import Actions, Jobs_runs  # type: ignore

from app.core import CoreConfig  # type: ignore

CORE_CONFIG = CoreConfig("core", **environ)


class OverrideDatabase(Database):
    def cleanup_actions_excess(self, max_actions: int) -> str:
        """Remove excess actions."""
        result = 0
        with suppress(BaseException), self._db_session() as session:
            rows_count = session.query(Actions).count()
            if rows_count > max_actions:
                result = session.query(Actions).order_by(Actions.date.asc()).limit(rows_count - max_actions).with_for_update().delete(synchronize_session=False)
                session.commit()

        return (self._exceptions.get(getpid()) or [str(result)]).pop()

    def cleanup_jobs_runs_excess(self, max_runs: int) -> str:
        """Remove excess actions."""
        result = 0
        with suppress(BaseException), self._db_session() as session:
            rows_count = session.query(Jobs_runs).count()
            if rows_count > max_runs:
                result = session.query(Jobs_runs).order_by(Jobs_runs.end_date.asc()).limit(rows_count - max_runs).with_for_update().delete(synchronize_session=False)
                session.commit()

        return (self._exceptions.get(getpid()) or [str(result)]).pop()


DB = OverrideDatabase(CORE_CONFIG.logger, CORE_CONFIG.DATABASE_URI)

description = """## API's description

This API is used by Bunkerweb to execute actions on the database."""

app = FastAPI(title="Bunkerweb Database API", description=description, version="1.0")
root_path = "/db"


class ErrorMessage(BaseModel):
    message: str


@app.post(
    "/actions/cleanup",
    response_model=Dict[Literal["message"], str],
    summary="Cleanup the oldest actions that are over the limit",
    response_description="Cleanup result",
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
async def cleanup_actions(method: str, background_tasks: BackgroundTasks, limit: Annotated[int, Form()] = 10000):
    """
    Cleanup the oldest actions that are older than the limit.
    """
    actions_cleaned = DB.cleanup_actions_excess(limit)

    if "database is locked" in actions_cleaned or "file is not a database" in actions_cleaned:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't cleanup actions : database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif not actions_cleaned.isdigit():
        return JSONResponse(content={"message": actions_cleaned}, status_code=500)

    message = f"Cleaned {actions_cleaned} actions from the database."
    background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "POST", "method": method, "tags": ["plugin", "action"], "title": "Cleanup actions", "description": message})
    return JSONResponse(content={"message": message})


@app.post(
    "/jobs/cleanup",
    response_model=Dict[Literal["message"], str],
    summary="Cleanup the oldest jobs runs that are over the limit",
    response_description="Cleanup result",
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
async def cleanup_jobs(method: str, background_tasks: BackgroundTasks, limit: Annotated[int, Form()] = 1000):
    """
    Cleanup the oldest jobs runs that are older than the limit.
    """
    actions_cleaned = DB.cleanup_jobs_runs_excess(limit)

    if "database is locked" in actions_cleaned or "file is not a database" in actions_cleaned:
        retry_in = str(uniform(1.0, 5.0))
        CORE_CONFIG.logger.warning(f"Can't cleanup jobs runs : database is locked or had trouble handling the request, retry in {retry_in} seconds")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": f"Database is locked or had trouble handling the request, retry in {retry_in} seconds"},
            headers={"Retry-After": retry_in},
        )
    elif not actions_cleaned.isdigit():
        return JSONResponse(content={"message": actions_cleaned}, status_code=500)

    message = f"Cleaned {actions_cleaned} jobs runs from the database."
    background_tasks.add_task(DB.add_action, {"date": datetime.now(), "api_method": "POST", "method": method, "tags": ["plugin", "job"], "title": "Cleanup jobs runs", "description": message})
    return JSONResponse(content={"message": message})
