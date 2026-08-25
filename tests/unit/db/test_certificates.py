from base64 import b64decode, b64encode
from datetime import datetime, timedelta, timezone
from io import BytesIO
from json import loads
from tarfile import REGTYPE, SYMTYPE, TarInfo, open as tar_open

import pytest

from certificate_utils import generate_self_signed  # type: ignore
from fixtures.seed import add_service, seed_minimal, session
from model import Certificates, Jobs, Metadata, ResourceAttachments  # type: ignore


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


def test_renew_works_without_an_environment_keyring(db, monkeypatch):
    """A stock install has no CERTIFICATE_ENCRYPTION_* env, so the keyring comes from the
    metadata row -- and reading it opens a database session. `_db_session` is not reentrant
    (its `finally` calls `session.remove()`), so resolving the keyring from inside the renewal
    session used to close that session and the next attribute load raised DetachedInstanceError.
    Every other test here configures the env keyring, which is why none of them caught it."""
    monkeypatch.delenv("CERTIFICATE_ENCRYPTION_KEYS", raising=False)
    monkeypatch.delenv("CERTIFICATE_ENCRYPTION_ACTIVE_KEY", raising=False)
    seed_minimal(db)  # the fallback keyring lives in the Metadata row, so one has to exist
    certificate, private_key = generate_self_signed("db-keyring.example.com", [])
    error, resource_id = db.create_certificate(
        name="db-keyring",
        source="selfsigned",
        certificate_pem=certificate,
        private_key_pem=private_key,
        service_ids=[],
    )
    assert error == ""
    # The worker recycles its process after every job, so the renewal is the first thing to
    # touch the keyring in a fresh process -- with the cache warm, nothing nests and the bug
    # hides. deploy-certificates renews before it deploys, which is exactly this order.
    db._db_keyring = None
    assert db.renew_self_signed_certificate(resource_id) == ""


def test_a_short_lived_certificate_is_not_due_the_moment_it_exists(db, monkeypatch):
    """`next_renewal` used to be a flat 30 days before expiry, so anything living 30 days or
    less was due at issuance: deploy-certificates renewed it on every run, re-issuing material
    and pushing it to the whole fleet each time (SELF_SIGNED_SSL_EXPIRY=30 does exactly that)."""
    _configure_keyring(monkeypatch)
    certificate, private_key = generate_self_signed("short.example.com", [], valid_days=30)
    error, resource_id = db.create_certificate(
        name="short",
        source="selfsigned",
        certificate_pem=certificate,
        private_key_pem=private_key,
        service_ids=[],
    )
    assert error == ""
    assert resource_id not in db.get_self_signed_certificates_due_for_renewal()

    details = db.get_certificate_details(resource_id)
    valid_from = datetime.fromisoformat(details["valid_from"])
    next_renewal = datetime.fromisoformat(details["next_renewal"])
    valid_to = datetime.fromisoformat(details["valid_to"])
    assert valid_from < next_renewal < valid_to


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


def _generated_keyring(db):
    """The keyring row as persisted by the metadata-backed fallback."""
    with session(db) as db_session:
        row = db_session.get(Metadata, 1)
        return row.certificate_keyring, row.certificate_keyring_active


def test_keyring_environment_wins_over_database(db, monkeypatch):
    """An operator-provided keyring must keep the key material out of the database."""
    db.initialize_db("1.7.0", "Docker")
    _configure_keyring(monkeypatch)

    values = db._keyring_values()

    assert values["CERTIFICATE_ENCRYPTION_ACTIVE_KEY"] == "v1"
    assert _generated_keyring(db) == (None, None)


def test_keyring_generated_on_demand_and_reused(db, monkeypatch):
    """Without an environment keyring, one is generated once and then reused."""
    db.initialize_db("1.7.0", "Docker")
    monkeypatch.delenv("CERTIFICATE_ENCRYPTION_KEYS", raising=False)
    monkeypatch.delenv("CERTIFICATE_ENCRYPTION_ACTIVE_KEY", raising=False)

    values = db._keyring_values()
    stored, active = _generated_keyring(db)

    assert active == "db-v1"
    assert len(b64decode(loads(stored)["db-v1"], validate=True)) == 32
    # Cached, and a fresh Database over the same schema adopts the stored key rather
    # than minting a second one.
    assert db._keyring_values() is values
    db._db_keyring = None
    assert db._keyring_values() == values


