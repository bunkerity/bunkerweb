#!/usr/bin/env python3

from base64 import b64encode
from io import BytesIO
from os.path import join
from typing import List, Optional

from qrcode.main import QRCode

import math


def get_remain(remain_time):
    # Convert s to ms
    ms = int(str(remain_time) + "000")

    seconds = math.floor(ms / 1000)
    minutes = math.floor(seconds / 60)
    hours = math.floor(minutes / 60)
    days = math.floor(hours / 24)
    months = math.floor(days / 30)
    years = math.floor(days / 365)
    seconds %= 60
    minutes %= 60
    hours %= 24
    days %= 30
    months %= 12

    remain = f'{format_remain(years, "year")} {format_remain(months, "month")} {format_remain(days, "day")} {format_remain(hours, "hour")} {format_remain(minutes, "minute")} {format_remain(seconds, "second")}'
    return remain


def format_remain(num, singular):
    if not num:
        return ""

    if num == 1:
        return f"{num} {singular}"

    if num > 1:
        return f"{num} {singular}s"


def get_range_from_remain(remain):
    # Not handle
    if remain == "unknown":
        return remain

    # Data, need format <n>y <n>m <n>d <n>h <n>min <n>s
    split_remain = remain.split(" ")
    terms = [num for num in split_remain if num.isdigit()]
    term = ""
    formats = ["year(s)", "month(s)", "day(s)", "hour(s)", "minute(s)", "second(s)"]
    chars = ["year", "month", "day", "hour", "second", "s"]

    # start from seconds to years, stop when first 0 occurrence
    # The remain term is first 0 occurrence - 1
    for i in range(len(terms)):
        # remove letter
        num = terms[len(terms) - 1 - i]
        for char in chars:
            num = num.replace(char, "")
            num = "0" if not num else num

        num = int(num)

        # Case seconds or less
        if not num and i == 0:
            term = formats[len(formats) - 1]
            break

        # Case last element
        if num and i == (len(terms) - 1):
            term = formats[len(formats) - 1 - i]
            break

        # Case between seconds and years
        if not num:
            term = formats[len(formats) - i]
            break

    return term


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
                d["children"][config_types.index(type_lower)]["children"][[x["name"] for x in d["children"][config_types.index(type_lower)]["children"]].index(conf["service_id"])]["children"].append(file_info)
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
            "children": [
                {
                    "name": service,
                    "type": "folder",
                    "path": join(path, service),
                    "can_create_files": False,
                    "can_create_folders": False,
                    "can_edit": False,
                    "can_delete": False,
                    "children": [],
                }
                for service in services
            ],
        }

        for conf in db_data:
            file_info = {
                "name": join(conf["job_name"], conf["file_name"]),
                "type": "file",
                "path": join(
                    path,
                    conf["service_id"] or "",
                    conf["file_name"],
                ),
                "can_edit": False,
                "can_delete": False,
                "can_download": True,
                "content": conf["data"],
            }

            if conf["service_id"]:
                d["children"][[x["name"] for x in d["children"]].index(conf["service_id"])]["children"].append(file_info)
            else:
                d["children"].append(file_info)

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
