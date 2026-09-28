#!/usr/bin/env python3

import logging
import os
import re
import ssl
import zlib
from dataclasses import dataclass
from gzip import GzipFile
from html.parser import HTMLParser
from hmac import compare_digest
from http.client import IncompleteRead
from pathlib import Path
from shutil import copy2
from socket import timeout as SocketTimeout
from stat import S_IMODE
from tempfile import TemporaryDirectory, mkstemp
from time import sleep
from typing import Callable, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from cache_restore import write_atomic
from common_utils import file_hash

try:
    from maxminddb import open_database
except ImportError:  # pragma: no cover - the scheduler dependency is installed in production.
    open_database = None


LOGGER = logging.getLogger("BUNKERWEB.MMDB")

# Bounds protect the scheduler and updater from unexpectedly large network input.
MAX_COMPRESSED_SIZE = 64 * 1024 * 1024
MAX_DECOMPRESSED_SIZE = 128 * 1024 * 1024
MAX_METADATA_SIZE = 2 * 1024 * 1024
MAX_RETRIES = 3
MAX_REDIRECTS = 3
HTTP_TIMEOUT_SECONDS = 15
RETRY_DELAY_SECONDS = 1
CHUNK_SIZE = 64 * 1024
TMP_ROOT = Path("/var/tmp/bunkerweb")
DOWNLOAD_HOST = "download.db-ip.com"
MMDB_FILENAME_SUFFIX = r"\d{4}-(?:0[1-9]|1[0-2])\.mmdb\.gz"


class MMDBError(Exception):
    """Base class for errors that invalidate a DB-IP update."""


class MetadataError(MMDBError):
    """The official DB-IP metadata was unavailable or ambiguous."""


class DownloadError(MMDBError):
    """The DB-IP archive could not be downloaded safely."""


class SizeLimitError(DownloadError):
    """A response exceeded its configured bound."""


class DecompressionError(MMDBError):
    """The archive was not a valid, bounded gzip stream."""


class IntegrityError(MMDBError):
    """The archive did not match DB-IP's published SHA-1."""

    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__(f"expected {expected}, got {actual}")


class MMDBValidationError(MMDBError):
    """The candidate could not be opened as an MMDB database."""


@dataclass(frozen=True)
class MMDBDescriptor:
    key: str
    display_name: str
    metadata_url: str
    download_prefix: str
    local_name: str
    metadata_host: str = "db-ip.com"
    download_host: str = DOWNLOAD_HOST


@dataclass(frozen=True)
class DBIPMetadata:
    expected_sha1: str
    download_url: str


@dataclass(frozen=True)
class VerifiedCandidate:
    path: Path
    metadata: DBIPMetadata
    sha1: str
    checksum: str


@dataclass(frozen=True)
class RuntimeCandidate:
    path: Path
    source: str
    sha1: str
    checksum: str


COUNTRY = MMDBDescriptor(
    key="country",
    display_name="Country",
    metadata_url="https://db-ip.com/db/download/ip-to-country-lite",
    download_prefix="dbip-country-lite-",
    local_name="country.mmdb",
)
ASN = MMDBDescriptor(
    key="asn",
    display_name="ASN",
    metadata_url="https://db-ip.com/db/download/ip-to-asn-lite",
    download_prefix="dbip-asn-lite-",
    local_name="asn.mmdb",
)
DESCRIPTORS = (ASN, COUNTRY)


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: List[Tuple[str, str]] = []
        self._text: List[str] = []
        self._anchor_href: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            self._text.append(" ")
            return
        self._anchor_href = dict(attrs).get("href")

    def handle_data(self, data):
        if self._anchor_href is None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a":
            return
        if self._anchor_href:
            self.links.append((self._anchor_href, "".join(self._text)))
            self._text = []
        self._anchor_href = None


def _artifact_link(href: str, descriptor: MMDBDescriptor) -> bool:
    try:
        filename = urlsplit(href).path.rsplit("/", 1)[-1]
    except ValueError:
        return False
    return bool(re.fullmatch(re.escape(descriptor.download_prefix) + MMDB_FILENAME_SUFFIX, filename, re.IGNORECASE))


