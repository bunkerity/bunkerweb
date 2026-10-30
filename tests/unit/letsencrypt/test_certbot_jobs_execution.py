"""Execute issuance and renewal jobs with temporary storage and fake process boundaries."""

from contextlib import nullcontext
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import certbot_concurrency
import jobs
import letsencrypt_utils as utils
import logger
import requests

JOBS = Path(__file__).resolve().parents[3] / "src/common/core/letsencrypt/jobs"


@pytest.fixture
def job_run(monkeypatch, tmp_path):
    env = {"SERVER_NAME": "app.example.com", "AUTO_LETS_ENCRYPT": "yes", "EMAIL_LETS_ENCRYPT": "ops@example.com"}
    monkeypatch.setattr(os, "environ", env)
    monkeypatch.setattr(utils, "environ", env)
    monkeypatch.setattr(certbot_concurrency, "environ", env)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    cache = tmp_path / "cache"
    data = cache / "etc"
    data.mkdir(parents=True)
    log = Mock()
    job = SimpleNamespace(restore_ok=True, cache_dir=Mock(return_value=(True, "")), del_cache=Mock())

    def cache_file(name, body):
        (cache / name).write_bytes(body)
        return True, ""

    job.cache_file = Mock(side_effect=cache_file)
    job.get_cache = Mock(return_value={"last_update": datetime.now().timestamp(), "data": b"com\norg\nco.uk\n"})
    state = SimpleNamespace(
        env=env,
        cache=cache,
        data=data,
        job=job,
        log=log,
        listing=subprocess.CompletedProcess([], 0, stdout=""),
        returncode=0,
        lines=[],
        stream_ok=True,
        rotate=False,
    )
    for name, value in {
        "LETSENCRYPT_CACHE_PATH": cache,
        "LETSENCRYPT_DATA_PATH": data,
        "LETSENCRYPT_WORK_DIR": str(tmp_path / "work"),
        "LETSENCRYPT_LOGS_DIR": str(tmp_path / "logs"),
        "LETSENCRYPT_JOBS_PATH": JOBS,
        "CERTBOT_BIN": str(tmp_path / "certbot"),
        "ZEROSSL_BOT_SCRIPT": tmp_path / "zerossl-bot.sh",
        "attach_job_log_file": Mock(),
        "prepare_logs_dir": Mock(),
        "build_certbot_env": Mock(return_value={"PATH": "/test/bin", "API_TOKEN": "test-internal-token"}),
        "sanitize_and_persist": Mock(return_value=[]),
        "setup_route53_aws_config": Mock(return_value=[]),
        "letsencrypt_cache_consistent": Mock(return_value=(True, "")),
        "le_cache_write_lock": nullcontext,
        "resolve_certbot_entrypoint": Mock(return_value=[str(tmp_path / "certbot")]),
    }.items():
        monkeypatch.setattr(utils, name, value)
    state.recover = Mock()
    monkeypatch.setattr(certbot_concurrency, "ensure_accounts_for_orphans", state.recover)
    monkeypatch.setattr(certbot_concurrency, "ensure_accounts", Mock())
    monkeypatch.setattr(certbot_concurrency, "ensure_zerossl_accounts", Mock())
    monkeypatch.setattr(jobs, "Job", Mock(return_value=job))
    monkeypatch.setattr(logger, "getLogger", Mock(return_value=log))
    state.run = Mock(side_effect=lambda *args, **kwargs: state.listing)
    monkeypatch.setattr(subprocess, "run", state.run)
    state.get = Mock(side_effect=AssertionError("Unexpected network request"))
    monkeypatch.setattr(requests, "get", state.get)

    def popen(command, **kwargs):
        if state.rotate:
            name = command[command.index("--cert-name") + 1] if "--cert-name" in command else "app.example.com"
            config = Path(command[command.index("--config-dir") + 1])
            fullchain = config / "live" / name / "fullchain.pem"
            fullchain.parent.mkdir(parents=True, exist_ok=True)
            fullchain.write_bytes(b"new certificate")
        return SimpleNamespace(returncode=state.returncode)

    state.popen = Mock(side_effect=popen)
    monkeypatch.setattr(subprocess, "Popen", state.popen)

    def stream(process, log, timeout, on_line=None):
        if on_line:
            for line in state.lines:
                on_line(line)
        return state.stream_ok

    monkeypatch.setattr(utils, "stream_certbot", stream)

    def load(kind="new"):
        spec = importlib.util.spec_from_file_location(f"unit_certbot_{kind}", JOBS / f"certbot-{kind}.py")
        module = importlib.util.module_from_spec(spec)
        with pytest.raises(SystemExit) as stopped:
            spec.loader.exec_module(module)
        return module, stopped.value.code

    state.load = load
    return state


def live_cert(state, name="app.example.com", body=b"old certificate"):
    path = state.data / "live" / name / "fullchain.pem"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def renewal_conf(state, name="app.example.com", **settings):
    path = state.data / "renewal" / f"{name}.conf"
    path.parent.mkdir(parents=True, exist_ok=True)
    values = {"pref_challs": "http-01,", "authenticator": "manual", "preferred_profile": "classic", "server": utils.LETSENCRYPT_PRODUCTION_DIRECTORY}
    values.update(settings)
    path.write_text("\n".join(f"{key} = {value}" for key, value in values.items()))
    return path


