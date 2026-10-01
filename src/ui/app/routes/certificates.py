from collections import Counter
from json import dumps
from re import split

from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from flask import Blueprint, Response, redirect, render_template, request, url_for
from flask_login import login_required
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from default_server import is_reserved_default_server  # type: ignore

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.form_retry import keep_form, take_form_retry
from app.i18n import translated
from app.utils import LOGGER, flash, is_readonly_request

certificates = Blueprint("certificates", __name__)
CERTIFICATE_UPLOAD_MAX_BODY_SIZE = (2 * 1024 * 1024) + (64 * 1024)


def _redirect():
    return redirect(url_for("certificates.certificates_page"))


def _services():
    values = list(dict.fromkeys(value.strip() for value in request.form.getlist("service_ids") if value.strip()))
    if len(values) > 100:
        raise ValueError(translated("certificates.flash.too_many_services") or "A certificate cannot be attached to more than 100 services")
    return values


def _sans():
    values = list(dict.fromkeys(value for value in split(r"[\s,;]+", request.form.get("sans", "").strip()) if value))
    if len(values) > 100:
        raise ValueError(translated("certificates.flash.too_many_sans") or "A certificate cannot contain more than 100 subject alternative names")
    return values


def _valid_days(default=365):
    try:
        value = int(request.form.get("valid_days", default))
    except (TypeError, ValueError) as exc:
        raise ValueError(translated("certificates.flash.validity_whole_number") or "Validity must be a whole number of days") from exc
    if not 1 <= value <= 825:
        raise ValueError(translated("certificates.flash.validity_range") or "Validity must be between 1 and 825 days")
    return value


def _readonly():
    if API_CLIENT.readonly:
        flash(translated("flash.database_read_only_mode") or "Database is in read-only mode", "error")
        return True
    if is_readonly_request(API_CLIENT.readonly):
        # Two causes, two messages: the database is fine here, the session's permission is not.
        flash(translated("flash.do_not_have_write_permission") or "You do not have the write permission", "error")
        return True
    return False


@certificates.route("/certificates", methods=["GET"])
@login_required
def certificates_page():
    try:
        result = API_CLIENT.get_certificates(limit=500)
        certificate_rows = result.get("certificates", [])
        total = result.get("total", len(certificate_rows))
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(translated("certificates.flash.could_not_fetch_certificates", message=exc.message) or f"Could not fetch certificates: {exc.message}", "error")
        certificate_rows, total = [], 0

    try:
        # A picker filter, not a guard -- the API has no reserved-id refusal on a certificate
        # attachment, so this only stops the operator from offering it in the first place (DS-B4
        # handoff item 4 / criticos-DS-B optional 8). Defensible anyway: certificate selection
        # (certificates.lua:ssl_certificate()) keys on the TLS handshake's own client-controlled
        # SNI, which is never the reserved id for any real client, so an attachment made on it
        # despite this filter would still never be selected in practice.
        services = [service for service in API_CLIENT.get_services(with_drafts=True) if not is_reserved_default_server(service)]
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(
            translated("certificates.flash.could_not_fetch_services_certificate_assignments", message=exc.message)
            or f"Could not fetch services for certificate assignments: {exc.message}",
            "error",
        )
        services = []

    try:
        orphan_states = {orphan["cert_name"]: orphan for orphan in API_CLIENT.get_letsencrypt_orphans() if isinstance(orphan, dict) and orphan.get("cert_name")}
    except (ApiClientError, ApiUnavailableError):
        orphan_states = {}

    # Built by the API from the plugins that declare themselves a certificate source, so a
    # certificate issued by a pro or external provider is filterable like any core one.
    try:
        sources = API_CLIENT.get_certificate_sources()
    except (ApiClientError, ApiUnavailableError):
        sources = {}

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
        sources=sources,
        form_retry=take_form_retry(),
    )


def _refuse(form_id: str, message: str) -> None:
    """Flash a refusal AND keep the modal's input, which the page reopens it with (QA-UI M28):
    these forms post natively, and the redirect used to come back with the modal closed and empty.
    `message` is resolved by the caller (translated() or already-translated), never a raw literal here."""
    flash(message, "error")
    keep_form(form_id, message)


