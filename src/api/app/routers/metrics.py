#!/usr/bin/env python3
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..auth.guard import guard
from ..deps import get_instances_api_caller
from ..utils import get_db

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _merge_timing(accumulator: Dict[str, float], sample: Dict[str, Any]) -> Dict[str, float]:
    """Fold one instance's {count, sum, max} aggregate into the running total.

    Counts and sums add, max is the larger of the two -- the same arithmetic the Lua side
    uses to combine workers, applied one level up to combine instances.
    """
    count = _number(sample.get("count"))
    total = _number(sample.get("sum"))
    peak = _number(sample.get("max"))
    if not accumulator:
        return {"count": count, "sum": total, "max": peak}
    accumulator["count"] += count
    accumulator["sum"] += total
    accumulator["max"] = max(accumulator["max"], peak)
    return accumulator


def _number(value: Any) -> float:
    """Coerce a scraped aggregate field to a number. A malformed entry from one instance
    must not take down the whole fan-out."""
    if isinstance(value, bool) or value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_search_panes(raw: str) -> Dict[str, List[str]]:
    """Parse the UI search-panes string ``field1:v1,v2;field2:v3`` into a ``{field: [values]}`` filter dict.

    ``protocol`` doubles as the HTTP/TCP/UDP filter on every endpoint here — it is an ordinary
    facet field, so it needs no parameter of its own. ``protocol:stream`` is expanded to the two
    L4 protocols, which is how a caller asks for "everything that is not HTTP" in one term.
    """
    filters: Dict[str, List[str]] = {}
    for part in raw.split(";"):
        field, separator, values = part.partition(":")
        if not separator:
            continue
        field = field.strip()
        selected = [value for value in values.split(",") if value]
        if field == "protocol" and "stream" in selected:
            selected = [value for value in selected if value != "stream"] + ["tcp", "udp"]
            selected = list(dict.fromkeys(selected))
        if field and selected:
            filters[field] = selected
    return filters


@router.get("/timings", dependencies=[Depends(guard)])
def query_metrics_timings(api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Report how long each plugin takes in each request phase, merged across instances.

    Unlike the other endpoints here, timings are not persisted: they live in each instance's
    shared memory and are read by fanning out, the same way the web-cache router reads cache
    status. Whole-request duration appears as plugin ``metrics`` / phase ``request``.
    """
    ok, responses = api_caller.send_to_apis("GET", "/metrics/timings", response=True)
    responses = responses or {}

    merged: Dict[str, Dict[str, Dict[str, float]]] = {}
    for response in responses.values():
        if not isinstance(response, dict) or response.get("status") != "success":
            continue
        payload = response.get("msg")
        if not isinstance(payload, dict):
            continue
        for plugin_id, phases in payload.items():
            if not isinstance(phases, dict):
                continue
            for phase, sample in phases.items():
                if not isinstance(sample, dict):
                    continue
                merged.setdefault(plugin_id, {})[phase] = _merge_timing(merged.get(plugin_id, {}).get(phase, {}), sample)

    # mean is derived rather than stored: it is what an operator actually reads, and keeping
    # it out of the aggregate means workers and instances stay mergeable by plain addition.
    for phases in merged.values():
        for stats in phases.values():
            stats["mean"] = (stats["sum"] / stats["count"]) if stats["count"] else 0.0

    if not responses:
        status_code, status = 503, "error"
    elif ok:
        status_code, status = 200, "success"
    else:
        status_code, status = 207, "partial"

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "timings": merged,
            "instances": responses,
            "message": None if responses else "No BunkerWeb instance reported timings",
        },
    )


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


# The threatmap groups three columns over a caller-supplied window, and only `date` is indexed
# for it (`country` is not) — so the window is the only thing bounding the scan. The page asks for
# a day; 31 lets an operator widen it without handing an authenticated caller a whole-table scan.
MAX_THREATMAP_WINDOW_SECONDS = 31 * 86400


@router.get("/threatmap", dependencies=[Depends(guard)])
def query_metrics_threatmap(start: int, end: int, limit: int = 50, facet_limit: int = 25, search_panes: str = "") -> JSONResponse:
    """Everything the threatmap page paints for ``[start, end)`` in a single call:
    ``{status, count, distinct, by_country, by_server, by_reason, recent}``.

    The window is caller-supplied epochs rather than a ``window=today`` shortcut on purpose: only
    the browser knows the operator's timezone, so "today" is resolved client-side and the server
    never has to guess between a rolling 24 h and a local midnight.
    """
    if end <= start:
        return JSONResponse(status_code=400, content={"status": "error", "message": "end must be greater than start"})
    if end - start > MAX_THREATMAP_WINDOW_SECONDS:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": f"requested window too large: {end - start}s exceeds {MAX_THREATMAP_WINDOW_SECONDS}s"},
        )

    db = get_db()
    filters = _parse_search_panes(search_panes)
    try:
        # Both limits are clamped here rather than trusted: `limit` reaches a LIMIT on a row SELECT,
        # and `facet_limit` bounds a payload that is otherwise one row per distinct service.
        result = db.get_metrics_threatmap(
            start=start,
            end=end,
            recent_limit=min(max(1, limit), 200),
            facet_limit=min(max(1, facet_limit), 100),
            filters=filters,
        )
    except ValueError as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
    return JSONResponse(status_code=200, content={"status": "success", **result})


@router.get("/requests/top-rules", dependencies=[Depends(guard)])
def query_metrics_top_rules(start: int, end: int, limit: int = 10) -> JSONResponse:
    db = get_db()
    try:
        result = db.get_metrics_top_rules(start=start, end=end, limit=limit)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
    return JSONResponse(status_code=200, content={"status": "success", "rules": result})
