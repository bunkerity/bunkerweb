"""Templator SSL ECDH-curve resolution — preference ranking + auto/fallback.

Pure ranking logic; libssl probing (`_supports_tls_group`) is monkeypatched so results
are deterministic and system-independent. ``_best_ssl_ecdh_curve`` is lru_cached, so the
cache is cleared around every test.
"""

import pytest

import Templator as T  # type: ignore  (src/common/gen on path; needs jinja2)


@pytest.fixture(autouse=True)
def _clear_curve_cache():
    T._best_ssl_ecdh_curve.cache_clear()
    yield
    T._best_ssl_ecdh_curve.cache_clear()


class TestBestSslEcdhCurve:
    def test_preference_order(self, monkeypatch):
        supported = {"X25519", "prime256v1", "secp384r1"}
        monkeypatch.setattr(T, "_supports_tls_group", lambda n: n in supported)
        # preferred order is X25519MLKEM768, X25519, prime256v1, secp384r1, secp521r1, X448
        assert T._best_ssl_ecdh_curve() == "X25519:prime256v1:secp384r1"

    def test_alias_fallback(self, monkeypatch):
        # prime256v1 unsupported but its P-256 alias is -> alias selected
        monkeypatch.setattr(T, "_supports_tls_group", lambda n: n == "P-256")
        assert T._best_ssl_ecdh_curve() == "P-256"

    def test_none_when_nothing_supported(self, monkeypatch):
        monkeypatch.setattr(T, "_supports_tls_group", lambda n: False)
        assert T._best_ssl_ecdh_curve() is None


class TestResolveSslEcdhCurve:
    def test_explicit_value_passthrough(self):
        assert T.resolve_ssl_ecdh_curve("secp384r1") == "secp384r1"

    def test_auto_uses_best(self, monkeypatch):
        monkeypatch.setattr(T, "_supports_tls_group", lambda n: n == "X25519")
        assert T.resolve_ssl_ecdh_curve("auto") == "X25519"

    def test_auto_fallback_when_none(self, monkeypatch):
        monkeypatch.setattr(T, "_supports_tls_group", lambda n: False)
        assert T.resolve_ssl_ecdh_curve("auto", fallback="prime256v1") == "prime256v1"

    def test_empty_takes_auto_path(self, monkeypatch):
        monkeypatch.setattr(T, "_supports_tls_group", lambda n: n == "X25519")
        assert T.resolve_ssl_ecdh_curve("") == "X25519"
