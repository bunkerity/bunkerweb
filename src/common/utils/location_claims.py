#!/usr/bin/env python3
"""The per-service HTTP location namespace, shared by every plugin that emits a ``location``.

Three core plugins render a ``location`` into the same server block: ``reverseproxy``
(``proxy_pass``), ``grpc`` (``grpc_pass``) and ``redirect`` (``return 3xx``). NGINX refuses two
``location`` blocks with the same URI outright, so a path claimed by any of them is claimed for
all of them — even though each family stores its rules under its own suffixed settings.

Both resolvers scan this namespace: for **allocation** each needs only its own family's
occupied suffixes, but for **conflict detection** all three families must be considered
together. Keeping the two concerns in one module is what stops the next vertical from
re-implementing half of it and reopening the hole.
"""

from typing import Any, Dict, List, Optional

# label -> (setting whose non-empty value makes the location render, setting holding its path).
# The trigger is the exact condition each template loops on, so a blanked-out rule frees its
# path instead of blocking it.
LOCATION_FAMILIES = {
    "reverse proxy": ("REVERSE_PROXY_HOST", "REVERSE_PROXY_URL"),
    "gRPC": ("GRPC_HOST", "GRPC_URL"),
    "redirect": ("REDIRECT_TO", "REDIRECT_FROM"),
}


def suffix_key(base: str, index: int) -> str:
    return base if index == 0 else f"{base}_{index}"


def family_occupancy(config: Dict[str, Any], prefixes: List[str], trigger: str, path_setting: str) -> Dict[int, str]:
    """``{suffix: path}`` for one family's locations that actually render for one server.

    A suffix counts as taken only when its trigger setting is non-empty. Later prefixes override
    earlier ones on the same suffix, matching the global-then-server-specific merge Templator
    applies — which is why the caller passes the prefixes least specific first.
    """
    taken: Dict[int, str] = {}
    for prefix in prefixes:
        base = f"{prefix}{trigger}"
        for key, value in config.items():
            if not isinstance(key, str) or not key.startswith(base):
                continue
            suffix = key[len(base) :]  # noqa: E203
            if suffix and not (suffix.startswith("_") and suffix[1:].isdigit()):
                continue
            index = int(suffix[1:]) if suffix else 0
            if not str(value or "").strip():
                taken.pop(index, None)  # a server-specific blank disables the inherited location
                continue
            taken[index] = str(config.get(suffix_key(f"{prefix}{path_setting}", index), "") or config.get(suffix_key(path_setting, index), "/") or "/")
    return taken


def inline_location_conflict(config: Dict[str, Any], server: str, prefixes: List[str], attached_paths: Any) -> str:
    """Return an error when the incoming inline settings land on a path a resource already serves.

    The mutation-path mirror of the resolvers' check: here the incoming value is an inline rule
    and ``attached_paths`` is what the service already carries through attached resources.
    """
    if not attached_paths:
        return ""
    for path, label in claimed_paths(config, prefixes).items():
        if path in attached_paths:
            return (
                f"Cannot save these {label} settings: {server} already serves {path} through an attached resource. "
                f"Detach it from {server}, or use a different path here."
            )
    return ""


def claimed_paths(config: Dict[str, Any], prefixes: List[str], *, families: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """``{path: family label}`` for every location that renders for one server.

    Used for conflict detection, where what matters is that the path is taken at all — not by
    which family, beyond naming it in the error.
    """
    claims: Dict[str, str] = {}
    for label, (trigger, path_setting) in (families or LOCATION_FAMILIES).items():
        for path in family_occupancy(config, prefixes, trigger, path_setting).values():
            claims.setdefault(path, label)
    return claims
