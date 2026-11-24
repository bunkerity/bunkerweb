"""Data-Shield preset change: cache transition from the retired critical URL, and one download per URL per run."""

import hashlib
import logging
import os
import runpy
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import common_utils
import pytest
import requests

ROOT = Path(os.environ.get("BW_LISTS_PORT_ROOT", Path(__file__).resolve().parents[3]))
JOB = ROOT / "src/common/core/blacklist/jobs/blacklist-download.py"
BASE = "https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/"
STANDARD_URL = BASE + "prod_data-shield_ipv4_blocklist.txt"
CRITICAL_URL = BASE + "prod_critical_data-shield_ipv4_blocklist.txt"
FEED_URL = "https://feed.example/ip.txt"
AGGRESSIVE = "ip:laurent-minne-data-shield-aggressive"
CRITICAL = "ip:laurent-minne-data-shield-critical"


def legacy_file(url):
    """Cache name of the retired critical URL: written by an older job, one file per URL."""
    return f"{hashlib.sha1(url.encode()).hexdigest()}.list"


def url_file(url, kind="IP"):
    """Parsed cache of a URL for one kind: a kind never reads the parsed cache of another."""
    return f"{hashlib.sha1(f'{kind} {url}'.encode()).hexdigest()}.list"


class FileCache:
    """Job cache backed by real files, like the job's own cache directory."""

    def __init__(self, path):
        self.job_path = path
        self.job_path.mkdir(parents=True, exist_ok=True)
        self.fail_writes = set()  # cache names whose write fails
        self.raise_writes = set()  # cache names whose write raises
        self.raise_reads = set()  # cache names whose read raises
        self.raise_reads_once = set()  # cache names whose next read raises, the following ones work

    def path(self, name, service_id=""):
        return self.job_path / service_id / name if service_id else self.job_path / name

    def seed(self, name, data, service_id="", age=0):
        target = self.path(name, service_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        stamp = time.time() - age
        os.utime(target, (stamp, stamp))

    def get_cache(self, name, service_id="", with_info=False, with_data=True, **kwargs):
        if name in self.raise_reads:
            raise OSError("unreadable")
        if name in self.raise_reads_once:
            self.raise_reads_once.discard(name)
            raise OSError("transiently unreadable")
        target = self.path(name, service_id)
        if not target.is_file():
            return None
        return {"data": target.read_bytes(), "last_update": target.stat().st_mtime}

    def cache_file(self, name, data, service_id="", **kwargs):
        if name in self.raise_writes:
            raise OSError("disk exploded")
        if name in self.fail_writes:
            return False, "disk full"
        self.seed(name, data, service_id)
        return True, ""

    def cache_hash(self, name, service_id=""):
        target = self.path(name, service_id)
        return hashlib.sha512(target.read_bytes()).hexdigest() if target.is_file() else None

    def del_cache(self, name, service_id="", **kwargs):
        self.path(name, service_id).unlink(missing_ok=True)
        return True, ""

    def entries(self, service_id="a.example", kind="IP"):
        target = self.path(f"{kind}.list", service_id)
        return set(target.read_bytes().split()) if target.is_file() else None


def run_job(tmp_path, monkeypatch, responses, cache=None, **env):
    for key in list(os.environ):
        if "BLACKLIST_" in key:
            monkeypatch.delenv(key)
    for key, value in {"SERVER_NAME": "a.example", "MULTISITE": "no", "USE_BLACKLIST": "yes", **env}.items():
        monkeypatch.setenv(key, value)
    cache = cache or FileCache(tmp_path / "cache")
    requested = []

    def fake_get(url, **kwargs):
        requested.append(url)
        outcome = responses.get(url, (404, b""))
        if isinstance(outcome, Exception):
            raise outcome
        status, body = outcome
        return SimpleNamespace(status_code=status, content=body, headers={})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)  # the job waits between connection retries
    monkeypatch.setitem(sys.modules, "jobs", SimpleNamespace(Job=lambda *args: cache))
    monkeypatch.setitem(sys.modules, "logger", SimpleNamespace(getLogger=logging.getLogger))
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(JOB))
    return result.value.code, requested, cache


def seed_upgrading_instance(cache):
    """An instance upgraded from a build whose critical preset still downloaded the critical URL."""
    cache.seed(legacy_file(CRITICAL_URL), b"# Downloaded from " + CRITICAL_URL.encode() + b"\n192.0.2.9\n192.0.2.8\n", age=7200)
    cache.seed("IP.list", b"192.0.2.8\n192.0.2.9\n198.51.100.1\n", service_id="a.example", age=7200)


