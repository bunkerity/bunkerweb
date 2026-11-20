"""The setup wizard: it must work exactly once and never again for an anonymous visitor."""

from datetime import datetime, timedelta

import pytest


def _flashed(h, client):
    return [message for message, _category in h.flashes(client)]


@pytest.fixture
def setup(h, monkeypatch):
    h.db.get_config.return_value = {"SERVER_NAME": ""}
    h.db.get_ui_user.return_value = None
    h.db.create_ui_user.return_value = ""
    h.db.checked_changes.return_value = ""
    h.config.new_service.return_value = ("", False)
    h.config.edit_service.return_value = ("", False)
    h.config.get_plugins_settings.return_value = {}
    for name in ("ADMIN_USERNAME", "ADMIN_PASSWORD", "UI_HOST", "PRO_LICENSE_KEY", "AUTO_LETS_ENCRYPT"):
        monkeypatch.delenv(name, raising=False)
    module = h.routes.setup
    monkeypatch.setattr(module, "sleep", lambda seconds: None)
    # bcrypt at cost 13 is ~0.3 s a call; the hashing itself is covered by the profile tests and test_ui_utils
    monkeypatch.setattr(module, "gen_password_hash", lambda password: b"$2b$13$stub" + password.encode())
    return module


FORM = {
    "theme": "dark",
    "admin_username": "admin",
    "admin_email": "admin@example.com",
    "admin_password": "Str0ng-Passw0rd!",
    "admin_password_check": "Str0ng-Passw0rd!",
    "server_name": "ui.example.com",
    "ui_host": "http://bw-ui:7000",
    "ui_url": "",
    "auto_lets_encrypt": "no",
    "lets_encrypt_staging": "no",
    "lets_encrypt_wildcard": "no",
    "email_lets_encrypt": "",
    "lets_encrypt_challenge": "http",
    "lets_encrypt_profile": "classic",
    "lets_encrypt_custom_profile": "",
    "lets_encrypt_dns_provider": "",
    "lets_encrypt_dns_propagation": "default",
}
UI_SERVICE = {"SERVER_NAME": "ui.example.com", "ui.example.com_USE_UI": "yes", "ui.example.com_REVERSE_PROXY_URL": "/admin"}


# --------------------------------------------------------------------------------------
# who can reach the wizard
# --------------------------------------------------------------------------------------
def test_the_wizard_page_renders_for_a_fresh_install(h, setup):
    h.client(None).get("/setup?reason=session_expired", headers={"Host": "bw.example.org:8443"})

    template, context = h.renders[-1]
    assert template == "setup.html" and context["server_name"] == "bw.example.org" and context["ui_user"] is None
    assert "Your session ended" in context["notice"]


def test_an_unknown_reason_is_not_echoed(h, setup):
    h.client(None).get("/setup?reason=<b>x</b>")

    assert h.renders[-1][1]["notice"] is None


def test_the_host_defaults_when_the_header_is_empty(h, setup):
    h.client(None).get("/setup", headers={"Host": ""})

    assert h.renders[-1][1]["server_name"] in ("www.example.com", "localhost")


def test_a_finished_setup_sends_an_anonymous_visitor_to_the_login_page(h, setup):
    h.db.get_ui_user.return_value = object()
    h.db.get_config.return_value = UI_SERVICE

    response = h.client(None).get("/setup")

    assert response.status_code == 303 and response.headers["Location"].endswith("/login")


def test_a_finished_setup_sends_a_signed_in_user_home(h, setup):
    h.db.get_ui_user.return_value = object()
    h.db.get_config.return_value = UI_SERVICE

    assert h.client("alice").get("/setup").headers["Location"].endswith("/home")


def test_an_existing_admin_without_a_ui_service_requires_a_login_first(h, setup):
    h.db.get_ui_user.return_value = object()

    response = h.client(None).get("/setup")

    assert response.status_code == 302 and "/login?next=" in response.headers["Location"]


def test_a_signed_in_user_without_an_admin_record_is_sent_home(h, setup):
    assert h.client("alice").get("/setup").headers["Location"].endswith("/home")


