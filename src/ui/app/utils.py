#!/usr/bin/env python3

from datetime import datetime
from os import _exit, getenv, sep
from os.path import join
from pathlib import Path
from string import printable
from subprocess import PIPE, Popen, call
from sys import path as sys_path
from typing import Dict, Optional, Set, Union

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for utils module")

from bcrypt import checkpw, gensalt, hashpw
from flask import flash as flask_flash, session
from regex import compile as re_compile, match
from requests import get


TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")

USER_PASSWORD_RX = re_compile(r"^(?=.*\p{Ll})(?=.*\p{Lu})(?=.*\d)(?=.*\P{Alnum}).{8,}$")
PLUGIN_NAME_RX = re_compile(r"^[\w.-]{4,64}$")

BISCUIT_PUBLIC_KEY_FILE = LIB_DIR.joinpath(".biscuit_public_key")
BISCUIT_PRIVATE_KEY_FILE = LIB_DIR.joinpath(".biscuit_private_key")

COLUMNS_PREFERENCES_DEFAULTS = {
    "bans": {
        "3": True,
        "4": True,
        "5": True,
        "6": True,
        "7": True,
        "8": True,
        "9": True,
    },
    "cache": {
        "4": True,
        "5": True,
        "6": True,
        "7": False,
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
        "4": True,
        "5": False,
        "6": True,
        "7": False,
        "8": False,
        "9": True,
        "10": True,
        "11": True,
        "12": True,
    },
    "services": {
        "3": True,
        "4": True,
        "5": True,
        "6": True,
    },
}

ALWAYS_USED_PLUGINS = (
    "general",
    "errors",
    "headers",
    "misc",
    "php",
    "pro",
    "sessions",
    "ssl",
)
PLUGINS_SPECIFICS = {
    "COUNTRY": {"BLACKLIST_COUNTRY": "", "WHITELIST_COUNTRY": ""},
    "CUSTOMCERT": {"USE_CUSTOM_SSL": "no"},
    "INJECT": {"INJECT_BODY": "", "INJECT_HEAD": ""},
    "LETSENCRYPT": {"AUTO_LETS_ENCRYPT": "no"},
    "LIMIT": {"USE_LIMIT_REQ": "no", "USE_LIMIT_CONN": "no"},
    "REDIRECT": {"REDIRECT_TO": ""},
    "SELFSIGNED": {"GENERATE_SELF_SIGNED_SSL": "no"},
}


# Terminate the BunkerWeb UI process gracefully or with force.
# Sends SIGTERM signal to the gunicorn process and exits with the 
# specified status code.
def stop(status, _stop: bool = True):
    if DEBUG_MODE:
        logger.debug(f"stop() called with status={status}, _stop={_stop}")
    
    if _stop:
        pid_file = Path(sep, "var", "run", "bunkerweb", "ui.pid")
        if DEBUG_MODE:
            logger.debug(f"Checking for PID file: {pid_file}")
        
        if pid_file.is_file():
            if DEBUG_MODE:
                logger.debug(f"Reading PID from file: {pid_file}")
            pid = pid_file.read_bytes()
        else:
            if DEBUG_MODE:
                logger.debug("PID file not found, using pgrep to find process")
            p = Popen(["pgrep", "-f", "gunicorn"], stdout=PIPE)
            pid, _ = p.communicate()
        
        pid_str = pid.strip().decode().split("\n")[0]
        if DEBUG_MODE:
            logger.debug(f"Sending SIGTERM to PID: {pid_str}")
        call(["kill", "-SIGTERM", pid_str])
    
    if DEBUG_MODE:
        logger.debug(f"Exiting with status: {status}")
    _exit(status)


# Handle stop signals (SIGINT, SIGTERM) and perform graceful shutdown.
# Logs the signal received and calls the stop function to terminate
# the application cleanly.
def handle_stop(signum, frame):
    if DEBUG_MODE:
        logger.debug(f"handle_stop() called with signal: {signum}")
    
    logger.info("Caught stop operation")
    logger.info("Stopping web ui ...")
    stop(0, False)


# Extract and organize multiple settings configurations by suffix.
# Processes settings with numeric suffixes and groups them by their
# multiple identifier for dynamic form generation.
def get_multiples(settings: dict, config: dict) -> Dict[str, Dict[str, Dict[str, dict]]]:
    if DEBUG_MODE:
        logger.debug(f"get_multiples() called with {len(settings)} settings and {len(config)} config items")
    
    plugin_multiples = {}

    for setting, data in settings.items():
        multiple = data.get("multiple")
        if multiple:
            if DEBUG_MODE:
                logger.debug(f"Processing multiple setting: {setting} with multiple: {multiple}")
            
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
                    if DEBUG_MODE:
                        logger.debug(f"Found suffixed setting: {config_setting} with suffix {suffix}")
                    
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

    if DEBUG_MODE:
        logger.debug(f"Processed {len(plugin_multiples)} multiple groups")
    
    return plugin_multiples


