from contextlib import suppress
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ports import HTTP_PORT_SETTING, http01_refusals, services_from_config  # type: ignore

from ..auth.guard import guard
from ..utils import get_db
from ..schemas import ServiceCreateRequest, ServiceUpdateRequest

router = APIRouter(prefix="/services", tags=["services"])


def _iso(dt) -> Optional[str]:
    with suppress(Exception):
        return dt.astimezone().isoformat()
    return None


@router.get("", dependencies=[Depends(guard)])
def list_services(with_drafts: bool = True) -> JSONResponse:
    """List all services with their configurations.

    Args:
        with_drafts: Include draft services in the results (default: True)
    """
    services = get_db().get_services(with_drafts=with_drafts)
    for it in services:
        it["creation_date"] = _iso(it.get("creation_date"))
        it["last_update"] = _iso(it.get("last_update"))
    return JSONResponse(status_code=200, content={"status": "success", "services": services})


@router.get("/{service}", dependencies=[Depends(guard)])
def get_service(service: str, full: bool = False, methods: bool = True, with_drafts: bool = True) -> JSONResponse:
    """Get configuration for a specific service.

    Args:
        service: Service identifier
        full: Return complete configuration including defaults
        methods: Include method metadata for each setting
        with_drafts: Include draft services when computing templates
    """
    db = get_db()
    # Check existence
    exists = any(s.get("id") == service for s in db.get_services(with_drafts=True))
    if not exists:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Service {service} not found"})

    if full:
        conf = db.get_config(methods=methods, with_drafts=with_drafts, service=service)
        return JSONResponse(status_code=200, content={"status": "success", "service": service, "config": conf})

    conf = db.get_non_default_settings(methods=methods, with_drafts=with_drafts, service=service)
    return JSONResponse(status_code=200, content={"status": "success", "service": service, "config": conf})


def _full_config_snapshot() -> Dict[str, Any]:
    """Return a full config snapshot (global + services) as flat dict of values only."""
    return get_db().get_non_default_settings(methods=False, with_drafts=True)


def _persist_config(config: Dict[str, Any]) -> JSONResponse:
    ret = get_db().save_config(config, "api", changed=True)

    if isinstance(ret, str):
        code = 400 if ("read-only" in ret or "already exists" in ret or "doesn't exist" in ret) else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success", "changed_plugins": sorted(list(ret))})


def _invalid_variables(variables: Optional[Dict[str, Any]], *, skip: tuple = ()) -> List[str]:
    """Return "KEY: reason" for every variable the setting's own schema forbids.

    save_config runs no regex check of its own: an unknown key is dropped inside it, and a
    known key with an illegal value is WRITTEN to Services_settings and echoed back by GET,
    then dropped at generation time by gen/Configurator.py with a log line. Either way this
    endpoint used to answer 200 having lost the value -- the defect PATCH /global_settings
    was fixed for.

    Keys arrive unprefixed and are service-scoped, so multisite=True: the same gate
    Configurator applies to `<service>_<KEY>`, and how autoconf validates the same kind of
    key (autoconf/Config.py). extra_services is deliberately NOT passed -- it is only
    consulted when an already-prefixed key misses the plain lookup (config_read.py), and
    that branch does not set multisite, so routing through it would silently weaken the
    very context check this exists to perform.

    Only the keys in THIS payload, never the merged snapshot: a pre-existing invalid row
    must not block an unrelated future save (same rule as global_settings.py).
    """
    db = get_db()
    invalid = []
    for key, value in (variables or {}).items():
        if key in skip:
            continue
        # value=None means "check the name only" and would skip value validation entirely.
        ok, err = db.is_valid_setting(key, value="" if value is None else value, multisite=True)
        if not ok:
            invalid.append(f"{key}: {err}")
            continue

        # USE_TEMPLATE holds an ORDERED LIST of template ids, and its regex is `^.*$` because
        # the ids are user-created -- so a typo passes every lexical gate above and is only
        # noticed at generation time, which drops ONE LAYER OF N with a log line nobody reads.
        # Referential check, same principle as the SERVER_NAME gate below: refuse at the save.
        if key == "USE_TEMPLATE" and value is not None:
            unknown = db.unknown_template_layers(str(value))
            if unknown:
                invalid.append(f"{key}: " + ", ".join(f'unknown template "{layer}" at position {position}' for position, layer in unknown))
    return invalid


