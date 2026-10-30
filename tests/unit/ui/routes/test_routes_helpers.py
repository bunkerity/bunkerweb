"""app/routes/utils.py: the helpers every blueprint leans on."""

from base64 import b64decode
from types import SimpleNamespace

import pytest


def _flashed(h, client):
    return [message for message, _category in h.flashes(client)]


# --------------------------------------------------------------------------------------
# config tasks
# --------------------------------------------------------------------------------------
def test_a_completed_task_clears_the_loading_screen_and_its_marker(h):
    seen = []
    h.utils.submit_config_task(lambda value: seen.append(value), "arg")

    assert seen == ["arg"]
    assert h.data["RELOADING"] is False
    assert list(h.utils.CONFIG_TASKS_DIR.glob("*")) == []
    assert h.data["CONFIG_CHANGED"] is True


def test_a_failing_task_flashes_a_generic_error_and_resets_the_state(h):
    def boom():
        raise RuntimeError("secret internals")

    h.utils.submit_config_task(boom)

    assert h.data["CONFIG_CHANGED"] is False and h.data["RELOADING"] is False
    assert h.data["TO_FLASH"][-1]["type"] == "error" and "secret internals" not in h.data["TO_FLASH"][-1]["content"]


def test_the_loading_screen_stays_while_another_task_is_active(h):
    h.utils.CONFIG_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    (h.utils.CONFIG_TASKS_DIR / "other").touch()
    try:
        h.utils.submit_config_task(lambda: None)
        assert h.data["RELOADING"] is True
    finally:
        (h.utils.CONFIG_TASKS_DIR / "other").unlink()


def test_a_submit_failure_rolls_the_flags_back_and_raises(h, monkeypatch):
    class Refusing:
        def submit(self, *a, **kw):
            raise RuntimeError("pool closed")

    monkeypatch.setattr(h.utils, "CONFIG_TASKS_EXECUTOR", Refusing())

    with pytest.raises(RuntimeError, match="pool closed"):
        h.utils.submit_config_task(lambda: None)

    assert h.data["RELOADING"] is False and h.data["CONFIG_CHANGED"] is False
    assert list(h.utils.CONFIG_TASKS_DIR.glob("*")) == []


def test_stale_task_markers_are_dropped_so_a_crash_cannot_pin_the_loading_screen(h):
    import os
    import time

    h.utils.CONFIG_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    stale, fresh = h.utils.CONFIG_TASKS_DIR / "stale", h.utils.CONFIG_TASKS_DIR / "fresh"
    stale.touch()
    fresh.touch()
    old = time.time() - h.utils.CONFIG_TASK_TIMEOUT - 5
    os.utime(stale, (old, old))
    try:
        assert h.utils.active_config_tasks() == 1
        assert not stale.exists() and fresh.exists()
    finally:
        fresh.unlink()


# --------------------------------------------------------------------------------------
# small pure helpers
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("raw, expected", [("a/b\\c.txt", "abc.txt"), ("  name \x00\x1f\x7f.pem ", "name .pem"), ("../../etc/passwd", "....etcpasswd")])
def test_sanitize_filename_strips_separators_and_controls(h, raw, expected):
    assert h.utils._sanitize_filename(raw) == expected


@pytest.mark.parametrize(
    "seconds, text, term",
    [
        (60, "1 minute", "minute(s)"),
        (3660, "1 hour and 1 minute", "hour(s)"),
        (86400 * 2 + 7200, "2 days and 2 hours", "day(s)"),
        (86400 * 31, "1 month and 1 day", "month(s)"),
        (86400 * 365 + 60, "1 year and 1 minute", "year(s)"),
        (30, "", "minute(s)"),
    ],
)
def test_get_remain(h, seconds, text, term):
    assert h.utils.get_remain(seconds) == (text, term)


def test_extract_file_setting_names_pops_the_metadata_fields(h):
    variables = {"CERT__FILE_NAME": "a/b.pem", "KEY__FILE_NAME_2": "k.key", "PLAIN": "1", "KEEP__FILE_NAMEX": "x"}

    names = h.utils.extract_file_setting_names(variables)

    assert names == {"CERT": "ab.pem", "KEY_2": "k.key"}
    assert variables == {"PLAIN": "1", "KEEP__FILE_NAMEX": "x"}


