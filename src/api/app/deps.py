from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from fastapi import HTTPException

from .config import api_config
from .utils import get_db


def get_internal_api() -> API:
    """Dependency that returns the internal NGINX API client."""
    return API(api_config.internal_endpoint, api_config.internal_api_host_header)


def get_instances_api_caller() -> ApiCaller:
    """Build an ApiCaller targeting all known instances from the database."""
    db = get_db(log=False)
    apis = []
    try:
        for inst in db.get_instances():
            try:
                endpoint = f"http://{inst['hostname']}:{inst['port']}"
                host = inst.get("server_name") or inst.get("name") or "bwapi"
                apis.append(API(endpoint, host))
            except Exception:
                continue
    except Exception:
        # Fallback to internal API only if DB access fails
        apis.append(API(api_config.internal_endpoint, api_config.internal_api_host_header))
    return ApiCaller(apis)


def get_api_for_hostname(hostname: str) -> API:
    """Dependency returning a single API client targeting the given hostname."""
    inst = get_db(log=False).get_instance(hostname)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instance {hostname} not found")
    endpoint = f"http://{inst['hostname']}:{inst['port']}"
    host = inst.get("server_name") or inst.get("name") or "bwapi"
    return API(endpoint, host)