def test_critical_cache_kept_until_standard_has_a_valid_cache(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    seed_upgrading_instance(cache)
    # Standard fails (404) while another IP feed succeeds.
    _, requested, _ = run_job(
        tmp_path,
        monkeypatch,
        {FEED_URL: (200, b"198.51.100.1\n")},
        cache,
        BLACKLIST_COMMUNITY_LISTS=CRITICAL,
        BLACKLIST_IP_URLS=FEED_URL,
    )
    assert CRITICAL_URL not in requested
    assert cache.entries() == {b"192.0.2.8", b"192.0.2.9", b"198.51.100.1"}
    assert cache.path(legacy_file(CRITICAL_URL)).is_file()

    # Standard answers later: the service switches to it and the old cache is cleaned by the job's normal rules.
    run_job(
        tmp_path,
        monkeypatch,
        {FEED_URL: (200, b"198.51.100.1\n"), STANDARD_URL: (200, b"192.0.2.1\n")},
        cache,
        BLACKLIST_COMMUNITY_LISTS=CRITICAL,
        BLACKLIST_IP_URLS=FEED_URL,
    )
    assert cache.entries() == {b"192.0.2.1", b"198.51.100.1"}
    assert not cache.path(legacy_file(CRITICAL_URL)).exists()
    assert cache.path(url_file(STANDARD_URL)).is_file()


def test_critical_cache_kept_per_service_only_for_services_holding_critical(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    seed_upgrading_instance(cache)
    cache.seed(legacy_file(CRITICAL_URL), b"# Downloaded from " + CRITICAL_URL.encode() + b"\n192.0.2.9\n", age=7200)
    cache.seed("IP.list", b"192.0.2.9\n", service_id="a.example", age=7200)
    _, requested, _ = run_job(
        tmp_path,
        monkeypatch,
        {FEED_URL: (200, b"198.51.100.1\n")},
        cache,
        MULTISITE="yes",
        SERVER_NAME="a.example b.example",
        **{
            "a.example_BLACKLIST_COMMUNITY_LISTS": CRITICAL,
            "b.example_BLACKLIST_COMMUNITY_LISTS": AGGRESSIVE,
            "a.example_BLACKLIST_IP_URLS": FEED_URL,
            "b.example_BLACKLIST_IP_URLS": FEED_URL,
        },
    )
    assert CRITICAL_URL not in requested
    assert cache.entries("a.example") == {b"192.0.2.9", b"198.51.100.1"}
    assert cache.entries("b.example") == {b"198.51.100.1"}


def test_standard_failure_without_any_critical_cache_still_fails_cleanly(tmp_path, monkeypatch):
    code, _, cache = run_job(tmp_path, monkeypatch, {}, BLACKLIST_COMMUNITY_LISTS=CRITICAL)
    assert code == 2
    assert cache.entries() is None


def seed_standard(cache, age):
    cache.seed(url_file(STANDARD_URL), b"# Downloaded from " + STANDARD_URL.encode() + b"\n192.0.2.50\n", age=age)


def multisite(**intervals):
    env = {"MULTISITE": "yes", "SERVER_NAME": " ".join(intervals)}
    for service, interval in intervals.items():
        env[f"{service}_BLACKLIST_COMMUNITY_LISTS"] = AGGRESSIVE
        env[f"{service}_BLACKLIST_URLS_REFRESH_INTERVAL"] = interval
    return env


def test_shared_url_with_interval_zero_is_fetched_once(tmp_path, monkeypatch):
    code, requested, cache = run_job(tmp_path, monkeypatch, {STANDARD_URL: (200, b"192.0.2.1\n")}, **multisite(**{"a.example": "0", "b.example": "0"}))
    assert code == 1
    assert len(requested) == 1
    assert requested.count(STANDARD_URL) == 1
    assert cache.entries("a.example") == cache.entries("b.example") == {b"192.0.2.1"}


@pytest.mark.parametrize(
    "intervals",
    [
        {"a.example": "1h", "b.example": "0"},
        {"a.example": "0", "b.example": "1h"},
        {"a.example": "10m", "b.example": "1h"},
        {"a.example": "1h", "b.example": "10m"},
    ],
)
def test_shortest_interval_decides_whether_the_url_is_due(tmp_path, monkeypatch, intervals):
    cache = FileCache(tmp_path / "cache")
    seed_standard(cache, age=1800)  # 30 minutes old: fresh for 1h, due for 10m and 0
    _, requested, _ = run_job(tmp_path, monkeypatch, {STANDARD_URL: (200, b"192.0.2.1\n")}, cache, **multisite(**intervals))
    assert requested == [STANDARD_URL]
    assert cache.entries("a.example") == cache.entries("b.example") == {b"192.0.2.1"}


def test_url_stays_cached_when_every_interval_is_still_fresh(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    seed_standard(cache, age=1800)
    _, requested, _ = run_job(tmp_path, monkeypatch, {STANDARD_URL: (200, b"192.0.2.1\n")}, cache, **multisite(**{"a.example": "1h", "b.example": "2h"}))
    assert requested == []
    assert cache.entries("a.example") == cache.entries("b.example") == {b"192.0.2.50"}


def test_critical_cache_kept_when_the_standard_cache_write_fails(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    seed_upgrading_instance(cache)
    cache.fail_writes.add(url_file(STANDARD_URL))
    env = {"BLACKLIST_COMMUNITY_LISTS": CRITICAL, "BLACKLIST_IP_URLS": FEED_URL}

    # Standard downloads but is not persisted: the download is its data for this run, so the retired entries are not merged,
    # but the retired cache file stays for a later outage.
    run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"198.51.100.1\n"), STANDARD_URL: (200, b"192.0.2.1\n")}, cache, **env)
    assert cache.path(legacy_file(CRITICAL_URL)).is_file()
    assert not cache.path(url_file(STANDARD_URL)).exists()
    assert cache.entries() == {b"192.0.2.1", b"198.51.100.1"}

    # A later outage of Standard still finds them.
    run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"198.51.100.1\n")}, cache, **env)
    assert cache.path(legacy_file(CRITICAL_URL)).is_file()
    assert cache.entries() == {b"192.0.2.8", b"192.0.2.9", b"198.51.100.1"}


