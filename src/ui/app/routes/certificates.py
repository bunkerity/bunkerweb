from collections import Counter
from json import dumps
from re import split

from flask import Blueprint, Response, redirect, render_template, request, url_for
from flask_login import login_required
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.utils import flash

certificates = Blueprint("certificates", __name__)
CERTIFICATE_UPLOAD_MAX_BODY_SIZE = (2 * 1024 * 1024) + (64 * 1024)


def _redirect():
    return redirect(url_for("certificates.certificates_page"))


def _services():
    values = list(dict.fromkeys(value.strip() for value in request.form.getlist("service_ids") if value.strip()))
    if len(values) > 100:
        raise ValueError("A certificate cannot be attached to more than 100 services")
    return values


def _sans():
    values = list(dict.fromkeys(value for value in split(r"[\s,;]+", request.form.get("sans", "").strip()) if value))
    if len(values) > 100:
        raise ValueError("A certificate cannot contain more than 100 subject alternative names")
    return values


def _valid_days(default=365):
    try:
        value = int(request.form.get("valid_days", default))
    except (TypeError, ValueError) as exc:
        raise ValueError("Validity must be a whole number of days") from exc
    if not 1 <= value <= 825:
        raise ValueError("Validity must be between 1 and 825 days")
    return value


def _readonly():
    if not API_CLIENT.readonly:
        return False
    flash("Database is in read-only mode", "error")
    return True


@certificates.route("/certificates", methods=["GET"])
@login_required
def certificates_page():
    try:
        result = API_CLIENT.get_certificates(limit=500)
        certificate_rows = result.get("certificates", [])
        total = result.get("total", len(certificate_rows))
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not fetch certificates: {exc.message}", "error")
        certificate_rows, total = [], 0

    try:
        services = API_CLIENT.get_services(with_drafts=True)
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not fetch services for certificate assignments: {exc.message}", "error")
        services = []

    try:
        orphan_states = {orphan["cert_name"]: orphan for orphan in API_CLIENT.get_letsencrypt_orphans() if isinstance(orphan, dict) and orphan.get("cert_name")}
    except (ApiClientError, ApiUnavailableError):
        orphan_states = {}

    for certificate in certificate_rows:
        cert_name = (certificate.get("renewal_metadata") or {}).get("cert_name")
        certificate["orphan_state"] = orphan_states.get(cert_name) if certificate.get("source") == "letsencrypt" else None
        certificate["is_orphan"] = certificate["orphan_state"] is not None

    status_counts = Counter(certificate.get("status", "") for certificate in certificate_rows)
    issuer_counts = Counter(certificate.get("issuer") or "Unknown" for certificate in certificate_rows)
    upcoming = sorted(
        (certificate for certificate in certificate_rows if certificate.get("status") in {"expiring_soon", "expired"}),
        key=lambda certificate: certificate.get("valid_to", ""),
    )
    certificate_context = [
        {
            "id": certificate.get("id"),
            "name": certificate.get("name"),
            "description": certificate.get("description") or "",
            "common_name": certificate.get("common_name"),
            "source": certificate.get("source"),
            "status": certificate.get("status"),
            "is_orphan": certificate.get("is_orphan", False),
            "attachments": certificate.get("attachments", []),
        }
        for certificate in certificate_rows
    ]
    return render_template(
        "certificates.html",
        certificates=certificate_rows,
        total=total,
        truncated=total > len(certificate_rows),
        status_counts=status_counts,
        issuer_counts=issuer_counts.most_common(),
        upcoming=upcoming,
        certificate_context=certificate_context,
        services=services,
    )


@certificates.route("/certificates/create", methods=["POST"])
@login_required
def certificates_create():
    if _readonly():
        return _redirect()
    try:
        source = request.form.get("source", "")
        if source not in {"letsencrypt", "selfsigned"}:
            raise ValueError("Invalid certificate source")
        service_ids = _services()
        if source == "letsencrypt":
            if not service_ids:
                raise ValueError("Select at least one service for Let's Encrypt issuance")
            first_service = service_ids[0]
            payload = {
                "source": source,
                "name": f"Let's Encrypt: {first_service}"[:256],
                "description": "",
                "common_name": first_service[:253],
                "sans": [],
                "service_ids": service_ids,
                "primary": False,
                "valid_days": 365,
                "key_type": "ec",
                "renewal_metadata": {},
            }
        else:
            name = (request.form.get("name") or "").strip()
            common_name = (request.form.get("common_name") or "").strip()
            if not name or not common_name:
                raise ValueError("Name and common name are required")
            payload = {
                "source": source,
                "name": name,
                "description": (request.form.get("description") or "").strip(),
                "common_name": common_name,
                "sans": _sans(),
                "service_ids": service_ids,
                "primary": "primary" in request.form,
                "valid_days": _valid_days(),
                "key_type": request.form.get("key_type", "ec"),
                "renewal_metadata": {},
            }
        result = API_CLIENT.create_certificate(**payload)
        flash(result.get("message") or ("Let's Encrypt issuance scheduled" if source == "letsencrypt" else "Self-signed certificate created"))
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not create the certificate: {exc.message}", "error")
    return _redirect()


