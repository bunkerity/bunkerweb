"""Secure enrollment: issue / redeem / rotate / revoke on ``bw_instances``.

Four properties here are the whole security of the feature and every one of them fails silently
when wrong:

* **single use** -- a code that survives its redemption is a reusable credential minter;
* **expiry** -- a code with no deadline is a permanent one, which is the GitLab CVE-2022-0735
  lesson the design cites;
* **opacity** -- every rejection must answer the same string, because this runs unauthenticated
  and a distinguishable "unknown host" turns the route into an instance enumerator;
* **scope** -- a reconcile that re-sources its rows from a live environment would wipe a minted
  credential, so enrollment is restricted to the rows the control plane can own one on
  (``ENROLLABLE_METHODS``), and that restriction is pinned below -- derived from the tuple, never
  hard-coded, because it moved once already. ``manual`` joined it on 2026-09-02: its rebuild
  (``save_config.py`` → ``update_instances(declarations, method="manual")``) now carries those
  columns across, which is covered in ``test_instance_enrollment_preservation.py``. ``autoconf``
  did not: nothing an operator controls drives that reconcile.

Runs against every selected engine via the ``db`` fixture.
"""

import base64
import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from db_methods.instances import (  # type: ignore
    ENROLLABLE_METHODS,
    ENROLLMENT_MAX_FAILURES,
    ENROLLMENT_REJECTED,
    ENROLLMENT_TTL_MAX,
    hash_enrollment_code,
)

# Derived, never hard-coded: `ENROLLABLE_METHODS` widened once already (2026-09-02, `manual`), and a
# frozen list here would assert the opposite of the rule the code enforces.
ENV_SOURCED_METHODS = tuple(method for method in ("autoconf", "manual", "scheduler") if method not in ENROLLABLE_METHODS)

_TEST_KEY_ID = "test-key-1"
_TEST_KEYRING = json.dumps({_TEST_KEY_ID: base64.b64encode(b"\x00" * 32).decode()})


@pytest.fixture
def db_enroll(db, monkeypatch):
    """A database with a keyring (credentials are stored encrypted) and one enrollable row."""
    monkeypatch.setenv("CERTIFICATE_ENCRYPTION_KEYS", _TEST_KEYRING)
    monkeypatch.setenv("CERTIFICATE_ENCRYPTION_ACTIVE_KEY", _TEST_KEY_ID)
    db.initialize_db("1.7.0", "Docker")
    assert db.add_instance("bw-1", 5000, "bwapi", "ui") == ""
    return db


def _expire(db, hostname):
    """Backdate the stored deadline so the TTL branch runs without sleeping."""
    from model import Instances  # type: ignore
    from sqlalchemy import update

    with db._db_session() as session:
        session.execute(update(Instances).filter_by(hostname=hostname).values({"enroll_token_expires_at": datetime.now().astimezone() - timedelta(seconds=1)}))
        session.commit()


