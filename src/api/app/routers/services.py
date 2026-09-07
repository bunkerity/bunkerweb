from contextlib import suppress
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from default_server import (  # type: ignore
    DEFAULT_SERVER_ID,
    DEFAULT_SERVER_RESERVED_MESSAGE,
    DEFAULT_SERVER_SERVER_TYPE_MESSAGE,
    DEFAULT_SERVER_STREAM_PORTS_SETTING,
    DEFAULT_SERVER_STREAM_SSL_PORTS_SETTING,
    default_server_stream_refusal,
    is_default_server,
    is_reserved_default_server,
)
from ports import collect_ports  # type: ignore

from ..auth.guard import guard
from ..http01 import http01_refusals_for
from ..utils import get_db, reportable_config, LOGGER  # DEV-2b4: reportable_config
from ..schemas import ServiceCreateRequest, ServiceUpdateRequest

router = APIRouter(prefix="/services", tags=["services"])

# One sentence, said the same way on every refusal, because it is the only place an operator finds
# out WHY the id is refused (PO ruling 7).
RESERVED_SERVICE_MESSAGE = f"{DEFAULT_SERVER_RESERVED_MESSAGE} Edit its certificate, TLS, headers and error pages with " f"PATCH /services/{DEFAULT_SERVER_ID}."


def _reserved_refusal() -> JSONResponse:
    """403, not 400: the request is well-formed, the operation is forbidden on this id."""
    return JSONResponse(status_code=403, content={"status": "error", "message": RESERVED_SERVICE_MESSAGE})