@pytest.mark.parametrize("admin_exists", [True])
def test_an_anonymous_post_cannot_rerun_the_wizard_once_an_admin_exists(h, setup, admin_exists):
    h.db.get_ui_user.return_value = object()
    h.db.get_config.return_value = UI_SERVICE

    response = h.client(None).post("/setup", data=FORM)

    assert response.status_code == 303
    h.db.create_ui_user.assert_not_called()
    h.config.new_service.assert_not_called()
    h.config.edit_global_conf.assert_not_called()


def test_an_anonymous_post_cannot_add_a_service_when_only_the_admin_exists(h, setup):
    h.db.get_ui_user.return_value = object()

    response = h.client(None).post("/setup", data=FORM)

    assert response.status_code == 302 and "/login" in response.headers["Location"]
    h.config.new_service.assert_not_called()


# --------------------------------------------------------------------------------------
# the wizard POST
# --------------------------------------------------------------------------------------
def test_the_wizard_creates_the_admin_and_the_ui_service(h, setup):
    h.db.get_config.return_value = {"SERVER_NAME": ""}
    client = h.client(None)

    response = client.post("/setup", data=FORM | {"language": "fr"})

    assert response.status_code == 200
    args, kwargs = h.db.create_ui_user.call_args
    assert args[0] == "admin" and args[1].startswith(b"$2") and args[2] == ["admin"] and args[3] == "admin@example.com"
    assert kwargs["theme"] == "dark" and kwargs["language"] == "fr" and kwargs["method"] == "wizard" and kwargs["admin"] is True
    base = h.config.new_service.call_args.args[0]
    assert base == {"SERVER_NAME": "ui.example.com", "USE_UI": "yes", "USE_TEMPLATE": "ui"}
    assert h.config.new_service.call_args.kwargs == {"override_method": "wizard", "check_changes": False}
    edited = h.config.edit_service.call_args.args
    assert edited[0] == "ui.example.com" and edited[1]["REVERSE_PROXY_HOST"] == "http://bw-ui:7000" and edited[1]["REVERSE_PROXY_URL"] == "/"
    h.db.checked_changes.assert_called_once_with(["config", "custom_configs"], plugins_changes="all", value=True)
    assert any(call.args[0].get("MULTISITE") == "yes" for call in h.config.edit_global_conf.call_args_list)


def test_the_wizard_can_add_a_license_key_and_dns_credentials(h, setup):
    h.db.get_config.return_value = {"SERVER_NAME": ""}

    h.client(None).post("/setup", data=FORM | {"pro_license_key": "KEY", "lets_encrypt_dns_credential_items": ["a=1", "", "b=2"]})

    assert any(call.args[0].get("PRO_LICENSE_KEY") == "KEY" for call in h.config.edit_global_conf.call_args_list)
    config = h.config.edit_service.call_args.args[1]
    assert config["LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"] == "a=1" and config["LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_2"] == "b=2"


@pytest.mark.parametrize(
    "change, message",
    [
        ({"admin_username": "u" * 257}, "The admin username is too long."),
        ({"admin_email": "e" * 257}, "The admin email is too long."),
        ({"admin_password_check": "other"}, "The passwords do not match."),
        ({"admin_password": "weak", "admin_password_check": "weak"}, "The admin password is not strong enough."),
        ({"admin_password": "Aa1!" + "x" * 80, "admin_password_check": "Aa1!" + "x" * 80}, "The admin password is too long."),
        ({"server_name": "  "}, "The hostname can't be empty."),
        ({"ui_host": "not a url"}, "The hostname is not valid."),
    ],
)
def test_the_wizard_validates_before_creating_anything(h, setup, change, message):
    client = h.client(None)

    response = client.post("/setup", data=FORM | change)

    assert response.status_code == 302
    h.config.new_service.assert_not_called()
    assert any(message in flashed for flashed in _flashed(h, client))
    if "admin" in message or "passwords" in message:
        h.db.create_ui_user.assert_not_called()


def test_a_hostname_already_in_use_is_refused(h, setup):
    h.db.get_config.return_value = {"SERVER_NAME": "ui.example.com other.example.com", "other.example.com_SERVER_NAME": "alias.example.com"}
    client = h.client(None)

    client.post("/setup", data=FORM)
    client.post("/setup", data=FORM | {"server_name": "alias.example.com"})

    h.config.new_service.assert_not_called()
    assert _flashed(h, client).count("The hostname ui.example.com is already in use.") == 1
    assert "The hostname alias.example.com is already in use." in _flashed(h, client)