UA_URL = "https://feed.example/mixed.txt"
MIXED = b"192.0.2.1\nBadBot\n"
WRAPPED = {b"(?:\\b)192.0.2.1(?:\\b)", b"(?:\\b)BadBot(?:\\b)"}


def test_shared_url_keeps_a_parsed_cache_per_kind(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    env = {"BLACKLIST_IP_URLS": UA_URL, "BLACKLIST_USER_AGENT_URLS": UA_URL, "BLACKLIST_COMMUNITY_LISTS": ""}
    code, requested, _ = run_job(tmp_path, monkeypatch, {UA_URL: (200, MIXED)}, cache, **env)
    assert requested == [UA_URL]
    assert cache.entries(kind="IP") == {b"192.0.2.1"}
    assert cache.entries(kind="USER_AGENT") == WRAPPED
    assert b"BadBot" not in cache.path(url_file(UA_URL, "IP")).read_bytes()
    assert b"(?:" in cache.path(url_file(UA_URL, "USER_AGENT")).read_bytes()

    # Fresh caches: nothing is requested, and each kind is served its own cache, never the other kind's.
    code, requested, _ = run_job(tmp_path, monkeypatch, {UA_URL: (200, b"203.0.113.9\n")}, cache, **env)
    assert requested == []
    assert cache.entries(kind="IP") == {b"192.0.2.1"}
    assert cache.entries(kind="USER_AGENT") == WRAPPED


def test_kind_that_rejects_every_entry_is_a_failure_and_never_borrows_another_kinds_cache(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    env = {"BLACKLIST_IP_URLS": UA_URL, "BLACKLIST_USER_AGENT_URLS": UA_URL, "BLACKLIST_COMMUNITY_LISTS": ""}
    for expected in (3, 2):  # the first run publishes USER_AGENT.list, the second changes nothing
        code, _, _ = run_job(tmp_path, monkeypatch, {UA_URL: (200, b"BadBot\n")}, cache, **env)
        assert code == expected
        assert cache.entries(kind="IP") is None
        assert cache.entries(kind="USER_AGENT") == {b"(?:\\b)BadBot(?:\\b)"}


def test_fetched_body_is_dropped_after_its_last_consumer(tmp_path, monkeypatch):
    seen = []
    original = common_utils.iter_list_entries

    def spy(*args, **kwargs):
        fetched = sys._getframe(1).f_globals["fetched"]
        seen.append((fetched, set(fetched)))
        return original(*args, **kwargs)

    monkeypatch.setattr(common_utils, "iter_list_entries", spy)
    only, shared = "https://feed.example/only.txt", "https://feed.example/shared.txt"
    env = {"MULTISITE": "yes", "SERVER_NAME": "a.example b.example c.example"}
    # c reads the shared body as another kind: the same kind would reuse the completed entries of b and never parse it
    for service, url, kind in (("a.example", only, "IP"), ("b.example", shared, "IP"), ("c.example", shared, "IGNORE_IP")):
        env[f"{service}_BLACKLIST_{kind}_URLS"] = url
        env[f"{service}_BLACKLIST_COMMUNITY_LISTS"] = ""
        env[f"{service}_BLACKLIST_URLS_REFRESH_INTERVAL"] = "0"
    run_job(tmp_path, monkeypatch, {only: (200, b"192.0.2.1\n"), shared: (200, b"192.0.2.2\n")}, **env)
    # a single-consumer body is gone before the next URL is parsed, the shared one is kept for its second consumer only
    assert [urls for _, urls in seen] == [{only}, {shared}, {shared}]
    assert not seen[-1][0]


FEED2_URL = "https://feed2.example/ip.txt"


def seed_legacy(cache, url, *lines, age=7200):
    """An instance upgraded from a build that cached the parsed entries of a URL under sha1(url) only."""
    cache.seed(legacy_file(url), b"# Downloaded from " + url.encode() + b"\n" + b"".join(line + b"\n" for line in lines), age=age)


def test_legacy_cache_survives_a_feed_outage_after_upgrade(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    seed_legacy(cache, FEED2_URL, b"192.0.2.5")
    cache.seed("IP.list", b"192.0.2.5\n198.51.100.1\n", service_id="a.example", age=7200)
    env = {"BLACKLIST_COMMUNITY_LISTS": "", "BLACKLIST_IP_URLS": f"{FEED_URL} {FEED2_URL}"}

    # First run after the upgrade: feed 2 is down and feed 1 answers. The list keeps the legacy entries, the legacy file stays.
    code, _, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"198.51.100.1\n")}, cache, **env)
    assert code == 2
    assert cache.entries() == {b"192.0.2.5", b"198.51.100.1"}
    assert cache.path(legacy_file(FEED2_URL)).is_file()
    assert not cache.path(url_file(FEED2_URL)).exists()

    # Feed 2 answers later: it gets its own cache and the legacy file goes.
    code, _, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"198.51.100.1\n"), FEED2_URL: (200, b"192.0.2.6\n")}, cache, **env)
    assert code == 1
    assert cache.entries() == {b"192.0.2.6", b"198.51.100.1"}
    assert cache.path(url_file(FEED2_URL)).is_file()
    assert not cache.path(legacy_file(FEED2_URL)).exists()


