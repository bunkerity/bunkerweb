#!/usr/bin/env python3

from os import getenv, sep
from pathlib import Path
from requests import request as requests_request, ReadTimeout
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from common_utils import get_os_info, get_integration, get_version  # type: ignore


def request(
    method: Literal["POST", "GET"], url: str, _id: Optional[str] = None, *, additional_data: Dict[str, Any] = None
) -> Tuple[bool, Optional[int], Union[str, dict]]:
    data = {
        "integration": get_integration(),
        "version": get_version(),
        "os": get_os_info(),
    }
    if _id:
        data["id"] = _id
    if additional_data:
        data.update(additional_data)

    try:
        resp = requests_request(
            method,
            f"{getenv('BUNKERNET_SERVER', 'https://api.bunkerweb.io')}{url}",
            json=data,
            headers={"User-Agent": f"BunkerWeb/{data['version']}"},
            timeout=5,
        )
        status = resp.status_code
        if status == 429:
            return True, 429, "rate limited"
        elif status == 403:
            return True, 403, "forbidden"

        raw_data: dict = resp.json()

        assert "result" in raw_data
        assert "data" in raw_data
    except ReadTimeout:
        return False, None, "request timed out"
    except Exception as e:
        return False, None, f"request failed: {e}"
    return True, status, raw_data


def register() -> Tuple[bool, Optional[int], Union[str, dict]]:
    return request("POST", "/register")


def ping(_id: Optional[str] = None) -> Tuple[bool, Optional[int], Union[str, dict]]:
    return request("GET", "/ping", _id=_id or get_id())


def data() -> Tuple[bool, Optional[int], Union[str, dict]]:
    return request("GET", "/db", _id=get_id())


def send_reports(reports: List[Dict[str, Any]]) -> Tuple[bool, Optional[int], Union[str, dict]]:
    return request("POST", "/report", _id=get_id(), additional_data={"reports": reports})


def get_id() -> str:
    return Path(sep, "var", "cache", "bunkerweb", "bunkernet", "instance.id").read_text(encoding="utf-8").strip()
