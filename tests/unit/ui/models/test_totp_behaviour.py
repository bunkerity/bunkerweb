"""``app.models.totp``: secret encryption, token and recovery-code checks, replay protection.

The module builds its key table at import time from files under ``LIB_DIR`` and binds the global ``DB``, so each
test loads a fresh copy by file path with ``LIB_DIR`` pointing at a temporary directory and ``app.dependencies``
replaced by a stub that carries the database under test.
"""

import base64
import importlib.util
import json
import logging
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from bcrypt import gensalt, hashpw

import app.utils as app_utils

# T5B_MUTANT_TOTP points the suite at a mutated scratch copy when a mutation proof is run
SRC = Path(os.environ.get("T5B_MUTANT_TOTP") or Path(__file__).resolve().parents[4] / "src" / "ui" / "app" / "models" / "totp.py")
KEYS = {"1": "k" * 32}
# 15 s into a 30 s period: far from both boundaries, so only the current period is in reach
NOW = 1_700_000_015
PERIOD = 30


class _Stopped(Exception):
    pass


def _load(tmp_path, monkeypatch, *, db=None, keys_file=".totp_encryption_keys.json", keys=KEYS):
    if keys_file:
        tmp_path.joinpath(keys_file).write_text(json.dumps(keys), encoding="utf-8")
    monkeypatch.setattr(app_utils, "LIB_DIR", tmp_path)

    def stop(status, _stop=True):
        raise _Stopped(status)

    monkeypatch.setattr(app_utils, "stop", stop)
    deps = ModuleType("app.dependencies")
    deps.DB = db if db is not None else SimpleNamespace(readonly=False, use_ui_user_totp=lambda *a: True)
    monkeypatch.setitem(sys.modules, "app.dependencies", deps)
    spec = importlib.util.spec_from_file_location("t5b_totp_under_test", SRC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # a fixed clock, so a token is accepted or refused by its window and never by the wall clock
    module.clock = [NOW]
    module.totp._totp = module.totp._totp.using(now=lambda: module.clock[0])
    return module


@pytest.fixture
def totp_module(tmp_path, monkeypatch):
    return _load(tmp_path, monkeypatch)


@pytest.fixture
def secret(totp_module):
    return totp_module.totp.generate_totp_secret()


def _token(module, secret, offset=0):
    """The token of the period ``offset`` periods away from the module's current clock."""
    return module.totp._totp.from_source(secret).generate(time=module.clock[0] + offset * PERIOD).token


class TestKeyTable:
    def test_the_current_key_file_is_used(self, totp_module):
        assert totp_module.TOTP_ENCRYPTION_KEYS == KEYS

    def test_the_legacy_file_still_works_and_says_so(self, tmp_path, monkeypatch, caplog):
        with caplog.at_level(logging.WARNING, logger="UI"):
            module = _load(tmp_path, monkeypatch, keys_file=".totp_secrets.json", keys={"7": "legacy" * 6})
        assert module.TOTP_ENCRYPTION_KEYS == {"7": "legacy" * 6}
        assert any("legacy .totp_secrets.json" in record.getMessage() for record in caplog.records)

    def test_the_current_file_wins_over_the_legacy_one(self, tmp_path, monkeypatch):
        tmp_path.joinpath(".totp_secrets.json").write_text(json.dumps({"9": "z" * 32}), encoding="utf-8")
        module = _load(tmp_path, monkeypatch)
        assert module.TOTP_ENCRYPTION_KEYS == KEYS

    def test_without_any_key_file_the_ui_stops_with_status_1(self, tmp_path, monkeypatch, caplog):
        with caplog.at_level(logging.ERROR, logger="UI"), pytest.raises(_Stopped) as raised:
            _load(tmp_path, monkeypatch, keys_file=None)
        assert raised.value.args == (1,)
        assert any("Neither .totp_encryption_keys.json nor .totp_secrets.json" in record.getMessage() for record in caplog.records)


class TestSecretAndProvisioning:
    def test_the_stored_secret_is_encrypted_with_the_configured_key(self, totp_module, secret):
        data = json.loads(secret)
        assert data["enckey"]["t"] == "1"  # the tag of the configured key
        assert "key" not in data  # the raw key never reaches storage

    def test_two_secrets_differ(self, totp_module, secret):
        assert totp_module.totp.generate_totp_secret() != secret

    def test_the_manual_entry_key_is_readable_and_stable(self, totp_module, secret):
        pretty = totp_module.totp.get_totp_pretty_key(secret)
        assert pretty and " " not in pretty and pretty == pretty.upper()
        assert totp_module.totp.get_totp_pretty_key(secret) == pretty

    def test_an_empty_secret_has_no_manual_entry_key(self, totp_module):
        assert totp_module.totp.get_totp_pretty_key("") == ""
        assert totp_module.totp.get_totp_pretty_key(None) == ""

    def test_the_provisioning_uri_names_the_issuer_and_the_account(self, totp_module, secret):
        uri = totp_module.totp.get_totp_uri("alice", secret)
        assert uri.startswith("otpauth://totp/")
        assert "alice" in uri and "issuer=BunkerWeb%20UI" in uri

    def test_the_qr_code_is_an_inline_jpeg(self, totp_module, secret):
        data_uri = totp_module.totp.generate_qrcode("alice", secret)
        prefix = "data:image/jpeg;base64,"
        assert data_uri.startswith(prefix)
        assert base64.b64decode(data_uri[len(prefix) :])[:3] == b"\xff\xd8\xff"  # noqa: E203

    def test_a_secret_encrypted_under_another_key_table_cannot_be_read(self, tmp_path, monkeypatch, secret):
        (tmp_path / "other").mkdir()
        other = _load(tmp_path / "other", monkeypatch, keys={"2": "o" * 32})
        with pytest.raises(Exception):
            other.totp.get_totp_pretty_key(secret)


class TestRecoveryCodes:
    def test_six_codes_in_four_groups_of_four_hex_digits(self, totp_module):
        codes = totp_module.totp.generate_recovery_codes()
        assert len(codes) == 6 and len(set(codes)) == 6
        for code in codes:
            groups = code.split("-")
            assert [len(group) for group in groups] == [4, 4, 4, 4]
            int("".join(groups), 16)

    def _user(self, *codes):
        return SimpleNamespace(list_recovery_codes=[hashpw(code.encode(), gensalt(rounds=4)).decode() for code in codes])

    def test_a_valid_code_returns_its_stored_hash_and_leaves_the_others(self, totp_module):
        user = self._user("aaaa-bbbb-cccc-dddd", "1111-2222-3333-4444")
        second = user.list_recovery_codes[1]
        remaining_first = user.list_recovery_codes[0]
        assert totp_module.totp.verify_recovery_code("1111-2222-3333-4444", user) == second
        assert user.list_recovery_codes == [remaining_first]

    def test_a_wrong_code_consumes_nothing(self, totp_module):
        user = self._user("aaaa-bbbb-cccc-dddd")
        before = list(user.list_recovery_codes)
        assert totp_module.totp.verify_recovery_code("0000-0000-0000-0000", user) is None
        assert user.list_recovery_codes == before

    def test_a_user_without_codes_never_verifies(self, totp_module):
        assert totp_module.totp.verify_recovery_code("aaaa-bbbb-cccc-dddd", SimpleNamespace(list_recovery_codes=[])) is None
        assert totp_module.totp.verify_recovery_code("aaaa-bbbb-cccc-dddd", SimpleNamespace(list_recovery_codes=None)) is None


class TestMatchTotp:
    def test_the_current_token_matches_with_its_counter(self, totp_module, secret):
        match = totp_module.totp.match_totp(_token(totp_module, secret), secret)
        assert match is not None and match.counter == NOW // PERIOD

    @pytest.mark.parametrize("offset", [-2, -1, 1, 2, 40])
    def test_a_token_of_another_period_is_refused_in_the_middle_of_a_period(self, totp_module, secret, offset):
        assert totp_module.totp.match_totp(_token(totp_module, secret, offset), secret) is None

    @pytest.mark.parametrize("second, offset", [(1, -1), (28, 1)])
    def test_the_neighbour_period_is_accepted_only_within_three_seconds_of_its_boundary(self, totp_module, secret, second, offset):
        # passlib measures ``window`` in seconds: ``window=3`` reaches 3 s, not 3 periods, around the clock
        totp_module.clock[0] = NOW - NOW % PERIOD + second
        match = totp_module.totp.match_totp(_token(totp_module, secret, offset), secret)
        assert match is not None and match.counter == totp_module.clock[0] // PERIOD + offset

    @pytest.mark.parametrize("second, offset", [(5, -1), (24, 1)])
    def test_the_neighbour_period_is_refused_beyond_three_seconds_of_its_boundary(self, totp_module, secret, second, offset):
        totp_module.clock[0] = NOW - NOW % PERIOD + second
        assert totp_module.totp.match_totp(_token(totp_module, secret, offset), secret) is None

    @pytest.mark.parametrize("token", ["", "12345", "abcdef", "1234567"])
    def test_a_malformed_token_is_refused_quietly(self, totp_module, secret, token, caplog):
        with caplog.at_level(logging.ERROR, logger="UI"):
            assert totp_module.totp.match_totp(token, secret) is None
        assert not caplog.records

    @pytest.mark.parametrize("secret_value", ["", None])
    def test_no_stored_secret_never_matches(self, totp_module, secret_value):
        assert totp_module.totp.match_totp("123456", secret_value) is None

    def test_an_unusable_stored_secret_is_logged_without_its_content(self, totp_module, caplog):
        with caplog.at_level(logging.ERROR, logger="UI"):
            assert totp_module.totp.match_totp("123456", "{not-a-secret") is None
        messages = [record.getMessage() for record in caplog.records]
        assert messages and messages[0].startswith("Stored TOTP secret is unusable (") and "not-a-secret" not in messages[0]


class _FakeDb:
    def __init__(self, *, consumed=True, readonly=False, readonly_after=None):
        self.readonly = readonly
        self.consumed = consumed
        self.readonly_after = readonly_after
        self.calls = []

    def use_ui_user_totp(self, username, secret, counter):
        self.calls.append((username, secret, counter))
        if self.readonly_after is not None:
            self.readonly = self.readonly_after
        return self.consumed


def _user(secret, name="alice"):
    return SimpleNamespace(totp_secret=secret, get_id=lambda: name)


class TestVerifyTotp:
    def test_a_secret_or_a_user_is_required(self, totp_module):
        with pytest.raises(ValueError, match="Either totp_secret or user must be provided"):
            totp_module.totp.verify_totp("123456")

    def test_a_wrong_token_never_reaches_the_database(self, tmp_path, monkeypatch, secret):
        db = _FakeDb()
        module = _load(tmp_path, monkeypatch, db=db)
        assert module.totp.verify_totp("000000", user=_user(secret)) is False
        assert db.calls == []

    def test_an_enrolment_check_with_an_explicit_secret_consumes_no_counter(self, tmp_path, monkeypatch, secret):
        db = _FakeDb()
        module = _load(tmp_path, monkeypatch, db=db)
        assert module.totp.verify_totp(_token(module, secret), totp_secret=secret) is True
        # a user whose stored secret differs from the one being enrolled is an enrolment as well
        assert module.totp.verify_totp(_token(module, secret), totp_secret=secret, user=_user("OTHER")) is True
        assert db.calls == []

    def test_a_login_consumes_the_matched_counter_and_returns_the_database_verdict(self, tmp_path, monkeypatch, secret):
        db = _FakeDb(consumed=True)
        module = _load(tmp_path, monkeypatch, db=db)
        assert module.totp.verify_totp(_token(module, secret), user=_user(secret)) is True
        assert db.calls == [("alice", secret, NOW // PERIOD)]

    def test_a_replayed_counter_is_refused(self, tmp_path, monkeypatch, secret):
        db = _FakeDb(consumed=False, readonly=False)
        module = _load(tmp_path, monkeypatch, db=db)
        assert module.totp.verify_totp(_token(module, secret), user=_user(secret)) is False

    def test_a_refused_write_is_a_replay_unless_the_database_just_went_read_only(self, tmp_path, monkeypatch, secret, caplog):
        db = _FakeDb(consumed=False, readonly=False, readonly_after=True)
        module = _load(tmp_path, monkeypatch, db=db)
        with caplog.at_level(logging.WARNING, logger="UI"):
            assert module.totp.verify_totp(_token(module, secret), user=_user(secret)) is True
        assert any("accepted without replay protection" in record.getMessage() for record in caplog.records)

    def test_in_read_only_mode_the_login_stays_available_without_consuming(self, tmp_path, monkeypatch, secret, caplog):
        db = _FakeDb(readonly=True)
        module = _load(tmp_path, monkeypatch, db=db)
        with caplog.at_level(logging.WARNING, logger="UI"):
            assert module.totp.verify_totp(_token(module, secret), user=_user(secret)) is True
        assert db.calls == []
        assert any("read-only" in record.getMessage() for record in caplog.records)

    def test_read_only_mode_still_refuses_a_wrong_token(self, tmp_path, monkeypatch, secret):
        module = _load(tmp_path, monkeypatch, db=_FakeDb(readonly=True))
        assert module.totp.verify_totp("000000", user=_user(secret)) is False


@pytest.mark.multiengine
class TestReplayAgainstARealDatabase:
    def test_a_token_logs_in_once_and_the_next_period_logs_in_again(self, ui_db, tmp_path, monkeypatch):
        module = _load(tmp_path, monkeypatch, db=ui_db)
        secret = module.totp.generate_totp_secret()
        assert ui_db.create_ui_user("alice", b"h", [], totp_secret=secret) == ""
        user = ui_db.get_ui_user(username="alice")
        current = _token(module, secret)
        assert module.totp.verify_totp(current, user=user) is True
        assert module.totp.verify_totp(current, user=user) is False  # replay of the consumed counter
        module.clock[0] -= PERIOD
        assert module.totp.verify_totp(_token(module, secret), user=user) is False  # an older period than the consumed counter
        module.clock[0] += 2 * PERIOD
        assert module.totp.verify_totp(_token(module, secret), user=user) is True  # the next period logs in again
        assert module.totp.verify_totp(_token(module, secret), user=user) is False

    def test_enrolment_stores_the_secret_and_spends_the_enrolment_code(self, ui_db, tmp_path, monkeypatch):
        module = _load(tmp_path, monkeypatch, db=ui_db)
        secret = module.totp.generate_totp_secret()
        assert ui_db.create_ui_user("alice", b"h", []) == ""
        token = _token(module, secret)
        assert module.totp.verify_totp(token, totp_secret=secret) is True
        match = module.totp.match_totp(token, secret)
        assert ui_db.enable_ui_user_totp("alice", secret, match.counter, module.totp.generate_recovery_codes()) == ""
        user = ui_db.get_ui_user(username="alice")
        assert user.totp_secret == secret
        assert module.totp.verify_totp(token, user=user) is False
