#!/usr/bin/env python3
# Shared download / unpack / validate / cache logic for the three GeoIP databases.
# Imported by geoip-country.py, geoip-asn.py and geoip-city.py — not a job itself.
#
# Source priority is implicit, there is no source selector setting:
#   GEOIP_<KIND>_MMDB set (path or URL) -> custom
#   else MAXMIND_LICENSE_KEY set        -> MaxMind
#   else                               -> DB-IP lite

from dataclasses import dataclass
from datetime import date
from email.utils import formatdate
from gzip import decompress
from io import BytesIO
from os import environ, sep
from os.path import join
from pathlib import Path
from re import sub
from sys import path as sys_path
from tarfile import open as tar_open
from time import sleep
from traceback import format_exc
from typing import Optional, Tuple

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from maxminddb import open_database
from requests import RequestException, Response, get
from requests.exceptions import ConnectionError

from common_utils import bytes_hash, file_hash  # type: ignore

TMP_PATH = Path(sep, "var", "tmp", "bunkerweb")

# A cache row bigger than this is where MariaDB/MySQL max_allowed_packet (64 MB by
# default) starts rejecting the write, so the failure message must say so.
PACKET_HINT_THRESHOLD = 48 * 1024 * 1024

GZIP_MAGIC = b"\x1f\x8b"


@dataclass(frozen=True)
class Kind:
    """Everything that differs between the three databases."""

    name: str
    file_name: str
    setting: str
    dbip_page: str
    dbip_slug: str
    maxmind_edition: str
    # Substrings accepted in the mmdb metadata database_type. A City database also
    # carries country.iso_code, and GeoIP2-ISP carries the ASN fields, so both are
    # legitimate stand-ins rather than a misconfiguration.
    db_types: Tuple[str, ...]


KINDS = {
    "country": Kind(
        "country",
        "country.mmdb",
        "GEOIP_COUNTRY_MMDB",
        "https://db-ip.com/db/download/ip-to-country-lite",
        "country",
        "GeoLite2-Country",
        ("country", "city"),
    ),
    "asn": Kind(
        "asn",
        "asn.mmdb",
        "GEOIP_ASN_MMDB",
        "https://db-ip.com/db/download/ip-to-asn-lite",
        "asn",
        "GeoLite2-ASN",
        ("asn", "isp"),
    ),
    "city": Kind(
        "city",
        "city.mmdb",
        "GEOIP_CITY_MMDB",
        "https://db-ip.com/db/download/ip-to-city-lite",
        "city",
        "GeoLite2-City",
        ("city",),
    ),
}


@dataclass(frozen=True)
class Source:
    """Where one database comes from once the priority has been applied."""

    provider: str  # custom | maxmind | dbip
    url: str = ""
    path: str = ""  # local file, custom provider only
    auth: Optional[Tuple[str, str]] = None


def redact(text: str) -> str:
    """Strip the MaxMind licence key before anything reaches the logs.

    The deprecated key-only endpoint carries the key in the query string, and requests
    embeds the full URL in its exceptions ("401 Client Error: ... for url: ..."). So this
    must be applied to exception text and tracebacks too, not only to URLs we format
    ourselves — a wrong or expired key is precisely when those get logged.
    """
    return sub(r"(license_key=)[^&\s]*", r"\1***", text)


def resolve_source(kind: str, env=None, today=None) -> Source:
    """Apply the priority custom -> MaxMind -> DB-IP. Pure: no I/O, no network."""
    env = environ if env is None else env
    k = KINDS[kind]

    custom = (env.get(k.setting) or "").strip()
    if custom:
        if custom.startswith(("http://", "https://")):
            return Source("custom", url=custom)
        return Source("custom", path=custom)

    license_key = (env.get("MAXMIND_LICENSE_KEY") or "").strip()
    if license_key:
        account_id = (env.get("MAXMIND_ACCOUNT_ID") or "").strip()
        if account_id:
            return Source(
                "maxmind",
                url=f"https://download.maxmind.com/geoip/databases/{k.maxmind_edition}/download?suffix=tar.gz",
                auth=(account_id, license_key),
            )
        # Deprecated endpoint, kept by MaxMind for backwards compatibility: it is the
        # only one that works without an account ID. Callers warn about it.
        return Source(
            "maxmind",
            url=f"https://download.maxmind.com/app/geoip_download?edition_id={k.maxmind_edition}&license_key={license_key}&suffix=tar.gz",
        )

    month = (today or date.today()).strftime("%Y-%m")
    return Source("dbip", url=f"https://download.db-ip.com/free/dbip-{k.dbip_slug}-lite-{month}.mmdb.gz")


