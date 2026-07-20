#!/usr/bin/env python3
"""Provider-owned API routes for self-signed certificates."""

from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas import CertificateCreateRequest, CertificateRenewRequest  # type: ignore
from app.utils import get_db  # type: ignore
from certificate_utils import generate_self_signed  # type: ignore

router = APIRouter(tags=["certificates", "selfsigned"])


class SelfSignedCreateRequest(CertificateCreateRequest):
    source: Literal["selfsigned"] = "selfsigned"


def _error(message: str, status_code: int = 400) -> JSONResponse:
    if "not found" in message.lower():
        status_code = 404
    elif "read-only" in message.lower():
        status_code = 409
    elif "already owned" in message.lower():
        status_code = 409
    return JSONResponse(status_code=status_code, content={"status": "error", "message": message})


@router.post("/certificates")
def create_certificate(payload: SelfSignedCreateRequest) -> JSONResponse:
    try:
        certificate_pem, private_key_pem = generate_self_signed(
            payload.common_name,
            payload.sans,
            valid_days=payload.valid_days,
            key_type=payload.key_type,
        )
    except ValueError as exc:
        return _error(str(exc), 422)

    db = get_db()
    error, certificate_id = db.create_certificate(
        name=payload.name,
        description=payload.description,
        source="selfsigned",
        certificate_pem=certificate_pem,
        private_key_pem=private_key_pem,
        service_ids=payload.service_ids,
        primary=payload.primary,
        renewal_metadata=payload.renewal_metadata,
    )
    if error:
        return _error(error)
    certificate = db.get_certificate_details(certificate_id)
    if certificate is None:
        return _error("Certificate was created but could not be read", 500)
    return JSONResponse(status_code=201, content={"status": "success", "certificate": certificate})


@router.post("/certificates/renew-due")
def renew_due_certificates() -> JSONResponse:
    db = get_db()
    due = []
    offset = 0
    while True:
        page = db.get_certificates(source="selfsigned", offset=offset, limit=500)
        due.extend(certificate for certificate in page["items"] if certificate["status"] in ("expiring_soon", "expired"))
        offset += len(page["items"])
        if not page["items"] or offset >= page["total"]:
            break

    results = []
    failed = 0
    for certificate in due:
        error = db.renew_self_signed_certificate(certificate["id"])
        results.append(
            {
                "id": certificate["id"],
                "name": certificate["name"],
                "source": "selfsigned",
                "status": "error" if error else "renewed",
                **({"message": error} if error else {}),
            }
        )
        failed += bool(error)

    renewed = len(due) - failed
    if not due:
        message = "No self-signed certificates are due for renewal"
    elif failed:
        message = f"Renewed {renewed} of {len(due)} due self-signed certificates; {failed} failed"
    else:
        message = f"Renewed {renewed} due self-signed certificate{'s' if renewed != 1 else ''}"
    return JSONResponse(
        status_code=207 if failed else 200,
        content={"status": "partial" if failed else "success", "total_due": len(due), "results": results, "message": message},
    )


@router.post("/certificates/{certificate_id}/renew")
def renew_certificate(certificate_id: str, payload: CertificateRenewRequest) -> JSONResponse:
    db = get_db()
    if error := db.renew_self_signed_certificate(certificate_id, valid_days=payload.valid_days):
        return _error(error, 409)
    return JSONResponse(status_code=200, content={"status": "success", "certificate": db.get_certificate_details(certificate_id)})
