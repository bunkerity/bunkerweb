from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..auth.guard import guard
from ..schemas import RedirectAttachmentRequest, RedirectCreateRequest, RedirectUpdateRequest
from ..utils import get_db

router = APIRouter(prefix="/redirects", tags=["redirects"])


def _error(message: str, default: int = 400) -> JSONResponse:
    if "not found" in message.lower():
        default = 404
    elif "read-only" in message.lower():
        default = 409
    elif "already has" in message.lower() or "already exists" in message.lower() or "attached to a service" in message.lower():
        default = 409
    return JSONResponse(status_code=default, content={"status": "error", "message": message})


@router.get("", dependencies=[Depends(guard)])
def list_redirects(
    search: str = "",
    service_id: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> JSONResponse:
    result = get_db().get_redirects(search=search, service_id=service_id, offset=offset, limit=limit)
    return JSONResponse(
        status_code=200, content={"status": "success", "redirects": result["items"], **{key: result[key] for key in ("total", "offset", "limit")}}
    )


@router.post("", dependencies=[Depends(guard)])
def create_redirect(payload: RedirectCreateRequest) -> JSONResponse:
    db = get_db()
    values = payload.model_dump()
    service_ids = values.pop("service_ids")
    resource_id, error = db.create_redirect(**values)
    if error:
        return _error(error)

    for service_id in service_ids:
        if attach_error := db.attach_redirect(resource_id, service_id):
            # All-or-nothing: a rule created but attached to only some of the requested
            # services is a half-applied mutation the caller cannot see, so undo it and
            # report why. Deletion is safe — the successful attachments are removed with it.
            for attached in service_ids:
                db.detach_redirect(resource_id, attached)
            db.delete_redirect(resource_id)
            return _error(attach_error)

    return JSONResponse(status_code=201, content={"status": "success", "redirect": db.get_redirect_details(resource_id)})


@router.get("/{redirect_id}", dependencies=[Depends(guard)])
def get_redirect(redirect_id: str) -> JSONResponse:
    redirect = get_db().get_redirect_details(redirect_id)
    if redirect is None:
        return _error("Redirect not found", 404)
    return JSONResponse(status_code=200, content={"status": "success", "redirect": redirect})


@router.patch("/{redirect_id}", dependencies=[Depends(guard)])
def update_redirect(redirect_id: str, payload: RedirectUpdateRequest) -> JSONResponse:
    db = get_db()
    if error := db.update_redirect(redirect_id, **payload.model_dump(exclude_unset=True)):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success", "redirect": db.get_redirect_details(redirect_id)})


@router.delete("/{redirect_id}", dependencies=[Depends(guard)])
def delete_redirect(redirect_id: str) -> JSONResponse:
    if error := get_db().delete_redirect(redirect_id):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success"})


@router.post("/{redirect_id}/attachments", dependencies=[Depends(guard)])
def attach_redirect(redirect_id: str, payload: RedirectAttachmentRequest) -> JSONResponse:
    db = get_db()
    if error := db.attach_redirect(redirect_id, payload.service_id):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success", "redirect": db.get_redirect_details(redirect_id)})


@router.delete("/{redirect_id}/attachments/{service_id}", dependencies=[Depends(guard)])
def detach_redirect(redirect_id: str, service_id: str) -> JSONResponse:
    db = get_db()
    if error := db.detach_redirect(redirect_id, service_id):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success", "redirect": db.get_redirect_details(redirect_id)})
