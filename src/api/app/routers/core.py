from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..utils import get_api_db


router = APIRouter(tags=["core"])  # Utils-only (ping, health)
from .auth import router as auth_router
from .instances import router as instances_router
from .global_config import router as global_config_router
from .bans import router as bans_router
from .services import router as services_router
from .configs import router as configs_router
from .plugins import router as plugins_router
from .cache import router as cache_router
from .jobs import router as jobs_router


@router.get("/ping")
def ping() -> dict:
    """Simple ping/pong health check endpoint."""
    return {"status": "ok", "message": "pong"}


@router.get("/health")
def health() -> JSONResponse:
    """Lightweight liveness probe for the API service itself.

    Returns 200 when the FastAPI service is up and routing requests.
    Does not call internal BunkerWeb instances.
    """
    return JSONResponse(status_code=200, content={"status": "ok"})


# Mount category routers under core
# Conditionally expose auth endpoints only if API users exist
_adb = get_api_db(log=False)
_has_api_user = _adb.has_api_user()

if _has_api_user:
    router.include_router(auth_router)

router.include_router(instances_router)
router.include_router(bans_router)
router.include_router(global_config_router)
router.include_router(services_router)
router.include_router(configs_router)
router.include_router(plugins_router)
router.include_router(cache_router)
router.include_router(jobs_router)
