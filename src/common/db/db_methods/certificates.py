#!/usr/bin/env python3
"""First-class certificate resource persistence."""

from datetime import datetime, timedelta, timezone
from json import JSONDecodeError, dumps, loads
from tarfile import TarError
from typing import Any, Dict, List, Optional
from uuid import uuid4

from certificate_utils import certificate_status, decrypt_private_key, encrypt_private_key, parse_certificate, read_certbot_cache, renew_self_signed  # type: ignore
from cryptography.exceptions import InvalidTag
from model import Certificates, ResourceAttachments, Resources, Services  # type: ignore
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError

from .common import DatabaseMixinBase

CERTIFICATE_SOURCES = frozenset(("letsencrypt", "customcert", "selfsigned"))
CERTIFICATE_PROVIDER_METADATA_KEYS = frozenset(("cache_checksum", "cert_name", "legacy", "managed_by", "service_ids"))


def _json_object(value: Optional[dict]) -> str:
    return dumps(value or {}, sort_keys=True, separators=(",", ":"))


def _load_json(value: Optional[str], fallback):
    try:
        parsed = loads(value or "")
    except (JSONDecodeError, TypeError):
        return fallback
    return parsed


class DatabaseCertificatesMixin(DatabaseMixinBase):
    """Certificate CRUD, assignment and self-signed renewal."""

    def _certificate_attachments(self, session, resource_ids: List[str]) -> Dict[str, List[dict]]:
        attachments: Dict[str, List[dict]] = {resource_id: [] for resource_id in resource_ids}
        if not resource_ids:
            return attachments
        for row in session.execute(
            select(ResourceAttachments.resource_id, ResourceAttachments.service_id, ResourceAttachments.is_primary)
            .where(ResourceAttachments.resource_id.in_(resource_ids))
            .order_by(ResourceAttachments.service_id)
        ):
            attachments[row.resource_id].append({"service_id": row.service_id, "is_primary": row.is_primary})
        return attachments

    @staticmethod
    def _certificate_dict(resource, certificate, attachments: List[dict]) -> dict:
        return {
            "id": resource.id,
            "name": resource.name,
            "description": resource.description or "",
            "source": certificate.source,
            "common_name": certificate.common_name,
            "sans": _load_json(certificate.sans, []),
            "issuer": certificate.issuer,
            "serial_number": certificate.serial_number,
            "fingerprint": certificate.fingerprint,
            "key_type": certificate.key_type,
            "valid_from": certificate.valid_from.isoformat(),
            "valid_to": certificate.valid_to.isoformat(),
            "status": certificate_status(certificate.valid_from, certificate.valid_to, revoked=certificate.revoked),
            "renewal_metadata": _load_json(certificate.renewal_metadata, {}),
            "last_renewal": certificate.last_renewal.isoformat() if certificate.last_renewal else None,
            "next_renewal": certificate.next_renewal.isoformat() if certificate.next_renewal else None,
            "last_error": certificate.last_error or "",
            "revoked": certificate.revoked,
            "revoked_at": certificate.revoked_at.isoformat() if certificate.revoked_at else None,
            "attachments": attachments,
            "creation_date": resource.creation_date.isoformat(),
            "last_update": resource.last_update.isoformat(),
        }

    def get_certificates(
        self,
        *,
        search: str = "",
        source: str = "",
        status: str = "",
        service_id: str = "",
        offset: int = 0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        with self._db_session() as session:
            query = select(Resources, Certificates).join(Certificates, Certificates.resource_id == Resources.id).order_by(Certificates.valid_to, Resources.name)
            if source:
                query = query.where(Certificates.source == source)
            if search:
                pattern = f"%{search.strip()}%"
                query = query.where(
                    or_(
                        Resources.name.ilike(pattern),
                        Certificates.common_name.ilike(pattern),
                        Certificates.issuer.ilike(pattern),
                        Certificates.fingerprint.ilike(pattern),
                    )
                )
            rows = list(session.execute(query))
            ids = [resource.id for resource, _ in rows]
            attachments = self._certificate_attachments(session, ids)
            items = [self._certificate_dict(resource, certificate, attachments[resource.id]) for resource, certificate in rows]

        if service_id:
            items = [item for item in items if any(attachment["service_id"] == service_id for attachment in item["attachments"])]
        if status:
            items = [item for item in items if item["status"] == status]
        total = len(items)
        offset = max(0, offset)
        limit = max(1, min(limit, 500))
        return {"items": items[offset : offset + limit], "total": total, "offset": offset, "limit": limit}  # noqa: E203

    def get_certificate_details(self, resource_id: str) -> Optional[Dict[str, Any]]:
        with self._db_session() as session:
            row = session.execute(
                select(Resources, Certificates).join(Certificates, Certificates.resource_id == Resources.id).where(Resources.id == resource_id).limit(1)
            ).first()
            if not row:
                return None
            attachments = self._certificate_attachments(session, [resource_id])
            return self._certificate_dict(row[0], row[1], attachments[resource_id])

    def create_certificate(
        self,
        *,
        name: str,
        source: str,
        certificate_pem: bytes,
        private_key_pem: bytes,
        description: str = "",
        service_ids: Optional[List[str]] = None,
        primary: bool = True,
        renewal_metadata: Optional[dict] = None,
        deduplicate: bool = False,
    ) -> tuple[str, Optional[str]]:
        if self.readonly:
            return "The database is read-only, the changes will not be saved", None
        source = source.strip().lower()
        if source not in CERTIFICATE_SOURCES:
            return f"Invalid certificate source: {source}", None
        name = name.strip()
        if not name:
            return "Certificate name is required", None
        service_ids = list(dict.fromkeys(service_id.strip() for service_id in service_ids or [] if service_id.strip()))
        try:
            parsed = parse_certificate(certificate_pem, private_key_pem)
        except (TypeError, ValueError) as exc:
            return str(exc), None

        resource_id = str(uuid4())
        try:
            ciphertext, nonce, key_id = encrypt_private_key(private_key_pem, resource_id)
        except ValueError as exc:
            return str(exc), None

        with self._db_session() as session:
            duplicate = session.execute(
                select(Certificates.resource_id, Certificates.source).where(Certificates.fingerprint == parsed["fingerprint"]).limit(1)
            ).first()
            if duplicate:
                if deduplicate and duplicate.source == source:
                    return "", duplicate.resource_id
                return f"Certificate fingerprint is already owned by {duplicate.source}", None
            if session.execute(select(Resources.id).where(Resources.type == "certificate", Resources.name == name).limit(1)).first():
                return f"Certificate name {name} already exists", None

            if service_ids:
                # Serialize primary assignment per service; without this lock two
                # concurrent creates can both clear then insert a primary row.
                existing_services = set(session.scalars(select(Services.id).where(Services.id.in_(service_ids)).with_for_update()))
                missing = [service_id for service_id in service_ids if service_id not in existing_services]
                if missing:
                    return f"Unknown service(s): {', '.join(missing)}", None

            now = datetime.now(timezone.utc)
            stored_metadata = dict(renewal_metadata or {})
            if service_ids:
                stored_metadata["service_ids"] = service_ids
            resource = Resources(id=resource_id, type="certificate", name=name, description=description or "", creation_date=now, last_update=now)
            resource.certificate = Certificates(
                source=source,
                certificate_pem=parsed["certificate_pem"],
                private_key_ciphertext=ciphertext,
                private_key_nonce=nonce,
                private_key_key_id=key_id,
                common_name=parsed["common_name"],
                sans=dumps(parsed["sans"], separators=(",", ":")),
                issuer=parsed["issuer"],
                serial_number=parsed["serial_number"],
                fingerprint=parsed["fingerprint"],
                key_type=parsed["key_type"],
                valid_from=parsed["valid_from"],
                valid_to=parsed["valid_to"],
                renewal_metadata=_json_object(stored_metadata),
                next_renewal=parsed["valid_to"] - timedelta(days=30),
                revoked=False,
            )
            session.add(resource)
            try:
                session.flush()
                for service_id in service_ids:
                    if primary:
                        session.execute(update(ResourceAttachments).where(ResourceAttachments.service_id == service_id).values(is_primary=False))
                    session.add(ResourceAttachments(resource_id=resource_id, service_id=service_id, is_primary=primary, creation_date=now))
                session.commit()
            except IntegrityError:
                session.rollback()
                duplicate = session.execute(
                    select(Certificates.resource_id, Certificates.source).where(Certificates.fingerprint == parsed["fingerprint"]).limit(1)
                ).first()
                if duplicate:
                    if deduplicate and duplicate.source == source:
                        return "", duplicate.resource_id
                    return f"Certificate fingerprint is already owned by {duplicate.source}", None
                if session.execute(select(Resources.id).where(Resources.type == "certificate", Resources.name == name).limit(1)).first():
                    return f"Certificate name {name} already exists", None
                return "Certificate could not be created because a conflicting resource was inserted concurrently", None
            except BaseException as exc:
                return f"An error occurred while creating certificate: {exc}", None
        return "", resource_id

    def import_certificate(self, **kwargs) -> tuple[str, Optional[str]]:
        """Idempotently create or refresh an imported certificate by fingerprint/name."""
        if self.readonly:
            return "The database is read-only, the changes will not be saved", None

        name = str(kwargs.get("name", "")).strip()
        source = str(kwargs.get("source", "")).strip().lower()
        certificate_pem = kwargs.get("certificate_pem", b"")
        private_key_pem = kwargs.get("private_key_pem", b"")
        service_ids = list(dict.fromkeys(kwargs.get("service_ids") or []))
        try:
            parsed = parse_certificate(certificate_pem, private_key_pem)
        except (TypeError, ValueError) as exc:
            return str(exc), None

        with self._db_session() as session:
            fingerprint_match = session.execute(
                select(Resources, Certificates)
                .join(Certificates, Certificates.resource_id == Resources.id)
                .where(Certificates.fingerprint == parsed["fingerprint"])
                .limit(1)
            ).first()
            existing = session.execute(
                select(Resources, Certificates)
                .join(Certificates, Certificates.resource_id == Resources.id)
                .where(Resources.type == "certificate", Resources.name == name, Certificates.source == source)
                .limit(1)
            ).first()

        if fingerprint_match:
            fingerprint_source = fingerprint_match[1].source
            if fingerprint_source != source:
                return (
                    f"Certificate fingerprint is already owned by {fingerprint_source}; "
                    f"remove that inventory certificate before importing it through {source}",
                    None,
                )
            existing = fingerprint_match

        if fingerprint_match and source != "letsencrypt":
            fingerprint_id = fingerprint_match[0].id
            for service_id in service_ids:
                if error := self.attach_certificate(fingerprint_id, service_id, primary=True):
                    return error, None
            return "", fingerprint_id

        if not existing:
            return self.create_certificate(deduplicate=True, **kwargs)

        resource, certificate = existing
        material_changed = certificate.fingerprint != parsed["fingerprint"]
        if material_changed:
            try:
                ciphertext, nonce, key_id = encrypt_private_key(private_key_pem, resource.id)
            except ValueError as exc:
                return str(exc), None
        with self._db_session() as session:
            resource = session.get(Resources, resource.id)
            certificate = session.get(Certificates, certificate.resource_id)
            if resource is None or certificate is None:
                return "Certificate disappeared during import", None
            now = datetime.now(timezone.utc)
            metadata = dict(kwargs.get("renewal_metadata") or {})
            if source == "letsencrypt":
                metadata["cert_name"] = str(metadata.get("cert_name") or name)
                metadata["managed_by"] = "letsencrypt"
            if service_ids:
                metadata["service_ids"] = service_ids

            certificate.source = source
            metadata_json = _json_object(metadata)
            metadata_changed = certificate.renewal_metadata != metadata_json
            certificate.renewal_metadata = metadata_json
            if material_changed:
                certificate.certificate_pem = parsed["certificate_pem"]
                certificate.private_key_ciphertext = ciphertext
                certificate.private_key_nonce = nonce
                certificate.private_key_key_id = key_id
                certificate.common_name = parsed["common_name"]
                certificate.sans = dumps(parsed["sans"], separators=(",", ":"))
                certificate.issuer = parsed["issuer"]
                certificate.serial_number = parsed["serial_number"]
                certificate.fingerprint = parsed["fingerprint"]
                certificate.key_type = parsed["key_type"]
                certificate.valid_from = parsed["valid_from"]
                certificate.valid_to = parsed["valid_to"]
                certificate.last_renewal = now
                certificate.next_renewal = parsed["valid_to"] - timedelta(days=30)
                certificate.last_error = ""
                certificate.revoked = False
                certificate.revoked_at = None
            if material_changed or metadata_changed:
                resource.last_update = now
            try:
                session.commit()
            except BaseException as exc:
                return f"An error occurred while importing certificate: {exc}", None
        for service_id in service_ids:
            if error := self.attach_certificate(resource.id, service_id, primary=True):
                return error, None
        return "", resource.id

    def import_legacy_certbot_certificates(self) -> Dict[str, Any]:
        """Import current certbot DB caches without writing plaintext keys to disk."""
        if self.readonly:
            return {"imported": 0, "unchanged": 0, "errors": []}

        cache_files = []
        for job_name in ("certbot-new", "certbot-renew"):
            cache_files.extend(self.get_jobs_cache_files(with_data=True, job_name=job_name))
        cache_files.sort(key=lambda item: str(item.get("last_update") or ""))
        known_services = {service["id"] for service in self.get_services(with_drafts=True)}
        summary: Dict[str, Any] = {"imported": 0, "unchanged": 0, "errors": []}
        for cache_file in cache_files:
            if not cache_file["file_name"].startswith("folder:") or not cache_file["file_name"].endswith(".tgz"):
                continue
            try:
                records = read_certbot_cache(cache_file["data"])
            except (OSError, TarError, ValueError) as exc:
                summary["errors"].append(str(exc))
                continue
            for record in records:
                try:
                    parsed = parse_certificate(record["certificate_pem"])
                except (TypeError, ValueError) as exc:
                    summary["errors"].append(f"{record['name']}: {exc}")
                    continue
                names = {record["name"], parsed["common_name"], *parsed["sans"]}
                service_ids = sorted(known_services.intersection(names))
                previous = self.get_certificates(search=record["name"], source="letsencrypt", limit=500)["items"]
                previous_fingerprints = {item["fingerprint"] for item in previous if item["name"] == record["name"]}
                metadata = dict(record["renewal_metadata"])
                metadata["cert_name"] = record["name"]
                metadata["managed_by"] = "letsencrypt"
                metadata["cache_checksum"] = cache_file.get("checksum") or ""
                error, _ = self.import_certificate(
                    name=record["name"],
                    description="Imported from the legacy certbot cache",
                    source="letsencrypt",
                    certificate_pem=record["certificate_pem"],
                    private_key_pem=record["private_key_pem"],
                    service_ids=service_ids,
                    primary=True,
                    renewal_metadata=metadata,
                )
                if error:
                    summary["errors"].append(f"{record['name']}: {error}")
                elif parsed["fingerprint"] in previous_fingerprints:
                    summary["unchanged"] += 1
                else:
                    summary["imported"] += 1
        return summary

    def update_certificate(
        self,
        resource_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        renewal_metadata: Optional[dict] = None,
        last_error: Optional[str] = None,
    ) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            row = session.execute(
                select(Resources, Certificates).join(Certificates, Certificates.resource_id == Resources.id).where(Resources.id == resource_id).limit(1)
            ).first()
            if not row:
                return "Certificate not found"
            resource, certificate = row
            if name is not None:
                normalized = name.strip()
                if not normalized:
                    return "Certificate name is required"
                duplicate = session.execute(
                    select(Resources.id).where(Resources.type == "certificate", Resources.name == normalized, Resources.id != resource_id).limit(1)
                ).first()
                if duplicate:
                    return f"Certificate name {normalized} already exists"
                resource.name = normalized
            if description is not None:
                resource.description = description
            if renewal_metadata is not None:
                current_metadata = _load_json(certificate.renewal_metadata, {})
                updated_metadata = {key: value for key, value in renewal_metadata.items() if key not in CERTIFICATE_PROVIDER_METADATA_KEYS}
                for key in CERTIFICATE_PROVIDER_METADATA_KEYS:
                    if key in current_metadata:
                        updated_metadata[key] = current_metadata[key]
                certificate.renewal_metadata = _json_object(updated_metadata)
            if last_error is not None:
                certificate.last_error = last_error
            resource.last_update = datetime.now(timezone.utc)
            try:
                session.commit()
            except BaseException as exc:
                return f"An error occurred while updating certificate: {exc}"
        return ""

    def delete_certificate(self, resource_id: str) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            resource = session.get(Resources, resource_id)
            if resource is None or resource.type != "certificate":
                return "Certificate not found"
            certificate = session.get(Certificates, resource_id)
            metadata = _load_json(certificate.renewal_metadata, {}) if certificate is not None else {}
            if certificate is not None and (certificate.source == "letsencrypt" or metadata.get("managed_by") or metadata.get("legacy") is True):
                return "Managed certificates cannot be deleted from inventory; disable the provider and remove its source cache instead"
            if session.execute(select(ResourceAttachments.id).where(ResourceAttachments.resource_id == resource_id).limit(1)).first():
                return "Certificate is attached to a service"
            session.delete(resource)
            try:
                session.commit()
            except BaseException as exc:
                return f"An error occurred while deleting certificate: {exc}"
        return ""

    def attach_certificate(self, resource_id: str, service_id: str, *, primary: bool = True) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            if session.get(Certificates, resource_id) is None:
                return "Certificate not found"
            service = session.execute(select(Services).where(Services.id == service_id).with_for_update()).scalar_one_or_none()
            if service is None:
                return "Service not found"
            attachment = session.execute(
                select(ResourceAttachments).where(ResourceAttachments.resource_id == resource_id, ResourceAttachments.service_id == service_id).limit(1)
            ).scalar_one_or_none()
            if primary:
                session.execute(update(ResourceAttachments).where(ResourceAttachments.service_id == service_id).values(is_primary=False))
            if attachment:
                attachment.is_primary = primary
            else:
                session.add(
                    ResourceAttachments(
                        resource_id=resource_id,
                        service_id=service_id,
                        is_primary=primary,
                        creation_date=datetime.now(timezone.utc),
                    )
                )
            try:
                session.commit()
            except BaseException as exc:
                return f"An error occurred while attaching certificate: {exc}"
        return ""

    def detach_certificate(self, resource_id: str, service_id: str) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            result = session.execute(
                delete(ResourceAttachments).where(ResourceAttachments.resource_id == resource_id, ResourceAttachments.service_id == service_id),
                execution_options={"synchronize_session": False},
            )
            if not result.rowcount:
                return "Certificate attachment not found"
            try:
                session.commit()
            except BaseException as exc:
                return f"An error occurred while detaching certificate: {exc}"
        return ""

    def get_certificate_public_data(self, resource_id: str, part: str) -> Optional[bytes]:
        with self._db_session() as session:
            certificate_pem = session.execute(select(Certificates.certificate_pem).where(Certificates.resource_id == resource_id)).scalar_one_or_none()
        if certificate_pem is None:
            return None
        parsed = parse_certificate(certificate_pem.encode())
        return parsed["leaf_pem"] if part == "leaf" else certificate_pem.encode()

    def renew_self_signed_certificate(self, resource_id: str, *, valid_days: int = 365) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            certificate = session.get(Certificates, resource_id)
            if certificate is None:
                return "Certificate not found"
            if certificate.source != "selfsigned":
                return "Only self-signed certificates can be renewed locally"
            try:
                private_key = decrypt_private_key(
                    certificate.private_key_ciphertext,
                    certificate.private_key_nonce,
                    certificate.private_key_key_id,
                    resource_id,
                )
                renewed_pem = renew_self_signed(certificate.certificate_pem.encode(), private_key, valid_days=valid_days)
                parsed = parse_certificate(renewed_pem, private_key)
            except (TypeError, ValueError, InvalidTag) as exc:
                certificate.last_error = str(exc) or exc.__class__.__name__
                session.commit()
                return certificate.last_error
            now = datetime.now(timezone.utc)
            certificate.certificate_pem = parsed["certificate_pem"]
            certificate.serial_number = parsed["serial_number"]
            certificate.fingerprint = parsed["fingerprint"]
            certificate.valid_from = parsed["valid_from"]
            certificate.valid_to = parsed["valid_to"]
            certificate.last_renewal = now
            certificate.next_renewal = parsed["valid_to"] - timedelta(days=30)
            certificate.last_error = ""
            certificate.revoked = False
            certificate.revoked_at = None
            certificate.resource.last_update = now
            try:
                session.commit()
            except BaseException as exc:
                return f"An error occurred while renewing certificate: {exc}"
        return ""

    def revoke_certificate(self, resource_id: str) -> str:
        with self._db_session() as session:
            if self.readonly:
                return "The database is read-only, the changes will not be saved"
            certificate = session.get(Certificates, resource_id)
            if certificate is None:
                return "Certificate not found"
            if certificate.source == "letsencrypt":
                return "ACME certificate revocation must be performed by the certificate worker"
            now = datetime.now(timezone.utc)
            certificate.revoked = True
            certificate.revoked_at = now
            certificate.resource.last_update = now
            try:
                session.commit()
            except BaseException as exc:
                return f"An error occurred while revoking certificate: {exc}"
        return ""