class TestIssue:
    def test_issue_sets_pending_and_hides_the_code(self, db_enroll):
        code, err = db_enroll.issue_enrollment_code("bw-1")
        assert err == ""
        assert code

        instance = db_enroll.get_instance("bw-1")
        assert instance["enrollment_state"] == "pending"
        assert instance["enrollment_expires_at"]
        # The projection must never carry the digest, let alone the code.
        assert "enroll_token_hash" not in instance
        assert code not in str(instance)

    def test_reissue_changes_the_code(self, db_enroll):
        first, _ = db_enroll.issue_enrollment_code("bw-1")
        second, _ = db_enroll.issue_enrollment_code("bw-1")
        assert first != second
        # The first code is dead: only the latest digest is stored.
        assert db_enroll.redeem_enrollment_code("bw-1", first) == (None, ENROLLMENT_REJECTED)

    def test_ttl_is_capped(self, db_enroll):
        before = datetime.now().astimezone()
        code, err = db_enroll.issue_enrollment_code("bw-1", ttl_seconds=999999)
        assert (code, err) != (None, "")
        expires = datetime.fromisoformat(db_enroll.get_instance("bw-1")["enrollment_expires_at"])
        assert expires <= before + timedelta(seconds=ENROLLMENT_TTL_MAX + 5)

    def test_unknown_instance(self, db_enroll):
        code, err = db_enroll.issue_enrollment_code("nope")
        assert code is None
        assert "does not exist" in err

    @pytest.mark.parametrize("method", ENV_SOURCED_METHODS)
    def test_env_sourced_rows_are_refused(self, db_enroll, method):
        """A row re-sourced from a live environment by `update_instances()` cannot hold a minted
        credential: the next reconcile wipes it and nothing reports the lockout."""
        assert db_enroll.add_instance(f"bw-{method}", 5000, "bwapi", method) == ""
        code, err = db_enroll.issue_enrollment_code(f"bw-{method}")
        assert code is None
        assert "sourced from its environment" in err

    @pytest.mark.parametrize("method", ENROLLABLE_METHODS)
    def test_every_enrollable_method_is_actually_accepted(self, db_enroll, method):
        """The other half of the same rule. `manual` -- BUNKERWEB_INSTANCES / BUNKERWEB_INSTANCE_*,
        the Docker and Linux default -- is in here since 2026-09-02, and it is the shape most
        operators run."""
        assert db_enroll.add_instance(f"bw-ok-{method}", 5000, "bwapi", method) == ""
        code, err = db_enroll.issue_enrollment_code(f"bw-ok-{method}")
        assert err == "" and code


