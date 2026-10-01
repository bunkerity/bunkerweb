"""Validation and normalization for RAW setting-draft metadata."""

from json import JSONDecodeError, loads
from typing import Any, Mapping, Optional, Sequence

from app.i18n import translated
from app.utils import get_blacklisted_settings, is_editable_method

RAW_DRAFT_SETTINGS = "RAW_DRAFT_SETTINGS"
RAW_PRESENT_SETTINGS = "RAW_PRESENT_SETTINGS"


def _msg(key: str, english: str, **variables: Any) -> str:
    return translated(f"raw_drafts.{key}", **variables) or english.format(**variables)


def draft_edits_discarded() -> str:
    return _msg("edits_discarded", "Draft settings remain unchanged; activate or edit them in Raw mode.")


def metadata_raw_only() -> str:
    return _msg("metadata_raw_only", "Setting draft metadata is only accepted in raw mode.")


# These values describe the service/global shape and are never setting drafts.
STRUCTURAL_SETTINGS = frozenset(
    {
        "SERVER_NAME",
        "MULTISITE",
        "IS_DRAFT",
        "USE_TEMPLATE",
        "DATABASE_URI",
        "DATABASE_URI_READONLY",
        "OLD_SERVER_NAME",
        "USE_UI",
        "OVERRIDE_NON_GLOBAL_SERVICES",
    }
)


class RawDraftSettingsError(ValueError):
    """Raised when a RAW draft metadata field is malformed or unsafe."""


def existing_draft_keys(config: Mapping[str, Any]) -> tuple[str, ...]:
    """Return setting keys carrying saved draft metadata from a DB snapshot."""
    return tuple(key for key, value in config.items() if isinstance(value, Mapping) and bool(value.get("is_draft")))


def _decode_keys(raw_value: Optional[str], field: str) -> list[str]:
    if raw_value is None:
        raise RawDraftSettingsError(_msg("missing_metadata", "Missing {field} metadata.", field=field))

    try:
        value = loads(raw_value)
    except (JSONDecodeError, TypeError):
        raise RawDraftSettingsError(f"{field} must be a JSON list of setting names.") from None

    if not isinstance(value, list) or any(not isinstance(key, str) for key in value):
        raise RawDraftSettingsError(f"{field} must be a JSON list of setting names.")
    if len(value) != len(set(value)):
        raise RawDraftSettingsError(f"{field} contains duplicate setting names.")
    return value


def _setting_name(key: str, service: Optional[str], source_services: Sequence[str]) -> str:
    if not service:
        return key

    for candidate in (service, *source_services):
        if candidate and key.startswith(f"{candidate}_"):
            return key.removeprefix(f"{candidate}_")
    return key


def _full_key(key: str, service: Optional[str], source_services: Sequence[str]) -> str:
    return f"{service}_{_setting_name(key, service, source_services)}" if service else key


def _is_known_setting(key: str, settings: Optional[Mapping[str, Mapping[str, Any]]]) -> bool:
    if not isinstance(settings, Mapping) or not settings:
        return False
    if key in settings:
        return True
    base, separator, suffix = key.rpartition("_")
    setting = settings.get(base)
    return bool(separator and suffix.isdigit() and isinstance(setting, Mapping) and setting.get("multiple"))


def _is_service_setting(key: str, settings: Optional[Mapping[str, Mapping[str, Any]]]) -> bool:
    if not isinstance(settings, Mapping) or not settings:
        return False
    base = key.rsplit("_", 1)[0] if key.rsplit("_", 1)[-1].isdigit() else key
    setting = settings.get(base)
    return isinstance(setting, Mapping) and setting.get("context") == "multisite"


