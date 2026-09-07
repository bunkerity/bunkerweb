"""A TOTP code that has been used must never be accepted a second time.

The replay defence is a counter: passlib refuses a token whose counter is not newer than the last
one accepted, so the counter has to be spent exactly once and the store has to be shared. It used
to be a JSON file under `/var/tmp/bunkerweb`, read and written by whichever gunicorn worker took
the request -- so two workers could both read the same last counter and both accept the same six
digits before either write landed, and a restart that rewrote the file dropped it altogether.

It now lives in the database, behind `POST /users/{username}/totp/use`, whose UPDATE only matches
a row whose stored counter is still older than the one being spent. What is pinned here is the
property -- a used code is refused -- plus the two seams that give it its lifetime: the UI asks
the API rather than a local file, and a refusal is told apart from an outage.

passlib and qrcode are not in the unit-test venv, so the factory is a stand-in that implements the
one contract this code depends on: `verify(...)` returns a match carrying the token's counter.
`FakeApiClient` implements the other one: the conditional UPDATE, as a dict.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest

_UI_ROOT = Path(__file__).resolve().parents[3] / "src" / "ui"
MODEL_PATH = _UI_ROOT / "app" / "models" / "totp.py"


class TokenError(Exception):
    """Stands in for `passlib.exc.TokenError`."""


class MalformedTokenError(TokenError):
    """Stands in for `passlib.exc.MalformedTokenError`."""


class ApiClientError(Exception):
    """Stands in for `app.api_client.ApiClientError`."""

    def __init__(self, message="boom"):
        super().__init__(message)
        self.message = message


class ApiUnavailableError(Exception):
    """Stands in for `app.api_client.ApiUnavailableError` — a *sibling* of `ApiClientError`.

    Not a subclass, because the real ones are not (`base_api_client.py`): `src/ui/app/routes/totp.py`
    catches them in that order and would read an outage as a 4xx if this shape were copied forward.
    """

    def __init__(self, message="API unavailable"):
        super().__init__(message)
        self.message = message


class FakeTotpFactory:
    """passlib's `TOTP.verify` reduced to its counter contract.

    A token is its own counter here ("42" -> counter 42), so a test can replay one by submitting
    the same string twice, exactly as an attacker replays six digits.
    """

    def verify(self, token, secret, *, window=None, last_counter=None):
        try:
            counter = int(token)
        except ValueError:
            raise MalformedTokenError(token)
        return SimpleNamespace(counter=counter)


class FakeApiClient:
    """`POST /users/{u}/totp/use` as the API implements it: spend the counter, or refuse.

    `readonly` rides in the response because only the database knows whether a refusal means
    "already spent" or "nothing can be written", and the client's own `readonly` property is a
    5-second cache that answers **True whenever its probe fails** -- so reading it after a failed
    consume turns an API outage into a free replay window. Reading it is a defect, so it is a
    property here that fails the test loudly instead of a value that quietly papers over one.
    """

    def __init__(self):
        self.counters = {}
        self.readonly_db = False
        self.raises = None
        self.calls = []

    @property
    def readonly(self):
        raise AssertionError("verify_totp must not consult the client's cached readonly probe")

    def use_totp_counter(self, username, totp_secret, counter):
        self.calls.append((username, totp_secret, counter))
        if self.raises:
            raise self.raises
        if self.readonly_db:
            return {"status": "success", "consumed": False, "readonly": True}
        stored = self.counters.get((username, totp_secret))
        if stored is not None and counter <= stored:
            return {"status": "success", "consumed": False, "readonly": False}
        self.counters[(username, totp_secret)] = counter
        return {"status": "success", "consumed": True, "readonly": False}


def _stub(name, **attributes):
    """A module object that also passes as a package, so `from x.y import z` resolves."""
    module = ModuleType(name)
    module.__path__ = []
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def _load(lib_dir, api_client, logger, suffix=""):
    """`app/models/totp.py` executed against the given API client, as one gunicorn worker."""
    stubs = {
        "app.api_client": _stub("app.api_client", ApiClientError=ApiClientError, ApiUnavailableError=ApiUnavailableError),
        "app.dependencies": _stub("app.dependencies", API_CLIENT=api_client),
        "app.utils": _stub("app.utils", LIB_DIR=lib_dir, LOGGER=logger, stop=Mock()),
        "passlib": _stub("passlib"),
        "passlib.totp": _stub(
            "passlib.totp",
            TOTP=SimpleNamespace(using=lambda **kwargs: FakeTotpFactory()),
            MalformedTokenError=MalformedTokenError,
            TokenError=TokenError,
            TotpMatch=SimpleNamespace,
        ),
        "passlib.pwd": _stub("passlib.pwd", genword=Mock(return_value=[])),
        "qrcode": _stub("qrcode", make=Mock()),
        "qrcode.image": _stub("qrcode.image"),
        "qrcode.image.pil": _stub("qrcode.image.pil", PilImage=Mock()),
    }
    module_name = f"app.models._totp_replay_test{suffix}"
    spec = importlib.util.spec_from_file_location(module_name, MODEL_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {**stubs, module_name: module}):
        spec.loader.exec_module(module)
    return module


@pytest.fixture
def totp_model(tmp_path):
    """One worker: the real `Totp`, a fake API, and the real encryption-keys file it needs."""
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / ".totp_encryption_keys.json").write_text(json.dumps({"1": "0" * 32}), encoding="utf-8")

    api_client = FakeApiClient()
    logger = Mock()
    module = _load(lib_dir, api_client, logger)
    return SimpleNamespace(
        totp=module.totp,
        api_client=api_client,
        logger=logger,
        lib_dir=lib_dir,
        user=SimpleNamespace(get_id=lambda: "alice", totp_secret="SECRET"),
        load=lambda suffix: _load(lib_dir, api_client, logger, suffix),
    )


def test_a_used_code_is_refused_the_second_time(totp_model):
    """The defect, stated as the attacker sees it: submit the same six digits twice."""
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is True
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is False


def test_an_older_code_is_refused_too(totp_model):
    """Replaying the *previous* step's code is the same attack one tick later."""
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is True
    assert totp_model.totp.verify_totp("41", user=totp_model.user) is False
    assert totp_model.totp.verify_totp("43", user=totp_model.user) is True