def test_new_issues_http_certificate_and_persists_it(job_run):
    job_run.rotate = True
    module, status = job_run.load()
    assert status == 1
    command = job_run.popen.call_args.args[0]
    assert command[:4] == [utils.CERTBOT_BIN, "certonly", "-n", "--cert-name"]
    assert command[command.index("-d") + 1] == "app.example.com"
    assert command[command.index("--manual-auth-hook") + 1] == str(JOBS / "certbot-auth.py")
    assert command[command.index("--manual-cleanup-hook") + 1] == str(JOBS / "certbot-cleanup.py")
    assert "--preferred-challenges=http" in command
    assert job_run.popen.call_args.kwargs["env"]["API_TOKEN"] == "test-internal-token"
    assert (job_run.data / "live/app.example.com/fullchain.pem").read_bytes() == b"new certificate"
    job_run.job.cache_dir.assert_called_once_with(job_run.data)
    assert module.RUNNING_CERTBOT == 0
    assert module.MONITOR_THREAD is None


@pytest.mark.parametrize("kind", ["new", "renew"])
@pytest.mark.parametrize("settings", [{"AUTO_LETS_ENCRYPT": "no"}, {"MULTISITE": "yes", "SERVER_NAME": ""}])
def test_disabled_jobs_never_start_certbot(job_run, kind, settings):
    job_run.env.update(settings)
    _, status = job_run.load(kind)
    assert status == 0
    job_run.popen.assert_not_called()
    job_run.run.assert_not_called()
    job_run.job.cache_dir.assert_not_called()


@pytest.mark.parametrize(
    "settings",
    [
        {"SERVER_NAME": ""},
        {"LETS_ENCRYPT_CHALLENGE": "invalid"},
        {"LETS_ENCRYPT_CHALLENGE": "dns"},
        {"LETS_ENCRYPT_CHALLENGE": "dns", "LETS_ENCRYPT_DNS_PROVIDER": "unsupported"},
        {"LETS_ENCRYPT_CHALLENGE": "dns", "LETS_ENCRYPT_DNS_PROVIDER": "cloudflare"},
        {"SERVER_NAME": "localhost 192.0.2.1"},
        {"SERVER_NAME": "8.8.8.8"},
        {"LETS_ENCRYPT_SERVER": "zerossl", "EMAIL_LETS_ENCRYPT": ""},
    ],
)
def test_invalid_issuance_config_does_not_start_certbot(job_run, settings):
    job_run.env.update(settings)
    module, status = job_run.load()
    assert status == (0 if settings.get("SERVER_NAME") == "" else 2)
    job_run.popen.assert_not_called()
    job_run.job.cache_dir.assert_not_called()
    if status == 2:
        assert module.list_misconfigured(module.services) or module.rejected_services


def test_service_config_falls_back_and_filters_unissuable_names(job_run):
    job_run.env.update(
        AUTO_LETS_ENCRYPT="no",
        SERVER_NAME="app.example.com localhost 192.0.2.1 8.8.8.8",
        EMAIL_LETS_ENCRYPT="invalid",
        LETS_ENCRYPT_SERVER="invalid",
        LETS_ENCRYPT_MAX_RETRIES="-1",
        LETS_ENCRYPT_PROFILE="invalid",
        LETS_ENCRYPT_DNS_PROPAGATION="-1",
        LETS_ENCRYPT_ZEROSSL_API_RETRY="-1",
        LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY="-1",
        LETS_ENCRYPT_ZEROSSL_API_CONNECT_TIMEOUT="0",
        LETS_ENCRYPT_ZEROSSL_API_MAX_TIME="bad",
        USE_LETS_ENCRYPT_WILDCARD="yes",
    )
    module, _ = job_run.load()
    names, config = module.build_service_config("app.example.com")
    assert names == ["app.example.com"]
    assert {key: config[key] for key in ("acme_server", "email", "retries", "profile", "dns_propagation", "wildcard")} == {
        "acme_server": "letsencrypt",
        "email": "",
        "retries": 0,
        "profile": "classic",
        "dns_propagation": "default",
        "wildcard": False,
    }
    assert [config[key] for key in ("zerossl_api_retry", "zerossl_api_retry_delay", "zerossl_api_connect_timeout", "zerossl_api_max_time")] == [3, 2, 5, 20]


def test_service_config_duration_and_custom_profile(job_run):
    job_run.env.update(AUTO_LETS_ENCRYPT="no", LETS_ENCRYPT_MAX_RETRIES="bad", LETS_ENCRYPT_CUSTOM_PROFILE="CUSTOM", LETS_ENCRYPT_DNS_PROPAGATION="2m")
    module, _ = job_run.load()
    names, config = module.build_service_config("app.example.com")
    assert names == ["app.example.com"]
    assert config["profile"] == "custom"
    assert config["dns_propagation"] == "120"
    assert config["retries"] == 0