def test_legacy_cache_is_kept_until_every_kind_of_a_shared_url_has_its_own_cache(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    # The old job kept one file for the URL: an IP line and a URI line, which no single kind accepts together.
    seed_legacy(cache, UA_URL, b"192.0.2.1", b"/admin")
    env = {"BLACKLIST_COMMUNITY_LISTS": "", "BLACKLIST_IP_URLS": UA_URL, "BLACKLIST_URI_URLS": UA_URL}

    # Outage: each kind keeps only the legacy lines it accepts.
    run_job(tmp_path, monkeypatch, {}, cache, **env)
    assert cache.entries(kind="IP") == {b"192.0.2.1"}
    assert cache.entries(kind="URI") == {b"/admin"}
    assert cache.path(legacy_file(UA_URL)).is_file()

    # The feed answers with IP lines only: IP is persisted, URI rejects the body and still has no cache of its own.
    code, _, _ = run_job(tmp_path, monkeypatch, {UA_URL: (200, b"192.0.2.7\n")}, cache, **env)
    assert code == 3  # a list changed and a source failed
    assert cache.path(url_file(UA_URL, "IP")).is_file()
    assert not cache.path(url_file(UA_URL, "URI")).exists()
    assert cache.entries(kind="IP") == {b"192.0.2.7"}
    assert cache.entries(kind="URI") == {b"/admin"}
    assert cache.path(legacy_file(UA_URL)).is_file()

    # Both kinds persisted: the legacy file is cleaned.
    code, _, _ = run_job(tmp_path, monkeypatch, {UA_URL: (200, b"192.0.2.7\n/admin\n")}, cache, **env)
    assert code == 0  # both lists are unchanged
    assert cache.entries(kind="URI") == {b"/admin"}
    assert cache.path(url_file(UA_URL, "URI")).is_file()
    assert not cache.path(legacy_file(UA_URL)).exists()


def test_legacy_user_agent_lines_must_be_wrapped_and_a_useless_legacy_file_is_not_kept(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    seed_legacy(cache, UA_URL, b"192.0.2.1", b"(?:\\b)BadBot(?:\\b)")
    env = {"BLACKLIST_COMMUNITY_LISTS": "", "BLACKLIST_USER_AGENT_URLS": UA_URL}
    run_job(tmp_path, monkeypatch, {}, cache, **env)
    assert cache.entries(kind="USER_AGENT") == {b"(?:\\b)BadBot(?:\\b)"}  # the raw IP line is no user agent entry
    assert cache.path(legacy_file(UA_URL)).is_file()

    other = FileCache(tmp_path / "other")
    seed_legacy(other, FEED_URL, b"/admin")  # nothing the IP kind accepts
    run_job(tmp_path, monkeypatch, {}, other, BLACKLIST_COMMUNITY_LISTS="", BLACKLIST_IP_URLS=FEED_URL)
    assert not other.path(legacy_file(FEED_URL)).exists()
    assert other.entries() is None


def test_source_without_any_data_contributes_nothing_and_old_published_entries_go(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    # Feed 2 has no per-kind cache, no legacy cache and no download: it has nothing. 192.0.2.5 lives only in the published list.
    cache.seed("IGNORE_IP.list", b"192.0.2.5\n198.51.100.1\n", service_id="a.example", age=7200)
    env = {"BLACKLIST_COMMUNITY_LISTS": "", "BLACKLIST_IGNORE_IP_URLS": f"{FEED_URL} {FEED2_URL}"}
    code, _, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"198.51.100.2\n")}, cache, **env)
    assert code == 3  # a list changed and a source failed
    assert cache.entries(kind="IGNORE_IP") == {b"198.51.100.2"}

    # Once feed 2 answers, the list is its own sources.
    code, _, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"198.51.100.2\n"), FEED2_URL: (200, b"192.0.2.6\n")}, cache, **env)
    assert code == 1
    assert cache.entries(kind="IGNORE_IP") == {b"192.0.2.6", b"198.51.100.2"}


