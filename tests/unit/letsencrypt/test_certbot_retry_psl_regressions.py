"""Retry environment and public-suffix boundary regressions without external calls."""

import pytest

import certbot_concurrency
import test_certbot_jobs_execution

job_run = test_certbot_jobs_execution.job_run


@pytest.mark.parametrize("value, expected", [("0", ("0", "0")), ("", ("3", "2")), (None, ("3", "2"))])
def test_concurrent_registration_preserves_zero_and_defaults(job_run, value, expected):
    job_run.env.update(
        LETS_ENCRYPT_CONCURRENT_REQUESTS="yes",
        LETS_ENCRYPT_SERVER="zerossl",
        LETS_ENCRYPT_ZEROSSL_API_KEY="test-key",
    )
    if value is not None:
        job_run.env.update(LETS_ENCRYPT_ZEROSSL_API_RETRY=value, LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY=value)
    _, status = job_run.load()
    assert status == 1
    register_env = certbot_concurrency.ensure_zerossl_accounts.call_args.args[1]
    assert (register_env["LETS_ENCRYPT_ZEROSSL_API_RETRY"], register_env["LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY"]) == expected


@pytest.mark.parametrize("value", [None, ""])
def test_issuance_defaults_missing_or_empty_retry_values(job_run, value):
    job_run.env.update(AUTO_LETS_ENCRYPT="no", LETS_ENCRYPT_SERVER="zerossl", LETS_ENCRYPT_ZEROSSL_API_KEY="test-key")
    module, _ = job_run.load()
    _, config = module.build_service_config("app.example.com")
    config["server_names"] = "app.example.com"
    for key in ("zerossl_api_retry", "zerossl_api_retry_delay"):
        if value is None:
            config.pop(key)
        else:
            config[key] = value
    cmd_env = {}
    paths = certbot_concurrency.CertbotPaths(job_run.data, job_run.cache / "work", job_run.cache / "logs")
    assert module.certbot_new("app.example.com", config, cmd_env, paths) == 0
    assert cmd_env["LETS_ENCRYPT_ZEROSSL_API_RETRY"] == cmd_env["ZEROSSL_API_RETRY"] == "3"
    assert cmd_env["LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY"] == cmd_env["ZEROSSL_API_RETRY_DELAY"] == "2"


@pytest.mark.parametrize(
    "domain, blocked",
    [
        ("foo.ck", True),
        ("*.foo.ck", True),
        ("www.ck", False),
        ("*.www.ck", False),
        ("site.foo.ck", False),
        ("foo.bar", True),
        ("site.foo.bar", True),
        ("foo.site.foo.bar", False),
        ("www.foo.bar", False),
    ],
)
def test_psl_wildcard_uses_matched_label_depth_and_exception(job_run, domain, blocked):
    job_run.env["AUTO_LETS_ENCRYPT"] = "no"
    module, _ = job_run.load()
    rules = module.parse_psl(["*.ck", "!www.ck", "*.bar", "*.foo.bar", "!www.foo.bar"])
    assert module.is_domain_blacklisted(domain, rules) is blocked