def test_new_multisite_uses_service_settings_and_continues_after_invalid_sibling(job_run):
    job_run.env.update(
        MULTISITE="yes",
        SERVER_NAME="app.example.com bad.example.com",
        **{
            "app.example.com_AUTO_LETS_ENCRYPT": "yes",
            "app.example.com_SERVER_NAME": "app.example.com alias.example.com",
            "bad.example.com_AUTO_LETS_ENCRYPT": "yes",
            "bad.example.com_SERVER_NAME": "localhost",
        },
    )
    job_run.rotate = True
    module, status = job_run.load()
    assert status == 1
    assert module.services["bad.example.com"]["misconfigured"]
    assert job_run.popen.call_count == 1
    assert job_run.popen.call_args.args[0][5:7] == ["-d", "alias.example.com,app.example.com"]
    job_run.job.cache_dir.assert_called_once()


@pytest.mark.parametrize("kind", ["new", "renew"])
def test_failed_restore_never_overwrites_cached_certificates(job_run, kind):
    live_cert(job_run)
    job_run.job.restore_ok = False
    _, status = job_run.load(kind)
    assert status == 2
    job_run.job.cache_dir.assert_not_called()
    assert any("initial cache restore failed" in call.args[0] for call in job_run.log.error.call_args_list)


@pytest.mark.parametrize("kind", ["new", "renew"])
def test_empty_tree_is_not_persisted_unless_sanitized(job_run, kind):
    _, status = job_run.load(kind)
    assert status == (1 if kind == "new" else 0)
    job_run.job.cache_dir.assert_not_called()
    utils.sanitize_and_persist.return_value = ["broken.example.com"]
    _, status = job_run.load(kind)
    assert status == (1 if kind == "new" else 0)
    job_run.job.cache_dir.assert_called_once_with(job_run.data)


@pytest.mark.parametrize("kind", ["new", "renew"])
def test_inconsistent_tree_preserves_db_and_requests_reload(job_run, kind):
    live_cert(job_run)
    utils.letsencrypt_cache_consistent.return_value = (False, "orphan account")
    _, status = job_run.load(kind)
    assert status == 1
    job_run.job.cache_dir.assert_not_called()
    assert any("orphan account" in call.args[0] for call in job_run.log.error.call_args_list)


@pytest.mark.parametrize("kind", ["new", "renew"])
def test_cache_write_failure_is_logged(job_run, kind):
    live_cert(job_run)
    job_run.job.cache_dir.return_value = (False, "db refused")
    job_run.load(kind)
    assert any("db refused" in call.args[0] for call in job_run.log.error.call_args_list)


def test_listing_failure_keeps_live_certificate_and_skips_destructive_cleanup(job_run):
    original = live_cert(job_run)
    job_run.listing = subprocess.CompletedProcess([], 1, stdout="parse failure")
    job_run.env["LETS_ENCRYPT_CLEAR_OLD_CERTS"] = "yes"
    module, status = job_run.load()
    assert status == 0
    assert module.services["app.example.com"]["exists"]
    job_run.popen.assert_not_called()
    assert original.read_bytes() == b"old certificate"
    job_run.job.cache_dir.assert_called_once()


def test_matching_listing_skips_issuance_and_reads_renewal_settings(job_run):
    live_cert(job_run)
    renewal_conf(job_run)
    job_run.listing.stdout = "Certificate Name: app.example.com\n  Domains: app.example.com\n"
    module, status = job_run.load()
    assert status == 0
    job_run.popen.assert_not_called()
    assert module.services["app.example.com"]["exists"]
    assert module.existing_certificates["app.example.com"]["challenge"] == "http"
    job_run.get.assert_not_called()


def test_added_names_expand_without_deleting_current_lineage(job_run):
    live_cert(job_run)
    renewal_conf(job_run)
    job_run.env["SERVER_NAME"] = "app.example.com www.example.com"
    job_run.listing.stdout = "Certificate Name: app.example.com\n  Identifiers: app.example.com\n"
    module, status = job_run.load()
    assert status == 1
    assert module.services["app.example.com"]["expand_names"]
    assert not module.services["app.example.com"]["force_renew"]
    assert [call.args[0][1] for call in job_run.popen.call_args_list] == ["certonly"]


def test_removed_names_delete_then_reissue(job_run):
    live_cert(job_run)
    renewal_conf(job_run)
    job_run.listing.stdout = "Certificate Name: app.example.com\n  Domains: app.example.com old.example.com\n"
    _, status = job_run.load()
    assert status == 1
    assert [call.args[0][1] for call in job_run.popen.call_args_list] == ["delete", "certonly"]


@pytest.mark.parametrize(
    "provider, credential_items",
    [
        ("cloudflare", {"LETS_ENCRYPT_DNS_CREDENTIAL_ITEM": "dns_cloudflare_api_token test-token"}),
        (
            "route53",
            {"LETS_ENCRYPT_DNS_CREDENTIAL_ITEM": "aws_access_key_id test-key", "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM_1": "aws_secret_access_key test-secret"},
        ),
    ],
)
def test_dns_issuance_caches_private_credentials_and_sets_provider_arguments(job_run, provider, credential_items):
    job_run.env.update(LETS_ENCRYPT_CHALLENGE="dns", LETS_ENCRYPT_DNS_PROVIDER=provider, LETS_ENCRYPT_DNS_PROPAGATION="2m", **credential_items)
    job_run.rotate = True
    _, status = job_run.load()
    assert status == 1
    command = job_run.popen.call_args.args[0]
    credentials = next(job_run.cache.glob("credentials_*.*"))
    assert credentials.stat().st_mode & 0o777 == 0o600
    assert b"test-" in credentials.read_bytes()
    assert command[command.index(f"--dns-{provider}-propagation-seconds") + 1] == "120"
    assert "--preferred-challenges=dns" in command
    if provider == "route53":
        assert job_run.popen.call_args.kwargs["env"]["AWS_CONFIG_FILE"] == str(credentials)
        assert "--dns-route53-credentials" not in command
    else:
        assert command[command.index("--dns-cloudflare-credentials") + 1] == str(credentials)


