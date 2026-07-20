from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response

from ..auth.guard import guard
from ..schemas import CertificateAttachmentRequest, CertificateUpdateRequest
from ..utils import LOGGER, get_db

router = APIRouter(prefix="/certificates", tags=["certificates"])


def _error(message: str, default: int = 400) -> JSONResponse:
    if "not found" in message.lower():
        default = 404
    elif "read-only" in message.lower():
        default = 409
    return JSONResponse(status_code=default, content={"status": "error", "message": message})


def import_legacy_certificates() -> None:
    """Best-effort migration of the existing certbot cache into inventory."""
    try:
        summary = get_db().import_legacy_certbot_certificates()
    except Exception as exc:
        LOGGER.warning(f"Unable to import legacy certificates: {exc}")
        return
    if summary["errors"]:
        LOGGER.warning(f"Legacy certificate import completed with {len(summary['errors'])} error(s): {summary['errors']}")


@router.get("", dependencies=[Depends(guard)])
def list_certificates(
    search: str = "",
    source: str = Query("", pattern="^(|letsencrypt|customcert|selfsigned)$"),
    status: str = Query("", pattern="^(|valid|expiring_soon|expired|not_yet_valid|revoked)$"),
    service_id: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> JSONResponse:
    result = get_db().get_certificates(search=search, source=source, status=status, service_id=service_id, offset=offset, limit=limit)
    return JSONResponse(
        status_code=200, content={"status": "success", "certificates": result["items"], **{key: result[key] for key in ("total", "offset", "limit")}}
    )


@router.get("/{certificate_id}", dependencies=[Depends(guard)])
def get_certificate(certificate_id: str) -> JSONResponse:
    certificate = get_db().get_certificate_details(certificate_id)
    if certificate is None:
        return _error("Certificate not found", 404)
    return JSONResponse(status_code=200, content={"status": "success", "certificate": certificate})


@router.patch("/{certificate_id}", dependencies=[Depends(guard)])
def update_certificate(certificate_id: str, payload: CertificateUpdateRequest) -> JSONResponse:
    values = payload.model_dump(exclude_unset=True)
    error = get_db().update_certificate(certificate_id, **values)
    if error:
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success", "certificate": get_db().get_certificate_details(certificate_id)})


@router.delete("/{certificate_id}", dependencies=[Depends(guard)])
def delete_certificate(certificate_id: str) -> JSONResponse:
    db = get_db()
    certificate = db.get_certificate_details(certificate_id)
    if certificate is None:
        return _error("Certificate not found", 404)
    if certificate["attachments"]:
        return _error("Certificate is attached to a service", 409)

    if error := db.delete_certificate(certificate_id):
        return _error(error, 409)
    return JSONResponse(status_code=200, content={"status": "success"})


@router.post("/{certificate_id}/attachments", dependencies=[Depends(guard)])
def attach_certificate(certificate_id: str, payload: CertificateAttachmentRequest) -> JSONResponse:
    if error := get_db().attach_certificate(certificate_id, payload.service_id, primary=payload.primary):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success", "certificate": get_db().get_certificate_details(certificate_id)})


@router.delete("/{certificate_id}/attachments/{service_id}", dependencies=[Depends(guard)])
def detach_certificate(certificate_id: str, service_id: str) -> JSONResponse:
    if error := get_db().detach_certificate(certificate_id, service_id):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success", "certificate": get_db().get_certificate_details(certificate_id)})


@router.get("/{certificate_id}/download", dependencies=[Depends(guard)])
def download_certificate(certificate_id: str, part: Literal["leaf", "chain"] = "chain") -> Response:
    db = get_db()
    certificate = db.get_certificate_details(certificate_id)
    if certificate is None:
        return _error("Certificate not found", 404)
    try:
        data = db.get_certificate_public_data(certificate_id, part)
    except ValueError as exc:
        return _error(f"Stored certificate is invalid: {exc}", 500)
    filename = quote(f"{certificate['name']}-{part}.pem")
    return Response(
        content=data,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}", "X-Content-Type-Options": "nosniff"},
    )
