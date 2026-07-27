from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..auth.guard import guard
from ..schemas import UpstreamAttachmentRequest, UpstreamCreateRequest, UpstreamUpdateRequest
from ..utils import get_db

router = APIRouter(prefix="/upstreams", tags=["upstreams"])


def _error(message: str, default: int = 400) -> JSONResponse:
    if "not found" in message.lower():
        default = 404
    elif "read-only" in message.lower():
        default = 409
    elif "already has" in message.lower() or "already exists" in message.lower() or "attached to a service" in message.lower():
        default = 409
    return JSONResponse(status_code=default, content={"status": "error", "message": message})


@router.get("", dependencies=[Depends(guard)])
def list_upstreams(
    search: str = "",
    service_id: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> JSONResponse:
    result = get_db().get_upstreams(search=search, service_id=service_id, offset=offset, limit=limit)
    return JSONResponse(
        status_code=200, content={"status": "success", "upstreams": result["items"], **{key: result[key] for key in ("total", "offset", "limit")}}
    )


@router.post("", dependencies=[Depends(guard)])
def create_upstream(payload: UpstreamCreateRequest) -> JSONResponse:
    db = get_db()
    values = payload.model_dump()
    services = values.pop("services")
    resource_id, error = db.create_upstream(**values)
    if error:
        return _error(error)

    for attachment in services:
        if attach_error := db.attach_upstream(resource_id, attachment["service_id"], match_path=attachment["match_path"]):
            # All-or-nothing: a pool created but attached to only some of the requested
            # services is a half-applied mutation the caller cannot see, so undo it and report
            # why. Deletion is safe — the successful attachments are removed with it.
            for attached in services:
                db.detach_upstream(resource_id, attached["service_id"])
            db.delete_upstream(resource_id)
            return _error(attach_error)

    return JSONResponse(status_code=201, content={"status": "success", "upstream": db.get_upstream_details(resource_id)})


@router.get("/{upstream_id}", dependencies=[Depends(guard)])
def get_upstream(upstream_id: str) -> JSONResponse:
    upstream = get_db().get_upstream_details(upstream_id)
    if upstream is None:
        return _error("Upstream not found", 404)
    return JSONResponse(status_code=200, content={"status": "success", "upstream": upstream})


@router.patch("/{upstream_id}", dependencies=[Depends(guard)])
def update_upstream(upstream_id: str, payload: UpstreamUpdateRequest) -> JSONResponse:
    db = get_db()
    values = payload.model_dump(exclude_unset=True)
    # An explicit ``"keepalive": null`` clears the directive, while omitting the key keeps the
    # stored value — a distinction ``exclude_unset`` preserves but a plain None cannot carry.
    if "keepalive" in values and values["keepalive"] is None:
        values.pop("keepalive")
        values["clear_keepalive"] = True
    if error := db.update_upstream(upstream_id, **values):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success", "upstream": db.get_upstream_details(upstream_id)})


@router.delete("/{upstream_id}", dependencies=[Depends(guard)])
def delete_upstream(upstream_id: str) -> JSONResponse:
    if error := get_db().delete_upstream(upstream_id):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success"})


@router.post("/{upstream_id}/attachments", dependencies=[Depends(guard)])
def attach_upstream(upstream_id: str, payload: UpstreamAttachmentRequest) -> JSONResponse:
    db = get_db()
    if error := db.attach_upstream(upstream_id, payload.service_id, match_path=payload.match_path):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success", "upstream": db.get_upstream_details(upstream_id)})


@router.delete("/{upstream_id}/attachments/{service_id}", dependencies=[Depends(guard)])
def detach_upstream(upstream_id: str, service_id: str, match_path: str = "") -> JSONResponse:
    """Detach a pool from a service. Without ``match_path`` every path is detached."""
    db = get_db()
    if error := db.detach_upstream(upstream_id, service_id, match_path=match_path):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success", "upstream": db.get_upstream_details(upstream_id)})
