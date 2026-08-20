#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime
from functools import lru_cache
from os import _exit
from os.path import sep
from pathlib import Path
from string import printable
from subprocess import PIPE, Popen, call
from time import sleep
from typing import Any, Dict, FrozenSet, Optional, Set, Union
from urllib.parse import unquote

from defusedcsv.csv import _escape as _defusedcsv_escape, writer as _defusedcsv_writer
from flask import current_app, flash as flask_flash, session
from flask_login import current_user
from regex import compile as re_compile, match
from requests import get

from logger import getLogger  # type: ignore
from password_utils import (  # type: ignore  # noqa: F401
    BCRYPT_HASH_RX as BCRYPT_HASH_RX,
    MAX_PASSWORD_BYTES as MAX_PASSWORD_BYTES,
    MIN_BCRYPT_COST as MIN_BCRYPT_COST,
    RECOMMENDED_BCRYPT_COST as RECOMMENDED_BCRYPT_COST,
    USER_PASSWORD_RX as USER_PASSWORD_RX,
    _bcrypt_secret as _bcrypt_secret,
    bcrypt_cost as bcrypt_cost,
    check_password as check_password,
    gen_password_hash as gen_password_hash,
    is_bcrypt_hash as is_bcrypt_hash,
    password_exceeds_bcrypt_limit as password_exceeds_bcrypt_limit,
)
from plugin_extensions import iter_plugin_activations  # type: ignore

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")

LOGGER = getLogger("UI")

RESERVED_SERVICE_NAMES = frozenset({"unknown", "Web UI", "bwcli", "default server", ""})

# Static-asset URL prefixes served by Flask that never carry privilege (no auth/authz needed).
# Single source of truth shared by main.py (before_request fast-paths) and the Biscuit
# authorization middleware, so the two never drift.
STATIC_PATH_PREFIXES = ("/css/", "/img/", "/js/", "/json/", "/fonts/", "/libs/", "/locales/")

# Pages whose templates read the *declared settings schema* off the shared `plugins` context:
# the compose shelf and its request-path strip (models/compose_pane.html, included by
# global_settings.html and service_settings.html) and the plugin grid's "manage activation"
# gate (plugins.html:172). Everywhere else -- the sidebar plugin list, the template editor's
# plugin badge -- only needs each plugin's identity.
#
# That schema is 95% of the /plugins payload (216 KB of 228 KB on a stock install), fetched
# once per render, so every other page asks for the slim shape. Adding a page that renders
# settings from this context means adding its prefix here; `tests/unit/ui/test_plugins_payload.py`
# fails if a template starts reading settings from a page that is not listed.
SETTINGS_HUNGRY_PATH_PREFIXES = ("/global-config", "/global-settings", "/services", "/plugins")

# Characters that could break out of a quoted string when a username is embedded in
# Datalog/Biscuit source. Token construction binds usernames as parameters already; this is a
# defense-in-depth gate applied at user creation/rename/import (and SSO provisioning).
USER_NAME_UNSAFE_RX = re_compile(r'["\\\x00-\x1f\x7f]')
# `\Z`, not `$`: `$` also matches before a trailing newline, so `"plugin\n"` would pass and
# become a directory name. Same defect as the config-name regexes.
PLUGIN_NAME_RX = re_compile(r"^[\w.-]{4,64}\Z")

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
        # 14 = protocol (shown: it says which vocabulary the row is written in), 15-19 = the
        # stream-only columns, hidden until an operator with TCP/UDP services wants them,
        # 20 = actions. Appended rather than inserted: these keys are column indices and are
        # persisted per user, so renumbering the existing ones would shuffle saved layouts.
        "14": True,
        "15": False,
        "16": False,
        "17": False,
        "18": False,
        "19": False,
        "20": True,
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