class TestRedeem:
    def test_happy_path_mints_a_credential(self, db_enroll):
        code, _ = db_enroll.issue_enrollment_code("bw-1")
        credential, err = db_enroll.redeem_enrollment_code("bw-1", code)
        assert err == ""
        assert credential

        instance = db_enroll.get_instance("bw-1")
        assert instance["enrollment_state"] == "enrolled"
        assert instance["credential_set"] is True
        assert instance["enrollment_expires_at"] is None
        # The minted credential is what the dial will actually present.
        assert db_enroll.get_instance_credential("bw-1") == credential

    def test_single_use(self, db_enroll):
        code, _ = db_enroll.issue_enrollment_code("bw-1")
        first, err = db_enroll.redeem_enrollment_code("bw-1", code)
        assert err == "" and first
        assert db_enroll.redeem_enrollment_code("bw-1", code) == (None, ENROLLMENT_REJECTED)
        # The already-minted credential survives the refused second attempt.
        assert db_enroll.get_instance_credential("bw-1") == first

    def test_expired_code_is_refused(self, db_enroll):
        code, _ = db_enroll.issue_enrollment_code("bw-1")
        _expire(db_enroll, "bw-1")
        assert db_enroll.redeem_enrollment_code("bw-1", code) == (None, ENROLLMENT_REJECTED)
        assert db_enroll.get_instance("bw-1")["credential_set"] is False

    def test_wrong_code_counts_then_burns(self, db_enroll):
        code, _ = db_enroll.issue_enrollment_code("bw-1")
        for _ in range(ENROLLMENT_MAX_FAILURES):
            assert db_enroll.redeem_enrollment_code("bw-1", "wrong") == (None, ENROLLMENT_REJECTED)
        # The code is burned, so even the RIGHT one no longer works.
        assert db_enroll.redeem_enrollment_code("bw-1", code) == (None, ENROLLMENT_REJECTED)
        assert db_enroll.get_instance("bw-1")["enrollment_state"] == "none"

    def test_every_rejection_is_the_same_string(self, db_enroll):
        db_enroll.issue_enrollment_code("bw-1")
        assert db_enroll.add_instance("bw-auto", 5000, "bwapi", "autoconf") == ""
        rejections = {
            db_enroll.redeem_enrollment_code("does-not-exist", "x")[1],
            db_enroll.redeem_enrollment_code("bw-auto", "x")[1],
            db_enroll.redeem_enrollment_code("bw-1", "wrong")[1],
        }
        assert rejections == {ENROLLMENT_REJECTED}

    def test_no_pending_code_is_refused(self, db_enroll):
        assert db_enroll.redeem_enrollment_code("bw-1", "anything") == (None, ENROLLMENT_REJECTED)

    def test_a_redemption_that_read_the_digest_first_still_cannot_land_its_write(self, db_enroll):
        """The compare-and-swap gets driven through the product, not replayed beside it.

        Two callers can read the same digest before either writes. The winner's UPDATE clears it;
        the loser's is conditioned on ``enroll_token_hash`` still being what it read, matches no
        row, and ``rowcount == 0`` is what tells it it lost. Drop that predicate and both callers
        mint a credential.

        The window is opened from inside ``redeem_enrollment_code`` itself: the real
        ``_encrypt_instance_credential`` call happens after the digest is read and before the
        conditional UPDATE, so consuming the digest there puts the function in exactly the loser's
        position. The write goes through a Session built straight on the engine -- ``_db_session``
        is not reentrant, and the outer session has only read at that point, so it holds no write
        lock.

        A previous version of this test hand-wrote the same UPDATE next to the product instead of
        driving it. Removing the predicate from the product left that version green: it asserted
        SQLAlchemy's semantics rather than this function's use of them.
        """
        from model import Instances  # type: ignore
        from sqlalchemy import update
        from sqlalchemy.orm import Session

        code, _ = db_enroll.issue_enrollment_code("bw-1")
        original_encrypt = db_enroll._encrypt_instance_credential
        consumed = []

        def _consume_the_digest_first(hostname, token, keyring=None):
            # The probe runs before the row is read; only the real mint is inside the window.
            if token != "keyring-probe" and not consumed:
                consumed.append(True)
                with Session(db_enroll.sql_engine) as racer:
                    racer.execute(
                        update(Instances).filter_by(hostname="bw-1").values({"enroll_token_hash": None, "enroll_code_state": "none"}),
                        execution_options={"synchronize_session": False},
                    )
                    racer.commit()
            return original_encrypt(hostname, token, keyring)

        db_enroll._encrypt_instance_credential = _consume_the_digest_first
        try:
            credential, err = db_enroll.redeem_enrollment_code("bw-1", code)
        finally:
            db_enroll._encrypt_instance_credential = original_encrypt

        assert consumed, "the window never opened; _encrypt_instance_credential no longer runs before the UPDATE"
        assert (credential, err) == (None, ENROLLMENT_REJECTED), "the loser must not be handed a credential"
        # And it must not have written one either.
        assert db_enroll.get_instance("bw-1")["credential_set"] is False

    def test_hash_is_what_is_stored(self, db_enroll):
        from model import Instances  # type: ignore
        from sqlalchemy import select

        code, _ = db_enroll.issue_enrollment_code("bw-1")
        with db_enroll._db_session() as session:
            row = session.scalars(select(Instances).filter_by(hostname="bw-1")).first()
            assert row.enroll_token_hash == hash_enrollment_code(code)
            assert row.enroll_token_hash != code


