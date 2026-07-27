#!/usr/bin/env python3
"""Flatten redirect resources attached to a service into ``REDIRECT_*`` settings.

A redirect resource is a named, reusable rule attached to N services. NGINX and the
``redirect`` core plugin template know nothing about that: they only consume the flat,
suffixed ``REDIRECT_FROM`` / ``REDIRECT_TO`` / ``REDIRECT_TO_REQUEST_URI`` /
``REDIRECT_TO_STATUS_CODE`` settings. This module injects each service's attached rules
into its next free suffixes just before configuration is materialized, so the existing
template renders resource-backed and inline rules through the same path.

Inline settings are never renumbered or removed — they keep their suffixes and their NGINX
precedence, resources take the ones left over. A source path claimed twice on one service
aborts generation instead of letting ``location`` ordering silently pick a winner.

Like ``resource_group_resolver`` it is deliberately dependency-light (no ORM import): the
caller hands it a ``db`` object exposing ``get_service_redirects()``.
"""

from typing import Any, Dict, List

REDIRECT_TO = "REDIRECT_TO"
REDIRECT_FROM = "REDIRECT_FROM"
REDIRECT_REQUEST_URI = "REDIRECT_TO_REQUEST_URI"
REDIRECT_STATUS_CODE = "REDIRECT_TO_STATUS_CODE"

# Highest suffix the generator will allocate. Well above any realistic rule count, and only
# there so a corrupt attachment set cannot spin the allocator forever.
MAX_REDIRECT_SUFFIX = 1000


class RedirectConflictError(Exception):
    """Two rules claim the same source path on one service.

    Raised rather than resolved: the mutation paths (API, save_config) already refuse to
    create this state, so reaching it means the configuration on disk would silently depend
    on ``location`` ordering nobody chose. Aborting keeps the last valid configuration.
    """


def _suffix_key(base: str, index: int) -> str:
    return base if index == 0 else f"{base}_{index}"


def config_servers(config: Dict[str, Any]) -> List[str]:
    """Server names, mirroring Templator.

    In multisite each server is one name out of ``SERVER_NAME``; otherwise the whole
    ``SERVER_NAME`` is a single server.
    """
    server_name = str(config.get("SERVER_NAME", "")).strip()
    if config.get("MULTISITE", "no") == "yes":
        return server_name.split()
    return [server_name] if server_name else []


def scan_prefixes(server: str, multisite: bool) -> List[str]:
    """Key prefixes whose ``REDIRECT_*`` settings render for ``server``, least specific first.

    In multisite a service inherits the unprefixed global value unless it defines its own,
    exactly how Templator merges global settings under server-specific ones. Scanning only
    the prefixed keys would miss a global inline rule and hand its suffix to a resource,
    silently dropping the operator's rule at render time.
    """
    return ["", f"{server}_"] if multisite else [""]


def _occupied(config: Dict[str, Any], prefixes: List[str]) -> Dict[int, str]:
    """``{suffix: from_path}`` for the inline rules that actually render for one server.

    A suffix counts as taken only when its ``REDIRECT_TO`` is non-empty, which is the exact
    condition the redirect template renders on — so the empty default at suffix 0, and any
    inline rule the operator blanked out, stay available for a resource. Later prefixes
    override earlier ones on the same suffix, matching global-then-server-specific merging.
    """
    taken: Dict[int, str] = {}
    for prefix in prefixes:
        base = f"{prefix}{REDIRECT_TO}"
        for key, value in config.items():
            if not isinstance(key, str) or not key.startswith(base):
                continue
            suffix = key[len(base) :]  # noqa: E203
            if suffix and not (suffix.startswith("_") and suffix[1:].isdigit()):
                continue  # REDIRECT_TO_REQUEST_URI / REDIRECT_TO_STATUS_CODE and their suffixes
            index = int(suffix[1:]) if suffix else 0
            if not str(value or "").strip():
                taken.pop(index, None)  # a server-specific blank disables the inherited rule
                continue
            taken[index] = str(config.get(_suffix_key(f"{prefix}{REDIRECT_FROM}", index), "") or config.get(_suffix_key(REDIRECT_FROM, index), "/") or "/")
    return taken


def expand_service_redirects(config: Dict[str, Any], db: Any, logger: Any = None) -> Dict[str, Any]:
    """Return a copy of ``config`` with every attached redirect rule flattened into settings.

    A database read failure degrades to the unchanged config (a transient DB problem must not
    take generation down), but a path conflict raises ``RedirectConflictError``.
    """
    if db is None:
        return config.copy()
    try:
        service_redirects = db.get_service_redirects()
    except Exception as exc:  # noqa: BLE001 - never break config generation over a DB read
        if logger is not None:
            logger.warning(f"Could not expand redirect resources: {exc}")
        return config.copy()
    if not service_redirects:
        return config.copy()

    out = config.copy()
    multisite = config.get("MULTISITE", "no") == "yes"
    for server in config_servers(config):
        rules = service_redirects.get(server)
        if not rules:
            continue
        prefix = f"{server}_" if multisite else ""
        taken = _occupied(out, scan_prefixes(server, multisite))
        claimed = dict(taken)
        next_index = 0
        for rule in rules:
            from_path = rule["from_path"]
            for index, path in claimed.items():
                if path == from_path:
                    origin = "an inline redirect" if index in taken else "another redirect resource"
                    raise RedirectConflictError(f"Service {server} has {origin} on path {from_path}, conflicting with redirect {rule['name']}")

            while next_index in claimed:
                next_index += 1
            if next_index > MAX_REDIRECT_SUFFIX:
                raise RedirectConflictError(f"Service {server} exceeds the {MAX_REDIRECT_SUFFIX} redirect limit")

            out[_suffix_key(f"{prefix}{REDIRECT_FROM}", next_index)] = from_path
            out[_suffix_key(f"{prefix}{REDIRECT_TO}", next_index)] = rule["to_url"]
            out[_suffix_key(f"{prefix}{REDIRECT_REQUEST_URI}", next_index)] = "yes" if rule["append_request_uri"] else "no"
            out[_suffix_key(f"{prefix}{REDIRECT_STATUS_CODE}", next_index)] = str(rule["status_code"])
            claimed[next_index] = from_path

    return out


def inline_redirect_conflict(config: Dict[str, Any], server: str, attached_paths: Any, *, multisite: bool = True) -> str:
    """Return an error when a service's inline rules collide with its attached resources.

    Used by the settings save path, where the incoming value is an inline rule and the
    resources are what the service already carries — the mirror of the check the redirects
    mixin runs when the resource side changes.
    """
    if not attached_paths:
        return ""
    for path in _occupied(config, scan_prefixes(server, multisite)).values():
        if path in attached_paths:
            return f"Service {server} already has a redirect resource on path {path}"
    return ""
