"""Rate rule formats, matching, client keys and storage options stay predictable."""

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from test_rate_limit_once import _load_rate_limit


@pytest.fixture
def rules(monkeypatch):
    for name in (
        "USE_REDIS",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_DATABASE",
        "REDIS_TIMEOUT",
        "REDIS_KEEPALIVE_POOL",
        "REDIS_USERNAME",
        "REDIS_PASSWORD",
        "REDIS_SSL",
        "REDIS_SSL_VERIFY",
        "REDIS_SENTINEL_HOSTS",
        "REDIS_SENTINEL_MASTER",
        "REDIS_SENTINEL_USERNAME",
        "REDIS_SENTINEL_PASSWORD",
        "REDIS_CLUSTER_NODES",
    ):
        monkeypatch.delenv(name, raising=False)
    return _load_rate_limit(monkeypatch)


def request(ip="192.0.2.9", **headers):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "client": (ip, 1) if ip else None,
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        }
    )


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("3r/s", (3, 1)),
        ("40r/m", (40, 60)),
        ("200r/h", (200, 3600)),
        ("4/d", (4, 86400)),
        ("10 per hour", (10, 3600)),
        ("500/7days", (500, 604800)),
        ("200 per 30 minutes", (200, 1800)),
        ("100/60", (100, 60)),
        ("5/month", (5, 2592000)),
        ("2/years", (2, 31536000)),
    ],
)
def test_rate_notations_resolve_to_count_and_seconds(rules, raw, expected):
    assert rules._parse_rate(raw) == expected


@pytest.mark.parametrize("raw", ["10", "a/hour", "10/bananas", "3/1.5minutes"])
def test_bad_rate_raises_value_error(rules, raw):
    with pytest.raises(ValueError):
        rules._parse_rate(raw)


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (1, "5/second"),
        (60, "5/minute"),
        (3600, "5/hour"),
        (86400, "5/day"),
        (2592000, "5/month"),
        (31536000, "5/year"),
        (120, "5/2minutes"),
        (17, "5 per 17 seconds"),
    ],
)
def test_limit_string_preserves_arbitrary_periods(rules, seconds, expected):
    assert rules._limit_string(5, seconds) == expected


@pytest.mark.parametrize("value", [None, "", "  "])
def test_absent_rules_are_empty(rules, value):
    assert rules._load_rules(value) == []


@pytest.mark.parametrize(
    "source",
    [
        [{"path": "/things/*", "methods": ["get", "post"], "rate": "7/2minutes"}, "ignored"],
        {"GET|POST /things/*": "7/2minutes"},
        '[{"path":"/things/*","methods":"GET|POST","times":7,"seconds":120}]',
        '"GET|POST /things/* 7/2minutes"; "bad rule"',
        "- path: /things/*\n  methods: GET|POST\n  rate: 7/2minutes\n",
    ],
)
def test_rule_sources_match_only_configured_methods_and_paths(rules, source, monkeypatch):
    loaded = rules._load_rules(source)
    assert len(loaded) == 1
    assert loaded[0].raw
    monkeypatch.setattr(rules, "_rules", loaded)
    monkeypatch.setattr(rules.api_config, "API_ROOT_PATH", "/api")
    assert rules._match_rule(" get ", "/things/one") == "7/2minutes"
    assert rules._match_rule("POST", "/api/things/two") == "7/2minutes"
    assert rules._match_rule("DELETE", "/things/one") is None
    assert rules._match_rule("GET", "/other") is None


def test_rule_file_and_regex_path(rules, tmp_path, monkeypatch):
    path = tmp_path / "rules.yml"
    path.write_text('- path: "re:^/items/[0-9]+$"\n  rate: 2r/s\n')
    monkeypatch.setattr(rules, "_rules", rules._load_rules(str(path)))
    assert rules._match_rule("PATCH", "/items/12") == "2/second"
    assert rules._match_rule("GET", "/items/letters") is None
    path.write_text("")
    assert rules._load_rules(str(path)) == []


def test_unreadable_rule_file_warns_and_disables_rules(rules, tmp_path, monkeypatch, caplog):
    path = tmp_path / "rules.yml"
    path.write_text("anything")
    monkeypatch.setattr(rules.Path, "read_text", lambda *a, **kw: (_ for _ in ()).throw(OSError("unreadable")))
    assert rules._load_rules(str(path)) == []
    assert "Cannot read rate limit rules file" in caplog.text


def test_csv_quotes_and_blank_fields(rules):
    assert rules._csv_items('"GET /a,b 2r/s"; ;"POST /c 3r/m"') == ["GET /a,b 2r/s", "POST /c 3r/m"]
    assert rules._csv_items("") == []
    assert rules._rules_from_string("garbage,GET /ok 3r/s")[-1].limit_string == "3/second"
    assert rules._load_rules(42) == []


def test_rate_defaults_disable_and_invalid_fallback(rules, caplog):
    assert rules._resolve_rate(None, 9, 60, label="base") == (9, 60)
    assert rules._resolve_rate("", 9, 60, label="base") == (9, 60)
    assert rules._resolve_rate("OFF", 9, 60, label="auth", allow_disable=True) is None
    assert rules._resolve_rate("bogus", 9, 60, label="base") == (9, 60)
    assert "Invalid base 'bogus'" in caplog.text


