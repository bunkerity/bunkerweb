"""Scheduler script contracts through real cache files and database rows; no remote I/O."""

import gzip
import hashlib
import importlib.util
import json
import logging
import os
import socket
import subprocess
import sys
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from tarfile import open as tar_open
from types import SimpleNamespace
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

import mmdb
import common_utils
from _other_jobs_helpers import ROOT, load_job
from fixtures.seed import FIXED_DT, seed_minimal, session
from jobs import Job as RealJob
from model import Jobs, Jobs_cache, Jobs_runs, Plugins, Services

pytestmark = pytest.mark.multiengine


def _module(path):
    spec = importlib.util.spec_from_file_location("job_contract_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def no_remote_io(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError(f"Unexpected network operation: {args}")

    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(requests.sessions.Session, "request", blocked)
    monkeypatch.setattr(mmdb, "_open_response", blocked)
    monkeypatch.setattr(mmdb, "sleep", lambda _: None)
    monkeypatch.setattr(common_utils, "get_version", lambda: "1.6.18")
    monkeypatch.setattr(common_utils, "get_integration", lambda: "Docker")
    monkeypatch.setattr(common_utils, "get_os_info", lambda: {"id": "unit"})
    # Prevent a developer's shell settings from selecting unrelated services or endpoints.
    for key in tuple(os.environ):
        if key in ("API_LISTEN_HTTPS", "FORCE_BACKUP", "USE_BACKUP", "BACKUP_SCHEDULE", "BACKUP_ROTATION") or any(
            term in key for term in ("BUNKERNET", "CUSTOM_SSL", "BLACKLIST", "GREYLIST", "WHITELIST")
        ):
            monkeypatch.delenv(key)


@pytest.fixture
def runtime(db, tmp_path, monkeypatch):
    seed_minimal(db)
    assert db.set_metadata({"scheduler_first_start": False}) == ""
    with session(db) as s:
        for service in ("app.example", "alias.example", "off.example"):
            s.add(Services(id=service, method="manual", creation_date=FIXED_DT, last_update=FIXED_DT))

    def create(relative):
        plugin, _, filename = relative.split("/")
        name = Path(filename).stem
        with session(db) as s:
            if s.get(Plugins, plugin) is None:
                s.add(Plugins(id=plugin, name=plugin, description="Unit fixture", version="1.0"))
                s.flush()
            if s.get(Jobs, name) is None:
                s.add(Jobs(name=name, plugin_id=plugin, file_name=filename, every="day"))
        # Only construction/auto-restore is bypassed: every cache read, hash, write and delete is real.
        job = RealJob.__new__(RealJob)
        job.job_path = tmp_path / "system/var/cache/bunkerweb" / plugin
        job.job_path.mkdir(parents=True, exist_ok=True)
        job.job_name, job.db, job.logger, job.restore_ok = name, db, logging.getLogger("job-contract"), True

        def run(**kwargs):
            return load_job(monkeypatch, tmp_path, relative, cache=job, database=db, **kwargs)

        return job, run

    return create


def _row(job, name, service=""):
    with session(job.db) as s:
        row = s.query(Jobs_cache).filter_by(job_name=job.job_name, file_name=name, service_id=service or None).one()
        return row.data, row.checksum


def _assert_file(job, name, content, service="", mode=0o600):
    path = job.job_path / service / name
    assert path.read_bytes() == content
    assert path.stat().st_mode & 0o777 == mode
    assert _row(job, name, service) == (content, hashlib.sha512(content).hexdigest())


def _response(content=b"", status=200, content_type="application/octet-stream"):
    response = requests.Response()
    response.status_code, response._content, response._content_consumed = status, content, True
    response.headers["Content-Type"] = content_type
    return response


def _bunkernet(monkeypatch, **methods):
    module = SimpleNamespace(**methods)
    monkeypatch.setitem(sys.modules, "bunkernet", module)
    return module


@pytest.mark.parametrize("multisite", [False, True])
def test_bunkernet_data_publishes_changed_list_then_skips_fresh_cache(runtime, monkeypatch, multisite):
    job, run = runtime("bunkernet/jobs/bunkernet-data.py")
    assert job.cache_file("instance.id", b"fixture-id")[0]
    remote = Mock(return_value=(True, 200, {"result": "ok", "data": ["203.0.113.7", "2001:db8::1"]}))
    _bunkernet(monkeypatch, data=remote)
    env = {"MULTISITE": "yes", "SERVER_NAME": "off.example app.example", "off.example_USE_BUNKERNET": "no"} if multisite else {}
    _, status = run(env=env)
    assert status == 1  # Changed security data asks the scheduler to reload.
    _assert_file(job, "ip.list", b"203.0.113.7\n2001:db8::1")
    _, status = run(env=env)
    assert status == 0
    assert remote.call_count == 1


@pytest.mark.parametrize(
    "reply,expected",
    [
        ((False, None, "offline"), 2),
        ((True, 429, "rate limited"), 0),
        ((True, 403, "banned"), 0),
        ((True, 200, []), 2),
        ((True, 200, {"result": "ko", "data": "rejected"}), 2),
        ((True, 200, {"result": "ok"}), 2),
    ],
)
def test_bunkernet_data_failure_retains_last_good_file_and_row(runtime, monkeypatch, reply, expected):
    job, run = runtime("bunkernet/jobs/bunkernet-data.py")
    assert job.cache_file("instance.id", b"fixture-id")[0]
    assert job.cache_file("ip.list", b"203.0.113.9")[0]
    with session(job.db) as s:
        s.query(Jobs_cache).filter_by(job_name=job.job_name, file_name="ip.list").update({"last_update": FIXED_DT})
    _bunkernet(monkeypatch, data=Mock(return_value=reply))
    _, status = run()
    assert status == expected
    _assert_file(job, "ip.list", b"203.0.113.9")


def test_bunkernet_unchanged_download_does_not_request_reload(runtime, monkeypatch):
    job, run = runtime("bunkernet/jobs/bunkernet-data.py")
    assert job.cache_file("instance.id", b"fixture-id")[0]
    assert job.cache_file("ip.list", b"203.0.113.9")[0]
    with session(job.db) as s:
        s.query(Jobs_cache).filter_by(job_name=job.job_name, file_name="ip.list").update({"last_update": FIXED_DT})
    _bunkernet(monkeypatch, data=Mock(return_value=(True, 200, {"result": "ok", "data": ["203.0.113.9"]})))
    assert run()[1] == 0
    _assert_file(job, "ip.list", b"203.0.113.9")


@pytest.mark.parametrize("script", ["bunkernet-data.py", "bunkernet-send.py"])
@pytest.mark.parametrize("env,expected", [({"USE_BUNKERNET": "no"}, 0), ({}, 2)])
def test_unregistered_or_disabled_bunkernet_never_contacts_remote(runtime, monkeypatch, script, env, expected):
    job, run = runtime(f"bunkernet/jobs/{script}")
    remote = Mock(side_effect=AssertionError("unregistered instance must not send"))
    _bunkernet(monkeypatch, data=remote, send_reports=remote)
    assert run(env=env)[1] == expected
    remote.assert_not_called()
    with session(job.db) as s:
        assert s.query(Jobs_cache).count() == 0


def _reports(count):
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [{"date": (origin + timedelta(seconds=i)).isoformat(), "ip": "203.0.113.1", "url": f"/{i}"} for i in range(count)]


def _send_runtime(runtime, monkeypatch, count, *, age=0, reply=(True, 200, {"result": "ok", "data": None}), queued=None):
    job, run = runtime("bunkernet/jobs/bunkernet-send.py")
    assert job.cache_file("instance.id", b"fixture-id")[0]
    created = (datetime.now().astimezone() - timedelta(hours=age)).isoformat()
    payload = json.dumps({"created": created, "reports": list(reversed(_reports(count)))}).encode()
    assert job.cache_file("reports.json", payload)[0]
    remote = Mock(return_value=reply)
    _bunkernet(monkeypatch, send_reports=remote)
    caller = SimpleNamespace(send_to_apis=Mock(return_value=(True, {"node": {"status": "success", "msg": queued or []}})))
    monkeypatch.setitem(sys.modules, "ApiCaller", SimpleNamespace(ApiCaller=lambda _: caller))
    return job, run, remote


@pytest.mark.parametrize("count,age,batches,left", [(205, 0, [100, 100], 5), (3, 25, [3], 0), (3, 0, [], 3)])
def test_bunkernet_batches_oldest_first_and_persists_only_unsent_reports(runtime, monkeypatch, count, age, batches, left):
    job, run, remote = _send_runtime(runtime, monkeypatch, count, age=age)
    assert run()[1] == 0
    assert [len(call.args[0]) for call in remote.call_args_list] == batches
    sent = [report["url"] for call in remote.call_args_list for report in call.args[0]]
    assert sent == [f"/{i}" for i in range(count - left)]
    if left:
        payload = (job.job_path / "reports.json").read_bytes()
        assert [report["url"] for report in json.loads(payload)["reports"]] == [f"/{i}" for i in range(count - left, count)]
        _assert_file(job, "reports.json", payload)
    else:
        assert not (job.job_path / "reports.json").exists()
        with session(job.db) as s:
            assert s.query(Jobs_cache).filter_by(job_name=job.job_name, file_name="reports.json").count() == 0


@pytest.mark.parametrize("reply", [(False, None, "offline"), (True, 429, "limited"), (True, 403, "banned")])
def test_bunkernet_send_outage_keeps_newest_bounded_backlog(runtime, monkeypatch, reply):
    job, run, remote = _send_runtime(runtime, monkeypatch, 10005, reply=reply)
    assert run()[1] == 0
    assert remote.call_count == 1
    payload = (job.job_path / "reports.json").read_bytes()
    reports = json.loads(payload)["reports"]
    assert len(reports) == 10000
    assert (reports[0]["url"], reports[-1]["url"]) == ("/5", "/10004")
    _assert_file(job, "reports.json", payload)


def test_bunkernet_failed_backlog_cache_reports_scheduler_error(runtime, monkeypatch):
    job, run, _ = _send_runtime(runtime, monkeypatch, 3)
    before = _row(job, "reports.json")
    job.db.readonly = True
    status = run()[1]
    assert _row(job, "reports.json") == before
    assert status == 2


@pytest.mark.parametrize("http_status,expected", [(429, (True, 429, "rate limited")), (403, (True, 403, "forbidden"))])
def test_bunkernet_transport_exposes_throttle_without_parsing_body(monkeypatch, http_status, expected):
    module = _module(ROOT / "src/common/core/bunkernet/jobs/bunkernet.py")
    reply = _response(b"non-json", http_status)
    monkeypatch.setattr(module, "requests_request", Mock(return_value=reply))
    assert module.request("GET", "/db") == expected


@pytest.mark.parametrize("error", [requests.ReadTimeout(), ValueError("bad JSON"), AssertionError("missing fields")])
def test_bunkernet_transport_returns_error_instead_of_raising(monkeypatch, error):
    module = _module(ROOT / "src/common/core/bunkernet/jobs/bunkernet.py")
    monkeypatch.setattr(module, "requests_request", Mock(side_effect=error))
    ok, status, message = module.request("GET", "/db")
    assert ok is False and status is None
    assert "timed out" in message if isinstance(error, requests.ReadTimeout) else "request failed" in message


def test_bunkernet_transport_authenticates_payload_and_wrappers(monkeypatch, tmp_path):
    module = _module(ROOT / "src/common/core/bunkernet/jobs/bunkernet.py")
    monkeypatch.setattr(module, "get_id", lambda: "fixture-id")
    monkeypatch.setattr(module, "get_version", lambda: "1.6.18")
    monkeypatch.setattr(module, "get_integration", lambda: "Docker")
    monkeypatch.setattr(module, "get_os_info", lambda: {"id": "unit"})
    remote = Mock(return_value=_response(b'{"result":"ok","data":[]}'))
    monkeypatch.setattr(module, "requests_request", remote)
    for method in (module.register, module.ping, module.data, lambda: module.send_reports([{"url": "/"}])):
        assert method() == (True, 200, {"result": "ok", "data": []})
    assert [call.args for call in remote.call_args_list] == [
        ("POST", "https://api.bunkerweb.io/register"),
        ("GET", "https://api.bunkerweb.io/ping"),
        ("GET", "https://api.bunkerweb.io/db"),
        ("POST", "https://api.bunkerweb.io/report"),
    ]
    assert remote.call_args.kwargs == {
        "json": {"integration": "Docker", "version": "1.6.18", "os": {"id": "unit"}, "id": "fixture-id", "reports": [{"url": "/"}]},
        "headers": {"User-Agent": "BunkerWeb/1.6.18"},
        "timeout": 5,
    }


@pytest.fixture
def pem_pair():
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "app.example")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=10))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM), key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def test_custom_certificate_publishes_valid_pair_and_unchanged_pair_skips_reload(runtime, pem_pair):
    job, run = runtime("customcert/jobs/custom-cert.py")
    cert, key = pem_pair
    env = {"USE_CUSTOM_SSL": "yes", "CUSTOM_SSL_CERT_DATA": cert.decode(), "CUSTOM_SSL_KEY_DATA": key.decode()}
    assert run(env=env)[1] == 1
    _assert_file(job, "cert.pem", cert, "app.example")
    _assert_file(job, "key.pem", key, "app.example")
    assert run(env=env)[1] == 0


