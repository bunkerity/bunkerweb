"""ui/app/utils.py — bcrypt password helpers + small pure predicates.

Imported via the ``app`` package (``src/ui`` on path, added by the ui conftest). These
are security-relevant: hashing, verification, the 72-byte bcrypt truncation contract,
and the cost factor.
"""

from app.utils import (  # type: ignore
    bcrypt_cost,
    can_delete_service,
    check_password,
    gen_password_hash,
    is_bcrypt_hash,
    is_editable_method,
    is_ui_api_method,
    password_exceeds_bcrypt_limit,
)


class TestPasswordHashing:
    def test_hash_and_check_roundtrip(self):
        h = gen_password_hash("S3cret!")
        assert isinstance(h, bytes)
        assert check_password("S3cret!", h) is True
        assert check_password("wrong", h) is False

    def test_is_bcrypt_hash(self):
        h = gen_password_hash("x").decode("utf-8")
        assert is_bcrypt_hash(h) is True
        assert is_bcrypt_hash("not-a-hash") is False
        assert is_bcrypt_hash("plaintext-password") is False

    def test_bcrypt_cost_is_13(self):
        h = gen_password_hash("x").decode("utf-8")
        assert bcrypt_cost(h) == 13  # gensalt(rounds=13)

    def test_password_exceeds_limit(self):
        assert password_exceeds_bcrypt_limit("a" * 72) is False
        assert password_exceeds_bcrypt_limit("a" * 73) is True

    def test_72_byte_truncation_symmetry(self):
        # >72 bytes is truncated to 72 for both hashing and verification, so two passwords
        # sharing their first 72 bytes verify against each other's hash (documented contract).
        base = "a" * 72
        h = gen_password_hash(base + "EXTRA")
        assert check_password(base + "DIFFERENT", h) is True


class TestMethodPredicates:
    def test_is_editable_method_default(self):
        assert is_editable_method("default") is False
        assert is_editable_method("default", allow_default=True) is True

    def test_is_ui_api_method(self):
        assert is_ui_api_method("ui") is True
        assert is_ui_api_method("definitely_not_a_method") is False

    def test_can_delete_service(self):
        assert can_delete_service({"method": "ui"}) is True
        assert can_delete_service({"method": "autoconf", "is_draft": True}) is True
        assert can_delete_service({"method": "autoconf", "is_draft": False}) is False
