#!/usr/bin/env python3
from typing import Dict, List

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..auth.guard import guard
from ..utils import get_db

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _parse_search_panes(raw: str) -> Dict[str, List[str]]:
    """Parse the UI search-panes string ``field1:v1,v2;field2:v3`` into a ``{field: [values]}`` filter dict."""
    filters: Dict[str, List[str]] = {}
    for part in raw.split(";"):
        field, separator, values = part.partition(":")
        if not separator:
            continue
        field = field.strip()
        selected = [value for value in values.split(",") if value]
        if field and selected:
            filters[field] = selected
    return filters


@router.get("/requests", dependencies=[Depends(guard)])
def query_metrics_requests(
    start: int = 0,
    length: int = 10,
    search: str = "",
    order_column: str = "date",
    order_dir: str = "desc",
    search_panes: str = "",
    count_only: bool = False,
    include_pane_counts: bool = True,
) -> JSONResponse:
    """Persisted blocked-request reports (DB-backed; replaces the per-instance Lua scrape).

    Mirrors the DataTables contract the UI sends: pagination, free-text ``search``, ``search_panes``
    facet filters, and ``count_only``. Returns ``{status, total, filtered, data[, pane_counts]}``.
    """
    db = get_db()
    filters = _parse_search_panes(search_panes)
    result = db.get_metrics_requests(
        start=start,
        length=length,
        search=search,
        order_column=order_column,
        order_dir=order_dir,
        filters=filters,
        count_only=count_only,
    )
    if include_pane_counts:
        result["pane_counts"] = db.get_metrics_facets(search=search, filters=filters)
    return JSONResponse(status_code=200, content={"status": "success", **result})


@router.get("/requests/timeseries", dependencies=[Depends(guard)])
def query_metrics_timeseries(start: int, end: int, bucket: str = "hour", search_panes: str = "") -> JSONResponse:
    db = get_db()
    filters = _parse_search_panes(search_panes)
    try:
        result = db.get_metrics_timeseries(start=start, end=end, bucket=bucket, filters=filters)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
    return JSONResponse(status_code=200, content={"status": "success", **result})


@router.get("/requests/top-offenders", dependencies=[Depends(guard)])
def query_metrics_top_offenders(start: int, end: int, limit: int = 10, search_panes: str = "") -> JSONResponse:
    db = get_db()
    filters = _parse_search_panes(search_panes)
    try:
        result = db.get_metrics_top_offenders(start=start, end=end, limit=limit, filters=filters)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
    return JSONResponse(status_code=200, content={"status": "success", "offenders": result})


@router.get("/requests/top-rules", dependencies=[Depends(guard)])
def query_metrics_top_rules(start: int, end: int, limit: int = 10) -> JSONResponse:
    db = get_db()
    try:
        result = db.get_metrics_top_rules(start=start, end=end, limit=limit)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
    return JSONResponse(status_code=200, content={"status": "success", "rules": result})