def is_readonly_request(api_readonly: bool) -> bool:
    """Would the page that rendered this form have disabled every field?

    Mirrors main.py:1283's `is_readonly` context processor (its `request.path` exemption is for
    /profile, which no settings-save route serves). `current_user.list_permissions` is set to an
    empty set when the permission load fails mid-request, so a transient API error must be read
    the same way here as it was on the page the user submitted.

    Every settings POST handler needs it, because a read-only page posts nothing but still posts
    a valid csrf_token -- and "in scope but not posted" means DELETE
    (db_methods/config_save.py:592). What that costs is NOT symmetric and this helper must not be
    read as if it were: at global scope it wipes a plugin's whole configuration, one plugin per
    POST (see the note at routes/global_settings.py:207-212); on a service page the same POST is
    a harmless no-op, because the service's own rows are re-materialised from the DB. Both
    callers still have to pass it -- the scope functions are where the asymmetry lives.

    Takes the API's readonly flag rather than importing it: `app.dependencies` builds real
    singletons at module scope (`Config()` reads the image-only /usr/share/bunkerweb/settings.json),
    so importing it here would make `app.utils` -- which every unit test imports bare -- fail to
    import in a checkout.
    """
    return api_readonly or "write" not in getattr(current_user, "list_permissions", [])


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


def get_github_stars():
    """The repository's star count, or None when GitHub does not report one.

    Fetched server-side and cached, rather than in the browser. The vendored github-buttons
    widget this replaces made one unauthenticated call *per visitor per page view* and its
    label lived in a closed shadow root, so it could never be translated. The unauthenticated
    REST limit is 60/hour and conditional requests do not help — a 304 still decrements it
    (measured 2026-08-20), so the hourly refresh in `main.py` is the whole defence, and it
    keeps the budget at 2/60.
    """
    response = get("https://api.github.com/repos/bunkerity/bunkerweb", headers={"User-Agent": "BunkerWeb"}, timeout=3)
    response.raise_for_status()
    return response.json().get("stargazers_count")


# Reasons a route may hand the login page, mapped to the message key it renders.
#
# This is `flash()`'s out-of-band twin, and it lives here for the same reason it exists at all:
# anything that must outlive a logout cannot go through `flash()`. `logout_page()` calls
# `session.clear()`, which empties BOTH stores below -- Flask's `_flashes` and our own
# `session["flash_messages"]` -- and `_establish_session()` re-wipes the second on the way back in.
# So the reason travels in the URL instead.
#
# It sits in `utils` rather than in `login.py` because `logout.py` needs it too, and
# `login -> app.models.biscuit -> logout -> login` is a real import cycle (caught by
# tests/unit/ui/test_login_notices.py). Both route modules already import from here.
#
# Looked up, never echoed: whatever is in the query string must not reach the page. The value is a
# translation key rather than a sentence because this UI translates server-side (i18n Lot B).
LOGIN_NOTICES = {
    "password_changed": "login.notice_password_changed",
    # Distinct from session_expired on purpose: that one says "your change was discarded", which is
    # wrong here. The absolute-lifetime logout fires on a GET as often as a POST and usually
    # discards nothing -- what the user needs to know is why they were signed out mid-session.
    "session_timeout": "login.notice_session_timeout",
    "session_expired": "login.notice_session_expired",
}


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


# `general` is synthesized from settings.json at db_methods/initialization.py:323 and has no
# plugin.json, so it cannot declare a manifest. One hardcoded entry, not a table.
_SYNTHESIZED_ALWAYS_ON = frozenset({"general"})


@lru_cache(maxsize=1)
def get_activation_map() -> dict:
    """Manifest activation declarations, keyed by plugin id. Cached: manifests are read off
    disk and only change when plugins are installed, which restarts the UI workers.

    # ponytail: a disk-scan failure here (not a single bad plugin.json — iter_plugin_activations
    # already isolates those — but e.g. the whole core plugin directory being unreadable) drops
    # to tier 3 for every plugin, which reads `errors`/`headers`/`misc`/`pro`/`sessions`/`ssl` as
    # inactive (none declare a USE_* setting). Accepted: this is a scan-directory-level fault,
    # not a per-plugin one, so it already implies something is badly wrong with the plugin tree;
    # upgrade path is a second hardcoded `_SYNTHESIZED_ALWAYS_ON`-style fallback set if a bare
    # "conventions only" mode ever needs to keep reporting these as active during an outage.
    """
    try:
        return iter_plugin_activations()
    except Exception:  # a broken plugin tree must not take the plugins page down
        LOGGER.exception("Could not read plugin activation manifests, falling back to conventions")
        return {}