def test_concurrent_issuance_merges_distinct_certificates_and_preregisters_accounts(job_run):
    job_run.env.update(MULTISITE="yes", LETS_ENCRYPT_CONCURRENT_REQUESTS="yes", SERVER_NAME="a.example.com b.example.com")
    for name in ("a.example.com", "b.example.com"):
        job_run.env.update({f"{name}_AUTO_LETS_ENCRYPT": "yes", f"{name}_SERVER_NAME": name})
    job_run.rotate = True
    module, status = job_run.load()
    assert status == 1
    assert sorted(path.parent.name for path in job_run.data.glob("live/*/fullchain.pem")) == ["a.example.com", "b.example.com"]
    certbot_concurrency.ensure_accounts.assert_called_once()
    assert certbot_concurrency.ensure_accounts.call_args.args[0] == {(False, "")}
    assert not list(job_run.cache.glob("certbot-*/"))
    assert module.RUNNING_CERTBOT == 0


def test_retry_backoff_and_finalization(job_run, monkeypatch):
    job_run.env["AUTO_LETS_ENCRYPT"] = "no"
    module, _ = job_run.load()
    _, config = module.build_service_config("app.example.com")
    config.update(server_names="app.example.com", retries=2)
    new = Mock(side_effect=[1, 1, 0])
    finalize = Mock()
    sleep = Mock()
    monkeypatch.setattr(module, "certbot_new", new)
    monkeypatch.setattr(module, "finalize_certbot_run", finalize)
    monkeypatch.setattr(module, "sleep", sleep)
    assert module.generate_certificate("app.example.com", config, {"keep": "value"})
    assert [call.args[0] for call in sleep.call_args_list] == [30, 60]
    assert finalize.call_args.args[2] is True
    assert module.RUNNING_CERTBOT == 0
    new.side_effect = RuntimeError("process creation failed")
    with pytest.raises(RuntimeError, match="process creation failed"):
        module.generate_certificate("app.example.com", config, {})
    assert finalize.call_args.args[2] is False
    assert module.RUNNING_CERTBOT == 0


@pytest.mark.parametrize("kind", ["new", "renew"])
def test_certbot_timeout_is_failed_job(job_run, kind):
    job_run.stream_ok = False
    _, status = job_run.load(kind)
    assert status == 2
    assert any("timed out" in call.args[0] for call in job_run.log.error.call_args_list)


@pytest.mark.parametrize("rotated, returncode, expected", [(False, 0, 0), (True, 0, 1), (False, 1, 2), (True, 1, 3)])
def test_renewal_exit_code_reports_both_rotation_and_failure(job_run, rotated, returncode, expected):
    live_cert(job_run)
    job_run.rotate = rotated
    job_run.returncode = returncode
    _, status = job_run.load("renew")
    assert status == expected
    command = job_run.popen.call_args.args[0]
    assert command[1:4] == ["renew", "-n", "--no-random-sleep-on-renew"]
    assert "--max-log-backups" in command
    job_run.job.cache_dir.assert_called_once_with(job_run.data)


def test_renewal_recovers_stale_uri_and_lineage_accounts_in_same_run(job_run, monkeypatch):
    live_cert(job_run)
    job_run.returncode = 1
    job_run.lines = [
        'Unable to validate JWS :: Account "https://acme.example/acme/acct/7" not found',
        'Failed to renew certificate app.example.com with error: Unable to validate JWS :: Account is not valid, has status "deactivated"',
        'Unable to validate JWS :: Account is not valid, has status "deactivated"',
    ]
    uri_purge = Mock(return_value=True)
    account_purge = Mock(return_value=True)
    monkeypatch.setattr(utils, "purge_stale_account_by_uri", uri_purge)
    monkeypatch.setattr(utils, "purge_stale_account", account_purge)
    monkeypatch.setattr(utils, "account_id_for_cert", Mock(return_value="dead-id"))
    _, status = job_run.load("renew")
    assert status == 2
    uri_purge.assert_called_once_with(job_run.data, "https://acme.example/acme/acct/7", job_run.log)
    account_purge.assert_called_once_with(job_run.data, "dead-id", job_run.log)
    assert job_run.recover.call_count == utils.sanitize_and_persist.call_count == 2
    assert any("named neither" in call.args[0] for call in job_run.log.error.call_args_list)