def test_invalid_custom_certificate_keeps_previously_served_pair(runtime, pem_pair):
    job, run = runtime("customcert/jobs/custom-cert.py")
    cert, key = pem_pair
    assert job.cache_file("cert.pem", cert, service_id="app.example")[0]
    assert job.cache_file("key.pem", key, service_id="app.example")[0]
    assert run(env={"USE_CUSTOM_SSL": "yes", "CUSTOM_SSL_CERT_DATA": "corrupt", "CUSTOM_SSL_KEY_DATA": key.decode()})[1] == 2
    _assert_file(job, "cert.pem", cert, "app.example")
    _assert_file(job, "key.pem", key, "app.example")


@pytest.mark.parametrize("key_source", ["valid", "bad", "missing"])
def test_custom_certificate_file_priority_validates_both_inputs(runtime, tmp_path, pem_pair, key_source):
    job, run = runtime("customcert/jobs/custom-cert.py")
    cert, key = pem_pair
    cert_path, key_path = tmp_path / "input.pem", tmp_path / "input.key"
    cert_path.write_bytes(cert)
    if key_source != "missing":
        key_path.write_bytes(key if key_source == "valid" else b"corrupt key")
    _, status = run(env={"USE_CUSTOM_SSL": "yes", "CUSTOM_SSL_CERT": str(cert_path), "CUSTOM_SSL_KEY": str(key_path)})
    assert status == (1 if key_source == "valid" else 2)
    assert cert_path.read_bytes() == cert
    if key_source == "valid":
        assert key_path.read_bytes() == key
        _assert_file(job, "cert.pem", cert, "app.example")
        _assert_file(job, "key.pem", key, "app.example")
    else:
        with session(job.db) as s:
            assert s.query(Jobs_cache).count() == 0


