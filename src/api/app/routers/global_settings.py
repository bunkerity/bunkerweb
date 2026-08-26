from typing import Any, Dict, List, Mapping, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ports import HTTP_PORT_SETTING  # type: ignore

from ..auth.guard import guard
from ..http01 import http01_refusals_for
from ..utils import LOGGER, get_db
from ..schemas import GlobalSettingsUpdate, ValidateSettingRequest, SaveConfigRequest

config_router = APIRouter(prefix="/global_config", tags=["global_settings"])

# The settings whose value decides whether a service can still answer an ACME http-01 challenge.
# ``HTTP_PORT`` counts in both directions: moving the FLEET's list makes a service that spelled out
# the old one look moved, exactly as moving the service's own list does.
HTTP01_SETTINGS = ("AUTO_LETS_ENCRYPT", "LETS_ENCRYPT_CHALLENGE", "LETS_ENCRYPT_PASSTHROUGH", HTTP_PORT_SETTING)
_HTTP01_SUFFIXES = tuple(f"_{name}" for name in HTTP01_SETTINGS)


def _touches_http01(keys) -> bool:
    """Whether a payload can change the answer to "can this service still be validated?".

    Matched on the SUFFIX, so a service-prefixed key counts too. That is not defensive breadth: an
    autoconf payload carries every label as ``<server_name>_AUTO_LETS_ENCRYPT`` and can contain no
    global row at all (``autoconf/Config.py:__get_full_env`` builds ``SERVER_NAME``, ``MULTISITE``
    and prefixed keys), so a global-only test would skip exactly the path this gate exists for.

    A trailing ``_<digits>`` is dropped first, because a port list is spelled ``HTTP_PORT_1``.
    Over-matching costs nothing -- this only decides whether the real check below runs at all.
    """
    for key in keys:
        head, _, tail = key.rpartition("_")
        if head and tail.isdigit():
            key = head
        if key in HTTP01_SETTINGS or key.endswith(_HTTP01_SUFFIXES):
            return True
    return False


def _http01_refusal_message(db, config: Mapping[str, Any], server_names) -> Optional[str]:
    """The 400 body for a fleet-wide write that would strand one or more services, or None.

    Every offending service is named with its own reason: unlike a single-service write, one
    global change can reach many at once, and an operator who is told about the first of five
    fixes it and gets refused again four times.
    """
    refusals = http01_refusals_for(db, config, server_names)
    if not refusals:
        return None
    return " ".join(refusals[name] for name in sorted(refusals))


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

    A configuration that would strand a service's http-01 challenge is refused with a 400 for an
    interactive caller and logged-then-saved for ``method="autoconf"`` -- see the branch below.
    """
    db = get_db()

    # Semantic gate, deliberately beyond this endpoint's payload-shape contract. The payload IS
    # the complete desired state here (`Database.save_config` deletes any in-scope key it omits),
    # so unlike PATCH below there is nothing to merge and nothing to skip: judge it as written.
    #
    # This is the autoconf settings-apply path -- `src/autoconf/Config.py:apply()` reaches it
    # through `AutoconfApiClient.save_config` -- and the UI's config editor
    # (`ui/app/models/config.py`) reaches it too. Both used to persist a service that had been
    # moved off the fleet's HTTP listener while asking for an http-01 challenge, and the failure
    # surfaced sixty seconds later inside the certificate job.
    server_names = str(req.config.get("SERVER_NAME", "") or "").split()
    if server_names and _touches_http01(req.config):
        refusal = _http01_refusal_message(db, req.config, server_names)
        if refusal:
            # Split by CALLER, and only here. `autoconf` is a declarative reconciler with no
            # operator in the loop, and its payload is the WHOLE fleet: refusing it would leave
            # every other service unconfigured too -- on a first boot, nothing at all -- because
            # one container carries a bad label. That trades one service's certificate failure for
            # a fleet-wide outage, which is strictly worse than the defect being fixed. So the same
            # message is logged and the configuration is saved UNCHANGED: the offending service's
            # http-01 order then fails exactly as it does today, no worse, but the diagnostic
            # arrives at apply time instead of sixty seconds later inside a job.
            #
            # Nothing is rewritten to make it valid. Silently moving a port or switching a
            # challenge would be a reconciler deciding what the operator meant.
            #
            # Every other method reaching here is a human editing one thing -- the UI config editor
            # (`ui`), `manual`, `wizard` -- where the 400 is the whole point: they see it and fix
            # their input. `scheduler` is allowed by the schema but never arrives: the scheduler
            # shells out to `gen/save_config.py` (main.py:196, :645, :726) and has no client method
            # for this endpoint. If that is ever wired up, it belongs on the autoconf side of this
            # branch for exactly the same reason.
            if req.method == "autoconf":
                LOGGER.error(f"Saving an autoconf configuration that strands an http-01 challenge: {refusal}")
            else:
                return JSONResponse(status_code=400, content={"status": "error", "message": refusal})

    ret = db.save_config(req.config, req.method, changed=req.changed, disable_cleanup=req.disable_cleanup)
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
            continue
        # See routers/services.py:_invalid_variables -- USE_TEMPLATE's regex cannot express
        # "these ids exist", so an unknown layer is caught referentially or not at all.
        if key == "USE_TEMPLATE":
            unknown = db.unknown_template_layers(value)
            if unknown:
                invalid.append(f"{key}: " + ", ".join(f'unknown template "{layer}" at position {position}' for position, layer in unknown))
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

    # Semantic gate, and the ONE check here that is not payload-only. Everything above judges the
    # incoming keys alone, on purpose (see both comments), because a pre-existing invalid or
    # foreign-owned row must not block an unrelated save. This one cannot be payload-only:
    # "can this service still answer an http-01 challenge?" is a property of the MERGED config --
    # the challenge is global while the port that breaks it is per-service -- and a fleet-wide
    # write reaches every service at once. It keeps the spirit of the rule by firing only when the
    # payload actually carries a setting that decides the answer: a PATCH touching none of them
    # cannot strand anything and pays no snapshot read.
    if _touches_http01(to_set):
        snapshot = db.get_non_default_settings(methods=False, with_drafts=True)
        # The roster is taken BEFORE the overlay and from the database, not from the payload: this
        # save passes skip_service_management=True, so a SERVER_NAME in the payload creates and
        # deletes nothing, and the services that can be stranded are the ones that already exist.
        server_names = str(snapshot.get("SERVER_NAME", "") or "").split()
        snapshot.update(to_set)
        refusal = _http01_refusal_message(db, snapshot, server_names) if server_names else None
        if refusal:
            return JSONResponse(status_code=400, content={"status": "error", "message": refusal})

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
