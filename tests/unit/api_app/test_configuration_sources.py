"""Configuration precedence, secret substitution and typed compatibility properties."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic_settings import SettingsConfigDict

from _api_http_helpers import VERSION  # noqa: F401 - import bootstrap

from app.config import ApiConfig
import app.utils as utils
from app.yaml_base_settings import YamlBaseSettings, replace_secrets, yaml_config_settings_source


@pytest.fixture
def config_type(tmp_path, monkeypatch):
    yaml = tmp_path / "api.yml"
    yaml.write_text("{}\n")
    env = tmp_path / "api.env"
    env.write_text("")
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    for name in ApiConfig.model_fields:
        monkeypatch.delenv(name, raising=False)

    class LocalConfig(ApiConfig):
        model_config = SettingsConfigDict(yaml_file=str(yaml), env_file=str(env), secrets_dir=str(secrets))

    return LocalConfig, yaml, env, secrets


def test_config_precedence_init_env_secret_yaml_dotenv_defaults(config_type, monkeypatch):
    cls, yaml, env, secrets = config_type
    env.write_text("API_TOKEN=dotenv\n")
    assert cls().API_TOKEN == "dotenv"
    yaml.write_text("API_TOKEN: yaml\n")
    assert cls().API_TOKEN == "yaml"
    (secrets / "API_TOKEN").write_text("secret")
    assert cls().API_TOKEN == "secret"
    monkeypatch.setenv("API_TOKEN", "environment")
    assert cls().API_TOKEN == "environment"
    assert cls(API_TOKEN="explicit").API_TOKEN == "explicit"


@pytest.mark.parametrize("value,expected", [("YES", True), ("on", True), ("1", True), (True, True), ("no", False), ("disabled", False), (False, False)])
def test_compatibility_boolean_properties(config_type, value, expected):
    cls, *_ = config_type
    cfg = cls(CHECK_PRIVATE_IP=value, API_WHITELIST_ENABLED=value, API_RATE_LIMIT_ENABLED=value, API_RATE_LIMIT_HEADERS_ENABLED=value)
    assert (cfg.check_private_ip, cfg.whitelist_enabled, cfg.rate_limit_enabled, cfg.rate_limit_headers_enabled) == (expected,) * 4


@pytest.mark.parametrize("value,expected", [("off", 0), ("", 0), ("-9", 0), ("2.5", 2), ("garbage", 3600), (123, 123)])
def test_biscuit_ttl_normalization(config_type, value, expected):
    cls, *_ = config_type
    assert cls(API_BISCUIT_TTL_SECONDS=value).biscuit_ttl_seconds == expected


@pytest.mark.parametrize("value,expected", [(None, "/docs"), ("off", None), ("", None), (" /custom ", " /custom ")])
def test_documentation_urls_can_be_disabled(config_type, value, expected):
    cls, *_ = config_type
    cfg = cls(API_DOCS_URL=value, API_REDOC_URL=value, API_OPENAPI_URL=value)
    assert cfg.docs_url == expected
    assert cfg.redoc_url == ("/redoc" if value is None else expected)
    assert cfg.openapi_url == ("/openapi.json" if value is None else expected)


def test_allowed_hosts_parse_and_internal_db_fallbacks(config_type, monkeypatch):
    cls, *_ = config_type
    db = Mock()
    db.get_config.return_value = {"API_HTTP_PORT": "8080", "API_SERVER_NAME": "internal"}
    monkeypatch.setattr(utils, "get_db", lambda **_: db)
    cfg = cls(API_ALLOWED_HOSTS="example.com, *.example.net\napi.test")
    assert cfg.allowed_hosts == ["example.com", "*.example.net", "api.test"]
    assert cfg.internal_api_port == "8080"
    assert cfg.internal_api_host_header == "internal"
    assert cfg.internal_endpoint == "http://127.0.0.1:8080"
    db.get_config.side_effect = RuntimeError("unavailable")
    assert cfg.internal_api_port == "5000" and cfg.internal_api_host_header == "bwapi"
    assert cls().allowed_hosts == []


def test_yaml_secret_substitution_sections_and_missing_secret(tmp_path, capsys):
    (tmp_path / "token").write_text("fixture-value")
    document = "TOKEN: <file:token>\nMISSING: <file:missing>\n"
    substituted = replace_secrets(tmp_path, document)
    assert substituted == "TOKEN: fixture-value\nMISSING: <file:missing>\n"
    assert "Secret file referenced in yaml file not found" in capsys.readouterr().out
    path = tmp_path / "config.yml"
    path.write_text("api:\n  TOKEN: <file:token>\nother: 3\n")
    settings = SimpleNamespace(model_config={"yaml_file": str(path), "secrets_dir": str(tmp_path), "yaml_config_section": "api"})
    assert yaml_config_settings_source(settings) == {"TOKEN": "fixture-value"}
    assert yaml_config_settings_source(settings, yaml_config_section="absent") == {"api": {"TOKEN": "fixture-value"}, "other": 3}
    path.write_text("")
    assert yaml_config_settings_source(settings) == {}


def test_missing_yaml_and_missing_configuration_fail_explicitly(tmp_path):
    with pytest.raises(FileNotFoundError, match="Could not open yaml settings"):
        yaml_config_settings_source(SimpleNamespace(model_config={"yaml_file": str(tmp_path / "missing"), "secrets_dir": str(tmp_path)}))
    with pytest.raises(AssertionError, match="yaml_file"):
        yaml_config_settings_source(SimpleNamespace(model_config={}))


def test_lowercase_yaml_keys_are_case_insensitive(config_type):
    cls, yaml, *_ = config_type
    yaml.write_text("api_token: from-lowercase\n")
    assert cls().API_TOKEN == "from-lowercase"


def test_generic_yaml_settings_support_typed_values(tmp_path):
    yaml = tmp_path / "settings.yml"
    yaml.write_text("COUNT: 7\nNAMES: [one, two]\n")

    class Settings(YamlBaseSettings):
        COUNT: int = 1
        NAMES: list[str] = []
        model_config = SettingsConfigDict(yaml_file=str(yaml), env_file=None, secrets_dir=str(tmp_path))

    cfg = Settings()
    assert cfg.COUNT == 7 and cfg.NAMES == ["one", "two"]