def _validate_endpoint(url: str, expected_host: str, error_type=DownloadError):
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise error_type(f"Invalid DB-IP URL: {url}") from error
    if (
        parsed.scheme.lower() != "https"
        or hostname is None
        or hostname.lower() != expected_host
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise error_type(f"Unexpected DB-IP endpoint: {url}")
    return parsed


def _validate_artifact_url(url: str, descriptor: MMDBDescriptor):
    parsed = _validate_endpoint(url, descriptor.download_host, MetadataError)
    filename = parsed.path.rsplit("/", 1)[-1]
    if parsed.path.split("/")[:-1] != ["", "free"] or not re.fullmatch(re.escape(descriptor.download_prefix) + MMDB_FILENAME_SUFFIX, filename, re.IGNORECASE):
        raise MetadataError(f"Unexpected {descriptor.display_name} MMDB download path: {url}")
    return parsed


def parse_metadata(html: str, descriptor: MMDBDescriptor) -> DBIPMetadata:
    """Extract exactly one MMDB SHA-1 and its matching download link."""
    parser = _PageParser()
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, TypeError) as error:
        raise MetadataError(f"Unable to parse DB-IP {descriptor.display_name} metadata") from error

    candidates = [(href, block) for href, block in parser.links if _artifact_link(href, descriptor)]
    if len(candidates) != 1:
        raise MetadataError(f"Expected one {descriptor.display_name} MMDB artifact, found {len(candidates)}")

    download_url, block = candidates[0]
    _validate_artifact_url(download_url, descriptor)
    normalized = " ".join(block.split())
    if len(re.findall(r"\bformat\b\s*[:\-]?\s*mmdb\b", normalized, re.IGNORECASE)) != 1:
        raise MetadataError(f"MMDB format is not unambiguous for {descriptor.display_name}")

    sha1_values = re.findall(r"\bsha1sum\b\s*[:\-]?\s*([^\s]+)", normalized, re.IGNORECASE)
    hash_values = re.findall(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])", normalized, re.IGNORECASE)
    if len(sha1_values) != 1 or not re.fullmatch(r"[0-9a-f]{40}", sha1_values[0], re.IGNORECASE) or len(hash_values) != 1:
        raise MetadataError(f"Expected one SHA-1 for {descriptor.display_name} MMDB")
    return DBIPMetadata(expected_sha1=sha1_values[0].lower(), download_url=download_url)


def _status(response) -> int:
    status = getattr(response, "status", None)
    if status is None:
        status = response.getcode()
    return status or 200


def _content_length(response, maximum: int) -> Optional[int]:
    headers = getattr(response, "headers", {}) or {}
    value = headers.get("Content-Length")
    if value is None:
        return None
    try:
        length = int(value)
    except (TypeError, ValueError) as error:
        raise DownloadError("Invalid Content-Length from DB-IP") from error
    if length < 0:
        raise DownloadError("Invalid negative Content-Length from DB-IP")
    if length > maximum:
        raise SizeLimitError(f"DB-IP response exceeds {maximum} bytes")
    return length


class _RestrictedRedirectHandler(HTTPRedirectHandler):
    def __init__(self, expected_host: str):
        super().__init__()
        self.expected_host = expected_host
        self.max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirect_url = urljoin(req.full_url, newurl)
        _validate_endpoint(redirect_url, self.expected_host)
        return super().redirect_request(req, fp, code, msg, headers, redirect_url)


def _open_response(url: str, expected_host: str):
    _validate_endpoint(url, expected_host)
    opener = build_opener(
        _RestrictedRedirectHandler(expected_host),
        HTTPSHandler(context=ssl.create_default_context()),
    )
    request = Request(url, headers={"User-Agent": "BunkerWeb MMDB updater"})
    response = None
    try:
        response = opener.open(request, timeout=HTTP_TIMEOUT_SECONDS)
        _validate_endpoint(response.geturl(), expected_host)
        return response
    except Exception:
        if response is not None:
            response.close()
        raise


class _RetryableHTTP(Exception):
    def __init__(self, status: int):
        self.status = status
        super().__init__(f"HTTP {status}")


_RETRYABLE_NETWORK_ERRORS = (ConnectionError, IncompleteRead, SocketTimeout, TimeoutError, URLError)


def _retryable_status(status: int) -> bool:
    return status == 429 or 500 <= status <= 599