def test_a_custom_certificate_needs_both_halves(h, setup):
    client = h.client(None)

    client.post("/setup", data=FORM | {"use_custom_ssl": "yes", "custom_ssl_cert": "/c.pem"})

    h.config.new_service.assert_not_called()
    assert "When using a custom SSL certificate, you must set both the certificate and the key." in _flashed(h, client)


def test_a_custom_certificate_given_as_data_is_accepted(h, setup):
    h.client(None).post("/setup", data=FORM | {"use_custom_ssl": "yes", "custom_ssl_cert_data": "C", "custom_ssl_key_data": "K"})

    config = h.config.edit_service.call_args.args[1]
    assert config["USE_CUSTOM_SSL"] == "yes" and config["CUSTOM_SSL_CERT_DATA"] == "C" and config["CUSTOM_SSL_KEY_DATA"] == "K"


def test_service_creation_errors_are_reported(h, setup):
    client = h.client(None)

    h.config.new_service.return_value = ("duplicate", True)
    client.post("/setup", data=FORM)
    h.config.new_service.return_value = ("", False)
    h.config.edit_service.return_value = ("bad setting", True)
    client.post("/setup", data=FORM)

    flashed = _flashed(h, client)
    assert "Couldn't create the new service: duplicate" in flashed and "Couldn't edit the new service: bad setting" in flashed


def test_an_admin_creation_error_stops_the_wizard(h, setup):
    h.db.create_ui_user.return_value = "locked"
    client = h.client(None)

    client.post("/setup", data=FORM)

    h.config.new_service.assert_not_called()
    assert "Couldn't create the admin user in the database: locked" in _flashed(h, client)


def test_the_wizard_post_is_refused_in_read_only_mode(h, setup):
    h.db.readonly = True
    client = h.client(None)

    client.post("/setup", data=FORM)

    h.db.create_ui_user.assert_not_called()
    assert "Database is in read-only mode" in _flashed(h, client)


def test_a_post_without_any_expected_field_is_refused(h, setup):
    client = h.client(None)

    client.post("/setup", data={"unrelated": "1"})

    h.db.create_ui_user.assert_not_called()
    assert any("Missing either one of the following parameters" in message for message in _flashed(h, client))


# --------------------------------------------------------------------------------------
# /setup/loading
# --------------------------------------------------------------------------------------
def test_loading_waits_until_the_ui_service_exists(h, setup):
    h.db.get_ui_user.return_value = None

    response = h.client(None).get("/setup/loading")

    assert response.status_code == 302 and response.headers["Location"].endswith("/setup/loading")


def test_loading_sends_an_old_enough_admin_to_the_login_page(h, setup):
    h.db.get_config.return_value = UI_SERVICE
    h.db.get_ui_user.return_value = {"creation_date": datetime.now().astimezone() - timedelta(minutes=10)}

    response = h.client(None).get("/setup/loading")

    assert response.status_code == 303 and response.headers["Location"].endswith("/login")


def test_loading_normalizes_the_ui_url_and_sanitizes_next(h, setup):
    h.db.get_config.return_value = UI_SERVICE | {"ui.example.com_REVERSE_PROXY_URL": "admin"}
    h.db.get_ui_user.return_value = {"creation_date": datetime.now().astimezone()}

    h.client(None).get("/setup/loading?next=https://evil.example/")

    template, context = h.renders[-1]
    assert template == "loading.html" and context["next"] == "/admin/login"


def test_loading_keeps_an_internal_next(h, setup):
    h.db.get_config.return_value = UI_SERVICE
    h.db.get_ui_user.return_value = None

    h.client(None).get("/setup/loading?next=/admin/home")

    assert h.renders[-1][1]["next"] == "/admin/home"


def test_loading_only_accepts_the_check_endpoint_of_the_ui_service(h, setup):
    h.db.get_config.return_value = UI_SERVICE
    h.db.get_ui_user.return_value = None
    client = h.client(None)

    assert client.get("/setup/loading?target_endpoint=https://evil.example/check").status_code == 400
    assert client.get("/setup/loading?target_endpoint=https://ui.example.com/admin/check").status_code == 200
    assert h.renders[-1][1]["target_endpoint"] == "https://ui.example.com/admin/check"