def _is_tar(payload: bytes) -> bool:
    """POSIX tar puts the "ustar" magic at offset 257."""
    return len(payload) > 262 and payload[257:262] == b"ustar"


def unpack(payload: bytes) -> bytes:
    """Return the raw mmdb out of a plain file, a .gz (DB-IP) or a .tar.gz (MaxMind)."""
    if payload[:2] == GZIP_MAGIC:
        payload = decompress(payload)

    if _is_tar(payload):
        # MaxMind archives ship as GeoLite2-City_20260701/GeoLite2-City.mmdb
        with tar_open(fileobj=BytesIO(payload), mode="r:") as tar:
            member = next((m for m in tar.getmembers() if m.isfile() and m.name.endswith(".mmdb")), None)
            if member is None:
                raise ValueError("archive contains no .mmdb member")
            extracted = tar.extractfile(member)
            if extracted is None:
                raise ValueError(f"could not read {member.name} from archive")
            return extracted.read()

    return payload


def validate(path: Path, kind: str) -> str:
    """Open the database and check it is the kind we asked for.

    Without the database_type check, pointing GEOIP_CITY_MMDB at a country database
    silently yields no city forever instead of failing.
    """
    with open_database(path.as_posix()) as reader:
        database_type = reader.metadata().database_type

    lowered = database_type.lower()
    if not any(token in lowered for token in KINDS[kind].db_types):
        raise ValueError(f"database type {database_type!r} is not a {kind} database")
    return database_type


def request(url: str, *, auth=None, headers=None, timeout=5, stream=False, logger=None) -> Response:
    """GET with the retry/backoff behaviour the mmdb jobs have always had."""
    max_retries = 3
    retry_count = 0
    while True:
        try:
            return get(url, auth=auth, headers=headers, timeout=timeout, stream=stream)
        except ConnectionError:
            retry_count += 1
            if retry_count == max_retries:
                raise
            if logger:
                logger.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
            sleep(3)


def _dbip_is_current(kind: str, digest: str, logger) -> bool:
    """DB-IP publishes the sha1 of the current file on its download page.

    Cheapest possible freshness probe: no need to pull 125 MB of city database to
    discover it has not changed since yesterday.
    """
    try:
        response = request(KINDS[kind].dbip_page, timeout=5, logger=logger)
        if response.status_code != 200:
            logger.warning("Unable to check the latest version from db-ip.com, downloading anyway...")
            return False
        return response.content.find(digest.encode()) != -1
    except RequestException:
        logger.debug(redact(format_exc()))
        logger.warning("Unable to reach db-ip.com, downloading anyway...")
        return False


def _fetch_payload(source: Source, job_cache, logger) -> Optional[bytes]:
    """Read the custom local file, or download. None means "unchanged, nothing to do"."""
    if source.path:
        return Path(source.path).read_bytes()

    headers = {}
    # MaxMind honours If-Modified-Since (this is what geoipupdate relies on) and a
    # well-behaved custom URL will too. A 304 saves the whole transfer.
    last_update = job_cache.get("last_update") if job_cache else None
    if last_update:
        headers["If-Modified-Since"] = formatdate(last_update, usegmt=True)

    logger.info(f"Downloading {source.provider} database from {redact(source.url)} ...")
    with request(source.url, auth=source.auth, headers=headers, timeout=5, stream=True, logger=logger) as response:
        if response.status_code == 304:
            return None
        response.raise_for_status()
        content = BytesIO()
        for chunk in response.iter_content(chunk_size=4 * 1024):
            if chunk:
                content.write(chunk)
        return content.getvalue()


def _store(job, kind: str, tmp_path: Path, digest: str, logger) -> bool:
    # delete_file defaults to True: the temporary copy is dropped once the database
    # lives in the cache, so a 400 MB city database is never on disk twice.
    cached, err = job.cache_file(KINDS[kind].file_name, tmp_path, checksum=digest)
    if cached:
        return True

    logger.error(f"Error while caching the {kind} database: {err}")
    if tmp_path.stat().st_size > PACKET_HINT_THRESHOLD:
        size_mb = tmp_path.stat().st_size // (1024 * 1024)
        logger.error(
            f"The {kind} database is {size_mb} MB. MariaDB/MySQL reject rows larger than max_allowed_packet "
            f"(64 MB by default): set max_allowed_packet to at least {size_mb * 2} MB on the database server, "
            f"or leave GEOIP_CITY to no. The worker also needs more than {size_mb} MB of memory to store a "
            f"database of that size (WORKER_MAX_MEMORY_KB and the container memory limit)."
        )
    return False


