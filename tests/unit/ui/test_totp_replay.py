"""A TOTP code that has been used must never be accepted a second time.

`Totp.verify_totp` asks passlib to reject a token whose counter is not newer than the last one
accepted (`last_counter=`), which is the whole of the replay defence. The counter it hands over
comes from `get_last_counter`, and the counter it stores comes from `set_last_counter` — and
`set_last_counter` used to assign into the nested dict *inside* `DATA`:

    DATA["totp_last_counter"][user.get_id()] = tmatch.counter

`UIData` persists on `__setitem__`, so the top-level `DATA["totp_last_counter"] = {}` line above
it wrote an **empty** mapping to disk and the counter itself never left memory. `get_last_counter`
opens with `DATA.load_from_file()`, which copies that empty mapping back over the in-memory one —
so every lookup returned `None`, passlib was told "nothing used yet", and the same six digits kept
working for the rest of the window. Not only across gunicorn workers or a restart: in the same
process, on the very next call.

What is pinned here is the property — a used code is refused — plus the mechanism that gives it
its lifetime: the counter is on **disk**, so a second worker and a restarted one both see it.

passlib and qrcode are not in the unit-test venv, so the factory is a stand-in that implements
the one contract this code depends on: `verify(...)` raises `UsedTokenError` (a `TokenError`)
when the token's counter is not newer than `last_counter`. Everything else — `UIData`, and the
`Totp` methods under test — is the real thing.
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

from app.models.ui_data import UIData  # noqa: E402 — `src/ui` is on sys.path via conftest


class TokenError(Exception):
    """Stands in for `passlib.exc.TokenError`."""


class UsedTokenError(TokenError):
    """Stands in for `passlib.exc.UsedTokenError`, which passlib raises on replay."""


class MalformedTokenError(TokenError):
    """Stands in for `passlib.exc.MalformedTokenError`."""


class FakeTotpFactory:
    """passlib's `TOTP.verify` reduced to its counter contract.

    A token is its own counter here ("42" -> counter 42), so a test can replay one by
    submitting the same string twice, exactly as an attacker replays six digits.
    """

    def verify(self, token, secret, *, window=None, last_counter=None):
        try:
            counter = int(token)
        except ValueError:
            raise MalformedTokenError(token)
        # passlib: "token has already been used, or is older than the last one accepted"
        if last_counter is not None and counter <= last_counter:
            raise UsedTokenError(token)
        return SimpleNamespace(counter=counter)


def _stub(name, **attributes):
    """A module object that also passes as a package, so `from x.y import z` resolves."""
    module = ModuleType(name)
    module.__path__ = []
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


@pytest.fixture
def totp_model(tmp_path):
    """`app/models/totp.py` executed against a real, file-backed `UIData`.

    The encryption-keys file is real too: the module refuses to import without one.
    """
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / ".totp_encryption_keys.json").write_text(json.dumps({"1": "0" * 32}), encoding="utf-8")

    data_file = tmp_path / "ui_data.json"
    data = UIData(data_file)

    factory = FakeTotpFactory()
    stubs = {
        "app.dependencies": _stub("app.dependencies", DATA=data),
        "app.utils": _stub("app.utils", LIB_DIR=lib_dir, LOGGER=Mock(), stop=Mock()),
        "passlib": _stub("passlib"),
        "passlib.totp": _stub(
            "passlib.totp",
            TOTP=SimpleNamespace(using=lambda **kwargs: factory),
            MalformedTokenError=MalformedTokenError,
            TokenError=TokenError,
            TotpMatch=SimpleNamespace,
        ),
        "passlib.pwd": _stub("passlib.pwd", genword=Mock(return_value=[])),
        "qrcode": _stub("qrcode", make=Mock()),
        "qrcode.image": _stub("qrcode.image"),
        "qrcode.image.pil": _stub("qrcode.image.pil", PilImage=Mock()),
    }

    module_name = "app.models._totp_replay_test"
    spec = importlib.util.spec_from_file_location(module_name, MODEL_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {**stubs, module_name: module}):
        spec.loader.exec_module(module)
        yield SimpleNamespace(totp=module.totp, data=data, data_file=data_file, user=SimpleNamespace(get_id=lambda: "alice", totp_secret="SECRET"))


def test_a_used_code_is_refused_the_second_time(totp_model):
    """The defect, stated as the attacker sees it: submit the same six digits twice."""
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is True
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is False


def test_an_older_code_is_refused_too(totp_model):
    """Replaying the *previous* step's code is the same attack one tick later."""
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is True
    assert totp_model.totp.verify_totp("41", user=totp_model.user) is False
    assert totp_model.totp.verify_totp("43", user=totp_model.user) is True


def test_the_counter_reaches_disk(totp_model):
    """In-memory only would still let a second gunicorn worker — or a restart — accept the code."""
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is True

    on_disk = json.loads(totp_model.data_file.read_text(encoding="utf-8"))
    assert on_disk.get("totp_last_counter", {}).get("alice") == 42

    # A different process reading the same file is what a second worker really is.
    fresh = UIData(totp_model.data_file)
    assert fresh["totp_last_counter"]["alice"] == 42


def test_counters_are_per_user(totp_model):
    """One user burning a counter must not lock another user out of the same tick."""
    other = SimpleNamespace(get_id=lambda: "bob", totp_secret="SECRET")
    assert totp_model.totp.verify_totp("42", user=totp_model.user) is True
    assert totp_model.totp.verify_totp("42", user=other) is True
    assert totp_model.totp.verify_totp("42", user=other) is False


def test_enrolment_verifies_without_a_user(totp_model):
    """`user` is optional in the signature: enrolment checks a candidate secret before there is
    anything to store a counter against. Reading `user.get_id()` there is an AttributeError."""
    assert totp_model.totp.verify_totp("42", totp_secret="CANDIDATE") is True