def is_plugin_active(plugin_id: str, plugin_name: str, config: dict) -> bool:
    """Is this plugin doing anything for this config?

    Three tiers, in order:
      1. ``extensions.activation`` map in the plugin's own manifest — active when ANY declared
         setting differs from its declared inactive value.
      2. ``extensions.activation: "always"`` — always active, no switch.
      3. the legacy ``USE_<ID>`` / ``USE_<NAME>`` naming convention. This tier is load-bearing:
         it is what every plugin that declares nothing relies on, including every third-party
         plugin until it opts in.
    """
    if plugin_id in _SYNTHESIZED_ALWAYS_ON:
        return True

    declaration = get_activation_map().get(plugin_id)
    if declaration == "always":
        return True
    if isinstance(declaration, dict):
        return any(config.get(key, {"value": inactive})["value"] != inactive for key, inactive in declaration.items())

    plugin_name_formatted = plugin_name.replace(" ", "_").upper()
    return config.get(f"USE_{plugin_id.upper()}", config.get(f"USE_{plugin_name_formatted}", {"value": "no"}))["value"] != "no"


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


# Revoked UI session ids are kept in the same store that backs Flask-Session -- Redis when
# USE_REDIS=yes, otherwise the SafeFileSystemCache under LIB_DIR -- so revocation gets exactly the
# durability and the sharing of the sessions it guards. They used to live in DATA, which is
# file-backed under /var/tmp (outside the container's persistent volume) and per-container, so a
# container recreate forgot every revocation while the session entries under LIB_DIR survived, and
# revocation never propagated across UI replicas.
# The backend expires the keys itself, so there is no pruning to do here. A revoked id only needs
# to be retained until the session it names can no longer exist, i.e. the maximum session lifetime.
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


def _session_store_backend():
    """``(redis_client, key_prefix)`` or ``(cachelib_cache, None)``, whichever backs Flask-Session.

    Same two-branch shape as main.py's ``_delete_session_store_entry``. ``(None, None)`` if the
    session interface exposes neither, which only happens if the backend failed to initialise.
    """
    interface = getattr(current_app, "session_interface", None)
    client = getattr(interface, "client", None)
    if client is not None:
        return client, getattr(interface, "key_prefix", "") or ""
    return getattr(interface, "cache", None), None


def _revoked_session_key(session_id, prefix) -> str:
    return f"{prefix}revoked:{session_id}" if prefix is not None else f"revoked:{session_id}"


def revoke_sessions(ids) -> str:
    """Mark session ids revoked for as long as the sessions they name can still exist.

    Returns "" on success or an error string, matching the Database method convention, so a
    caller that must not silently half-revoke (wipe-other-sessions) can surface the failure.
    """
    ids = [sid for sid in ids if sid]
    if not ids:
        return ""

    backend, prefix = _session_store_backend()
    if backend is None:
        return "No session backend available to record the revocation"

    ttl = _revoked_session_ttl_seconds()
    try:
        for sid in ids:
            key = _revoked_session_key(sid, prefix)
            if prefix is not None:
                backend.setex(key, ttl, b"1")
            else:
                backend.set(key, True, timeout=ttl)
    except BaseException as e:
        LOGGER.exception("Couldn't record revoked session ids")
        return str(e)

    return ""


def is_session_revoked(session_id) -> bool:
    """Whether this session id has been revoked. Checked on every authenticated request.

    Fails open on a backend error, which is safe here: the same backend stores the sessions
    themselves, so if it is unreachable the session cannot be loaded and the request is
    unauthenticated long before this check runs.
    """
    if not session_id:
        return False

    backend, prefix = _session_store_backend()
    if backend is None:
        return False

    key = _revoked_session_key(session_id, prefix)
    try:
        if prefix is not None:
            return bool(backend.exists(key))
        return bool(backend.get(key))
    except BaseException:
        LOGGER.exception(f"Couldn't check whether session {session_id} is revoked")
        return False


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