def test_certificate_roundtrips_on_generated_keyring(db, monkeypatch):
    """A certificate written under the generated keyring stays decryptable."""
    db.initialize_db("1.7.0", "Docker")
    monkeypatch.delenv("CERTIFICATE_ENCRYPTION_KEYS", raising=False)
    monkeypatch.delenv("CERTIFICATE_ENCRYPTION_ACTIVE_KEY", raising=False)

    certificate, private_key = generate_self_signed("gen.example.com", [])
    error, resource_id = db.create_certificate(name="gen", source="selfsigned", certificate_pem=certificate, private_key_pem=private_key)

    assert error == ""
    # renew decrypts the stored private key, so a successful renewal proves the round trip.
    assert db.renew_self_signed_certificate(resource_id, valid_days=30) == ""


def test_keyring_unavailable_fails_closed(db, monkeypatch):
    """No environment keyring and no metadata row must refuse the write, not store plaintext."""
    monkeypatch.delenv("CERTIFICATE_ENCRYPTION_KEYS", raising=False)
    monkeypatch.delenv("CERTIFICATE_ENCRYPTION_ACTIVE_KEY", raising=False)

    certificate, private_key = generate_self_signed("nokey.example.com", [])
    error, resource_id = db.create_certificate(name="nokey", source="selfsigned", certificate_pem=certificate, private_key_pem=private_key)

    assert resource_id is None
    assert "must both be configured" in error


def test_set_metadata_cannot_overwrite_the_keyring(db, monkeypatch):
    """PATCH /metadata must not be able to destroy or plant the encryption key."""
    db.initialize_db("1.7.0", "Docker")
    monkeypatch.delenv("CERTIFICATE_ENCRYPTION_KEYS", raising=False)
    monkeypatch.delenv("CERTIFICATE_ENCRYPTION_ACTIVE_KEY", raising=False)
    db._keyring_values()
    stored, active = _generated_keyring(db)

    assert db.set_metadata({"certificate_keyring": '{"evil":"' + b64encode(b"e" * 32).decode() + '"}', "certificate_keyring_active": "evil"}) == ""

    assert _generated_keyring(db) == (stored, active)


def test_certificate_sources_registry(db, monkeypatch):
    """Built-in sources are always accepted; unknown ones are refused."""
    assert set(db.certificate_sources()) >= {"letsencrypt", "customcert", "selfsigned"}

    certificate, private_key = generate_self_signed("nope.example.com", [])
    _configure_keyring(monkeypatch)
    error, resource_id = db.create_certificate(name="nope", source="vault", certificate_pem=certificate, private_key_pem=private_key)

    assert resource_id is None
    assert error == "Invalid certificate source: vault"


def test_plugin_declared_source_accepted(db, monkeypatch):
    """A plugin declaring extensions.certificate_source can own inventory rows."""
    import db_methods.certificates as certificates_module

    monkeypatch.setattr(certificates_module, "iter_certificate_sources", lambda: {"vault": {"label": "Vault", "renews": True}})
    _configure_keyring(monkeypatch)
    certificate, private_key = generate_self_signed("vault.example.com", [])

    error, resource_id = db.create_certificate(name="vault", source="vault", certificate_pem=certificate, private_key_pem=private_key)

    assert error == ""
    assert db.get_certificate_details(resource_id)["source"] == "vault"


def test_deployable_resolution_prefers_primary_and_skips_revoked(db, monkeypatch):
    """Only the winning attachment of each service is deployed, and never a revoked one."""
    seed_minimal(db)
    first, _, _ = _create(db, monkeypatch, name="first", service_ids=["app1.example.com"])
    second, _, _ = _create(db, monkeypatch, name="second")
    assert db.attach_certificate(second, "app1.example.com", primary=True) == ""

    deployable = db.get_deployable_certificates()

    assert set(deployable) == {"app1.example.com"}
    assert deployable["app1.example.com"]["resource_id"] == second
    assert deployable["app1.example.com"]["private_key_pem"].startswith(b"-----BEGIN PRIVATE KEY-----")

    # Revoking the primary falls back to the other attachment rather than serving it.
    assert db.revoke_certificate(second) == ""
    assert db.get_deployable_certificates()["app1.example.com"]["resource_id"] == first


def test_deployable_resolution_uses_latest_attachment_id_when_timestamps_tie(db, monkeypatch):
    seed_minimal(db)
    first, _, _ = _create(db, monkeypatch, name="first", service_ids=["app1.example.com"])
    second, _, _ = _create(db, monkeypatch, name="second")
    assert db.attach_certificate(second, "app1.example.com") == ""
    with session(db) as db_session:
        attachments = db_session.query(ResourceAttachments).filter_by(service_id="app1.example.com").order_by(ResourceAttachments.id).all()
        for attachment in attachments:
            attachment.is_primary = False
            attachment.creation_date = attachments[0].creation_date

    assert db.get_deployable_certificates()["app1.example.com"]["resource_id"] == second


