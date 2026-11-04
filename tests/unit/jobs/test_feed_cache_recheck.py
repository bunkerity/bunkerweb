"""Fresh URL caches obey current validators without rewrapping user-agent regexes."""

import ast
from pathlib import Path

import pytest

from common_utils import bytes_hash
from _other_jobs_helpers import Cache, load_job

URL = "https://feeds.example/list"
URL_FILE = f"{bytes_hash(URL, algorithm='sha1')}.list"
KINDS = {
    "realip": ("IP",),
    "blacklist": ("IP", "RDNS", "ASN", "URI", "IGNORE_IP", "IGNORE_RDNS", "IGNORE_ASN", "IGNORE_URI"),
    "greylist": ("IP", "RDNS", "ASN", "URI"),
    "whitelist": ("IP", "RDNS", "ASN", "URI"),
    "dnsbl": ("IGNORE_IP",),
}
RECHECKED = [(plugin, kind) for plugin, kinds in KINDS.items() for kind in kinds]

# Same corpus as the pre-edit idempotence probe, including existing feed fixtures.
CORPUS = set()
for filename in ("test_ipv6_feed_zone_ids.py", "test_lists_port_download.py", "test_dnsbl_ignore_download.py"):
    for node in ast.walk(ast.parse(Path(__file__).with_name(filename).read_text())):
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            value = node.value.encode() if isinstance(node.value, str) else node.value
            CORPUS.update(value.splitlines())
CORPUS.update(
    (
        b"192.0.2.1",
        b"192.0.2.0/24",
        b"2001:db8::1",
        b"2001:db8::/32",
        b"2001:0DB8:0000:0000:0000:0000:0000:0001",
        b"::ffff:192.0.2.1",
        b"fe80::1%eth0",
        b"fe80::%eth0/64",
        b"EXAMPLE.COM",
        b"example.com",
        b"AS123",
        b"as456",
        b"123",
        b"Mozilla/5.0 Example Bot",
        b"/admin",
        b"/api?x=1",
        b"",
    )
)


def run_cached_job(plugin, kind, content, tmp_path, monkeypatch, cache=None):
    if cache is None:
        cache = Cache(tmp_path / "cache")
        cache.cache_file(URL_FILE, b"# Downloaded from " + URL.encode() + b"\n" + content)
    setting = "REAL_IP_FROM_URLS" if plugin == "realip" else f"{plugin.upper()}_{kind}_URLS"
    env = {
        "SERVER_NAME": "lists.example",
        "MULTISITE": "no",
        "USE_REAL_IP" if plugin == "realip" else f"USE_{plugin.upper()}": "yes",
        "BLACKLIST_COMMUNITY_LISTS": "",
        setting: URL,
    }
    module, status = load_job(monkeypatch, tmp_path, f"{plugin}/jobs/{plugin}-download.py", cache=cache, env=env)
    name = "combined.list" if plugin == "realip" else f"{kind}.list"
    return module, status, cache, cache.data["" if plugin == "realip" else "lists.example", name]


@pytest.mark.parametrize(("plugin", "kind"), [(p, k) for p, k in RECHECKED if k in ("IP", "IGNORE_IP")])
def test_fresh_cached_ip_entries_drop_zone_ids(plugin, kind, tmp_path, monkeypatch):
    content = b"fe80::1%eth0\n192.0.2.1\nfe80::%eth0/64\n2001:db8::/32\n"
    _, status, _, published = run_cached_job(plugin, kind, content, tmp_path, monkeypatch)
    assert status == 1
    assert published == b"192.0.2.1\n2001:db8::/32\n"


def test_cached_user_agent_bytes_survive_two_runs(tmp_path, monkeypatch):
    content = b"(?:\\b)Mozilla/5.0 Example Bot(?:\\b)\n"
    _, status, cache, published = run_cached_job("blacklist", "IGNORE_USER_AGENT", content, tmp_path, monkeypatch)
    assert status == 1
    assert published == content
    _, status, _, published = run_cached_job("blacklist", "IGNORE_USER_AGENT", content, tmp_path, monkeypatch, cache=cache)
    assert status == 0
    assert published == content
    assert cache.data["", URL_FILE] == b"# Downloaded from " + URL.encode() + b"\n" + content


@pytest.mark.parametrize(("plugin", "kind"), RECHECKED)
def test_validated_corpus_round_trips_through_cache(plugin, kind, tmp_path, monkeypatch):
    module, status = load_job(monkeypatch, tmp_path, f"{plugin}/jobs/{plugin}-download.py", env={"SERVER_NAME": ""})
    assert status == 0
    entries = set()
    for line in CORPUS:
        if plugin == "dnsbl":
            data = module.check_ip_line(line)
            if data is not None:
                assert module.check_ip_line(data) == data
                entries.add(data)
        else:
            ok, data = module.check_line(line) if plugin == "realip" else module.check_line(kind, line)
            if ok:
                assert (module.check_line(data) if plugin == "realip" else module.check_line(kind, data)) == (True, data)
                entries.add(data)
    assert entries, (plugin, kind)
    content = b"\n".join(sorted(entries)) + b"\n"
    _, status, _, published = run_cached_job(plugin, kind, content, tmp_path, monkeypatch)
    assert status == 1
    assert published == content
