"""Safe read helpers for the cached Certbot configuration tree."""

from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from tarfile import open as tar_open
from tempfile import TemporaryDirectory
from typing import Iterator

from common_utils import safe_tar_extractall  # type: ignore
from letsencrypt_consistency import detect_orphan_renewals  # type: ignore

LE_CACHE_DIR = Path("/var/cache/bunkerweb/letsencrypt/etc")
LE_CACHE_FILE_NAME = f"folder:{LE_CACHE_DIR.as_posix()}.tgz"
LE_CACHE_JOB_NAME = "certbot-renew"
LE_SCRATCH_ROOT = Path("/var/tmp/bunkerweb/api/letsencrypt")


def _cache_snapshot(db) -> tuple[bytes, str | None]:
    for cache_file in db.get_jobs_cache_files(job_name=LE_CACHE_JOB_NAME):
        if cache_file.get("file_name") == LE_CACHE_FILE_NAME and cache_file.get("data"):
            return bytes(cache_file["data"]), cache_file.get("checksum") or None
    raise ValueError("Let's Encrypt cache is not available")


@contextmanager
def _restored_cache(db, scratch_root: Path | None = None) -> Iterator[tuple[Path, str | None]]:
    root = scratch_root or LE_SCRATCH_ROOT
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with TemporaryDirectory(prefix="le-api-", dir=root) as directory:
        scratch = Path(directory)
        data, checksum = _cache_snapshot(db)
        with tar_open(fileobj=BytesIO(data), mode="r:gz") as archive:
            safe_tar_extractall(archive, scratch, tar_filter="auto")
        yield scratch, checksum


def list_letsencrypt_orphans(db, *, scratch_root: Path | None = None) -> list[dict[str, str]]:
    """Return orphan renewal records from the canonical Certbot cache row."""
    with _restored_cache(db, scratch_root) as (scratch, _checksum):
        return detect_orphan_renewals(scratch)