def test_deployable_skips_undecryptable_and_records_the_error(db, monkeypatch):
    """One unreadable private key must not block the other services."""
    seed_minimal(db)
    add_service(db, "app2.example.com")
    broken, _, _ = _create(db, monkeypatch, name="broken", service_ids=["app1.example.com"])
    healthy, _, _ = _create(db, monkeypatch, name="healthy", service_ids=["app2.example.com"])
    with session(db) as db_session:
        db_session.get(Certificates, broken).private_key_ciphertext = b"tampered"

    deployable = db.get_deployable_certificates()

    assert set(deployable) == {"app2.example.com"}
    assert deployable["app2.example.com"]["resource_id"] == healthy
    assert db.get_certificate_details(broken)["last_error"] == "InvalidTag"


def test_attachment_changes_flag_the_scheduler(db, monkeypatch):
    """The scheduler only redeploys when it is told material changed."""
    db.initialize_db("1.7.0", "Docker")
    seed_minimal(db)
    assert db.get_metadata()["certificates_changed"] is False

    resource_id, _, _ = _create(db, monkeypatch, name="flagged")
    assert db.checked_changes(["certificates"], value=False) == ""
    assert db.get_metadata()["certificates_changed"] is False

    assert db.attach_certificate(resource_id, "app1.example.com", primary=True) == ""
    assert db.get_metadata()["certificates_changed"] is True

    assert db.checked_changes(["certificates"], value=False) == ""
    assert db.detach_certificate(resource_id, "app1.example.com") == ""
    assert db.get_metadata()["certificates_changed"] is True


def test_sync_managed_attachments_detaches_withdrawn_services(db, monkeypatch):
    """A provider that stops covering a service must stop serving it."""
    seed_minimal(db)
    add_service(db, "app2.example.com")
    managed = {"managed_by": "customcert"}
    kept, _, _ = _create(db, monkeypatch, name="kept", source="customcert", service_ids=["app1.example.com"], renewal_metadata=managed)
    dropped, _, _ = _create(db, monkeypatch, name="dropped", source="customcert", service_ids=["app2.example.com"], renewal_metadata=managed)
    other, _, _ = _create(db, monkeypatch, name="other", source="selfsigned", service_ids=["app2.example.com"], renewal_metadata={"managed_by": "selfsigned"})

    assert db.sync_managed_attachments("customcert", ["app1.example.com"]) == ""

    assert db.get_certificate_details(kept)["attachments"] == [{"service_id": "app1.example.com", "is_primary": True}]
    assert db.get_certificate_details(dropped)["attachments"] == []
    # Another source's attachments are untouched.
    assert db.get_certificate_details(other)["attachments"] == [{"service_id": "app2.example.com", "is_primary": True}]


def test_self_signed_renewal_is_due_only_after_next_renewal(db, monkeypatch):
    resource_id, _, _ = _create(db, monkeypatch, name="renewable")
    assert db.get_self_signed_certificates_due_for_renewal() == []

    with session(db) as db_session:
        db_session.get(Certificates, resource_id).next_renewal = datetime.now(timezone.utc) - timedelta(days=1)

    assert db.get_self_signed_certificates_due_for_renewal() == [resource_id]

    # A different source is never renewed locally, even when overdue.
    uploaded, _, _ = _create(db, monkeypatch, name="uploaded", source="customcert")
    with session(db) as db_session:
        db_session.get(Certificates, uploaded).next_renewal = datetime.now(timezone.utc) - timedelta(days=1)
    assert db.get_self_signed_certificates_due_for_renewal() == [resource_id]


def test_sync_leaves_manually_assigned_certificates_alone(db, monkeypatch):
    """A provider run must not detach a certificate the operator uploaded and assigned itself.

    A hand-uploaded certificate carries source="customcert" like the provider's own entries;
    only the managed_by marker separates them, and matching on the source alone silently wiped
    the operator's assignment on the next run of the custom-cert job.
    """
    seed_minimal(db)
    add_service(db, "app2.example.com")
    managed, _, _ = _create(
        db, monkeypatch, name="provider", source="customcert", service_ids=["app2.example.com"], renewal_metadata={"managed_by": "customcert"}
    )
    manual, _, _ = _create(db, monkeypatch, name="uploaded", source="customcert", service_ids=["app1.example.com"])

    # The provider no longer covers anything.
    assert db.sync_managed_attachments("customcert", []) == ""

    assert db.get_certificate_details(managed)["attachments"] == []
    assert db.get_certificate_details(manual)["attachments"] == [{"service_id": "app1.example.com", "is_primary": True}]


