#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime
from io import BytesIO
from os import _exit
from os.path import sep
from pathlib import Path
from shutil import rmtree
from stat import S_IRGRP, S_IRUSR, S_IWUSR, S_IXGRP, S_IXUSR
from string import printable
from subprocess import PIPE, Popen, call
from tarfile import open as tar_open
from traceback import format_exc
from typing import Dict, Set, Union

from bcrypt import checkpw, gensalt, hashpw
from flask import flash as flask_flash, session
from regex import compile as re_compile, match
from requests import get

from logger import setup_logger  # type: ignore
from common_utils import bytes_hash  # type: ignore


TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")

EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
PRO_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "pro", "plugins")

LOGGER = setup_logger("UI")

USER_PASSWORD_RX = re_compile(r"^(?=.*\p{Ll})(?=.*\p{Lu})(?=.*\d)(?=.*\P{Alnum}).{8,}$")
PLUGIN_NAME_RX = re_compile(r"^[\w.-]{4,64}$")

COLUMNS_PREFERENCES_DEFAULTS = {
    "bans": {
        "3": True,
        "4": True,
        "5": True,
        "6": True,
        "7": True,
        "8": True,
    },
    "configs": {
        "3": True,
        "4": True,
        "5": True,
        "6": True,
        "7": False,
    },
    "instances": {
        "3": False,
        "4": False,
        "5": True,
        "6": True,
        "7": True,
        "8": True,
    },
    "jobs": {
        "3": True,
        "4": True,
        "5": True,
        "6": True,
        "7": True,
    },
    "plugins": {
        "2": False,
        "4": False,
        "5": True,
        "6": True,
        "7": True,
        "8": True,
    },
    "reports": {
        "3": True,
        "4": False,
        "5": False,
        "6": False,
        "7": False,
        "8": True,
        "9": True,
        "10": True,
        "11": True,
    },
    "services": {
        "3": True,
        "4": True,
        "5": True,
        "6": True,
    },
}


def stop(status, _stop: bool = True):
    if _stop:
        pid_file = Path(sep, "var", "run", "bunkerweb", "ui.pid")
        if pid_file.is_file():
            pid = pid_file.read_bytes()
        else:
            p = Popen(["pgrep", "-f", "gunicorn"], stdout=PIPE)
            pid, _ = p.communicate()
        call(["kill", "-SIGTERM", pid.strip().decode().split("\n")[0]])
    _exit(status)


def handle_stop(signum, frame):
    LOGGER.info("Caught stop operation")
    LOGGER.info("Stopping web ui ...")
    stop(0, False)


def get_multiples(settings: dict, config: dict) -> Dict[str, Dict[str, Dict[str, dict]]]:
    plugin_multiples = {}

    for setting, data in settings.items():
        multiple = data.get("multiple")
        if multiple:
            # Add the setting without suffix for reference
            data = data | {"setting_no_suffix": setting}

            if multiple not in plugin_multiples:
                plugin_multiples[multiple] = {}
            if "0" not in plugin_multiples[multiple]:
                plugin_multiples[multiple]["0"] = {}

            # Add the base (suffix "0") setting
            plugin_multiples[multiple]["0"].update({setting: data})

            # Process config settings with suffixes
            for config_setting, value in config.items():
                setting_match = match(setting + r"_(?P<suffix>\d+)$", config_setting)
                if setting_match:
                    suffix = setting_match.group("suffix")
                    if suffix not in plugin_multiples[multiple]:
                        plugin_multiples[multiple][suffix] = {}
                    plugin_multiples[multiple][suffix][config_setting] = {
                        **data,
                        "value": value,  # Include the value from the config
                    }

            # Ensure every suffix group has all settings in the same order as "0"
            base_settings = plugin_multiples[multiple]["0"]
            for suffix, settings_dict in plugin_multiples[multiple].items():
                if suffix == "0":
                    continue
                for default_setting, default_data in base_settings.items():
                    if f"{default_setting}_{suffix}" not in settings_dict:
                        settings_dict[f"{default_setting}_{suffix}"] = {
                            **default_data,
                            "value": default_data.get("value"),  # Default value if not in config
                        }

                # Preserve the order of settings based on suffix "0"
                plugin_multiples[multiple][suffix] = {
                    f"{default_setting}_{suffix}": settings_dict[f"{default_setting}_{suffix}"] for default_setting in base_settings
                }

    # Sort the multiples and their settings
    for multiple, multiples in plugin_multiples.items():
        plugin_multiples[multiple] = dict(sorted(multiples.items(), key=lambda x: int(x[0])))

    return plugin_multiples