def test_renewal_ignores_missing_and_unreadable_live_material(job_run):
    fullchain = live_cert(job_run)
    broken = job_run.data / "live/broken.example.com/fullchain.pem"
    broken.parent.mkdir(parents=True)
    broken.symlink_to("missing.pem")
    module, _ = job_run.load("renew")
    assert set(module.certificate_digests(job_run.data)) == {fullchain.parent.name}
    assert module.publication_status(2, {"old": "digest"}, {}) == 2
    assert module.publication_status(3, {}, {"new": "digest"}) == 3


def test_zerossl_hash_file_roundtrip_and_invalid_data(job_run):
    job_run.env["AUTO_LETS_ENCRYPT"] = "no"
    module, _ = job_run.load()
    assert module.load_zerossl_api_key_hashes() == {}
    module.save_zerossl_api_key_hashes({"b.example.com": "b", "a.example.com": "a"})
    assert json.loads(module.ZEROSSL_API_KEY_HASHES_PATH.read_text()) == {"a.example.com": "a", "b.example.com": "b"}
    assert module.load_zerossl_api_key_hashes() == {"a.example.com": "a", "b.example.com": "b"}
    for body in ("[1,2]", "not json"):
        module.ZEROSSL_API_KEY_HASHES_PATH.write_text(body)
        assert module.load_zerossl_api_key_hashes() == {}
    module.save_zerossl_api_key_hashes({})
    assert not module.ZEROSSL_API_KEY_HASHES_PATH.exists()


def test_psl_download_falls_back_to_stale_cache(job_run):
    job_run.env["AUTO_LETS_ENCRYPT"] = "no"
    module, _ = job_run.load()
    job_run.job.get_cache.return_value = {"last_update": 0, "data": b"// comment\ncom\n*.ck\n!www.ck\n"}
    assert module.load_public_suffix_list(job_run.job) == ["// comment", "com", "*.ck", "!www.ck"]
    parsed = module.parse_psl(module.load_public_suffix_list(job_run.job))
    assert module.check_psl_blacklist(["com"], parsed, "svc")
    assert not module.check_psl_blacklist(["www.ck", "app.example.com", "8.8.8.8"], parsed, "svc")
    job_run.job.get_cache.return_value = None
    assert module.load_public_suffix_list(job_run.job) == []


def test_psl_download_persists_response_even_when_cache_write_fails(job_run):
    job_run.env["AUTO_LETS_ENCRYPT"] = "no"
    module, _ = job_run.load()
    job_run.job.get_cache.return_value = None
    job_run.get.side_effect = None
    job_run.get.return_value = SimpleNamespace(text="com\norg\n", raise_for_status=Mock())
    job_run.job.cache_file.side_effect = None
    job_run.job.cache_file.return_value = (False, "disk full")
    assert module.load_public_suffix_list(job_run.job) == ["com", "org"]
    job_run.job.cache_file.assert_called_once_with("public_suffix_list.dat", b"com\norg\n")
    assert any("disk full" in call.args[0] for call in job_run.log.error.call_args_list)


def test_wildcard_issuance_keeps_explicit_scopes_and_rejects_uncovered_groups(job_run):
    job_run.env.update(
        SERVER_NAME="*.a.example.com b.example.com",
        USE_LETS_ENCRYPT_WILDCARD="yes",
        LETS_ENCRYPT_CHALLENGE="dns",
        LETS_ENCRYPT_DNS_PROVIDER="cloudflare",
        LETS_ENCRYPT_DNS_CREDENTIAL_ITEM="dns_cloudflare_api_token test-token",
    )
    module, status = job_run.load()
    assert status == 1
    assert {name: config["server_names"] for name, config in module.services.items()} == {
        "a.example.com": "*.a.example.com,a.example.com",
        "example.com": "*.example.com,example.com",
    }
    rejected = set()
    assert module.extract_wildcard_groups(["example.com", "a.b.example.com"], "svc", rejected) == {}
    assert rejected == {"svc"}
    assert module.extract_wildcard_groups(["", "."], "svc") == {}
    assert module._determine_wildcard_bases([], "svc") == set()


@pytest.mark.parametrize(
    "key, value, expected",
    [
        ("challenge", "dns", "Challenge type"),
        ("authenticator", "cloudflare", "DNS provider"),
        ("staging", True, "Staging environment"),
        ("profile", "shortlived", "Profile"),
        ("acme_server_url", "https://other-ca/directory", "ACME server"),
    ],
)
def test_certificate_setting_changes_force_renewal(job_run, key, value, expected):
    job_run.env["AUTO_LETS_ENCRYPT"] = "no"
    module, _ = job_run.load()
    _, config = module.build_service_config("app.example.com")
    config["server_names"] = "app.example.com"
    existing = dict(config, server_names_set={"app.example.com"}, credentials_hash="")
    existing[key] = value
    reasons, expand = module.certificate_changes("app.example.com", config, existing, {})
    assert len(reasons) == 1 and expected in reasons[0]
    assert not expand