@pytest.mark.parametrize("kind", ["country", "asn"])
@pytest.mark.parametrize("fault", ["valid", "checksum", "archive", "structure", "empty", "offline"])
def test_mmdb_scripts_verify_download_before_publishing(runtime, monkeypatch, tmp_path, kind, fault):
    job, run = runtime(f"jobs/jobs/mmdb-{kind}.py")
    content = b"previous MMDB fixture"
    assert job.cache_file(f"{kind}.mmdb", content)[0]
    previous = _row(job, f"{kind}.mmdb")
    candidate = content + b"candidate generation" if fault != "structure" else b"not an MMDB"

    # The optional maxminddb reader is the format boundary; download, gzip, integrity and cache I/O stay real.
    def open_database(path):
        if Path(path).read_bytes() not in (content, content + b"candidate generation"):
            raise ValueError("invalid MMDB structure")
        return nullcontext()

    monkeypatch.setattr(mmdb, "open_database", open_database)
    digest = hashlib.sha1(candidate).hexdigest() if fault != "checksum" else "0" * 40
    descriptor = mmdb.COUNTRY if kind == "country" else mmdb.ASN
    metadata = (f'Format: MMDB SHA1sum: {digest}<a href="https://download.db-ip.com/free/{descriptor.download_prefix}2026-10.mmdb.gz">Download</a>').encode()
    body = b"invalid gzip" if fault == "archive" else gzip.compress(candidate)
    if fault == "empty":
        body = b""

    def response(request, host):
        url = request.full_url if hasattr(request, "full_url") else request
        if fault == "offline" and url == descriptor.metadata_url:
            raise mmdb.URLError("offline")
        stream = BytesIO(metadata if url == descriptor.metadata_url else body)
        setattr(stream, "status", 200)
        setattr(stream, "headers", {})
        return stream

    monkeypatch.setattr(mmdb, "_open_response", response)
    original = mmdb.update_runtime_mmdb
    monkeypatch.setattr(mmdb, "update_runtime_mmdb", lambda desc, cache, fallback, **kw: original(desc, cache, fallback, temp_root=tmp_path / "work", **kw))
    _, status = run()
    assert status == (1 if fault == "valid" else 0 if fault == "offline" else 2)
    if fault == "valid":
        _assert_file(job, f"{kind}.mmdb", candidate)
        assert run()[1] == 0
    else:
        _assert_file(job, f"{kind}.mmdb", content)
        assert _row(job, f"{kind}.mmdb") == previous
    assert list((tmp_path / "work").iterdir()) == []


@pytest.mark.parametrize("enabled", [False, True])
def test_api_certificate_generated_with_restricted_key_and_cached_pair(runtime, monkeypatch, enabled):
    job, run = runtime("jobs/jobs/api-server-cert.py")
    monkeypatch.setenv("API_LISTEN_HTTPS", "yes" if enabled else "no")
    _, status = run()
    assert status == (1 if enabled else 0)
    directory = job.job_path
    if enabled:
        cert, key = directory / "api-server-cert.pem", directory / "api-server-cert.key"
        assert key.stat().st_mode & 0o777 == 0o600
        assert (
            x509.load_pem_x509_certificate(cert.read_bytes()).public_key().public_numbers()
            == serialization.load_pem_private_key(key.read_bytes(), password=None).public_key().public_numbers()
        )
        for path in (cert, key):
            assert _row(job, path.name)[0] == path.read_bytes()
        assert run()[1] == 0
    else:
        assert list(directory.iterdir()) == []


