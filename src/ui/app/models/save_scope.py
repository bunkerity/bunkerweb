"""Which stored settings must survive a save that only owns part of the configuration.

``Database.save_config`` treats its payload as the complete desired state: a key absent
from it has its row deleted (``db_methods/config_save.py:592``). That is safe only while a
single form posts every key, which is how the UI worked until per-plugin pages existed.

Two separate protections live here, and conflating them breaks one of them:

* **Method-based** (pre-existing). A form may omit a key by accident -- a multi-value
  rebuild dropping a suffix, a conditional Jinja branch, a plugin tab absent from the DOM,
  a JS race. Restoring keys whose method is *not* UI-editable covers that without
  swallowing a legitimate clear, because clearing a ui-method setting posts an empty
  value rather than nothing at all.

* **Scope-based** (new). A form that is authoritative for only part of the configuration
  declares that part. Everything outside it is preserved whatever its method, so a plugin
  page cannot delete another plugin's rows -- by construction rather than by care.

``scope=None`` means "no scope declared" and reproduces the method-based behaviour on its
own, so callers can adopt this function before they can compute a scope.
"""

from re import search as re_search
from typing import Any, Dict, Optional, Set, Tuple

from common_utils import split_templates  # type: ignore

from app.utils import is_editable_method

# The keys a surface must post itself because this module deliberately never restores them
# (they are in the caller's `restore_skip`, so omitting one destroys it). Rendered as hidden
# inputs AFTER the settings body: `request.form.to_dict()` keeps the FIRST value for a repeated
# name, so an enabled field in the body wins and a disabled/blacklisted/absent one falls through
# to the trailing fallback -- the rule plugin_settings_page.html:2-19 already writes out.
#
# The two pages need DIFFERENT lists, which is why this is one function keyed on the page rather
# than one shared constant:
#
#   * SERVER_NAME / OLD_SERVER_NAME -- the rename pair. Omitting BOTH makes update_service fall
#     back to `variables["SERVER_NAME"] = old_server_name` == "" (routes/services.py:750-755) and
#     `Config.edit_service` then raises IndexError on `server_name_splitted[0]`
#     (models/config.py:375) inside CONFIG_TASKS_EXECUTOR -- DATA["RELOADING"] is never cleared,
#     so the save is lost and the loading page spins forever. At GLOBAL scope SERVER_NAME is the
#     service *list*: it is blacklisted there (app/utils.py:272) and posting it would rewrite
#     that list, so the global page must NOT emit it.
#   * IS_DRAFT -- blacklisted, hence never restored, and routes/services.py:931 does
#     `variables.pop("IS_DRAFT", "no")`, so omitting it PUBLISHES a draft service. Global
#     settings have no draft state and update_global_config never reads it.
#   * USE_TEMPLATE -- in the service `restore_skip`; omitting it deletes the row, the service
#     loses its template, and `template_unchanged` goes False so the outgoing template's values
#     are dropped rather than materialised. Blacklisted at global scope.
#   * USE_UI -- in the service `restore_skip` only (`get_blacklisted_settings(True)` does not add
#     it, and global_settings.py:55 passes exactly that). It is also the `ui` plugin's tier-3
#     activation key, so it is a control key and a shelf switch at once; the ordering rule above
#     resolves that collision.
#
# `OVERRIDE_NON_GLOBAL_SERVICES` is deliberately absent: it is a form control, not a setting, and
# it is popped before any of this runs (global_settings.py:148).
_SERVICE_CONTROL_KEYS: Tuple[str, ...] = ("SERVER_NAME", "OLD_SERVER_NAME", "IS_DRAFT", "USE_TEMPLATE", "USE_UI")


def control_keys(global_page: bool = False) -> Tuple[str, ...]:
    """The keys this page must post itself, in render order. Empty at global scope -- see above."""
    return () if global_page else _SERVICE_CONTROL_KEYS


def templates_unchanged(old_value: Any, new_value: Any) -> bool:
    """Does this save leave the service's ``USE_TEMPLATE`` LAYER LIST exactly as it was?

    ``USE_TEMPLATE`` is an ordered list, and this is an EXACT ORDERED comparison on purpose --
    only whitespace is canonicalised, so "low  high" and "low high" (the same overlay) stop
    reading as a change while "low high" and "high low" (genuinely different overlays) keep
    reading as one.

    DO NOT relax this into a set/subset test, a "layers were only added, so nothing changed"
    shortcut, or a per-key ``entry["template"] in new_list`` membership test. The return value
    drives ``restore_unowned_settings``' guard below, which fires ONLY for keys the overlay
    synthesised (method "default" + a template id). The load-bearing property of those keys is
    that **an overlay-synthesised key is always re-derivable from the merged overlay** -- state
    it that way, not as "the value is always the template's own default": that stronger claim is
    the one the ``multiple``-group re-materialisation in ``db_methods/config_read.py`` broke by
    emitting a PLUGIN default under a truthy owning layer. It records ``None`` there now, so both
    readings hold today, but only re-derivability is what the guard actually needs. Therefore:

    * returning False (drop) loses nothing -- the value is re-derived from the merged overlay on
      the very next read;
    * returning True (restore) is a no-op only while the merged default is unchanged. As soon as
      a newly added layer overrides that key, ``config_save`` resolves ``template_setting_default``
      against the NEW list, ``_check_value`` returns False, and a real ``method="ui"`` row is
      written FREEZING the outgoing layer's value -- permanently defeating the layer the user
      just added, on exactly the add-a-layer gesture multi-template exists for.

    So any change to the list -- add, remove or reorder -- must return False. Blunt is correct
    here; the clever version is the data-loss path.
    """
    return split_templates(old_value) == split_templates(new_value)


