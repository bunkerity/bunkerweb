#!/usr/bin/env python3

from datetime import datetime
from os import _exit
from os.path import sep
from pathlib import Path
from string import printable
from subprocess import PIPE, Popen, call
from typing import Dict, Set, Union

from bcrypt import checkpw, gensalt, hashpw
from flask import flash as flask_flash, session
from regex import compile as re_compile, match
from requests import get

from logger import setup_logger  # type: ignore


TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")

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
