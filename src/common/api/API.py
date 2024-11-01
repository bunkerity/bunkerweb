#!/usr/bin/env python3

from os import environ
from typing import Literal, Optional, Union
from requests import request


class API:
    def __init__(self, endpoint: str, host: str = "bwapi"):
        self.__endpoint = endpoint
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
        method: Union[Literal["POST"], Literal["GET"]],
        url: str,
        data: Optional[Union[dict, bytes]] = None,
        files=None,
        timeout=(int(environ.get('API_TIMEOUT', 10)), 
                 int(environ.get('API_READ_TIMEOUT', 30))),
    ) -> tuple[bool, str, Optional[int], Optional[dict]]:
        try:
            kwargs = {}
            if isinstance(data, dict):
                kwargs["json"] = data
            elif isinstance(data, bytes):
                kwargs["data"] = data
            elif data is not None:
                return False, f"Unsupported data type: {type(data)}", None, None

            if files:
                kwargs["files"] = files

            resp = request(
                method,
                f"{self.__endpoint}{url if not url.startswith('/') else url[1:]}",
                timeout=timeout,
                headers={"User-Agent": "bwapi", "Host": self.__host},
                **kwargs,
            )
        except Exception as e:
            return False, f"Request failed: {e}", None, None

        return True, "ok", resp.status_code, resp.json()
