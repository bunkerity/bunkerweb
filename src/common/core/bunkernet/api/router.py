#!/usr/bin/env python3
"""API router for the BunkerNet effectiveness pilot, mounted at /bunkernet (guard injected)."""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.utils import get_db  # type: ignore

router = APIRouter(tags=["bunkernet"])


@router.get("/effectiveness")
def bunkernet_effectiveness(since: int = Query(0, ge=0, description="Epoch-seconds lower bound (0 = last 24h)")) -> JSONResponse:
    data = get_db().ext("bunkernet").get_effectiveness(since=since or None)
    return JSONResponse(status_code=200, content={"status": "success", "data": data})


@router.get("/stats")
def bunkernet_stats(
    metric: str = Query("", description="Filter by metric name"),
    instance_hostname: str = Query("", description="Filter by instance hostname"),
    since: int = Query(0, ge=0, description="Epoch-seconds lower bound"),
    limit: int = Query(1000, ge=1, le=10000),
) -> JSONResponse:
    data = (
        get_db()
        .ext("bunkernet")
        .get_stats(
            metric=metric or None,
            instance_hostname=instance_hostname if instance_hostname else None,
            since=since or None,
            limit=limit,
        )
    )
    return JSONResponse(status_code=200, content={"status": "success", "data": data})
