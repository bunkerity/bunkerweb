#!/usr/bin/env python3

from io import BytesIO
from os import getenv, sep
from os.path import join
from sys import path as sys_path
from tarfile import open as tar_open
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from logger import setup_logger


class ApiCaller:
    def __init__(self, apis: Optional[List[API]] = None):
        self.apis = apis or []
        self.__logger = setup_logger("Api", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))

    def send_to_apis(
        self,
        method: Union[Literal["POST"], Literal["GET"]],
        url: str,
        files: Optional[Dict[str, BytesIO]] = None,
        data: Optional[Dict[str, Any]] = None,
        response: bool = False,
    ) -> Tuple[bool, Tuple[bool, Optional[Dict[str, Any]]]]:
        ret = True
        url = url if not url.startswith("/") else url[1:]
        responses = {}
        for api in self.apis:
            if files is not None:
                for buffer in files.values():
                    buffer.seek(0, 0)
            sent, err, status, resp = api.request(method, url, files=files, data=data)
            if not sent:
                ret = False
                self.__logger.error(
                    f"Can't send API request to {api.endpoint}{url} : {err}",
                )
            else:
                if status != 200:
                    ret = False
                    self.__logger.error(
                        f"Error while sending API request to {api.endpoint}{url} : status = {resp['status']}, msg = {resp['msg']}",
                    )
                else:
                    self.__logger.info(
                        f"Successfully sent API request to {api.endpoint}{url}",
                    )

                    if response:
                        instance = api.endpoint.replace("http://", "").split(":")[0]
                        if isinstance(resp, dict):
                            responses[instance] = resp
                        else:
                            responses[instance] = resp.json()

        if response:
            return ret, responses
        return ret

    def send_files(self, path: str, url: str) -> bool:
        ret = True
        with BytesIO() as tgz:
            with tar_open(mode="w:gz", fileobj=tgz, dereference=True, compresslevel=3) as tf:
                tf.add(path, arcname=".")
            tgz.seek(0, 0)
            files = {"archive.tar.gz": tgz}
            if not self.send_to_apis("POST", url, files=files):
                ret = False
        return ret