def test_source_removed_from_the_config_leaves_the_list_while_another_source_has_no_data(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    # The published list still holds the entries of FEED2_URL, no longer configured; the configured FEED_URL has no data.
    cache.seed("IP.list", b"192.0.2.5\n198.51.100.1\n", service_id="a.example", age=7200)
    cache.seed(url_file(UA_URL), b"# Downloaded from " + UA_URL.encode() + b"\n203.0.113.3\n", age=7200)
    env = {"BLACKLIST_COMMUNITY_LISTS": "", "BLACKLIST_IP_URLS": f"{FEED_URL} {UA_URL}"}
    run_job(tmp_path, monkeypatch, {}, cache, **env)
    assert cache.entries() == {b"203.0.113.3"}


def test_legacy_cache_read_error_freezes_the_list_and_keeps_the_file(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    seed_legacy(cache, FEED2_URL, b"192.0.2.5")
    cache.seed("IP.list", b"192.0.2.5\n198.51.100.1\n", service_id="a.example", age=7200)
    before = cache.path("IP.list", "a.example").read_bytes()
    cache.raise_reads.add(legacy_file(FEED2_URL))
    env = {"BLACKLIST_COMMUNITY_LISTS": "", "BLACKLIST_IP_URLS": f"{FEED_URL} {FEED2_URL}"}
    code, _, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"198.51.100.2\n")}, cache, **env)
    assert code == 2
    assert cache.path("IP.list", "a.example").read_bytes() == before
    assert cache.path(legacy_file(FEED2_URL)).is_file()
    assert cache.path(url_file(FEED_URL)).is_file()  # the healthy feed still caches its own data


def test_retired_cache_read_error_freezes_the_list_and_keeps_the_file(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    seed_upgrading_instance(cache)
    before = cache.path("IP.list", "a.example").read_bytes()
    cache.raise_reads.add(legacy_file(CRITICAL_URL))
    code, _, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"198.51.100.2\n")}, cache, BLACKLIST_COMMUNITY_LISTS=CRITICAL, BLACKLIST_IP_URLS=FEED_URL)
    assert code == 2
    assert cache.path("IP.list", "a.example").read_bytes() == before
    assert cache.path(legacy_file(CRITICAL_URL)).is_file()


