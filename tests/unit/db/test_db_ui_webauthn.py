"""Base DatabaseUIUsersMixin — WebAuthn credential storage.

Exercised through the plain `db` fixture (engine matrix), the same path the API
`/users/*/webauthn-credentials` router takes. Only public credential material is stored here;
the ceremonies themselves live in the UI (tests/unit/ui/test_webauthn.py).
"""

from datetime import datetime, timezone

DT = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _add_credential(db, username, credential_id, **kwargs):
    kwargs.setdefault("user_handle", "HANDLE")
    kwargs.setdefault("public_key", "PUBKEY")
    kwargs.setdefault("name", credential_id)
    kwargs.setdefault("creation_date", DT)
    return db.create_ui_user_webauthn_credential(username, credential_id=credential_id, **kwargs)


class TestCreate:
    def test_create_and_list(self, db):
        db.create_ui_user("alice", b"h", [])
        assert _add_credential(db, "alice", "cred-1", name="YubiKey", transports=["usb", "nfc"], device_type="single_device") == ""

        credentials = db.get_ui_user_webauthn_credentials("alice", as_dict=True)
        assert len(credentials) == 1
        assert credentials[0]["credential_id"] == "cred-1"
        assert credentials[0]["name"] == "YubiKey"
        assert credentials[0]["username"] == "alice"
        assert credentials[0]["sign_count"] == 0
        assert credentials[0]["last_used"] is None
        # transports round-trip as a list even though they are stored comma-joined
        assert credentials[0]["transports"] == ["usb", "nfc"]

    def test_transports_default_to_empty_list(self, db):
        db.create_ui_user("alice", b"h", [])
        _add_credential(db, "alice", "cred-1")
        assert db.get_ui_user_webauthn_credentials("alice", as_dict=True)[0]["transports"] == []

    def test_unknown_user_rejected(self, db):
        assert _add_credential(db, "ghost", "cred-1") == "User ghost doesn't exist"

    def test_duplicate_credential_rejected(self, db):
        db.create_ui_user("alice", b"h", [])
        _add_credential(db, "alice", "cred-1")
        assert _add_credential(db, "alice", "cred-1") == "This credential already exists"

    def test_credential_id_is_globally_unique(self, db):
        """The same authenticator credential must not be claimable by a second account."""
        db.create_ui_user("alice", b"h", [])
        db.create_ui_user("bob", b"h", [])
        _add_credential(db, "alice", "cred-1")
        assert _add_credential(db, "bob", "cred-1") == "This credential already exists"

    def test_list_is_empty_for_user_without_credentials(self, db):
        db.create_ui_user("alice", b"h", [])
        assert db.get_ui_user_webauthn_credentials("alice", as_dict=True) == []


class TestUserHandle:
    def test_no_handle_before_first_credential(self, db):
        db.create_ui_user("alice", b"h", [])
        assert db.get_ui_user_webauthn_handle("alice") is None

    def test_handle_is_reused_across_credentials(self, db):
        """Authenticators dedupe accounts by user handle, so a user's keys must share one."""
        db.create_ui_user("alice", b"h", [])
        _add_credential(db, "alice", "cred-1", user_handle="H-ALICE")
        _add_credential(db, "alice", "cred-2", user_handle="H-ALICE")
        assert db.get_ui_user_webauthn_handle("alice") == "H-ALICE"
        assert {c["user_handle"] for c in db.get_ui_user_webauthn_credentials("alice", as_dict=True)} == {"H-ALICE"}

    def test_handle_is_per_user(self, db):
        db.create_ui_user("alice", b"h", [])
        db.create_ui_user("bob", b"h", [])
        _add_credential(db, "alice", "cred-1", user_handle="H-ALICE")
        _add_credential(db, "bob", "cred-2", user_handle="H-BOB")
        assert db.get_ui_user_webauthn_handle("bob") == "H-BOB"