def test_dns_credential_change_and_zerossl_key_rotation_force_renewal(job_run):
    job_run.env.update(
        AUTO_LETS_ENCRYPT="no",
        LETS_ENCRYPT_CHALLENGE="dns",
        LETS_ENCRYPT_DNS_PROVIDER="cloudflare",
        LETS_ENCRYPT_DNS_CREDENTIAL_ITEM="dns_cloudflare_api_token test-token",
    )
    module, _ = job_run.load()
    _, config = module.build_service_config("app.example.com")
    config.update(server_names="app.example.com", acme_server="zerossl", zerossl_api_key_hash="new-key-hash")
    existing = dict(config, server_names_set={"app.example.com"}, credentials_hash="different-hash")
    reasons, expand = module.certificate_changes("app.example.com", config, existing, {"app.example.com": "old-key-hash"})
    assert any("ZeroSSL API key changed" in reason for reason in reasons)
    assert any("DNS credentials have changed" in reason for reason in reasons)
    assert not expand


def test_old_certificate_cleanup_falls_back_to_lineage_purge(job_run, monkeypatch):
    job_run.env["LETS_ENCRYPT_CLEAR_OLD_CERTS"] = "yes"
    job_run.listing.stdout = "Certificate Name: removed.example.com\n  Domains: removed.example.com\n"
    job_run.returncode = 1
    purge = Mock(return_value=["removed.conf", "live/removed.example.com"])
    monkeypatch.setattr(utils, "purge_lineage", purge)
    _, status = job_run.load()
    assert status == 2
    purge.assert_called_once_with(job_run.data, job_run.data / "renewal/removed.example.com.conf", quarantine_root=None, logger=job_run.log)
    assert any("purged 2 path(s)" in call.args[0] for call in job_run.log.info.call_args_list)


def test_credential_cleanup_keeps_current_dns_credentials(job_run):
    stale = job_run.cache / "credentials_stale.ini"
    stale.write_text("old-secret")
    job_run.env.update(
        LETS_ENCRYPT_CHALLENGE="dns", LETS_ENCRYPT_DNS_PROVIDER="cloudflare", LETS_ENCRYPT_DNS_CREDENTIAL_ITEM="dns_cloudflare_api_token test-token"
    )
    job_run.load()
    job_run.job.del_cache.assert_called_once_with("credentials_stale.ini")


def test_concurrent_services_contain_process_errors_and_register_zerossl(job_run):
    job_run.env.update(MULTISITE="yes", LETS_ENCRYPT_CONCURRENT_REQUESTS="yes", SERVER_NAME="good.example.com fail.example.com")
    for name in ("good.example.com", "fail.example.com"):
        job_run.env.update({f"{name}_AUTO_LETS_ENCRYPT": "yes", f"{name}_SERVER_NAME": name})
    job_run.env.update({"good.example.com_LETS_ENCRYPT_SERVER": "zerossl", "good.example.com_LETS_ENCRYPT_ZEROSSL_API_KEY": "test-key"})
    original = job_run.popen.side_effect

    def process(command, **kwargs):
        if "fail.example.com" in command:
            raise OSError("process failed")
        return original(command, **kwargs)

    job_run.popen.side_effect = process
    job_run.rotate = True
    module, status = job_run.load()
    assert status == 2
    assert module.services["good.example.com"]["exists"]
    assert not module.services["fail.example.com"]["exists"]
    certbot_concurrency.ensure_zerossl_accounts.assert_called_once()
    register_env = certbot_concurrency.ensure_zerossl_accounts.call_args.args[1]
    assert register_env["LETS_ENCRYPT_ZEROSSL_API_KEY"] == "test-key"
    assert register_env["CERTBOT_BIN"] == utils.CERTBOT_BIN
    job_run.job.cache_dir.assert_called_once_with(job_run.data)


def test_new_stale_account_recovery_uses_canonical_tree(job_run, monkeypatch):
    job_run.returncode = 1
    job_run.lines = ['Unable to validate JWS :: Account "https://ca/acme/acct/1" not found']
    monkeypatch.setattr(certbot_concurrency, "select_account_id", Mock(return_value="dead-id"))
    purge = Mock(return_value=True)
    monkeypatch.setattr(utils, "purge_stale_account", purge)
    module, status = job_run.load()
    assert status == 2
    purge.assert_called_once_with(job_run.data, "dead-id", job_run.log)
    assert module.STALE_ACCOUNT_PURGED.is_set()
    assert job_run.recover.call_count == utils.sanitize_and_persist.call_count == 2


@pytest.mark.parametrize("kind", ["new", "renew"])
def test_unexpected_process_failure_is_logged_and_returns_failure(job_run, kind):
    job_run.popen.side_effect = OSError("cannot start certbot")
    _, status = job_run.load(kind)
    assert status == 2
    assert any("cannot start certbot" in call.args[0] for call in job_run.log.error.call_args_list)


def test_multisite_renewal_uses_zerossl_wrapper_and_debug_flags(job_run):
    job_run.env.update(
        MULTISITE="yes",
        SERVER_NAME="off.example.com app.example.com",
        CUSTOM_LOG_LEVEL="debug",
        **{"app.example.com_AUTO_LETS_ENCRYPT": "yes", "app.example.com_LETS_ENCRYPT_SERVER": "zerossl"},
    )
    utils.resolve_certbot_entrypoint.return_value = ["fake-zerossl-bot"]
    _, status = job_run.load("renew")
    assert status == 0
    command = job_run.popen.call_args.args[0]
    assert command[0] == "fake-zerossl-bot"
    assert command[-1] == "-v"
    assert any("zerossl-bot wrapper" in call.args[0] for call in job_run.log.info.call_args_list)