def parse_raw_draft_settings(
    raw_value: Optional[str],
    *,
    posted_keys: set[str],
    service: Optional[str] = None,
    source_services: Sequence[str] = (),
    present_value: Optional[str] = None,
    existing_draft_keys: Optional[Sequence[str]] = None,
    settings: Optional[Mapping[str, Mapping[str, Any]]] = None,
    global_config: bool = False,
) -> dict[str, Optional[bool]]:
    """Return a flat DB draft-state map for a RAW form.

    The browser sends setting names as they appear in the editor. Service pages
    show bare names, while the database stores service-prefixed names. Every
    posted, draftable key receives an explicit boolean, so a RAW save can
    activate a setting as well as draft it. A saved draft absent from
    ``RAW_PRESENT_SETTINGS`` receives ``None`` when ``existing_draft_keys`` is
    supplied; the database treats that value as an explicit row deletion.
    """

    draft_keys = _decode_keys(raw_value, RAW_DRAFT_SETTINGS)
    present_keys = _decode_keys(present_value, RAW_PRESENT_SETTINGS)

    canonical_posted = {_full_key(key, service, source_services): key for key in posted_keys}
    canonical_drafts = {_full_key(key, service, source_services) for key in draft_keys}
    canonical_present = {_full_key(key, service, source_services) for key in present_keys}

    blacklisted = get_blacklisted_settings(global_config) | STRUCTURAL_SETTINGS
    for key in canonical_drafts:
        setting = _setting_name(key, service, source_services)
        if setting in blacklisted:
            raise RawDraftSettingsError(_msg("cannot_be_draft", "Setting {setting} cannot be made a draft.", setting=setting))
        if key not in canonical_posted:
            raise RawDraftSettingsError(_msg("draft_not_posted", "Draft setting {setting} was not posted.", setting=setting))
        if not _is_known_setting(setting, settings):
            raise RawDraftSettingsError(_msg("setting_not_valid", "Setting {setting} is not valid.", setting=setting))
        if service and not _is_service_setting(setting, settings):
            raise RawDraftSettingsError(_msg("global_not_service_draft", "Global setting {setting} cannot be made a service draft.", setting=setting))

    # Structural controls are posted alongside the editor metadata but are
    # removed from the setting payload before this parser is called.
    canonical_present = {key for key in canonical_present if _setting_name(key, service, source_services) not in blacklisted}
    missing_present = canonical_drafts - canonical_present
    if missing_present:
        setting = _setting_name(next(iter(missing_present)), service, source_services)
        raise RawDraftSettingsError(_msg("draft_not_present", "Draft setting {setting} is not present in the RAW editor.", setting=setting))

    unknown_present = canonical_present - set(canonical_posted)
    if unknown_present:
        setting = _setting_name(next(iter(unknown_present)), service, source_services)
        raise RawDraftSettingsError(_msg("present_not_posted", "Present setting {setting} was not posted.", setting=setting))
    invalid_present = {key for key in canonical_present if not _is_known_setting(_setting_name(key, service, source_services), settings)}
    if invalid_present:
        setting = _setting_name(next(iter(invalid_present)), service, source_services)
        raise RawDraftSettingsError(_msg("present_not_valid", "Present setting {setting} is not valid.", setting=setting))

    result: dict[str, Optional[bool]] = {}
    for full_key in canonical_posted:
        setting = _setting_name(full_key, service, source_services)
        if setting in blacklisted or not _is_known_setting(setting, settings):
            continue
        if service and not _is_service_setting(setting, settings):
            continue
        if full_key not in canonical_present:
            continue
        result[full_key] = full_key in canonical_drafts

    if existing_draft_keys is not None:
        canonical_existing = {_full_key(key, service, source_services) for key in existing_draft_keys}
        for full_key in canonical_existing - canonical_present:
            setting = _setting_name(full_key, service, source_services)
            if setting in blacklisted or not _is_known_setting(setting, settings):
                continue
            if service and not _is_service_setting(setting, settings):
                continue
            result[full_key] = None

    return result


def drafted_settings(config: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """The draftable entries of a ``with_setting_drafts`` snapshot that are drafts right now."""
    return {key: value for key, value in config.items() if isinstance(value, Mapping) and value.get("is_draft") and key not in STRUCTURAL_SETTINGS}


def freeze_draft_edits(variables: dict, drafted: Mapping[str, Any], effective: Mapping[str, Any]) -> set[str]:
    """Outside the RAW editor a drafted setting is read-only. Its form field shows the EFFECTIVE
    value, so an edit there would otherwise be saved over (or propagated from) a key whose row is
    a draft. Put the effective value back -- or drop the key when the snapshot has none -- and
    return the keys whose edit was discarded so the caller can say so."""
    discarded = set()
    for key in drafted:
        if key not in variables:
            continue
        current = effective.get(key)
        if isinstance(current, Mapping):
            if variables[key] != current.get("value"):
                discarded.add(key)
            variables[key] = current.get("value", "")
        else:
            discarded.add(key)
            variables.pop(key)
    return discarded


def locked_draft_change(draft_settings: Mapping[str, Optional[bool]], draft_config: Mapping[str, Any], name_of=lambda key: key) -> Optional[str]:
    """The error for a draft-state change on a setting the UI may not edit, or None.

    ``name_of`` maps a map key to the snapshot's key (the service page strips the service prefix).
    A setting with no stored row has no method yet: it is a default, and drafting it is exactly
    how a new value gets staged (dev cf76f5bb7e).
    """
    for key, desired in draft_settings.items():
        setting = name_of(key)
        metadata = draft_config.get(setting, {})
        if not isinstance(metadata, Mapping) or not draft_state_changes(desired, metadata):
            continue
        method = metadata.get("method") or "default"
        if not is_editable_method(method, allow_default=True):
            return _msg(
                "locked_by_method", "Setting {setting} cannot change draft state because it is managed by the {method} method.", setting=setting, method=method
            )
    return None


def draft_state_changes(desired: Optional[bool], metadata: Any) -> bool:
    current = isinstance(metadata, Mapping) and bool(metadata.get("is_draft"))
    return current if desired is None else bool(desired) != current
