from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..auth.guard import guard
from ..deps import get_instances_api_caller
from ..schemas import WebCachePurgeRequest

# Web cache = the NGINX proxy_cache (reverseproxy plugin), distinct from the /cache
# router which manages the job file cache. Purge/status/metrics are fanned out to
# every BunkerWeb instance (each keeps its own /var/tmp/bunkerweb/proxy_cache zone).
router = APIRouter(prefix="/web-cache", tags=["web_cache"])


@router.get("/status", dependencies=[Depends(guard)])
def web_cache_status(api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Report the proxy_cache status (enabled, on-disk size, entry count) per instance."""
    ok, responses = api_caller.send_to_apis("GET", "/proxy-cache/status", response=True)
    return JSONResponse(status_code=200 if ok else 502, content=responses or {"status": "error", "msg": "internal error"})


@router.get("/metrics", dependencies=[Depends(guard)])
def web_cache_metrics(api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Report proxy_cache hit/miss counters (from the metrics plugin) per instance."""
    ok, responses = api_caller.send_to_apis("GET", "/metrics/reverseproxy", response=True)
    return JSONResponse(status_code=200 if ok else 502, content=responses or {"status": "error", "msg": "internal error"})


@router.post("/purge", dependencies=[Depends(guard)])
def web_cache_purge(req: WebCachePurgeRequest, api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Purge the proxy response cache across all BunkerWeb instances.

    Args:
        req: scope="all" clears the whole cache; scope="url" purges the exact cache
            key of each provided URL. No NGINX reload is triggered.
    """
    payload = req.model_dump(exclude_none=True)
    ok, responses = api_caller.send_to_apis("POST", "/proxy-cache/purge", data=payload, response=True)
    return JSONResponse(status_code=200 if ok else 502, content=responses or {"status": "success" if ok else "error"})
