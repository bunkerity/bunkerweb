"""app/models/session_cookie.py and safe_session_cache.py: cookie naming per request, JSON-only session files."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from cachelib import SimpleCache
from flask import Flask, session
from flask_session.cachelib import CacheLibSessionInterface

from app.models.safe_session_cache import SafeFileSystemCache, SafeFileSystemSerializer
from app.models.session_cookie import DIRECT_COOKIE_NAME, PROXIED_COOKIE_NAME, is_proxied_request, use_per_request_cookie


@pytest.fixture
def app():
    app = Flask("cookie")
    app.secret_key = "k"
    app.config.update(SESSION_COOKIE_DOMAIN="example.org", SESSION_COOKIE_SECURE=False)
    app.session_interface = CacheLibSessionInterface(app, client=SimpleCache())
    use_per_request_cookie(app.session_interface)
    app.add_url_rule("/set", "set", lambda: session.__setitem__("u", "alice") or "ok")
    app.add_url_rule("/get", "get", lambda: session.get("u", "none"))
    return app


def _cookie_headers(response):
    return response.headers.getlist("Set-Cookie")


class TestPerRequestCookie:
    def test_direct_request_gets_the_plain_insecure_cookie(self, app):
        response = app.test_client().get("/set", base_url="http://localhost")
        (header,) = _cookie_headers(response)
        assert header.startswith(f"{DIRECT_COOKIE_NAME}=")
        assert "Secure" not in header and "Domain" not in header

    def test_forwarded_request_gets_the_host_locked_secure_cookie(self, app):
        response = app.test_client().get("/set", headers={"X-Forwarded-For": "1.2.3.4"}, base_url="http://localhost")
        (header,) = _cookie_headers(response)
        assert header.startswith(f"{PROXIED_COOKIE_NAME}=")
        assert "Secure" in header and "Domain" not in header

    def test_https_request_counts_as_proxied(self, app):
        with app.test_request_context("/", base_url="https://localhost"):
            assert is_proxied_request() is True
        with app.test_request_context("/", base_url="http://localhost"):
            assert is_proxied_request() is False

    def test_each_cookie_only_opens_its_own_session(self, app):
        client = app.test_client()
        client.get("/set", headers={"X-Forwarded-For": "1.2.3.4"}, base_url="http://localhost")
        assert client.get("/get", headers={"X-Forwarded-For": "1.2.3.4"}, base_url="http://localhost").data == b"alice"
        assert client.get("/get", base_url="http://localhost").data == b"none"

    def test_unknown_sid_gets_a_fresh_session(self, app):
        client = app.test_client()
        client.set_cookie(DIRECT_COOKIE_NAME, "forged-sid", domain="localhost")
        assert client.get("/get", base_url="http://localhost").data == b"none"

    def test_class_swap_keeps_the_base_name_and_state(self, app):
        interface = app.session_interface
        assert type(interface).__name__ == "CacheLibSessionInterface"
        assert type(interface).__mro__[1].__name__ == "PerRequestCookieMixin"
        assert interface.cache is not None  # the cachelib client survived the swap


class TestSafeSerializer:
    def test_datetime_round_trip(self, tmp_path):
        cache = SafeFileSystemCache(str(tmp_path), threshold=10)
        moment = datetime(2026, 10, 26, 12, 30, tzinfo=timezone.utc)
        cache.set("k", {"when": moment, "n": [1, 2], "nested": {"t": moment}})
        assert cache.get("k") == {"when": moment, "n": [1, 2], "nested": {"t": moment}}

    def test_files_on_disk_are_json(self, tmp_path):
        cache = SafeFileSystemCache(str(tmp_path), threshold=10)
        cache.set("k", {"a": 1})
        stored = Path(cache._get_filename("k"))
        assert b'{"a": 1}' in stored.read_bytes()

    def test_pickled_legacy_file_reads_as_a_miss(self, tmp_path):
        import pickle

        cache = SafeFileSystemCache(str(tmp_path), threshold=10)
        cache.set("k", {"a": 1})
        stored = Path(cache._get_filename("k"))
        stored.write_bytes(b"\x00\x00\x00\x00" + pickle.dumps({"a": 1}))
        assert cache.get("k") is None

    def test_non_utf8_payload_is_a_miss(self):
        import io

        assert SafeFileSystemSerializer().load(io.BytesIO(b"\xff\xfe\xfa")) is None

    def test_unserializable_value_raises_type_error(self):
        import io

        with pytest.raises(TypeError, match="Object of type object is not JSON serializable"):
            SafeFileSystemSerializer().dump({"x": object()}, io.BytesIO())

    def test_single_key_marker_dict_only_decodes_when_it_is_the_whole_object(self):
        import io

        buffer = io.BytesIO(b'{"__dt__": "2026-01-02T03:04:05", "other": 1}')
        assert SafeFileSystemSerializer().load(buffer) == {"__dt__": "2026-01-02T03:04:05", "other": 1}
        buffer = io.BytesIO(b'{"__dt__": "2026-01-02T03:04:05"}')
        assert SafeFileSystemSerializer().load(buffer) == datetime(2026, 1, 2, 3, 4, 5)
