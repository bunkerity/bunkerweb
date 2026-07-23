"""api/app/schemas.py — Pydantic request models and their validators.

Pure logic (stdlib + pydantic), imported as the top-level ``schemas`` module via
``src/api/app`` on the path (the API conftest adds it). No DB, runs once.
"""

import pytest
from pydantic import ValidationError

import schemas  # type: ignore  (src/api/app on sys.path)


class TestConfigTypeHelpers:
    def test_normalize_config_type(self):
        assert schemas.normalize_config_type("Server-HTTP") == "server_http"

    def test_validate_config_name(self):
        assert schemas.validate_config_name("my_config-1") is None
        assert schemas.validate_config_name("bad name!") is not None
        assert schemas.validate_config_name("") is not None


class TestBanRequest:
    def test_defaults(self):
        b = schemas.BanRequest(ip="1.2.3.4")
        assert (b.exp, b.reason, b.service) == (86400, "api", None)

    def test_strips_ip(self):
        assert schemas.BanRequest(ip="  1.2.3.4  ").ip == "1.2.3.4"

    def test_invalid_ip(self):
        with pytest.raises(ValidationError):
            schemas.BanRequest(ip="not-an-ip")

    def test_negative_exp(self):
        with pytest.raises(ValidationError):
            schemas.BanRequest(ip="1.2.3.4", exp=-1)


class TestConfigCreateRequest:
    def test_type_normalized(self):
        assert schemas.ConfigCreateRequest(type="Server-HTTP", name="x", data="d").type == "server_http"

    def test_service_global_becomes_none(self):
        assert schemas.ConfigCreateRequest(service="global", type="http", name="x", data="d").service is None

    def test_invalid_type(self):
        with pytest.raises(ValidationError):
            schemas.ConfigCreateRequest(type="bogus", name="x", data="d")

    def test_invalid_name(self):
        with pytest.raises(ValidationError):
            schemas.ConfigCreateRequest(type="http", name="bad name!", data="d")


class TestBulkMethodValidator:
    @pytest.mark.parametrize("method", ["autoconf", "scheduler", "manual", "ui", "wizard"])
    def test_allowed(self, method):
        assert schemas.SaveConfigRequest(config={}, method=method).method == method

    def test_disallowed(self):
        with pytest.raises(ValidationError):
            schemas.SaveConfigRequest(config={}, method="api")


class TestPatternsAndAliases:
    def test_instance_status_ok(self):
        assert schemas.InstanceStatusRequest(status="up").status == "up"

    def test_instance_status_bad(self):
        with pytest.raises(ValidationError):
            schemas.InstanceStatusRequest(status="bogus")

    def test_dispatch_job_async_alias(self):
        j = schemas.DispatchJobItem(
            name="job",
            plugin_id="pl",
            file="job.py",
            path="/x",
            every="hour",
            **{"async": True},
        )
        assert j.run_async is True

    def test_dispatch_job_bad_file_pattern(self):
        with pytest.raises(ValidationError):
            schemas.DispatchJobItem(name="job", plugin_id="pl", file="job.sh", path="/x", every="hour")

    def test_external_plugins_type_alias(self):
        assert schemas.UpdateExternalPluginsRequest(plugins=[], **{"_type": "pro"}).plugin_type == "pro"

    def test_external_plugins_bad_type(self):
        with pytest.raises(ValidationError):
            schemas.UpdateExternalPluginsRequest(plugins=[], **{"_type": "bogus"})

    def test_plugin_enabled_request_bool(self):
        assert schemas.PluginEnabledRequest(enabled=True).enabled is True
        assert schemas.PluginEnabledRequest(enabled=False).enabled is False

    def test_plugin_enabled_request_requires_enabled(self):
        with pytest.raises(ValidationError):
            schemas.PluginEnabledRequest()


class TestGlobalSettingsUpdate:
    def test_scalars_ok(self):
        m = schemas.GlobalSettingsUpdate({"A": "1", "B": 2, "C": True, "D": None})
        assert m.root["B"] == 2

    def test_rejects_nested(self):
        with pytest.raises(ValidationError):
            schemas.GlobalSettingsUpdate({"A": {"nested": 1}})


