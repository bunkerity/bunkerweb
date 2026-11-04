"""Bounded DB-IP downloads and verification without opening a network socket."""

import gzip
import hashlib
import io
from contextlib import nullcontext
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

import mmdb


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(mmdb, "_open_response", Mock(side_effect=AssertionError("unexpected network request")))
    monkeypatch.setattr(mmdb, "sleep", lambda _: None)


def page(descriptor=mmdb.ASN, sha1="a" * 40):
    return f'<div>Format: MMDB</div> SHA1sum: {sha1}<a href="https://download.db-ip.com/free/{descriptor.download_prefix}2026-10.mmdb.gz">Download</a>'


def response(body=b"data", status=200, headers=None):
    stream = io.BytesIO(body)
    stream.status = status
    stream.headers = headers or {}
    return stream


@pytest.mark.parametrize("descriptor", mmdb.DESCRIPTORS)
def test_metadata_selects_matching_artifact_and_normalizes_sha1(descriptor):
    metadata = mmdb.parse_metadata(page(descriptor, "AB" * 20), descriptor)
    assert metadata.expected_sha1 == "ab" * 20
    assert metadata.download_url == f"https://download.db-ip.com/free/{descriptor.download_prefix}2026-10.mmdb.gz"


@pytest.mark.parametrize(
    "html,match",
    [
        ("no artifact", "found 0"),
        (page() + page(), "found 2"),
        (page().replace("Format: MMDB", "Format: CSV"), "format"),
        (page().replace("a" * 40, "not-a-checksum"), "SHA-1"),
        (page().replace("SHA1sum:", "SHA1sum: " + "b" * 40), "SHA-1"),
        (page().replace("/free/", "/private/"), "download path"),
        (page().replace("download.db-ip.com", "attacker.invalid"), "endpoint"),
    ],
)
def test_ambiguous_or_untrusted_metadata_is_rejected(html, match):
    with pytest.raises(mmdb.MetadataError, match=match):
        mmdb.parse_metadata(html, mmdb.ASN)


@pytest.mark.parametrize(
    "url",
    [
        "http://download.db-ip.com/free/file",
        "https://download.db-ip.com:443/free/file",
        "https://user:password@download.db-ip.com/free/file",
        "https://download.db-ip.com/free/file?q=1",
        "https://download.db-ip.com/free/file#fragment",
        "https://download.db-ip.com.evil.invalid/file",
        "https://[invalid/file",
    ],
)
def test_endpoint_rejects_credentials_ports_and_origin_changes(url):
    with pytest.raises(mmdb.DownloadError):
        mmdb._validate_endpoint(url, mmdb.DOWNLOAD_HOST)


@pytest.mark.parametrize("length,error", [("bad", mmdb.DownloadError), ("-1", mmdb.DownloadError), ("9", mmdb.SizeLimitError)])
def test_declared_size_rejected_before_consumer(monkeypatch, length, error):
    reply = response(headers={"Content-Length": length})
    monkeypatch.setattr(mmdb, "_open_response", lambda *_: reply)
    consumer = Mock()
    with pytest.raises(error):
        mmdb._request_stream("url", "host", 8, consumer, mmdb.LOGGER)
    consumer.assert_not_called()
    assert reply.closed


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transient_http_status_retries_and_closes_every_response(monkeypatch, status):
    replies = [response(status=status), response(b"done", headers={"Content-Length": "4"})]
    opener = Mock(side_effect=replies)
    monkeypatch.setattr(mmdb, "_open_response", opener)
    assert mmdb._request_stream("url", "host", 8, lambda r, n: mmdb._read_response(r, n, 8), mmdb.LOGGER) == b"done"
    assert opener.call_count == 2
    assert all(reply.closed for reply in replies)


@pytest.mark.parametrize("error", [URLError("offline"), HTTPError("url", 503, "unavailable", {}, None)])
def test_retry_budget_reports_failure(monkeypatch, error):
    opener = Mock(side_effect=error)
    monkeypatch.setattr(mmdb, "_open_response", opener)
    with pytest.raises(mmdb.DownloadError, match="after 3 attempts"):
        mmdb._request_stream("url", "host", 8, Mock(), mmdb.LOGGER)
    assert opener.call_count == 3