class TestBurningACodeNeverDemotesALiveCredential:
    """Re-issue on an already-enrolled row, then let the code die. The credential must survive it.

    The chain this closes: `issue_enrollment_code` moves an enrolled row to `pending`; the instance
    boots late and redeems an expired code; the burn used to stamp `enrollment_state="none"` on a
    row that still held a live credential. Downstream, "none" is what the reconcile guard reads as
    "safe to take over" (so the credential got wiped on the next config save) and what the UI reads
    as "not enrolled" (so the operator lost the revoke button on an instance that could still be
    reached). Nothing in the enrollment tests saw it, because the credential itself was intact.
    """

    def _enrolled_then_reissued(self, db):
        code, _ = db.issue_enrollment_code("bw-1")
        credential, err = db.redeem_enrollment_code("bw-1", code)
        assert err == "" and credential
        db.issue_enrollment_code("bw-1")  # re-issue: the row is now "pending" WITH a credential
        assert db.get_instance("bw-1")["enrollment_state"] == "pending"
        return credential

    def test_an_expired_code_leaves_an_enrolled_row_enrolled(self, db_enroll):
        credential = self._enrolled_then_reissued(db_enroll)
        _expire(db_enroll, "bw-1")
        assert db_enroll.redeem_enrollment_code("bw-1", "whatever") == (None, ENROLLMENT_REJECTED)

        instance = db_enroll.get_instance("bw-1")
        assert instance["enrollment_state"] == "enrolled", "burning the code must not demote the credential"
        assert db_enroll.get_instance_credential("bw-1") == credential

    def test_the_failure_cap_leaves_an_enrolled_row_enrolled(self, db_enroll):
        credential = self._enrolled_then_reissued(db_enroll)
        for _ in range(ENROLLMENT_MAX_FAILURES):
            db_enroll.redeem_enrollment_code("bw-1", "wrong")

        instance = db_enroll.get_instance("bw-1")
        assert instance["enrollment_state"] == "enrolled"
        assert db_enroll.get_instance_credential("bw-1") == credential

    def test_a_burn_on_a_row_that_never_enrolled_still_goes_to_none(self, db_enroll):
        code, _ = db_enroll.issue_enrollment_code("bw-1")
        _expire(db_enroll, "bw-1")
        assert db_enroll.redeem_enrollment_code("bw-1", code) == (None, ENROLLMENT_REJECTED)
        assert db_enroll.get_instance("bw-1")["enrollment_state"] == "none"

    def test_a_credential_alone_is_enough_to_survive_a_reconcile(self, db_enroll):
        """Defence in depth for the same bug: a row holding a credential is not the reconcile's to
        take over, whatever the other two columns say.

        Since the split there is nothing left to force: a redeemed row already carries
        ``enroll_code_state="none"`` and a NULL ``credential_revoked_at``, so the credential is
        provably the only arm of the guard that can be firing here. Asserted rather than assumed.
        """
        code, _ = db_enroll.issue_enrollment_code("bw-1")
        credential, _ = db_enroll.redeem_enrollment_code("bw-1", code)
        from model import Instances  # type: ignore
        from sqlalchemy import select

        with db_enroll._db_session() as session:
            row = session.scalars(select(Instances).filter_by(hostname="bw-1").limit(1)).first()
            assert row.enroll_code_state == "none" and row.credential_revoked_at is None

        assert (
            db_enroll.update_instances(
                [{"hostname": "bw-1", "name": "hijacked", "env": {}, "method": "autoconf"}],
                method="autoconf",
                changed=False,
            )
            == ""
        )
        assert db_enroll.get_instance_credential("bw-1") == credential


