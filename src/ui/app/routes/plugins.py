from contextlib import suppress
from html import escape
from importlib.machinery import SourceFileLoader
from io import BytesIO
from json import JSONDecodeError, loads as json_loads
from os import listdir
from os.path import basename, dirname, isabs, join, sep
from pathlib import Path
from re import compile as re_compile
from shutil import move, rmtree
from sys import path as sys_path
from tarfile import CompressionError, HeaderError, ReadError, TarError, open as tar_open
from time import time
from typing import Dict, List, Mapping, Optional, Union
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from flask import Blueprint, Response, current_app, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from jinja2 import Environment, FileSystemLoader, select_autoescape
from werkzeug.routing import BuildError
from werkzeug.utils import secure_filename

from common_utils import bytes_hash, create_plugin_tar_gz, safe_tar_extractall, safe_zip_extractall  # type: ignore

from app.dependencies import (
    API_CLIENT,
    CORE_PLUGINS_PATH,
    BW_CONFIG,
    BW_INSTANCES_UTILS,
    CONFIG_TASKS_EXECUTOR,
    DATA,
    EXTERNAL_PLUGINS_PATH,
    PRO_PLUGINS_PATH,
)
from app.api_client import ApiClientError, ApiUnavailableError
from app.utils import LOGGER, PLUGIN_NAME_RX, TMP_DIR, get_activation_map, is_plugin_active

from app.routes.utils import PLUGIN_KEYS, error_message, handle_error, verify_data_in_form, wait_applying

plugins = Blueprint("plugins", __name__)

# Only a master USE_* toggle may be flipped through /plugins/enable's core path.
USE_SETTING_RX = re_compile(r"^USE_[A-Z0-9_]+$")

# Plugin ids that ship a curated brand icon (static/img/plugins/plugin-<id>.svg AND its
# -white dark variant). Listed once at import time — these are shipped assets, not runtime
# state. The marketplace card renders both <img> variants for ids in this set and falls back
# to the boxicon for everything else, so no card can ever point at a missing file in either
# theme (require both variants below). Kept independent of the DB `icon` field on purpose:
# the card serves these static marks by id, so do NOT collapse this into plugin_data.icon —
# that would reintroduce the missing-file / broken-image risk this existence check prevents.
_ICON_DIR = Path(__file__).resolve().parent.parent / "static" / "img" / "plugins"
_ICON_LIGHT = {p.stem.removeprefix("plugin-") for p in _ICON_DIR.glob("plugin-*.svg") if not p.stem.endswith("-white")}
_ICON_DARK = {p.stem.removeprefix("plugin-").removesuffix("-white") for p in _ICON_DIR.glob("plugin-*-white.svg")}
CUSTOM_PLUGIN_ICONS = frozenset(_ICON_LIGHT & _ICON_DARK)
# Every static icon filename actually on disk, so the field-first template can serve a plugin.json
# ``icon`` that names a bare ``*.svg`` static asset only when the file exists (no broken <img>),
# and otherwise fall back to a boxicon. Existence-checked at import for the same reason as above.
STATIC_PLUGIN_ICONS = frozenset(p.name for p in _ICON_DIR.glob("*.svg"))


@plugins.route("/plugins", methods=["GET"])
@login_required
def plugins_page():
    tmp_ui_path = TMP_DIR.joinpath("ui")
    # Remove everything in the tmp folder
    rmtree(tmp_ui_path, ignore_errors=True)
    tmp_ui_path.mkdir(parents=True, exist_ok=True)
    # `plugins`/`config` come from the global before_request context; pass the manifest-driven
    # activation map the marketplace grid needs to decide how each core card's switch behaves
    # (locked "always on" chip vs. a toggle vs. a non-toggleable state badge).
    #
    # `activation_toggles` names, per map-declared plugin, the key its switch posts -- it exists
    # only for the plugins the shared activation writer can flip BOTH ways, so "map-declared" is
    # no longer a blanket reason to render the read-only badge. Definitions come off `g._env`
    # (main.py:1314), which already holds this request's `BW_CONFIG.get_plugins()` payload -- no
    # extra round-trip, and no new failure mode. An `_env` without plugins yields no toggles at
    # all, i.e. every map-declared card degrades to the read-only badge.
    definitions = env_setting_definitions()
    activation_toggles = {plugin_id: key for plugin_id in get_activation_map() if (key := activation_toggle_setting(plugin_id, definitions))}

    return render_template(
        "plugins.html",
        plugin_activations=get_activation_map(),
        activation_toggles=activation_toggles,
        custom_icons=CUSTOM_PLUGIN_ICONS,
        static_icons=STATIC_PLUGIN_ICONS,
    )


# Same three neutralizing headers the API sets on an icon response: the bytes are
# attacker-controlled for external/pro plugins, so on top of <img src>-only intended usage we
# stop any script in an SVG from executing on direct navigation (CSP default-src 'none'; sandbox),
# block MIME confusion (nosniff), and quote the filename. Serving name is fixed to icon.<ext>.
def _icon_response_headers(content_type: str) -> dict:
    ext = "png" if content_type == "image/png" else "svg"
    return {
        "Content-Type": content_type,
        "Content-Disposition": f'inline; filename="icon.{ext}"',
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "Cache-Control": "private, max-age=3600",
    }


@plugins.route("/plugins/<string:plugin>/icon", methods=["GET"])
@login_required
def plugin_icon(plugin: str):
    """Proxy a plugin's shipped icon from the API (browsers can't authenticate to the API).

    The marketplace card's ``@file/<name>`` icons point here. ``plugin`` is validated against the
    same id regex as every other plugin route (no slashes -> no traversal), the bytes come from
    ``GET /plugins/<id>/icon`` on the API, and the response re-serves them with the same security
    headers plus a short private cache. A missing/unservable icon maps to 404, an unreachable API
    to 502."""
    if not PLUGIN_NAME_RX.match(plugin):
        return Response("Invalid plugin id", 404)
    try:
        content, content_type = API_CLIENT.get_plugin_icon(plugin)
    except ApiClientError as e:
        return Response("Plugin icon not found", e.status_code or 404)
    except ApiUnavailableError:
        return Response("Plugin icon unavailable", 502)
    return Response(content, headers=_icon_response_headers(content_type))