def test_api_certificate_openssl_failure_retains_previous_pair(runtime, monkeypatch):
    job, run = runtime("jobs/jobs/api-server-cert.py")
    directory = job.job_path.parent / "misc"
    directory.mkdir(parents=True)
    for name in ("api-server-cert.pem", "api-server-cert.key"):
        (directory / name).write_bytes(b"previous")
    monkeypatch.setattr(subprocess, "run", Mock(return_value=SimpleNamespace(returncode=1, stderr="openssl failed")))
    _, status = run(env={"API_LISTEN_HTTPS": "yes"})
    assert status == 2
    assert [p.read_bytes() for p in sorted(directory.iterdir())] == [b"previous", b"previous"]
    with session(job.db) as s:
        assert s.query(Jobs_cache).count() == 0


@pytest.mark.parametrize("multisite,nightly", [(False, False), (False, True), (True, True), (True, False)])
def test_nightly_crs_deprecation_warns_only_when_selected(runtime, caplog, multisite, nightly):
    _, run = runtime("modsecurity/jobs/coreruleset-nightly.py")
    version = "nightly" if nightly else "4"
    env = {"MULTISITE": "yes", "app.example_MODSECURITY_CRS_VERSION": version} if multisite else {"MODSECURITY_CRS_VERSION": version}
    with caplog.at_level(logging.WARNING):
        assert run(env=env)[1] == 0
    assert ("CRS v4 will be used instead" in caplog.text) is nightly


@pytest.mark.parametrize("limit", [0, 2, 10])
def test_cleanup_job_removes_only_oldest_excess_run_rows(runtime, limit):
    job, run = runtime("db/jobs/cleanup-excess-jobs-runs.py")
    with session(job.db) as s:
        for i in range(4):
            date = FIXED_DT + timedelta(seconds=i)
            s.add(Jobs_runs(job_name=job.job_name, start_date=date, end_date=date, success=True))
    assert run(env={"DATABASE_MAX_JOBS_RUNS": str(limit)})[1] == 0
    with session(job.db) as s:
        rows = s.query(Jobs_runs).order_by(Jobs_runs.start_date).all()
        assert [row.start_date.replace(tzinfo=None) for row in rows] == [
            (FIXED_DT + timedelta(seconds=i)).replace(tzinfo=None) for i in range(max(0, 4 - limit), 4)
        ]


@pytest.mark.parametrize(
    "value",
    ["invalid", "-1"],
)
def test_cleanup_job_rejects_invalid_limit_without_deleting_rows(runtime, value):
    job, run = runtime("db/jobs/cleanup-excess-jobs-runs.py")
    with session(job.db) as s:
        s.add(Jobs_runs(job_name=job.job_name, start_date=FIXED_DT, end_date=FIXED_DT, success=True))
    assert run(env={"DATABASE_MAX_JOBS_RUNS": value})[1] == 2
    with session(job.db) as s:
        assert s.query(Jobs_runs).count() == 1


LIST_PLUGINS = ("blacklist", "greylist", "whitelist")


def _feed_env(plugin, **extra):
    return {f"USE_{plugin.upper()}": "yes", "BLACKLIST_COMMUNITY_LISTS": "", **extra}


@pytest.mark.parametrize("plugin", LIST_PLUGINS)
@pytest.mark.parametrize(
    "kind,body,expected",
    [
        ("IP", b"203.0.113.8\ninvalid\n2001:db8::/32\nfe80::1%eth0\n203.0.113.8\n", b"2001:db8::/32\n203.0.113.8\n"),
        ("RDNS", b"Example.COM\n", b"example.com\n"),
        ("ASN", b"AS64512\nas64513\ninvalid\n", b"64512\n64513\n"),
        ("USER_AGENT", b"Bad Bot\n", b"(?:\\b)Bad Bot(?:\\b)\n"),
        ("URI", b"/admin\ninvalid\n", b"/admin\n"),
    ],
)
def test_feed_download_persists_validated_entries_and_fresh_cache_is_idempotent(runtime, plugin, kind, body, expected):
    job, run = runtime(f"{plugin}/jobs/{plugin}-download.py")
    url = "https://feeds.invalid/list"
    remote = Mock(return_value=_response(body))
    env = _feed_env(plugin, **{f"{plugin.upper()}_{kind}_URLS": url})
    assert run(env=env, get=remote)[1] == 1
    _assert_file(job, f"{kind}.list", expected, "app.example")
    url_file = hashlib.sha1(url.encode()).hexdigest() + ".list"
    raw = (job.job_path / url_file).read_bytes()
    assert raw.startswith(b"# Downloaded from https://feeds.invalid/list\n")
    _assert_file(job, url_file, raw)
    assert run(env=env, get=remote)[1] == 0
    _assert_file(job, f"{kind}.list", expected, "app.example")
    assert remote.call_count == 1


@pytest.mark.parametrize("plugin", LIST_PLUGINS)
@pytest.mark.parametrize("failure", ["http", "offline", "empty", "corrupt", "file-missing"])
def test_feed_failure_retains_previous_service_list(runtime, plugin, failure, tmp_path):
    job, run = runtime(f"{plugin}/jobs/{plugin}-download.py")
    assert job.cache_file("IP.list", b"203.0.113.9\n", service_id="app.example")[0]
    url = (tmp_path / "missing-feed").as_uri() if failure == "file-missing" else "https://feeds.invalid/list"
    remote = Mock(
        side_effect=requests.ConnectionError("offline") if failure == "offline" else None,
        return_value=_response(b"" if failure == "empty" else b"not-an-ip", 503 if failure == "http" else 200),
    )
    _, status = run(env=_feed_env(plugin, **{f"{plugin.upper()}_IP_URLS": url}), get=remote)
    assert status == (0 if failure in ("empty", "corrupt") else 2)
    _assert_file(job, "IP.list", b"203.0.113.9\n", "app.example")
    assert remote.call_count == (3 if failure == "offline" else 0 if failure == "file-missing" else 1)


