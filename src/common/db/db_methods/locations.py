#!/usr/bin/env python3
"""Mutation-time guard for the per-service HTTP location namespace.

``reverseproxy``, ``grpc``, ``redirect`` and ``php`` all render a ``location`` into the same
server block, and NGINX refuses two ``location`` blocks with the same URI. A path is therefore
claimed across all four families at once — by an inline setting or by an attached resource alike — so
every vertical that mounts something on a path checks here rather than only against its own
kind. The render-time mirror of this lives in ``utils/location_claims.py``.

⚠️ Both mirrors compare ``rendered_location()`` output, not the stored value: an anchored path
renders as a regex ``location``, so ``^/api`` and ``~ ^/api`` are one location and must be one
claim. **Normalizing only one mirror produces a false refusal** — the guard rejecting an attach
NGINX would accept — which is what happened when the templates gained the rule and this file did
not. ``tests/unit/db/test_redirects.py`` pins both directions.
"""

from typing import Any, Dict, List, Optional, Tuple

from model import Global_values, Redirects, ResourceAttachments, Resources, Services_settings, Upstreams  # type: ignore
from location_claims import FIXED_LOCATION, rendered_location  # type: ignore
from sqlalchemy import select

# label -> (trigger, setting holding its path). Kept in step with
# ``utils/location_claims.LOCATION_FAMILIES`` — same two special shapes, same reason: a family may
# carry several triggers (``php.conf`` renders for ``REMOTE_PHP`` *or* ``LOCAL_PHP``) and its path
# setting is ``None`` when the template hardcodes the location (``php.conf:2`` is ``location /``).
LOCATION_SETTINGS = {
    "reverse proxy": ("REVERSE_PROXY_HOST", "REVERSE_PROXY_URL"),
    "gRPC": ("GRPC_HOST", "GRPC_URL"),
    "redirect": ("REDIRECT_TO", "REDIRECT_FROM"),
    "PHP": (("REMOTE_PHP", "LOCAL_PHP"), None),
}


def inline_family_paths(session, service_id: str, trigger: Any, path_setting: Optional[str]) -> set:
    """Paths served by one plugin's inline settings on a service.

    A suffix counts only when a trigger setting is non-empty — the exact condition each template
    loops on — so a blanked-out rule never blocks a resource. A family with several triggers is
    served by *any* of them, matching the template's ``or``. Service values shadow global ones,
    matching multisite inheritance.
    """
    triggers = (trigger,) if isinstance(trigger, str) else tuple(trigger)
    wanted = triggers + ((path_setting,) if path_setting else ())
    by_suffix: Dict[int, Dict[str, str]] = {}
    for scope in (
        select(Global_values.setting_id, Global_values.value, Global_values.suffix).where(Global_values.setting_id.in_(wanted)),
        select(Services_settings.setting_id, Services_settings.value, Services_settings.suffix).where(
            Services_settings.service_id == service_id, Services_settings.setting_id.in_(wanted)
        ),
    ):
        for row in session.execute(scope):
            by_suffix.setdefault(row.suffix or 0, {})[row.setting_id] = row.value or ""

    paths = set()
    for values in by_suffix.values():
        if not any(values.get(one) for one in triggers):
            continue
        # A family with no path setting has nothing to read: its template hardcodes the location.
        path = FIXED_LOCATION if path_setting is None else (values.get(path_setting) or "/")
        # ``path_setting`` is not read by the helper — deliberately, so it can never grow a
        # per-family branch — and every other mirror passes "". Keep the four call sites identical.
        paths.add(rendered_location("", path))
    return paths


def inline_location_paths(session, service_id: str, *, families: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
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
    # Compare what NGINX will receive, not what was stored; the messages keep the operator's own
    # spelling, since that is what they have to go and change.
    location = rendered_location("", path)
    for service_id, claimed, kind, name in resource_location_claims(session, service_ids, resource_id):
        if rendered_location("", claimed) == location:
            return (
                f"Cannot attach {subject}: {service_id} already serves {claimed} through the {kind} “{name}”. "
                f"Detach “{name}” from {service_id}, or give one of them a different path."
            )
    for service_id in service_ids:
        inline = inline_location_paths(session, service_id)
        if location in inline:
            return (
                f"Cannot attach {subject}: {service_id} already serves {path} through its own {inline[location]} settings. "
                f"Clear those settings for {path} on {service_id}, or use a different path."
            )
    return ""


def stored_service_setting(session, service_id: str, setting_id: str) -> Optional[str]:
    """The service's OWN stored value, or None when it inherits the global one.

    ``service_setting`` collapses both cases into one value, which is wrong for any caller that
    has to tell "this service overrides the global" apart from "this service follows it".
    """
    value = session.execute(
        select(Services_settings.value).where(Services_settings.service_id == service_id, Services_settings.setting_id == setting_id).limit(1)
    ).scalar_one_or_none()
    return value or None


def service_setting(session, service_id: str, setting_id: str, default: str = "") -> Any:
    """One service's effective value for a setting, falling back to the global one."""
    value = stored_service_setting(session, service_id, setting_id)
    if value is None:
        value = session.execute(select(Global_values.value).where(Global_values.setting_id == setting_id).limit(1)).scalar_one_or_none()
    return value or default


def server_type_attachment_conflict(session, config: Dict[str, Any]) -> str:
    """Reject SERVER_TYPE changes that would make an attached resource invalid."""
    if not any(key == "SERVER_TYPE" or key.endswith("_SERVER_TYPE") for key in config):
        return ""

    multisite = str(config.get("MULTISITE", "no")) == "yes"
    service_ids = set(str(config.get("SERVER_NAME", "")).split())
    attached_service_ids = set(session.scalars(select(ResourceAttachments.service_id).distinct()).all())
    if "SERVER_TYPE" in config:
        service_ids.update(attached_service_ids)
    service_ids.update(service_id for service_id in attached_service_ids if f"{service_id}_SERVER_TYPE" in config)
    for service_id in service_ids:
        # A service that stores its own SERVER_TYPE is untouched by the global key, so the global
        # default riding along in a whole-config payload must not read as a change to it. Getting
        # this wrong made every global save fail for any service with a stream upstream attached.
        explicit = config.get(f"{service_id}_SERVER_TYPE")
        if explicit is not None:
            desired = str(explicit)
        else:
            stored = stored_service_setting(session, service_id, "SERVER_TYPE")
            desired = str(stored if stored is not None else config.get("SERVER_TYPE", service_setting(session, service_id, "SERVER_TYPE", "http")))
        for resource_type, protocol in session.execute(
            select(Resources.type, Upstreams.protocol)
            .join(ResourceAttachments, ResourceAttachments.resource_id == Resources.id)
            .outerjoin(Upstreams, Upstreams.resource_id == Resources.id)
            .where(ResourceAttachments.service_id == service_id)
        ):
            if resource_type == "redirect" and desired != "http":
                return f"Cannot change {service_id} to stream while a redirect is attached"
            if resource_type == "upstream":
                wanted = "stream" if protocol == "stream" else "http"
                if desired != wanted:
                    key = f"{service_id}_SERVER_TYPE" if multisite else "SERVER_TYPE"
                    return f"Cannot set {key} to {desired} while a {protocol} upstream is attached to {service_id}"
    return ""