def _request_stream(
    url: str,
    expected_host: str,
    maximum: int,
    consumer: Callable,
    logger: logging.Logger,
):
    last_error: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        response = None
        try:
            response = _open_response(url, expected_host)
            status = _status(response)
            if _retryable_status(status):
                raise _RetryableHTTP(status)
            if status >= 400:
                raise DownloadError(f"DB-IP returned HTTP {status}")
            content_length = _content_length(response, maximum)
            return consumer(response, content_length)
        except _RetryableHTTP as error:
            last_error = error
        except HTTPError as error:
            error.close()
            if _retryable_status(error.code):
                last_error = error
            else:
                raise DownloadError(f"DB-IP returned HTTP {error.code}") from error
        except _RETRYABLE_NETWORK_ERRORS as error:
            last_error = error
        except MMDBError:
            raise
        finally:
            if response is not None:
                response.close()

        if attempt + 1 < MAX_RETRIES:
            logger.warning("Transient DB-IP download error, retrying (%s/%s)", attempt + 1, MAX_RETRIES)
            sleep(RETRY_DELAY_SECONDS)

    raise DownloadError(f"DB-IP request failed after {MAX_RETRIES} attempts: {last_error}") from last_error


def _read_response(response, content_length: Optional[int], maximum: int) -> bytes:
    data = bytearray()
    total = 0
    while True:
        chunk = response.read(CHUNK_SIZE)
        if not chunk:
            break
        if not isinstance(chunk, bytes):
            raise DownloadError("DB-IP returned a non-byte response")
        total += len(chunk)
        if total > maximum:
            raise SizeLimitError(f"DB-IP response exceeds {maximum} bytes")
        data.extend(chunk)
    if content_length is not None and total != content_length:
        raise DownloadError("DB-IP response was truncated")
    if not data:
        raise DownloadError("DB-IP returned an empty response")
    return bytes(data)


def fetch_metadata(descriptor: MMDBDescriptor, logger: Optional[logging.Logger] = None) -> DBIPMetadata:
    logger = logger or LOGGER
    logger.info("Fetching DB-IP metadata for %s database", descriptor.display_name)
    try:
        body = _request_stream(
            descriptor.metadata_url,
            descriptor.metadata_host,
            MAX_METADATA_SIZE,
            lambda response, length: _read_response(response, length, MAX_METADATA_SIZE),
            logger,
        )
        html = body.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MetadataError(f"DB-IP {descriptor.display_name} metadata is not UTF-8") from error
    except DownloadError as error:
        raise MetadataError(f"Unable to fetch DB-IP {descriptor.display_name} metadata: {error}") from error
    return parse_metadata(html, descriptor)


def _copy_response(response, content_length: Optional[int], destination: Path, maximum: int) -> None:
    total = 0
    with destination.open("wb") as output:
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            if not isinstance(chunk, bytes):
                raise DownloadError("DB-IP returned a non-byte response")
            total += len(chunk)
            if total > maximum:
                raise SizeLimitError(f"DB-IP response exceeds {maximum} bytes")
            output.write(chunk)
    if content_length is not None and total != content_length:
        raise DownloadError("DB-IP response was truncated")
    if total == 0:
        raise DownloadError("DB-IP returned an empty response")


