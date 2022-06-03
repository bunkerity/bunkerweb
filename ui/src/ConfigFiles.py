import os
from re import compile as re_compile
from shutil import rmtree, move as shutil_move
from typing import Tuple

from ui.utils import path_to_dict


class ConfigFiles:
    def __init__(self):
        self.__name_regex = re_compile(r"^[a-zA-Z0-9_-]{1,64}$")
        self.__root_dirs = [
            child["name"]
            for child in path_to_dict("/opt/bunkerweb/configs")["children"]
        ]
        self.__file_creation_blacklist = ["http", "stream"]

    def check_name(self, name: str) -> bool:
        return self.__name_regex.match(name)

    def check_path(self, path: str, root_path: str = "/opt/bunkerweb/configs/") -> str:
        root_dir: str = path.split("/")[4]
        if not (
            path.startswith(root_path)
            or root_path == "/opt/bunkerweb/configs/"
            and path.startswith(root_path)
            and root_dir in self.__root_dirs
            and (
                not path.endswith(".conf")
                or root_dir not in self.__file_creation_blacklist
                or len(path.split("/")) > 5
            )
        ):
            return f"{path} is not a valid path"

        if root_path == "/opt/bunkerweb/configs/":
            dirs = path.split("/")[5:]
            nbr_children = len(dirs)
            dirs = "/".join(dirs)
            if len(dirs) > 1:
                for x in range(nbr_children - 1):
                    if not os.path.exists(
                        f"{root_path}{root_dir}/{'/'.join(dirs.split('/')[0:-x])}"
                    ):
                        return f"{root_path}{root_dir}/{'/'.join(dirs.split('/')[0:-x])} doesn't exist"

        return ""

    def delete_path(self, path: str) -> Tuple[str, int]:
        try:
            if os.path.isfile(path):
                os.remove(path)
            else:
                rmtree(path)
        except OSError:
            return f"Could not delete {path}", 1

        return f"{path} was successfully deleted", 0

    def create_folder(self, path: str, name: str) -> Tuple[str, int]:
        folder_path = os.path.join(path, name)
        try:
            os.mkdir(folder_path)
        except OSError:
            return f"Could not create {folder_path}", 1

        return f"The folder {folder_path} was successfully created", 0

    def create_file(self, path: str, name: str, content: str) -> Tuple[str, int]:
        file_path = os.path.join(path, name)
        with open(file_path, "w") as f:
            f.write(content)

        return f"The file {file_path} was successfully created", 0

    def edit_folder(self, path: str, name: str) -> Tuple[str, int]:
        new_folder_path = os.path.dirname(os.path.join(path, name))

        if path == new_folder_path:
            return (
                f"{path} was not renamed because the name didn't change",
                0,
            )

        try:
            shutil_move(path, new_folder_path)
        except OSError:
            return f"Could not move {path}", 1

        return f"The folder {path} was successfully renamed to {new_folder_path}", 0

    def edit_file(self, path: str, name: str, content: str) -> Tuple[str, int]:
        new_path = os.path.dirname(os.path.join(path, name))
        try:
            with open(path, "r") as f:
                file_content = f.read()
        except FileNotFoundError:
            return f"Could not find {path}", 1

        if path == new_path and file_content == content:
            return (
                f"{path} was not edited because the content and the name didn't change",
                0,
            )
        elif file_content == content:
            try:
                os.replace(path, new_path)
                return f"{path} was successfully renamed to {new_path}", 0
            except OSError:
                return f"Could not rename {path} into {new_path}", 1
        elif path == new_path:
            new_path = path
        else:
            try:
                os.remove(path)
            except OSError:
                return f"Could not remove {path}", 1

        with open(new_path, "w") as f:
            f.write(content)

        return f"The file {path} was successfully edited", 0