class TestRevoke:
    def test_revoke_clears_the_credential(self, db_enroll):
        code, _ = db_enroll.issue_enrollment_code("bw-1")
        assert db_enroll.redeem_enrollment_code("bw-1", code)[0]
        assert db_enroll.revoke_instance_enrollment("bw-1") == ""

        instance = db_enroll.get_instance("bw-1")
        assert instance["enrollment_state"] == "revoked"
        assert instance["credential_set"] is False
        assert db_enroll.get_instance_credential("bw-1") is None

    def test_revoke_unknown_instance(self, db_enroll):
        assert "does not exist" in db_enroll.revoke_instance_enrollment("nope")

    @pytest.mark.parametrize("method", ENV_SOURCED_METHODS)
    def test_env_sourced_rows_cannot_be_revoked_either(self, db_enroll, method):
        """Issuing refuses them, so revoking must too. Otherwise the row parks in a state where
        every push is refused until the next reconcile silently un-revokes it, and the UI cannot
        undo it -- DELETE refuses non-UI/API rows."""
        assert db_enroll.add_instance(f"bw-{method}", 5000, "bwapi", method) == ""
        assert "sourced from its environment" in db_enroll.revoke_instance_enrollment(f"bw-{method}")
        assert db_enroll.get_instance(f"bw-{method}")["enrollment_state"] == "none"

    def test_reissue_after_revoke_is_the_recovery_path(self, db_enroll):
        code, _ = db_enroll.issue_enrollment_code("bw-1")
        db_enroll.redeem_enrollment_code("bw-1", code)
        db_enroll.revoke_instance_enrollment("bw-1")

        new_code, err = db_enroll.issue_enrollment_code("bw-1")
        assert err == "" and new_code
        credential, err = db_enroll.redeem_enrollment_code("bw-1", new_code)
        assert err == "" and credential
        assert db_enroll.get_instance("bw-1")["enrollment_state"] == "enrolled"


class TestARevocationHoldsUntilTheCodeIsRedeemed:
    """A revoked row an admin is re-enrolling stays unreachable until the instance redeems, and is
    never dialled with the global API_TOKEN in the meantime.

    Before the split this was live. ``enrollment_state`` carried both the code lifecycle and the
    credential fact, ``issue_enrollment_code`` stamped "pending" over "revoked", and
    ``API.from_instance`` read that string -- so issuing the recovery code lifted the revocation
    instantly, and since revoking had already cleared the credential columns the dial fell straight
    back to the shared token the instance is supposed to have stopped accepting. Driven end to end
    (real row, real projection, real ``API``): a hand-built dict is exactly what hid it.
    """

    def _api(self, db, token="the-global-token"):
        from API import API  # type: ignore

        return API.from_instance(db.get_instance("bw-1", with_credential=True), token=token)

    def _enrolled_then_revoked(self, db):
        code, _ = db.issue_enrollment_code("bw-1")
        assert db.redeem_enrollment_code("bw-1", code)[0]
        assert db.revoke_instance_enrollment("bw-1") == ""

    def test_issuing_a_code_on_a_revoked_row_does_not_lift_the_revocation(self, db_enroll, monkeypatch):
        monkeypatch.setenv("API_TOKEN", "the-environment-token")
        self._enrolled_then_revoked(db_enroll)
        new_code, err = db_enroll.issue_enrollment_code("bw-1")
        assert err == "" and new_code

        instance = db_enroll.get_instance("bw-1", with_credential=True)
        # The chip still reads "pending" -- an admin IS re-enrolling it, and that is what the old
        # single column stored too. The dial must not read it.
        assert instance["enrollment_state"] == "pending"
        assert instance["credential_revoked"] is True

        api = self._api(db_enroll)
        with patch("API.request") as network:
            sent, err, status, _ = api.request("GET", "/ping")
        network.assert_not_called()
        assert sent is False and "revoked" in err
        # Neither the passed fallback nor API.__init__'s own getenv("API_TOKEN") got attached.
        assert not getattr(api, "_API__token")

    def test_a_successful_redemption_is_what_lifts_it(self, db_enroll):
        self._enrolled_then_revoked(db_enroll)
        new_code, _ = db_enroll.issue_enrollment_code("bw-1")
        credential, err = db_enroll.redeem_enrollment_code("bw-1", new_code)
        assert err == "" and credential

        instance = db_enroll.get_instance("bw-1", with_credential=True)
        assert instance["credential_revoked"] is False
        assert instance["enrollment_state"] == "enrolled"

        api = self._api(db_enroll)
        with patch("API.request") as network:
            network.return_value = type("R", (), {"status_code": 200, "json": lambda self: {"status": "ok"}, "text": "{}"})()
            api.request("GET", "/ping")
        assert network.call_args.kwargs["headers"]["Authorization"] == f"Bearer {credential}"


