"""DatabaseInstancesMixin — BunkerWeb instance registry CRUD.

Runs against every selected engine via the ``db`` fixture. ``db_init`` seeds the
singleton Metadata row so the ``changed`` -> ``instances_changed`` paths are exercised.
"""

import base64
import json

import pytest


@pytest.fixture
def db_init(db):
    db.initialize_db("1.7.0", "Docker")
    return db


_TEST_KEY_ID = "test-key-1"
_TEST_KEYRING = json.dumps({_TEST_KEY_ID: base64.b64encode(b"\x00" * 32).decode()})


@pytest.fixture
def db_keyring(db_init, monkeypatch):
    """A ``db_init`` with a valid AES-256-GCM keyring configured for credential tests."""
    monkeypatch.setenv("CERTIFICATE_ENCRYPTION_KEYS", _TEST_KEYRING)
    monkeypatch.setenv("CERTIFICATE_ENCRYPTION_ACTIVE_KEY", _TEST_KEY_ID)
    return db_init


class TestAddInstance:
    def test_add_and_get(self, db_init):
        assert db_init.add_instance("bw-1", 5000, "bwapi", "manual") == ""
        inst = db_init.get_instance("bw-1")
        assert inst["hostname"] == "bw-1"
        assert inst["port"] == 5000
        assert inst["server_name"] == "bwapi"
        assert inst["method"] == "manual"
        assert inst["listen_https"] is False

    def test_duplicate_rejected(self, db_init):
        db_init.add_instance("bw-1", 5000, "bwapi", "manual")
        msg = db_init.add_instance("bw-1", 5000, "bwapi", "manual")
        assert "already exists" in msg

    def test_changed_flag_flips_metadata(self, db_init):
        assert db_init.get_metadata()["instances_changed"] is False
        db_init.add_instance("bw-1", 5000, "bwapi", "manual", changed=True)
        assert db_init.get_metadata()["instances_changed"] is True

    def test_listen_https_roundtrip(self, db_init):
        db_init.add_instance("bw-tls", 5000, "bwapi", "manual", listen_https=True, https_port=8443)
        inst = db_init.get_instance("bw-tls")
        assert inst["listen_https"] is True
        assert inst["https_port"] == 8443


class TestGetInstances:
    def test_method_filter_and_autoconf_shape(self, db_init):
        db_init.add_instance("bw-a", 5000, "bwapi", "manual")
        db_init.add_instance("bw-b", 5000, "bwapi", "autoconf")
        assert {i["hostname"] for i in db_init.get_instances()} == {"bw-a", "bw-b"}
        manual = db_init.get_instances(method="manual")
        assert [i["hostname"] for i in manual] == ["bw-a"]
        auto = db_init.get_instances(method="autoconf", autoconf=True)
        assert len(auto) == 1
        # autoconf=True augments each row with health + env; don't assume a default status.
        assert "health" in auto[0]
        assert auto[0]["env"] == {}

    def test_missing_returns_empty_dict(self, db_init):
        assert db_init.get_instance("nope") == {}


class TestDeleteInstance:
    def test_delete(self, db_init):
        db_init.add_instance("bw-1", 5000, "bwapi", "manual")
        assert db_init.delete_instance("bw-1") == ""
        assert db_init.get_instance("bw-1") == {}

    def test_delete_absent(self, db_init):
        assert "does not exist" in db_init.delete_instance("ghost")

    def test_delete_instances_none_found(self, db_init):
        assert db_init.delete_instances(["ghost"]) == "No instances found to delete."


class TestUpdateInstances:
    def test_empty_autoconf_list_is_noop_data_loss_guard(self, db_init):
        db_init.add_instance("bw-auto", 5000, "bwapi", "autoconf")
        # An empty list for method 'autoconf' must NOT wipe existing autoconf instances.
        assert db_init.update_instances([], "autoconf") == ""
        assert db_init.get_instance("bw-auto")["hostname"] == "bw-auto"

    def test_update_replaces_method_scope(self, db_init):
        db_init.add_instance("old", 5000, "bwapi", "autoconf")
        new = [{"hostname": "new", "env": {"API_HTTP_PORT": 5000, "API_SERVER_NAME": "bwapi"}}]
        assert db_init.update_instances(new, "autoconf") == ""
        # 'old' (autoconf) is cleared and replaced by 'new'.
        assert {i["hostname"] for i in db_init.get_instances()} == {"new"}