@pytest.mark.parametrize(
    "selector,headers,expected",
    [
        ("ip", {}, "192.0.2.9"),
        ("ip_ua", {"user-agent": "agent"}, "192.0.2.9|agent"),
        ("header:X-Client", {"x-client": "customer"}, "customer"),
        ("header:X-Client", {}, "192.0.2.9"),
        ("unknown", {}, "192.0.2.9"),
    ],
)
def test_client_key_selection(rules, monkeypatch, selector, headers, expected):
    monkeypatch.setattr(rules.api_config, "API_RATE_LIMIT_KEY", selector)
    assert rules._build_key_func()(request(**headers)) == expected


def test_exempt_networks_accept_v4_v6_and_ignore_bad_entries(rules, monkeypatch):
    networks = rules._parse_exempt_ips("192.0.2.0/24, 2001:db8::1 invalid 198.51.100.8")
    assert list(map(str, networks)) == ["192.0.2.0/24", "2001:db8::1/128", "198.51.100.8/32"]
    monkeypatch.setattr(rules, "_exempt_networks", networks)
    assert rules._is_exempt(request())
    assert rules._is_exempt(request("2001:db8::1"))
    assert not rules._is_exempt(request("203.0.113.1"))
    assert not rules._is_exempt(request("not-an-ip"))
    assert rules._client_identifier(request(None)) == "0.0.0.0"
    assert rules._parse_exempt_ips(None) == []


def test_auth_limit_applies_only_to_post_auth_with_root_path(rules, monkeypatch):
    monkeypatch.setattr(rules, "_auth_limit", "2/minute")
    monkeypatch.setattr(rules.api_config, "API_ROOT_PATH", "/api/")
    assert rules._auth_default_limit("POST", "/api/auth/") == "2/minute"
    assert rules._auth_default_limit("GET", "/auth") is None
    assert rules._auth_default_limit("POST", "/elsewhere") is None
    monkeypatch.setattr(rules, "_auth_limit", None)
    assert rules._auth_default_limit("POST", "/auth") is None


def test_direct_redis_uses_env_over_db_and_keeps_custom_options(rules, monkeypatch):
    monkeypatch.setattr(rules.api_config, "API_RATE_LIMIT_STORAGE_OPTIONS", '{"max_connections":4}')
    monkeypatch.setenv("REDIS_HOST", "environment")
    uri, options = rules._build_storage(
        {
            "USE_REDIS": "yes",
            "REDIS_HOST": "database",
            "REDIS_SSL": "yes",
            "REDIS_USERNAME": "user",
            "REDIS_PASSWORD": "fixture",
            "REDIS_TIMEOUT": "2500",
            "REDIS_DATABASE": "2",
        }
    )
    assert uri == "rediss://user:fixture@environment:6379/2"
    assert options == {"socket_timeout": 2.5, "socket_connect_timeout": 2.5, "socket_keepalive": True, "max_connections": 4}


def test_sentinel_separates_redis_and_sentinel_credentials(rules):
    uri, options = rules._build_storage(
        {
            "USE_REDIS": "yes",
            "REDIS_SENTINEL_HOSTS": "s1 s2:26380",
            "REDIS_SENTINEL_MASTER": "master",
            "REDIS_USERNAME": "redis-user",
            "REDIS_PASSWORD": "redis-fixture",
            "REDIS_SSL": "yes",
            "REDIS_SENTINEL_USERNAME": "sentinel-user",
            "REDIS_SENTINEL_PASSWORD": "sentinel-fixture",
        }
    )
    assert uri == "redis+sentinel://s1:26379,s2:26380/master"
    assert options["username"] == "redis-user" and options["password"] == "redis-fixture"
    assert options["sentinel_kwargs"] == {
        "socket_timeout": 1.0,
        "socket_connect_timeout": 1.0,
        "socket_keepalive": True,
        "ssl": True,
        "username": "sentinel-user",
        "password": "sentinel-fixture",
    }


@pytest.mark.parametrize(
    "nodes,expected", [("[2001:db8::1]:6379 cache:6380", "redis+cluster://[2001:db8::1]:6379"), ("cache cache2:6380", "redis+cluster://cache:6379")]
)
def test_cluster_nodes_are_passed_as_options_without_network(rules, nodes, expected):
    uri, options = rules._build_storage(
        {"USE_REDIS": "yes", "REDIS_CLUSTER_NODES": nodes, "REDIS_SSL": "yes", "REDIS_SSL_VERIFY": "no", "REDIS_USERNAME": "u", "REDIS_PASSWORD": "fixture"}
    )
    assert uri == expected
    assert len(options["startup_nodes"]) == 2
    assert options["ssl"] is True and options["ssl_cert_reqs"] == "none"
    assert options["password"] == "fixture" and options["username"] == "u"


@pytest.mark.parametrize(
    "extra",
    [
        {"REDIS_CLUSTER_NODES": "cache:invalid"},
        {"REDIS_CLUSTER_NODES": "cache", "REDIS_DATABASE": "1"},
        {"REDIS_CLUSTER_NODES": "cache", "REDIS_SENTINEL_HOSTS": "sentinel"},
        {"REDIS_HOST": ""},
    ],
)
def test_unusable_redis_falls_back_to_memory(rules, extra):
    uri, _ = rules._build_storage({"USE_REDIS": "yes", "REDIS_TIMEOUT": "invalid", "REDIS_KEEPALIVE_POOL": "invalid", **extra})
    assert uri == "memory://"


def test_disabled_setup_leaves_app_without_limiter(rules, monkeypatch):
    monkeypatch.setattr(rules.api_config, "rate_limit_enabled", False)
    application = SimpleNamespace(state=SimpleNamespace())
    rules.setup_rate_limiter(application)
    assert not hasattr(application.state, "limiter")
    assert not rules.is_enabled()
