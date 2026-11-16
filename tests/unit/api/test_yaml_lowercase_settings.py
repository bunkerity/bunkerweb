"""YAML aliases retain their existing precedence without mutating an iterator."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = spec_from_file_location("bw_yaml_settings", ROOT / "src/api/app/yaml_base_settings.py")
YAML = module_from_spec(SPEC)
SPEC.loader.exec_module(YAML)


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        ("API_PORT: 5001\n", 5001),
        ("api_port: 5002\n", 5002),
        ("Api_Port: 5003\n", 5003),
        ("api_port: 5004\nAPI_PORT: 5005\n", 5004),
        ("API_PORT: 5005\napi_port: 5004\n", 5004),
    ],
)
def test_yaml_normalizes_keys_without_changing_alias_precedence(tmp_path, document, expected):
    path = tmp_path / "api.yml"
    path.write_text(document)

    class Settings(YAML.YamlBaseSettings):
        API_PORT: int = 5000
        model_config = YAML.YamlSettingsConfigDict(yaml_file=str(path), secrets_dir=str(tmp_path), extra="ignore")

    assert Settings().API_PORT == expected


def test_env_still_takes_precedence_over_lowercase_yaml(tmp_path, monkeypatch):
    path = tmp_path / "api.yml"
    path.write_text("api_port: 5002\n")
    monkeypatch.setenv("API_PORT", "5006")

    class Settings(YAML.YamlBaseSettings):
        API_PORT: int = 5000
        model_config = YAML.YamlSettingsConfigDict(yaml_file=str(path), secrets_dir=str(tmp_path), extra="ignore")

    assert Settings().API_PORT == 5006