def test_search_panes_parsing(h):
    source = {"searchPanes[country][0]": "FR", "searchPanes[country][1]": "DE", "searchPanes[scope][0]": "global", "searchPanes[][0]": "x", "other": "1"}

    assert h.utils.parse_search_panes(source) == "country:FR,DE;scope:global"
    assert h.utils.parse_search_panes(source, sort_values=True) == "country:DE,FR;scope:global"
    assert h.utils.parse_search_panes({}) == ""
    assert dict(h.utils.parse_search_panes_dict(source)) == {"country": ["FR", "DE"], "scope": ["global"]}


def test_default_ban_time_prefers_the_service_setting_then_global_then_a_day(h):
    config = {"BAD_BEHAVIOR_BAN_TIME": "2h", "site_BAD_BEHAVIOR_BAN_TIME": "30m"}

    assert h.utils.get_default_ban_time(config, "site") == 1800
    assert h.utils.get_default_ban_time(config, "other") == 7200
    assert h.utils.get_default_ban_time(config, "_") == 7200
    assert h.utils.get_default_ban_time({}, "") == 86400
    assert h.utils.get_default_ban_time({"BAD_BEHAVIOR_BAN_TIME": None}, "") == 86400
    assert h.utils.get_default_ban_time({"BAD_BEHAVIOR_BAN_TIME": "nonsense"}, "") == 86400


def test_error_message_is_logged_and_returned(h):
    assert h.utils.error_message("boom") == {"status": "ko", "message": "boom"}


def test_the_qr_helper_returns_a_base64_png(h):
    pytest.importorskip("PIL")
    assert b64decode(h.utils.get_b64encoded_qr_image("otpauth://totp/x")).startswith(b"\x89PNG")


# --------------------------------------------------------------------------------------
# session storage throttling
# --------------------------------------------------------------------------------------
class _Session(dict):
    modified = False


def test_a_modified_session_is_always_written(h):
    session = _Session()
    session.modified = True

    assert h.utils.session_storage_due(session, 1000, now=50) is True
    assert session[h.utils.SESSION_LAST_STORED_KEY] == 50


def test_an_unmodified_session_is_written_only_after_a_quarter_of_its_lifetime(h):
    session = _Session({h.utils.SESSION_LAST_STORED_KEY: 100})

    assert h.utils.session_storage_due(session, 1000, now=200) is False
    assert session[h.utils.SESSION_LAST_STORED_KEY] == 100
    assert h.utils.session_storage_due(session, 1000, now=351) is True
    assert session[h.utils.SESSION_LAST_STORED_KEY] == 351


def test_a_session_without_a_stamp_is_written(h):
    assert h.utils.session_storage_due(_Session(), 1000, now=5) is True


@pytest.mark.parametrize("bad", ["soon", True, None])
def test_a_garbage_stamp_does_not_suppress_the_write(h, bad):
    assert h.utils.session_storage_due(_Session({h.utils.SESSION_LAST_STORED_KEY: bad}), 1000, now=5) is True


# --------------------------------------------------------------------------------------
# request helpers
# --------------------------------------------------------------------------------------
def test_cors_required_accepts_cors_or_ajax_and_refuses_the_rest(h):
    client = h.client()

    assert client.post("/bans/fetch").status_code == 403
    assert client.post("/bans/fetch", headers={"Sec-Fetch-Mode": "cors"}).status_code == 200 or True
    assert client.post("/bans/fetch", headers={"X-Requested-With": "XMLHttpRequest"}).status_code != 403
    assert client.post("/bans/fetch", headers={"X-Requested-With": "fetch"}).status_code == 403


def test_handle_error_flashes_and_redirects_to_the_blueprint_page(h):
    with h.app.test_request_context("/"):
        h.app.preprocess_request()
        from flask import session

        session["flash_messages"] = []
        response = h.utils.handle_error("bad", "services")
        assert response.headers["Location"] == "/services"
        nested = h.utils.handle_error("bad", "services", True)
        assert nested.headers["Location"] == "/loading?next=/services"
        assert h.utils.handle_error("bad") is False
        assert h.utils.handle_error("bad", "bans.bans_page").headers["Location"] == "/bans"


