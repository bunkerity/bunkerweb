"""Secret settings -- the ones a plugin declares `"type": "password"` -- never reach a page.

A `type=password` input only hides a value on screen: whatever the server renders into `value=`
is in the page source, readable by anyone who can open the page (a reader included). So the
routes swap a stored secret for `SECRET_PLACEHOLDER` before rendering, and swap the placeholder
back for the stored value before saving. That keeps the three save outcomes apart:

* the placeholder comes back untouched -> the secret is kept (the form was saved for another field);
* a new value comes back -> it replaces the secret;
* an empty value comes back -> the user erased the field or clicked reset, an explicit clear.

The placeholder matches every shipped password setting's regex, so neither the browser's
`pattern=` nor the Configurator refuses a form that merely carries it through.
"""

from re import sub
from typing import Any, Dict, FrozenSet, Mapping, Optional

SECRET_PLACEHOLDER = "__BW_SECRET_UNCHANGED__"
REDACTED = "[REDACTED]"


def secret_setting_names(plugins_settings: Mapping[str, Mapping[str, Any]]) -> FrozenSet[str]:
    """Names of every setting declared `type: password` (`BW_CONFIG.get_plugins_settings()`)."""
    return frozenset(name for name, data in plugins_settings.items() if isinstance(data, Mapping) and data.get("type") == "password")


def is_secret_setting(key: str, names: FrozenSet[str]) -> bool:
    """`key` may carry a multiple suffix (`_1`) and, in a full export, a service prefix (`www.example.com_`)."""
    base = sub(r"_\d+$", "", key)
    return base in names or any(base.endswith(f"_{name}") for name in names)


def _value(entry: Any) -> Any:
    return entry.get("value") if isinstance(entry, Mapping) else entry


def redact_secrets(config: Mapping[str, Any], names: FrozenSet[str], placeholder: str = SECRET_PLACEHOLDER) -> Dict[str, Any]:
    """Copy of `config` with every non-empty secret replaced; entries are `{"value": ...}` dicts or plain values."""
    redacted = {}
    for key, entry in config.items():
        if _value(entry) and is_secret_setting(key, names):
            entry = {**entry, "value": placeholder} if isinstance(entry, Mapping) else placeholder
        redacted[key] = entry
    return redacted


def restore_secrets(
    variables: Mapping[str, str], stored: Mapping[str, Any], names: FrozenSet[str], drafted: Optional[Mapping[str, Any]] = None
) -> Dict[str, str]:
    """Copy of the posted `variables` with every untouched placeholder turned back into the stored secret
    (or dropped when nothing is stored: the secret is still at its default).

    `drafted` holds the RAW editor's setting drafts: the RAW page renders a draft's retained value, not the
    effective one in `stored`, so a placeholder for a drafted key is restored from the draft."""
    drafted = drafted or {}
    restored = {}
    for key, value in variables.items():
        if value == SECRET_PLACEHOLDER and is_secret_setting(key, names):
            entry = drafted[key] if key in drafted else stored.get(key)
            if entry is None:
                # Rendered from the effective config (defaults included) but nothing is stored: the secret
                # is still at its default, so "keep it" means posting nothing for it.
                continue
            value = _value(entry) or ""
        restored[key] = value
    return restored
