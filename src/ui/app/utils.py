#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime
from os import _exit
from os.path import sep
from pathlib import Path
from string import printable
from subprocess import PIPE, Popen, call
from time import sleep
from typing import Any, Dict, FrozenSet, Optional, Set, Union
from urllib.parse import unquote

from bcrypt import checkpw, gensalt, hashpw
from defusedcsv.csv import _escape as _defusedcsv_escape, writer as _defusedcsv_writer
from flask import current_app, flash as flask_flash, session
from regex import compile as re_compile, match
from requests import get

from logger import getLogger  # type: ignore

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")

LOGGER = getLogger("UI")

RESERVED_SERVICE_NAMES = frozenset({"unknown", "Web UI", "bwcli", "default server", ""})

# Static-asset URL prefixes served by Flask that never carry privilege (no auth/authz needed).
# Single source of truth shared by main.py (before_request fast-paths) and the Biscuit
# authorization middleware, so the two never drift.
STATIC_PATH_PREFIXES = ("/css/", "/img/", "/js/", "/json/", "/fonts/", "/libs/", "/locales/")

USER_PASSWORD_RX = re_compile(r"^(?=.*\p{Ll})(?=.*\p{Lu})(?=.*\d)(?=.*\P{Alnum}).{8,}$")
# Characters that could break out of a quoted string when a username is embedded in
# Datalog/Biscuit source. Token construction binds usernames as parameters already; this is a
# defense-in-depth gate applied at user creation/rename/import (and SSO provisioning).
USER_NAME_UNSAFE_RX = re_compile(r'["\\\x00-\x1f\x7f]')
BCRYPT_HASH_RX = re_compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}\Z")
RECOMMENDED_BCRYPT_COST = 12  # below this, a supplied pre-hashed ADMIN_PASSWORD triggers a warning
MIN_BCRYPT_COST = 10  # absolute floor; a supplied pre-hashed ADMIN_PASSWORD below this is refused
MAX_PASSWORD_BYTES = 72  # bcrypt only consumes the first 72 bytes of a secret; 5.x raises ValueError on more
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
        "7": True,
        "8": False,
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
        "4": True,
        "5": True,
        "6": False,
        "7": True,
        "8": False,
        "9": False,
        "10": True,
        "11": True,
        "12": True,
        "13": True,
        "14": True,
    },
    "services": {
        "3": True,
        "4": True,
        "5": True,
        "6": True,
        "7": True,
    },
    "templates": {
        "3": False,
        "4": True,
        "5": True,
        "6": True,
        "7": True,
        "8": True,
        "9": True,
        "10": True,
    },
}

ALWAYS_USED_PLUGINS = (
    "general",
    "errors",
    "headers",
    "misc",
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
    "PHP": {"REMOTE_PHP": "", "LOCAL_PHP": ""},
    "REDIRECT": {"REDIRECT_TO": ""},
    "SELFSIGNED": {"GENERATE_SELF_SIGNED_SSL": "no"},
}

UI_API_METHODS: FrozenSet[str] = frozenset({"ui", "api"})
EDITABLE_METHODS: FrozenSet[str] = UI_API_METHODS | frozenset({"wizard"})


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


def restart_workers():
    sleep(3)
    pid_file = Path(sep, "var", "run", "bunkerweb", "ui.pid")
    if pid_file.is_file():
        pid = pid_file.read_bytes()
    else:
        p = Popen(["pgrep", "-f", "gunicorn"], stdout=PIPE)
        pid, _ = p.communicate()
    call(["kill", "-HUP", pid.strip().decode().split("\n")[0]])


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


def is_editable_method(method: Optional[str], *, allow_default: bool = False) -> bool:
    """
    Determine if a configuration method is editable from the UI.

    Parameters
    ----------
    method : Optional[str]
        The method associated with a configuration (for example "ui" or "api").
    allow_default : bool, optional
        When True, the "default" method is also considered editable.
    """
    if method == "default":
        return allow_default
    return method in EDITABLE_METHODS


def is_ui_api_method(method: Optional[str]) -> bool:
    """Determine if a method belongs to the UI/API editable family."""
    return method in UI_API_METHODS


def can_delete_service(service: Dict[str, Any]) -> bool:
    """Services deletable from the UI: ui/api methods always, autoconf only when drafted."""
    method = service.get("method")
    if is_ui_api_method(method):
        return True
    return method == "autoconf" and bool(service.get("is_draft"))


def get_filtered_settings(settings: dict, global_config: bool = False) -> Dict[str, dict]:
    multisites = {}
    for setting, data in settings.items():
        if not global_config and data["context"] == "global":
            continue
        multisites[setting] = data
    return multisites


def get_blacklisted_settings(global_config: bool = False) -> Set[str]:
    blacklisted_settings = {
        "IS_LOADING",
        "AUTOCONF_MODE",
        "SWARM_MODE",
        "KUBERNETES_MODE",
        "IS_DRAFT",
        "BUNKERWEB_INSTANCES",
        "DATABASE_URI",
        "DATABASE_URI_READONLY",
    }
    if global_config:
        blacklisted_settings.update({"SERVER_NAME", "USE_TEMPLATE"})
    return blacklisted_settings