@pytest.mark.parametrize("plugin", LIST_PLUGINS)
def test_multisite_feed_shared_url_downloaded_once_and_disabled_service_not_modified(runtime, plugin):
    job, run = runtime(f"{plugin}/jobs/{plugin}-download.py")
    assert job.cache_file("IP.list", b"old\n", service_id="off.example")[0]
    remote = Mock(return_value=_response(b"203.0.113.8\n"))
    prefix = plugin.upper()
    env = _feed_env(
        plugin,
        MULTISITE="yes",
        SERVER_NAME="app.example alias.example off.example",
        **{
            f"app.example_USE_{prefix}": "yes",
            f"alias.example_USE_{prefix}": "yes",
            f"off.example_USE_{prefix}": "no",
            f"app.example_{prefix}_IP_URLS": "https://feeds.invalid/shared",
            f"alias.example_{prefix}_IP_URLS": "https://feeds.invalid/shared",
            "app.example_BLACKLIST_COMMUNITY_LISTS": "",
            "alias.example_BLACKLIST_COMMUNITY_LISTS": "",
        },
    )
    assert run(env=env, get=remote)[1] == 1
    assert remote.call_count == 1
    for service in ("app.example", "alias.example"):
        _assert_file(job, "IP.list", b"203.0.113.8\n", service)
    _assert_file(job, "IP.list", b"old\n", "off.example")


@pytest.mark.parametrize("plugin", LIST_PLUGINS)
def test_feed_without_urls_removes_obsolete_cache_rows_and_files(runtime, plugin):
    job, run = runtime(f"{plugin}/jobs/{plugin}-download.py")
    assert job.cache_file("IP.list", b"203.0.113.9\n", service_id="app.example")[0]
    assert job.cache_file("obsolete.list", b"old\n")[0]
    assert run(env=_feed_env(plugin))[1] == 0
    assert not list(job.job_path.rglob("*.list"))
    with session(job.db) as s:
        assert s.query(Jobs_cache).count() == 0


@pytest.mark.parametrize("plugin", LIST_PLUGINS)
def test_feed_changed_url_removes_stale_url_cache_row_and_file(runtime, plugin):
    job, run = runtime(f"{plugin}/jobs/{plugin}-download.py")
    old_url, new_url = "https://feeds.invalid/old", "https://feeds.invalid/new"
    old_file = hashlib.sha1(old_url.encode()).hexdigest() + ".list"
    new_file = hashlib.sha1(new_url.encode()).hexdigest() + ".list"
    assert job.cache_file(old_file, b"203.0.113.9\n")[0]
    assert job.cache_file("IP.list", b"203.0.113.9\n", service_id="app.example")[0]
    assert run(env=_feed_env(plugin, **{f"{plugin.upper()}_IP_URLS": new_url}), get=Mock(return_value=_response(b"203.0.113.8\n")))[1] == 1
    assert not (job.job_path / old_file).exists()
    with session(job.db) as s:
        assert s.query(Jobs_cache).filter_by(job_name=job.job_name, file_name=old_file).count() == 0
    _assert_file(job, "IP.list", b"203.0.113.8\n", "app.example")
    _assert_file(job, new_file, b"# Downloaded from https://feeds.invalid/new\n203.0.113.8\n")


def _backup_module(monkeypatch, tmp_path):
    module = _module(ROOT / "src/common/core/backup/backup.py")
    monkeypatch.setattr(module, "DB_LOCK_FILE", tmp_path / "db.lock")
    monkeypatch.setitem(sys.modules, "backup", module)
    return module


@pytest.mark.parametrize("force", [False, True])
def test_backup_script_creates_private_archive_and_rotates_oldest(runtime, monkeypatch, tmp_path, force):
    job, run = runtime("backup/jobs/backup-data.py")
    module = _backup_module(monkeypatch, tmp_path)
    # Dump process is the engine boundary; real backup archive creation and metadata remain intact.
    dump = Mock(return_value=SimpleNamespace(returncode=0, stdout=b"-- SQL fixture\n", stderr=b""))
    monkeypatch.setattr(module, "run", dump)
    directory = tmp_path / "backups"
    directory.mkdir()
    for i in range(3):
        (directory / f"backup-2000-01-0{i}.zip").write_bytes(b"old")
    assert run(env={"BACKUP_DIRECTORY": str(directory), "BACKUP_ROTATION": "2", "FORCE_BACKUP": "yes" if force else "no"})[1] == 0
    files = sorted(directory.glob("backup-*.zip"))
    assert len(files) == (4 if force else 2)
    newest = files[-1]
    assert newest.stat().st_mode & 0o777 == 0o600
    with ZipFile(newest) as archive:
        assert archive.namelist() == [newest.with_suffix(".sql").name]
        assert archive.read(archive.namelist()[0]) == b"-- SQL fixture\n"
    if force:
        with session(job.db) as s:
            assert s.query(Jobs_cache).count() == 0
    else:
        cached = json.loads(_row(job, "backup.json")[0])
        assert cached["files"] == [file.name for file in files]
        assert datetime.fromisoformat(cached["date"]).tzinfo is not None
    assert dump.call_count == 1


@pytest.mark.parametrize("schedule", ["daily", "weekly", "monthly"])
def test_backup_fresh_cache_skips_dump_but_applies_rotation(runtime, monkeypatch, tmp_path, schedule):
    job, run = runtime("backup/jobs/backup-data.py")
    module = _backup_module(monkeypatch, tmp_path)
    monkeypatch.setattr(module, "run", Mock(side_effect=AssertionError("fresh backup must not dump")))
    directory = tmp_path / "backups"
    directory.mkdir()
    for i in range(4):
        (directory / f"backup-2000-01-0{i}.zip").write_bytes(b"old")
    assert job.cache_file("backup.json", json.dumps({"date": datetime.now().astimezone().isoformat()}).encode())[0]
    assert run(env={"BACKUP_DIRECTORY": str(directory), "BACKUP_ROTATION": "2", "BACKUP_SCHEDULE": schedule})[1] == 0
    assert [file.name for file in sorted(directory.iterdir())] == ["backup-2000-01-02.zip", "backup-2000-01-03.zip"]
    assert run(env={"BACKUP_DIRECTORY": str(directory), "BACKUP_ROTATION": "2", "BACKUP_SCHEDULE": schedule})[1] == 0


