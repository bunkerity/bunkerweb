#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from inspect import getsourcefile
from io import BytesIO
from logging import Logger
from os import getenv
from os.path import sep
from pathlib import Path
from shutil import rmtree
from sys import _getframe
from tarfile import open as tar_open
from threading import Lock
from traceback import format_exc
from typing import Any, Dict, Literal, Optional, Tuple, Union

from common_utils import bytes_hash, file_hash

LOCK = Lock()
EXPIRE_TIME = {
    "hour": timedelta(hours=1).total_seconds(),
    "day": timedelta(days=1).total_seconds(),
    "week": timedelta(weeks=1).total_seconds(),
    "month": timedelta(days=30).total_seconds(),
}


class Job:
    def __init__(self, logger: Optional[Logger] = None, db=None, *, job_name: str = "", deprecated: bool = False):
        source_file = getsourcefile(_getframe(1))
        if source_file is None:
            raise ValueError("source_file could not be determined.")
        elif not logger and not db:
            raise ValueError("Either logger or db must be provided.")
        source_path = Path(source_file)
        self.job_path = Path(sep, "var", "cache", "bunkerweb", source_path.parent.parent.name)
        self.job_name = job_name or source_path.name.replace(".py", "")

        self.db = db
        if not self.db:
            from Database import Database  # type: ignore

            self.db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI"))
        self.logger = logger or self.db.logger

        if not deprecated:
            with LOCK:
                is_scheduler_first_start = self.db.is_scheduler_first_start()
            if not is_scheduler_first_start:
                self.restore_cache(manual=False)

    def restore_cache(self, *, job_name: str = "", plugin_id: str = "", manual: bool = True) -> bool:
        """Restore job cache files from database."""
        ret = True
        with LOCK:
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
                    ignored_dirs.add(extract_path.as_posix())
                    if job_cache_file["job_name"] != job_name:
                        continue
                    with LOCK:
                        rmtree(extract_path, ignore_errors=True)
                        extract_path.mkdir(parents=True, exist_ok=True)
                        with tar_open(fileobj=BytesIO(job_cache_file["data"]), mode="r:gz") as tar:
                            try:
                                tar.extractall(extract_path, filter="fully_trusted")
                            except TypeError:
                                tar.extractall(extract_path)
                    continue
                elif job_cache_file["job_name"] != job_name:
                    continue
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(job_cache_file["data"])
            except BaseException as e:
                self.logger.error(f"Exception while restoring cache file {job_cache_file['file_name']} :\n{e}")
                ret = False

        with LOCK:
            if not manual and self.job_path.is_dir():
                for file in self.job_path.rglob("*"):
                    skipped = False
                    if file.as_posix().startswith(tuple(ignored_dirs)):
                        skipped = True
                        break

                    if skipped:
                        continue

                    self.logger.debug(f"Checking if {file} should be removed")
                    if file not in plugin_cache_files and file.is_file():
                        self.logger.debug(f"Removing non-cached file {file}")
                        file.unlink(missing_ok=True)
                        if file.parent.is_dir() and not list(file.parent.iterdir()):
                            self.logger.debug(f"Removing empty directory {file.parent}")
                            rmtree(file.parent, ignore_errors=True)
                            if file.parent == self.job_path:
                                break
                    elif file.is_dir() and not list(file.iterdir()):
                        self.logger.debug(f"Removing empty directory {file}")
                        rmtree(file, ignore_errors=True)

        return ret

    def get_cache(
        self, name: str, *, job_name: str = "", service_id: str = "", plugin_id: str = "", with_info: bool = False, with_data: bool = True
    ) -> Optional[Union[Dict[str, Any], bytes]]:
        """Get cache file from database or from local cache file."""
        cache_path = self.job_path.joinpath(service_id, name)
        ret_data = {}
        if cache_path.is_file():
            if with_data and not with_info:
                return cache_path.read_bytes()
            if with_data:
                ret_data["data"] = cache_path.read_bytes()

        with LOCK:
            if not ret_data:
                return self.db.get_job_cache_file(job_name or self.job_name, name, service_id=service_id, plugin_id=plugin_id or self.job_path.name, with_info=with_info, with_data=with_data)  # type: ignore
            ret_data.update(self.db.get_job_cache_file(job_name or self.job_name, name, service_id=service_id, plugin_id=plugin_id or self.job_path.name, with_info=True, with_data=False))  # type: ignore
        return ret_data

    def is_cached_file(
        self, name: str, expire: Literal["hour", "day", "week", "month"], *, job_name: str = "", service_id: str = "", plugin_id: str = ""
    ) -> bool:
        """Check if cache file is cached and if it's still fresh."""
        is_cached = False
        try:
            cache_info = self.get_cache(name, job_name=job_name, service_id=service_id, plugin_id=plugin_id, with_info=True, with_data=False)
            if isinstance(cache_info, dict):
                current_time = datetime.now().timestamp()
                if current_time < cache_info["last_update"]:
                    return False
                is_cached = current_time - cache_info["last_update"] < EXPIRE_TIME[expire]
        except:
            is_cached = False
        return is_cached

    def cache_file(
        self,
        name: str,
        file_cache: Union[bytes, str, Path],
        *,
        job_name: str = "",
        service_id: str = "",
        checksum: Optional[str] = None,
        delete_file: bool = True,
        overwrite_file: bool = True,
    ) -> Tuple[bool, str]:
        """Cache file in database and in local cache file."""
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
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(content)

        if not checksum:
            checksum = bytes_hash(content)

        try:
            with LOCK:
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

        return self.cache_file(file_name, content.read(), job_name=job_name, service_id=service_id)

    def del_cache(self, name: str, *, job_name: str = "", service_id: str = "") -> Tuple[bool, str]:
        """Delete cache file from database and local cache file."""
        ret, err = True, "success"
        job_name = job_name or self.job_name
        job_path = self.job_path.joinpath(service_id)
        cache_path = job_path.joinpath(name)

        if cache_path.is_file():
            cache_path.unlink(missing_ok=True)

        if job_path.is_dir() and not list(job_path.iterdir()):
            rmtree(job_path, ignore_errors=True)

        try:
            with LOCK:
                self.db.delete_job_cache(name, job_name=job_name, service_id=service_id)  # type: ignore
        except:
            return False, f"exception :\n{format_exc()}"
        return ret, err

    def cache_hash(self, name: str, *, job_name: str = "", service_id: str = "", plugin_id: str = "") -> Optional[str]:
        """Get cache file hash from database or from local cache file."""
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
        return cache["data"]
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