class TestUpdateInstance:
    def test_update_status(self, db_init):
        db_init.add_instance("bw-1", 5000, "bwapi", "manual")
        assert db_init.update_instance("bw-1", "up") == ""
        assert db_init.get_instance("bw-1")["status"] == "up"

    def test_update_status_missing(self, db_init):
        assert "does not exist" in db_init.update_instance("ghost", "up")

    def test_update_fields(self, db_init):
        db_init.add_instance("bw-1", 5000, "bwapi", "manual")
        assert db_init.update_instance_fields("bw-1", name="renamed", port=6000) == ""
        inst = db_init.get_instance("bw-1")
        assert inst["name"] == "renamed"
        assert inst["port"] == 6000

    def test_update_fields_missing(self, db_init):
        assert "does not exist" in db_init.update_instance_fields("ghost", name="x")


class TestInstanceCredential:
    def test_add_with_credential_encrypts_and_roundtrips(self, db_keyring):
        assert db_keyring.add_instance("bw-c", 5000, "bwapi", "manual", credential="secret-token") == ""
        inst = db_keyring.get_instance("bw-c")
        # The raw token is never exposed in the normal projection ...
        assert inst["credential_set"] is True
        assert "credential" not in inst
        assert inst["credential_updated_at"] is not None
        # ... but is decryptable for the dial path.
        assert db_keyring.get_instance_credential("bw-c") == "secret-token"
        assert db_keyring.get_instance("bw-c", with_credential=True)["credential"] == "secret-token"

    def test_set_and_clear_credential(self, db_keyring):
        db_keyring.add_instance("bw-c", 5000, "bwapi", "manual")
        assert db_keyring.get_instance("bw-c")["credential_set"] is False
        assert db_keyring.set_instance_credential("bw-c", "tok") == ""
        assert db_keyring.get_instance_credential("bw-c") == "tok"
        # An empty token clears it.
        assert db_keyring.set_instance_credential("bw-c", "") == ""
        assert db_keyring.get_instance_credential("bw-c") is None
        assert db_keyring.get_instance("bw-c")["credential_set"] is False

    def test_credential_without_keyring_falls_back(self, db_init, monkeypatch):
        monkeypatch.delenv("CERTIFICATE_ENCRYPTION_KEYS", raising=False)
        monkeypatch.delenv("CERTIFICATE_ENCRYPTION_ACTIVE_KEY", raising=False)
        # No keyring -> the credential is silently not stored (global-token fallback), not an error.
        assert db_init.add_instance("bw-nokey", 5000, "bwapi", "manual", credential="tok") == ""
        assert db_init.get_instance("bw-nokey")["credential_set"] is False
        assert db_init.get_instance_credential("bw-nokey") is None


class TestInstanceTls:
    def test_tls_mode_and_fingerprint_roundtrip(self, db_init):
        fp = "a" * 64
        db_init.add_instance("bw-p", 5000, "bwapi", "manual", tls_mode="pinned", tls_fingerprint=fp)
        inst = db_init.get_instance("bw-p")
        assert inst["tls_mode"] == "pinned"
        assert inst["tls_fingerprint"] == fp

    def test_tls_defaults_off(self, db_init):
        db_init.add_instance("bw-d", 5000, "bwapi", "manual")
        inst = db_init.get_instance("bw-d")
        assert inst["tls_mode"] == "off"
        assert inst["tls_fingerprint"] is None

    def test_update_tls_fields(self, db_init):
        db_init.add_instance("bw-u", 5000, "bwapi", "manual")
        assert db_init.update_instance_fields("bw-u", tls_mode="pinned", tls_fingerprint="b" * 64) == ""
        inst = db_init.get_instance("bw-u")
        assert inst["tls_mode"] == "pinned"
        assert inst["tls_fingerprint"] == "b" * 64


class TestReconcileCredential:
    def test_env_token_distinct_from_global_is_stored(self, db_keyring, monkeypatch):
        monkeypatch.setenv("API_TOKEN", "global-token")
        specs = [{"hostname": "bw-e", "env": {"API_HTTP_PORT": 5000, "API_SERVER_NAME": "bwapi", "API_TOKEN": "per-instance-token"}}]
        assert db_keyring.update_instances(specs, "autoconf") == ""
        assert db_keyring.get_instance_credential("bw-e") == "per-instance-token"

    def test_env_token_equal_global_not_stored(self, db_keyring, monkeypatch):
        monkeypatch.setenv("API_TOKEN", "same-token")
        specs = [{"hostname": "bw-s", "env": {"API_HTTP_PORT": 5000, "API_SERVER_NAME": "bwapi", "API_TOKEN": "same-token"}}]
        assert db_keyring.update_instances(specs, "autoconf") == ""
        assert db_keyring.get_instance("bw-s")["credential_set"] is False