@pytest.mark.parametrize(
    "cause",
    [
        "disabled",
        "first-start",
        "busy",
        "dump",
        "cache-corrupt",
    ],
)
def test_backup_failure_or_skip_releases_lock_and_preserves_old_archive(runtime, monkeypatch, tmp_path, cause):
    job, run = runtime("backup/jobs/backup-data.py")
    module = _backup_module(monkeypatch, tmp_path)
    if cause == "first-start":
        assert job.db.set_metadata({"scheduler_first_start": True}) == ""
    elif cause == "cache-corrupt":
        assert job.cache_file("backup.json", b"not-json")[0]
    acquired, released = Mock(return_value=17), Mock()
    if cause == "busy":
        acquired.side_effect = module.DatabaseLockBusy("lock held")
    monkeypatch.setattr(module, "acquire_db_lock", acquired)
    monkeypatch.setattr(module, "release_db_lock", released)
    monkeypatch.setattr(module, "run", Mock(return_value=SimpleNamespace(returncode=1, stdout=b"", stderr=b"dump rejected")))
    directory = tmp_path / "backups"
    directory.mkdir()
    (directory / "backup-old.zip").write_bytes(b"last good archive")
    status = run(env={"BACKUP_DIRECTORY": str(directory), "USE_BACKUP": "no" if cause == "disabled" else "yes"})[1]
    assert (directory / "backup-old.zip").read_bytes() == b"last good archive"
    assert list(directory.iterdir()) == [directory / "backup-old.zip"]
    if cause == "busy":
        released.assert_not_called()
    else:
        released.assert_called_once_with(17)
    assert status == (0 if cause in ("disabled", "first-start") else 2)


def _plugin_archive(crs=False):
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        if crs:
            archive.writestr("demo/demo-config.conf", "# Plugin name: demo\n# Plugin version: 1.0\n")
            archive.writestr("demo/rules.conf", "setvar:'tx.inbound_anomaly_score_pl1=+%{tx.critical_anomaly_score}'\n")
        else:
            archive.writestr("demo/plugin.json", json.dumps({"id": "demo", "name": "Demo", "description": "Unit fixture", "version": "1.0", "stream": "no"}))
            archive.writestr("demo/jobs/run.py", "print('fixture')\n")
    return buffer.getvalue()


@pytest.mark.parametrize("plugin", ["misc", "pro"])
def test_plugin_download_stores_exact_archive_and_executable_mode(runtime, monkeypatch, tmp_path, plugin):
    _, run = runtime(f"{plugin}/jobs/download-{'pro-' if plugin == 'pro' else ''}plugins.py")
    module, status = run(
        get=Mock(return_value=_response(_plugin_archive(), content_type="application/zip")),
        env={"EXTERNAL_PLUGIN_URLS": "https://plugins.invalid/demo.zip"} if plugin == "misc" else {},
    )
    assert status == 1
    root = module.EXTERNAL_PLUGINS_DIR if plugin == "misc" else module.PRO_PLUGINS_DIR
    assert (root / "demo/jobs/run.py").read_bytes() == b"print('fixture')\n"
    assert (root / "demo/jobs/run.py").stat().st_mode & 0o777 == 0o750
    with session(module.db) as s:
        row = s.get(Plugins, "demo")
        assert (row.version, row.method, row.type) == ("1.0", "scheduler", "external" if plugin == "misc" else "pro")
        assert hashlib.sha256(row.data).hexdigest() == row.checksum
        with tar_open(fileobj=BytesIO(row.data), mode="r:gz") as archive:
            member = next(member for member in archive.getmembers() if member.name.endswith("jobs/run.py"))
            payload = archive.extractfile(member)
            assert payload is not None
            assert payload.read() == b"print('fixture')\n"
            assert member.mode == 0o750


@pytest.mark.parametrize("failure", ["http", "corrupt", "empty", "database"])
def test_crs_plugin_download_failure_preserves_manifest_archive_and_live_tree(runtime, monkeypatch, tmp_path, failure):
    job, run = runtime("modsecurity/jobs/download-crs-plugins.py")
    patch = tmp_path / "system/usr/share/bunkerweb/core/modsecurity/misc/patch.sh"
    patch.parent.mkdir(parents=True)
    patch.write_bytes((ROOT / "src/common/core/modsecurity/misc/patch.sh").read_bytes())
    patch.chmod(0o750)
    (tmp_path / "system/var/tmp/bunkerweb").mkdir(parents=True)
    env = {"MODSECURITY_CRS_PLUGINS": "https://plugins.invalid/demo.zip"}
    module, status = run(get=Mock(return_value=_response(_plugin_archive(crs=True))), env=env)
    assert status == 1
    manifest = (job.job_path / "crs-plugins.json").read_bytes()
    assert json.loads(manifest) == {"app.example": ["demo-1.0"], "alias.example": []}
    _assert_file(job, "crs-plugins.json", manifest)
    rows = job.db.get_jobs_cache_files(plugin_id="modsecurity")
    original = {row["file_name"]: row["data"] for row in rows}
    archive_name = f"folder:{module.CRS_PLUGINS_DIR}.tgz"
    assert set(original) == {"crs-plugins.json", archive_name}
    assert _row(job, archive_name)[1] == hashlib.sha512(original[archive_name]).hexdigest()
    with tar_open(fileobj=BytesIO(original[archive_name]), mode="r:gz") as archive:
        rules = archive.extractfile("./demo-1.0/rules.conf")
        assert rules is not None
        assert "tx.bunkerweb_anomaly_score" in rules.read().decode()
    live = module.CRS_PLUGINS_DIR / "demo-1.0"
    assert "tx.bunkerweb_anomaly_score" in (live / "rules.conf").read_text()
    if failure == "database":
        monkeypatch.setattr(job.db, "upsert_job_caches", Mock(return_value="database refused publication"))
    payload = b"" if failure == "empty" else b"corrupt" if failure == "corrupt" else _plugin_archive(crs=True)
    assert run(get=Mock(return_value=_response(payload, 503 if failure == "http" else 200)), env=env)[1] == 2
    assert (job.job_path / "crs-plugins.json").read_bytes() == manifest
    assert "tx.bunkerweb_anomaly_score" in (live / "rules.conf").read_text()
    assert {row["file_name"]: row["data"] for row in job.db.get_jobs_cache_files(plugin_id="modsecurity")} == original


@pytest.mark.parametrize("kind", ["country", "asn"])
def test_mmdb_wrapper_reports_unexpected_updater_failure_to_scheduler(runtime, monkeypatch, caplog, kind):
    job, run = runtime(f"jobs/jobs/mmdb-{kind}.py")
    assert job.cache_file(f"{kind}.mmdb", b"previous")[0]
    monkeypatch.setattr(mmdb, "update_runtime_mmdb", Mock(side_effect=OSError("read-only cache")))
    assert run()[1] == 2
    assert "read-only cache" in caplog.text
    _assert_file(job, f"{kind}.mmdb", b"previous")


