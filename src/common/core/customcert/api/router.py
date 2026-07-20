#!/usr/bin/env python3
"""Provider-owned API routes for uploaded certificates."""

from json import JSONDecodeError, loads

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.schemas import CertificateAttachmentRequest, CertificateUpdateRequest  # type: ignore
from app.utils import get_db  # type: ignore
from certificate_utils import MAX_PEM_SIZE  # type: ignore

router = APIRouter(tags=["certificates", "customcert"])


def _error(message: str, status_code: int = 400) -> JSONResponse:
    if "not found" in message.lower():
        status_code = 404
    elif "read-only" in message.lower():
        status_code = 409
    elif "already owned" in message.lower():
        status_code = 409
    return JSONResponse(status_code=status_code, content={"status": "error", "message": message})


@router.post("/certificates/upload")
async def upload_certificate(
    certificate: UploadFile = File(...),
    private_key: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
    service_ids: str = Form("[]"),
    primary: bool = Form(True),
    renewal_metadata: str = Form("{}"),
) -> JSONResponse:
    certificate_pem = await certificate.read(MAX_PEM_SIZE + 1)
    private_key_pem = await private_key.read(MAX_PEM_SIZE + 1)
    if len(certificate_pem) > MAX_PEM_SIZE or len(private_key_pem) > MAX_PEM_SIZE:
        return _error("Certificate and private key files must each be at most 1 MiB", 422)

    try:
        parsed_service_ids = loads(service_ids)
        parsed_metadata = loads(renewal_metadata)
        if not isinstance(parsed_service_ids, list) or len(parsed_service_ids) > 100:
            raise ValueError("service_ids must be a JSON array with at most 100 values")
        normalized_service_ids = [CertificateAttachmentRequest(service_id=value).service_id for value in parsed_service_ids]
        validated = CertificateUpdateRequest(name=name, description=description, renewal_metadata=parsed_metadata)
    except (JSONDecodeError, TypeError, ValueError) as exc:
        return _error(str(exc), 422)

    db = get_db()
    error, certificate_id = db.create_certificate(
        name=validated.name,
        description=validated.description or "",
        source="customcert",
        certificate_pem=certificate_pem,
        private_key_pem=private_key_pem,
        service_ids=list(dict.fromkeys(normalized_service_ids)),
        primary=primary,
        renewal_metadata=validated.renewal_metadata,
    )
    if error:
        return _error(error)
    stored = db.get_certificate_details(certificate_id)
    if stored is None:
        return _error("Certificate was uploaded but could not be read", 500)
    return JSONResponse(status_code=201, content={"status": "success", "certificate": stored})