class TestResolve:
    def test_resolve_returns_owner(self, db):
        """Passwordless login has only a credential ID to go on."""
        db.create_ui_user("alice", b"h", [])
        _add_credential(db, "alice", "cred-1", public_key="PK", user_handle="H")

        resolved = db.get_ui_user_webauthn_credential("cred-1", as_dict=True)
        assert resolved["username"] == "alice"
        assert resolved["public_key"] == "PK"
        assert resolved["user_handle"] == "H"

    def test_resolve_unknown_returns_none(self, db):
        assert db.get_ui_user_webauthn_credential("nope") is None


class TestUpdate:
    def test_update_sign_count_and_last_used(self, db):
        db.create_ui_user("alice", b"h", [])
        _add_credential(db, "alice", "cred-1")

        used_at = datetime(2024, 6, 1, tzinfo=timezone.utc)
        assert db.update_ui_user_webauthn_credential("cred-1", sign_count=42, last_used=used_at) == ""

        credential = db.get_ui_user_webauthn_credential("cred-1", as_dict=True)
        assert credential["sign_count"] == 42
        assert credential["last_used"] is not None

    def test_rename(self, db):
        db.create_ui_user("alice", b"h", [])
        _add_credential(db, "alice", "cred-1", name="Old")
        assert db.update_ui_user_webauthn_credential("cred-1", name="New") == ""
        assert db.get_ui_user_webauthn_credential("cred-1", as_dict=True)["name"] == "New"

    def test_partial_update_leaves_other_fields(self, db):
        db.create_ui_user("alice", b"h", [])
        _add_credential(db, "alice", "cred-1", name="Keep", sign_count=7)
        db.update_ui_user_webauthn_credential("cred-1", sign_count=8)
        credential = db.get_ui_user_webauthn_credential("cred-1", as_dict=True)
        assert credential["name"] == "Keep"
        assert credential["sign_count"] == 8

    def test_update_missing_credential(self, db):
        assert db.update_ui_user_webauthn_credential("nope", sign_count=1) == "Credential not found"


class TestDelete:
    def test_delete(self, db):
        db.create_ui_user("alice", b"h", [])
        _add_credential(db, "alice", "cred-1")
        assert db.delete_ui_user_webauthn_credential("alice", "cred-1") == ""
        assert db.get_ui_user_webauthn_credentials("alice") == []

    def test_delete_is_scoped_to_the_owner(self, db):
        """A user must not be able to remove someone else's credential."""
        db.create_ui_user("alice", b"h", [])
        db.create_ui_user("bob", b"h", [])
        _add_credential(db, "alice", "cred-1")

        assert db.delete_ui_user_webauthn_credential("bob", "cred-1") == "Credential not found"
        assert len(db.get_ui_user_webauthn_credentials("alice")) == 1

    def test_delete_missing_credential(self, db):
        db.create_ui_user("alice", b"h", [])
        assert db.delete_ui_user_webauthn_credential("alice", "nope") == "Credential not found"


class TestUserLinkage:
    def test_credentials_follow_a_username_rename(self, db):
        """The FK cascades on update; the user handle is what stays stable for authenticators."""
        db.create_ui_user("alice", b"h", [])
        _add_credential(db, "alice", "cred-1", user_handle="H-ALICE")

        assert db.update_ui_user("alicia", b"h", None, old_username="alice") == ""

        assert db.get_ui_user_webauthn_credential("cred-1", as_dict=True)["username"] == "alicia"
        assert len(db.get_ui_user_webauthn_credentials("alicia")) == 1
        assert db.get_ui_user_webauthn_handle("alicia") == "H-ALICE"

    def test_user_payload_carries_the_credential_count(self, db):
        """The UI's second-factor gate reads this instead of paying for a second round trip."""
        db.create_ui_user("alice", b"h", [])
        assert db.get_ui_user(username="alice", as_dict=True)["webauthn_credentials_count"] == 0

        _add_credential(db, "alice", "cred-1")
        _add_credential(db, "alice", "cred-2")
        assert db.get_ui_user(username="alice", as_dict=True)["webauthn_credentials_count"] == 2
