#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from io import BytesIO
from os import getenv, sep
from os.path import join
from sys import path as sys_path
from tarfile import open as tar_open
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from logger import setup_logger


class ApiCaller:
    def __init__(self, apis: Optional[Union[List[API], set[API]]] = None):
        self.__apis = apis or []
        self.__logger = setup_logger("Api", getenv("LOG_LEVEL", "INFO"))

    @property
    def apis(self) -> Union[List[API], set[API]]:
        return self.__apis.copy()

    @apis.setter
    def apis(self, apis: Union[List[API], set[API]]):
        self.__apis = apis

    def remove(self, api: API):
        self.__apis.remove(api)

    def send_to_apis(
        self,
        method: Union[Literal["POST"], Literal["GET"], Literal["DELETE"]],
        url: str,
        files: Optional[Dict[str, BytesIO]] = None,
        data: Optional[Dict[str, Any]] = None,
        response: bool = False,
    ) -> Tuple[List[API], Optional[Dict[str, Any]]]:
        ret = []
        url = url if not url.startswith("/") else url[1:]
        responses = {}
        for api in self.__apis:
            if files is not None:
                for buffer in files.values():
                    buffer.seek(0, 0)
            sent, err, status, resp = api.request(method, url, files=files, data=data)
            if not sent:
                ret.append(api)
                self.__logger.error(
                    f"Can't send API request to {api.endpoint}{url} : {err}",
                )
            else:
                if status != 200:
                    ret.append(api)
                    msg = "No message"
                    if resp.headers.get("Content-Type", "").startswith("application/json"):
                        resp = resp.json()
                        status = resp["status"]
                        msg = resp["msg"]
                    self.__logger.error(
                        f"Error while sending API request to {api.endpoint}{url} : status = {status}, msg = {msg}",
                    )
                else:
                    self.__logger.info(
                        f"Successfully sent API request to {api.endpoint}{url}",
                    )

                    if response:
                        instance = api.endpoint.split("://", 1).pop().split(":")[0]
                        if isinstance(resp, dict):
                            responses[instance] = resp
                        else:
                            responses[instance] = resp.json()

        return ret, responses

    def send_files(self, path: str, url: str) -> Tuple[List[API], Optional[Dict[str, Any]]]:
        ret = []
        with BytesIO() as tgz:
            with tar_open(mode="w:gz", fileobj=tgz, dereference=True, compresslevel=3) as tf:
                tf.add(path, arcname=".")
            tgz.seek(0, 0)
            files = {"archive.tar.gz": tgz}
            ret = self.send_to_apis("POST", url, files=files, response=True)
        return ret