# --- provider swap must not wedge the inventory ---------------------------------------------
# Both provider jobs name their inventory entry after the service (`name=first_server`), so every
# selfsigned <-> customcert swap lands on the same `bw_resources.name`. `create_certificate`'s name
# check was source-BLIND while `import_certificate`'s lookup was source-SCOPED, and
# `sync_managed_attachments` only ever deletes ResourceAttachments rows -- so the withdrawn
# provider's Resources row survived forever and the new provider's job errored on every single run.


def _import(db, monkeypatch, *, source, name, service_ids=None, sans=None, managed=True):
    _configure_keyring(monkeypatch)
    certificate, private_key = generate_self_signed(f"{name}", sans or [])
    return (
        db.import_certificate(
            name=name,
            description=f"Managed by the {source} provider",
            source=source,
            certificate_pem=certificate,
            private_key_pem=private_key,
            service_ids=service_ids or [],
            primary=True,
            renewal_metadata={"managed_by": source} if managed else {},
        ),
        certificate,
    )


@pytest.mark.parametrize("first,second", [("selfsigned", "customcert"), ("customcert", "selfsigned")])
def test_a_provider_swap_takes_the_managed_inventory_row_over(db, monkeypatch, first, second):
    seed_minimal(db)
    service = "app1.example.com"

    (first_error, first_id), _ = _import(db, monkeypatch, source=first, name=service, service_ids=[service])
    assert first_error == ""
    # The withdrawn provider's job stops covering the service and detaches it. It does NOT (and
    # must not) delete the inventory row -- that is exactly the row the swap used to trip over.
    assert db.sync_managed_attachments(first, []) == ""

    (second_error, second_id), second_certificate = _import(db, monkeypatch, source=second, name=service, service_ids=[service], sans=[f"extra.{service}"])

    assert second_error == "", "the swap must not wedge the inventory"
    assert second_id == first_id, "the row is taken over, not duplicated"
    details = db.get_certificate_details(second_id)
    assert details["source"] == second, "ownership must move to the new provider"
    assert details["renewal_metadata"]["managed_by"] == second
    assert f"extra.{service}" in details["sans"], "the new provider's material must win"
    assert details["attachments"] == [{"service_id": service, "is_primary": True}]
    assert db.get_certificates()["total"] == 1, "no orphan left behind"


def test_repeated_swaps_keep_working(db, monkeypatch):
    """The wedge was permanent, so one successful swap is not enough evidence.

    A *swap* means the outgoing provider is DISABLED -- its job keeps running and detaches the
    service (`sync_managed_attachments` sits outside the per-service gate in both jobs), which is
    the release signal the takeover waits for. Two providers running at once is a different
    situation entirely: see test_two_active_providers_do_not_flap_the_inventory_row.
    """
    seed_minimal(db)
    service = "app1.example.com"
    previous = None

    for index, source in enumerate(("selfsigned", "customcert", "selfsigned", "customcert")):
        if previous:
            # The outgoing provider no longer covers this service.
            assert db.sync_managed_attachments(previous, []) == ""
        (error, resource_id), _ = _import(db, monkeypatch, source=source, name=service, service_ids=[service], sans=[f"r{index}.{service}"])
        assert error == "", f"swap {index} to {source} failed: {error}"
        assert db.get_certificate_details(resource_id)["source"] == source
        previous = source
    assert db.get_certificates()["total"] == 1


def test_two_active_providers_do_not_flap_the_inventory_row(db, monkeypatch):
    """Nothing forbids GENERATE_SELF_SIGNED_SSL=yes AND USE_CUSTOM_SSL=yes on one service: each job
    gates only on its own setting, both run daily, and self-signed still calls import_certificate
    when generate_cert short-circuits on a still-valid cached certificate (it returns True, 0).

    An unbounded takeover turns that into a DAILY FLAP -- each run adopts the other's row, replaces
    the material and flags certificates_changed, and `certificates` is ahead of both providers in
    order.json's ssl_certificate phase, so the alternating leaf reaches the wire. Requiring a
    released row keeps this (already misconfigured) service stable: one provider owns the name, the
    other gets the ordinary "already exists" refusal every run, which is what it did before
    takeover existed.
    """
    seed_minimal(db)
    service = "app1.example.com"
    owners = []

    for day in range(3):
        for source in ("selfsigned", "customcert"):
            (error, resource_id), _ = _import(db, monkeypatch, source=source, name=service, service_ids=[service], sans=[f"{source}{day}.example.com"])
            if not error:
                owners.append(db.get_certificate_details(resource_id)["source"])

    assert set(owners) == {"selfsigned"}, f"the inventory row flaps between providers: {owners}"
    assert db.get_certificates()["total"] == 1
    details = db.get_certificates()["items"][0]
    assert details["source"] == "selfsigned"
    assert details["attachments"] == [{"service_id": service, "is_primary": True}]


