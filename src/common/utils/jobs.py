#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from json import dumps as json_dumps
from inspect import currentframe, getframeinfo
from io import BytesIO
from logging import Logger
from os import getenv, replace
from os.path import sep
from pathlib import Path
from shutil import rmtree
from tarfile import TarFile, open as tar_open
from threading import Lock
from traceback import format_exc
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from tempfile import NamedTemporaryFile
from time import time
from stat import S_IMODE

from common_utils import bytes_hash, file_hash, safe_tar_extractall

LOCK = Lock()
EXPIRE_TIME = {
    "hour": timedelta(hours=1).total_seconds(),
    "day": timedelta(days=1).total_seconds(),
    "week": timedelta(weeks=1).total_seconds(),
    "month": timedelta(days=30).total_seconds(),
}


# `_write_atomic` drops its scratch file next to the target, where `Job.restore_cache`'s stale-file
# sweep also runs. The sweep deletes anything it does not recognise, so the temporary needs a marker
# it can match on: a leading dot is not enough, because `.key` files are genuine cache entries that
# get pushed to instances.
ATOMIC_TMP_SUFFIX = ".bw-tmp"
# How long a temporary may exist before the sweep treats it as an orphan of a killed process rather
# than someone else's write in progress. A leaked temporary is not harmless: the cache is shipped to
# instances as a tar of this directory, so it would travel with it.
ATOMIC_TMP_GRACE_SECONDS = 300


# The Redis set the worker drains. Defined here and imported by src/worker/tasks.py rather than
# duplicated: two literals that drifted apart would not error anywhere -- one side would write a key
# the other never reads, and the change flag would stay pinned while the set grew.
RELOAD_ACK_PENDING_KEY = "bw:reload_pending_acks"

# What the job just deferred, waiting for the worker to publish it.
#
# A job cannot reach the broker itself: the worker strips CELERY_BROKER_URL from every job env
# (jobs include third-party plugin code, and the URL carries credentials), so a job's own client
# falls back to redis://localhost, which a split-container worker refuses -- the deferral then
# failed on every run and the feature was inert. Jobs run in-process in the worker, so hand the
# payload over through this module and let `_publish_deferred_acks` ship it.
_PENDING_ACKS: List[str] = []


def drain_pending_acks() -> List[str]:
    """Take what the job that just ran deferred. Worker side."""
    drained = list(_PENDING_ACKS)
    _PENDING_ACKS.clear()
    return drained


def defer_change_acknowledgement(keys: Tuple[str, ...], snapshot: Dict[str, Any], logger: Logger) -> str:
    """Hand a change acknowledgement to whoever performs the next successful push and reload.

    A job that writes files and requests a reload (exit 1) has not delivered anything yet: the push
    to the instances happens later, in the worker. Clearing its change flag on the way out records a
    delivery that may still fail, and nothing re-dispatches it -- the instances then keep serving the
    previous material with only a successful job run as evidence. Enqueue it instead; the worker
    applies it once the instances have the files and have reloaded, and leaves it queued otherwise.

    Returns an error string, empty when the acknowledgement was queued.
    """
    # Everything below stays inside the try: this runs on a job's way out, and a caller that hands
    # in something unexpected must get an error string back, not an exception that replaces the
    # job's own exit status.
    try:
        # Only scalars survive JSON. That is fine for the watermarks clear_applied_changes
        # compares -- until a caller defers a key whose watermark is not one: `plugins_config`
        # carries {plugin_id: last_config_change}, and silently dropping it would make the clear
        # match nothing, report success, and lose the flag forever. Refuse instead of degrading.
        serializable: Dict[str, Any] = {}
        for key, value in snapshot.items():
            if isinstance(value, datetime):
                serializable[key] = value.isoformat()
            elif isinstance(value, (bool, str, int, float, type(None))):
                serializable[key] = value
            elif any(key == f"{k}_changed" or key == f"last_{k}_change" for k in keys):
                return f"cannot defer {key}: {type(value).__name__} does not survive the broker, and dropping it would silently no-op the acknowledgement"

        _PENDING_ACKS.append(json_dumps({"keys": list(keys), "snapshot": serializable}))
        logger.info(f"Deferred the {list(keys)} acknowledgement until the configuration reaches the instances")
    except BaseException as e:
        logger.debug(format_exc())
        return str(e)

    return ""


