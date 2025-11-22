#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
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
from typing import Any, Dict, Literal, Optional, Tuple, Union
from tempfile import NamedTemporaryFile
from stat import S_IMODE

from common_utils import bytes_hash, file_hash

LOCK = Lock()
EXPIRE_TIME = {
    "hour": timedelta(hours=1).total_seconds(),
    "day": timedelta(days=1).total_seconds(),
    "week": timedelta(weeks=1).total_seconds(),
    "month": timedelta(days=30).total_seconds(),
}


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
        with NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as tmp:
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

        if not deprecated:
            db_metadata = self.db.get_metadata()
            if not isinstance(db_metadata, str) and not db_metadata["scheduler_first_start"]:
                self.restore_cache(manual=False)

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
                                for member in tar.getmembers():
                                    try:
                                        tar.extract(member, path=extract_path)
                                    except Exception as e:
                                        self.logger.error(f"Error extracting {member.name}: {e}")
                                ignored_dirs.add(extract_path.as_posix())
                                self.logger.debug(f"Restored cache directory {extract_path}")
                            except Exception as e:
                                self.logger.error(f"Error extracting tar file: {e}")
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
            if not manual and self.job_path.is_dir():
                for file in list(self.job_path.rglob("*")):
                    if file.as_posix().startswith(tuple(ignored_dirs)):
                        continue

                    self.logger.debug(f"Checking if {file} should be removed")
                    if file not in plugin_cache_files and file.is_file():
                        self.logger.debug(f"Removing non-cached file {file}")
                        file.unlink(missing_ok=True)
                        if file.parent.is_dir():
                            self.logger.debug(f"Removing directory {file.parent}")
                            rmtree(file.parent, ignore_errors=True)
                            if file.parent == self.job_path:
                                break
                    elif file.is_dir():
                        self.logger.debug(f"Removing directory {file}")
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
