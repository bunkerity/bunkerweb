"""`SSL_ECDH_CURVE=auto` must ask libssl the question nginx asks, not the one `ssl.SSLContext` answers.

`auto` once probed each group with `SSLContext.set_ecdh_curve`, which uses another name table and ignores
the provider/FIPS policy: it accepted X25519 on a FIPS OpenSSL, nginx then refused the directive and failed
to start. The probe is now `SSL_CTX_set1_groups_list` bound through ctypes (`_set1_groups_list_probe`) and the
`SSLContext` path is only the fallback when libssl cannot be bound. These tests go through the probe itself;
`test_templator_ssl.py` stubs `_supports_tls_group`, so it never reaches it. Refs #3549.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import Templator as T  # type: ignore  (src/common/gen on path; needs jinja2)

BOGUS = "bunkerweb-not-a-real-group"
FIPS_REJECTED = {"X25519", "X25519MLKEM768", "X448"}


@pytest.fixture(autouse=True)
def _clear_caches():
    def clear():
        for name in ("_best_ssl_ecdh_curve", "_supports_tls_group", "_set1_groups_list_probe"):
            func = getattr(T, name, None)
            if func is not None:
                func.cache_clear()

    clear()
    yield
    clear()


def _fake_libssl(accepted):
    """A stand-in libssl whose ``SSL_CTX_ctrl(SET_GROUPS_LIST)`` returns 1 only for ``accepted`` groups."""
    lib = MagicMock()
    lib.TLS_server_method.return_value = 1
    lib.SSL_CTX_new.return_value = 2
    lib.SSL_CTX_ctrl.side_effect = lambda ctx, op, arg, parg: 1 if parg.decode() in accepted else 0
    return lib


def _bind(monkeypatch, lib):
    monkeypatch.setattr(T, "find_library", lambda name: "libssl-fake.so")
    monkeypatch.setattr(T, "CDLL", lambda candidate: lib)


def test_real_probe_accepts_a_known_group_and_rejects_a_bogus_one():
    probe = T._set1_groups_list_probe()
    if probe is None:
        pytest.skip("libssl cannot be bound on this host, the probe falls back")
    assert probe("prime256v1") is True
    assert probe(BOGUS) is False


def test_supports_tls_group_goes_through_the_real_probe():
    if T._set1_groups_list_probe() is None:
        pytest.skip("libssl cannot be bound on this host, the probe falls back")
    assert T._supports_tls_group("prime256v1") is True
    assert T._supports_tls_group(BOGUS) is False


def test_probe_asks_libssl_with_the_groups_list_ctrl_and_frees_the_context(monkeypatch):
    lib = _fake_libssl({"prime256v1", "X25519"})
    _bind(monkeypatch, lib)

    probe = T._set1_groups_list_probe()

    assert probe is not None
    assert probe("X25519") is True
    assert probe("secp256k1") is False
    ops = {call.args[1] for call in lib.SSL_CTX_ctrl.call_args_list}
    assert ops == {92}, "nginx's ssl_ecdh_curve goes through SSL_CTRL_SET_GROUPS_LIST"
    assert lib.SSL_CTX_free.call_count == lib.SSL_CTX_new.call_count


def test_probe_is_rejected_when_the_binding_accepts_a_bogus_group(monkeypatch):
    _bind(monkeypatch, _fake_libssl({"prime256v1", BOGUS}))

    assert T._set1_groups_list_probe() is None


def test_probe_is_unavailable_when_no_libssl_candidate_loads(monkeypatch):
    def refuse(candidate):
        raise OSError(candidate)

    monkeypatch.setattr(T, "find_library", lambda name: None)
    monkeypatch.setattr(T, "CDLL", refuse)

    assert T._set1_groups_list_probe() is None


def test_probe_answer_wins_over_the_sslcontext_answer(monkeypatch):
    """libssl refuses X25519 (FIPS) while `SSLContext` would accept it: the answer must be libssl's."""
    monkeypatch.setattr(T, "_set1_groups_list_probe", lambda: (lambda group: group not in FIPS_REJECTED), raising=False)
    ctx = MagicMock()
    monkeypatch.setattr(T, "SSLContext", lambda *args: ctx)

    assert T._supports_tls_group("X25519") is False
    assert T._supports_tls_group("prime256v1") is True
    ctx.set_ecdh_curve.assert_not_called()


def test_auto_omits_the_groups_the_probe_rejects(monkeypatch):
    monkeypatch.setattr(T, "_set1_groups_list_probe", lambda: (lambda group: group not in FIPS_REJECTED), raising=False)
    monkeypatch.setattr(T, "SSLContext", lambda *args: SimpleNamespace(set_ecdh_curve=lambda name: None))

    curve = T._best_ssl_ecdh_curve()

    assert curve == "prime256v1:secp384r1:secp521r1"
    assert T.resolve_ssl_ecdh_curve("auto") == "prime256v1:secp384r1:secp521r1"


def test_auto_keeps_every_group_a_permissive_probe_accepts(monkeypatch):
    monkeypatch.setattr(T, "_set1_groups_list_probe", lambda: (lambda group: True), raising=False)

    assert T._best_ssl_ecdh_curve() == "X25519MLKEM768:X25519:prime256v1:secp384r1:secp521r1:X448"


def test_without_a_probe_the_sslcontext_answer_is_used(monkeypatch):
    monkeypatch.setattr(T, "_set1_groups_list_probe", lambda: None, raising=False)

    def make_context(*args):
        def set_ecdh_curve(name):
            if name not in {"prime256v1", "secp384r1"}:
                raise ValueError(name)

        return SimpleNamespace(set_ecdh_curve=set_ecdh_curve)

    monkeypatch.setattr(T, "SSLContext", make_context)
    monkeypatch.setattr(T, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout=""))

    assert T._supports_tls_group("prime256v1") is True
    assert T._supports_tls_group("X25519") is False
    assert T._best_ssl_ecdh_curve() == "prime256v1:secp384r1"


def test_without_a_probe_a_pqc_hybrid_is_found_through_the_openssl_cli(monkeypatch):
    monkeypatch.setattr(T, "_set1_groups_list_probe", lambda: None, raising=False)

    def refuse(name):
        raise ValueError(name)

    monkeypatch.setattr(T, "SSLContext", lambda *a: SimpleNamespace(set_ecdh_curve=refuse))
    monkeypatch.setattr(T, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="  X25519MLKEM768 @ default\n"))

    assert T._supports_tls_group("X25519MLKEM768") is True
    assert T._supports_tls_group("X25519") is False