@pytest.mark.parametrize("setting", ["LETS_ENCRYPT_ZEROSSL_API_RETRY", "LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY"])
def test_zerossl_issuance_preserves_explicit_zero_retries(job_run, setting):
    job_run.env.update(
        AUTO_LETS_ENCRYPT="no",
        LETS_ENCRYPT_SERVER="zerossl",
        LETS_ENCRYPT_ZEROSSL_API_KEY="test-key",
        LETS_ENCRYPT_ZEROSSL_API_RETRY="0",
        LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY="0",
    )
    module, _ = job_run.load()
    _, config = module.build_service_config("app.example.com")
    config["server_names"] = "app.example.com"
    assert config["zerossl_api_retry"] == config["zerossl_api_retry_delay"] == 0
    cmd_env = {}
    paths = certbot_concurrency.CertbotPaths(job_run.data, job_run.cache / "work", job_run.cache / "logs")
    assert module.certbot_new("app.example.com", config, cmd_env, paths) == 0
    assert cmd_env[setting] == "0"


def test_psl_wildcard_blocks_public_suffix_but_allows_exception_and_registrable_domain(job_run):
    job_run.env["AUTO_LETS_ENCRYPT"] = "no"
    module, _ = job_run.load()
    rules = module.parse_psl(["*.ck", "!www.ck"])
    assert not module.is_domain_blacklisted("www.ck", rules)
    assert not module.is_domain_blacklisted("site.foo.ck", rules)
    assert module.is_domain_blacklisted("foo.ck", rules)


@pytest.mark.parametrize(
    "key, value, result_key, expected, warning",
    [
        ("LETS_ENCRYPT_MAX_RETRIES", "bad", "retries", 0, "not a valid integer"),
        ("LETS_ENCRYPT_MAX_RETRIES", "-1", "retries", 0, "negative"),
        ("LETS_ENCRYPT_SERVER", "unknown", "acme_server", "letsencrypt", "Defaulting"),
        ("LETS_ENCRYPT_PROFILE", "unknown", "profile", "classic", "Defaulting"),
        ("LETS_ENCRYPT_DNS_PROPAGATION", "0", "dns_propagation", "default", "positive integer"),
        ("LETS_ENCRYPT_DNS_PROPAGATION", "bad", "dns_propagation", "default", "not a valid integer"),
        ("LETS_ENCRYPT_ZEROSSL_API_RETRY", "-1", "zerossl_api_retry", 3, "must be >= 0"),
        ("LETS_ENCRYPT_ZEROSSL_API_RETRY_DELAY", "-1", "zerossl_api_retry_delay", 2, "must be >= 0"),
        ("LETS_ENCRYPT_ZEROSSL_API_CONNECT_TIMEOUT", "0", "zerossl_api_connect_timeout", 5, "must be > 0"),
        ("LETS_ENCRYPT_ZEROSSL_API_MAX_TIME", "0", "zerossl_api_max_time", 20, "must be > 0"),
    ],
)
def test_invalid_service_values_fall_back_with_operator_warning(job_run, key, value, result_key, expected, warning):
    job_run.env["AUTO_LETS_ENCRYPT"] = "no"
    module, _ = job_run.load()
    job_run.env.update(AUTO_LETS_ENCRYPT="yes", LETS_ENCRYPT_SERVER="zerossl", LETS_ENCRYPT_ZEROSSL_API_KEY="test-key")
    job_run.env[key] = value
    job_run.log.reset_mock()
    _, config = module.build_service_config("app.example.com")
    assert config["activated"]
    assert config[result_key] == expected
    assert any(key in call.args[0] and warning in call.args[0] for call in job_run.log.warning.call_args_list)


@pytest.mark.parametrize("conflicts", [False, True])
def test_shared_wildcard_lineage_merges_matching_services_and_warns_on_conflict(job_run, conflicts):
    job_run.env.update(MULTISITE="yes", SERVER_NAME="a.example.com b.example.com")
    for index, name in enumerate(("a.example.com", "b.example.com")):
        job_run.env.update(
            {
                f"{name}_AUTO_LETS_ENCRYPT": "yes",
                f"{name}_SERVER_NAME": name,
                f"{name}_USE_LETS_ENCRYPT_WILDCARD": "yes",
                f"{name}_LETS_ENCRYPT_CHALLENGE": "dns",
                f"{name}_LETS_ENCRYPT_DNS_PROVIDER": "cloudflare",
                f"{name}_LETS_ENCRYPT_DNS_CREDENTIAL_ITEM": f"dns_cloudflare_api_token token-{index if conflicts else 0}",
            }
        )
    module, status = job_run.load()
    assert status == 1
    assert list(module.services) == ["example.com"]
    assert module.services["example.com"]["server_names"] == "*.example.com,example.com"
    assert job_run.popen.call_count == 1
    warnings = [call.args[0] for call in job_run.log.warning.call_args_list]
    assert any("configuration conflict" in message for message in warnings) is conflicts