# Filter settings based on context (global vs multisite).
# Returns only settings appropriate for the specified configuration
# context to prevent invalid setting combinations.
def get_filtered_settings(settings: dict, global_config: bool = False) -> Dict[str, dict]:
    if DEBUG_MODE:
        logger.debug(f"get_filtered_settings() called with global_config={global_config}, {len(settings)} settings")
    
    multisites = {}
    filtered_count = 0
    for setting, data in settings.items():
        if not global_config and data["context"] == "global":
            filtered_count += 1
            continue
        multisites[setting] = data
    
    if DEBUG_MODE:
        logger.debug(f"Filtered {len(multisites)} settings from {len(settings)} total ({filtered_count} excluded)")
    
    return multisites


# Get list of settings that should be excluded from configuration.
# Returns blacklisted setting names that are managed internally
# and should not be user-configurable.
def get_blacklisted_settings(global_config: bool = False) -> Set[str]:
    if DEBUG_MODE:
        logger.debug(f"get_blacklisted_settings() called with global_config={global_config}")
    
    blacklisted_settings = {"IS_LOADING", "AUTOCONF_MODE", "SWARM_MODE", "KUBERNETES_MODE", "IS_DRAFT", "BUNKERWEB_INSTANCES"}
    if global_config:
        blacklisted_settings.update({"SERVER_NAME", "USE_TEMPLATE"})
    
    if DEBUG_MODE:
        logger.debug(f"Returning {len(blacklisted_settings)} blacklisted settings: {blacklisted_settings}")
    
    return blacklisted_settings


# Generate secure bcrypt hash from plaintext password.
# Uses 13 rounds of bcrypt hashing for strong password security
# suitable for authentication storage.
def gen_password_hash(password: str) -> bytes:
    if DEBUG_MODE:
        logger.debug(f"gen_password_hash() called with password length: {len(password)}")
    
    hash_result = hashpw(password.encode("utf-8"), gensalt(rounds=13))
    
    if DEBUG_MODE:
        logger.debug("Password hash generated successfully")
    
    return hash_result


# Verify plaintext password against stored bcrypt hash.
# Returns True if password matches the hash, False otherwise
# for secure authentication verification.
def check_password(password: str, hashed: bytes) -> bool:
    if DEBUG_MODE:
        logger.debug(f"check_password() called with password length: {len(password)}, hash length: {len(hashed)}")
    
    result = checkpw(password.encode("utf-8"), hashed)
    
    if DEBUG_MODE:
        logger.debug(f"Password verification result: {result}")
    
    return result


# Convert binary data to printable string or fallback message.
# Attempts UTF-8 decoding and checks for printable characters,
# returning safe content or download prompt for binary files.
def get_printable_content(data: bytes) -> str:
    if DEBUG_MODE:
        logger.debug(f"get_printable_content() called with {len(data)} bytes")
    
    try:
        content = data.decode("utf-8")
        if DEBUG_MODE:
            logger.debug(f"Successfully decoded {len(content)} characters from UTF-8")
    except UnicodeDecodeError:
        if DEBUG_MODE:
            logger.debug("Content is not valid UTF-8, returning download prompt")
        return "Download file to view content"
    
    if all(c in printable for c in content):
        if DEBUG_MODE:
            logger.debug("Content contains only printable characters")
        return content
    
    if DEBUG_MODE:
        logger.debug("Content contains non-printable characters, returning download prompt")
    return "Download file to view content"


# Fetch latest stable release information from GitHub API.
# Queries BunkerWeb repository releases and returns the most recent
# non-prerelease version data for update checking.
def get_latest_stable_release():
    if DEBUG_MODE:
        logger.debug("get_latest_stable_release() called, making GitHub API request")
    
    response = get("https://api.github.com/repos/bunkerity/bunkerweb/releases", headers={"User-Agent": "BunkerWeb"}, timeout=3)
    response.raise_for_status()
    
    if DEBUG_MODE:
        logger.debug(f"GitHub API response status: {response.status_code}")
    
    releases = response.json()
    
    if DEBUG_MODE:
        logger.debug(f"Retrieved {len(releases)} releases from GitHub API")

    for i, release in enumerate(releases):
        if DEBUG_MODE:
            logger.debug(f"Checking release {i}: {release.get('tag_name')} (prerelease: {release.get('prerelease')})")
        
        if not release["prerelease"]:
            if DEBUG_MODE:
                logger.debug(f"Found stable release: {release.get('tag_name')}")
            return release
    
    if DEBUG_MODE:
        logger.debug("No stable releases found in response")
    return None