@pytest.mark.parametrize("raised", [False, True])
def test_permanent_http_failure_does_not_retry(monkeypatch, raised):
    opener = Mock(side_effect=HTTPError("url", 404, "missing", {}, None)) if raised else Mock(return_value=response(status=404))
    monkeypatch.setattr(mmdb, "_open_response", opener)
    with pytest.raises(mmdb.DownloadError, match="HTTP 404"):
        mmdb._request_stream("url", "host", 8, Mock(), mmdb.LOGGER)
    assert opener.call_count == 1


@pytest.mark.parametrize("file_output", [False, True])
@pytest.mark.parametrize("body,length,maximum,match", [(b"", None, 8, "empty"), (b"abc", 4, 8, "truncated"), (b"12345", None, 4, "exceeds")])
def test_response_actual_size_is_checked(tmp_path, file_output, body, length, maximum, match):
    with pytest.raises(mmdb.DownloadError, match=match):
        if file_output:
            mmdb._copy_response(response(body), length, tmp_path / "output", maximum)
        else:
            mmdb._read_response(response(body), length, maximum)


def test_failed_download_removes_partial_file(tmp_path, monkeypatch):
    target = tmp_path / "sub" / "download.gz"
    monkeypatch.setattr(mmdb, "_open_response", lambda *_: response(b"partial", headers={"Content-Length": "99"}))
    with pytest.raises(mmdb.DownloadError, match="truncated"):
        mmdb.download_to_file("url", target)
    assert not target.exists()


@pytest.mark.parametrize("payload,error", [(b"not gzip", mmdb.DecompressionError), (gzip.compress(b"12345"), mmdb.SizeLimitError)])
def test_bad_archive_removes_partial_output(tmp_path, payload, error):
    archive = tmp_path / "source.gz"
    archive.write_bytes(payload)
    target = tmp_path / "db.mmdb"
    with pytest.raises(error):
        mmdb.decompress_to_file(archive, target, max_size=4)
    assert not target.exists()


@pytest.mark.parametrize("valid_hash", [False, True])
def test_candidate_verified_before_publication(tmp_path, monkeypatch, valid_hash):
    content = b"tiny mmdb fixture"
    digest = hashlib.sha1(content).hexdigest()
    metadata = mmdb.DBIPMetadata(digest if valid_hash else "0" * 40, "https://download.db-ip.com/free/dbip-asn-lite-2026-10.mmdb.gz")
    monkeypatch.setattr(mmdb, "_open_response", lambda *_: response(gzip.compress(content)))
    reader = Mock(return_value=nullcontext())
    monkeypatch.setattr(mmdb, "open_database", reader)
    if valid_hash:
        candidate = mmdb.download_verified_candidate(mmdb.ASN, metadata, tmp_path)
        assert candidate.path.read_bytes() == content
        assert candidate.sha1 == digest
        assert candidate.checksum == hashlib.sha512(content).hexdigest()
        reader.assert_called_once_with(candidate.path.as_posix())
    else:
        with pytest.raises(mmdb.IntegrityError) as raised:
            mmdb.download_verified_candidate(mmdb.ASN, metadata, tmp_path)
        assert raised.value.actual == digest
        assert not (tmp_path / "asn.mmdb").exists()
        reader.assert_not_called()
    assert not (tmp_path / "asn.mmdb.gz").exists()


@pytest.mark.parametrize("reader", [None, Mock(side_effect=ValueError("invalid MMDB"))])
def test_mmdb_reader_failure_is_wrapped(tmp_path, monkeypatch, reader):
    monkeypatch.setattr(mmdb, "open_database", reader)
    with pytest.raises(mmdb.MMDBValidationError):
        mmdb.validate_mmdb(tmp_path / "invalid.mmdb")


@pytest.mark.parametrize("body", [page().encode(), b"\xff"])
def test_fetch_metadata_decodes_utf8(monkeypatch, body):
    monkeypatch.setattr(mmdb, "_open_response", lambda *_: response(body))
    if body == b"\xff":
        with pytest.raises(mmdb.MetadataError, match="not UTF-8"):
            mmdb.fetch_metadata(mmdb.ASN)
    else:
        assert mmdb.fetch_metadata(mmdb.ASN).expected_sha1 == "a" * 40


def test_fetch_metadata_wraps_download_errors(monkeypatch):
    monkeypatch.setattr(mmdb, "_open_response", Mock(side_effect=mmdb.DownloadError("offline")))
    with pytest.raises(mmdb.MetadataError, match="offline"):
        mmdb.fetch_metadata(mmdb.ASN)