def test_read_error_of_one_kind_leaves_the_other_kind_of_the_same_url_published(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    for kind, line in (("IP", b"192.0.2.1"), ("USER_AGENT", b"(?:\\b)BadBot(?:\\b)")):
        cache.seed(url_file(UA_URL, kind), b"# Downloaded from " + UA_URL.encode() + b"\n" + line + b"\n", age=7200)
        cache.seed(f"{kind}.list", line + b"\nstale\n", service_id="a.example", age=7200)
    before = cache.path("IP.list", "a.example").read_bytes()
    cache.raise_reads.add(url_file(UA_URL, "IP"))
    code, _, _ = run_job(tmp_path, monkeypatch, {}, cache, **shared_kinds_env())  # feed down: both kinds go to their cache
    assert code == 3  # a list changed and a source failed
    assert cache.path("IP.list", "a.example").read_bytes() == before
    assert cache.path(url_file(UA_URL, "IP")).is_file()
    assert cache.entries(kind="USER_AGENT") == {b"(?:\\b)BadBot(?:\\b)"}


def shared_kinds_env():
    return {"BLACKLIST_COMMUNITY_LISTS": "", "BLACKLIST_IP_URLS": UA_URL, "BLACKLIST_USER_AGENT_URLS": UA_URL}


def test_cache_write_exception_is_scoped_to_its_kind(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    cache.seed(url_file(UA_URL, "IP"), b"# Downloaded from " + UA_URL.encode() + b"\n192.0.2.100\n", age=7200)
    cache.raise_writes.add(url_file(UA_URL, "IP"))
    code, requested, _ = run_job(tmp_path, monkeypatch, {UA_URL: (200, MIXED)}, cache, **shared_kinds_env())
    assert requested == [UA_URL]  # the body already in memory serves the second kind
    assert code == 3  # a list changed and a source failed
    assert cache.entries(kind="IP") == {b"192.0.2.1"}  # the complete download is the kind's data, persisted or not
    assert cache.entries(kind="USER_AGENT") == WRAPPED
    assert cache.path(url_file(UA_URL, "USER_AGENT")).is_file()


def test_parse_exception_is_scoped_to_its_kind(tmp_path, monkeypatch):
    original = common_utils.iter_list_entries

    def broken_for_ip(*args, **kwargs):
        if kwargs.get("ip_list"):
            raise ValueError("unparsable")
        return original(*args, **kwargs)

    monkeypatch.setattr(common_utils, "iter_list_entries", broken_for_ip)
    cache = FileCache(tmp_path / "cache")
    cache.seed(url_file(UA_URL, "IP"), b"# Downloaded from " + UA_URL.encode() + b"\n192.0.2.100\n", age=7200)
    code, requested, _ = run_job(tmp_path, monkeypatch, {UA_URL: (200, MIXED)}, cache, **shared_kinds_env())
    assert requested == [UA_URL]
    assert code == 3  # a list changed and a source failed
    assert cache.entries(kind="IP") == {b"192.0.2.100"}
    assert cache.entries(kind="USER_AGENT") == WRAPPED


def test_transport_error_still_fails_the_whole_url(tmp_path, monkeypatch):
    code, requested, _ = run_job(tmp_path, monkeypatch, {UA_URL: requests.ConnectionError("refused")}, **shared_kinds_env())
    assert code == 2
    assert requested == [UA_URL] * 3  # three attempts for the first kind, none for the second


def test_exit_status_is_3_when_a_list_changes_and_another_source_has_a_cache_error(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    # b.example has a cached feed that cannot be read while its feed is down: it freezes. a.example changes on the same run.
    cache.seed(url_file(FEED2_URL), b"# Downloaded from " + FEED2_URL.encode() + b"\n192.0.2.5\n", age=7200)
    cache.seed("IP.list", b"192.0.2.5\n", service_id="b.example", age=7200)
    cache.raise_reads.add(url_file(FEED2_URL))
    env = {
        "MULTISITE": "yes",
        "SERVER_NAME": "a.example b.example",
        "a.example_BLACKLIST_COMMUNITY_LISTS": "",
        "a.example_BLACKLIST_IP_URLS": FEED_URL,
        "b.example_BLACKLIST_COMMUNITY_LISTS": "",
        "b.example_BLACKLIST_IP_URLS": FEED2_URL,
    }
    code, _, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"198.51.100.2\n")}, cache, **env)
    assert code == 3
    assert cache.entries("a.example") == {b"198.51.100.2"}
    assert cache.entries("b.example") == {b"192.0.2.5"}


def test_exit_status_is_1_for_a_change_2_for_an_error_and_0_for_neither(tmp_path, monkeypatch):
    env = {"BLACKLIST_COMMUNITY_LISTS": "", "BLACKLIST_IP_URLS": FEED_URL}
    cache = FileCache(tmp_path / "cache")
    assert run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"198.51.100.2\n")}, cache, **env)[0] == 1
    assert run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"198.51.100.2\n")}, cache, **env)[0] == 0  # fresh cache: nothing to do
    assert run_job(tmp_path, monkeypatch, {}, FileCache(tmp_path / "empty"), **env)[0] == 2  # feed down, nothing cached


def break_the_parser_after_two_entries(monkeypatch):
    def broken(body, **kwargs):
        yield b"192.0.2.1"
        yield b"192.0.2.2"
        raise ValueError("truncated")

    monkeypatch.setattr(common_utils, "iter_list_entries", broken)


def test_parser_that_raises_after_yielding_adds_nothing_and_the_last_good_data_is_used(tmp_path, monkeypatch):
    break_the_parser_after_two_entries(monkeypatch)
    cache = FileCache(tmp_path / "cache")
    good = b"# Downloaded from " + FEED_URL.encode() + b"\n192.0.2.100\n"
    cache.seed(url_file(FEED_URL), good, age=7200)
    cache.seed("IP.list", b"192.0.2.100\n", service_id="a.example", age=7200)
    code, requested, _ = run_job(
        tmp_path, monkeypatch, {FEED_URL: (200, b"192.0.2.1\n192.0.2.2\n192.0.2.3\n")}, cache, BLACKLIST_COMMUNITY_LISTS="", BLACKLIST_IP_URLS=FEED_URL
    )
    assert requested == [FEED_URL]
    assert code == 2
    assert cache.entries() == {b"192.0.2.100"}
    assert cache.path(url_file(FEED_URL)).read_bytes() == good