def _declared_stream_ports(variables: Optional[Dict[str, Any]]) -> List[str]:
    """The stream-port values a request carries, base key and numbered suffixes, for BOTH lists.

    The SSL list is in here too because a refusal on it -- an SSL port the port list does not
    contain -- is just as much "something this request asked for" as a colliding port is.
    """
    return collect_ports(variables or {}, DEFAULT_SERVER_STREAM_PORTS_SETTING) + collect_ports(variables or {}, DEFAULT_SERVER_STREAM_SSL_PORTS_SETTING)


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
    # Single-site: the reserved row is not part of the product there (PO ruling 2026-09-06). The
    # seeding stands down, but a database that was multisite once still holds the row, and every
    # client -- the UI list first -- would otherwise pin a page whose settings render nowhere. An
    # operator's own service that merely took the name is NOT hidden: it is a real service.
    if not _is_multisite():
        services = [it for it in services if not is_reserved_default_server(it)]
    for it in services:
        it["creation_date"] = _iso(it.get("creation_date"))
        it["last_update"] = _iso(it.get("last_update"))
        # The reserved default server is returned like any other service -- it is configurable, and
        # a client that hides it would hide the only place its certificate can be set -- but flagged
        # so a UI knows to pin it and to offer no delete. Id AND method: a row that only took the
        # name carries none of the refusals, so it must not be flagged as if it did.
        it["reserved"] = is_reserved_default_server(it)
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

    # DEV-2b4: `get_config(methods=True)` then reduce, NOT `get_non_default_settings`: the latter reports
    # stored rows only, so a service whose template supplies a value was answered with the global
    # value the generator was about to discard. See `reportable_config`.
    # DEV-2b5: `service=` so the reduction can tell an inherited port list from a declared one.
    conf = reportable_config(db.get_config(methods=True, with_drafts=with_drafts, service=service), methods=methods, service=service)
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
    judged; a pre-existing violation on a sibling must not block an unrelated save, which is why
    the shared helper takes the service set from its caller.
    """
    return http01_refusals_for(get_db(), config, [service]).get(service)


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


def _is_multisite() -> bool:
    """Whether this deployment runs in multisite mode.

    The reserved default server is a multisite-only feature (PO ruling 2026-09-06): single-site has
    no per-service settings materialisation and no per-site variables table, so the row would be a
    page whose every setting resolves to the globals. Read live rather than cached -- an operator
    can flip MULTISITE from the global settings page while this process runs.

    `Database.is_multisite` rather than `get_config`: this runs on `GET /services`, the hottest
    endpoint the web UI has, and `get_config` rebuilds `SERVER_NAME` from `bw_services` on the way
    to answering a one-key question.

    Fails OPEN (multisite) on a database hiccup: the only thing this gate does is HIDE the reserved
    row, and hiding it takes the operator's Default server page away. Showing it for a moment on a
    single-site deployment is the cheaper of the two mistakes.
    """
    try:
        return get_db().is_multisite()
    except Exception as exc:
        LOGGER.warning(f"Could not read MULTISITE, defaulting to multisite: {exc}")
        return True


def _is_reserved(service: str) -> bool:
    """Whether ``service`` is the reserved default server AND is the row this API refuses to touch.

    The id alone is not the answer: a row an operator created under that name before 1.7 reserved it
    is not the reserved service, is not adopted by the seeding, and must stay renamable and
    deletable -- it is the only way out of a site `http.conf` already dropped from its roster.
    """
    return is_reserved_default_server({"id": service, "method": _service_method(service)})


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

    if is_default_server(name):
        return _reserved_refusal()

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
        if new_name != service and (is_default_server(new_name) or _is_reserved(service)):
            # Both directions: the reserved service cannot be renamed away, and no other service may
            # take the reserved id. Renaming it to itself is not a rename, and stays allowed so a
            # PATCH that echoes back the current server_name is not a 403.
            #
            # Asymmetric on purpose. Taking the id is refused whatever the target row is. Renaming
            # AWAY from it is refused only for the reserved row itself: a service an operator
            # created under that name before 1.7 reserved it gets no server block any more
            # (`http.conf` drops the id by name, whatever the method) and the seeding refuses to
            # adopt it, so this rename is its only recovery.
            return _reserved_refusal()
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
        if _is_reserved(target) and bool(req.is_draft):
            # Same reason as POST /{service}/convert: a drafted default server is a deleted one.
            return _reserved_refusal()
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

    # Only when the reserved service itself is being edited. A PATCH on an ordinary service that
    # happens to take a port the default server declared is NOT refused: the gate's rule is to fail
    # safe towards the real service, so that collision is resolved at generation time by dropping
    # the reserved block instead.
    if is_default_server(target):
        if "SERVER_TYPE" in (req.variables or {}):
            return JSONResponse(status_code=400, content={"status": "error", "message": DEFAULT_SERVER_SERVER_TYPE_MESSAGE})
        # Only the ports THIS request declares: a service can take a port the reserved list already
        # held, and refusing every later write on the reserved service for it would lock the whole
        # resource over stored state the renderer already neutralises by dropping the port.
        refusal = default_server_stream_refusal(conf, _declared_stream_ports(req.variables))
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
    # The reserved row only -- an operator's own service that took the name stays deletable, which
    # with the rename above is the second half of its recovery path.
    if is_reserved_default_server(svc or {"id": service, "method": _service_method(service)}):
        return _reserved_refusal()

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
    if _is_reserved(service):
        # Drafting it is deletion by another name: a draft row drops out of SERVER_NAME, the default
        # server falls silently back to the global-only rendering and every setting on its page stops
        # applying with no error anywhere. The reserved row only, for the same reason as the rename
        # and the delete above.
        return _reserved_refusal()

    conf = _full_config_snapshot()
    services_list = (conf.get("SERVER_NAME", "") or "").split()
    to_convert = [s for s in (service,) if s in services_list]
    if not to_convert:
        return JSONResponse(status_code=400, content={"status": "error", "message": "No valid services to convert"})
    to_val = "no" if convert_to == "online" else "yes"
    for s in to_convert:
        conf[f"{s}_IS_DRAFT"] = to_val
    return _persist_config(conf)
