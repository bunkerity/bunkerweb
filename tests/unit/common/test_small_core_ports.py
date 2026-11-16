"""Regressions for the small core ports from dev."""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Template

import common_utils

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src/common/core"


def test_low_template_allows_cross_origin_embeds():
    template = json.loads((CORE / "templates/templates/low.json").read_text())
    assert template["settings"].get("CROSS_ORIGIN_EMBEDDER_POLICY") == "unsafe-none"
    assert any("CROSS_ORIGIN_EMBEDDER_POLICY" in step["settings"] for step in template["steps"])


def test_permissions_policy_defaults_agree():
    policy = json.loads((CORE / "headers/plugin.json").read_text())["settings"]["PERMISSIONS_POLICY"]["default"]
    assert "unbounded-element=()" in policy
    for name in ("high", "medium"):
        assert json.loads((CORE / f"templates/templates/{name}.json").read_text())["settings"]["PERMISSIONS_POLICY"] == policy
    for path in (
        CORE / "errors/errors.lua",
        ROOT / "src/common/confs/default-server-http.conf",
        CORE / "misc/confs/default-server-http/page.conf",
    ):
        assert policy in path.read_text(), path
    # UI grants these capabilities to its own pages (fullscreen, passkeys and wake lock).
    ui_policy = policy
    for feature in ("fullscreen", "publickey-credentials-create", "publickey-credentials-get", "screen-wake-lock"):
        ui_policy = ui_policy.replace(f"{feature}=()", f"{feature}=(self)")
    assert ui_policy in (ROOT / "src/ui/main.py").read_text()


@pytest.mark.parametrize("subsystem", ["http", "stream"])
@pytest.mark.parametrize("mode,enabled,expected", [("detect", "yes", "on"), ("block", "yes", "off"), ("detect", "no", None)])
def test_connection_limits_detect_mode(subsystem, mode, enabled, expected):
    source = (CORE / f"limit/confs/server-{subsystem}/limitconn.conf").read_text()
    rendered = Template(source).render(
        USE_LIMIT_CONN=enabled,
        SECURITY_MODE=mode,
        LIMIT_CONN_MAX_HTTP1=10,
        LIMIT_CONN_MAX_HTTP2=100,
        LIMIT_CONN_MAX_HTTP3=100,
        LIMIT_CONN_MAX_STREAM=10,
    )
    if expected is None:
        assert "limit_conn" not in rendered
    else:
        assert f"limit_conn_dry_run {expected};" in rendered
        assert "limit_conn " in rendered


@pytest.mark.parametrize("level", ["WARNING", "DEBUG"])
def test_sqlalchemy_children_inherit_database_level(level):
    script = """
import logging
import logger
parent = logging.getLogger('sqlalchemy')
child = logging.getLogger('sqlalchemy.orm.strategies.SelectInLoader')
assert child.getEffectiveLevel() == parent.getEffectiveLevel() == logging._nameToLevel[LEVEL]
assert logging.getLogger('application').getEffectiveLevel() == logging.INFO
""".replace("LEVEL", repr(level))
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src/common/utils"), "DATABASE_LOG_LEVEL": level, "LOG_LEVEL": "INFO"},
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("auth", [True, False])
@pytest.mark.parametrize("tls", [True, False])
def test_sentinel_nodes_receive_their_own_auth_and_tls(monkeypatch, auth, tls):
    calls = {}

    class Sentinel:
        def __init__(self, hosts, **kwargs):
            calls.update(kwargs)

        def master_for(self, name, **kwargs):
            calls["master"] = kwargs
            return SimpleNamespace(ping=lambda: True)

        def discover_master(self, name):
            return "redis", 6379

    import redis

    monkeypatch.setattr(redis, "Sentinel", Sentinel)
    monkeypatch.setattr(common_utils, "_REDIS_CLIENT_ENTRY", None)
    client = common_utils.get_redis_client(
        use_redis=True,
        redis_sentinel_hosts=[("sentinel", 26379)],
        redis_sentinel_master="master",
        redis_sentinel_username="sentinel-user" if auth else None,
        redis_sentinel_password="sentinel-pass" if auth else None,
        redis_username="data-user",
        redis_password="data-pass",
        redis_ssl=tls,
        redis_ssl_ca="/ca.pem" if tls else None,
        redis_timeout=250,
    )
    assert client is not None
    options = calls["sentinel_kwargs"]
    assert options["ssl"] is tls
    assert options["socket_timeout"] == options["socket_connect_timeout"] == 0.25
    assert options["socket_keepalive"] is True
    assert options.get("username") == ("sentinel-user" if auth else None)
    assert options.get("password") == ("sentinel-pass" if auth else None)
    if tls:
        assert options["ssl_ca_certs"] == "/ca.pem"
    assert calls["master"]["username"] == "data-user"
    assert calls["master"]["password"] == "data-pass"