def _http01_refusal(config: Dict[str, Any], service: str) -> Optional[str]:
    """Why ``service`` cannot keep ``LETS_ENCRYPT_CHALLENGE=http``, or None.

    Checked on the config the handler is ABOUT TO PERSIST, not on the payload: the challenge and
    the port can arrive in different requests, or one of the two can already be stored, and only
    the merged result says whether the combination is reachable.

    A hard refusal rather than a warning, on the PO's ruling: an ACME server contacts public port
    80 and follows no redirect, so the alternative is a job failing sixty seconds after a save that
    answered 200 — a support ticket instead of an error message. Only the service being written is
    judged; a pre-existing violation on a sibling must not block an unrelated save.
    """
    services = services_from_config(config, [service], multisite=True)
    globals_only = {key: value for key, value in config.items() if not key.startswith(f"{service}_")}
    # A snapshot carries the NON-default settings, so a global port left at its declared default
    # has no row at all -- and a service that merely restates that default would then look moved
    # and be told to "remove this service's HTTP_PORT override", i.e. to remove the value it just
    # set. Same fallback the services listing already applies for `link_port`
    # (`db_methods/services.py:73-76`).
    #
    # Gated on the BASE key, not on the whole list being empty: a fleet that added a second port
    # without moving the first one has a row for `HTTP_PORT_1` and none for `HTTP_PORT`, so a
    # list-wide gate never fires on exactly the shape that needs it. And keyed on the key being
    # ABSENT, never on its value being empty: `HTTP_PORT=""` is a deliberate global with a row.
    if HTTP_PORT_SETTING not in globals_only:
        declared = get_db().get_config(global_only=True, methods=False, filtered_settings=(HTTP_PORT_SETTING,))
        if HTTP_PORT_SETTING in declared:
            # Appending the recovered base is safe because `collect_ports` orders by SUFFIX, not by
            # dict order. It was not: `list_moved` compares ordered sequences, so the recovered
            # base landed last and answered ['8081', '8080'] against the service's ['8080', '8081'],
            # refusing the very save this fallback exists to accept. Re-inserting it in position
            # here would have fixed only half of it -- `services_from_config` appends the service's
            # own base after the global repetition on the other side of the same comparison.
            globals_only[HTTP_PORT_SETTING] = declared[HTTP_PORT_SETTING]
    return http01_refusals(services, globals_only).get(service)


def _invalid_server_name(name: str) -> Optional[str]:
    """Return the reason `name` is unusable as a server name, or None.

    An illegal name is not merely dropped: it lands in the global SERVER_NAME roster, and
    gen/Configurator.py answers an invalid SERVER_NAME with exit(1). The generator is a
    subprocess so the scheduler survives, but NO config is regenerated for ANY service until
    the bad name is found and removed. Validate the incoming name only, never the whole
    roster -- a legacy-invalid sibling must not block an unrelated create.
    """
    ok, err = get_db().is_valid_setting("SERVER_NAME", value=name, multisite=True)
    return None if ok else err


def _service_method(service: str) -> Optional[str]:
    for item in get_db().get_services(with_drafts=True):
        if item.get("id") == service:
            return item.get("method")
    return None


@router.post("", dependencies=[Depends(guard)])
def create_service(req: ServiceCreateRequest) -> JSONResponse:
    """Create a new service with the specified configuration.

    Args:
        req: Service creation request with server_name, variables, and draft status
    """
    conf = _full_config_snapshot()
    name = req.server_name.split(" ")[0].strip()
    if not name:
        return JSONResponse(status_code=422, content={"status": "error", "message": "server_name is required"})

    err = _invalid_server_name(name)
    if err:
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Invalid server_name: {err}"})

    # Reject duplicates
    existing = set((conf.get("SERVER_NAME", "") or "").split())
    if name in existing:
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Service {name} already exists"})

    # SERVER_NAME is not skipped here: unlike the update handler, this one honours
    # variables["SERVER_NAME"] below, so it is a real write and must be gated.
    invalid = _invalid_variables(req.variables)
    if invalid:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid settings: " + "; ".join(invalid)})

    # Draft flag
    conf[f"{name}_IS_DRAFT"] = "yes" if req.is_draft else "no"

    # Set provided variables (unprefixed)
    for k, v in (req.variables or {}).items():
        if isinstance(v, (dict, list)):
            return JSONResponse(status_code=422, content={"status": "error", "message": f"Invalid value for {k}: must be scalar"})
        conf[f"{name}_{k}"] = "" if v is None else v

    if "SERVER_NAME" not in (req.variables or {}):
        conf[f"{name}_SERVER_NAME"] = name

    conf["SERVER_NAME"] = " ".join(sorted(existing | {name}))

    refusal = _http01_refusal(conf, name)
    if refusal:
        return JSONResponse(status_code=400, content={"status": "error", "message": refusal})

    return _persist_config(conf)