@pytest.mark.parametrize("multisite", [False, True])
def test_blacklist_community_feeds_merge_with_explicit_urls_and_skip_unknown_id(runtime, multisite, caplog):
    job, run = runtime("blacklist/jobs/blacklist-download.py")
    prefix = "app.example_" if multisite else ""
    env = {
        "MULTISITE": "yes" if multisite else "no",
        "SERVER_NAME": "app.example",
        f"{prefix}BLACKLIST_COMMUNITY_LISTS": "ip:danmeuk-tor-exit ua:mitchellkrogza-bad-user-agents unknown",
        f"{prefix}BLACKLIST_IP_URLS": "https://feeds.invalid/extra",
    }

    def get(url, **kwargs):
        return _response(b"Bad Bot\n" if "bad-user-agents" in url else b"203.0.113.8\n")

    assert run(env=env, get=get)[1] == 1
    _assert_file(job, "IP.list", b"203.0.113.8\n", "app.example")
    _assert_file(job, "USER_AGENT.list", b"(?:\\b)Bad Bot(?:\\b)\n", "app.example")
    assert "Community blacklist unknown not found" in caplog.text


def test_custom_certificate_multisite_data_priority_and_disabled_service_cleanup(runtime, pem_pair):
    job, run = runtime("customcert/jobs/custom-cert.py")
    cert, key = pem_pair
    for name in ("cert.pem", "key.pem"):
        assert job.cache_file(name, b"obsolete", service_id="off.example")[0]
    env = {
        "MULTISITE": "yes",
        "SERVER_NAME": "off.example app.example",
        "app.example_USE_CUSTOM_SSL": "yes",
        "app.example_CUSTOM_SSL_CERT_PRIORITY": "data",
        "app.example_CUSTOM_SSL_CERT": "/missing/ignored.pem",
        "app.example_CUSTOM_SSL_KEY": "/missing/ignored.key",
        "app.example_CUSTOM_SSL_CERT_DATA": cert.decode(),
        "app.example_CUSTOM_SSL_KEY_DATA": key.decode(),
    }
    assert run(env=env)[1] == 1
    _assert_file(job, "cert.pem", cert, "app.example")
    _assert_file(job, "key.pem", key, "app.example")
    assert not (job.job_path / "off.example").exists()
    with session(job.db) as s:
        assert s.query(Jobs_cache).filter_by(service_id="off.example").count() == 0


@pytest.mark.parametrize("body", [b"not-json", b"{}", b'{"result":"ok"}', b"null"])
def test_bunkernet_transport_rejects_malformed_api_body(monkeypatch, body):
    module = _module(ROOT / "src/common/core/bunkernet/jobs/bunkernet.py")
    monkeypatch.setattr(module, "requests_request", Mock(return_value=_response(body)))
    ok, status, message = module.request("GET", "/db")
    assert ok is False and status is None
    assert message.startswith("request failed:")


def test_bunkernet_id_reader_strips_file_whitespace(monkeypatch, tmp_path):
    module = _module(ROOT / "src/common/core/bunkernet/jobs/bunkernet.py")
    id_file = tmp_path / "instance.id"
    id_file.write_text("  fixture-id\n")
    monkeypatch.setattr(module, "Path", lambda *_: id_file)
    assert module.get_id() == "fixture-id"


@pytest.mark.parametrize("script", ["bunkernet-data.py", "bunkernet-send.py"])
def test_multisite_disabled_bunkernet_never_creates_cache(runtime, monkeypatch, script):
    job, run = runtime(f"bunkernet/jobs/{script}")
    remote = Mock(side_effect=AssertionError("disabled service must not contact remote"))
    _bunkernet(monkeypatch, data=remote, send_reports=remote)
    assert run(env={"MULTISITE": "yes", "SERVER_NAME": "off.example", "off.example_USE_BUNKERNET": "no"})[1] == 0
    remote.assert_not_called()
    assert list(job.job_path.iterdir()) == []


def test_bunkernet_send_first_start_preserves_queue_without_sending(runtime, monkeypatch):
    job, run, remote = _send_runtime(runtime, monkeypatch, 3)
    original = (job.job_path / "reports.json").read_bytes()
    assert job.db.set_metadata({"scheduler_first_start": True}) == ""
    assert run()[1] == 0
    remote.assert_not_called()
    _assert_file(job, "reports.json", original)


def test_bunkernet_send_corrupt_cached_json_reports_error_and_preserves_bytes(runtime, monkeypatch):
    job, run, remote = _send_runtime(runtime, monkeypatch, 3)
    assert job.cache_file("reports.json", b"not-json")[0]
    assert run()[1] == 2
    remote.assert_not_called()
    _assert_file(job, "reports.json", b"not-json")


@pytest.mark.parametrize("plugin", ["misc", "pro"])
@pytest.mark.parametrize("failure", ["http", "empty", "corrupt"])
def test_plugin_download_failure_keeps_previous_plugin_files_and_db_archive(runtime, plugin, failure):
    job, run = runtime(f"{plugin}/jobs/download-{'pro-' if plugin == 'pro' else ''}plugins.py")
    env = {"EXTERNAL_PLUGIN_URLS": "https://plugins.invalid/demo.zip"} if plugin == "misc" else {}
    module, status = run(env=env, get=Mock(return_value=_response(_plugin_archive(), content_type="application/zip")))
    assert status == 1
    root = module.EXTERNAL_PLUGINS_DIR if plugin == "misc" else module.PRO_PLUGINS_DIR
    with session(job.db) as s:
        installed = s.get(Plugins, "demo")
        before = installed.data, installed.checksum
    assert job.db.set_metadata({"last_pro_check": None}) == ""
    body = b"corrupt" if failure == "corrupt" else b""
    _, status = run(env=env, get=Mock(return_value=_response(body, 503 if failure == "http" else 200, "application/zip")))
    assert status == (0 if plugin == "misc" else 2)
    assert (root / "demo/jobs/run.py").read_bytes() == b"print('fixture')\n"
    with session(job.db) as s:
        installed = s.get(Plugins, "demo")
        assert (installed.data, installed.checksum) == before