def _bcrypt_secret(password: str) -> bytes:
    # bcrypt only ever consumes the first 72 bytes of a secret. bcrypt 4.x truncated
    # longer input silently; bcrypt 5.x raises ValueError instead. Truncate explicitly
    # so behaviour (and every already-stored hash) stays identical across both versions.
    # Set-time flows reject >72 bytes up front (see password_exceeds_bcrypt_limit); this
    # truncation only matters for verifying legacy hashes created before that cap existed.
    return password.encode("utf-8")[:MAX_PASSWORD_BYTES]


def password_exceeds_bcrypt_limit(password: str) -> bool:
    """True if the password is longer than bcrypt's MAX_PASSWORD_BYTES-byte limit.

    bcrypt 5.x raises a ValueError past 72 bytes (4.x silently truncated). Password
    set/change flows reject overly long input with this check so nothing is silently
    truncated going forward; verification still truncates so pre-cap hashes keep working.
    """
    return len(password.encode("utf-8")) > MAX_PASSWORD_BYTES


def gen_password_hash(password: str) -> bytes:
    return hashpw(_bcrypt_secret(password), gensalt(rounds=13))


def is_bcrypt_hash(value: str) -> bool:
    """True if value is a well-formed bcrypt hash this build's bcrypt lib can verify."""
    if not BCRYPT_HASH_RX.match(value):
        return False
    try:
        checkpw(b"bunkerweb-bcrypt-probe", value.encode("utf-8"))
    except (ValueError, TypeError):
        return False  # prefix/format the installed bcrypt lib cannot parse -> treat as plaintext
    return True


def bcrypt_cost(value: str) -> int:
    """Cost factor of a bcrypt hash. Caller must ensure value passed is_bcrypt_hash() first."""
    return int(value[4:6])


def check_password(password: str, hashed: bytes) -> bool:
    return checkpw(_bcrypt_secret(password), hashed)


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
    latest_release = None

    for release in reversed(releases):
        if not release["prerelease"]:
            latest_release = release

    if not latest_release:
        LOGGER.error("Failed to fetch latest release information")
        latest_release = "unknown"
    else:
        latest_release = latest_release["tag_name"].removeprefix("v")

    return latest_release


def flash(message: str, category: str = "success", i18n_key: Optional[str] = None, *, save: bool = True) -> None:
    if i18n_key:
        message = f'<span data-i18n="{i18n_key}">{message}</span>'

    if category != "success":
        flask_flash(message, category)
    else:
        flask_flash(message)

    if save and "flash_messages" in session:
        session["flash_messages"].append((message, category, datetime.now().astimezone().isoformat()))
        session.modified = True


def human_readable_number(value: Union[str, int]) -> str:
    value = int(value)
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}M"  # noqa: E226
    elif value >= 1_000:
        return f"{value/1_000:.1f}k"  # noqa: E226
    return str(value)


def is_plugin_active(plugin_id: str, plugin_name: str, config: dict) -> bool:
    plugin_name_formatted = plugin_name.replace(" ", "_").upper()

    def plugin_used(plugin_id: str) -> bool:
        plugin_id = plugin_id.upper()
        if plugin_id in PLUGINS_SPECIFICS:
            for key, value in PLUGINS_SPECIFICS[plugin_id].items():
                if config.get(key, {"value": value})["value"] != value:
                    return True
        elif config.get(f"USE_{plugin_id}", config.get(f"USE_{plugin_name_formatted}", {"value": "no"}))["value"] != "no":
            return True
        return False

    return plugin_id in ALWAYS_USED_PLUGINS or plugin_used(plugin_id)


def _sanitize_internal_next(next_url, default):
    """Return a safe same-origin internal path, else raise ValueError.

    Hardened against open redirect (CWE-601). A value is accepted only if, in BOTH its
    raw and its once-URL-decoded form, it is a single-slash-rooted path with:
      * no protocol-relative prefix -- ``//host`` or ``/\\host`` (browsers fold ``\\`` to
        ``/`` so ``/\\host`` becomes ``//host``);
      * no scheme and no backslash anywhere (``scheme://`` / ``\\``);
      * no control characters (defeats header/redirect splitting);
      * no ``.`` or ``..`` path segment. The browser URL parser *normalizes* these rather
        than rejecting them, and a leading collapse escapes the origin (``/..//host`` and
        ``/.//host`` both normalize to the protocol-relative ``//host``). Rather than
        replicate that normalization to isolate only the escaping subset, this rejects the
        whole superset (so a harmless ``/a/../b`` is also refused) -- fail-closed, and the
        app's own internal routes never carry dot segments, so the cost is nil. Only the
        path portion is inspected, so dots inside a query string are preserved.

    The browser URL parser decodes percent-encoding only once, so evaluating the raw and
    the once-decoded forms matches its behavior: single-encoded escapes (``/%2f%2fhost``,
    ``/%5chost``) are caught, while double-encoded payloads stay percent-encoded and remain
    same-origin (and therefore harmless) when navigated.
    """
    if next_url is None:
        return default
    if not isinstance(next_url, str):
        raise ValueError("next must be str")
    candidate = next_url.strip()
    if len(candidate) > 4096:  # bound before decode to avoid abuse
        raise ValueError("too long")
    decoded = unquote(candidate)[:4096]
    for value in (candidate, decoded):
        if not value.startswith("/"):
            raise ValueError("must start with /")
        if value[1:2] in ("/", "\\"):
            raise ValueError("protocol-relative not allowed")
        if "\\" in value or "://" in value:
            raise ValueError("scheme or backslash not allowed")
        if any(ord(c) < 32 for c in value):
            raise ValueError("control chars not allowed")
        path_segments = value.split("?", 1)[0].split("#", 1)[0].split("/")
        if "." in path_segments or ".." in path_segments:
            raise ValueError("dot path segment not allowed")
    return decoded or default


