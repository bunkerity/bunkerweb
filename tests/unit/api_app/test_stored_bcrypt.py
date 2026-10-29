"""Malformed stored credentials fail closed without skipping bcrypt work."""

from unittest.mock import Mock

from bcrypt import checkpw
import pytest

import app.utils as utils
from app.models.models import UiUsers


def test_invalid_api_hash_is_refused_with_warning_and_bcrypt_work(monkeypatch):
    logger = Mock()
    checks = Mock(wraps=checkpw)
    monkeypatch.setattr(utils, "LOGGER", logger)
    monkeypatch.setattr(utils, "checkpw", checks)
    assert utils.check_password("private-password", b"private-invalid-hash") is False
    logger.warning.assert_called_once()
    assert "private" not in str(logger.warning.call_args)
    assert checks.call_count == 2
    assert checks.call_args.args[1].startswith(b"$2b$13$")


def test_api_user_model_refuses_invalid_hash():
    user = UiUsers(username="alice", password="invalid-stored-hash")
    assert user.check_password("private-password") is False


@pytest.mark.parametrize("document", ["api_token: lower\nAPI_TOKEN: upper\n", "API_TOKEN: upper\napi_token: lower\n"])
def test_yaml_mixed_case_keeps_existing_lowercase_precedence(tmp_path, document):
    from pydantic_settings import SettingsConfigDict
    from app.yaml_base_settings import YamlBaseSettings

    yaml = tmp_path / "api.yml"
    yaml.write_text(document)

    class Settings(YamlBaseSettings):
        API_TOKEN: str = ""
        model_config = SettingsConfigDict(yaml_file=str(yaml), env_file=None, secrets_dir=str(tmp_path), extra="ignore")

    assert Settings().API_TOKEN == "lower"