@certificates.route("/certificates/update", methods=["POST"])
@login_required
def certificates_update():
    if _readonly():
        return _redirect()
    certificate_id = (request.form.get("certificate_id") or "").strip()
    name = (request.form.get("name") or "").strip()
    if not certificate_id or not name:
        flash("Certificate and name are required", "error")
        return _redirect()
    try:
        API_CLIENT.update_certificate(
            certificate_id,
            name=name,
            description=(request.form.get("description") or "").strip(),
        )
        flash("Certificate metadata updated successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not update the certificate: {exc.message}", "error")
    return _redirect()


@certificates.route("/certificates/upload", methods=["POST"])
@login_required
def certificates_upload():
    if _readonly():
        return _redirect()
    request.max_content_length = CERTIFICATE_UPLOAD_MAX_BODY_SIZE
    try:
        if request.content_length is not None and request.content_length > CERTIFICATE_UPLOAD_MAX_BODY_SIZE:
            raise RequestEntityTooLarge
        certificate = request.files.get("certificate")
        private_key = request.files.get("private_key")
    except RequestEntityTooLarge:
        flash("Certificate upload exceeds the 2 MiB request limit", "error")
        return _redirect()
    if not certificate or not certificate.filename or not private_key or not private_key.filename:
        flash("A PEM certificate and private key are required", "error")
        return _redirect()

    try:
        name = (request.form.get("name") or "").strip()
        if not name:
            raise ValueError("Certificate name is required")
        API_CLIENT.upload_certificate(
            (secure_filename(certificate.filename) or "certificate.pem", certificate.stream, certificate.mimetype or "application/x-pem-file"),
            (secure_filename(private_key.filename) or "private-key.pem", private_key.stream, private_key.mimetype or "application/x-pem-file"),
            name=name,
            description=(request.form.get("description") or "").strip(),
            service_ids=dumps(_services()),
            primary="true" if "primary" in request.form else "false",
            renewal_metadata="{}",
        )
        flash("Custom certificate uploaded successfully")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not upload the certificate: {exc.message}", "error")
    return _redirect()


@certificates.route("/certificates/attach", methods=["POST"])
@login_required
def certificates_attach():
    if _readonly():
        return _redirect()
    certificate_id = (request.form.get("certificate_id") or "").strip()
    service_id = (request.form.get("service_id") or "").strip()
    if not certificate_id or not service_id:
        flash("Certificate and service are required", "error")
        return _redirect()
    try:
        API_CLIENT.attach_certificate(certificate_id, service_id, primary="primary" in request.form)
        flash("Certificate inventory assignment added successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not attach the certificate: {exc.message}", "error")
    return _redirect()


@certificates.route("/certificates/detach", methods=["POST"])
@login_required
def certificates_detach():
    if _readonly():
        return _redirect()
    certificate_id = (request.form.get("certificate_id") or "").strip()
    service_id = (request.form.get("service_id") or "").strip()
    if not certificate_id or not service_id:
        flash("Certificate and service are required", "error")
        return _redirect()
    try:
        API_CLIENT.detach_certificate(certificate_id, service_id)
        flash("Certificate inventory assignment removed successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not detach the certificate: {exc.message}", "error")
    return _redirect()


@certificates.route("/certificates/action", methods=["POST"])
@login_required
def certificates_action():
    if _readonly():
        return _redirect()
    action = request.form.get("action", "")
    certificate_id = (request.form.get("certificate_id") or "").strip()
    source = (request.form.get("source") or "").strip()
    try:
        if action == "renew_due":
            result = API_CLIENT.renew_due_certificates()
            flash(
                result.get("message") or f"Checked {result.get('total_due', 0)} certificates due for renewal",
                "warning" if result.get("status") == "partial" else "success",
            )
        elif not certificate_id:
            raise ValueError("Certificate is required")
        elif action == "renew":
            result = API_CLIENT.renew_certificate(certificate_id, source, valid_days=_valid_days())
            flash(result.get("message") or "Certificate renewed successfully")
        elif action == "delete":
            API_CLIENT.delete_certificate(certificate_id)
            flash("Certificate deleted successfully")
        else:
            raise ValueError("Invalid certificate action")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Certificate action failed: {exc.message}", "error")
    return _redirect()


@certificates.route("/certificates/<certificate_id>/download/<part>", methods=["GET"])
@login_required
def certificates_download(certificate_id, part):
    if part not in {"leaf", "chain"}:
        return Response("Invalid certificate part", status=400)
    try:
        response = API_CLIENT.download_certificate(certificate_id, part=part)
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not download the certificate: {exc.message}", "error")
        return _redirect()

    return Response(
        response.content,
        mimetype="application/x-pem-file",
        headers={
            "Content-Disposition": response.headers.get("Content-Disposition", f'attachment; filename="certificate-{part}.pem"'),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
