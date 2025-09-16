#!/usr/bin/env python3

from typing import Literal, Optional, Union
from os import getenv
from requests import request


class API:
    def __init__(self, endpoint: str, host: str = "bwapi", token: Optional[str] = None):
        self.__endpoint = endpoint
        if not self.__endpoint.endswith("/"):
            self.__endpoint += "/"
        self.__host = host
        # Optional API token: if not provided, fallback to env var
        self.__token = token if token is not None else getenv("API_TOKEN")

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
        timeout=(5, 10),
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

            headers = {"User-Agent": "bwapi", "Host": self.__host}
            # Add Authorization header if a token is set
            if self.__token:
                headers["Authorization"] = f"Bearer {self.__token}"

            resp = request(
                method,
                f"{self.__endpoint}{url if not url.startswith('/') else url[1:]}",
                timeout=timeout,
                headers=headers,
                **kwargs,
            )
        except Exception as e:
            return False, f"Request failed: {e}", None, None

        return True, "ok", resp.status_code, resp.json()
