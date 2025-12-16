#!/usr/bin/env python3

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from io import BytesIO
from os import sep
from os.path import join
from sys import path as sys_path
from tarfile import open as tar_open
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from urllib.parse import urlsplit

# Update system path for dependencies
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from logger import getLogger


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
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        def send_request(api, files):
            sent, err, status, resp = api.request(method, url, files=files, data=data, timeout=timeout)
            return api, sent, err, status, resp

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

    def send_files(self, path: str, url: str, timeout=(5, 10), response: bool = False) -> Union[bool, Tuple[bool, Optional[Dict[str, Any]]]]:
        with BytesIO() as tgz:
            with tar_open(mode="w:gz", fileobj=tgz, dereference=True, compresslevel=3) as tf:
                tf.add(path, arcname=".")
            tgz.seek(0, 0)
            files = {"archive.tar.gz": tgz}
            ret = self.send_to_apis("POST", url, files=files, timeout=timeout, response=response)
            if response:
                return ret[0], ret[1]
            return ret[0]