def test_public_ip_issuance_uses_shortlived_http_profile_and_warns_about_sni(job_run):
    job_run.env.update(SERVER_NAME="8.8.8.8 app.example.com", LETS_ENCRYPT_PROFILE="shortlived", DISABLE_DEFAULT_SERVER_STRICT_SNI="yes")
    _, status = job_run.load()
    assert status == 1
    command = job_run.popen.call_args.args[0]
    assert command[command.index("--ip-address") + 1] == "8.8.8.8"
    assert command[command.index("-d") + 1] == "app.example.com"
    assert command[command.index("--preferred-profile") + 1] == "shortlived"
    assert any("without SNI" in call.args[0] for call in job_run.log.warning.call_args_list)


@pytest.mark.parametrize("invalid_utf8", [False, True])
def test_listing_without_readable_renewal_metadata_can_reissue(job_run, invalid_utf8):
    live_cert(job_run)
    if invalid_utf8:
        renewal_conf(job_run).write_bytes(b"\xff")
    job_run.listing.stdout = "Certificate Name: app.example.com\n  Domains: app.example.com\n"
    module, status = job_run.load()
    assert status == 1
    assert module.services["app.example.com"]["force_renew"]
    assert module.services["app.example.com"]["exists"]
    if invalid_utf8:
        assert any("not valid UTF-8" in call.args[0] for call in job_run.log.error.call_args_list)


def test_blacklisted_public_suffix_does_not_reissue_existing_certificate(job_run):
    job_run.env["SERVER_NAME"] = "co.uk"
    original = live_cert(job_run, "co.uk")
    renewal_conf(job_run, "co.uk")
    job_run.listing.stdout = "Certificate Name: co.uk\n  Domains: co.uk\n"
    module, status = job_run.load()
    assert status == 2
    assert module.services["co.uk"]["misconfigured"]
    job_run.popen.assert_not_called()
    assert original.read_bytes() == b"old certificate"


def test_exhausted_retries_keep_failure_and_finalize_once(job_run, monkeypatch):
    job_run.env["AUTO_LETS_ENCRYPT"] = "no"
    module, _ = job_run.load()
    _, config = module.build_service_config("app.example.com")
    config.update(server_names="app.example.com", retries=1)
    new, finalize, sleep = Mock(return_value=1), Mock(), Mock()
    monkeypatch.setattr(module, "certbot_new", new)
    monkeypatch.setattr(module, "finalize_certbot_run", finalize)
    monkeypatch.setattr(module, "sleep", sleep)
    assert not module.generate_certificate("app.example.com", config, {})
    assert new.call_count == 2
    sleep.assert_called_once_with(30)
    finalize.assert_called_once()
    assert finalize.call_args.args[2] is False


def test_missing_wrapper_and_delete_timeout_return_failure(job_run, monkeypatch):
    job_run.env["AUTO_LETS_ENCRYPT"] = "no"
    module, _ = job_run.load()
    _, config = module.build_service_config("app.example.com")
    config["server_names"] = "app.example.com"
    utils.resolve_certbot_entrypoint.return_value = []
    paths = certbot_concurrency.CertbotPaths(job_run.data, job_run.cache / "work", job_run.cache / "logs")
    assert module.certbot_new("app.example.com", config, {}, paths) == 2
    job_run.popen.assert_not_called()
    monkeypatch.setattr(module, "stream_certbot", lambda *args: False)
    assert module.certbot_delete("app.example.com", {}) == 1
    assert "timed out" in job_run.log.error.call_args.args[0]


def test_staging_debug_issuance_uses_scoped_account_and_verbose_flags(job_run, monkeypatch):
    job_run.env.update(USE_LETS_ENCRYPT_STAGING="yes", CUSTOM_LOG_LEVEL="debug")
    select = Mock(return_value="staging-account")
    monkeypatch.setattr(certbot_concurrency, "select_account_id", select)
    _, status = job_run.load()
    assert status == 1
    command = job_run.popen.call_args.args[0]
    assert "--staging" in command
    assert "-v" in command
    assert command[command.index("--account") + 1] == "staging-account"
    select.assert_called_once_with(job_run.data / "accounts", True, "ops@example.com", server_url=utils.LETSENCRYPT_STAGING_DIRECTORY)


def test_zerossl_hash_write_error_preserves_previous_hash(job_run, monkeypatch):
    job_run.env["AUTO_LETS_ENCRYPT"] = "no"
    module, _ = job_run.load()
    module.save_zerossl_api_key_hashes({"app.example.com": "hash"})
    original = Path.write_text

    def write(path, *args, **kwargs):
        if path == module.ZEROSSL_API_KEY_HASHES_PATH:
            raise OSError("read-only")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write)
    module.save_zerossl_api_key_hashes({"app.example.com": "new-hash"})
    assert module.load_zerossl_api_key_hashes() == {"app.example.com": "hash"}
    assert "read-only" in job_run.log.warning.call_args.args[0]


def test_renewal_ordinary_output_does_not_retire_account(job_run, monkeypatch):
    job_run.lines = ["Certificate not yet due for renewal"]
    purge = Mock()
    monkeypatch.setattr(utils, "purge_stale_account", purge)
    _, status = job_run.load("renew")
    assert status == 0
    purge.assert_not_called()
