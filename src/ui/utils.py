#!/usr/bin/env python3

from base64 import b64encode
from io import BytesIO
from os.path import join
from typing import List, Optional

from magic import Magic
from qrcode.main import QRCode


def get_remain(seconds):
    term = "minute(s)"
    years, seconds = divmod(seconds, 60 * 60 * 24 * 365)
    months, seconds = divmod(seconds, 60 * 60 * 24 * 30)
    while months >= 12:
        years += 1
        months -= 12
    days, seconds = divmod(seconds, 60 * 60 * 24)
    hours, seconds = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(seconds, 60)
    time_parts = []
    if years > 0:
        term = "year(s)"
        time_parts.append(f"{int(years)} year{'' if years == 1 else 's'}")
    if months > 0:
        if term == "minute(s)":
            term = "month(s)"
        time_parts.append(f"{int(months)} month{'' if months == 1 else 's'}")
    if days > 0:
        if term == "minute(s)":
            term = "day(s)"
        time_parts.append(f"{int(days)} day{'' if days == 1 else 's'}")
    if hours > 0:
        if term == "minute(s)":
            term = "hour(s)"
        time_parts.append(f"{int(hours)} hour{'' if hours == 1 else 's'}")
    if minutes > 0:
        time_parts.append(f"{int(minutes)} minute{'' if minutes == 1 else 's'}")

    if len(time_parts) > 1:
        time_parts[-1] = f"and {time_parts[-1]}"

    return " ".join(time_parts), term


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
        config_types = [
            "http",
            "stream",
            "server-http",
            "server-stream",
            "default-server-http",
            "modsec",
            "modsec-crs",
        ]

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


def check_settings(settings: dict, check: str) -> bool:
    return any(setting["context"] == check for setting in settings.values())


def get_b64encoded_qr_image(data: str):
    qr = QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0b5577", back_color="white")
    buffered = BytesIO()
    img.save(buffered)
    return b64encode(buffered.getvalue()).decode("utf-8")
