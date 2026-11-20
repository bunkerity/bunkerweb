"""Issuance warns, without failing, when a service asks for more names than its Let's Encrypt profile allows.

`classic` allows 100 names, `tlsserver` and `shortlived` 25. Past that the CA rejects the order, and
until the job said so the operator only saw an opaque ACME error. The warning is advisory: the job
still goes on and lets the CA decide. Refs #3251.
"""

import pytest

from test_certbot_jobs_execution import job_run  # noqa: F401 -- fixture, reused read-only


def names(count):
    return ",".join(f"h{n}.example.com" for n in range(count))


def warnings(state):
    return [call.args[0] for call in state.log.warning.call_args_list if "supports at most" in call.args[0]]


@pytest.mark.parametrize(
    "profile, count, limit",
    [("tlsserver", 26, 25), ("shortlived", 26, 25), ("classic", 101, 100)],
)
def test_names_over_the_profile_limit_are_reported(job_run, profile, count, limit):  # noqa: F811
    job_run.env["AUTO_LETS_ENCRYPT"] = "no"
    module, _ = job_run.load()

    module.warn_profile_name_limit("svc", {"acme_server": "letsencrypt", "profile": profile, "server_names": names(count)})

    found = warnings(job_run)
    assert len(found) == 1, found
    message = found[0]
    assert f"profile '{profile}' supports at most {limit} names, but {count} were requested" in message
    assert "[Service: svc]" in message


@pytest.mark.parametrize(
    "config",
    [
        {"acme_server": "letsencrypt", "profile": "tlsserver", "server_names": names(25)},  # exactly at the limit
        {"acme_server": "letsencrypt", "profile": "classic", "server_names": names(26)},  # classic is not limited at 25
        {"acme_server": "zerossl", "profile": "tlsserver", "server_names": names(40)},  # other CAs have their own limits
        {"acme_server": "letsencrypt", "profile": "custom", "server_names": names(40)},  # unknown profile: no verdict
    ],
)
def test_names_within_the_limit_or_out_of_scope_stay_silent(job_run, config):  # noqa: F811
    job_run.env["AUTO_LETS_ENCRYPT"] = "no"
    module, _ = job_run.load()

    module.warn_profile_name_limit("svc", config)

    assert warnings(job_run) == []