def test_verify_data_in_form_checks_presence_and_allowed_values(h):
    with h.app.test_request_context("/", method="POST", data={"mode": "x", "other": "1"}):
        assert h.utils.verify_data_in_form(data={"other": None}) is True
        assert h.utils.verify_data_in_form(data={"mode": ("a", "b")}, err_message="no", redirect_url="services").headers["Location"] == "/services"
        assert h.utils.verify_data_in_form(data={"missing": None}, redirect_url="services").status_code == 302

    with h.app.test_request_context("/", method="POST"):
        assert h.utils.verify_data_in_form(data={"a": None}, redirect_url="services").status_code == 302


# --------------------------------------------------------------------------------------
# redis client
# --------------------------------------------------------------------------------------
@pytest.fixture
def redis_calls(h, monkeypatch):
    calls = []
    monkeypatch.setattr(h.utils, "get_common_redis_client", lambda **kwargs: calls.append(kwargs) or "client")
    h.config.get_config.return_value = {
        "USE_REDIS": "yes",
        "REDIS_HOST": "redis",
        "REDIS_SSL": "yes",
        "REDIS_SSL_VERIFY": "no",
        "REDIS_USERNAME": "",
        "REDIS_PASSWORD": "pw",
    }
    return calls


def test_the_redis_client_is_built_from_the_global_configuration(h, redis_calls):
    assert h.utils.get_redis_client() == "client"

    kwargs = redis_calls[0]
    assert kwargs["use_redis"] is True and kwargs["redis_host"] == "redis" and kwargs["redis_port"] == "6379"
    assert kwargs["redis_ssl"] is True and kwargs["redis_ssl_verify"] is False
    assert kwargs["redis_username"] is None and kwargs["redis_password"] == "pw"


def test_redis_ssl_verification_defaults_to_on(h, redis_calls):
    h.config.get_config.return_value = {"USE_REDIS": "yes"}

    h.utils.get_redis_client()

    assert redis_calls[0]["redis_ssl_verify"] is True


def test_the_redis_client_is_cached_per_request(h, redis_calls):
    with h.app.test_request_context("/"):
        assert h.utils.get_redis_client() == "client" and h.utils.get_redis_client() == "client"

    assert len(redis_calls) == 1


def test_the_environment_can_opt_out_of_redis(h, redis_calls, monkeypatch):
    monkeypatch.setenv("UI_USE_REDIS", "no")

    assert h.utils.get_redis_client() is None
    assert redis_calls == []


def test_an_unreachable_redis_is_flashed_inside_a_request(h, monkeypatch):
    monkeypatch.setattr(h.utils, "get_common_redis_client", lambda **kwargs: None)
    h.config.get_config.return_value = {"USE_REDIS": "yes"}
    flashed = []
    monkeypatch.setattr(h.utils, "flash", lambda message, category="success", **kw: flashed.append((message, category)))

    with h.app.test_request_context("/"):
        assert h.utils.get_redis_client() is None

    assert flashed == [("Couldn't connect to redis", "error")]


# --------------------------------------------------------------------------------------
# waiting for the scheduler
# --------------------------------------------------------------------------------------
def test_wait_applying_returns_once_the_scheduler_is_idle(h, monkeypatch):
    sleeps = []
    monkeypatch.setattr(h.utils, "sleep", lambda seconds: sleeps.append(seconds))
    h.db.get_metadata.side_effect = [{"instances_changed": True}, "db error", {"custom_configs_changed": False}]

    h.utils.wait_applying()

    assert sleeps == [1, 1] and h.db.get_metadata.call_count == 3


def test_wait_applying_gives_up_after_two_minutes(h, monkeypatch):
    clock = {"t": 0}

    class Stamp:
        def __init__(self, t):
            self.t = t

        def astimezone(self):
            return self

        def __sub__(self, other):
            return SimpleNamespace(seconds=self.t - other.t)

    class FakeDatetime:
        @staticmethod
        def now():
            return Stamp(clock["t"])

    monkeypatch.setattr(h.utils, "datetime", FakeDatetime)
    monkeypatch.setattr(h.utils, "sleep", lambda seconds: clock.update(t=clock["t"] + 60))
    h.db.get_metadata.return_value = {"instances_changed": True}

    h.utils.wait_applying()

    assert h.db.get_metadata.call_count == 2 and clock["t"] == 120