def test_parser_that_raises_after_yielding_freezes_the_list_when_the_last_good_data_cannot_be_read(tmp_path, monkeypatch):
    break_the_parser_after_two_entries(monkeypatch)
    cache = FileCache(tmp_path / "cache")
    good = b"# Downloaded from " + FEED_URL.encode() + b"\n192.0.2.100\n"
    cache.seed(url_file(FEED_URL), good, age=7200)
    cache.seed("IP.list", b"192.0.2.100\n198.51.100.1\n", service_id="a.example", age=7200)
    before = cache.path("IP.list", "a.example").read_bytes()
    cache.raise_reads.add(url_file(FEED_URL))
    code, _, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"192.0.2.1\n")}, cache, BLACKLIST_COMMUNITY_LISTS="", BLACKLIST_IP_URLS=FEED_URL)
    assert code == 2
    assert cache.path("IP.list", "a.example").read_bytes() == before
    assert cache.path(url_file(FEED_URL)).read_bytes() == good


def seed_ignore_ip_source_with_legacy_file(cache):
    """An IGNORE_IP source whose legacy file still lists 192.0.2.8, which the feed has dropped since."""
    cache.seed(legacy_file(FEED_URL), b"# Downloaded from " + FEED_URL.encode() + b"\n192.0.2.7\n192.0.2.8\n", age=7200)
    cache.seed("IGNORE_IP.list", b"192.0.2.7\n192.0.2.8\n", service_id="a.example", age=7200)
    cache.fail_writes.add(url_file(FEED_URL, "IGNORE_IP"))
    return {"BLACKLIST_COMMUNITY_LISTS": "", "BLACKLIST_IGNORE_IP_URLS": FEED_URL}


def test_complete_download_whose_cache_write_fails_does_not_bring_back_the_legacy_entries(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    env = seed_ignore_ip_source_with_legacy_file(cache)
    code, _, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"192.0.2.7\n")}, cache, **env)
    assert code == 3  # the list changed and the cache write failed
    assert cache.entries(kind="IGNORE_IP") == {b"192.0.2.7"}  # the revoked exception stays revoked
    assert cache.path(legacy_file(FEED_URL)).is_file()  # kept: the per-kind cache was not persisted
    assert not cache.path(url_file(FEED_URL, "IGNORE_IP")).exists()


def test_complete_download_whose_cache_write_raises_does_not_bring_back_the_legacy_entries(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    env = seed_ignore_ip_source_with_legacy_file(cache)
    cache.fail_writes.clear()
    cache.raise_writes.add(url_file(FEED_URL, "IGNORE_IP"))
    code, requested, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"192.0.2.7\n")}, cache, **env)
    assert code == 3  # the list changed and the cache write failed
    assert requested == [FEED_URL]
    assert cache.entries(kind="IGNORE_IP") == {b"192.0.2.7"}  # the revoked exception stays revoked
    assert cache.path(legacy_file(FEED_URL)).is_file()  # kept: the per-kind cache was not persisted
    assert not cache.path(url_file(FEED_URL, "IGNORE_IP")).exists()


def test_cache_write_that_raises_does_not_reject_the_url_for_the_next_service(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    env = seed_ignore_ip_source_with_legacy_file(cache)
    cache.fail_writes.clear()
    cache.raise_writes.add(url_file(FEED_URL, "IGNORE_IP"))
    cache.seed("IGNORE_IP.list", b"192.0.2.7\n192.0.2.8\n", service_id="b.example", age=7200)
    env = {
        "MULTISITE": "yes",
        "SERVER_NAME": "a.example b.example",
        "a.example_BLACKLIST_COMMUNITY_LISTS": "",
        "a.example_BLACKLIST_IGNORE_IP_URLS": FEED_URL,
        "b.example_BLACKLIST_COMMUNITY_LISTS": "",
        "b.example_BLACKLIST_IGNORE_IP_URLS": FEED_URL,
    }
    code, requested, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"192.0.2.7\n")}, cache, **env)
    assert code == 3
    assert requested == [FEED_URL]  # one request for both services
    assert cache.entries("a.example", "IGNORE_IP") == {b"192.0.2.7"}
    assert cache.entries("b.example", "IGNORE_IP") == {b"192.0.2.7"}  # the same complete download, not the legacy file
    assert cache.path(legacy_file(FEED_URL)).is_file()


