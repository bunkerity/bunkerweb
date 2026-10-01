"""The authenticated page env that `main.py`'s `before_request` builds, through the real hook.

Q6-M1  The tab title was English on every authenticated page in every language: `before_request`
       resolved a translated `page_title` but only passed it to the anonymous env; the
       authenticated `data = dict(...)` left it out, so `base.html` fell back to the humanised
       English endpoint. `test_page_title_i18n.py` only covered the pure `resolve_page_title`.
M18    Deleting an unreachable instance showed the NGINX failover banner with an empty message:
       the scheduler raised `failover` for an unreachable instance. The UI now shows the banner
       only with NGINX's own error output to show.

`main.py` cannot be imported in the unit venv, so `before_request` and `inject_variables` are
spliced out of its source (`test_session_plumbing._shipped`) and registered, decorators and all, on
a real Flask app with Babel; only their collaborators are stubbed.
"""

import re
from datetime import datetime, timedelta
from ipaddress import ip_address
from json import loads
from logging import getLogger
from pathlib import Path
from secrets import token_hex, token_urlsafe
from time import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, g, jsonify, make_response, redirect, render_template_string, request, session, url_for
from markupsafe import Markup

from app.i18n import init_i18n, plugin_catalog_fingerprint, resolve_page_title, translated

from test_session_plumbing import MAIN, _shipped

REPO = Path(__file__).resolve().parents[3]


def _catalog_value(language: str, key: str) -> str:
    node = loads((REPO / "src" / "ui" / "app" / "static" / "locales" / f"{language}.json").read_text(encoding="utf-8"))
    for part in key.split("."):
        node = node[part]
    return node


class _Data(dict):
    def load_from_file(self):
        return None


class _ApiError(Exception):
    pass


def _app(metadata: dict, data: _Data, flashed: list) -> Flask:
    application = Flask("bw_ui_before_request_test", root_path=str(REPO / "src" / "ui"))
    application.config.update(
        SECRET_KEY="test",
        CHECK_PRIVATE_IP=False,
        BEFORE_REQUEST_HOOKS=[],
        CONTEXT_PROCESSOR_HOOKS=[],
        EXTRA_PAGES=[],
    )
    init_i18n(application)

    user = SimpleNamespace(
        is_authenticated=True,
        totp_secret=None,
        theme="light",
        language="fr",
        list_permissions=["read", "write"],
        admin=True,
        get_id=lambda: "admin",
    )
    api_client = Mock(readonly=False)
    api_client.get_metadata.return_value = metadata
    api_client.get_user_preferences.return_value = {}
    api_client.get_last_job_run.return_value = None

    namespace = dict(
        app=application,
        request=request,
        session=session,
        g=g,
        jsonify=jsonify,
        make_response=make_response,
        redirect=redirect,
        url_for=url_for,
        Markup=Markup,
        datetime=datetime,
        timedelta=timedelta,
        time=time,
        ip_address=ip_address,
        token_hex=token_hex,
        token_urlsafe=token_urlsafe,
        translated=translated,
        resolve_page_title=resolve_page_title,
        plugin_catalog_fingerprint=plugin_catalog_fingerprint,
        flash=lambda message, category="message", save=True: flashed.append((category, str(message))),
        current_user=user,
        API_CLIENT=api_client,
        BW_CONFIG=Mock(get_plugins=lambda **kwargs: {}, get_config=lambda **kwargs: {}),
        DATA=data,
        LOGGER=getLogger("test"),
        ApiClientError=_ApiError,
        ApiUnavailableError=_ApiError,
        is_static_path=lambda path, *extra: False,
        _host_allowed=lambda host, allowed: True,
        _REQUEST_ID_RE=re.compile(r"[0-9a-f]{16}"),
        perf=Mock(),
        REQUEST_ID=Mock(),
        safe_reload_plugins=Mock(),
        schedule_restart_workers=Mock(),
        GITHUB_METADATA_REFRESH_SECONDS=3600,
        _periodic_tasks_executor=Mock(),
        update_github_metadata=Mock(),
        _SESSION_CLEANUP_INTERVAL_SECONDS=3600,
        _session_cleanup_last_run=0,
        check_api_readonly_state=lambda: None,
        _enforce_session_lifetime=lambda: False,
        MFA_PENDING_ENDPOINTS=frozenset(),
        _sanitize_internal_next=lambda raw, default: default,
        is_session_revoked=lambda session_id: False,
        logout_page=lambda: "logged out",
        SUPPORTED_LANGUAGES=[],
        JOB_DEFERRAL_PREFIX="deferred:",
        billable_service_count=lambda: 0,
        SETTINGS_HUNGRY_PATH_PREFIXES=("/global-settings",),
        ONBOARDING_PREFERENCE_KEY="onboarding",
        PREFERENCE_SESSION_KEYS={"notices": "notices", "cards": "cards", "mode": "mode"},
        DISMISSED_NOTICES_KEY="notices",
        HIDDEN_CARDS_KEY="cards",
        THEME_MODE_KEY="mode",
        load_dismissed_notices=lambda user_id: {},
        load_hidden_home_cards=lambda user_id: [],
        load_theme_mode=lambda user_id: None,
        pending_releases=lambda user_id, version: ((), None),
        is_newer_version_available=lambda current, latest: False,
        catalog_enabled=lambda: True,
        COLUMNS_PREFERENCES_DEFAULTS={},
    )
    _shipped(MAIN, ("before_request", "inject_variables"), namespace)

    application.add_url_rule("/templates", "templates_page", lambda: render_template_string("{{ page_title }}|{{ current_endpoint }}"))
    application.add_url_rule("/templates/<template_id>", "template_page", lambda template_id: render_template_string("{{ page_title }}"))
    return application


