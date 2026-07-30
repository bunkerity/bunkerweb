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
from typing import Any, Dict, Optional, Set

from app.utils import is_editable_method


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

        # Outside the declared scope: this form has no authority to remove it.
        if scope is not None and not _in_scope(setting, scope):
            variables[setting] = entry["value"]
            continue

        # Inside scope (or no scope declared): only non-UI-editable values are restored,
        # so a user's clear of a ui-method setting still goes through.
        if not is_editable_method(setting_method, allow_default=False):
            variables[setting] = entry["value"]

    return variables