@plugins.route("/plugins/delete", methods=["POST"])
@login_required
def delete_plugin():
    if API_CLIENT.readonly:
        return Response("Database is in read-only mode", 403)

    if not current_user.admin:
        return Response("Plugin management is restricted to administrators", 403)

    verify_data_in_form(
        data={"plugins": None},
        err_message="Missing plugins parameter on /plugins/delete.",
        redirect_url="plugins",
        next=True,
    )
    DATA.load_from_file()

    plugins = request.form["plugins"].split(",")

    def update_plugins(plugins: List[str]):
        wait_applying()

        try:
            deleted_plugins = []
            for plugin in plugins:
                try:
                    API_CLIENT.delete_plugin(plugin)
                    DATA["TO_FLASH"].append({"content": f"Deleted plugin {plugin} successfully", "type": "success"})
                    deleted_plugins.append(plugin)
                except ApiClientError as e:
                    if "not found" in e.message.lower() or "does not exist" in e.message.lower():
                        message = f"Plugin with id {plugin} not found"
                    else:
                        message = f"Couldn't delete plugin {plugin} in database: {e.message}"
                    DATA["TO_FLASH"].append({"content": message, "type": "error"})
                except ApiUnavailableError as e:
                    DATA["TO_FLASH"].append({"content": f"Couldn't delete plugin {plugin}: {e.message}", "type": "error"})

            if deleted_plugins:
                with suppress(ApiClientError, ApiUnavailableError):
                    API_CLIENT.checked_changes(["config"], plugins_changes=deleted_plugins.copy(), value=True)
        finally:
            # Always clear the loading-page flag, even if something above raised unexpectedly.
            # This runs on a bare ThreadPoolExecutor whose futures are never retrieved (see
            # toggle_plugin below), so an uncaught exception here would otherwise strand the
            # user on /loading until the 60s watchdog in main.py clears RELOADING.
            DATA["RELOADING"] = False

    DATA.update({"RELOADING": True, "LAST_RELOAD": time()})

    CONFIG_TASKS_EXECUTOR.submit(update_plugins, plugins)

    return redirect(url_for("loading", next=url_for("plugins.plugins_page"), message=f"Deleting plugins: {', '.join(plugins)}"))


def _active_value_for(setting_id: str, inactive: str, definitions: Dict[str, dict]) -> str:
    """Derive a schema-legal active value for ``setting_id`` given its inactive value.

    ``definitions`` is a ``{setting_id: definition}`` map in the shape
    ``models/select_setting.html`` already renders from (a select-typed
    entry carries ``"type": "select"`` and ``"select": [option, ...]``). Always passed in, never
    fetched here. Raises ``ValueError`` when no schema-legal active value can be derived (free-text
    settings such as ``INJECT_BODY``/``REMOTE_PHP`` have no such value).
    """
    definition = definitions.get(setting_id) or {}
    setting_type = definition.get("type")

    if setting_type == "select":
        for option in definition.get("select") or []:
            if option != inactive:
                return option
        raise ValueError(f"{setting_id!r} has no select option distinct from its inactive value {inactive!r}")

    if setting_type == "check":
        return "no" if inactive == "yes" else "yes"

    raise ValueError(f"{setting_id!r} (type={setting_type!r}) has no derivable active value; not safe to enable from a switch")


def _is_list_shaped(definition: dict) -> bool:
    """Whether an activation key holds a LIST, and so can never be driven by one switch.

    Two shapes, refused for two different reasons, in BOTH directions:

    * ``multiple`` -- the real values live under ``<KEY>_<n>`` (redirect's ``REDIRECT_TO``), so
      writing the bare base name claims "off" while every suffixed redirect keeps serving
      (``core/redirect/confs/server-http/redirect.conf`` iterates them all).
    * ``multiselect`` / ``multivalue`` -- a list has no single schema-legal "active" value to
      derive, and country's BLACKLIST_COUNTRY/WHITELIST_COUNTRY are the live case.

    Locked with the PO: those rows get a count + chevron, never a switch. Deliberately the same
    test and the same set as ``shelf_plugin_scope``'s (``routes/services.py``) -- the shelf leaves
    them out of its declared scope, so a write here would post a key the page does not own.
    """
    return bool(definition.get("multiple")) or definition.get("type") in ("multiselect", "multivalue")