def download_to_file(
    url: str,
    destination: Path,
    *,
    expected_host: str = DOWNLOAD_HOST,
    max_size: int = MAX_COMPRESSED_SIZE,
    logger: Optional[logging.Logger] = None,
) -> None:
    logger = logger or LOGGER
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        _request_stream(
            url,
            expected_host,
            max_size,
            lambda response, length: _copy_response(response, length, destination, max_size),
            logger,
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def decompress_to_file(archive: Path, destination: Path, *, max_size: int = MAX_DECOMPRESSED_SIZE) -> None:
    archive = Path(archive)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        total = 0
        with archive.open("rb") as compressed, GzipFile(fileobj=compressed, mode="rb") as source, destination.open("wb") as output:
            while True:
                chunk = source.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_size:
                    raise SizeLimitError(f"Decompressed MMDB exceeds {max_size} bytes")
                output.write(chunk)
    except SizeLimitError:
        destination.unlink(missing_ok=True)
        raise
    except (EOFError, OSError, zlib.error) as error:
        destination.unlink(missing_ok=True)
        raise DecompressionError(f"Invalid or truncated gzip archive: {archive}") from error


def validate_mmdb(path: Path) -> None:
    if open_database is None:
        raise MMDBValidationError("maxminddb is not installed")
    try:
        with open_database(Path(path).as_posix()):
            pass
    except Exception as error:
        raise MMDBValidationError(f"Unable to open MMDB database {path}") from error


def download_verified_candidate(
    descriptor: MMDBDescriptor,
    metadata: DBIPMetadata,
    temp_dir: Path,
    *,
    logger: Optional[logging.Logger] = None,
) -> VerifiedCandidate:
    logger = logger or LOGGER
    if not re.fullmatch(r"[0-9a-f]{40}", metadata.expected_sha1, re.IGNORECASE):
        raise MetadataError(f"Invalid DB-IP SHA-1 for {descriptor.display_name}")
    _validate_artifact_url(metadata.download_url, descriptor)
    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    archive = temp_dir / f"{descriptor.key}.mmdb.gz"
    candidate = temp_dir / descriptor.local_name
    try:
        logger.info("Downloading %s MMDB candidate from %s", descriptor.display_name, metadata.download_url)
        download_to_file(metadata.download_url, archive, expected_host=descriptor.download_host, logger=logger)
        logger.info("Decompressing %s MMDB candidate", descriptor.display_name)
        decompress_to_file(archive, candidate)
        logger.info("Verifying %s MMDB SHA-1", descriptor.display_name)
        actual_sha1 = file_hash(candidate, algorithm="sha1")
        if not compare_digest(actual_sha1, metadata.expected_sha1):
            raise IntegrityError(metadata.expected_sha1, actual_sha1)
        logger.info("%s MMDB checksum verified", descriptor.display_name)
        logger.info("Validating %s MMDB structure", descriptor.display_name)
        validate_mmdb(candidate)
        logger.info("%s MMDB structure validated", descriptor.display_name)
        return VerifiedCandidate(candidate, metadata, actual_sha1, file_hash(candidate))
    except Exception:
        candidate.unlink(missing_ok=True)
        archive.unlink(missing_ok=True)
        raise
    finally:
        archive.unlink(missing_ok=True)


def _candidate_from_path(path: Path, source: str, logger: logging.Logger) -> Optional[RuntimeCandidate]:
    path = Path(path)
    if not path.is_file():
        return None
    try:
        validate_mmdb(path)
        return RuntimeCandidate(path, source, file_hash(path, algorithm="sha1"), file_hash(path))
    except (MMDBValidationError, OSError) as error:
        logger.warning("Ignoring invalid %s MMDB at %s: %s", source, path, error)
        return None


def _collect_runtime_candidates(cache_path: Path, fallback_path: Path, logger: logging.Logger) -> List[RuntimeCandidate]:
    candidates: List[RuntimeCandidate] = []
    seen = set()
    for source, path in (("active", cache_path), ("bundled fallback", fallback_path)):
        path = Path(path)
        key = path.absolute()
        if key in seen:
            continue
        seen.add(key)
        candidate = _candidate_from_path(path, source, logger)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _load_database_candidate(job, descriptor: MMDBDescriptor, temp_dir: Path, logger: logging.Logger) -> Optional[RuntimeCandidate]:
    """Load and validate the DB blob only when no local candidate can be used."""
    try:
        database = getattr(job, "db", None)
        if database is not None:
            cached = database.get_job_cache_file(job.job_name, descriptor.local_name, with_info=True, with_data=True)
        else:
            cached = job.get_cache(descriptor.local_name, with_info=True, with_data=True)
    except Exception as error:
        logger.warning("Unable to load cached %s MMDB data: %s", descriptor.display_name, error)
        return None

    data = cached.get("data") if isinstance(cached, dict) else cached
    if not isinstance(data, (bytes, bytearray)):
        return None
    cached_path = Path(temp_dir) / f"database-{descriptor.key}.mmdb"
    try:
        cached_path.write_bytes(bytes(data))
    except OSError as error:
        logger.warning("Unable to materialize cached %s MMDB data: %s", descriptor.display_name, error)
        return None
    candidate = _candidate_from_path(cached_path, "DB cache", logger)
    if candidate is None:
        cached_path.unlink(missing_ok=True)
    return candidate


def _publish_local(descriptor: MMDBDescriptor, target: Path, source: Path, logger: logging.Logger) -> int:
    """Publish the cache file on disk only, leaving the DB row untouched."""
    source = Path(source)
    try:
        if target.is_file() and compare_digest(file_hash(target), file_hash(source)):
            return 0
        write_atomic(target, source.read_bytes())
    except (OSError, ValueError) as error:
        logger.error("Unable to publish %s MMDB to the local cache: %s", descriptor.display_name, error)
        return 2
    logger.info("%s MMDB published to the local cache only", descriptor.display_name)
    return 1


def _publish_runtime(job, descriptor: MMDBDescriptor, source: Path, checksum: str, logger: logging.Logger, *, trusted: bool = False) -> int:
    # A failed restore means the DB may still hold newer data than anything on disk, so a
    # locally-derived candidate must not be written back to it. A verified download is checked
    # against DB-IP's own SHA-1, owes nothing to the broken restore, and is always authoritative.
    if not trusted and getattr(job, "restore_ok", True) is False:
        logger.warning("Initial cache restore failed; not updating the %s MMDB DB cache", descriptor.display_name)
        return _publish_local(descriptor, Path(job.job_path) / descriptor.local_name, source, logger)
    cached, error = job.cache_file(descriptor.local_name, source, checksum=checksum, delete_file=False)
    if not cached:
        logger.error("Error while caching %s MMDB: %s", descriptor.display_name, error)
        return 2
    logger.info("%s MMDB verified and cached", descriptor.display_name)
    return 1


def update_runtime_mmdb(
    descriptor: MMDBDescriptor,
    job,
    fallback_path: Path,
    *,
    logger: Optional[logging.Logger] = None,
    temp_root: Path = TMP_ROOT,
) -> int:
    """Update one scheduler MMDB and return 0 unchanged, 1 changed, or 2 failed."""
    logger = logger or LOGGER
    temp_root = Path(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=f".{descriptor.key}-mmdb-", dir=temp_root) as working:
        working_path = Path(working)
        cache_path = Path(job.job_path) / descriptor.local_name
        try:
            job_cache = job.get_cache(descriptor.local_name, with_info=True, with_data=False)
        except Exception as error:
            logger.warning("Unable to inspect cached %s MMDB: %s", descriptor.display_name, error)
            job_cache = None
        candidates = _collect_runtime_candidates(cache_path, Path(fallback_path), logger)
        active = next((candidate for candidate in candidates if candidate.source == "active"), None)

        try:
            metadata = fetch_metadata(descriptor, logger=logger)
        except MMDBError as error:
            if active is not None:
                logger.warning("DB-IP metadata unavailable; retaining existing %s MMDB: %s", descriptor.display_name, error)
                return 0
            fallback = next((candidate for candidate in candidates if candidate.source == "bundled fallback"), None)
            if fallback is None:
                fallback = _load_database_candidate(job, descriptor, working_path, logger)
            if fallback is not None:
                logger.warning("DB-IP metadata unavailable; restoring %s MMDB from %s", descriptor.display_name, fallback.source)
                return _publish_runtime(job, descriptor, fallback.path, fallback.checksum, logger)
            logger.error("Unable to verify %s MMDB and no usable fallback exists: %s", descriptor.display_name, error)
            return 2

        matching = [candidate for candidate in candidates if compare_digest(candidate.sha1, metadata.expected_sha1)]
        if matching:
            selected = matching[0]
            if selected.source == "active" and isinstance(job_cache, dict) and compare_digest(str(job_cache.get("checksum") or ""), selected.checksum):
                logger.info("Current %s MMDB matches DB-IP SHA-1, skipping download", descriptor.display_name)
                return 0
            if selected.source == "active":
                logger.info("Current %s MMDB matches DB-IP SHA-1; repairing the DB cache metadata", descriptor.display_name)
            else:
                logger.info("Bundled %s MMDB matches DB-IP SHA-1; caching it", descriptor.display_name)
            return _publish_runtime(job, descriptor, selected.path, selected.checksum, logger)

        database_candidate = _load_database_candidate(job, descriptor, working_path, logger)
        if database_candidate is not None and compare_digest(database_candidate.sha1, metadata.expected_sha1):
            logger.info("DB cache %s MMDB matches DB-IP SHA-1; restoring it", descriptor.display_name)
            return _publish_runtime(job, descriptor, database_candidate.path, database_candidate.checksum, logger)

        try:
            verified = download_verified_candidate(descriptor, metadata, working_path, logger=logger)
        except IntegrityError as error:
            logger.error("%s MMDB integrity check failed: expected %s, got %s", descriptor.display_name, error.expected, error.actual)
            if candidates:
                logger.warning("Retaining existing %s MMDB after integrity failure", descriptor.display_name)
            return 2
        except (MMDBError, OSError) as error:
            logger.error("Unable to update %s MMDB: %s", descriptor.display_name, error)
            if candidates:
                logger.warning("Retaining existing %s MMDB after update failure", descriptor.display_name)
            return 2

        return _publish_runtime(job, descriptor, verified.path, verified.checksum, logger, trusted=True)


def _publish_bundled(verified: Dict[MMDBDescriptor, VerifiedCandidate], target_dir: Path, logger: logging.Logger) -> bool:
    replacements: List[Tuple[Path, Path]] = []
    staged: List[Path] = []
    for descriptor in DESCRIPTORS:
        target = target_dir / descriptor.local_name
        candidate = verified[descriptor].path
        if target.is_file() and compare_digest(file_hash(target), verified[descriptor].checksum):
            continue
        replacements.append((target, candidate))

    if not replacements:
        logger.info("Bundled DB-IP MMDB files are already current")
        return False

    backups: Dict[Path, Optional[Path]] = {}
    published: List[Path] = []
    try:
        same_dir_replacements: List[Tuple[Path, Path]] = []
        for target, candidate in replacements:
            fd, staging_name = mkstemp(prefix=f".{target.name}.staging-", dir=target.parent)
            os.close(fd)
            staging = Path(staging_name)
            staged.append(staging)
            copy2(candidate, staging)
            if target.is_file():
                staging.chmod(S_IMODE(target.stat().st_mode))
            same_dir_replacements.append((target, staging))

        for target, _candidate in same_dir_replacements:
            if not target.exists():
                backups[target] = None
                continue
            fd, backup_name = mkstemp(prefix=f".{target.name}.backup-", dir=target.parent)
            os.close(fd)
            backup = Path(backup_name)
            copy2(target, backup)
            backups[target] = backup
        for target, staging in same_dir_replacements:
            os.replace(staging, target)
            published.append(target)
    except Exception:
        for target in reversed(published):
            backup = backups.get(target)
            try:
                if backup is None:
                    target.unlink(missing_ok=True)
                else:
                    os.replace(backup, target)
                    backups[target] = None
            except OSError as error:
                if backup is None:
                    logger.error("Unable to remove the newly published %s: %s", target, error)
                else:
                    # Drop the entry so the cleanup below keeps the only good copy left of this file.
                    backups[target] = None
                    logger.error("Unable to roll back %s, recovery copy kept at %s: %s", target, backup, error)
        raise
    finally:
        for staging in staged:
            staging.unlink(missing_ok=True)
        for backup in backups.values():
            if backup is not None:
                backup.unlink(missing_ok=True)

    logger.info("Published verified DB-IP MMDB files: %s", ", ".join(target.name for target, _ in replacements))
    return True


def update_bundled_mmdbs(target_dir: Path, temp_root: Path, *, logger: Optional[logging.Logger] = None) -> bool:
    """Verify ASN and Country before publishing either bundled MMDB."""
    logger = logger or LOGGER
    target_dir = Path(target_dir)
    temp_root = Path(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".mmdb-update-", dir=temp_root) as working:
        working_path = Path(working)
        verified: Dict[MMDBDescriptor, VerifiedCandidate] = {}
        try:
            for descriptor in DESCRIPTORS:
                metadata = fetch_metadata(descriptor, logger=logger)
                verified[descriptor] = download_verified_candidate(descriptor, metadata, working_path, logger=logger)
        except MMDBError as error:
            logger.error("Bundled MMDB update aborted before publication: %s", error)
            return False
        try:
            _publish_bundled(verified, target_dir, logger)
        except OSError as error:
            logger.error("Bundled MMDB publication failed: %s", error)
            return False
        return True
