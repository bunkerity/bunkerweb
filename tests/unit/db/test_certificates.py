from base64 import b64encode
from io import BytesIO
from tarfile import REGTYPE, SYMTYPE, TarInfo, open as tar_open

from certificate_utils import generate_self_signed  # type: ignore
from fixtures.seed import add_service, seed_minimal, session
from model import Certificates, Jobs  # type: ignore


def _configure_keyring(monkeypatch):
    monkeypatch.setenv("CERTIFICATE_ENCRYPTION_KEYS", '{"v1":"' + b64encode(b"k" * 32).decode() + '"}')
    monkeypatch.setenv("CERTIFICATE_ENCRYPTION_ACTIVE_KEY", "v1")


def _create(db, monkeypatch, *, name="example", service_ids=None, source="selfsigned", renewal_metadata=None):
    _configure_keyring(monkeypatch)
    certificate, private_key = generate_self_signed(f"{name}.example.com", [])
    error, resource_id = db.create_certificate(
        name=name,
        source=source,
        certificate_pem=certificate,
        private_key_pem=private_key,
        service_ids=service_ids or [],
        renewal_metadata=renewal_metadata,
    )
    assert error == ""
    return resource_id, certificate, private_key


def _certbot_tar(certificate, private_key, name="app1.example.com"):
    output = BytesIO()
    with tar_open(fileobj=output, mode="w:gz") as archive:
        for path, data in (
            (f"archive/{name}/fullchain1.pem", certificate),
            (f"archive/{name}/privkey1.pem", private_key),
            (f"renewal/{name}.conf", b"[renewalparams]\nserver = letsencrypt\nauthenticator = webroot\n"),
        ):
            member = TarInfo(path)
            member.type = REGTYPE
            member.size = len(data)
            archive.addfile(member, BytesIO(data))
        for filename in ("fullchain", "privkey"):
            member = TarInfo(f"live/{name}/{filename}.pem")
            member.type = SYMTYPE
            member.linkname = f"../../archive/{name}/{filename}1.pem"
            archive.addfile(member)
    return output.getvalue()


def test_create_list_download_and_secret_redaction(db, monkeypatch):
    resource_id, certificate, _ = _create(db, monkeypatch)
    listing = db.get_certificates()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert item["id"] == resource_id
    assert item["common_name"] == "example.example.com"
    assert not any("private" in key for key in item)
    assert db.get_certificate_public_data(resource_id, "leaf") == certificate


def test_duplicate_fingerprint_reports_the_current_provider_owner(db, monkeypatch):
    _, certificate, private_key = _create(db, monkeypatch, source="customcert")

    error, resource_id = db.create_certificate(
        name="duplicate",
        source="selfsigned",
        certificate_pem=certificate,
        private_key_pem=private_key,
    )

    assert error == "Certificate fingerprint is already owned by customcert"
    assert resource_id is None


def test_assignment_enforces_one_primary_and_blocks_delete(db, monkeypatch):
    seed_minimal(db)
    first, _, _ = _create(db, monkeypatch, name="first", service_ids=["app1.example.com"])
    second, _, _ = _create(db, monkeypatch, name="second")
    assert db.attach_certificate(second, "app1.example.com", primary=True) == ""
    first_details = db.get_certificate_details(first)
    second_details = db.get_certificate_details(second)
    assert first_details["attachments"][0]["is_primary"] is False
    assert second_details["attachments"][0]["is_primary"] is True
    assert db.delete_certificate(second) == "Certificate is attached to a service"
    assert db.detach_certificate(second, "app1.example.com") == ""
    assert db.delete_certificate(second) == ""


def test_create_enforces_one_primary_per_service(db, monkeypatch):
    seed_minimal(db)
    first, _, _ = _create(db, monkeypatch, name="first", service_ids=["app1.example.com"])
    second, _, _ = _create(db, monkeypatch, name="second", service_ids=["app1.example.com"])
    attachments = db.get_certificate_details(first)["attachments"] + db.get_certificate_details(second)["attachments"]
    assert sum(attachment["is_primary"] for attachment in attachments) == 1


def test_renew_selfsigned_and_revoke(db, monkeypatch):
    resource_id, _, _ = _create(db, monkeypatch)
    old_fingerprint = db.get_certificate_details(resource_id)["fingerprint"]
    assert db.renew_self_signed_certificate(resource_id) == ""
    renewed = db.get_certificate_details(resource_id)
    assert renewed["fingerprint"] != old_fingerprint
    assert renewed["last_renewal"] is not None
    assert db.revoke_certificate(resource_id) == ""
    assert db.get_certificate_details(resource_id)["status"] == "revoked"