def _metadata(**overrides) -> dict:
    return {"pro_overlapped": False, "version": "1.7.0", "failover": False, "failover_message": ""} | overrides


def _get(path: str, *, metadata: dict, data=None, language="fr"):
    flashed = []
    application = _app(metadata, data if data is not None else _Data(LATEST_VERSION_LAST_CHECK=datetime.now().astimezone().isoformat()), flashed)
    client = application.test_client()
    with client.session_transaction() as flask_session:
        flask_session["language"] = language
    response = client.get(path, environ_base={"REMOTE_ADDR": "127.0.0.1"}, headers={"User-Agent": "pytest"})
    return response, flashed


# ------------------------------------------------------------------------------ Q6-M1 tab title


@pytest.mark.parametrize("language", ["fr", "de"])
def test_an_authenticated_list_page_gets_a_translated_title(language):
    response, _ = _get("/templates", metadata=_metadata(), language=language)

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_data(as_text=True) == f"{_catalog_value(language, 'navigation.templates')}|templates"


def test_an_authenticated_detail_page_gets_its_list_pages_title():
    response, _ = _get("/templates/011d056e-403a", metadata=_metadata())

    assert response.get_data(as_text=True) == _catalog_value("fr", "navigation.templates")


# ------------------------------------------------------------------------------ M18 failover banner


def _failover_flashes(flashed):
    banner = translated("main.flash.failover_configuration_error") or "configuration error on NGINX"
    return [content for _, content in flashed if banner in content or "Failover" in content or "basculement" in content]


def test_a_failover_without_a_message_is_not_shown_as_an_nginx_error():
    _, flashed = _get("/templates", metadata=_metadata(failover=True, failover_message=""))

    assert not _failover_flashes(flashed), flashed


def test_a_real_failover_still_shows_nginx_output():
    _, flashed = _get("/templates", metadata=_metadata(failover=True, failover_message='nginx: [emerg] unknown directive "foo"'))

    assert any("unknown directive" in content for _, content in flashed), flashed
    assert all(category == "error" for category, _ in flashed), flashed


def test_a_failover_message_wins_over_changes_ongoing():
    # push-configs keeps exiting 2 (custom_configs_changed stays 1) while the refused config is retried:
    # the operator must see NGINX's text, not only the generic "could not be applied".
    response, flashed = _get(
        "/templates",
        metadata=_metadata(failover=True, failover_message='nginx: [emerg] unknown directive "foo"', custom_configs_changed=True),
    )

    assert any("unknown directive" in content for _, content in flashed), flashed


def test_an_applied_change_is_reported_when_the_flag_has_no_message():
    data = _Data(LATEST_VERSION_LAST_CHECK=datetime.now().astimezone().isoformat(), CONFIG_CHANGED=True)
    _, flashed = _get("/templates", metadata=_metadata(failover=True, failover_message=""), data=data)

    assert [category for category, _ in flashed] == ["message"], flashed
    assert data["CONFIG_CHANGED"] is False