class TestReconcileCannotReachEnrolledRows:
    """The reconcile clears rows by method, and `ui`/`api` are not among the methods it is ever
    called with, so a control-plane row is never in its blast radius. The `manual` rows it IS called
    with are protected the other way, by the preservation covered in
    `test_instance_enrollment_preservation.py`."""

    def test_manual_reconcile_leaves_a_ui_row_alone(self, db_enroll):
        code, _ = db_enroll.issue_enrollment_code("bw-1")
        credential, err = db_enroll.redeem_enrollment_code("bw-1", code)
        assert err == "" and credential

        # Exactly what save_config.py runs on every scheduler config save.
        assert db_enroll.update_instances([], method="manual", changed=False) == ""

        instance = db_enroll.get_instance("bw-1")
        assert instance["enrollment_state"] == "enrolled"
        assert db_enroll.get_instance_credential("bw-1") == credential

    def test_autoconf_reconcile_leaves_a_ui_row_alone(self, db_enroll):
        code, _ = db_enroll.issue_enrollment_code("bw-1")
        credential, _ = db_enroll.redeem_enrollment_code("bw-1", code)

        assert (
            db_enroll.update_instances(
                [{"hostname": "bw-auto", "name": "bw-auto", "env": {}, "method": "autoconf"}],
                method="autoconf",
                changed=False,
            )
            == ""
        )
        assert db_enroll.get_instance("bw-1")["enrollment_state"] == "enrolled"
        assert db_enroll.get_instance_credential("bw-1") == credential


class TestTheReconcileSkipOnlyFiresOnEnrolledRows:
    """The guard added to `update_instances` must not change the ordinary reconcile.

    Worth being precise about what the guard can even reach, because it is narrower than it looks:
    the reconcile DELETEs by method first, so a row of the *same* method is already gone by the
    time the by-hostname lookup runs and always takes the INSERT branch. The guarded branch is
    reachable only for a row of a *different* method that happens to share a hostname -- which is
    exactly the enrolled-row takeover below. Widening the guard to every row is therefore
    unobservable, and the first test here does not pretend to catch it; it pins the reconcile's
    ordinary outcome so a future change to that DELETE cannot go unnoticed.
    """

    def test_an_ordinary_autoconf_row_is_still_rewritten(self, db_enroll):
        assert db_enroll.add_instance("bw-auto", 5000, "bwapi", "autoconf") == ""
        assert (
            db_enroll.update_instances(
                [{"hostname": "bw-auto", "name": "renamed", "env": {"API_HTTP_PORT": 5001}, "method": "autoconf"}],
                method="autoconf",
                changed=False,
            )
            == ""
        )
        instance = db_enroll.get_instance("bw-auto")
        assert (instance["name"], instance["port"]) == ("renamed", 5001)

    def test_an_enrolled_row_sharing_a_hostname_is_not_taken_over(self, db_enroll):
        """`bw-1` is a `ui` row, so it survives the DELETE-by-method and would otherwise be found
        by hostname and rewritten -- flipping its method and clearing its credential while
        `enrollment_state` stayed `enrolled`, which reads as "enrolled with no credential" and
        sends the dial back to the global token the instance no longer accepts."""
        code, _ = db_enroll.issue_enrollment_code("bw-1")
        credential, _ = db_enroll.redeem_enrollment_code("bw-1", code)

        assert (
            db_enroll.update_instances(
                [{"hostname": "bw-1", "name": "hijacked", "env": {}, "method": "autoconf"}],
                method="autoconf",
                changed=False,
            )
            == ""
        )
        instance = db_enroll.get_instance("bw-1")
        assert instance["method"] == "ui", "the reconcile must not take over an enrolled row"
        assert instance["name"] != "hijacked"
        assert instance["enrollment_state"] == "enrolled"
        assert db_enroll.get_instance_credential("bw-1") == credential