def test_renew_tampered_ciphertext_fails_closed(db, monkeypatch):
    resource_id, _, _ = _create(db, monkeypatch)
    with session(db) as db_session:
        certificate = db_session.get(Certificates, resource_id)
        certificate.private_key_ciphertext = b"tampered"
    assert db.renew_self_signed_certificate(resource_id) == "InvalidTag"
    assert db.get_certificate_details(resource_id)["last_error"] == "InvalidTag"


def test_legacy_import_is_idempotent_by_fingerprint(db, monkeypatch):
    _configure_keyring(monkeypatch)
    certificate, private_key = generate_self_signed("legacy.example.com", [])
    args = {
        "name": "legacy",
        "source": "letsencrypt",
        "certificate_pem": certificate,
        "private_key_pem": private_key,
    }
    first_error, first_id = db.import_certificate(**args)
    second_error, second_id = db.import_certificate(**(args | {"name": "legacy-copy"}))
    assert first_error == second_error == ""
    assert first_id == second_id


def test_same_provider_import_does_not_rewrite_material_or_renewal_time(db, monkeypatch):
    _configure_keyring(monkeypatch)
    certificate, private_key = generate_self_signed("stable.example.com", [])
    args = {
        "name": "stable",
        "source": "letsencrypt",
        "certificate_pem": certificate,
        "private_key_pem": private_key,
        "renewal_metadata": {"cert_name": "stable"},
    }
    first_error, resource_id = db.import_certificate(**args)
    assert first_error == ""
    with session(db) as db_session:
        stored = db_session.get(Certificates, resource_id)
        original_ciphertext = stored.private_key_ciphertext
        original_nonce = stored.private_key_nonce
        original_last_renewal = stored.last_renewal

    second_error, second_id = db.import_certificate(**args)

    assert second_error == ""
    assert second_id == resource_id
    with session(db) as db_session:
        stored = db_session.get(Certificates, resource_id)
        assert stored.private_key_ciphertext == original_ciphertext
        assert stored.private_key_nonce == original_nonce
        assert stored.last_renewal == original_last_renewal


def test_legacy_import_rejects_matching_certificate_owned_by_another_provider(db, monkeypatch):
    custom_id, certificate, private_key = _create(db, monkeypatch, name="uploaded", source="customcert")

    error, imported_id = db.import_certificate(
        name="managed.example.com",
        source="letsencrypt",
        certificate_pem=certificate,
        private_key_pem=private_key,
        renewal_metadata={},
    )

    assert "fingerprint is already owned by customcert" in error
    assert imported_id is None
    uploaded = db.get_certificate_details(custom_id)
    assert uploaded["source"] == "customcert"
    assert uploaded["renewal_metadata"] == {}
    assert db.delete_certificate(custom_id) == ""


def test_legacy_import_collision_leaves_existing_rows_and_attachments_unchanged(db, monkeypatch):
    seed_minimal(db)
    stale_id, _, _ = _create(
        db,
        monkeypatch,
        name="managed",
        source="letsencrypt",
        service_ids=["app1.example.com"],
        renewal_metadata={"cert_name": "managed", "managed_by": "letsencrypt"},
    )
    uploaded_id, certificate, private_key = _create(db, monkeypatch, name="uploaded", source="customcert")

    error, imported_id = db.import_certificate(
        name="managed",
        source="letsencrypt",
        certificate_pem=certificate,
        private_key_pem=private_key,
        renewal_metadata={},
    )

    assert "fingerprint is already owned by customcert" in error
    assert imported_id is None
    stale = db.get_certificate_details(stale_id)
    assert stale["source"] == "letsencrypt"
    assert stale["attachments"] == [{"service_id": "app1.example.com", "is_primary": True}]
    assert db.get_certificate_details(uploaded_id)["source"] == "customcert"
    assert db.get_certificates()["total"] == 2


def test_provider_metadata_cannot_bypass_or_poison_managed_deletion(db, monkeypatch):
    managed_id, _, _ = _create(
        db,
        monkeypatch,
        name="managed",
        source="letsencrypt",
        renewal_metadata={"cert_name": "managed.example.com", "managed_by": "letsencrypt"},
    )
    assert (
        db.update_certificate(
            managed_id,
            renewal_metadata={"cert_name": "victim.example.com", "managed_by": "caller", "note": "kept"},
        )
        == ""
    )
    managed = db.get_certificate_details(managed_id)
    assert managed["renewal_metadata"] == {
        "cert_name": "managed.example.com",
        "managed_by": "letsencrypt",
        "note": "kept",
    }
    assert "Managed certificates cannot be deleted" in db.delete_certificate(managed_id)

    custom_id, _, _ = _create(db, monkeypatch, name="custom", source="customcert")
    assert db.update_certificate(custom_id, renewal_metadata={"managed_by": "letsencrypt", "note": "kept"}) == ""
    custom = db.get_certificate_details(custom_id)
    assert custom["renewal_metadata"] == {"note": "kept"}
    assert db.delete_certificate(custom_id) == ""