def test_a_row_attached_to_other_services_is_never_consumed(db, monkeypatch):
    """A legacy letsencrypt row covering several services must not be swallowed by a
    single-service provider -- that would silently drop TLS for the services it does not name."""
    seed_minimal(db)
    add_service(db, "app2.example.com")
    (error, legacy_id), _ = _import(db, monkeypatch, source="letsencrypt", name="app1.example.com", service_ids=["app1.example.com", "app2.example.com"])
    assert error == ""

    (swap_error, swap_id), _ = _import(db, monkeypatch, source="selfsigned", name="app1.example.com", service_ids=["app1.example.com"], sans=["v2.example.com"])

    assert swap_error == "Certificate name app1.example.com already exists"
    assert swap_id is None
    unchanged = db.get_certificate_details(legacy_id)
    assert unchanged["source"] == "letsencrypt"
    assert {attachment["service_id"] for attachment in unchanged["attachments"]} == {"app1.example.com", "app2.example.com"}


def test_a_takeover_relabels_the_row_but_a_refresh_never_does(db, monkeypatch):
    """description is a provider-written label, so a takeover must rewrite it -- otherwise the row
    reads "Managed by the self-signed certificate provider" under source customcert. A same-source
    refresh must NOT: update_certificate lets an operator edit that field, and a daily job run
    would silently revert the edit."""
    seed_minimal(db)
    service = "app1.example.com"
    (error, resource_id), _ = _import(db, monkeypatch, source="selfsigned", name=service, service_ids=[service])
    assert error == ""
    assert db.sync_managed_attachments("selfsigned", []) == ""

    (error, taken_over_id), _ = _import(db, monkeypatch, source="customcert", name=service, service_ids=[service], sans=["v2.example.com"])

    assert error == ""
    assert taken_over_id == resource_id
    assert db.get_certificate_details(taken_over_id)["description"] == "Managed by the customcert provider"

    # Now an operator renames it, and the owning provider runs again.
    assert db.update_certificate(resource_id, description="Wildcard for the shop") == ""
    (error, refreshed_id), _ = _import(db, monkeypatch, source="customcert", name=service, service_ids=[service], sans=["v3.example.com"])

    assert error == ""
    assert refreshed_id == resource_id
    assert db.get_certificate_details(refreshed_id)["description"] == "Wildcard for the shop", "a same-source refresh must not revert an operator's edit"


def test_a_hand_uploaded_certificate_is_never_taken_over(db, monkeypatch):
    """An operator upload through /certificates carries `source="customcert"` with NO `managed_by`
    (same discriminator sync_managed_attachments uses). Overwriting it would be data loss, so the
    provider job must still get the explicit refusal."""
    seed_minimal(db)
    uploaded_id, _, _ = _create(db, monkeypatch, name="app1.example.com", source="customcert", renewal_metadata={})

    (error, imported_id), _ = _import(db, monkeypatch, source="selfsigned", name="app1.example.com", sans=["other.example.com"])

    assert error == "Certificate name app1.example.com already exists"
    assert imported_id is None
    unchanged = db.get_certificate_details(uploaded_id)
    assert unchanged["source"] == "customcert"
    assert unchanged["renewal_metadata"] == {}


def test_a_same_source_reimport_still_refreshes_in_place(db, monkeypatch):
    """The takeover widens the lookup; it must not change the ordinary same-provider path."""
    seed_minimal(db)
    (first_error, first_id), _ = _import(db, monkeypatch, source="selfsigned", name="app1.example.com", service_ids=["app1.example.com"])
    (second_error, second_id), _ = _import(
        db, monkeypatch, source="selfsigned", name="app1.example.com", service_ids=["app1.example.com"], sans=["v2.example.com"]
    )

    assert first_error == second_error == ""
    assert second_id == first_id
    assert db.get_certificate_details(second_id)["source"] == "selfsigned"
    assert db.get_certificates()["total"] == 1
