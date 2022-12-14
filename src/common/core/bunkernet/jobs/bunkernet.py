import requests, traceback
from os import getenv


def request(method, url, _id=None):
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
        raw_data = resp.json()
        assert "result" in raw_data
        assert "data" in raw_data
    except Exception as e:
        return False, None, traceback.format_exc()
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
        if getenv("KUBERNETES_MODE") == "yes":
            return "kubernetes"
        if getenv("SWARM_MODE") == "yes":
            return "swarm"
        with open("/etc/os-release", "r") as f:
            if f.read().contains("Alpine"):
                return "docker"
        return "linux"
    except:
        return "unknown"
