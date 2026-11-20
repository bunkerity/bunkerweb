"""The real IP download job is driven by `USE_REAL_IP`, the name the plugin declares.

The job read `USE_REALIP`, a name no setting has, so with `USE_REAL_IP=yes` it logged
"RealIP is not activated" and never downloaded the trusted proxy list. Refs #422.
"""

import pytest
import requests

from _other_jobs_helpers import Cache, load_job

JOB = "realip/jobs/realip-download.py"


@pytest.fixture(autouse=True)
def _clean_realip_env(monkeypatch):
    for name in ("USE_REAL_IP", "USE_REALIP", "REAL_IP_FROM_URLS", "MULTISITE"):
        monkeypatch.delenv(name, raising=False)


def test_use_real_ip_yes_downloads_the_configured_list(tmp_path, monkeypatch, url_server):
    url_server.routes["/proxies"] = (200, b"192.0.2.0/24\n198.51.100.7\n", {})
    cache = Cache(tmp_path / "cache")

    _, status = load_job(
        monkeypatch,
        tmp_path,
        JOB,
        cache=cache,
        get=requests.get,
        env={"USE_REAL_IP": "yes", "REAL_IP_FROM_URLS": url_server.http("/proxies")},
    )

    assert status == 1
    assert url_server.hits == ["/proxies"]
    assert b"192.0.2.0/24" in b"".join(cache.data.values())


def test_the_misspelt_name_does_not_activate_the_job(tmp_path, monkeypatch, url_server):
    url_server.routes["/proxies"] = (200, b"192.0.2.0/24\n", {})

    _, status = load_job(
        monkeypatch,
        tmp_path,
        JOB,
        get=requests.get,
        env={"USE_REALIP": "yes", "REAL_IP_FROM_URLS": url_server.http("/proxies")},
    )

    assert status == 0
    assert url_server.hits == []


def test_multisite_reads_the_per_service_use_real_ip(tmp_path, monkeypatch, url_server):
    url_server.routes["/proxies"] = (200, b"192.0.2.0/24\n", {})
    cache = Cache(tmp_path / "cache")

    _, status = load_job(
        monkeypatch,
        tmp_path,
        JOB,
        cache=cache,
        get=requests.get,
        env={
            "SERVER_NAME": "one.example two.example",
            "MULTISITE": "yes",
            "one.example_USE_REAL_IP": "yes",
            "one.example_REAL_IP_FROM_URLS": url_server.http("/proxies"),
            "two.example_USE_REALIP": "yes",
            "two.example_REAL_IP_FROM_URLS": url_server.http("/never"),
        },
    )

    assert status == 1
    assert url_server.hits == ["/proxies"]