@router.patch("/{service}", dependencies=[Depends(guard)])
def update_service(service: str, req: ServiceUpdateRequest) -> JSONResponse:
    """Update an existing service's configuration.

    Args:
        service: Current service identifier
        req: Update request with new server_name, variables, and draft status
    """
    conf = _full_config_snapshot()
    services_list = (conf.get("SERVER_NAME", "") or "").split()
    if service not in services_list:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Service {service} not found"})

    # SERVER_NAME is skipped to match the handler: it ignores direct edits to that key below,
    # so rejecting on a value that is never written would be a 400 for nothing.
    invalid = _invalid_variables(req.variables, skip=("SERVER_NAME",))
    if invalid:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid settings: " + "; ".join(invalid)})

    target = service
    # Handle rename
    if req.server_name:
        new_name = req.server_name.split(" ")[0].strip()
        if not new_name:
            return JSONResponse(status_code=422, content={"status": "error", "message": "server_name cannot be empty"})
        err = _invalid_server_name(new_name)
        if err:
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Invalid server_name: {err}"})
        if new_name != service and new_name in services_list:
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Service {new_name} already exists"})

        # Replace in SERVER_NAME and prefix keys
        services_list = [new_name if s == service else s for s in services_list]
        conf["SERVER_NAME"] = " ".join(services_list)
        # Rename prefixed keys
        renames: List[tuple[str, str]] = []
        for key in list(conf.keys()):
            if key.startswith(f"{service}_"):
                suffix = key[len(service) + 1 :]  # noqa: E203
                renames.append((key, f"{new_name}_{suffix}"))
        for old, new in renames:
            conf[new] = conf.pop(old)
        target = new_name

    # Draft flag update
    if req.is_draft is not None:
        conf[f"{target}_IS_DRAFT"] = "yes" if bool(req.is_draft) else "no"

    # Update provided variables (unprefixed)
    for k, v in (req.variables or {}).items():
        if k == "SERVER_NAME":
            # Ignore direct edits to SERVER_NAME via variables
            continue
        if isinstance(v, (dict, list)):
            return JSONResponse(status_code=422, content={"status": "error", "message": f"Invalid value for {k}: must be scalar"})
        conf[f"{target}_{k}"] = "" if v is None else v

    refusal = _http01_refusal(conf, target)
    if refusal:
        return JSONResponse(status_code=400, content={"status": "error", "message": refusal})

    return _persist_config(conf)


@router.delete("/{service}", dependencies=[Depends(guard)])
def delete_service(service: str) -> JSONResponse:
    """Delete a service and all its configuration.

    Args:
        service: Service identifier to delete
    """
    conf = _full_config_snapshot()
    services_list = (conf.get("SERVER_NAME", "") or "").split()
    if service not in services_list:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Service {service} not found"})

    svc = next((s for s in get_db().get_services(with_drafts=True) if s.get("id") == service), None)
    if (svc.get("method") if svc else _service_method(service)) == "wizard":
        return JSONResponse(status_code=403, content={"status": "error", "message": f"Service {service} is managed by wizard and cannot be deleted"})

    # Drafted autoconf services can't be removed through save_config(method="api") — the bulk-method
    # guard protects autoconf-owned rows. Hard-delete them directly for this authorized deletion.
    if svc is not None and svc.get("method") == "autoconf" and svc.get("is_draft"):
        err = get_db().delete_services([service])
        if err:
            code = 400 if "read-only" in err else 500
            return JSONResponse(status_code=code, content={"status": "error", "message": err})
        return JSONResponse(status_code=200, content={"status": "success", "changed_plugins": []})

    # Remove from server list
    conf["SERVER_NAME"] = " ".join([s for s in services_list if s != service])
    # Drop prefixed keys
    for key in list(conf.keys()):
        if key.startswith(f"{service}_"):
            conf.pop(key)

    return _persist_config(conf)


@router.post("/{service}/convert", dependencies=[Depends(guard)])
def convert_service(service: str, convert_to: str = Query(..., pattern="^(online|draft)$")) -> JSONResponse:
    """Convert a service between online and draft status.

    Args:
        service: Service identifier
        convert_to: Target status ("online" or "draft")
    """
    conf = _full_config_snapshot()
    services_list = (conf.get("SERVER_NAME", "") or "").split()
    to_convert = [s for s in (service,) if s in services_list]
    if not to_convert:
        return JSONResponse(status_code=400, content={"status": "error", "message": "No valid services to convert"})
    to_val = "no" if convert_to == "online" else "yes"
    for s in to_convert:
        conf[f"{s}_IS_DRAFT"] = to_val
    return _persist_config(conf)