def test_api_certificate_expired_cache_renews_same_pair_in_files_and_db(runtime):
    job, run = runtime("jobs/jobs/api-server-cert.py")
    assert run(env={"API_LISTEN_HTTPS": "yes"})[1] == 1
    old = _row(job, "api-server-cert.pem")[0]
    with session(job.db) as s:
        s.query(Jobs_cache).filter_by(job_name=job.job_name).update({"last_update": FIXED_DT})
    assert run(env={"API_LISTEN_HTTPS": "yes"})[1] == 1
    new = _row(job, "api-server-cert.pem")[0]
    assert new != old
    _assert_file(job, "api-server-cert.pem", new)
    _assert_file(job, "api-server-cert.key", _row(job, "api-server-cert.key")[0])


@pytest.mark.parametrize("statuses,expected", [([200], "main"), ([404, 200], "master"), ([404, 404], None)])
def test_crs_named_plugin_without_release_resolves_available_default_branch(runtime, monkeypatch, statuses, expected):
    _, run = runtime("modsecurity/jobs/download-crs-plugins.py")
    module, status = run(env={"USE_MODSECURITY_CRS_PLUGINS": "no"})
    assert status == 2  # Missing installed patch prevents script execution; resolver is independent.
    monkeypatch.setattr(module, "get", Mock(return_value=_response(b"[]")))
    head = Mock(side_effect=[_response(status=code) for code in statuses])
    monkeypatch.setattr(module, "head", head)
    assert module.get_download_url("https://github.com/unit/demo") == (
        (True, f"https://github.com/unit/demo/archive/refs/heads/{expected}.zip") if expected else (False, "No branches found")
    )
    assert [call.args[0] for call in head.call_args_list] == [
        f"https://github.com/unit/demo/archive/refs/heads/{name}.zip" for name in ("main", "master")[: len(statuses)]
    ]


def test_crs_release_lookup_error_is_actionable(runtime, monkeypatch):
    _, run = runtime("modsecurity/jobs/download-crs-plugins.py")
    module, _ = run()
    monkeypatch.setattr(module, "get", Mock(return_value=_response(b"service unavailable", 404)))
    with pytest.raises(RuntimeError, match="Failed to deduce the download URL"):
        module.get_download_url("https://github.com/unit/demo")


def test_api_certificate_missing_openssl_reports_error_without_writing_cache(runtime, monkeypatch, caplog):
    job, run = runtime("jobs/jobs/api-server-cert.py")
    monkeypatch.setattr(subprocess, "run", Mock(side_effect=FileNotFoundError("openssl unavailable")))
    assert run(env={"API_LISTEN_HTTPS": "yes"})[1] == 2
    assert "openssl unavailable" in caplog.text
    with session(job.db) as s:
        assert s.query(Jobs_cache).count() == 0
    assert not list(job.job_path.iterdir())


@pytest.mark.parametrize("cached_registry", [b"not-json", b"[]"])
def test_crs_corrupt_registry_and_failed_refresh_keep_previous_cache(runtime, tmp_path, caplog, cached_registry):
    job, run = runtime("modsecurity/jobs/download-crs-plugins.py")
    patch = tmp_path / "system/usr/share/bunkerweb/core/modsecurity/misc/patch.sh"
    patch.parent.mkdir(parents=True)
    patch.write_bytes((ROOT / "src/common/core/modsecurity/misc/patch.sh").read_bytes())
    patch.chmod(0o750)
    (tmp_path / "system/var/tmp/bunkerweb").mkdir(parents=True)
    assert job.cache_file("plugin_registry.json", cached_registry)[0]
    remote = Mock(return_value=_response(b"unavailable", 503))
    assert run(get=remote, env={"MODSECURITY_CRS_PLUGINS": "demo"})[1] == 2
    _assert_file(job, "plugin_registry.json", cached_registry)
    assert "503" in caplog.text
    assert not (job.job_path / "crs-plugins.json").exists()


@pytest.mark.parametrize("plugin", LIST_PLUGINS)
def test_disabled_feed_preserves_current_list_without_download(runtime, plugin):
    job, run = runtime(f"{plugin}/jobs/{plugin}-download.py")
    assert job.cache_file("IP.list", b"203.0.113.9\n", service_id="app.example")[0]
    remote = Mock(side_effect=AssertionError("disabled feed must not download"))
    assert run(env=_feed_env(plugin, **{f"USE_{plugin.upper()}": "no"}), get=remote)[1] == 0
    _assert_file(job, "IP.list", b"203.0.113.9\n", "app.example")
    remote.assert_not_called()


def test_cleanup_database_refusal_is_logged_and_keeps_history(runtime, monkeypatch, caplog):
    job, run = runtime("db/jobs/cleanup-excess-jobs-runs.py")
    with session(job.db) as s:
        s.add(Jobs_runs(job_name=job.job_name, start_date=FIXED_DT, end_date=FIXED_DT, success=True))
    monkeypatch.setattr(job.db, "cleanup_jobs_runs_excess", Mock(return_value="database unavailable"))
    status = run()[1]
    assert "database unavailable" in caplog.text
    with session(job.db) as s:
        assert s.query(Jobs_runs).count() == 1
    assert status == 2


@pytest.mark.parametrize("plugin", LIST_PLUGINS)
@pytest.mark.xfail(strict=True, reason="Empty successful feed overwrites the last-good URL cache with a comment-only file")
def test_empty_feed_retains_previous_url_cache_and_service_list(runtime, plugin):
    job, run = runtime(f"{plugin}/jobs/{plugin}-download.py")
    url = "https://feeds.invalid/list"
    filename = hashlib.sha1(url.encode()).hexdigest() + ".list"
    previous = b"# Downloaded from https://feeds.invalid/list\n203.0.113.9\n"
    assert job.cache_file(filename, previous)[0]
    assert job.cache_file("IP.list", b"203.0.113.9\n", service_id="app.example")[0]
    with session(job.db) as s:
        s.query(Jobs_cache).filter_by(job_name=job.job_name, file_name=filename).update({"last_update": FIXED_DT})
    run(env=_feed_env(plugin, **{f"{plugin.upper()}_IP_URLS": url}), get=Mock(return_value=_response(b"")))
    _assert_file(job, "IP.list", b"203.0.113.9\n", "app.example")
    _assert_file(job, filename, previous)
