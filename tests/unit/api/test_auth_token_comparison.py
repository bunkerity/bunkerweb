"""Credential comparison must be constant-time AND survive a malformed header.

`hmac.compare_digest` raises TypeError when either `str` carries a non-ASCII character, and the
presented value comes straight off an Authorization header -- so `Bearer é` reached the guard as a
TypeError and the caller got a 500 instead of a 401. The rate limiter grew a second call site of
the same comparison (the admin-token exemption), which is what made it worth one helper.

`app/auth/common.py` only imports `Request` from fastapi for a type hint. fastapi is pinned in
tests/unit/requirements.in since 2026-09-01, so the real module is always importable here — this
file used to install a stub into sys.modules when fastapi was absent, WITHOUT restoring it, which
poisoned every later `from fastapi import ...` in the run (12 collection-order-dependent errors
in test_downgrade_hold). No stub, no leak.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

COMMON = Path(__file__).resolve().parents[3] / "src" / "api" / "app" / "auth" / "common.py"


def _load_common():
    spec = spec_from_file_location("bw_api_auth_common", COMMON)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_matching_token_is_accepted():
    tokens_equal = _load_common().tokens_equal

    assert tokens_equal("s3cr3t", "s3cr3t") is True


def test_a_wrong_token_is_refused():
    tokens_equal = _load_common().tokens_equal

    assert tokens_equal("s3cr3t", "s3cr3T") is False
    assert tokens_equal("s3cr3t", "s3cr3t ") is False


def test_a_missing_side_never_matches():
    tokens_equal = _load_common().tokens_equal

    # An unset API_TOKEN must not turn every bearer-carrying request into an authenticated one.
    assert tokens_equal("s3cr3t", None) is False
    assert tokens_equal("s3cr3t", "") is False
    assert tokens_equal(None, "s3cr3t") is False
    assert tokens_equal("", "") is False


def test_a_non_ascii_credential_is_refused_instead_of_raising():
    tokens_equal = _load_common().tokens_equal

    assert tokens_equal("clé-privée", "s3cr3t") is False
    assert tokens_equal("s3cr3t", "clé-privée") is False
    assert tokens_equal("clé-privée", "clé-privée") is True
