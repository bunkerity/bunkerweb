"""Malformed stored credentials refuse auth through the helper and both user models."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import bcrypt
import password_utils
import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(params=["helper", "api", "ui"])
def verify(request):
    if request.param == "helper":
        return password_utils.check_password
    spec = spec_from_file_location(f"bw_{request.param}_credential_model", ROOT / f"src/{request.param}/app/models/models.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    def check(password, hashed):
        user = module.UiUsers(username="bcrypt-test", password=hashed.decode("utf-8"))
        return user.check_password(password)

    return check


@pytest.mark.parametrize("hashed", [b"", b"plaintext", b"$2b$13$broken", b"$2b$99$" + b"a" * 53])
def test_malformed_stored_hash_is_refused(verify, hashed):
    assert verify("secret", hashed) is False


def test_valid_and_wrong_passwords_keep_72_byte_semantics(verify):
    password = "\u00e9" * 40
    hashed = bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=4))
    assert verify(password, hashed) is True
    assert verify("wrong", hashed) is False


def test_malformed_hash_spends_normal_cost_without_accepting_dummy_match(verify, monkeypatch):
    real_checkpw = bcrypt.checkpw
    calls = []

    def record_checkpw(secret, hashed):
        calls.append((secret, hashed))
        if len(calls) == 1:
            return real_checkpw(secret, hashed)
        # A matching dummy credential must still refuse authentication.
        return True

    monkeypatch.setattr(password_utils, "checkpw", record_checkpw)
    assert verify("\u00e9" * 40, b"invalid-salt") is False
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0] == ("\u00e9" * 40).encode("utf-8")[:72]
    assert calls[1][1].startswith(b"$2b$13$")
    # Ensure the fallback really is a usable bcrypt hash.
    assert real_checkpw(b"wrong", calls[1][1]) is False
