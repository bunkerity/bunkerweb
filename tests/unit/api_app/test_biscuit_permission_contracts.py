"""Signed grants bind persisted resource/permission vocabularies and fail closed on bad tokens."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from biscuit_auth import Biscuit, BiscuitBuilder, BlockBuilder, KeyPair
from fastapi import HTTPException
import pytest

from _api_http_helpers import VERSION, _KEYPAIR
from test_biscuit_run_limit import make_request
from test_configs_move_authz import _token

import app.auth.biscuit as biscuit
from model import API_PERMISSION_ENUM, API_RESOURCE_ENUM


@pytest.fixture
def guard_config(monkeypatch):
    config = SimpleNamespace(API_ROOT_PATH=None, openapi_url=None, docs_url=None, redoc_url=None, biscuit_ttl_seconds=60, check_private_ip=True)
    monkeypatch.setattr(biscuit, "api_config", config)
    return config


PERMISSIONS = [
    ("/bans", "GET", "bans", "ban_read"),
    ("/bans", "POST", "bans", "ban_created"),
    ("/bans", "DELETE", "bans", "ban_delete"),
    ("/bans/ban", "POST", "bans", "ban_created"),
    ("/bans/unban", "POST", "bans", "ban_delete"),
    ("/instances/health", "GET", "instances", "instances_read"),
    ("/instances/ping", "OPTIONS", "instances", "instances_read"),
    ("/instances/node/ping", "OPTIONS", "instances", "instances_read"),
    ("/reload", "POST", "instances", "instances_execute"),
    ("/stop", "POST", "instances", "instances_execute"),
    ("/instances/node/reload", "POST", "instances", "instances_execute"),
    ("/instances/node/stop", "POST", "instances", "instances_execute"),
    ("/services/export", "GET", "services", "service_export"),
    ("/services/example/convert", "POST", "services", "service_convert"),
    ("/configs", "OPTIONS", "configs", "configs_read"),
    ("/configs/global/http/snippet", "OPTIONS", "configs", "config_read"),
    ("/configs/upload", "POST", "configs", "config_create"),
    ("/plugins/upload", "POST", "plugins", "plugin_create"),
    ("/plugins/p", "DELETE", "plugins", "plugin_delete"),
    ("/jobs", "GET", "jobs", "job_read"),
    ("/jobs/errors", "GET", "jobs", "job_read"),
    ("/jobs/run", "POST", "jobs", "job_run"),
    ("/cache/global/p/j/file", "GET", "cache", "cache_read"),
    ("/cache/global/p/j/file", "DELETE", "cache", "cache_delete"),
    ("/crowdsec/connections", "GET", "bans", "crowdsec_read"),
    ("/crowdsec/conn/decisions", "DELETE", "bans", "crowdsec_delete"),
]
for _path in ("/global_settings", "/global_config"):
    for _method in ("GET", "OPTIONS", "POST", "PUT", "PATCH"):
        PERMISSIONS.append((_path, _method, "global_config", "global_config_read" if _method in {"GET", "OPTIONS"} else "global_config_update"))
for _root, _resource, _mapping in [
    ("bans", "bans", {"GET": "ban_read", "POST": "ban_created", "PUT": "ban_update", "DELETE": "ban_delete"}),
    ("instances", "instances", {"GET": "instances_read", "POST": "instances_create", "PUT": "instances_update", "DELETE": "instances_delete"}),
    ("services", "services", {"GET": "service_read", "POST": "service_create", "PUT": "service_update", "DELETE": "service_delete"}),
    ("configs", "configs", {"GET": "config_read", "POST": "config_create", "PUT": "config_update", "DELETE": "config_delete"}),
    ("plugins", "plugins", {"GET": "plugin_read", "POST": "plugin_create", "PUT": "plugin_create", "DELETE": "plugin_delete"}),
]:
    for _method, _permission in _mapping.items():
        PERMISSIONS.append((f"/{_root}/example/extra", _method, _resource, _permission))


@pytest.mark.parametrize("path,method,resource,permission", PERMISSIONS)
@pytest.mark.parametrize("grant", [True, False])
def test_signed_grant_matches_both_persisted_vocabularies(guard_config, path, method, resource, permission, grant):
    assert resource in API_RESOURCE_ENUM.enums
    assert permission in API_PERMISSION_ENUM.enums
    assert biscuit._resolve_resource_and_perm(path, method) == (resource, permission)
    signed = _token((resource, "*", permission if grant else "unrelated_permission"))
    req = make_request(signed, path, method)
    if grant:
        assert biscuit.guard(req) is None
        assert isinstance(req.state.biscuit_token, Biscuit)
    else:
        with pytest.raises(HTTPException) as caught:
            biscuit.guard(req)
        assert (caught.value.status_code, caught.value.detail) == (403, "Forbidden")


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/global_settings",
        "/global_config",
        "/cache",
        "/jobs/run",
        "/bans",
        "/instances/node",
        "/services/example",
        "/configs/example/http/x",
        "/plugins/p",
    ],
)
@pytest.mark.parametrize("permitted", [True, False])
def test_unmapped_method_requires_coarse_permission(guard_config, path, permitted):
    # TRACE has no fine-grained verb. Coarse read permission remains required.
    signed = (
        BiscuitBuilder(
            'version({version}); time({now}); client_ip("127.0.0.1"); role("api_user", {operations});',
            {"version": VERSION, "now": datetime.now(timezone.utc), "operations": {"read"} if permitted else {"write"}},
        )
        .build(_KEYPAIR.private_key)
        .to_base64()
    )
    if permitted:
        assert biscuit.guard(make_request(signed, path, "TRACE")) is None
    else:
        with pytest.raises(HTTPException) as caught:
            biscuit.guard(make_request(signed, path, "TRACE"))
        assert (caught.value.status_code, caught.value.detail) == (403, "Forbidden")


@pytest.mark.parametrize(
    "path,resource,expected",
    [
        ("", "services", None),
        ("/services/example", None, None),
        ("services/example", "services", "example"),
        ("/services/export", "services", None),
        ("/services/convert", "services", None),
        ("/plugins/upload", "plugins", None),
        ("/configs/upload", "configs", None),
        ("/jobs/errors", "jobs", None),
        ("/jobs/run", "jobs", None),
        ("/instances/reload", "instances", None),
        ("/instances/stop", "instances", None),
        ("/global_settings", "global_config", None),
        ("/bans/ban", "bans", None),
        ("/cache/global/plugin/job/file", "cache", "global"),
    ],
)
def test_action_segments_cannot_be_misread_as_resource_ids(path, resource, expected):
    assert biscuit._extract_resource_id(path, resource) == expected


@pytest.mark.parametrize(
    "path,method,expected",
    [
        ("services/example/", "get", ("services", "service_read")),
        ("future/item", "GET", ("future", "future_read")),
        ("/future", "TRACE", ("future", None)),
        ("/", "GET", (None, None)),
        ("/jobs/extra", "GET", ("jobs", "job_read")),
        ("/jobs/extra", "POST", ("jobs", None)),
        ("/global_settings", "DELETE", ("global_config", None)),
    ],
)
def test_path_normalization_and_unmapped_fallbacks(path, method, expected):
    assert biscuit._resolve_resource_and_perm(path, method) == expected


@pytest.mark.parametrize("bad", ["garbage", "", "Bearer", "a.b.c", "////", "Basic YTpi"])
def test_malformed_tokens_fail_before_resource_authorization(guard_config, bad):
    with pytest.raises(HTTPException) as caught:
        biscuit.guard(make_request(bad))
    assert (caught.value.status_code, caught.value.detail) == (401, "Unauthorized")


def test_wrong_signing_key_is_refused(guard_config):
    token = BiscuitBuilder("version({version}); admin(true);", {"version": VERSION}).build(KeyPair().private_key).to_base64()
    with pytest.raises(HTTPException) as caught:
        biscuit.guard(make_request(token))
    assert (caught.value.status_code, caught.value.detail) == (401, "Unauthorized")


@pytest.mark.parametrize("code", ["check if true;", 'api_perm("configs", "*", "config_update");'])
def test_even_benign_attenuation_is_refused_before_datalog(guard_config, monkeypatch, code):
    token = Biscuit.from_base64(_token(admin=True), _KEYPAIR.public_key)
    block = BlockBuilder()
    block.add_code(code)
    token = token.append(block).to_base64()
    builder = Mock(side_effect=AssertionError("attenuated token reached Datalog"))
    monkeypatch.setattr(biscuit, "AuthorizerBuilder", builder)
    with pytest.raises(HTTPException) as caught:
        biscuit.guard(make_request(token))
    assert (caught.value.status_code, caught.value.detail) == (401, "Unauthorized")
    builder.assert_not_called()


@pytest.mark.parametrize("phase,code", [("parse", 401), ("freshness", 401), ("permission", 403), ("destination", 403)])
def test_unexpected_library_failures_remain_denials(guard_config, monkeypatch, phase, code):
    req = make_request(_token(admin=True))
    if phase == "parse":
        monkeypatch.setattr(biscuit, "Biscuit", SimpleNamespace(from_base64=Mock(side_effect=RuntimeError("parse failed"))))
    elif phase == "destination":
        req.state.biscuit_token = object()
        monkeypatch.setattr(biscuit, "AuthorizerBuilder", Mock(side_effect=RuntimeError("build failed")))
    else:
        real_builder = biscuit.AuthorizerBuilder
        builder = Mock(side_effect=[real_builder(), RuntimeError("build failed")]) if phase == "permission" else Mock(side_effect=RuntimeError("build failed"))
        monkeypatch.setattr(biscuit, "AuthorizerBuilder", builder)
    with pytest.raises(HTTPException) as caught:
        if phase == "destination":
            biscuit.authorize_resource(req, "configs", "config_update", "example")
        else:
            biscuit.guard(req)
    assert (caught.value.status_code, caught.value.detail) == (code, "Unauthorized" if code == 401 else "Forbidden")


@pytest.mark.parametrize("path", ["/health", "/ping", "/auth", "/openapi.json", "/docs/oauth2-redirect", "/redoc"])
def test_public_biscuit_paths_skip_verification_under_root_prefix(guard_config, monkeypatch, path):
    guard_config.API_ROOT_PATH = "/api"
    guard_config.openapi_url, guard_config.docs_url, guard_config.redoc_url = "/openapi.json", "/docs", "/redoc"
    verifier = Mock(side_effect=AssertionError("public endpoint parsed token"))
    monkeypatch.setattr(biscuit, "Biscuit", SimpleNamespace(from_base64=verifier))
    assert biscuit.guard(make_request("bad", "/api" + path)) is None
    verifier.assert_not_called()


def test_missing_client_is_bound_to_unspecified_ip(guard_config):
    signed = (
        BiscuitBuilder(
            'version({version}); time({now}); client_ip("0.0.0.0"); admin(true);',
            {"version": VERSION, "now": datetime.now(timezone.utc)},
        )
        .build(_KEYPAIR.private_key)
        .to_base64()
    )
    req = make_request(signed)
    req.client = None
    assert biscuit.guard(req) is None


@pytest.mark.parametrize("age,allowed", [(59, True), (60, True), (61, False)])
def test_ttl_boundary_is_inclusive(guard_config, monkeypatch, age, allowed):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(biscuit, "datetime", SimpleNamespace(now=lambda _: now))
    token = (
        BiscuitBuilder(
            'version({version}); time({issued}); client_ip("127.0.0.1"); admin(true);',
            {"version": VERSION, "issued": now - timedelta(seconds=age)},
        )
        .build(_KEYPAIR.private_key)
        .to_base64()
    )
    if allowed:
        assert biscuit.guard(make_request(token)) is None
    else:
        with pytest.raises(HTTPException) as caught:
            biscuit.guard(make_request(token))
        assert (caught.value.status_code, caught.value.detail) == (401, "Unauthorized")


def test_invalid_key_file_fails_closed_even_if_debug_logging_fails(guard_config, monkeypatch, tmp_path):
    path = tmp_path / "public.key"
    path.write_text("invalid")
    monkeypatch.setattr(biscuit, "BISCUIT_PUBLIC_KEY_FILE", path)
    monkeypatch.setattr(biscuit.guard._logger, "debug", Mock(side_effect=RuntimeError("logging failed")))
    with pytest.raises(RuntimeError, match="Failed to load Biscuit public key"):
        biscuit.BiscuitGuard()