def test_import_refresh_respects_readonly_database(db, monkeypatch):
    resource_id, _, _ = _create(db, monkeypatch, name="legacy", source="letsencrypt")
    original_fingerprint = db.get_certificate_details(resource_id)["fingerprint"]
    renewed_certificate, renewed_key = generate_self_signed("legacy.example.com", [])
    db.readonly = True
    try:
        error, imported_id = db.import_certificate(
            name="legacy",
            source="letsencrypt",
            certificate_pem=renewed_certificate,
            private_key_pem=renewed_key,
        )
    finally:
        db.readonly = False

    assert "read-only" in error
    assert imported_id is None
    assert db.get_certificate_details(resource_id)["fingerprint"] == original_fingerprint


def test_legacy_import_is_noop_in_readonly_database(db):
    db.readonly = True
    try:
        summary = db.import_legacy_certbot_certificates()
    finally:
        db.readonly = False
    assert summary == {"imported": 0, "unchanged": 0, "errors": []}


def test_unknown_service_rejected_without_partial_row(db, monkeypatch):
    resource_id, certificate, private_key = _create(db, monkeypatch, name="unattached")
    assert db.delete_certificate(resource_id) == ""
    error, created = db.create_certificate(
        name="bad",
        source="customcert",
        certificate_pem=certificate,
        private_key_pem=private_key,
        service_ids=["missing.example.com"],
    )
    assert "Unknown service" in error
    assert created is None
    assert db.get_certificates()["total"] == 0


def test_primary_is_scoped_per_service(db, monkeypatch):
    seed_minimal(db)
    add_service(db, "second.example.com")
    resource_id, _, _ = _create(db, monkeypatch, service_ids=["app1.example.com", "second.example.com"])
    assert {item["service_id"] for item in db.get_certificate_details(resource_id)["attachments"]} == {
        "app1.example.com",
        "second.example.com",
    }


def test_legacy_certbot_cache_import_and_refresh(db, monkeypatch):
    _configure_keyring(monkeypatch)
    seed_minimal(db)
    with session(db) as db_session:
        db_session.add(Jobs(name="certbot-renew", plugin_id="general", file_name="certbot-renew.py", every="day"))
    certificate, private_key = generate_self_signed("app1.example.com", [])
    cache_name = "folder:/var/cache/bunkerweb/letsencrypt/etc/letsencrypt.tgz"
    assert db.upsert_job_cache(None, cache_name, _certbot_tar(certificate, private_key), job_name="certbot-renew", checksum="v1") == ""

    first = db.import_legacy_certbot_certificates()
    assert first == {"imported": 1, "unchanged": 0, "errors": []}
    item = db.get_certificates()["items"][0]
    resource_id = item["id"]
    assert item["source"] == "letsencrypt"
    assert item["attachments"] == [{"service_id": "app1.example.com", "is_primary": True}]
    assert db.import_legacy_certbot_certificates()["unchanged"] == 1

    renewed_certificate, renewed_key = generate_self_signed("app1.example.com", [])
    assert db.upsert_job_cache(None, cache_name, _certbot_tar(renewed_certificate, renewed_key), job_name="certbot-renew", checksum="v2") == ""
    refreshed = db.import_legacy_certbot_certificates()
    assert refreshed["imported"] == 1
    assert db.get_certificates()["items"][0]["id"] == resource_id
    assert db.detach_certificate(resource_id, "app1.example.com") == ""
    assert "Managed certificates cannot be deleted" in db.delete_certificate(resource_id)


def test_legacy_import_reads_new_issuance_cache(db, monkeypatch):
    _configure_keyring(monkeypatch)
    seed_minimal(db)
    with session(db) as db_session:
        db_session.add(Jobs(name="certbot-new", plugin_id="general", file_name="certbot-new.py", every="minute"))
    certificate, private_key = generate_self_signed("app1.example.com", [])
    cache_name = "folder:/var/cache/bunkerweb/letsencrypt/etc/letsencrypt.tgz"
    assert db.upsert_job_cache(None, cache_name, _certbot_tar(certificate, private_key), job_name="certbot-new", checksum="new-v1") == ""

    summary = db.import_legacy_certbot_certificates()

    assert summary == {"imported": 1, "unchanged": 0, "errors": []}
    assert db.get_certificates()["items"][0]["attachments"] == [{"service_id": "app1.example.com", "is_primary": True}]