def resolve_activation_write(
    plugin_id: str,
    setting: Optional[str],
    *,
    enabled: bool,
    settings: Dict[str, dict],
    current_values: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    """Values to write to flip ``plugin_id`` on or off, derived from its declared activation.

    ONE writer for two surfaces: the ``/plugins`` marketplace grid (``POST /plugins/enable``) and
    the compose shelf. Both need EVERY declared key in the returned dict on every activation
    change, because the shelf's declared scope owns every key ``shelf_plugin_scope``
    (``routes/services.py``) returns, and an in-scope key the form does not post has its row
    DELETED (``db_methods/config_save.py:592``).

    * **OFF** writes every declared key at its declared inactive value. ``limit``'s
      ``USE_LIMIT_CONN`` gates ``limitconn.conf`` independently of ``USE_LIMIT_REQ``, so a partial
      OFF keeps enforcing after the UI claims the plugin is off.
    * **ON** writes the toggled key at a schema-legal active value and every SIBLING at its
      current resolved value from ``current_values`` -- a no-op write whose only job is to keep
      the row alive. Dropping a sibling deletes it and falls it back to its default, which for
      ``USE_LIMIT_CONN`` is ``"yes"``: enabling the plugin would silently switch the connection
      limiter on too. A sibling MISSING from ``current_values`` therefore **raises** rather than
      guessing -- falling back to the schema default is the very clobber this rule exists to
      prevent, and ``Database.py:463`` lets an ``api`` write overwrite a ``ui`` one, so the guess
      would land. Fail closed: an aborted toggle flashes an error, a wrong one silently re-arms a
      limiter the operator turned off.
    * ON is NOT the exact inverse of OFF for a multi-key plugin: OFF drives every key to its
      inactive value, so a following ON restores only the toggled key and leaves the siblings off.
      That is inherent to one switch owning several keys -- the per-plugin page is where the
      siblings come back.
    * A ``multiple`` / multiselect / multivalue activation key is refused in both directions, and
      refused for the WHOLE plugin (see ``_is_list_shaped``): the row carries one control, so
      there is no half state to drift into.
    * Undeclared plugins (no manifest entry) keep the legacy convention: a plain ``USE_<ID>``
      boolean, still guarded by ``USE_SETTING_RX``.
    * A plugin declared ``"always"`` (no switch, ever -- mirrors ``plugins.html``'s ``is_always``)
      is refused outright: it must never be flippable through this endpoint, even by a crafted
      ``setting`` that happens to match the ``USE_<ID>`` convention.

    ``settings`` is REQUIRED, and is this request's ``{setting_id: definition}`` map -- use
    ``env_setting_definitions()``. It has no default on purpose: the one it used to have
    (``BW_CONFIG.get_plugins_settings()``) had zero production callers left once both surfaces
    sourced from ``g._env``, and leaving it would let a caller silently re-add a per-call API
    round-trip that no test would catch.
    """
    declaration = get_activation_map().get(plugin_id)
    if declaration == "always":
        raise ValueError(f"{plugin_id!r} is always active and cannot be toggled")
    if not isinstance(declaration, dict):
        if not setting or not USE_SETTING_RX.match(setting):
            raise ValueError(f"No activation declaration and no conventional setting for {plugin_id!r}")
        return {setting: "yes" if enabled else "no"}

    if setting is not None and setting not in declaration:
        raise ValueError(f"{setting!r} is not an activation setting of {plugin_id!r}")

    for key in declaration:
        # A MISSING schema is not a scalar one. `_is_list_shaped({})` is False, so reading an
        # absent definition as "not list-shaped" makes this refusal fail OPEN on exactly the input
        # the sibling rule below fails CLOSED on -- and `main.py:1262-1265` parks `{}` whenever the
        # per-request get_plugins() failed, so it is reachable: measured, `redirect` OFF then wrote
        # REDIRECT_TO="" while every REDIRECT_TO_<n> kept serving, and `country` OFF wiped both
        # lists. Same missing-input condition, same failure mode: refuse.
        definition = settings.get(key)
        if definition is None:
            raise ValueError(f"no schema for {key!r}; refusing to flip {plugin_id!r} on an unknown setting shape")
        if _is_list_shaped(definition):
            raise ValueError(f"{plugin_id!r} activates through {key!r}, a list-shaped setting that no single switch can flip")

    if not enabled:
        return dict(declaration)

    # Insertion order is manifest order, so "the first declared key" is well-defined and stable
    # for a caller that has no particular key in mind (the shelf's one-switch row).
    toggled = setting or next(iter(declaration))
    values: Dict[str, str] = {}
    for key, inactive in declaration.items():
        if key == toggled:
            values[key] = _active_value_for(key, inactive, settings)
            continue
        if current_values is None or key not in current_values:
            raise ValueError(f"no current value for {key!r}; refusing to guess a sibling of {plugin_id!r}'s activation")
        values[key] = current_values[key]
    return values


def is_activation_setting(plugin_id: str, setting: str) -> bool:
    """Whether ``setting`` is a legal activation key to flip ``plugin_id`` through.

    A map-declared plugin's legal set is exactly the keys it declares -- tighter than
    ``USE_SETTING_RX`` for a given plugin, and the only way ``AUTO_LETS_ENCRYPT`` /
    ``GENERATE_SELF_SIGNED_SSL`` can reach the writer at all, since neither matches the
    ``USE_<...>`` convention. Everything else keeps the regex.

    **Bound, stated honestly:** this delegates the guard to the MANIFEST, and
    ``iter_plugin_activations`` does not check that a declared key belongs to the plugin declaring
    it (``src/common/utils/plugin_extensions.py:214-216`` type-checks only, and is deliberately not
    gated by ``is_trusted``). So an installed plugin declaring ``{"SERVER_NAME": ""}`` is accepted
    here and its OFF path writes that key -- measured. It is NOT a privilege boundary: reaching it
    already requires having installed a plugin that runs Python jobs. Zero shipped core manifests
    declare a foreign key. The root fix is an ownership filter in ``iter_plugin_activations``,
    where ``is_plugin_active`` and ``shelf_plugin_scope`` inherit the same trust; do not re-derive
    it here.
    """
    declaration = get_activation_map().get(plugin_id)
    if isinstance(declaration, dict):
        return setting in declaration
    return bool(USE_SETTING_RX.match(setting))


def activation_toggle_setting(plugin_id: str, settings: Dict[str, dict]) -> Optional[str]:
    """The activation key a single on/off switch may flip for ``plugin_id``, or None if none fits.

    Asks the writer rather than re-deriving its rules, so the control a surface renders and the
    values that surface writes can never disagree: ``country`` (multiselect), ``redirect``
    (multiple), ``inject`` and ``php`` (free text, no derivable active value) come back None and
    keep the marketplace's read-only Active/Inactive badge; ``antibot``, ``customcert``,
    ``letsencrypt``, ``selfsigned`` and ``limit`` come back with the key their switch posts.

    **A returned key does NOT mean "render a binary switch."** It means "one control may own this
    plugin"; the CONTROL SHAPE is the key's own `type`. ``USE_ANTIBOT`` is a 9-value select, and
    plan D2 gives that a MODE PICKER, not a switch -- a switch there silently selects "cookie", the
    first non-inactive option in manifest order (pinned by
    ``test_enabling_antibot_from_a_switch_picks_cookie``). The `/plugins` marketplace is binary by
    design and accepts that; any surface that is not must read ``settings[key]["type"]`` itself.

    None for an undeclared plugin too: those keep the template's own ``USE_<ID> in config``
    convention, which needs no schema.
    """
    declaration = get_activation_map().get(plugin_id)
    if not isinstance(declaration, dict):
        return None
    try:
        # The declaration itself is a legal, COMPLETE set of current values (every key at its
        # inactive value), so the probe never trips the writer's fail-closed sibling rule while
        # still exercising every other rule it enforces.
        resolve_activation_write(plugin_id, None, enabled=True, current_values=dict(declaration), settings=settings)
        resolve_activation_write(plugin_id, None, enabled=False, settings=settings)
    except ValueError:
        return None
    return next(iter(declaration))


def env_setting_definitions() -> Dict[str, dict]:
    """This request's flattened `{setting_id: definition}`, off `g._env` -- no API round-trip.

    `main.py:1263` already fetches `BW_CONFIG.get_plugins()` per request and parks it on `g._env`
    (`:1314`); each plugin entry carries its own `settings` with the `type` / `select` / `multiple`
    fields the activation writer reads (`db_methods/plugins.py:204-231`). Every activation key
    belongs to the plugin declaring it (pinned by
    `tests/unit/common/test_plugin_activations.py::test_declared_settings_exist_in_their_own_plugin`),
    so flattening the plugin payloads is complete for this purpose and `settings.json`'s globals
    are not needed. An absent `_env` yields `{}`, which makes every derivation fail closed.
    """
    return {key: data for entry in (getattr(g, "_env", {}).get("plugins") or {}).values() for key, data in (entry.get("settings") or {}).items()}


def env_current_values() -> Dict[str, str]:
    """This request's resolved global config flattened to `{setting_id: value}`, off `g._env`.

    `main.py:1297` fetches it with `methods=True`, so entries are `{"value", "method", ...}` dicts;
    every multisite setting is present, seeded from its default (`config_read.py:309-316`). Read in
    the REQUEST thread and handed to the executor, because `g` is gone by the time the task runs.
    """
    return {key: entry["value"] for key, entry in (getattr(g, "_env", {}).get("config") or {}).items() if isinstance(entry, dict) and "value" in entry}


@plugins.route("/plugins/enable", methods=["POST"])
@login_required
def enable_plugin():
    if API_CLIENT.readonly:
        return Response("Database is in read-only mode", 403)

    if not current_user.admin:
        return Response("Plugin management is restricted to administrators", 403)

    verify_data_in_form(
        data={"plugin": None, "enabled": None},
        err_message="Missing plugin or enabled parameter on /plugins/enable.",
        redirect_url="plugins",
        next=True,
    )
    DATA.load_from_file()

    plugin = request.form["plugin"]
    enabled = request.form["enabled"].strip().lower() in ("1", "true", "yes", "on")
    # Core plugins can't be DB-toggled (structurally required); the grid instead binds their
    # switch to one of the plugin's activation settings and passes its name here. Anything the
    # plugin does not declare (or, undeclared, anything failing USE_SETTING_RX) is rejected -- see
    # is_activation_setting for the one bound that guard does NOT give you: it trusts the manifest
    # to declare only its own keys, which nothing currently enforces.
    setting = request.form.get("setting", "").strip()
    if setting and not is_activation_setting(plugin, setting):
        return handle_error("Invalid setting parameter on /plugins/enable.", "plugins", True)

    # Read in the REQUEST thread: `g` is gone inside the executor. Both come off `g._env`, which
    # this request already paid for, so the toggle adds no round-trip -- and an empty `_env` makes
    # the writer raise instead of guessing a sibling's value.
    definitions = env_setting_definitions()
    current_values = env_current_values()

    def toggle_plugin(plugin: str, enabled: bool, setting: str):
        wait_applying()

        try:
            if setting:
                # Core plugin: write every value the manifest's activation declares (or, absent
                # one, the conventional USE_* boolean) instead of blindly writing "yes"/"no" --
                # a select-typed master setting (e.g. USE_ANTIBOT) has no legal "yes" value.
                # Enabling a MULTI-key activation also rewrites its siblings at their CURRENT
                # value; letting them fall back to their schema defaults would switch limit's
                # connection limiter back on behind an operator who had deliberately turned it off.
                API_CLIENT.update_global_settings(
                    resolve_activation_write(plugin, setting, enabled=enabled, current_values=current_values, settings=definitions)
                )
            else:
                # External/ui/pro plugin: flip the DB `enabled` flag.
                API_CLIENT.set_plugin_enabled(plugin, enabled)
                with suppress(ApiClientError, ApiUnavailableError):
                    API_CLIENT.checked_changes(["config"], plugins_changes=[plugin], value=True)
            state = "enabled" if enabled else "disabled"
            DATA["TO_FLASH"].append({"content": f"Plugin {plugin} {state} successfully", "type": "success"})
        except (ApiClientError, ApiUnavailableError) as e:
            DATA["TO_FLASH"].append({"content": f"Couldn't update plugin {plugin}: {e.message}", "type": "error"})
        except ValueError as e:
            # resolve_activation_write rejects an illegal toggle (an "always" plugin, a
            # multi-key or undeclared activation setting, a free-text activation). This must
            # be caught explicitly and not just relegated to the finally below: left uncaught,
            # it vanished with no log and no flash on this bare ThreadPoolExecutor (whose
            # futures are never retrieved), stranding the user on /loading until the 60s
            # watchdog in main.py cleared RELOADING.
            LOGGER.error(f"Rejected plugin toggle for {plugin!r}: {e}")
            DATA["TO_FLASH"].append({"content": f"Couldn't update plugin {plugin}: {e}", "type": "error"})
        finally:
            DATA["RELOADING"] = False

    DATA.update({"RELOADING": True, "LAST_RELOAD": time()})

    CONFIG_TASKS_EXECUTOR.submit(toggle_plugin, plugin, enabled, setting)

    action = "Enabling" if enabled else "Disabling"
    return redirect(url_for("loading", next=url_for("plugins.plugins_page"), message=f"{action} plugin: {plugin}"))


def get_plugin_path(plugin_id: str) -> Optional[Path]:
    """
    Find the filesystem path for a plugin given its ID.
    First checks in pro plugins path, then in external plugins path.

    Args:
        plugin_id: The plugin ID to search for

    Returns:
        Path object if found, None otherwise
    """
    # Look in pro plugins first (higher priority)
    pro_path = PRO_PLUGINS_PATH / plugin_id
    if (pro_path / "ui").exists():
        return pro_path

    # Then look in external plugins
    ext_path = EXTERNAL_PLUGINS_PATH / plugin_id
    if (ext_path / "ui").exists():
        return ext_path

    # And finally in core plugins
    core_path = CORE_PLUGINS_PATH / plugin_id
    if (core_path / "ui").exists():
        return core_path

    # Plugin not found in filesystem
    return None


def run_action(plugin: str, function_name: str = "", *, tmp_dir: Optional[Path] = None) -> Union[dict, Response]:
    message = ""

    # Try to load from filesystem first if tmp_dir is not provided
    if not tmp_dir:
        plugin_path = get_plugin_path(plugin)

        if plugin_path and (plugin_path / "ui" / "actions.py").exists():
            # Plugin exists in filesystem
            tmp_dir = plugin_path / "ui"
        else:
            # Fall back to API if not found in filesystem
            try:
                page = API_CLIENT.get_plugin_page(plugin)
            except (ApiClientError, ApiUnavailableError):
                page = None

            if not page:
                return {"status": "ko", "code": 404, "message": "The plugin does not have a page"}

            try:
                # Extract from API blob
                tmp_dir = TMP_DIR.joinpath("ui", "action", str(uuid4()))
                tmp_dir.mkdir(parents=True, exist_ok=True)

                with tar_open(fileobj=BytesIO(page), mode="r:gz") as tar:
                    # Validate all members before extracting any
                    tmp_dir_resolved = tmp_dir.resolve()
                    for member in tar.getmembers():
                        if member.name.startswith("/") or ".." in Path(member.name).parts:
                            return {"status": "ko", "code": 400, "message": "Invalid file path"}
                        if not tmp_dir.joinpath(member.name).resolve().is_relative_to(tmp_dir_resolved):
                            return {"status": "ko", "code": 400, "message": "Invalid file path"}

                    safe_tar_extractall(tar, tmp_dir)

                tmp_dir = tmp_dir.joinpath("ui")
            except BaseException as e:
                LOGGER.error(f"An error occurred while extracting the plugin: {e}")
                return {"status": "ko", "code": 500, "message": "An error occurred while extracting the plugin, see logs for more details"}

    try:
        action_file = tmp_dir.joinpath("actions.py")
        if not action_file.is_file():
            if function_name == "pre_render":
                # Mirror the missing pre_render method case: a plugin without an actions file is not a pre-render error
                return {"status": "ok", "code": 200, "message": "The plugin does not have an action file"}
            return {"status": "ko", "code": 404, "message": "The plugin does not have an action file"}

        sys_path.append(tmp_dir.as_posix())
        loader = SourceFileLoader("actions", action_file.as_posix())
        actions = loader.load_module()
    except BaseException as e:
        sys_path.pop()
        if function_name != "pre_render" and not str(tmp_dir).startswith((str(EXTERNAL_PLUGINS_PATH), str(PRO_PLUGINS_PATH))):
            rmtree(tmp_dir, ignore_errors=True)
            TMP_DIR.joinpath("ui").mkdir(parents=True, exist_ok=True)

        LOGGER.error(f"An error occurred while importing the plugin: {e}")
        return {"status": "ko", "code": 500, "message": "An error occurred while importing the plugin, see logs for more details"}

    exception = None
    res = None
    message = None

    try:
        # Try to get the custom plugin custom function and call it
        method = getattr(actions, function_name or plugin)
        queries = request.args.to_dict()
        try:
            data = request.json or {}
        except BaseException:
            data = {}

        res = method(app=current_app, db=None, bw_instances_utils=BW_INSTANCES_UTILS, args=queries, data=data)
    except AttributeError as e:
        if function_name == "pre_render":
            sys_path.pop()
            return {"status": "ok", "code": 200, "message": "The plugin does not have a pre_render method"}

        message = "The plugin does not have a method"
        exception = e
    except BaseException as e:
        message = "An error occurred while executing the plugin"
        exception = e
    finally:
        sys_path.pop()

        # Only clean up temporary directories that aren't permanent plugin paths
        if function_name != "pre_render" and not str(tmp_dir).startswith((str(EXTERNAL_PLUGINS_PATH), str(PRO_PLUGINS_PATH))):
            rmtree(tmp_dir, ignore_errors=True)
            TMP_DIR.joinpath("ui").mkdir(parents=True, exist_ok=True)

    if message:
        LOGGER.error(message + (f": {exception}" if exception else ""))
    if message or not isinstance(res, dict) and not res:
        return {
            "status": "ko",
            "code": 500,
            "message": message + ", see logs for more details" if message else "The plugin did not return a valid response",
        }

    if isinstance(res, Response):
        return res

    return {"status": "ok", "code": 200, "data": res}


@plugins.route("/plugins/refresh", methods=["POST"])
@login_required
def plugins_refresh():
    if API_CLIENT.readonly:
        return handle_error("Database is in read-only mode", "plugins")

    if not current_user.admin:
        return handle_error("Plugin management is restricted to administrators", "plugins")

    tmp_ui_path = TMP_DIR.joinpath("ui")

    verify_data_in_form(
        data={"csrf_token": None},
        err_message="Missing csrf_token parameter on /plugins.",
        redirect_url="plugins",
        next=True,
    )

    # Upload plugins
    if not tmp_ui_path.exists() or not listdir(str(tmp_ui_path)):
        return handle_error("Please upload new plugins to reload plugins", "plugins", True)
    DATA.load_from_file()

    errors = 0
    files_count = 0
    new_plugins = []
    new_plugins_ids = []

    for file in listdir(str(tmp_ui_path)):
        if not tmp_ui_path.joinpath(file).is_file():
            continue

        files_count += 1
        folder_name = ""
        temp_folder_name = file.split(".")[0]
        temp_folder_path = tmp_ui_path.joinpath(temp_folder_name)
        is_dir = False

        try:
            if file.endswith(".zip"):
                try:
                    with ZipFile(str(tmp_ui_path.joinpath(file))) as zip_file:
                        try:
                            zip_file.getinfo("plugin.json")
                        except KeyError:
                            is_dir = True
                        safe_zip_extractall(zip_file, str(temp_folder_path))
                except BadZipFile:
                    errors += 1
                    message = f"{file} is not a valid zip file. ({folder_name or temp_folder_name})"
                    LOGGER.exception(message)
                    DATA["TO_FLASH"].append({"content": f"{message}, check logs for more details", "type": "error", "save": False})
            else:
                try:
                    with tar_open(str(tmp_ui_path.joinpath(file)), errorlevel=2) as tar_file:
                        try:
                            tar_file.getmember("plugin.json")
                        except KeyError:
                            is_dir = True
                        safe_tar_extractall(tar_file, str(temp_folder_path))
                except ReadError:
                    errors += 1
                    message = f"Couldn't read file {file} ({folder_name or temp_folder_name})"
                    LOGGER.exception(message)
                    DATA["TO_FLASH"].append({"content": f"{message}, check logs for more details", "type": "error", "save": False})
                except CompressionError:
                    errors += 1
                    message = f"{file} is not a valid tar file ({folder_name or temp_folder_name})"
                    LOGGER.exception(message)
                    DATA["TO_FLASH"].append({"content": f"{message}, check logs for more details", "type": "error", "save": False})
                except HeaderError:
                    errors += 1
                    message = f"The file plugin.json in {file} is not valid ({folder_name or temp_folder_name})"
                    LOGGER.exception(message)
                    DATA["TO_FLASH"].append({"content": f"{message}, check logs for more details", "type": "error", "save": False})

            if is_dir:
                dirs = [d for d in listdir(str(temp_folder_path)) if temp_folder_path.joinpath(d).is_dir()]

                if not dirs or len(dirs) > 1 or not temp_folder_path.joinpath(dirs[0], "plugin.json").is_file():
                    raise KeyError

                for file_name in listdir(str(temp_folder_path.joinpath(dirs[0]))):
                    move(
                        str(temp_folder_path.joinpath(dirs[0], file_name)),
                        str(temp_folder_path.joinpath(file_name)),
                    )
                rmtree(
                    str(temp_folder_path.joinpath(dirs[0])),
                    ignore_errors=True,
                )

            plugin_file = json_loads(temp_folder_path.joinpath("plugin.json").read_text(encoding="utf-8"))

            if not all(key in plugin_file.keys() for key in PLUGIN_KEYS):
                raise ValueError

            folder_name = plugin_file["id"]

            if not PLUGIN_NAME_RX.match(folder_name):
                errors += 1
                DATA["TO_FLASH"].append(
                    {
                        "content": f"Invalid plugin name for {temp_folder_name}. (Can only contain numbers, letters, underscores and hyphens (min 4 characters and max 64))",
                        "type": "error",
                        "save": False,
                    }
                )
                raise Exception

            plugin_content = create_plugin_tar_gz(temp_folder_path, arc_root=temp_folder_name)
            value = plugin_content.getvalue()

            new_plugins.append(
                plugin_file
                | {
                    "type": "ui",
                    "page": "ui" in listdir(str(temp_folder_path)),
                    "method": "ui",
                    "data": value,
                    "checksum": bytes_hash(value, algorithm="sha256"),
                }
            )
            new_plugins_ids.append(folder_name)
        except KeyError:
            errors += 1
            DATA["TO_FLASH"].append(
                {
                    "content": f"{file} is not a valid plugin (plugin.json file is missing) ({folder_name or temp_folder_name})",
                    "type": "error",
                    "save": False,
                }
            )
        except JSONDecodeError as e:
            errors += 1
            DATA["TO_FLASH"].append(
                {
                    "content": f"The file plugin.json in {file} is not valid ({e.msg}: line {e.lineno} column {e.colno} (char {e.pos})) ({folder_name or temp_folder_name})",
                    "type": "error",
                    "save": False,
                }
            )
        except ValueError:
            errors += 1
            DATA["TO_FLASH"].append(
                {
                    "content": f"The file plugin.json is missing one or more of the following keys: <i>{', '.join(PLUGIN_KEYS)}</i> ({folder_name or temp_folder_name})",
                    "type": "error",
                    "save": False,
                }
            )
        except FileExistsError:
            errors += 1
            DATA["TO_FLASH"].append({"content": f"A plugin named {folder_name} already exists", "type": "error", "save": False})
        except (TarError, OSError) as e:
            errors += 1
            DATA["TO_FLASH"].append({"content": str(e), "type": "error", "save": False})
        except Exception as e:
            errors += 1
            DATA["TO_FLASH"].append({"content": str(e), "type": "error", "save": False})

    if errors >= files_count:
        return redirect(url_for("loading", next=url_for("plugins.plugins_page")))

    def update_plugins():
        wait_applying()

        plugins = BW_CONFIG.get_plugins(_type="ui", with_data=True)
        for plugin in plugins:
            if plugin in new_plugins_ids:
                DATA["TO_FLASH"].append({"content": f"Plugin {plugin} already exists", "type": "error"})
                del new_plugins[new_plugins_ids.index(plugin)]

        if not new_plugins:
            DATA["RELOADING"] = False
            return

        # Upload each plugin's tar.gz data via the API upload endpoint
        upload_files = []
        for plugin in new_plugins:
            plugin_data = plugin.get("data", b"")
            if plugin_data:
                upload_files.append(("files", (f"{plugin['id']}.tar.gz", BytesIO(plugin_data), "application/gzip")))

        if upload_files:
            try:
                result = API_CLIENT.upload_plugins(upload_files, method="ui")
                created = result.get("created", [])
                errors = result.get("errors", [])
                if created:
                    DATA["TO_FLASH"].append({"content": f"Plugins uploaded successfully: {', '.join(created)}", "type": "success"})
                for error in errors:
                    DATA["TO_FLASH"].append({"content": f"Plugin upload error ({error.get('file', '?')}): {error.get('error', 'unknown')}", "type": "error"})
                if not created and not errors:
                    DATA["TO_FLASH"].append({"content": "Plugins uploaded successfully", "type": "success"})
            except (ApiClientError, ApiUnavailableError) as e:
                DATA["TO_FLASH"].append({"content": f"Couldn't update ui plugins via API: {e}", "type": "error"})
        else:
            DATA["TO_FLASH"].append({"content": "No plugin data to upload", "type": "error"})

        DATA["RELOADING"] = False

    DATA.update({"RELOADING": True, "LAST_RELOAD": time()})
    CONFIG_TASKS_EXECUTOR.submit(update_plugins)

    return redirect(url_for("loading", next=url_for("plugins.plugins_page"), message="Reloading plugins"))


@plugins.route("/plugins/upload", methods=["POST"])
@login_required
def upload_plugin():
    if API_CLIENT.readonly:
        return {"status": "ko", "message": "Database is in read-only mode"}, 403

    if not current_user.admin:
        return {"status": "ko", "message": "Plugin management is restricted to administrators"}, 403

    if not request.files:
        return {"status": "ko"}, 400

    tmp_ui_path = TMP_DIR.joinpath("ui")

    for uploaded_file in request.files.values():
        if not uploaded_file.filename:
            return {"status": "ko"}, 422

        if not uploaded_file.filename.endswith((".zip", ".tar.gz", ".tar.xz")):
            return {"status": "ko"}, 422

        file_name = Path(secure_filename(uploaded_file.filename)).name
        folder_name = file_name.rsplit(".", 2)[0]

        with BytesIO(uploaded_file.read()) as plugin_file:
            plugin_file.seek(0, 0)
            plugins = []
            if uploaded_file.filename.endswith(".zip"):
                with ZipFile(plugin_file) as zip_file:
                    for file in zip_file.namelist():
                        if file.endswith("plugin.json"):
                            plugins.append(basename(dirname(file)))
                    if len(plugins) > 1:
                        for file in zip_file.namelist():
                            if isabs(file) or ".." in file:
                                return {"status": "ko"}, 422

                        safe_zip_extractall(zip_file, str(tmp_ui_path) + "/")
            else:
                with tar_open(fileobj=plugin_file) as tar_file:
                    for file in tar_file.getnames():
                        if file.endswith("plugin.json"):
                            plugins.append(basename(dirname(file)))
                    if len(plugins) > 1:
                        for member in tar_file.getmembers():
                            if isabs(member.name) or ".." in member.name:
                                return {"status": "ko"}, 422

                        safe_tar_extractall(tar_file, str(tmp_ui_path) + "/")

            if len(plugins) <= 1:
                plugin_file.seek(0, 0)
                # deepcode ignore PT: The folder name is being sanitized before
                tmp_ui_path.joinpath(file_name).write_bytes(plugin_file.read())
                return {"status": "ok"}, 201

        for plugin in plugins:
            if tmp_ui_path.joinpath(folder_name, plugin).exists():
                with BytesIO() as tgz:
                    with tar_open(mode="w:gz", fileobj=tgz, dereference=True, compresslevel=3) as tf:
                        tf.add(str(tmp_ui_path.joinpath(folder_name, plugin)), arcname=plugin)
                    tgz.seek(0, 0)
                    tmp_ui_path.joinpath(f"{plugin}.tar.gz").write_bytes(tgz.read())

    # deepcode ignore PT: The folder name is being sanitized before
    rmtree(tmp_ui_path.joinpath(folder_name), ignore_errors=True)

    return {"status": "ok"}, 201


@plugins.route("/plugins/<string:plugin>", methods=["GET", "POST"])
@login_required
def custom_plugin_page(plugin: str):
    rmtree(TMP_DIR.joinpath("ui", "page"), ignore_errors=True)

    if not PLUGIN_NAME_RX.match(plugin):
        return handle_error("Invalid plugin id, (must be between 1 and 64 characters, only letters, numbers, underscores and hyphens)", "plugins")

    if request.method == "POST":
        if not current_user.admin:
            return error_message("Plugin management is restricted to administrators"), 403
        action_result = run_action(plugin)

        if isinstance(action_result, Response):
            LOGGER.info("Plugin action executed successfully")
            return action_result

        # case error
        if action_result["status"] == "ko":
            return error_message(escape(action_result["message"])), action_result["code"]

        LOGGER.info(f"Plugin {plugin} action executed successfully")

        if request.content_type == "application/x-www-form-urlencoded":
            return redirect(f"{url_for('plugins.plugins_page')}/{plugin}", code=303)
        return jsonify({"message": "ok", "data": action_result["data"]}), 200

    plugin_data = {}
    for db_plugin, db_plugin_data in BW_CONFIG.get_plugins().items():
        if db_plugin == plugin:
            plugin_data = db_plugin_data | {"id": db_plugin}
            break

    if not plugin_data:
        return error_message("Plugin not found"), 404

    db_config = BW_CONFIG.get_config(methods=False)

    def plugin_used(prefix: str = "") -> bool:
        # Delegate to the single activation authority (manifest map, falling back to the
        # USE_<ID>/USE_<NAME> convention) instead of re-deriving the rules here, so this
        # plugin's own page can never disagree with the marketplace grid. is_plugin_active
        # takes a lowercase plugin id (manifest keys are lowercase) and `{"value": ...}`-shaped
        # config entries; db_config (methods=False) is flat strings, so wrap it.
        scoped = {key.removeprefix(prefix): value for key, value in db_config.items() if key.startswith(prefix)} if prefix else db_config
        return is_plugin_active(plugin, plugin_data["name"], {key: {"value": value} for key, value in scoped.items()})

    is_metrics_on = db_config.get("USE_METRICS", "yes") != "no"
    is_used = plugin_used() or plugin_data["type"] in ("pro", "ui")

    if is_metrics_on and not is_used:
        # Check if at least one service is using metrics and/or the plugin
        for service in db_config.get("SERVER_NAME", "www.example.com").split():
            if not is_metrics_on and db_config.get(f"{service}_USE_METRICS", "yes") != "no":
                is_metrics_on = True
            elif not is_used and plugin_used(f"{service}_"):
                is_used = True
            if is_metrics_on and is_used:
                break

    pre_render = {}
    plugin_page = ""

    if is_used and is_metrics_on:
        # Try loading from filesystem first
        plugin_fs_path = get_plugin_path(plugin)
        tmp_page_dir = None

        if plugin_fs_path and (plugin_fs_path / "ui").exists():
            # Use the filesystem path directly
            tmp_page_dir = plugin_fs_path / "ui"
            LOGGER.debug(f"Using filesystem path for plugin {plugin}: {tmp_page_dir}")
        else:
            # Fall back to API if not found in filesystem
            try:
                page = API_CLIENT.get_plugin_page(plugin)
            except (ApiClientError, ApiUnavailableError):
                page = None
            if not page:
                return error_message("The plugin does not have a page"), 404

            # Extract from API blob to temporary location
            tmp_page_dir = TMP_DIR.joinpath("ui", "page", str(uuid4()))
            tmp_page_dir.mkdir(parents=True, exist_ok=True)

            with tar_open(fileobj=BytesIO(page), mode="r:gz") as tar:
                # Validate all members before extracting any
                tmp_page_dir_resolved = tmp_page_dir.resolve()
                for member in tar.getmembers():
                    if member.name.startswith("/") or ".." in Path(member.name).parts:
                        return {"status": "ko", "code": 400, "message": "Invalid file path"}
                    if not tmp_page_dir.joinpath(member.name).resolve().is_relative_to(tmp_page_dir_resolved):
                        return {"status": "ko", "code": 400, "message": "the plugin page has an invalid file path"}

                safe_tar_extractall(tar, tmp_page_dir)

            tmp_page_dir = tmp_page_dir.joinpath("ui")
            LOGGER.debug(f"Plugin {plugin} page extracted successfully")

        # Blueprint-only plugins have neither an actions file nor an embedded template:
        # send the user to their dedicated page when it is registered instead of
        # rendering an empty (previously misleading) embedded page
        if not (tmp_page_dir / "template.html").is_file() and not (tmp_page_dir / "actions.py").is_file():
            # Only ever delete DB-blob extractions, never a permanent plugin directory
            if str(tmp_page_dir).startswith(str(TMP_DIR)):
                rmtree(tmp_page_dir.parent, ignore_errors=True)

            try:
                return redirect(url_for(f"{plugin}.{plugin}_page"))
            except BuildError:
                try:
                    return redirect(url_for(plugin))
                except BuildError:
                    return render_template(
                        "plugin_page.html", plugin_page="", plugin=plugin_data, is_used=is_used, is_metrics=is_metrics_on, pre_render={}, no_page=True
                    )

        # Execute pre-render action if exists
        pre_render = run_action(plugin, "pre_render", tmp_dir=tmp_page_dir)
        template_path = tmp_page_dir / "template.html"

        if template_path.is_file():
            page_content = template_path.read_text(encoding="utf-8")

            if page_content.startswith('{% extends "base.html" %}'):
                page_content = """<div class="d-flex align-items-center justify-content-center">
    <div class="text-center text-primary">
        <p class="text-center relative w-full p-2 text-primary rounded-lg fw-bold">
            Plugin page uses old template, therefore it will not be displayed correctly. Please update it to the new format.
        </p>
    </div>
</div>"""

            try:
                # Merge globals and ENV with ENV taking precedence
                template_vars = {**current_app.jinja_env.globals, **getattr(g, "_env", {})}

                # deepcode ignore Ssti: We trust the plugin template
                plugin_page = (
                    Environment(
                        loader=FileSystemLoader((tmp_page_dir.as_posix() + "/", join(sep, "usr", "share", "bunkerweb", "ui", "templates") + "/")),
                        autoescape=select_autoescape(["html"]),
                    )
                    .from_string(page_content)
                    .render(pre_render=pre_render, **template_vars)
                )
            except BaseException:
                LOGGER.exception("An error occurred while rendering the plugin page")
                plugin_page = '<div class="mt-2 mb-2 alert alert-danger text-center" role="alert">An error occurred while rendering the plugin page<br/>See logs for more details</div>'

            # Clean up temporary directories if extracted from database
            if not str(tmp_page_dir).startswith((str(EXTERNAL_PLUGINS_PATH), str(PRO_PLUGINS_PATH))):
                rmtree(tmp_page_dir.parent, ignore_errors=True)

    return render_template("plugin_page.html", plugin_page=plugin_page, plugin=plugin_data, is_used=is_used, is_metrics=is_metrics_on, pre_render=pre_render)
