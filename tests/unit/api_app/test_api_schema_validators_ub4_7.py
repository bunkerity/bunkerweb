"""UB4-7: request models reject invalid inputs and preserve supported normalization."""

import pytest
from pydantic import ValidationError

from app import schemas


@pytest.mark.parametrize("model", [schemas.BanRequest, schemas.UnbanRequest])
def test_ban_models_trim_ips_and_reject_non_addresses(model):
    assert model(ip=" 2001:db8::1 ").ip == "2001:db8::1"
    with pytest.raises(ValidationError, match="ip"):
        model(ip="not-an-ip")


def test_ban_expiration_allows_permanent_but_rejects_negative():
    assert schemas.BanRequest(ip="192.0.2.1", exp=0).exp == 0
    assert schemas.BanRequest(ip="192.0.2.1", exp=1).exp == 1
    with pytest.raises(ValidationError, match="exp must be non-negative"):
        schemas.BanRequest(ip="192.0.2.1", exp=-1)


def test_instance_hostname_refuses_userinfo():
    assert schemas.InstanceCreateRequest(hostname="backend.example.com").hostname == "backend.example.com"
    with pytest.raises(ValidationError, match="hostname must not contain '@'"):
        schemas.InstanceCreateRequest(hostname="user@backend.example.com")


@pytest.mark.parametrize("model", [schemas.ConfigCreateRequest, schemas.ConfigUpdateRequest, schemas.ConfigKey])
@pytest.mark.parametrize("given", ["", " ", "../escape", "bad/name", "bad.name", "x" * 256])
def test_config_names_refuse_invalid_filenames(model, given):
    with pytest.raises(ValidationError, match="Invalid name"):
        model(type="http", name=given, **({"data": ""} if model is schemas.ConfigCreateRequest else {}))


@pytest.mark.parametrize("model", [schemas.ConfigCreateRequest, schemas.ConfigUpdateRequest, schemas.ConfigKey])
def test_config_names_and_types_are_normalized(model):
    config = model(type=" SERVER-HTTP ", name=" valid_name-1 ", **({"data": ""} if model is schemas.ConfigCreateRequest else {}))
    assert (config.type, config.name) == ("server_http", "valid_name-1")


@pytest.mark.parametrize("model", [schemas.ConfigCreateRequest, schemas.ConfigUpdateRequest, schemas.ConfigKey])
@pytest.mark.parametrize("given", ["invalid", 123])
def test_config_types_refuse_unknown_and_non_string_values(model, given):
    with pytest.raises(ValidationError, match="Invalid type|type must be a string"):
        model(type=given, name="valid", **({"data": ""} if model is schemas.ConfigCreateRequest else {}))


def test_optional_config_fields_accept_none():
    config = schemas.ConfigUpdateRequest(type=None, name=None)
    assert config.type is None and config.name is None


@pytest.mark.parametrize("model", [schemas.ConfigCreateRequest, schemas.ConfigUpdateRequest, schemas.ConfigKey, schemas.CacheFileKey])
@pytest.mark.parametrize("service, expected", [(None, None), ("", None), ("global", None), ("app.example.com", "app.example.com")])
def test_config_and_cache_service_normalization(model, service, expected):
    fields = {"plugin": "dnsbl", "jobName": "download", "fileName": "cache"} if model is schemas.CacheFileKey else {"type": "http", "name": "valid"}
    if model is schemas.ConfigCreateRequest:
        fields["data"] = ""
    assert model(service=service, **fields).service == expected


@pytest.mark.parametrize("field", ["plugin", "jobName", "fileName"])
@pytest.mark.parametrize("value", ["", " "])
def test_cache_key_parts_must_be_non_empty(field, value):
    fields = {"plugin": "dnsbl", "jobName": "download", "fileName": "cache"}
    fields[field] = value
    with pytest.raises(ValidationError, match="must be a non-empty string"):
        schemas.CacheFileKey(**fields)


def test_cache_key_parts_are_trimmed():
    key = schemas.CacheFileKey(plugin=" dnsbl ", jobName=" download ", fileName=" cache ")
    assert (key.plugin, key.jobName, key.fileName) == ("dnsbl", "download", "cache")


@pytest.mark.parametrize("value", ["", " "])
def test_job_plugin_must_be_non_empty(value):
    with pytest.raises(ValidationError, match="plugin must be a non-empty string"):
        schemas.JobItem(plugin=value)


def test_job_plugin_is_trimmed():
    assert schemas.JobItem(plugin=" dnsbl ").plugin == "dnsbl"


@pytest.mark.parametrize(
    "model, field, item",
    [
        (schemas.ConfigsDeleteRequest, "configs", {"type": "http", "name": "valid"}),
        (schemas.CacheFilesDeleteRequest, "cache_files", {"plugin": "dnsbl", "jobName": "download", "fileName": "cache"}),
        (schemas.RunJobsRequest, "jobs", {"plugin": "dnsbl"}),
    ],
)
def test_bulk_requests_require_at_least_one_item(model, field, item):
    assert len(getattr(model.model_validate({field: [item]}), field)) == 1
    with pytest.raises(ValidationError, match=field):
        model.model_validate({field: []})


@pytest.mark.parametrize("body", [[], "LOG_LEVEL=info", None, {"LOG_LEVEL": {}}, {"LOG_LEVEL": []}])
def test_global_settings_require_object_of_scalars(body):
    with pytest.raises(ValidationError):
        schemas.GlobalSettingsUpdate.model_validate(body)


def test_global_settings_preserve_scalar_values():
    body = {"text": "info", "integer": 8080, "float": 1.5, "boolean": True, "empty": None}
    result = schemas.GlobalSettingsUpdate.model_validate(body).root
    assert result == body
    assert {key: type(value) for key, value in result.items()} == {key: type(value) for key, value in body.items()}