def purge(kind: str, logger, job) -> int:
    """Drop a database that is no longer wanted. 1 when something was actually removed."""
    k = KINDS[kind]
    cached = job.get_cache(k.file_name, with_info=True, with_data=False)
    on_disk = job.job_path.joinpath(k.file_name)
    if not isinstance(cached, dict) and not on_disk.is_file():
        return 0

    deleted, err = job.del_cache(k.file_name)
    if not deleted:
        logger.error(f"Error while removing the {kind} database: {err}")
        return 2

    TMP_PATH.joinpath(k.file_name).unlink(missing_ok=True)
    logger.info(f"Removed the {kind} database, it is no longer enabled")
    return 1


def run(kind: str, logger, job) -> int:
    """Refresh one database. 0 = unchanged, 1 = changed (reload), 2 = error."""
    k = KINDS[kind]
    tmp_path = TMP_PATH.joinpath(k.file_name)
    source = resolve_source(kind)

    if source.provider == "maxmind" and not source.auth:
        logger.warning(
            "MAXMIND_ACCOUNT_ID is not set, falling back to the deprecated key-only download endpoint. " "Add your account ID before MaxMind retires it."
        )

    try:
        job_cache = job.get_cache(k.file_name, with_info=True, with_data=True)
        job_cache = job_cache if isinstance(job_cache, dict) else None

        cached_data = job_cache.get("data") if job_cache else None

        # Freshness probe. Only a database we have *already cached* lets us stop early:
        # the cache is what gets shipped to the instances, so a bundled fallback that
        # happens to be current still has to be stored. Conflating the two would leave a
        # fresh install with no database on its instances at all.
        if cached_data and source.provider == "dbip":
            if _dbip_is_current(kind, bytes_hash(cached_data, algorithm="sha1"), logger):
                logger.info(f"{k.file_name} is already the latest version, skipping download...")
                return 0

        # Same idea for the bundled fallback: skip the transfer, but keep going so it
        # reaches the cache.
        skip_download = False
        if not cached_data and source.provider == "dbip" and tmp_path.is_file():
            if _dbip_is_current(kind, file_hash(tmp_path, algorithm="sha1"), logger):
                logger.info(f"{k.file_name} on disk is already the latest version, caching it without downloading...")
                skip_download = True

        try:
            if not skip_download:
                # If-Modified-Since is only meaningful when we already have something
                # cached, which is also what makes a 304 safe to treat as "nothing to do".
                payload = _fetch_payload(source, job_cache if cached_data else None, logger)
                if payload is None:
                    logger.info(f"{k.file_name} is unchanged at the source, skipping download...")
                    return 0
                tmp_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path.write_bytes(unpack(payload))
        except BaseException as e:
            logger.debug(redact(format_exc()))
            logger.error(f"Error while retrieving the {kind} database from {redact(source.url) or source.path}: {redact(str(e))}")
            if not tmp_path.is_file():
                # No bundled fallback exists for city, so it simply stays unavailable
                # and lookups fail open, exactly like a missing country database.
                return 2
            logger.warning(f"Falling back to the {kind} database already present on disk.")

        try:
            database_type = validate(tmp_path, kind)
        except BaseException:
            # Never leave a rejected file sitting under the database's name: with a custom
            # source it can be any file the operator pointed the setting at, and the next
            # run would otherwise treat it as the on-disk fallback.
            tmp_path.unlink(missing_ok=True)
            raise
        logger.info(f"{k.file_name} is a valid {database_type} database")

        digest = file_hash(tmp_path)
        if job_cache and digest == job_cache.get("checksum"):
            logger.info(f"{k.file_name} is identical to the cached file, reload is not needed")
            return 0

        if not _store(job, kind, tmp_path, digest, logger):
            return 2

        logger.info(f"Updated {k.file_name} from {source.provider}")
        return 1
    except BaseException as e:
        logger.debug(redact(format_exc()))
        logger.error(f"Exception while refreshing the {kind} database: {redact(str(e))}")
        return 2