def _pem_refusal(certificate, private_key) -> str:
    """Why the uploaded pair is not usable PEM, in words, or "".

    Checked here, before the upload, because the API passes the `cryptography` exception text
    through ("Unable to load PEM file. See https://cryptography.io/... MalformedFraming", QA-UI
    M28). The detail goes to the log; the check that the key MATCHES the certificate stays the
    API's, whose message is already readable.
    """
    try:
        certificate_pem = certificate.stream.read()
        certificate.stream.seek(0)
        if not x509.load_pem_x509_certificates(certificate_pem):
            raise ValueError("no certificate in the file")
    except ValueError as exc:
        LOGGER.warning(f"Refused the uploaded certificate {certificate.filename!r}: {exc}")
        return translated("certificates.flash.invalid_certificate_pem") or "The certificate file is not a valid PEM certificate."
    try:
        private_key_pem = private_key.stream.read()
        private_key.stream.seek(0)
        load_pem_private_key(private_key_pem, password=None)
    except TypeError:
        return translated("certificates.flash.encrypted_private_key") or "Encrypted private keys are not supported."
    except (ValueError, UnsupportedAlgorithm) as exc:
        LOGGER.warning(f"Refused the uploaded private key {private_key.filename!r}: {exc}")
        return translated("certificates.flash.invalid_private_key_pem") or "The private key file is not a valid PEM private key."
    return ""


@certificates.route("/certificates/create", methods=["POST"])
@login_required
def certificates_create():
    if _readonly():
        return _redirect()
    try:
        source = request.form.get("source", "")
        if source not in {"letsencrypt", "selfsigned"}:
            raise ValueError(translated("certificates.flash.invalid_certificate_source") or "Invalid certificate source")
        service_ids = _services()
        if source == "letsencrypt":
            if not service_ids:
                raise ValueError(translated("certificates.flash.select_service_letsencrypt") or "Select at least one service for Let's Encrypt issuance")
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
                raise ValueError(translated("certificates.flash.name_common_name_are_required") or "Name and common name are required")
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
        if source == "letsencrypt":
            flash(result.get("message") or translated("certificates.flash.letsencrypt_issuance_scheduled") or "Let's Encrypt issuance scheduled")
        else:
            flash(result.get("message") or translated("certificates.flash.selfsigned_certificate_created") or "Self-signed certificate created")
    except ValueError as exc:
        _refuse(f"certificate-{source}", str(exc))
    except (ApiClientError, ApiUnavailableError) as exc:
        if source == "letsencrypt":
            _refuse(
                f"certificate-{source}",
                translated("certificates.flash.could_not_schedule_letsencrypt", message=exc.message)
                or f"Could not schedule Let's Encrypt issuance: {exc.message}",
            )
        else:
            _refuse(
                f"certificate-{source}",
                translated("certificates.flash.could_not_create_certificate", message=exc.message) or f"Could not create the certificate: {exc.message}",
            )
    return _redirect()


@certificates.route("/certificates/update", methods=["POST"])
@login_required
def certificates_update():
    if _readonly():
        return _redirect()
    certificate_id = (request.form.get("certificate_id") or "").strip()
    name = (request.form.get("name") or "").strip()
    if not certificate_id or not name:
        _refuse("certificate-edit", translated("certificates.flash.certificate_name_are_required") or "Certificate and name are required")
        return _redirect()
    try:
        API_CLIENT.update_certificate(
            certificate_id,
            name=name,
            description=(request.form.get("description") or "").strip(),
        )
        flash(translated("certificates.flash.certificate_metadata_updated_successfully") or "Certificate metadata updated successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        _refuse(
            "certificate-edit",
            translated("certificates.flash.could_not_update_certificate", message=exc.message) or f"Could not update the certificate: {exc.message}",
        )
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
        flash(translated("certificates.flash.certificate_upload_exceeds_2_mib_request") or "Certificate upload exceeds the 2 MiB request limit", "error")
        return _redirect()
    if not certificate or not certificate.filename or not private_key or not private_key.filename:
        _refuse("certificate-upload", translated("certificates.flash.pem_certificate_private_key_required") or "A PEM certificate and private key are required")
        return _redirect()
    refusal = _pem_refusal(certificate, private_key)
    if refusal:
        _refuse("certificate-upload", refusal)
        return _redirect()

    try:
        name = (request.form.get("name") or "").strip()
        if not name:
            raise ValueError(translated("certificates.flash.certificate_name_required") or "Certificate name is required")
        API_CLIENT.upload_certificate(
            (secure_filename(certificate.filename) or "certificate.pem", certificate.stream, certificate.mimetype or "application/x-pem-file"),
            (secure_filename(private_key.filename) or "private-key.pem", private_key.stream, private_key.mimetype or "application/x-pem-file"),
            name=name,
            description=(request.form.get("description") or "").strip(),
            service_ids=dumps(_services()),
            primary="true" if "primary" in request.form else "false",
            renewal_metadata="{}",
        )
        flash(translated("certificates.flash.custom_certificate_uploaded_successfully") or "Custom certificate uploaded successfully")
    except ValueError as exc:
        _refuse("certificate-upload", str(exc))
    except (ApiClientError, ApiUnavailableError) as exc:
        _refuse(
            "certificate-upload",
            translated("certificates.flash.could_not_upload_certificate", message=exc.message) or f"Could not upload the certificate: {exc.message}",
        )
    return _redirect()


