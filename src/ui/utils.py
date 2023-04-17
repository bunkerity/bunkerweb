from typing import List
import os


def get_variables():
    vars = {}
    vars["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    vars["ABSOLUTE_URI"] = ""
    vars["FLASK_SECRET"] = os.urandom(32)
    vars["FLASK_ENV"] = "development"
    vars["ADMIN_USERNAME"] = "admin"
    vars["ADMIN_PASSWORD"] = "changeme"

    for k in vars:
        if k in os.environ:
            vars[k] = os.environ[k]

    return vars


def path_to_dict(
    path,
    *,
    is_cache: bool = False,
    db_data: List[dict] = [],
    services: List[str] = [],
) -> dict:
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
                    "path": f"{path}/{config}",
                    "can_create_files": True,
                    "can_create_folders": False,
                    "can_edit": False,
                    "can_delete": False,
                    "children": [
                        {
                            "name": service,
                            "type": "folder",
                            "path": f"{path}/{config}/{service}",
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
                "path": f"{path}/{type_lower}{'/' + conf['service_id'] if conf['service_id'] else ''}/{conf['name']}.conf",
                "can_edit": conf["method"] == "ui",
                "can_delete": True,
                "can_download": True,
                "content": conf["data"].decode("utf-8"),
            }

            if conf["service_id"]:
                d["children"][config_types.index(type_lower)]["children"][
                    [
                        x["name"]
                        for x in d["children"][config_types.index(type_lower)][
                            "children"
                        ]
                    ].index(conf["service_id"])
                ]["children"].append(file_info)
            else:
                d["children"][config_types.index(type_lower)]["children"].append(
                    file_info
                )
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
                    "path": f"{path}/{service}",
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
                "name": f"{conf['job_name']}/{conf['file_name']}",
                "type": "file",
                "path": f"{path}{'/' + conf['service_id'] if conf['service_id'] else ''}/{conf['file_name']}",
                "can_edit": False,
                "can_delete": False,
                "can_download": True,
                "content": conf["data"],
            }

            if conf["service_id"]:
                d["children"][
                    [x["name"] for x in d["children"]].index(conf["service_id"])
                ]["children"].append(file_info)
            else:
                d["children"].append(file_info)

    return d


def check_settings(settings: dict, check: str) -> bool:
    return any(setting["context"] == check for setting in settings.values())
