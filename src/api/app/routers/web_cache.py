from urllib.parse import urlsplit

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..auth.guard import guard
from ..deps import get_instances_api_caller
from ..schemas import WebCachePurgeRequest
from ..utils import get_db

# Web cache = the NGINX proxy_cache (reverseproxy plugin), distinct from the /cache
# router which manages the job file cache. Purge/status/metrics are fanned out to
# every BunkerWeb instance (each keeps its own /var/tmp/bunkerweb/proxy_cache zone).
router = APIRouter(prefix="/web-cache", tags=["web_cache"])


def _fanout_status(ok: bool, responses) -> int:
    """Use multi-status when some instances answered and service-unavailable when none did."""
    if not responses:
        return 503
    if ok:
        return 200
    return 207


def _fanout_label(ok: bool, responses) -> str:
    if not responses:
        return "error"
    if ok:
        return "success"
    return "partial"


def _service_cache_statuses() -> list[dict]:
    """Return effective cache enablement, including inherited template values."""
    db = get_db()
    config = db.get_config(
        methods=False,
        with_drafts=True,
        filtered_settings=("USE_PROXY_CACHE",),
    )
    return [
        {
            "id": service["id"],
            "enabled": config.get(f"{service['id']}_USE_PROXY_CACHE", config.get("USE_PROXY_CACHE", "no")) == "yes",
            "is_draft": bool(service.get("is_draft")),
        }
        for service in db.get_services(with_drafts=True)
    ]


def _target_hostnames(api_caller, responses) -> list[str]:
    """Return configured instance hostnames, falling back to response keys in tests."""
    hostnames = []
    try:
        apis = list(api_caller.apis)
    except (AttributeError, TypeError):
        apis = []
    for api in apis:
        endpoint = getattr(api, "endpoint", "")
        hostname = urlsplit(endpoint).hostname or endpoint
        if hostname and hostname not in hostnames:
            hostnames.append(hostname)
    for hostname in responses or {}:
        if hostname not in hostnames:
            hostnames.append(hostname)
    return hostnames


@router.get("/status", dependencies=[Depends(guard)])
def web_cache_status(api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Report the proxy_cache status (enabled, on-disk size, entry count) per instance."""
    ok, responses = api_caller.send_to_apis("GET", "/proxy-cache/status", response=True)
    return JSONResponse(
        status_code=_fanout_status(ok, responses),
        content={
            "status": _fanout_label(ok, responses),
            "instances": responses or {},
            "services": _service_cache_statuses(),
            "message": None if responses else "No BunkerWeb instance reported cache status",
        },
    )


@router.get("/metrics", dependencies=[Depends(guard)])
def web_cache_metrics(api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Report proxy_cache hit/miss counters (from the metrics plugin) per instance."""
    ok, responses = api_caller.send_to_apis("GET", "/metrics/reverseproxy", response=True)
    return JSONResponse(
        status_code=_fanout_status(ok, responses),
        content={
            "status": _fanout_label(ok, responses),
            "instances": responses or {},
            "message": None if responses else "No BunkerWeb instance reported cache metrics",
        },
    )


@router.post("/purge", dependencies=[Depends(guard)])
def web_cache_purge(req: WebCachePurgeRequest, api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Purge the proxy response cache across all BunkerWeb instances.

    Args:
        req: scope="all" clears the whole cache; scope="url" purges the exact cache
            key of each provided URL. No NGINX reload is triggered.
    """
    payload = req.model_dump(exclude_none=True)
    ok, responses = api_caller.send_to_apis("POST", "/proxy-cache/purge", data=payload, response=True)
    responses = responses or {}
    instances = {}
    succeeded = failed = skipped = 0

    for hostname in _target_hostnames(api_caller, responses):
        response = responses.get(hostname)
        if response is None:
            instances[hostname] = {
                "status": "skipped",
                "reason": "unreachable",
                "queued": False,
            }
            skipped += 1
            continue

        response_status = response.get("status") if isinstance(response, dict) else None
        if response_status == "error":
            instances[hostname] = {"status": "failed", "response": response}
            failed += 1
        else:
            instances[hostname] = {"status": "success", "response": response}
            succeeded += 1

    if succeeded and not (failed or skipped) and ok:
        status_code, status = 200, "success"
    elif succeeded:
        status_code, status = 207, "partial"
    else:
        status_code, status = 503, "error"

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "scope": payload["scope"],
            "summary": {
                "requested": len(instances),
                "succeeded": succeeded,
                "failed": failed,
                "skipped": skipped,
            },
            "instances": instances,
        },
    )
