from typing import Literal, Optional, Tuple, Union
import requests
from os import getenv
from os.path import exists


def request(
    method: Union[Literal["POST"], Literal["GET"]], url: str, _id: Optional[str] = None
) -> Tuple[bool, Optional[int], Union[str, dict]]:
    data = {"integration": get_integration(), "version": get_version()}
    headers = {"User-Agent": f"BunkerWeb/{get_version()}"}
    if _id is not None:
        data["id"] = _id
    try:
        resp = requests.request(
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
    except requests.ReadTimeout:
        return False, None, "request timed out"
    except Exception as e:
        return False, None, f"request failed: {e}"
    return True, status, raw_data


def register():
    return request("POST", "/register")


def ping(_id=None):
    return request("GET", "/ping", _id=get_id() if _id is None else _id)


def data():
    return request("GET", "/db", _id=get_id())


def get_id():
    with open("/var/cache/bunkerweb/bunkernet/instance.id", "r") as f:
        return f.read().strip()


def get_version():
    with open("/usr/share/bunkerweb/VERSION", "r") as f:
        return f.read().strip()


def get_integration():
    try:
        if getenv("AUTOCONF_MODE") == "yes":
            return "autoconf"
        if getenv("SWARM_MODE") == "yes":
            return "swarm"
        elif getenv("KUBERNETES_MODE") == "yes":
            return "kubernetes"
        elif exists("/usr/share/bunkerweb/INTEGRATION"):
            with open("/usr/share/bunkerweb/INTEGRATION", "r") as f:
                return f.read().strip().lower()

        return "linux"
    except:
        return "unknown"
