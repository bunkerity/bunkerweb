#!/usr/bin/env python3
"""Mutation-time guard for the per-service HTTP location namespace.

``reverseproxy``, ``grpc`` and ``redirect`` all render a ``location`` into the same server
block, and NGINX refuses two ``location`` blocks with the same URI. A path is therefore claimed
across all three families at once — by an inline setting or by an attached resource alike — so
every vertical that mounts something on a path checks here rather than only against its own
kind. The render-time mirror of this lives in ``utils/location_claims.py``.
"""

from typing import Any, Dict, List, Optional, Tuple

from model import Global_values, Redirects, ResourceAttachments, Resources, Services_settings, Upstreams  # type: ignore
from sqlalchemy import select

# label -> (setting whose non-empty value makes the location render, setting holding its path)
LOCATION_SETTINGS = {
    "reverse proxy": ("REVERSE_PROXY_HOST", "REVERSE_PROXY_URL"),
    "gRPC": ("GRPC_HOST", "GRPC_URL"),
    "redirect": ("REDIRECT_TO", "REDIRECT_FROM"),
}


def inline_family_paths(session, service_id: str, trigger: str, path_setting: str) -> set:
    """Paths served by one plugin's inline settings on a service.

    A suffix counts only when its trigger setting is non-empty — the exact condition each
    template loops on — so a blanked-out rule never blocks a resource. Service values shadow
    global ones, matching multisite inheritance.
    """
    by_suffix: Dict[int, Dict[str, str]] = {}
    for scope in (
        select(Global_values.setting_id, Global_values.value, Global_values.suffix).where(Global_values.setting_id.in_((trigger, path_setting))),
        select(Services_settings.setting_id, Services_settings.value, Services_settings.suffix).where(
            Services_settings.service_id == service_id, Services_settings.setting_id.in_((trigger, path_setting))
        ),
    ):
        for row in session.execute(scope):
            by_suffix.setdefault(row.suffix or 0, {})[row.setting_id] = row.value or ""

    return {values.get(path_setting) or "/" for values in by_suffix.values() if values.get(trigger)}


def inline_location_paths(session, service_id: str, *, families: Optional[Dict[str, Tuple[str, str]]] = None) -> Dict[str, str]:
    """``{path: family label}`` for every inline location configured on a service."""
    claims: Dict[str, str] = {}
    for label, (trigger, path_setting) in (families or LOCATION_SETTINGS).items():
        for path in inline_family_paths(session, service_id, trigger, path_setting):
            claims.setdefault(path, label)
    return claims


def resource_location_claims(session, service_ids: List[str], exclude_resource_id: str = "") -> List[Tuple[str, str, str, str]]:
    """``[(service_id, path, kind, resource name)]`` for attached resources that mount a location.

    A redirect carries its path on the resource, shared by every attachment; an upstream pool
    carries it on the attachment, so the same pool can sit on a different path per service. A
    stream pool has no path at all and is skipped.
    """
    claims: List[Tuple[str, str, str, str]] = []
    if not service_ids:
        return claims

    redirects = (
        select(ResourceAttachments.service_id, Resources.name, Redirects.from_path)
        .join(Resources, Resources.id == ResourceAttachments.resource_id)
        .join(Redirects, Redirects.resource_id == Resources.id)
        .where(ResourceAttachments.service_id.in_(service_ids))
    )
    upstreams = (
        select(ResourceAttachments.service_id, ResourceAttachments.match_path, Resources.name, Upstreams.protocol)
        .join(Resources, Resources.id == ResourceAttachments.resource_id)
        .join(Upstreams, Upstreams.resource_id == Resources.id)
        .where(ResourceAttachments.service_id.in_(service_ids))
    )
    if exclude_resource_id:
        redirects = redirects.where(ResourceAttachments.resource_id != exclude_resource_id)
        upstreams = upstreams.where(ResourceAttachments.resource_id != exclude_resource_id)

    for row in session.execute(redirects):
        claims.append((row.service_id, row.from_path, "redirect", row.name))
    for row in session.execute(upstreams):
        if row.protocol != "stream":
            claims.append((row.service_id, row.match_path, "upstream", row.name))
    return claims


def location_conflict(session, resource_id: str, path: str, service_ids: List[str], *, subject: str) -> str:
    """Return an actionable error when ``path`` is already served on one of the services.

    Refusing here keeps a configuration NGINX would reject outright out of the database,
    instead of discovering it at render time and falling back to the last valid configuration.
    """
    if not service_ids:
        return ""
    for service_id, claimed, kind, name in resource_location_claims(session, service_ids, resource_id):
        if claimed == path:
            return (
                f"Cannot attach {subject}: {service_id} already serves {path} through the {kind} “{name}”. "
                f"Detach “{name}” from {service_id}, or give one of them a different path."
            )
    for service_id in service_ids:
        inline = inline_location_paths(session, service_id)
        if path in inline:
            return (
                f"Cannot attach {subject}: {service_id} already serves {path} through its own {inline[path]} settings. "
                f"Clear those settings for {path} on {service_id}, or use a different path."
            )
    return ""


def service_setting(session, service_id: str, setting_id: str, default: str = "") -> Any:
    """One service's effective value for a setting, falling back to the global one."""
    value = session.execute(
        select(Services_settings.value).where(Services_settings.service_id == service_id, Services_settings.setting_id == setting_id).limit(1)
    ).scalar_one_or_none()
    if value is None:
        value = session.execute(select(Global_values.value).where(Global_values.setting_id == setting_id).limit(1)).scalar_one_or_none()
    return value or default