class TestWebCachePurgeRequest:
    def test_all_scope_needs_no_urls(self):
        assert schemas.WebCachePurgeRequest(scope="all").model_dump(exclude_none=True) == {"scope": "all"}

    @pytest.mark.parametrize("payload", [{}, {"scope": "url"}, {"scope": "url", "urls": []}])
    def test_url_scope_requires_urls(self, payload):
        with pytest.raises(ValidationError, match="requires a non-empty 'urls' list"):
            schemas.WebCachePurgeRequest(**payload)

    def test_url_is_trimmed(self):
        request = schemas.WebCachePurgeRequest(scope="url", urls=[{"url": " https://example.com/asset.js "}])
        assert request.model_dump(exclude_none=True) == {
            "scope": "url",
            "urls": [{"url": "https://example.com/asset.js"}],
        }

    @pytest.mark.parametrize(
        ("url", "canonical"),
        [
            ("HTTPS://Example.COM?x=1", "https://example.com/?x=1"),
            ("HTTPS://Example.COM?", "https://example.com/?"),
            ("http://Example.COM:8080", "http://example.com:8080/"),
            ("https://[2001:DB8::1]:8443/a", "https://[2001:db8::1]:8443/a"),
        ],
    )
    def test_url_is_canonicalized_for_lua_cache_key_reconstruction(self, url, canonical):
        request = schemas.WebCachePurgeRequest(scope="url", urls=[{"url": url}])
        assert request.urls[0].url == canonical

    @pytest.mark.parametrize(
        "url",
        ["/asset.js", "example.com/asset.js", "ftp://example.com/asset.js", "http://"],
    )
    def test_url_must_be_absolute_http(self, url):
        with pytest.raises(ValidationError, match=r"absolute HTTP\(S\) URL"):
            schemas.WebCachePurgeRequest(scope="url", urls=[{"url": url}])

    @pytest.mark.parametrize(
        "url",
        ["https://user@example.com/a", "https://example.com/a#section", "https://example.com/a#", "https://example.com:0/a"],
    )
    def test_url_rejects_authority_or_request_parts_that_cannot_match_cache_key(self, url):
        with pytest.raises(ValidationError):
            schemas.WebCachePurgeRequest(scope="url", urls=[{"url": url}])

    def test_bulk_and_field_sizes_are_capped(self):
        with pytest.raises(ValidationError):
            schemas.WebCachePurgeRequest(scope="url", urls=[{"url": "https://example.com/"}] * 101)
        with pytest.raises(ValidationError):
            schemas.WebCachePurgeRequest(scope="url", urls=[{"url": "https://example.com/" + "a" * 8192}])
        with pytest.raises(ValidationError):
            schemas.WebCachePurgeRequest(scope="url", urls=[{"url": "https://example.com/", "key": "$host" * 1025}])


class TestCertificateRequests:
    def test_selfsigned_defaults_and_normalization(self):
        request = schemas.CertificateCreateRequest(
            source="selfsigned",
            name=" cert ",
            common_name=" example.com ",
            sans=["example.com", "example.com", "www.example.com"],
        )
        assert request.name == "cert"
        assert request.common_name == "example.com"
        assert request.sans == ["example.com", "www.example.com"]
        assert request.key_type == "ec"

    def test_letsencrypt_requires_service(self):
        with pytest.raises(ValidationError, match="requires at least one service_id"):
            schemas.CertificateCreateRequest(source="letsencrypt", name="cert", common_name="example.com")

    def test_metadata_rejects_secrets(self):
        with pytest.raises(ValidationError, match="must not contain credentials"):
            schemas.CertificateCreateRequest(
                source="selfsigned",
                name="cert",
                common_name="example.com",
                renewal_metadata={"api_token": "secret"},
            )

        with pytest.raises(ValidationError, match="must not contain credentials"):
            schemas.CertificateCreateRequest(
                source="selfsigned",
                name="cert",
                common_name="example.com",
                renewal_metadata={"providers": [{"password": "secret"}]},
            )

    @pytest.mark.parametrize("key", ["cache_checksum", "cert_name", "legacy", "managed_by", "service_ids"])
    def test_metadata_rejects_provider_owned_keys(self, key):
        with pytest.raises(ValidationError, match="provider-managed"):
            schemas.CertificateUpdateRequest(renewal_metadata={key: "caller-controlled"})
