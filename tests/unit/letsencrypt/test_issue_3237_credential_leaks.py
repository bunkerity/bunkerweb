"""Let's Encrypt credential handling regressions: secrets stay out of argv and logs, DNS credentials are not mangled.

#3237: the ZeroSSL API key was passed on the certbot command line, and a provider model printed its
secrets when stringified. The key now travels in the child environment and every field is redacted
in ``repr``. #2627: the RFC2136 default algorithm was dropped from the credentials file, so an
explicit ``HMAC-SHA512`` never reached certbot. #2904: a credential that happens to be valid base64
was always decoded; ``decode_base64=False`` (``LETS_ENCRYPT_DNS_CREDENTIAL_DECODE_BASE64=no``) now
keeps it verbatim.
"""

from base64 import b64encode

import pytest

import certbot_concurrency
import letsencrypt_utils as utils
from letsencrypt_providers import CloudflareProvider, Rfc2136Provider
from test_certbot_jobs_execution import job_run  # noqa: F401 -- fixture, reused read-only

ITEM = "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM"


def test_zerossl_api_key_travels_in_the_environment_not_on_the_command_line(job_run):  # noqa: F811
    """#3237: `--zerossl-api-key <key>` was visible in `ps` and in any logged command."""
    job_run.env.update(AUTO_LETS_ENCRYPT="no", LETS_ENCRYPT_SERVER="zerossl", LETS_ENCRYPT_ZEROSSL_API_KEY="zs-secret-key")
    module, _ = job_run.load()
    _, config = module.build_service_config("app.example.com")
    config["server_names"] = "app.example.com"
    cmd_env = {}
    paths = certbot_concurrency.CertbotPaths(job_run.data, job_run.cache / "work", job_run.cache / "logs")

    assert module.certbot_new("app.example.com", config, cmd_env, paths) == 0

    command = job_run.popen.call_args.args[0]
    assert "--zerossl-api-key" not in command
    assert not any("zs-secret-key" in str(part) for part in command)
    assert cmd_env["LETS_ENCRYPT_ZEROSSL_API_KEY"] == "zs-secret-key"
    assert job_run.popen.call_args.kwargs["env"]["LETS_ENCRYPT_ZEROSSL_API_KEY"] == "zs-secret-key"


def test_a_provider_never_prints_its_secrets():
    """#3237: pydantic's repr listed every field, so a debug log of the provider published the token."""
    provider = CloudflareProvider(dns_cloudflare_api_token="cf-secret-token", dns_cloudflare_email="ops@example.com")

    for text in (repr(provider), str(provider)):
        assert "cf-secret-token" not in text
        assert "ops@example.com" not in text
        assert "***" in text
    # An unset field stays visible as empty so the log still says what was configured.
    assert "dns_cloudflare_api_key=''" in repr(provider)
    # Redaction is for display only: the credentials file certbot reads keeps the real value.
    assert b"dns_cloudflare_api_token = cf-secret-token" in provider.get_formatted_credentials()


@pytest.mark.parametrize("algorithm", ["HMAC-SHA512", "HMAC-SHA256", "HMAC-MD5"])
def test_rfc2136_algorithm_reaches_the_credentials_file(algorithm):
    """#2627: the default was HMAC-SHA512 and defaults are excluded, so choosing it wrote no algorithm line and certbot fell back to HMAC-MD5."""
    provider = Rfc2136Provider(dns_rfc2136_server="10.0.0.1", dns_rfc2136_name="key", dns_rfc2136_secret="c2VjcmV0", dns_rfc2136_algorithm=algorithm)

    lines = provider.get_formatted_credentials().decode().splitlines()

    if algorithm == "HMAC-MD5":
        # certbot's own default: leaving it out is the same thing.
        assert "dns_rfc2136_algorithm = HMAC-SHA512" not in lines
    else:
        assert f"dns_rfc2136_algorithm = {algorithm}" in lines


def test_rfc2136_default_algorithm_matches_certbots_default():
    """#2627: a file with no algorithm line must mean what certbot assumes, HMAC-MD5."""
    provider = Rfc2136Provider(dns_rfc2136_server="10.0.0.1", dns_rfc2136_name="key", dns_rfc2136_secret="c2VjcmV0")

    assert provider.dns_rfc2136_algorithm == "HMAC-MD5"
    assert not [line for line in provider.get_formatted_credentials().decode().splitlines() if line.startswith("dns_rfc2136_algorithm")]


def test_a_base64_looking_credential_is_kept_verbatim_when_decoding_is_off(monkeypatch):
    """#2904: a token that is valid base64 was decoded into garbage and the DNS API answered 401."""
    token = b64encode(b"plaintext").decode()  # a literal API token that is also valid base64
    monkeypatch.setenv(ITEM, f"dns_cloudflare_api_token {token}")

    kept = utils.extract_provider("svc", ITEM, "cloudflare", decode_base64=False)
    decoded = utils.extract_provider("svc", ITEM, "cloudflare", decode_base64=True)

    assert kept is not None
    assert kept.dns_cloudflare_api_token == token
    # With decoding on (the default) the legacy behaviour is untouched.
    assert decoded.dns_cloudflare_api_token == "plaintext"


def test_a_base64_json_blob_is_not_expanded_when_decoding_is_off(monkeypatch):
    """#2904: the single-blob form is expanded only when decoding is on."""
    blob = b64encode(b'{"DNS_CLOUDFLARE_API_TOKEN": "json-secret"}').decode()
    monkeypatch.setenv(ITEM, blob)

    assert utils.extract_provider("svc", ITEM, "cloudflare", decode_base64=True).dns_cloudflare_api_token == "json-secret"
    # Off: the blob is not a `key value` pair and is not expanded, so there is nothing to validate.
    assert utils.extract_provider("svc", ITEM, "cloudflare", decode_base64=False) is None
