from glob import glob
from os import listdir, replace, walk
from os.path import dirname, join
from pathlib import Path
from re import compile as re_compile
from shutil import rmtree, move as shutil_move
from typing import Any, Dict, List, Tuple

from utils import path_to_dict


def generate_custom_configs(
    custom_configs: List[Dict[str, Any]],
    *,
    original_path: str = "/data/configs",
):
    Path(original_path).mkdir(parents=True, exist_ok=True)
    for custom_config in custom_configs:
        tmp_path = f"{original_path}/{custom_config['type'].replace('_', '-')}"
        if custom_config["service_id"]:
            tmp_path += f"/{custom_config['service_id']}"
        tmp_path += f"/{custom_config['name']}.conf"
        Path(dirname(tmp_path)).mkdir(parents=True, exist_ok=True)
        Path(tmp_path).write_bytes(custom_config["data"])


class ConfigFiles:
    def __init__(self, logger, db):
        self.__name_regex = re_compile(r"^[a-zA-Z0-9_\-.]{1,64}$")
        self.__root_dirs = [
            child["name"]
            for child in path_to_dict("/etc/bunkerweb/configs")["children"]
        ]
        self.__file_creation_blacklist = ["http", "stream"]
        self.__logger = logger
        self.__db = db

        if not Path("/usr/sbin/nginx").is_file():
            custom_configs = self.__db.get_custom_configs()

            if custom_configs:
                self.__logger.info("Refreshing custom configs ...")
                # Remove old custom configs files
                for file in glob("/data/configs/*"):
                    if Path(file).is_symlink() or Path(file).is_file():
                        Path(file).unlink()
                    elif Path(file).is_dir():
                        rmtree(file, ignore_errors=False)

                generate_custom_configs(custom_configs)
                self.__logger.info("Custom configs refreshed successfully")

    def save_configs(self) -> str:
        custom_configs = []
        root_dirs = listdir("/etc/bunkerweb/configs")
        for root, dirs, files in walk("/etc/bunkerweb/configs", topdown=True):
            if (
                root != "configs"
                and (dirs and not root.split("/")[-1] in root_dirs)
                or files
            ):
                path_exploded = root.split("/")
                for file in files:
                    with open(join(root, file), "r") as f:
                        custom_configs.append(
                            {
                                "value": f.read(),
                                "exploded": (
                                    f"{path_exploded.pop()}"
                                    if path_exploded[-1] not in root_dirs
                                    else "",
                                    path_exploded[-1],
                                    file.replace(".conf", ""),
                                ),
                            }
                        )

        err = self.__db.save_custom_configs(custom_configs, "ui")
        if err:
            self.__logger.error(f"Could not save custom configs: {err}")
            return "Couldn't save custom configs to database"

        return ""

    def check_name(self, name: str) -> bool:
        return self.__name_regex.match(name) is not None

    def check_path(self, path: str, root_path: str = "/etc/bunkerweb/configs/") -> str:
        root_dir: str = path.split("/")[4]
        if not (
            path.startswith(root_path)
            or root_path == "/etc/bunkerweb/configs/"
            and path.startswith(root_path)
            and root_dir in self.__root_dirs
            and (
                not path.endswith(".conf")
                or root_dir not in self.__file_creation_blacklist
                or len(path.split("/")) > 5
            )
        ):
            return f"{path} is not a valid path"

        if root_path == "/etc/bunkerweb/configs/":
            dirs = path.split("/")[5:]
            nbr_children = len(dirs)
            dirs = "/".join(dirs)
            if len(dirs) > 1:
                for x in range(nbr_children - 1):
                    if not Path(
                        f"{root_path}{root_dir}/{'/'.join(dirs.split('/')[0:-x])}"
                    ).exists():
                        return f"{root_path}{root_dir}/{'/'.join(dirs.split('/')[0:-x])} doesn't exist"

        return ""

    def delete_path(self, path: str) -> Tuple[str, int]:
        try:
            if Path(path).is_file() or Path(f"{path}.conf").is_file():
                Path(f"{path}.conf").unlink()
            else:
                rmtree(path)
        except OSError:
            return f"Could not delete {path}", 1

        return f"{path} was successfully deleted", 0

    def create_folder(self, path: str, name: str) -> Tuple[str, int]:
        folder_path = join(path, name) if not path.endswith(name) else path
        try:
            Path(folder_path).mkdir()
        except OSError:
            return f"Could not create {folder_path}", 1

        return f"The folder {folder_path} was successfully created", 0

    def create_file(self, path: str, name: str, content: str) -> Tuple[str, int]:
        file_path = join(path, name)
        Path(path).mkdir(exist_ok=True)
        Path(file_path).write_text(content)
        return f"The file {file_path} was successfully created", 0

    def edit_folder(self, path: str, name: str, old_name: str) -> Tuple[str, int]:
        new_folder_path = join(dirname(path), name)
        old_folder_path = join(dirname(path), old_name)

        if old_folder_path == new_folder_path:
            return (
                f"{old_folder_path} was not renamed because the name didn't change",
                0,
            )

        try:
            shutil_move(old_folder_path, new_folder_path)
        except OSError:
            return f"Could not move {old_folder_path}", 1

        return (
            f"The folder {old_folder_path} was successfully renamed to {new_folder_path}",
            0,
        )

    def edit_file(
        self, path: str, name: str, old_name: str, content: str
    ) -> Tuple[str, int]:
        new_path = join(dirname(path), name)
        old_path = join(dirname(path), old_name)

        try:
            file_content = Path(old_path).read_text()
        except FileNotFoundError:
            return f"Could not find {old_path}", 1

        if old_path == new_path and file_content == content:
            return (
                f"{old_path} was not edited because the content and the name didn't change",
                0,
            )
        elif file_content == content:
            try:
                replace(path, new_path)
                return f"{old_path} was successfully renamed to {new_path}", 0
            except OSError:
                return f"Could not rename {old_path} into {new_path}", 1
        elif old_path == new_path:
            new_path = old_path
        else:
            try:
                Path(old_path).unlink()
            except OSError:
                return f"Could not remove {old_path}", 1

        Path(new_path).write_text(content)

        return f"The file {old_path} was successfully edited", 0
