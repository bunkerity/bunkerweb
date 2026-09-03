#!/usr/bin/env python3

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from inspect import signature
from gzip import GzipFile
from io import BytesIO
from os import sep
from os.path import join, realpath
from sys import path as sys_path
from tarfile import open as tar_open
from time import sleep
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from urllib.parse import urlsplit

# Update system path for dependencies
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from logger import getLogger

# Ceiling for the body-write budget a folder push derives from its read budget. The read budget is
# deliberately uncapped when an operator raises the floor, but the write budget is added to it on the
# wire, and the scheduler joins five folder pushes on its own loop thread: an uncapped body budget
# multiplies the worst case that loop can be blocked for. A caller that knows better passes its own.
WRITE_TIMEOUT_CAP = 120

# An instance serialises its push swaps and reloads on one lock and answers 503 while it is held, so
# a 503 means healthy but busy, not broken. Two reloads reaching the same instance at once is normal
# (the main loop after a change, plus a job that asks for a reload), and a config test on a CRS-heavy
# configuration outlasts the lock wait, so the loser has to try again rather than be marked down and
# evicted. A dead instance answers with a connection error instead, so this delays nothing real.
BUSY_STATUS = 503
BUSY_ATTEMPTS = 3
BUSY_RETRY_DELAY = 2


def _accepts_write_timeout(api) -> bool:
    """Whether this API client's request() takes a write_timeout, checked rather than assumed.

    A client that takes arbitrary keywords counts: it forwards what it is given.
    """
    try:
        params = signature(api.request).parameters
    except (AttributeError, TypeError, ValueError):
        return False
    return "write_timeout" in params or any(param.kind is param.VAR_KEYWORD for param in params.values())


def folder_push_timeout(min_timeout: int, service_count: int) -> Tuple[int, int]:
    """Connect and read budgets for a folder upload.

    The read budget grows with the number of services, because that is what makes the archive big,
    and only that derived value is capped: the scheduler healthcheck submits five folder pushes into
    a four-worker pool and blocks its loop on the results, so an unbounded one stalls the loop for
    two waves. An explicit SEND_FILES_MIN_TIMEOUT is operator intent and is not subject to the cap,
    otherwise the documented minimum silently hands back less than what was configured. The connect
    budget stays short so a host that never answers still fails fast.
    """
    return (5, max(min_timeout, min(120, max(1, 3 * service_count))))


