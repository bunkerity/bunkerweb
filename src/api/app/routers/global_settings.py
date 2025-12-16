from typing import Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..auth.guard import guard
from ..utils import get_db
from ..schemas import GlobalSettingsUpdate


config_router = APIRouter(prefix="/global_config", tags=["global_settings"])
router = APIRouter(prefix="/global_settings", tags=["global_settings"])


@config_router.get("", dependencies=[Depends(guard)])
@router.get("", dependencies=[Depends(guard)])
def read_global_settings(full: bool = False, methods: bool = False) -> JSONResponse:
    """Read the current global settings.

    Args:
        full: Include all settings, even those with default values
        methods: Include method metadata for each setting
    """
    db = get_db()
    if full:
        conf = db.get_config(global_only=True, methods=methods)
    else:
        conf = db.get_non_default_settings(global_only=True, methods=methods)
    return JSONResponse(status_code=200, content={"status": "success", "settings": conf})


def _current_api_global_overrides() -> Dict[str, str]:
    """Return only current global settings that are set via method 'api'.

    Values are returned as a flat dict: {setting_id: value}.
    """
    overrides: Dict[str, str] = {}
    conf = get_db().get_non_default_settings(global_only=True, methods=True, with_drafts=False)
    for key, meta in conf.items():
        try:
            if isinstance(meta, dict) and meta.get("method") == "api":
                overrides[key] = str(meta.get("value", ""))
        except Exception:
            # Be robust to unexpected values
            continue
    return overrides


@config_router.patch("", dependencies=[Depends(guard)])
@router.patch("", dependencies=[Depends(guard)])
def update_global_settings(payload: GlobalSettingsUpdate) -> JSONResponse:
    """Update global settings.

    Args:
        payload: JSON object with setting key-value pairs to update
    """
    # Normalize values to strings (DB expects strings for settings)
    to_set: Dict[str, str] = {}
    for k, v in payload.root.items():
        to_set[str(k)] = "" if v is None else str(v)

    base = _current_api_global_overrides()
    base.update(to_set)
    ret = get_db().save_config(base, "api", changed=True)
    if isinstance(ret, str):
        code = 400 if ret and ("read-only" in ret or "already exists" in ret or "doesn't exist" in ret) else (200 if ret == "" else 500)
        status = "success" if code == 200 else "error"
        return JSONResponse(status_code=code, content={"status": status, "message": ret} if status == "error" else {"status": status})
    # Success: return list of plugins impacted (may be empty set)
    return JSONResponse(status_code=200, content={"status": "success"})
