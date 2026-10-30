"""A zone id in a downloaded feed ("fe80::1%eth0") never reaches the cache the matchers read.

A zone id names an interface of the downloading host: neither NGINX nor the Lua matcher can load it, and it used to be
written to the cached list as a valid entry. The valid entries around it are kept.
"""

import pytest
import requests

from _other_jobs_helpers import Cache, load_job

FEED = b"2001:db8::/32\nfe80::1%eth0\n192.0.2.0/24\nfe80::%eth0/64\n198.51.100.7\n"
JOBS = [
    ("dnsbl/jobs/dnsbl-download.py", {"DNSBL_IGNORE_IP_URLS": "{url}"}),
    ("realip/jobs/realip-download.py", {"USE_REAL_IP": "yes", "REAL_IP_FROM_URLS": "{url}"}),
    ("blacklist/jobs/blacklist-download.py", {"USE_BLACKLIST": "yes", "BLACKLIST_COMMUNITY_LISTS": "", "BLACKLIST_IP_URLS": "{url}"}),
    ("greylist/jobs/greylist-download.py", {"USE_GREYLIST": "yes", "GREYLIST_IP_URLS": "{url}"}),
    ("whitelist/jobs/whitelist-download.py", {"USE_WHITELIST": "yes", "WHITELIST_IP_URLS": "{url}"}),
]


@pytest.mark.parametrize(("job", "env"), JOBS, ids=[job.split("/")[0] for job, _ in JOBS])
def test_zone_id_entries_are_dropped_and_the_valid_ones_kept(job, env, tmp_path, monkeypatch, url_server):
    for name in ("MULTISITE", "SERVER_NAME"):
        monkeypatch.delenv(name, raising=False)
    url_server.routes["/feed"] = (200, FEED, {})
    cache = Cache(tmp_path / "cache")
    url = url_server.http("/feed")

    _, status = load_job(monkeypatch, tmp_path, job, cache=cache, get=requests.get, env={k: v.format(url=url) for k, v in env.items()})

    cached = b"\n".join(cache.data.values())
    assert url_server.hits == ["/feed"], "the feed was never downloaded"
    assert status == 1
    assert b"2001:db8::/32" in cached and b"192.0.2.0/24" in cached and b"198.51.100.7" in cached
    assert b"%" not in cached, cached
