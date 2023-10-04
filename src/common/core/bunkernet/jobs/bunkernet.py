#!/usr/bin/python3

from os import getenv, sep
from pathlib import Path
from requests import request as requests_request, ReadTimeout
from typing import Literal, Optional, Tuple, Union


def request(method: Union[Literal["POST"], Literal["GET"]], url: str, _id: Optional[str] = None) -> Tuple[bool, Optional[int], Union[str, dict]]:
    data = {"integration": get_integration(), "version": get_version()}
    headers = {"User-Agent": f"BunkerWeb/{get_version()}"}
    if _id is not None:
        data["id"] = _id
    try:
        resp = requests_request(
            method,
            f"{getenv('BUNKERNET_SERVER', 'https://api.bunkerweb.io')}{url}",
            json=data,
            headers=headers,
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


def ping(_id: Optional[str]) -> Tuple[bool, Optional[int], Union[str, dict]]:
    return request("GET", "/ping", _id=_id)


def data(_id: Optional[str]) -> Tuple[bool, Optional[int], Union[str, dict]]:
    return request("GET", "/db", _id=_id)


def get_version() -> str:
    return Path(sep, "usr", "share", "bunkerweb", "VERSION").read_text(encoding="utf-8").strip()


def get_integration() -> str:
    try:
        integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
        os_release_path = Path(sep, "etc", "os-release")
        if getenv("KUBERNETES_MODE", "no").lower() == "yes":
            return "kubernetes"
        elif getenv("SWARM_MODE", "no").lower() == "yes":
            return "swarm"
        elif getenv("AUTOCONF_MODE", "no").lower() == "yes":
            return "autoconf"
        elif integration_path.is_file():
            return integration_path.read_text(encoding="utf-8").strip().lower()
        elif os_release_path.is_file() and "Alpine" in os_release_path.read_text(encoding="utf-8"):
            return "docker"

        return "linux"
    except:
        return "unknown"
