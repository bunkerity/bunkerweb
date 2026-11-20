"""Hosttech credentials use the shared provider and private-file paths."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

import letsencrypt_providers as providers
import letsencrypt_utils as utils


@pytest.mark.parametrize("alias", ["dns_hosttech_api_token", "hosttech_api_token", "api_token"])
def test_hosttech_credentials_aliases_render_and_redact(alias):
    provider_class = getattr(providers, "HosttechProvider", None)
    assert provider_class is not None
    provider = provider_class(**{alias: "dummy-hosttech-token"})
    assert provider.model_dump() == {"dns_hosttech_api_token": "dummy-hosttech-token"}
    assert provider.get_formatted_credentials() == b"dns_hosttech_api_token = dummy-hosttech-token"
    assert provider.get_file_type() == "ini"
    assert provider.get_extra_args() == ["-a", "dns-hosttech"]
    assert "dummy-hosttech-token" not in str(provider)
    assert "dummy-hosttech-token" not in repr(provider)
    assert "***" in str(provider)


def test_hosttech_requires_api_token():
    provider_class = getattr(providers, "HosttechProvider", None)
    assert provider_class is not None
    with pytest.raises(ValidationError):
        provider_class()


def test_hosttech_registry_extracts_credentials_and_writes_private_file(monkeypatch, tmp_path):
    assert "hosttech" in utils.PROVIDERS
    assert utils.PROVIDERS["hosttech"] is providers.HosttechProvider
    monkeypatch.setattr(utils, "environ", {"LETS_ENCRYPT_DNS_CREDENTIAL_ITEM": "api_token dummy-hosttech-token"})
    provider = utils.extract_provider("app.example.com", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM", "hosttech", logger=Mock())
    assert isinstance(provider, providers.HosttechProvider)
    credentials = Path(utils.write_provider_credentials_file(provider, tmp_path))
    assert credentials.read_bytes() == b"dns_hosttech_api_token = dummy-hosttech-token"
    assert credentials.stat().st_mode & 0o777 == 0o600