class ApiCaller:
    def __init__(self, apis: Optional[List[API]] = None):
        self.apis = apis or []
        self.__logger = getLogger("API.CALLER")

    def send_to_apis(
        self,
        method: Union[Literal["POST"], Literal["GET"]],
        url: str,
        files: Optional[Dict[str, BytesIO]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout=(5, 10),
        response: bool = False,
        write_timeout: Optional[int] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        def send_request(api, files):
            # Left out unless the client actually takes it, so an API client without the argument
            # keeps working instead of raising TypeError, which send_to_apis would swallow into a
            # failed send and turn into "every instance is down". The socket then carries the connect
            # budget through the body write, which is the behaviour that predates the argument.
            extra = {"write_timeout": write_timeout} if write_timeout is not None and _accepts_write_timeout(api) else {}

            for attempt in range(1, BUSY_ATTEMPTS + 1):
                if attempt > 1:
                    sleep(BUSY_RETRY_DELAY)
                    # Defence in depth rather than a live fix: API.request currently deepcopies the
                    # files before sending, so the previous attempt consumed a copy and left these at
                    # zero. Drop that copy, which is the obvious thing to do for a multi-MB archive,
                    # and without this the retry uploads an empty body.
                    for buffer in (files or {}).values():
                        buffer.seek(0)

                sent, err, status, resp = api.request(method, url, files=files, data=data, timeout=timeout, **extra)

                if status != BUSY_STATUS or attempt == BUSY_ATTEMPTS:
                    return api, sent, err, status, resp

                self.__logger.warning(
                    f"{api.endpoint}{url} answered {BUSY_STATUS}, the instance is busy applying another change: "
                    f"retrying in {BUSY_RETRY_DELAY}s (attempt {attempt}/{BUSY_ATTEMPTS}) ..."
                )

        ret = True
        url = url.lstrip("/")
        responses = {} if response else None

        if files:
            for buffer in files.values():
                buffer.seek(0, 0)  # Ensure the file pointer is at the beginning

        with ThreadPoolExecutor() as executor:
            future_to_api = {executor.submit(send_request, api, deepcopy(files) if files else None): api for api in self.apis}
            for future in as_completed(future_to_api):
                try:
                    api, sent, err, status, resp = future.result()
                    if not sent:
                        ret = False
                        self.__logger.error(f"Can't send API request to {api.endpoint}{url} : {err}")
                    else:
                        if status != 200:
                            ret = False
                            self.__logger.error(f"Error while sending API request to {api.endpoint}{url} : status = {status}, msg = {resp.get('msg')}")
                        else:
                            self.__logger.info(f"Successfully sent API request to {api.endpoint}{url}")

                        if resp and response:
                            # Extract hostname from endpoint (supports http and https)
                            try:
                                host = urlsplit(api.endpoint).hostname or api.endpoint
                            except Exception:
                                host = api.endpoint.replace("http://", "").replace("https://", "").split(":")[0]
                            if responses is not None:
                                responses[host] = resp if isinstance(resp, dict) else resp.json()
                except Exception as exc:
                    ret = False
                    self.__logger.error(f"API request generated an exception: {exc}")

        return ret, responses

    @staticmethod
    def _build_archive(path: str) -> BytesIO:
        """Build a gzip tar whose bytes depend only on file names and contents.

        Member metadata and the gzip header timestamp are normalized, so sending an
        unchanged directory twice produces the same bytes. Instances compare that
        digest to skip a push that would change nothing, which matters because the
        scheduler sends these directories on every start whether or not they changed.
        Mirrors create_plugin_tar_gz, which normalizes for the same reason.
        """

        def normalize(tarinfo):
            tarinfo.mtime = 0
            tarinfo.uid = 0
            tarinfo.gid = 0
            tarinfo.uname = "root"
            tarinfo.gname = "root"
            return tarinfo

        with BytesIO() as raw:
            with tar_open(fileobj=raw, mode="w") as tar:
                # top-level path may itself be a symlink (resolve it); nested symlinks must stay symlinks (no dereference)
                tar.add(realpath(path), arcname=".", filter=normalize)
            raw_bytes = raw.getvalue()

        result = BytesIO()
        with GzipFile(fileobj=result, mode="wb", compresslevel=3, mtime=0) as gz:
            gz.write(raw_bytes)
        result.seek(0)
        return result

    def send_files(
        self, path: str, url: str, timeout=(5, 30), response: bool = False, write_timeout: Optional[int] = None
    ) -> Union[bool, Tuple[bool, Optional[Dict[str, Any]]]]:
        """Upload a directory as one archive.

        write_timeout is the budget for writing the archive body. It is separate from the timeout
        tuple because the socket carries the connect budget until the body has been written, so a
        large archive over a backpressured link fails on the connect budget however large the read
        budget is. It defaults to the read budget, which is the one already sized for this archive:
        every folder push wants the body to get the time the caller asked for, and the connect
        component stays short so a host that never answers still fails fast.
        """
        if write_timeout is None:
            read_timeout = timeout[1] if isinstance(timeout, (tuple, list)) else timeout
            write_timeout = min(WRITE_TIMEOUT_CAP, read_timeout)

        with self._build_archive(path) as tgz:
            files = {"archive.tar.gz": tgz}
            ret = self.send_to_apis("POST", url, files=files, timeout=timeout, response=response, write_timeout=write_timeout)
            if response:
                return ret[0], ret[1]
            return ret[0]