SHARED_ENV = {
    "MULTISITE": "yes",
    "SERVER_NAME": "a.example b.example",
    "a.example_BLACKLIST_COMMUNITY_LISTS": "",
    "a.example_BLACKLIST_IGNORE_IP_URLS": FEED_URL,
    "b.example_BLACKLIST_COMMUNITY_LISTS": "",
    "b.example_BLACKLIST_IGNORE_IP_URLS": FEED_URL,
}


def test_complete_result_of_one_service_is_used_by_the_next_even_when_the_cache_is_readable_again(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    old = b"# Downloaded from " + FEED_URL.encode() + b"\n192.0.2.8\n"
    cache.seed(url_file(FEED_URL, "IGNORE_IP"), old, age=0)  # fresh
    for service in ("a.example", "b.example"):
        cache.seed("IGNORE_IP.list", b"192.0.2.8\n", service_id=service, age=7200)
    cache.raise_reads_once.add(url_file(FEED_URL, "IGNORE_IP"))  # service a hits a transient read error
    cache.fail_writes.add(url_file(FEED_URL, "IGNORE_IP"))
    code, requested, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"192.0.2.7\n")}, cache, **SHARED_ENV)
    assert code == 3
    assert requested == [FEED_URL]
    assert cache.entries("a.example", "IGNORE_IP") == {b"192.0.2.7"}
    assert cache.entries("b.example", "IGNORE_IP") == {b"192.0.2.7"}  # the complete result of a, not the old cache


def test_services_sharing_a_fresh_cache_both_use_it_without_a_request(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    cache.seed(url_file(FEED_URL, "IGNORE_IP"), b"# Downloaded from " + FEED_URL.encode() + b"\n192.0.2.8\n", age=0)
    code, requested, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"192.0.2.7\n")}, cache, **SHARED_ENV)
    assert code == 1  # the services have no published list yet
    assert requested == []
    assert cache.entries("a.example", "IGNORE_IP") == {b"192.0.2.8"}
    assert cache.entries("b.example", "IGNORE_IP") == {b"192.0.2.8"}


def test_failed_cache_write_without_a_list_change_exits_2(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    env = seed_ignore_ip_source_with_legacy_file(cache)
    cache.seed("IGNORE_IP.list", b"192.0.2.7\n", service_id="a.example", age=7200)
    code, _, _ = run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"192.0.2.7\n")}, cache, **env)
    assert code == 2
    assert cache.entries(kind="IGNORE_IP") == {b"192.0.2.7"}
    assert cache.path(legacy_file(FEED_URL)).is_file()


def test_legacy_file_is_still_the_fallback_when_the_feed_goes_down_after_a_failed_cache_write(tmp_path, monkeypatch):
    cache = FileCache(tmp_path / "cache")
    env = seed_ignore_ip_source_with_legacy_file(cache)
    run_job(tmp_path, monkeypatch, {FEED_URL: (200, b"192.0.2.7\n")}, cache, **env)
    assert cache.entries(kind="IGNORE_IP") == {b"192.0.2.7"}
    code, _, _ = run_job(tmp_path, monkeypatch, {}, cache, **env)  # feed down, the per-kind cache never persisted
    assert code == 3
    assert cache.entries(kind="IGNORE_IP") == {b"192.0.2.7", b"192.0.2.8"}
    assert cache.path(legacy_file(FEED_URL)).is_file()


@pytest.mark.parametrize("servers", ["a.example b.example", "b.example a.example"], ids=["standard-first", "critical-first"])
def test_reused_result_keeps_the_retired_cache_of_a_service_when_the_write_failed(tmp_path, monkeypatch, servers):
    cache = FileCache(tmp_path / "cache")
    seed_upgrading_instance(cache)
    cache.fail_writes.add(url_file(STANDARD_URL))
    # a.example has the plain Standard preset, b.example the retired Critical one with its retired cache file: both share STANDARD_URL
    env = {
        "MULTISITE": "yes",
        "SERVER_NAME": servers,
        "a.example_BLACKLIST_COMMUNITY_LISTS": AGGRESSIVE,
        "b.example_BLACKLIST_COMMUNITY_LISTS": CRITICAL,
    }
    code, requested, _ = run_job(tmp_path, monkeypatch, {STANDARD_URL: (200, b"192.0.2.1\n")}, cache, **env)
    assert code == 3  # a list changed and the cache write failed
    assert requested == [STANDARD_URL]
    assert cache.entries("a.example") == cache.entries("b.example") == {b"192.0.2.1"}
    assert cache.path(legacy_file(CRITICAL_URL)).is_file()  # the service that only reused the result keeps its fallback too
