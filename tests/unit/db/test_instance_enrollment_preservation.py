"""The config-save rebuild must not drop what the control plane minted.

``save_config.py`` sends the whole environment-declared roster again on **every** scheduler config
save. Until 2026-09-02 it did that as ``update_instances([], method="manual")`` -- a DELETE of every
``manual`` row -- followed by one ``add_instance()`` per declaration, so a credential minted by an
enrollment vanished silently at the next save. That is why ``manual`` rows were not enrollable at
all, and the PO ruling of 2026-09-02 reverses it: the rebuild preserves, and ``manual`` joins
``ENROLLABLE_METHODS``.

Three properties, each of which fails silently when wrong:

* **a declared hostname keeps its credential and its enrollment state** -- otherwise the control
  plane dials an instance with a credential it no longer has and every push is refused with nothing
  to read (``api.lua:is_allowed_token`` answers ONLY to the minted credential);
* **a hostname that disappeared from the environment loses everything with its row** -- preservation
  must not resurrect an enrollment the operator removed;
* **``autoconf`` is untouched by all of it** -- those rows really are re-sourced from a live
  orchestrator on every reconcile, and keeping a stale per-instance credential there is a lockout.

Runs against every selected engine via the ``db`` fixture.
"""

import base64
import json
from unittest.mock import patch

import pytest

from db_methods.instances import ENROLLABLE_METHODS, PRESERVED_CREDENTIAL_COLUMNS, PRESERVED_ENROLLMENT_COLUMNS  # type: ignore

_TEST_KEY_ID = "test-key-1"
_TEST_KEYRING = json.dumps({_TEST_KEY_ID: base64.b64encode(b"\x00" * 32).decode()})


@pytest.fixture
def db_enroll(db, monkeypatch):
    """A database with a keyring, holding one environment-declared (`manual`) instance."""
    monkeypatch.setenv("CERTIFICATE_ENCRYPTION_KEYS", _TEST_KEYRING)
    monkeypatch.setenv("CERTIFICATE_ENCRYPTION_ACTIVE_KEY", _TEST_KEY_ID)
    monkeypatch.delenv("API_TOKEN", raising=False)
    db.initialize_db("1.7.0", "Docker")
    assert db.add_instance("bw-1", 5000, "bwapi", "manual") == ""
    return db


def _declaration(hostname="bw-1", token=None):
    """Exactly the shape `save_config.py` hands `update_instances()` for a declared instance."""
    return {
        "hostname": hostname,
        "name": "manual instance",
        "status": "loading",
        "env": {"API_HTTP_PORT": 5000, "API_HTTPS_PORT": 5443, "API_LISTEN_HTTPS": "no", "API_SERVER_NAME": "bwapi", "API_TOKEN": token},
        "tls_mode": None,
        "tls_fingerprint": None,
    }


def _enroll(db, hostname="bw-1"):
    code, err = db.issue_enrollment_code(hostname)
    assert err == "" and code, err
    credential, err = db.redeem_enrollment_code(hostname, code)
    assert err == "" and credential, err
    return credential


class TestManualIsEnrollable:
    def test_the_shared_tuple_carries_manual(self):
        """The single authority: the DB guards, the rotate router and the UI mirror all read it."""
        assert "manual" in ENROLLABLE_METHODS

    def test_issue_redeem_revoke_all_accept_a_declared_instance(self, db_enroll):
        credential = _enroll(db_enroll)
        assert db_enroll.get_instance_credential("bw-1") == credential
        assert db_enroll.get_instance("bw-1")["enrollment_state"] == "enrolled"
        assert db_enroll.revoke_instance_enrollment("bw-1") == ""
        assert db_enroll.get_instance("bw-1")["enrollment_state"] == "revoked"

    def test_autoconf_is_still_refused(self, db_enroll):
        """The reconcile there is driven by a live orchestrator, not by an operator-controlled
        rebuild, so nothing can carry a minted credential across it."""
        assert "autoconf" not in ENROLLABLE_METHODS
        assert db_enroll.add_instance("bw-auto", 5000, "bwapi", "autoconf") == ""
        code, err = db_enroll.issue_enrollment_code("bw-auto")
        assert code is None and "sourced from its environment" in err