@certificates.route("/certificates/attach", methods=["POST"])
@login_required
def certificates_attach():
    if _readonly():
        return _redirect()
    certificate_id = (request.form.get("certificate_id") or "").strip()
    service_id = (request.form.get("service_id") or "").strip()
    if not certificate_id or not service_id:
        _refuse("certificate-attach", translated("certificates.flash.certificate_service_are_required") or "Certificate and service are required")
        return _redirect()
    try:
        API_CLIENT.attach_certificate(certificate_id, service_id, primary="primary" in request.form)
        flash(translated("certificates.flash.certificate_inventory_assignment_added_successfully") or "Certificate inventory assignment added successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        _refuse(
            "certificate-attach",
            translated("certificates.flash.could_not_attach_certificate", message=exc.message) or f"Could not attach the certificate: {exc.message}",
        )
    return _redirect()


@certificates.route("/certificates/detach", methods=["POST"])
@login_required
def certificates_detach():
    if _readonly():
        return _redirect()
    certificate_id = (request.form.get("certificate_id") or "").strip()
    service_id = (request.form.get("service_id") or "").strip()
    if not certificate_id or not service_id:
        flash(translated("certificates.flash.certificate_service_are_required") or "Certificate and service are required", "error")
        return _redirect()
    try:
        API_CLIENT.detach_certificate(certificate_id, service_id)
        flash(translated("certificates.flash.certificate_inventory_assignment_removed_successfully") or "Certificate inventory assignment removed successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(translated("certificates.flash.could_not_detach_certificate", message=exc.message) or f"Could not detach the certificate: {exc.message}", "error")
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
            total_due = result.get("total_due", 0)
            flash(
                result.get("message")
                or translated("certificates.flash.checked_certificates_due_renewal", total_due=total_due)
                or f"Checked {total_due} certificates due for renewal",
                "warning" if result.get("status") == "partial" else "success",
            )
        elif not certificate_id:
            raise ValueError(translated("certificates.flash.certificate_required") or "Certificate is required")
        elif action == "renew":
            result = API_CLIENT.renew_certificate(certificate_id, source, valid_days=_valid_days())
            flash(result.get("message") or translated("certificates.flash.certificate_renewed_successfully") or "Certificate renewed successfully")
        elif action == "delete":
            API_CLIENT.delete_certificate(certificate_id)
            flash(translated("certificates.flash.certificate_deleted_successfully") or "Certificate deleted successfully")
        else:
            raise ValueError(translated("certificates.flash.invalid_certificate_action") or "Invalid certificate action")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(translated("certificates.flash.certificate_action_failed", message=exc.message) or f"Certificate action failed: {exc.message}", "error")
    return _redirect()


@certificates.route("/certificates/<certificate_id>/download/<part>", methods=["GET"])
@login_required
def certificates_download(certificate_id, part):
    if part not in {"leaf", "chain"}:
        return Response(translated("certificates.flash.invalid_certificate_part") or "Invalid certificate part", status=400)
    try:
        response = API_CLIENT.download_certificate(certificate_id, part=part)
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(
            translated("certificates.flash.could_not_download_certificate", message=exc.message) or f"Could not download the certificate: {exc.message}",
            "error",
        )
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