def _in_scope(setting: str, scope: Set[str]) -> bool:
    """Is this stored key inside the declared scope, in either its base or suffixed form?

    `multiple` settings are stored suffixed (REVERSE_PROXY_URL_2) while a plugin manifest names the
    base (REVERSE_PROXY_URL), so a scope derived from plugin.json carries base names only. Matching
    both forms keeps a caller from silently losing the ability to clear a multi-value entry. The
    base-name derivation mirrors models/config.py:61.
    """
    if setting in scope:
        return True
    base = setting.rsplit("_", 1)[0] if re_search(r"_\d+$", setting) else setting
    return base in scope


def restore_unowned_settings(
    payload: Dict[str, str],
    db_config: Dict[str, Dict[str, Any]],
    *,
    scope: Optional[Set[str]] = None,
    restore_skip: Optional[Set[str]] = None,
    template_unchanged: bool = True,
    preserve_suffixed: bool = False,
) -> Dict[str, str]:
    """Return ``payload`` plus every stored setting that must not be deleted.

    Parameters
    ----------
    payload:
        What the form actually posted. Never mutated; a new dict is returned.
    db_config:
        Current stored state, ``{key: {"value": ..., "method": ..., "template": ...}}``.
    scope:
        The keys this form is authoritative for. ``None`` declares no scope, which
        preserves the historical method-based behaviour exactly.
    restore_skip:
        Transient and form-managed keys that are never restored whatever the rules say --
        they flow through their own rename/template paths instead.
    template_unchanged:
        False when this save switches ``USE_TEMPLATE``.
    preserve_suffixed:
        True for a surface that renders no multi-value cloner, so it can never post a stored
        ``_<digits>`` row. ``_in_scope`` base-matches, so declaring the base name would drag
        every suffix into scope and delete it. Tie this to the surface, never default it on: a
        surface that CAN edit multiples (the per-plugin page) needs it False or a legitimate
        clear becomes impossible, and ``scope=None`` + True would make every ``multiple`` row
        unclearable everywhere.
    """
    restore_skip = restore_skip or set()
    variables = dict(payload)

    for setting, entry in db_config.items():
        if setting in variables or setting in restore_skip:
            continue

        setting_method = entry.get("method")

        # Don't carry an outgoing template's defaults forward when switching templates.
        # Hoisted above BOTH branches below: when the service page changes USE_TEMPLATE
        # every plugin setting is out of scope, so leaving this inside the method branch
        # would let the scope branch materialise the old template's values as real rows.
        # Behaviour-preserving for scope=None -- "default" is non-editable under
        # allow_default=False, so this guard was already reached on exactly these keys.
        if setting_method == "default" and entry.get("template") and not template_unchanged:
            continue

        # A stored multi-value row on a surface with no cloner. Must sit ABOVE the scope branch:
        # an out-of-scope suffix would be restored there anyway, but an IN-scope one would fall
        # through to the method branch and be deleted whenever its method is ui/api/wizard.
        # Below the template guard on purpose -- an outgoing template's default must still be
        # dropped rather than frozen into the service as a real row.
        # Reaching this line at all means `setting` is not in `restore_skip`: verified over
        # src/common/settings.json + every src/common/core/*/plugin.json that no blacklisted or
        # control key is `multiple`, so no `<restore_skip name>_<n>` row can exist. That is a
        # property of the shipped manifests, not of the code -- pinned by
        # test_save_scope.py::test_no_restore_skip_name_is_a_multiple_setting.
        if preserve_suffixed and re_search(r"_\d+$", setting):
            variables[setting] = entry["value"]
            continue

        # Outside the declared scope: this form has no authority to remove it.
        if scope is not None and not _in_scope(setting, scope):
            variables[setting] = entry["value"]
            continue

        # Inside scope (or no scope declared): only non-UI-editable values are restored,
        # so a user's clear of a ui-method setting still goes through.
        if not is_editable_method(setting_method, allow_default=False):
            variables[setting] = entry["value"]

    return variables
