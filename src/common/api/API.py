#!/usr/bin/python3
# -*- coding: utf-8 -*-

from typing import Literal, Optional, Union
from requests import Response, request


class API:
    def __init__(self, endpoint: str, host: str = "bwapi"):
        self.__endpoint = endpoint
        if not self.__endpoint.startswith("http"):
            self.__endpoint = f"http://{self.__endpoint}"
        if not self.__endpoint.endswith("/"):
            self.__endpoint += "/"
        self.__host = host

    @property
    def endpoint(self) -> str:
        return self.__endpoint

    @property
    def host(self) -> str:
        return self.__host

    def request(
        self,
        method: Literal["POST", "GET", "PATCH", "PUT", "DELETE"],
        url: str,
        data: Optional[Union[dict, bytes]] = None,
        files=None,
        *,
        additonal_headers: Optional[dict] = None,
        timeout=(10, 30),
    ) -> tuple[bool, str, Optional[int], Optional[Response]]:
        additonal_headers = additonal_headers or {}
        try:
            kwargs = {}
            if data is not None:
                if isinstance(data, dict) and not files:
                    kwargs["json"] = data
                elif isinstance(data, (bytes, dict)):
                    kwargs["data"] = data
                else:
                    return False, f"Unsupported data type: {type(data)}", None, None

            if files:
                kwargs["files"] = files

            resp = request(
                method,
                f"{self.__endpoint}{url if not url.startswith('/') else url[1:]}",
                timeout=timeout,
                headers={"User-Agent": "bwapi", "Host": self.__host} | additonal_headers,
                **kwargs,
            )
        except Exception as e:
            return False, f"Request failed: {e}", None, None

        return True, "ok", resp.status_code, resp