def test_a_second_worker_refuses_the_code_the_first_one_spent(totp_model):
    """The point of moving the counter out of the process: another worker sees it too.

    A separate import of the module is a separate gunicorn worker -- separate module globals,
    separate `Totp` instance -- sharing only what the two really share, the database.
    """
    second_worker = totp_model.load("_worker2")
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is True
    assert second_worker.totp.verify_totp("42", user=totp_model.user) is False


def test_counters_are_per_user(totp_model):
    """One user burning a counter must not lock another user out of the same tick."""
    other = SimpleNamespace(get_id=lambda: "bob", totp_secret="SECRET")
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is True
    assert totp_model.totp.verify_totp("42", user=other) is True
    assert totp_model.totp.verify_totp("42", user=other) is False


def test_enrolment_verifies_without_consuming_anything(totp_model):
    """Enrolment checks a candidate secret the user does not have stored yet.

    There is no counter to spend against a secret that is not the user's, and asking the database
    to spend one would refuse the enrolment: the caller stores the secret, which seeds the counter.
    """
    assert totp_model.totp.verify_totp("42", totp_secret="CANDIDATE", user=totp_model.user) is True
    assert totp_model.api_client.calls == []


def test_enrolment_verifies_without_a_user(totp_model):
    """`user` is optional in the signature: setup checks a candidate before any user row exists."""
    assert totp_model.totp.verify_totp("42", totp_secret="CANDIDATE") is True
    assert totp_model.api_client.calls == []


def test_a_malformed_token_is_refused_without_a_call(totp_model):
    assert totp_model.totp.verify_totp("not-a-code", user=totp_model.user) is False
    assert totp_model.api_client.calls == []


def test_neither_secret_nor_user_is_a_programming_error(totp_model):
    with pytest.raises(ValueError):
        totp_model.totp.verify_totp("42")


def test_a_read_only_database_keeps_the_login_available(totp_model):
    """The counter store is the database; when it cannot be written, refusing every code would
    lock every 2FA user out. The code is accepted, unconsumed, and the warning says so.

    The verdict comes from the API's own answer, so it is still one request per attempt -- the code
    is not waved through without asking."""
    totp_model.api_client.readonly_db = True
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is True
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is True
    assert len(totp_model.api_client.calls) == 2
    assert totp_model.logger.warning.called


def test_an_unreachable_api_refuses_rather_than_letting_the_code_through(totp_model):
    """An outage is not a read-only database: it must not become a free replay window.

    This is the shape the `readonly` property guards. The real client answers True to `readonly`
    whenever its probe fails, so a version of `verify_totp` that gates on it -- before or after the
    consume -- reads an outage as "the database is read-only" and accepts every replayed code."""
    totp_model.api_client.raises = ApiUnavailableError("api down")
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is False
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is False
    assert totp_model.logger.error.called


def test_a_4xx_from_the_endpoint_refuses_too(totp_model):
    """A malformed or rejected request is not permission to log in."""
    totp_model.api_client.raises = ApiClientError("bad request")
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is False
    assert totp_model.logger.error.called


def test_a_replay_stays_refused_while_the_database_is_writable(totp_model):
    """The refusal path that is *not* read-only: `consumed` false, `readonly` false, code refused.

    Pinned separately because it is the branch a read-only fallback is most likely to swallow."""
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is True
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is False
    assert totp_model.logger.warning.called is False


def test_match_totp_reports_an_unusable_stored_secret(totp_model):
    """A wrong code is routine; a secret that cannot be parsed is an operator problem."""

    def explode(token, secret, *, window=None, last_counter=None):
        raise ValueError("bad secret")

    totp_model.totp._totp.verify = explode
    assert totp_model.totp.match_totp("42", "SECRET") is None
    assert totp_model.logger.error.called