# Revoked UI session ids are kept in DATA["REVOKED_SESSIONS"] (file-backed, checked on every
# request) so a logged-out / wiped / password-changed session is rejected before its server-side
# store entry naturally expires. Without pruning this set grows without bound. A revoked id only
# needs to be retained until the session it names can no longer exist, i.e. the maximum session
# lifetime; after that the store entry is gone and the id is dead weight.
REVOKED_SESSION_TTL_FALLBACK_SECONDS = 30 * 24 * 3600  # used only if no lifetime is configured


def _revoked_session_ttl_seconds():
    """Longest a revoked session id must be retained = the max possible session lifetime."""
    cfg = getattr(current_app, "config", {})
    candidates = []
    with suppress(Exception):
        candidates.append(int(cfg.get("SESSION_ABSOLUTE_SECONDS", 0) or 0))
    with suppress(Exception):
        perm = cfg.get("PERMANENT_SESSION_LIFETIME")
        if perm is not None:
            candidates.append(int(perm.total_seconds()))
    ttl = max(candidates) if candidates else 0
    return ttl if ttl > 0 else REVOKED_SESSION_TTL_FALLBACK_SECONDS


def prune_revoked_sessions(revoked, now_ts=None, ttl_seconds=None):
    """Return a {session_id: revoked_at_epoch} dict with entries older than the TTL dropped.

    Tolerates the legacy ``list[str]`` format (no timestamps): those entries are migrated and
    stamped at ``now`` so a format change never silently un-revokes a still-live session.
    """
    if now_ts is None:
        now_ts = datetime.now().timestamp()
    if ttl_seconds is None:
        ttl_seconds = _revoked_session_ttl_seconds()
    if isinstance(revoked, dict):
        return {sid: ts for sid, ts in revoked.items() if isinstance(ts, (int, float)) and (now_ts - ts) < ttl_seconds}
    if isinstance(revoked, (list, tuple, set)):
        return {str(sid): now_ts for sid in revoked if sid}
    return {}


def add_revoked_sessions(revoked, ids):
    """Prune stale entries, then add ``ids`` stamped at now. Returns the updated dict."""
    now_ts = datetime.now().timestamp()
    pruned = prune_revoked_sessions(revoked, now_ts)
    for sid in ids:
        if sid:
            pruned[str(sid)] = now_ts
    return pruned


# OWASP lists \t (0x09) and \r (0x0D) as spreadsheet-injection leaders, but defusedcsv's
# _escape only guards "@+-=|%". Prefix a quote for those two so Excel treats the cell as text.
_CSV_INJECTION_LEADERS = ("\t", "\r")


def _csv_escape(value: Any) -> Any:
    """defusedcsv formula-injection escaping (CWE-1236) plus the \\t / \\r leaders it omits."""
    escaped = _defusedcsv_escape(value)
    if isinstance(escaped, str) and escaped[:1] in _CSV_INJECTION_LEADERS:
        return "'" + escaped
    return escaped


class _CsvSafeWriter:
    """Wrap a CSV writer so every cell is escaped via :func:`_csv_escape`.

    Pre-escaping is idempotent: a value already prefixed with ``'`` is left untouched by
    the underlying ``defusedcsv`` writer (its first char is no longer an injection leader).
    """

    def __init__(self, writer):
        self._writer = writer

    def writerow(self, row):
        return self._writer.writerow([_csv_escape(cell) for cell in row])

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


def csv_writer(csvfile, *args, **kwargs):
    """Return a CSV writer that escapes spreadsheet formula payloads (CWE-1236).

    Wraps ``defusedcsv`` and additionally guards the tab/CR leaders defusedcsv omits.
    Use this for all UI CSV exports instead of ``csv.writer``.
    """
    return _CsvSafeWriter(_defusedcsv_writer(csvfile, *args, **kwargs))


def csv_safe(value: Any) -> Any:
    """Escape one cell value with formula-injection protection (CWE-1236).

    Use this for user-controlled values written through openpyxl.
    """
    return _csv_escape(value)