class TestTheRebuildPreserves:
    def test_a_still_declared_hostname_keeps_its_credential(self, db_enroll):
        credential = _enroll(db_enroll)

        # Exactly what save_config.py runs on every scheduler config save.
        assert db_enroll.update_instances([_declaration()], method="manual", changed=False) == ""

        assert db_enroll.get_instance_credential("bw-1") == credential
        assert db_enroll.get_instance("bw-1")["enrollment_state"] == "enrolled"

    def test_a_still_declared_row_is_updated_in_place_never_recreated(self, db_enroll):
        """The structural half of the fix, and the reason no snapshot is taken.

        A rebuild that DELETEs and re-INSERTs has a window: anything that commits between the two
        (a redemption, a rotation) is overwritten by whatever the rebuild carries. Updating the
        surviving row in place removes the window instead of racing it. `creation_date` is the
        observable proof -- a re-INSERT cannot keep it, and it also stopped churning on every
        config save for a row that never went away.
        """
        created = db_enroll.get_instance("bw-1")["creation_date"]
        _enroll(db_enroll)

        for _ in range(3):
            assert db_enroll.update_instances([_declaration()], method="manual", changed=False) == ""

        assert db_enroll.get_instance("bw-1")["creation_date"] == created

    def test_it_survives_repeated_saves(self, db_enroll):
        """The failure mode was per-save, so once is not proof."""
        credential = _enroll(db_enroll)
        for _ in range(3):
            assert db_enroll.update_instances([_declaration()], method="manual", changed=False) == ""
        assert db_enroll.get_instance_credential("bw-1") == credential

    def test_a_pending_code_survives_a_config_save(self, db_enroll):
        """An admin issues a code, then anything at all triggers a config save before the instance
        redeems it. Burning the code there would make enrollment a race against the scheduler."""
        code, err = db_enroll.issue_enrollment_code("bw-1")
        assert err == ""

        assert db_enroll.update_instances([_declaration()], method="manual", changed=False) == ""

        credential, err = db_enroll.redeem_enrollment_code("bw-1", code)
        assert err == "" and credential

    def test_a_revocation_survives_a_config_save(self, db_enroll):
        """`credential_revoked_at` is what stops the dial falling back to the global API_TOKEN;
        losing it in the rebuild would silently un-revoke the instance.

        The logger is patched for the sentinel, not for the revocation: the lift warning reads
        `reconciled.get("credential_revoked_at", "keep") is None`, and the default is the whole
        guard on this path. Drop it and `.get()` returns `None` for the three return shapes that
        carry no such key -- so a revoked row whose revocation is HOLDING would announce
        "the revocation is being lifted" on every single config save. This is the only test that
        builds that state, so it is the only place the sentinel can be pinned.
        """
        _enroll(db_enroll)
        assert db_enroll.revoke_instance_enrollment("bw-1") == ""

        warnings = []
        with patch.object(db_enroll.logger, "warning", warnings.append):
            assert db_enroll.update_instances([_declaration()], method="manual", changed=False) == ""

        assert db_enroll.get_instance("bw-1")["enrollment_state"] == "revoked"
        assert not [message for message in warnings if "revocation is being lifted" in message], warnings

    def test_a_re_sourced_declared_token_lifts_the_revocation_with_it(self, db_enroll):
        """The other half of `test_a_revocation_survives_a_config_save`, and the one that bites:
        a revocation stamps the row AND clears its credential, and `API.from_instance` then dials
        with `token=""` whatever the credential columns hold. So a declared token re-sourced onto a
        revoked row would be a fresh, valid credential the control plane refuses to use -- for good,
        because no reconcile lifts the stamp and a `manual` row cannot be deleted from the UI."""
        _enroll(db_enroll)
        assert db_enroll.revoke_instance_enrollment("bw-1") == ""

        # Lifting a revocation is a security control being switched back off: it must not be silent.
        # The sibling warning cannot cover it -- a revoke NULLs the credential columns first -- so
        # this pins the one that can.
        warnings = []
        with patch.object(db_enroll.logger, "warning", warnings.append):
            assert db_enroll.update_instances([_declaration(token="declared-token")], method="manual", changed=False) == ""

        instance = db_enroll.get_instance("bw-1")
        assert instance["credential_revoked"] is False
        assert instance["enrollment_state"] == "enrolled"
        assert db_enroll.get_instance_credential("bw-1") == "declared-token"
        assert any("revocation is being lifted" in message for message in warnings), warnings

    def test_an_ordinary_config_save_lifts_nothing_and_says_nothing(self, db_enroll):
        """The other side of the warning above: it must fire on the lift, not on every save of a
        declared-token row, or it is noise that gets filtered out before it ever matters."""
        assert db_enroll.update_instances([_declaration(token="declared-token")], method="manual", changed=False) == ""

        warnings = []
        with patch.object(db_enroll.logger, "warning", warnings.append):
            assert db_enroll.update_instances([_declaration(token="declared-token")], method="manual", changed=False) == ""

        assert not [message for message in warnings if "revocation is being lifted" in message]

    def test_a_vanished_hostname_loses_everything(self, db_enroll):
        """The only way a rebuild drops an enrollment: the operator removed the instance from
        BUNKERWEB_INSTANCES. Preservation must not resurrect it."""
        _enroll(db_enroll)

        assert db_enroll.update_instances([_declaration(hostname="bw-2")], method="manual", changed=False) == ""

        assert db_enroll.get_instance("bw-1") in (None, {})
        assert db_enroll.get_instance_credential("bw-1") is None

    def test_a_declared_token_still_wins(self, db_enroll):
        """An instance whose identity is declared in its own environment is not one the control
        plane mints for: BUNKERWEB_INSTANCE_API_TOKEN_n keeps being re-sourced, as it always was,
        so changing it in the environment still takes effect."""
        _enroll(db_enroll)

        assert db_enroll.update_instances([_declaration(token="declared-token")], method="manual", changed=False) == ""

        assert db_enroll.get_instance_credential("bw-1") == "declared-token"

    def test_the_declared_ports_and_tls_still_land(self, db_enroll):
        """The rebuild replaced an `add_instance()` loop that carried these; a preservation that
        quietly stopped applying the declaration would pin the row to its first save."""
        declaration = _declaration() | {"tls_mode": "pinned", "tls_fingerprint": "ab" * 32}
        declaration["env"]["API_HTTP_PORT"] = 5001
        declaration["env"]["API_SERVER_NAME"] = "other"

        assert db_enroll.update_instances([declaration], method="manual", changed=False) == ""

        instance = db_enroll.get_instance("bw-1")
        assert instance["port"] == 5001
        assert instance["server_name"] == "other"
        assert instance["tls_mode"] == "pinned"
        assert instance["tls_fingerprint"] == "ab" * 32

    def test_an_enrolled_row_still_picks_up_its_declaration(self, db_enroll):
        """Preservation must not turn an enrolled row into a frozen one.

        The takeover guard skips a row that carries an enrollment, because rewriting a row owned by
        ANOTHER method would clear its credential. A still-declared row of this reconcile's own
        method has to fall through that guard instead, or an operator editing
        `BUNKERWEB_INSTANCE_API_HTTP_PORT_1` would be silently ignored for exactly the instances
        this lane made enrollable.
        """
        credential = _enroll(db_enroll)
        declaration = _declaration() | {"tls_mode": "pinned", "tls_fingerprint": "cd" * 32}
        declaration["env"]["API_HTTP_PORT"] = 5002

        assert db_enroll.update_instances([declaration], method="manual", changed=False) == ""

        instance = db_enroll.get_instance("bw-1")
        assert instance["port"] == 5002
        assert instance["tls_mode"] == "pinned"
        # ... and the enrollment is still intact, which is the whole point of doing both.
        assert db_enroll.get_instance_credential("bw-1") == credential
        assert instance["enrollment_state"] == "enrolled"


