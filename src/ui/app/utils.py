#!/usr/bin/env python3

from os import _exit, getenv
from os.path import join, sep
from pathlib import Path
from subprocess import PIPE, Popen, call
from typing import List, Optional

from bcrypt import checkpw, gensalt, hashpw
from magic import Magic
from regex import compile as re_compile
from requests import get

from logger import setup_logger  # type: ignore

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")

LOGGER = setup_logger("UI", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))

USER_PASSWORD_RX = re_compile(r"^(?=.*?\p{Lowercase_Letter})(?=.*?\p{Uppercase_Letter})(?=.*?\d)(?=.*?[ !\"#$%&'()*+,./:;<=>?@[\\\]^_`{|}~-]).{8,}$")
PLUGIN_NAME_RX = re_compile(r"^[\w.-]{4,64}$")


def stop_gunicorn():
    p = Popen(["pgrep", "-f", "gunicorn"], stdout=PIPE)
    out, _ = p.communicate()
    pid = out.strip().decode().split("\n")[0]
    call(["kill", "-SIGTERM", pid])


def stop(status, _stop=True):
    Path(sep, "var", "run", "bunkerweb", "ui.pid").unlink(missing_ok=True)
    TMP_DIR.joinpath("ui.healthy").unlink(missing_ok=True)
    if _stop is True:
        stop_gunicorn()
    _exit(status)


def handle_stop(signum, frame):
    LOGGER.info("Caught stop operation")
    LOGGER.info("Stopping web ui ...")
    stop(0, False)


def check_settings(settings: dict, check: str) -> bool:
    return any(setting["context"] == check for setting in settings.values())


def gen_password_hash(password: str) -> bytes:
    return hashpw(password.encode("utf-8"), gensalt(rounds=13))


def check_password(password: str, hashed: bytes) -> bool:
    return checkpw(password.encode("utf-8"), hashed)


SHOWN_FILE_TYPES = ("text/plain", "text/html", "text/css", "text/javascript", "application/json", "application/xml")


def path_to_dict(
    path: str,
    *,
    is_cache: bool = False,
    db_data: Optional[List[dict]] = None,
    services: Optional[List[dict]] = None,
) -> dict:
    db_data = db_data or []
    services = services or []

    if not is_cache:
        config_types = (
            "http",
            "stream",
            "server-http",
            "server-stream",
            "default-server-http",
            "default-server-stream",
            "modsec",
            "modsec-crs",
            "crs-plugins-before",
            "crs-plugins-after",
        )

        d = {
            "name": "configs",
            "type": "folder",
            "path": path,
            "can_create_files": False,
            "can_create_folders": False,
            "can_edit": False,
            "can_delete": False,
            "children": [
                {
                    "name": config,
                    "type": "folder",
                    "path": join(path, config),
                    "can_create_files": True,
                    "can_create_folders": False,
                    "can_edit": False,
                    "can_delete": False,
                    "children": [
                        {
                            "name": service,
                            "type": "folder",
                            "path": join(path, config, service),
                            "can_create_files": True,
                            "can_create_folders": False,
                            "can_edit": False,
                            "can_delete": False,
                            "children": [],
                        }
                        for service in services
                    ],
                }
                for config in config_types
            ],
        }

        for conf in db_data:
            type_lower = conf["type"].replace("_", "-")
            file_info = {
                "name": f"{conf['name']}.conf",
                "type": "file",
                "path": join(
                    path,
                    type_lower,
                    conf["service_id"] or "",
                    f"{conf['name']}.conf",
                ),
                "can_edit": conf["method"] == "ui",
                "can_delete": True,
                "can_download": True,
                "content": conf["data"].decode("utf-8"),
            }

            if conf["service_id"]:
                d["children"][config_types.index(type_lower)]["children"][
                    [x["name"] for x in d["children"][config_types.index(type_lower)]["children"]].index(conf["service_id"])
                ]["children"].append(file_info)
            else:
                d["children"][config_types.index(type_lower)]["children"].append(file_info)
    else:
        d = {
            "name": "cache",
            "type": "folder",
            "path": path,
            "can_create_files": False,
            "can_create_folders": False,
            "can_edit": False,
            "can_delete": False,
            "children": [],
        }

        plugins = []
        paths = []
        for conf in db_data:
            if conf["plugin_id"] not in plugins:
                d["children"].append(
                    {
                        "name": conf["plugin_id"],
                        "type": "folder",
                        "path": join(path, conf["plugin_id"]),
                        "can_create_files": True,
                        "can_create_folders": False,
                        "can_edit": False,
                        "can_delete": False,
                        "children": [],
                    }
                )
                plugins.append(conf["plugin_id"])
                paths.append(join(path, conf["plugin_id"]))

            mime = Magic(mime=True)
            file_type = mime.from_buffer(conf["data"])

            file_info = {
                "name": conf["file_name"],
                "job_name": conf["job_name"],
                "type": "file",
                "path": join(
                    path,
                    conf["plugin_id"],
                    conf["service_id"] or "",
                    conf["file_name"],
                ),
                "can_edit": False,
                "can_delete": False,
                "can_download": True,
                "content": conf["data"].decode("utf-8") if file_type in SHOWN_FILE_TYPES else "Download file to view content",
            }

            if conf["service_id"]:
                if join(conf["plugin_id"], conf["service_id"]) not in paths:
                    d["children"][[x["name"] for x in d["children"]].index(conf["plugin_id"])]["children"].append(
                        {
                            "name": conf["service_id"],
                            "type": "folder",
                            "path": join(path, conf["plugin_id"], conf["service_id"]),
                            "can_create_files": True,
                            "can_create_folders": False,
                            "can_edit": False,
                            "can_delete": False,
                            "children": [],
                        }
                    )
                    paths.append(join(conf["plugin_id"], conf["service_id"]))

                data_plugin = d["children"][[x["name"] for x in d["children"]].index(conf["plugin_id"])]
                data_plugin["children"][[x["name"] for x in data_plugin["children"]].index(conf["service_id"])]["children"].append(file_info)
            else:
                d["children"][[x["name"] for x in d["children"]].index(conf["plugin_id"])]["children"].append(file_info)

    return d


def get_latest_stable_release():
    response = get("https://api.github.com/repos/bunkerity/bunkerweb/releases", headers={"User-Agent": "BunkerWeb"}, timeout=3)
    response.raise_for_status()
    releases = response.json()

    for release in releases:
        if not release["prerelease"]:
            return release
    return None
