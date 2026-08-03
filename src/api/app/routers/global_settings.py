from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..auth.guard import guard
from ..utils import get_db
from ..schemas import GlobalSettingsUpdate, ValidateSettingRequest, SaveConfigRequest

config_router = APIRouter(prefix="/global_config", tags=["global_settings"])
router = APIRouter(prefix="/global_settings", tags=["global_settings"])


@config_router.get("", dependencies=[Depends(guard)])
@router.get("", dependencies=[Depends(guard)])
def read_global_settings(
    full: bool = False,
    methods: bool = False,
    with_drafts: bool = False,
    filtered_settings: Optional[List[str]] = Query(None),
    global_only: bool = True,
) -> JSONResponse:
    """Read the current global settings.

    Args:
        full: Include all settings, even those with default values
        methods: Include method metadata for each setting
        with_drafts: Include draft services when computing settings
        filtered_settings: Only return these setting IDs
        global_only: If False, include per-service settings
    """
    db = get_db()
    fs = tuple(filtered_settings) if filtered_settings else None
    if full:
        conf = db.get_config(
            global_only=global_only,
            methods=methods,
            with_drafts=with_drafts,
            filtered_settings=fs,
        )
    else:
        conf = db.get_non_default_settings(
            global_only=global_only,
            methods=methods,
            with_drafts=with_drafts,
            filtered_settings=fs,
        )
    return JSONResponse(status_code=200, content={"status": "success", "settings": conf})


def _current_api_global_overrides() -> Tuple[Dict[str, str], Dict[str, Dict[str, str]]]:
    """Return current global settings owned by method 'api', plus every row's owner and value.

    Two results out of a single query, because a PATCH needs both: the 'api' subset is the base
    it merges into, and each row's (method, value) decides whether a key it carries is actually
    writable.

    Despite its name, ``get_non_default_settings`` joins Settings with Global_values, so it
    yields one entry per EXISTING global row -- not a value != default filter. Those are the rows
    ``save_config`` UPDATEs rather than INSERTs, which is what the ownership rule applies to. It
    is not a perfect mirror of save_config's key resolution: a row is keyed with its numeric
    suffix only when the setting is `multiple` AND the suffix is > 0, so a suffix-0 row comes back
    keyed plainly. Callers must normalise before looking a payload key up.

    Returns ({setting_id: value} for api-owned rows, {setting_id: {"method", "value"}} for all).
    """
    overrides: Dict[str, str] = {}
    rows: Dict[str, Dict[str, str]] = {}
    conf = get_db().get_non_default_settings(global_only=True, methods=True, with_drafts=False)
    for key, meta in conf.items():
        try:
            if not isinstance(meta, dict):
                continue
            method = meta.get("method")
            value = str(meta.get("value", ""))
            if method:
                rows[key] = {"method": str(method), "value": value}
            if method == "api":
                overrides[key] = value
        except Exception:
            # Be robust to unexpected values
            continue
    return overrides, rows


@router.post("/validate", dependencies=[Depends(guard)])
def validate_setting(req: ValidateSettingRequest) -> JSONResponse:
    """Validate a setting name and optionally its value."""
    db = get_db()
    success, err = db.is_valid_setting(
        req.setting,
        value=req.value,
        multisite=req.multisite,
        extra_services=req.extra_services,
    )
    return JSONResponse(
        status_code=200,
        content={"status": "success", "valid": success, "error": err},
    )


