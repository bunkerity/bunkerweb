"""What the UI writes to its log and streams from log files.

Pins that a DEBUG log never carries form values, that the login log cannot be used to forge a log line, and that a
log-stream resume far behind the end of the file reads at most the tail cap.
"""

import json
import logging

import pytest

from app.utils import LOGGER

SECRETS = ("S3cret-Passw0rd!", "123456-totp", "PRIVATE-KEY-DATA", "dns-credential-token", "zerossl-key")


@pytest.fixture
def debug_log(caplog):
    previous = LOGGER.level
    LOGGER.setLevel(logging.DEBUG)
    propagate = LOGGER.propagate
    LOGGER.propagate = True
    with caplog.at_level(logging.DEBUG):
        yield caplog
    LOGGER.setLevel(previous)
    LOGGER.propagate = propagate


def test_verify_data_in_form_logs_key_names_only(h, debug_log):
    with h.app.test_request_context("/x", method="POST", data={"password": SECRETS[0], "totp_token": SECRETS[1]}):
        assert h.utils.verify_data_in_form(data={"password": (), "totp_token": ()}, redirect_url="login") is True

    assert "password" in debug_log.text and "totp_token" in debug_log.text
    for secret in SECRETS:
        assert secret not in debug_log.text


def test_setup_debug_log_carries_no_form_value(h, debug_log):
    h.db.get_ui_user.return_value = None
    h.db.readonly = False
    h.db.get_config.return_value = {"SERVER_NAME": ""}
    h.db.create_ui_user.return_value = ""
    h.db.checked_changes.return_value = ""
    h.config.new_service.return_value = ("ok", False)
    h.config.edit_service.return_value = ("ok", False)
    form = {
        "theme": "light",
        "admin_username": "admin",
        "admin_email": "",
        "admin_password": SECRETS[0],
        "admin_password_check": SECRETS[0],
        "server_name": "www.example.com",
        "ui_host": "http://bw-ui:7000",
        "ui_url": "/",
        "auto_lets_encrypt": "no",
        "lets_encrypt_staging": "no",
        "lets_encrypt_wildcard": "no",
        "email_lets_encrypt": "",
        "lets_encrypt_zerossl_api_key": SECRETS[4],
        "lets_encrypt_challenge": "http",
        "lets_encrypt_profile": "classic",
        "lets_encrypt_custom_profile": "",
        "lets_encrypt_dns_provider": "",
        "lets_encrypt_dns_propagation": "",
        "lets_encrypt_dns_credential_items": SECRETS[3],
        "use_custom_ssl": "yes",
        "custom_ssl_cert_priority": "data",
        "custom_ssl_cert": "",
        "custom_ssl_key": "",
        "custom_ssl_cert_data": "CERT-DATA",
        "custom_ssl_key_data": SECRETS[2],
    }

    response = h.client(None).post("/setup", data=form)

    assert response.status_code == 200
    assert "Creating new service" in debug_log.text, "the setup debug line never ran"
    for secret in SECRETS:
        assert secret not in debug_log.text


@pytest.fixture
def login(h, tmp_path, monkeypatch):
    monkeypatch.setattr(h.routes.login, "BISCUIT_PRIVATE_KEY_FILE", tmp_path / "missing.key")
    h.db.get_ui_user.return_value = None
    h.db.get_ui_user.side_effect = lambda username=None: None if username else object()


def test_login_log_escapes_control_characters_in_the_username(h, login, caplog):
    forged = 'bob"\n2026-01-01 00:00:00 | ERROR | UI | forged record\rX'
    with caplog.at_level(logging.WARNING):
        h.client(None).post("/login", data={"username": forged, "password": "x"})

    lines = [r.getMessage() for r in caplog.records if "Login attempt" in r.getMessage()]
    assert len(lines) == 1
    assert "\n" not in lines[0] and "\r" not in lines[0]
    assert "forged record" in lines[0]


@pytest.fixture
def logs(h, tmp_path, monkeypatch):
    module = h.routes.logs
    root = tmp_path / "bunkerweb"
    (root / "letsencrypt").mkdir(parents=True)
    monkeypatch.setattr(module, "LOGS_PATH", root)
    monkeypatch.setattr(module, "_LINECOUNT_CACHE", {})
    monkeypatch.setattr(module, "REFRESH_TAIL_BYTES", 1024)
    (root / "ui.log").write_text("".join(f"line {i:05d} {'x' * 40}\n" for i in range(2000)), encoding="utf-8")
    return module


def _first_event(h, last_event_id):
    response = h.client().get("/logs/stream?file=ui.log", headers={"Last-Event-ID": last_event_id}, buffered=False)
    stream = iter(response.response)
    try:
        chunks = [next(stream), next(stream)]  # "retry:" then the first data event
    finally:
        response.close()
    event = chunks[1].decode() if isinstance(chunks[1], bytes) else chunks[1]
    return json.loads(event.split("data: ", 1)[1].split("\n\n", 1)[0])


def test_a_resume_far_behind_the_end_reads_at_most_the_tail_cap(h, logs):
    event = _first_event(h, "0")

    assert event["type"] == "refresh"
    assert len(event["content"].encode()) <= 1024


def test_a_resume_within_the_tail_cap_still_appends(h, logs):
    size = (logs.LOGS_PATH / "ui.log").stat().st_size
    event = _first_event(h, str(size - 100))

    assert event["type"] == "append"
    assert len(event["content"].encode()) == 100