# Display flash message to user with optional internationalization.
# Stores message in Flask session for display and optionally saves
# to session history with timestamp for persistence.
def flash(message: str, category: str = "success", i18n_key: Optional[str] = None, *, save: bool = True) -> None:
    if DEBUG_MODE:
        logger.debug(f"flash() called with category: {category}, i18n_key: {i18n_key}, save: {save}")
    
    if i18n_key:
        if DEBUG_MODE:
            logger.debug(f"Adding i18n wrapper with key: {i18n_key}")
        message = f'<span data-i18n="{i18n_key}">{message}</span>'

    if category != "success":
        flask_flash(message, category)
    else:
        flask_flash(message)

    if save and "flash_messages" in session:
        session["flash_messages"].append((message, category, datetime.now().astimezone().isoformat()))
        if DEBUG_MODE:
            logger.debug("Flash message saved to session history")
    elif DEBUG_MODE:
        logger.debug("Flash message not saved (save=False or no flash_messages in session)")


# Convert numeric value to human-readable format with suffixes.
# Formats large numbers with M (millions) or k (thousands) suffixes
# for better display in user interfaces.
def human_readable_number(value: Union[str, int]) -> str:
    if DEBUG_MODE:
        logger.debug(f"human_readable_number() called with value: {value} (type: {type(value)})")
    
    value = int(value)
    
    if value >= 1_000_000:
        result = f"{value/1_000_000:.1f}M"
        if DEBUG_MODE:
            logger.debug(f"Formatted {value} as millions: {result}")
    elif value >= 1_000:
        result = f"{value/1_000:.1f}k"
        if DEBUG_MODE:
            logger.debug(f"Formatted {value} as thousands: {result}")
    else:
        result = str(value)
        if DEBUG_MODE:
            logger.debug(f"Value {value} below 1000, returning as-is: {result}")
    
    return result


# Determine if a plugin is currently active based on configuration.
# Checks plugin-specific settings and USE_* flags to determine
# whether the plugin should be considered active and loaded.
def is_plugin_active(plugin_id: str, plugin_name: str, config: dict) -> bool:
    if DEBUG_MODE:
        logger.debug(f"is_plugin_active() called for plugin: {plugin_id} (name: {plugin_name})")
    
    plugin_name_formatted = plugin_name.replace(" ", "_").upper()
    if DEBUG_MODE:
        logger.debug(f"Formatted plugin name: {plugin_name_formatted}")

    def plugin_used(plugin_id: str) -> bool:
        plugin_id = plugin_id.upper()
        if DEBUG_MODE:
            logger.debug(f"Checking if plugin {plugin_id} is used")
        
        if plugin_id in PLUGINS_SPECIFICS:
            if DEBUG_MODE:
                logger.debug(f"Plugin {plugin_id} has specific settings: {PLUGINS_SPECIFICS[plugin_id]}")
            
            for key, value in PLUGINS_SPECIFICS[plugin_id].items():
                config_value = config.get(key, {"value": value})["value"]
                if DEBUG_MODE:
                    logger.debug(f"Checking specific setting {key}: config={config_value}, default={value}")
                
                if config_value != value:
                    if DEBUG_MODE:
                        logger.debug(f"Plugin {plugin_id} active via specific setting {key}")
                    return True
        else:
            use_key = f"USE_{plugin_id}"
            use_name_key = f"USE_{plugin_name_formatted}"
            
            use_value = config.get(use_key, config.get(use_name_key, {"value": "no"}))["value"]
            if DEBUG_MODE:
                logger.debug(f"Checking USE_ settings: {use_key} or {use_name_key} = {use_value}")
            
            if use_value != "no":
                if DEBUG_MODE:
                    logger.debug(f"Plugin {plugin_id} active via USE_ setting")
                return True
        
        if DEBUG_MODE:
            logger.debug(f"Plugin {plugin_id} not actively used")
        return False

    is_always_used = plugin_id in ALWAYS_USED_PLUGINS
    is_used = plugin_used(plugin_id)
    is_active = is_always_used or is_used
    
    if DEBUG_MODE:
        logger.debug(f"Plugin {plugin_id} status - always_used: {is_always_used}, used: {is_used}, active: {is_active}")
    
    return is_active