class TestAutoconfIsUnchanged:
    def test_a_dropped_env_token_is_still_cleared(self, db_enroll, monkeypatch):
        """Preservation must not leak to autoconf: an instance that removed API_TOKEN from its
        environment must fall back to the global token, not keep a stale per-instance one."""
        monkeypatch.setenv("API_TOKEN", "global-token")
        reconcile = {"hostname": "bw-auto", "name": "auto", "env": {"API_TOKEN": "own-token"}}
        assert db_enroll.update_instances([reconcile], method="autoconf", changed=False) == ""
        assert db_enroll.get_instance_credential("bw-auto") == "own-token"

        reconcile["env"].pop("API_TOKEN")
        assert db_enroll.update_instances([reconcile], method="autoconf", changed=False) == ""

        assert db_enroll.get_instance_credential("bw-auto") is None


class TestTheColumnListIsComplete:
    def test_every_column_the_control_plane_writes_is_preserved(self):
        """The list is the whole mechanism: a column added to the enrollment flow and forgotten
        here comes back to its default on the next config save, which is the original bug."""
        from model import Instances  # type: ignore

        control_plane_columns = {
            column.name for column in Instances.__table__.columns if column.name.startswith("enroll_") or column.name.startswith("credential_")
        }
        assert control_plane_columns == set(PRESERVED_ENROLLMENT_COLUMNS) | set(PRESERVED_CREDENTIAL_COLUMNS)