@router.put("/config", dependencies=[Depends(guard)])
def save_config(req: SaveConfigRequest) -> JSONResponse:
    """Save a complete config environment dict.

    Used by Autoconf to persist its merged configuration.
    Returns the list of changed plugin IDs on success.
    """
    ret = get_db().save_config(req.config, req.method, changed=req.changed, disable_cleanup=req.disable_cleanup)
    if isinstance(ret, str):
        code = 400 if "read-only" in ret.lower() or "resource group" in ret.lower() else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": ret})
    # ret is a set of changed plugin IDs
    return JSONResponse(
        status_code=200,
        content={"status": "success", "changed_plugins": sorted(ret)},
    )


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

    db = get_db()

    # Validate only the keys in THIS payload, never the merged base dict: a pre-existing
    # invalid row written before this check existed must not block an unrelated future save.
    invalid = []
    for key, value in to_set.items():
        ok, err = db.is_valid_setting(key, value=value)
        if not ok:
            invalid.append(f"{key}: {err}")
    if invalid:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Invalid settings: " + "; ".join(invalid)},
        )

    base, rows = _current_api_global_overrides()

    # save_config only overwrites a row whose method 'api' is allowed to take over
    # (Database._methods_are_compatible). Every other owner -- scheduler (env-var origin, the
    # dominant case in Docker/compose), autoconf, manual, wizard -- is skipped with no error and
    # no changed plugin, which is how this endpoint used to answer 200 "success" having written
    # nothing. Reject the whole payload instead: all-or-nothing matches the validation block
    # above, and a silently half-applied write is exactly the defect being fixed here.
    #
    # SCOPE, deliberately narrow -- this reports a refusal, it does not reproduce save_config's
    # resolution, and it cannot without duplicating the whole thing:
    #   * plain and `_<n>`-suffixed GLOBAL keys only. A service-prefixed key (`www.x.com_FOO`)
    #     has no entry here and still passes through to be dropped silently.
    #   * SERVER_NAME is exempt. get_non_default_settings unconditionally replaces its entry with
    #     the service list under a synthetic method="scheduler" (db_methods/config_read.py), so
    #     the owner it reports is not the row's real owner and would raise a bogus 409.
    #   * the value comparison is raw, while save_config compares against
    #     `_canonicalize_stored_value` of the incoming value, so a non-canonical spelling of the
    #     value already stored ("true" for "yes", " info ") can still 409. Erring towards a
    #     spurious conflict is the safe direction; erring towards a false success is the bug.
    #   * it assumes `file_name_changed` is always False, which holds only because no caller
    #     passes `file_names` to save_config. Wiring that up means revisiting this gate: that one
    #     branch writes even when the methods are incompatible.
    conflicts = []
    for key, value in to_set.items():
        if key == "SERVER_NAME":
            continue
        # A suffix-0 row is keyed plainly, so `FOO_0` must be looked up as `FOO` -- save_config
        # resolves both to (setting=FOO, suffix=0). Without this, `FOO_0` skipped the gate and
        # got the silent 200 this endpoint is being fixed for. `FOO_10` is unaffected.
        row = rows.get(key) or (rows.get(key[:-2]) if key.endswith("_0") else None)
        # No row means save_config INSERTs it whatever the method: nothing to conflict with.
        if not row:
            continue
        # An exact re-write of the stored value changes nothing, so save_config would not have
        # written it either and nothing is being dropped -- the old 200 was truthful there. Only
        # a value that would actually change is a refused write. This matters: the canonical way
        # to drive a merge-PATCH is GET the config, edit one key, PATCH the whole dict back, and
        # in Docker nearly every non-default global is scheduler-owned.
        if row["value"] == value:
            continue
        if not db._methods_are_compatible("api", row["method"]):
            conflicts.append(f"{key} ({row['method']})")
    if conflicts:
        return JSONResponse(
            status_code=409,
            content={"status": "error", "message": "Settings managed elsewhere: " + "; ".join(conflicts)},
        )

    base.update(to_set)
    ret = db.save_config(base, "api", changed=True, skip_service_management=True)
    if isinstance(ret, str):
        code = (
            400
            if ret
            and any(
                hint in ret.lower()
                for hint in (
                    "read-only",
                    "already exists",
                    "doesn't exist",
                    "resource group",
                )
            )
            else (200 if ret == "" else 500)
        )
        status = "success" if code == 200 else "error"
        return JSONResponse(
            status_code=code,
            content={"status": status, "message": ret} if status == "error" else {"status": status},
        )
    # Success: return list of plugins impacted (may be empty set)
    return JSONResponse(status_code=200, content={"status": "success"})