def _write_atomic(target: Path, data: bytes) -> None:
    """Write data to target atomically to avoid partial files."""
    target.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = None
    try:
        existing_mode = target.stat().st_mode
    except FileNotFoundError:
        existing_mode = None

    attempt = 0
    last_exc: Optional[BaseException] = None
    while attempt < 3:
        attempt += 1
        with NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", suffix=ATOMIC_TMP_SUFFIX, delete=False) as tmp:
            tmp.write(data)
            tmp.flush()
            tmp_path = Path(tmp.name)

        if existing_mode is not None:
            tmp_path.chmod(S_IMODE(existing_mode))

        try:
            replace(tmp_path, target)
            return
        except FileNotFoundError as exc:
            last_exc = exc
            tmp_path.unlink(missing_ok=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            continue
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    raise last_exc or FileNotFoundError(f"Failed to write atomically to {target}")


class Job:
    def __init__(self, logger: Logger, job_path: Optional[Union[str, Path]] = None, db=None, *, deprecated: bool = False):
        """Initialize Job class."""
        if job_path:
            job_path = Path(job_path)
            plugin_id = job_path.parent.parent.name
            job_name = job_path.stem
        else:
            frame = currentframe()
            if not frame:
                raise ValueError("frame could not be determined.")

            source_path = Path(getframeinfo(frame.f_back).filename)

            if not source_path.exists():
                raise ValueError("source_file could not be determined.")

            plugin_id = source_path.parent.parent.name
            job_name = job_name or source_path.name.replace(".py", "")

        if not job_name:
            raise ValueError("Could not determine job name.")

        # Set job_path and job_name
        self.job_path = Path(sep, "var", "cache", "bunkerweb", plugin_id)
        self.job_name = job_name

        # Additional validation for job_path
        if self.job_path == Path(sep, "var", "cache", "bunkerweb"):
            raise ValueError("Could not determine job path. Ensure passed_plugin_id is valid.")

        self.job_path.mkdir(parents=True, exist_ok=True)

        self.db = db
        if not self.db:
            from Database import Database  # type: ignore

            self.db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI"))
        self.logger = logger or self.db.logger

        # Tracks whether the most recent cache restore succeeded. Callers that subsequently
        # re-cache their on-disk state (e.g. certbot-new / certbot-renew) MUST check this
        # flag before overwriting the DB — otherwise a failed restore + successful re-cache
        # silently wipes the good cached data from both disk and DB.
        self.restore_ok = True

        if not deprecated:
            try:
                db_metadata = self.db.get_metadata()
                if not isinstance(db_metadata, str) and not db_metadata["scheduler_first_start"]:
                    self.restore_ok = self.restore_cache(manual=False)
            except BaseException as e:
                # Any unexpected failure during auto-restore must fail closed so that
                # downstream re-caching guards still hold — a crash here would have
                # skipped the guards entirely and left job scripts thinking restore_ok
                # was still the default True.
                self.restore_ok = False
                self.logger.error(f"Exception while auto-restoring cache in Job.__init__ for plugin '{self.job_path.name}': {e}")

    def restore_cache(self, *, job_name: str = "", plugin_id: str = "", manual: bool = True) -> bool:
        """Restore job cache files from database."""
        ret = True
        job_cache_files = self.db.get_jobs_cache_files(plugin_id=plugin_id or self.job_path.name)  # type: ignore

        job_name = job_name or self.job_name
        plugin_cache_files = set()
        ignored_dirs = set()

        for job_cache_file in job_cache_files:
            cache_path = self.job_path.joinpath(job_cache_file["service_id"] or "", job_cache_file["file_name"])
            plugin_cache_files.add(cache_path)

            try:
                if job_cache_file["file_name"].endswith(".tgz"):
                    extract_path = cache_path.parent
                    if job_cache_file["file_name"].startswith("folder:"):
                        extract_path = Path(job_cache_file["file_name"].split("folder:", 1)[1].rsplit(".tgz", 1)[0])
                    if job_cache_file["job_name"] != job_name:
                        ignored_dirs.add(extract_path.as_posix())
                        continue
                    with LOCK:
                        rmtree(extract_path, ignore_errors=True)
                        extract_path.mkdir(parents=True, exist_ok=True)
                        with tar_open(fileobj=BytesIO(job_cache_file["data"]), mode="r:gz") as tar:
                            assert isinstance(tar, TarFile)
                            try:
                                # tar_filter="auto" preserves symlinks when the archive contains
                                # them (e.g. Let's Encrypt live/* → archive/*) while still
                                # applying the stricter "data" filter to link-free archives.
                                safe_tar_extractall(tar, extract_path, tar_filter="auto")
                                ignored_dirs.add(extract_path.as_posix())
                                self.logger.debug(f"Restored cache directory {extract_path}")
                            except Exception as e:
                                # NOTE: rmtree() above already wiped extract_path before we got
                                # here. Callers MUST check self.restore_ok before re-caching
                                # from disk, otherwise they will overwrite the good DB row with
                                # the empty post-rmtree state.
                                self.logger.error(
                                    f"Error extracting tar file for job '{job_cache_file['job_name']}' "
                                    f"(plugin '{self.job_path.name}', file '{job_cache_file['file_name']}'): {e}"
                                )
                                ret = False
                    continue
                elif job_cache_file["job_name"] != job_name:
                    continue
                _write_atomic(cache_path, job_cache_file["data"])
                ignored_dirs.add(cache_path.parent.as_posix())
                self.logger.debug(
                    "Restored cache file " + ((job_cache_file["service_id"] + "/") if job_cache_file["service_id"] else "") + job_cache_file["file_name"]
                )
            except BaseException as e:
                self.logger.error(
                    "Exception while restoring cache file "
                    + ((job_cache_file["service_id"] + "/") if job_cache_file["service_id"] else "")
                    + job_cache_file["file_name"]
                    + f" :\n{e}"
                )
                ret = False

        with LOCK:
            # An empty row set means the plugin's cache is UNKNOWN, not that everything on disk is
            # unused. The sweep below deletes any file `not in plugin_cache_files`, and with no rows
            # that set is empty, so every file under job_path qualifies while `ret` stays True. For
            # Let's Encrypt that is accounts/, archive/ and the live/ symlinks -- destroyed by
            # deleting one cache row in the web UI, with the job reporting success.
            # (dev reaches the same loss through `startswith(())`; 1.7's sweep is a set membership
            # test, so the expression differs and the outcome does not.)
            if not job_cache_files and self.job_path.is_dir() and any(self.job_path.iterdir()):
                self.logger.warning(f"No cache row for plugin '{self.job_path.name}'; keeping the files already in {self.job_path} instead of clearing them.")
            elif not manual and self.job_path.is_dir():
                # Deepest first: unlink stale non-cached files, then drop only now-empty dirs —
                # never rmtree the job_path root (its children are freshly restored cache dirs).
                for file in sorted(self.job_path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                    if file.as_posix().startswith(tuple(ignored_dirs)):
                        continue

                    # Another job's in-flight atomic write lives here and is not in
                    # plugin_cache_files, so this sweep used to delete it out from under the writer.
                    # This guard covers the sweep only. `_materialize_caches` in push-configs still
                    # rmtree()s the directory of every `folder:`/`.tgz` row, and only the Let's
                    # Encrypt tree takes a cross-process lock for it (letsencrypt_consistency.py),
                    # so a job writing into another such tree can still lose its work. A marker
                    # cannot defend against rmtree; closing that needs the same flock extended to
                    # every folder row.
                    # `_write_atomic` retries three times, which is exactly how many times the
                    # temporary vanished, so the write failed and the instance silently lost the
                    # file -- seen live as "Failed to materialize cache 'asn.mmdb'" while geoip-asn
                    # was restoring into the same directory a second earlier.
                    if file.is_file() and file.name.endswith(ATOMIC_TMP_SUFFIX):
                        try:
                            orphaned = time() - file.stat().st_mtime >= ATOMIC_TMP_GRACE_SECONDS
                        except OSError:
                            continue
                        if orphaned:
                            self.logger.debug(f"Removing orphaned temporary file {file}")
                            file.unlink(missing_ok=True)
                        continue

                    self.logger.debug(f"Checking if {file} should be removed")
                    if file.is_file() and file not in plugin_cache_files:
                        self.logger.debug(f"Removing non-cached file {file}")
                        file.unlink(missing_ok=True)
                    elif file.is_dir() and file != self.job_path and not any(file.iterdir()):
                        self.logger.debug(f"Removing empty directory {file}")
                        rmtree(file, ignore_errors=True)

        return ret

    def get_cache(
        self, name: Union[str, Path], *, job_name: str = "", service_id: str = "", plugin_id: str = "", with_info: bool = False, with_data: bool = True
    ) -> Optional[Union[Dict[str, Any], bytes]]:
        """Get cache file from database or from local cache file."""
        if isinstance(name, Path):
            name = str(name)

        cache_path = self.job_path.joinpath(service_id, name)
        ret_data = {}
        if cache_path.is_file():
            if with_data and not with_info:
                return cache_path.read_bytes()
            if with_data:
                ret_data["data"] = cache_path.read_bytes()

        if not ret_data:
            return self.db.get_job_cache_file(job_name or self.job_name, name, service_id=service_id, plugin_id=plugin_id or self.job_path.name, with_info=with_info, with_data=with_data)  # type: ignore
        ret_data.update(self.db.get_job_cache_file(job_name or self.job_name, name, service_id=service_id, plugin_id=plugin_id or self.job_path.name, with_info=True, with_data=False) or {})  # type: ignore
        return ret_data

    def is_cached_file(
        self, name: Union[str, Path], expire: Literal["hour", "day", "week", "month"], *, job_name: str = "", service_id: str = "", plugin_id: str = ""
    ) -> bool:
        """Check if cache file is cached and if it's still fresh."""
        if isinstance(name, Path):
            name = str(name)

        is_cached = False
        try:
            cache_info = self.get_cache(name, job_name=job_name, service_id=service_id, plugin_id=plugin_id, with_info=True, with_data=False)
            if isinstance(cache_info, dict) and cache_info.get("last_update"):
                current_time = datetime.now().astimezone().timestamp()
                if current_time < cache_info["last_update"]:
                    return False
                is_cached = current_time - cache_info["last_update"] < EXPIRE_TIME[expire]
        except BaseException:
            is_cached = False
        return is_cached

    def cache_file(
        self,
        name: Union[str, Path],
        file_cache: Union[bytes, str, Path],
        *,
        job_name: str = "",
        service_id: str = "",
        checksum: Optional[str] = None,
        delete_file: bool = True,
        overwrite_file: bool = True,
    ) -> Tuple[bool, str]:
        """Cache file in database and in local cache file."""
        if isinstance(name, Path):
            name = str(name)

        ret, err = True, "success"
        cache_path = self.job_path.joinpath(service_id, name)

        if isinstance(file_cache, bytes):
            content = file_cache
        else:
            if isinstance(file_cache, str):
                file_cache = Path(file_cache)
            assert isinstance(file_cache, Path)
            content = file_cache.read_bytes()

        if not name.startswith("folder:") and (overwrite_file or not cache_path.is_file()):
            _write_atomic(cache_path, content)

        if not checksum:
            checksum = bytes_hash(content)

        try:
            err = self.db.upsert_job_cache(service_id, name, content, job_name=job_name or self.job_name, checksum=checksum)  # type: ignore
            if err:
                ret = False

            if ret and isinstance(file_cache, Path) and delete_file and file_cache != cache_path:
                file_cache.unlink(missing_ok=True)
        except:
            return False, f"exception :\n{format_exc()}"
        return ret, err

    def cache_dir(self, dir_path: Union[str, Path], *, job_name: str = "", service_id: str = "") -> Tuple[bool, str]:
        """Cache directory in database and in local cache file."""
        if isinstance(dir_path, str):
            dir_path = Path(dir_path)
        assert isinstance(dir_path, Path)

        file_name = f"folder:{dir_path.as_posix()}.tgz"
        content = BytesIO()
        with tar_open(file_name, mode="w:gz", fileobj=content, compresslevel=9) as tgz:
            tgz.add(dir_path, arcname=".")
        content.seek(0, 0)

        return self.cache_file(file_name, content.getvalue(), job_name=job_name, service_id=service_id)

    def del_cache(self, name: Union[str, Path], *, job_name: str = "", service_id: str = "") -> Tuple[bool, str]:
        """Delete cache file from database and local cache file."""
        if isinstance(name, Path):
            name = str(name)

        ret, err = True, "success"
        job_name = job_name or self.job_name
        job_path = self.job_path.joinpath(service_id)
        cache_path = job_path.joinpath(name)

        if cache_path.is_file():
            cache_path.unlink(missing_ok=True)

        if job_path.is_dir() and not list(job_path.iterdir()):
            rmtree(job_path, ignore_errors=True)

        try:
            self.db.delete_job_cache(name, job_name=job_name, service_id=service_id)  # type: ignore
        except:
            return False, f"exception :\n{format_exc()}"
        return ret, err

    def cache_hash(self, name: Union[str, Path], *, job_name: str = "", service_id: str = "", plugin_id: str = "") -> Optional[str]:
        """Get cache file hash from database or from local cache file."""
        if isinstance(name, Path):
            name = str(name)

        cache_path = self.job_path.joinpath(service_id, name)
        if cache_path.is_file():
            return file_hash(cache_path)

        cache_info = self.get_cache(name, with_info=True, with_data=False, job_name=job_name, service_id=service_id, plugin_id=plugin_id)

        if isinstance(cache_info, dict):
            return cache_info.get("checksum")
        return None


# ? Backward compatibility functions


def is_cached_file(file: Union[str, Path], expire: Literal["hour", "day", "week", "month"], db) -> bool:
    job = Job(None, db, deprecated=True)
    job.logger.warning("is_cached_file is deprecated, use the Job.is_cached_file method instead.")
    if not isinstance(file, Path):
        file = Path(file)
    return job.is_cached_file(file.name, expire)


def get_file_in_db(file: Union[str, Path], db, *, job_name: str = "") -> Optional[bytes]:
    job = Job(None, db, deprecated=True)
    job.logger.warning("get_file_in_db is deprecated, use the Job.get_cache method instead.")
    if not isinstance(file, Path):
        file = Path(file)
    cache = job.get_cache(file.name, job_name=job_name, with_data=True)
    if isinstance(cache, dict):
        return cache.get("data")
    return None


def set_file_in_db(name: str, content: bytes, db, *, job_name: str = "", service_id: str = "", checksum: Optional[str] = None) -> Tuple[bool, str]:
    job = Job(None, db, deprecated=True)
    job.logger.warning("set_file_in_db is deprecated, use the Job.cache_file method instead.")
    return job.cache_file(name, content, job_name=job_name, service_id=service_id, checksum=checksum)


def del_file_in_db(name: str, db, *, service_id: str = "") -> Tuple[bool, str]:
    job = Job(None, db, deprecated=True)
    job.logger.warning("del_file_in_db is deprecated, use the Job.del_cache method instead.")
    return job.del_cache(name, service_id=service_id)


def cache_hash(cache: Union[str, Path], db) -> Optional[str]:
    job = Job(None, db, deprecated=True)
    job.logger.warning("cache_hash is deprecated, use the Job.cache_hash method instead.")
    if not isinstance(cache, Path):
        cache = Path(cache)
    return job.cache_hash(cache.name)


def cache_file(
    file: Union[str, Path], cache: Union[str, Path], _hash: Optional[str], db, *, delete_file: bool = True, service_id: str = ""
) -> Tuple[bool, str]:
    job = Job(None, db, deprecated=True)
    job.logger.warning("cache_file is deprecated, use the Job.cache_file method instead.")
    if not isinstance(file, Path):
        file = Path(file)
    if not isinstance(cache, Path):
        cache = Path(cache)
    return job.cache_file(cache.name, file, job_name=cache.name, service_id=service_id, checksum=_hash, delete_file=delete_file)