def get_filtered_settings(settings: dict, global_config: bool = False) -> Dict[str, dict]:
    multisites = {}
    for setting, data in settings.items():
        if not global_config and data["context"] == "global":
            continue
        multisites[setting] = data
    return multisites


def get_blacklisted_settings(global_config: bool = False) -> Set[str]:
    blacklisted_settings = {"IS_LOADING", "AUTOCONF_MODE", "SWARM_MODE", "KUBERNETES_MODE", "IS_DRAFT", "BUNKERWEB_INSTANCES"}
    if global_config:
        blacklisted_settings.update({"SERVER_NAME", "USE_TEMPLATE"})
    return blacklisted_settings


def gen_password_hash(password: str) -> bytes:
    return hashpw(password.encode("utf-8"), gensalt(rounds=13))


def check_password(password: str, hashed: bytes) -> bool:
    return checkpw(password.encode("utf-8"), hashed)


def get_printable_content(data: bytes) -> str:
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        return "Download file to view content"
    if all(c in printable for c in content):
        return content
    return "Download file to view content"


def get_latest_stable_release():
    response = get("https://api.github.com/repos/bunkerity/bunkerweb/releases", headers={"User-Agent": "BunkerWeb"}, timeout=3)
    response.raise_for_status()
    releases = response.json()

    for release in releases:
        if not release["prerelease"]:
            return release
    return None


def flash(message: str, category: str = "success", *, save: bool = True) -> None:
    if category != "success":
        flask_flash(message, category)
    else:
        flask_flash(message)

    if save and "flash_messages" in session:
        session["flash_messages"].append((message, category, datetime.now().astimezone().isoformat()))


def human_readable_number(value: Union[str, int]) -> str:
    value = int(value)
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    elif value >= 1_000:
        return f"{value/1_000:.1f}k"
    return str(value)


def reload_plugins(db):
    plugins = db.get_plugins(_type="all", with_data=True)

    ignored_plugins = set()
    for plugin in plugins:
        # Determine the correct extraction path based on the plugin type.
        if plugin["type"] in ("external", "ui"):
            plugin_path = EXTERNAL_PLUGINS_PATH
        elif plugin["type"] == "pro":
            plugin_path = PRO_PLUGINS_PATH
        else:
            continue

        target = plugin_path / plugin["id"]

        # If the target exists, compare its checksum.
        if target.exists():
            with suppress(StopIteration, IndexError):
                with BytesIO() as plugin_content:
                    with tar_open(fileobj=plugin_content, mode="w:gz", compresslevel=9) as tar:
                        tar.add(target, arcname=target.name, recursive=True)
                    plugin_content.seek(0)
                    if bytes_hash(plugin_content, algorithm="sha256") == plugin["checksum"]:
                        ignored_plugins.add(target.name)
                        continue
                db.logger.debug(f"Checksum of {target} has changed, removing it ...")

                if target.is_symlink() or target.is_file():
                    with suppress(OSError):
                        target.unlink()
                elif target.is_dir():
                    rmtree(target, ignore_errors=True)

        try:
            if plugin["data"]:
                with tar_open(fileobj=BytesIO(plugin["data"]), mode="r:gz") as tar:
                    try:
                        tar.extractall(plugin_path, filter="fully_trusted")
                    except TypeError:
                        tar.extractall(plugin_path)

                plugin_folder = plugin_path / plugin["id"]
                # Add u+x permissions to executable files
                desired_perms = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP  # 0o750
                for subdir, pattern in (
                    ("jobs", "*"),
                    ("bwcli", "*"),
                    ("ui", "*.py"),
                ):
                    for executable_file in plugin_folder.joinpath(subdir).rglob(pattern):
                        if executable_file.stat().st_mode & 0o777 != desired_perms:
                            executable_file.chmod(desired_perms)
        except OSError as e:
            db.logger.debug(format_exc())
            if plugin["method"] != "manual":
                db.logger.error(f"Error while generating {plugin['type']} plugins \"{plugin['name']}\": {e}")
        except BaseException as e:
            db.logger.debug(format_exc())
            db.logger.error(f"Error while generating {plugin['type']} plugins \"{plugin['name']}\": {e}")

    ret = db.checked_changes(["ui_plugins"])
    if ret:
        db.logger.error(f"An error occurred when setting the changes to checked in the database : {ret}")
