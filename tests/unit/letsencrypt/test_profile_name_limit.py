"""A service that asks for more names than its Let's Encrypt profile allows is warned about (dev c5595e74d, #3251).

Let's Encrypt refuses an order past the profile's limit (``classic`` 100 names, ``tlsserver`` and
``shortlived`` 25), and certbot's rejection does not say which setting to change. The job logs a
warning that names the profile, its limit and the number of names requested, then carries on: the
order is still sent, because the limits belong to the CA and may change without a release of ours.
Only Let's Encrypt has these profiles; ZeroSSL and unknown profiles are never warned about.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from test_certbot_new_readiness_gate import _load_definitions


@pytest.fixture
def module():
    return _load_definitions()


def names(count):
    return ",".join(f"host{index}.example.com" for index in range(count))


def warnings(module):
    return [str(call.args[0]) for call in module.LOGGER.warning.call_args_list]


@pytest.mark.parametrize(
    "profile, limit",
    [("classic", 100), ("tlsserver", 25), ("shortlived", 25)],
)
def test_one_name_over_the_limit_warns(module, profile, limit):
    config = {"acme_server": "letsencrypt", "profile": profile, "server_names": names(limit + 1)}
    module.warn_profile_name_limit("svc", config)
    (message,) = warnings(module)
    assert "[Service: svc]" in message
    assert f"'{profile}'" in message
    assert f"at most {limit} names" in message
    assert f"{limit + 1} were requested" in message


@pytest.mark.parametrize("profile, limit", [("classic", 100), ("tlsserver", 25), ("shortlived", 25)])
def test_exactly_the_limit_does_not_warn(module, profile, limit):
    module.warn_profile_name_limit("svc", {"acme_server": "letsencrypt", "profile": profile, "server_names": names(limit)})
    assert warnings(module) == []


@pytest.mark.parametrize(
    "config",
    [
        {"acme_server": "zerossl", "profile": "classic", "server_names": names(500)},
        {"acme_server": "letsencrypt", "profile": "", "server_names": names(500)},
        {"acme_server": "letsencrypt", "server_names": names(500)},
        {"acme_server": "letsencrypt", "profile": "unheard-of", "server_names": names(500)},
        {"profile": "tlsserver", "server_names": names(500)},
    ],
)
def test_other_servers_and_unknown_profiles_are_never_warned_about(module, config):
    module.warn_profile_name_limit("svc", config)
    assert warnings(module) == []


def test_names_are_counted_like_the_job_counts_them(module):
    """Comma or space separated, case folded, a repeated name once."""
    listed = ",".join(["A.example.com", "a.example.com", "b.example.com"] * 20)
    module.warn_profile_name_limit("svc", {"acme_server": "letsencrypt", "profile": "tlsserver", "server_names": listed})
    assert warnings(module) == []


def test_a_missing_name_list_does_not_raise(module):
    module.warn_profile_name_limit("svc", {"acme_server": "letsencrypt", "profile": "tlsserver"})
    assert warnings(module) == []


def test_the_order_is_still_sent(module, tmp_path):
    """A warning, not a refusal: certbot is still run with every name."""
    module.resolve_certbot_entrypoint = Mock(return_value=["certbot"])
    module.certbot_log_backup_flags = Mock(return_value=[])
    module.select_account_id = Mock(return_value="existing-account")
    module.stream_certbot = Mock(return_value=True)
    module.Popen = Mock(return_value=SimpleNamespace(returncode=0))
    module.JOBS_PATH = tmp_path
    config = {
        "server_names": names(26),
        "profile": "tlsserver",
        "email": "admin@example.com",
        "challenge": "http",
        "staging": False,
        "force_renew": False,
        "acme_server": "letsencrypt",
        "acme_server_url": "https://acme.invalid/directory",
    }
    paths = SimpleNamespace(config_dir=tmp_path, work_dir=tmp_path, logs_dir=tmp_path)
    assert module.certbot_new("svc", config, {}, paths) == 0
    assert any("at most 25 names" in message for message in warnings(module))
    command = module.Popen.call_args.args[0]
    assert command[command.index("-d") + 1] == names(26)
