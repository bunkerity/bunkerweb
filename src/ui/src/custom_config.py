#!/usr/bin/env python3

from os import sep
from os.path import join
from pathlib import Path
from re import compile as re_compile

from utils import path_to_dict


class CustomConfig:
    def __init__(self):
        self.__name_regex = re_compile(r"^[\w.-]{4,64}$")
        self.__root_dirs = [child["name"] for child in path_to_dict(join(sep, "etc", "bunkerweb", "configs"))["children"]]
        self.__file_creation_blacklist = ["http", "stream"]

    def check_name(self, name: str) -> bool:
        return self.__name_regex.match(name) is not None

    def check_path(self, path: str, root_path: str = join(sep, "etc", "bunkerweb", "configs")) -> str:
        root_dir: str = path.split("/")[4]
        if not (
            path.startswith(root_path)
            or root_path == join(sep, "etc", "bunkerweb", "configs")
            and path.startswith(root_path)
            and root_dir in self.__root_dirs
            and (not path.endswith(".conf") or root_dir not in self.__file_creation_blacklist or len(path.split("/")) > 5)
        ):
            return f"{path} is not a valid path"

        if root_path == join(sep, "etc", "bunkerweb", "configs"):
            dirs = path.split("/")[5:]
            nbr_children = len(dirs)
            dirs = "/".join(dirs)
            if len(dirs) > 1:
                for x in range(nbr_children - 1):
                    if not Path(root_path, root_dir, "/".join(dirs.split("/")[0:-x])).exists():
                        return f"{join(root_path, root_dir, '/'.join(dirs.split('/')[0:-x]))} doesn't exist"

        return ""
