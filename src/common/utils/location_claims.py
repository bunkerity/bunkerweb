#!/usr/bin/env python3
"""The per-service HTTP location namespace, shared by every plugin that emits a ``location``.

Four core plugins render a ``location`` into the same server block: ``reverseproxy``
(``proxy_pass``), ``grpc`` (``grpc_pass``), ``redirect`` (``return 3xx``) and ``php``
(``try_files``). NGINX refuses two ``location`` blocks with the same URI outright, so a path
claimed by any of them is claimed for all of them — even though each family stores its rules
under its own suffixed settings.

Both resolvers scan this namespace: for **allocation** each needs only its own family's
occupied suffixes, but for **conflict detection** all four families must be considered
together. Keeping the two concerns in one module is what stops the next vertical from
re-implementing half of it and reopening the hole.

Registering a family here is what makes it visible to *every* conflict check at once, which is
the whole point: ``php`` was missing for four releases and its unconditional ``location /``
reached NGINX as ``duplicate location "/"`` — an ``[emerg]`` that refuses the entire reload —
whenever the service also carried a reverse proxy, a gRPC backend or a redirect on the default
path.
"""

from typing import Any, Dict, List, Optional

# label -> (trigger, setting holding its path). The trigger is the exact condition each template
# loops on, so a blanked-out rule frees its path instead of blocking it. Two shapes are allowed
# for the family whose template does not follow the usual one-trigger-one-path-setting form:
#
# * a **tuple of triggers** — ``php.conf`` renders its location for ``REMOTE_PHP`` *or*
#   ``LOCAL_PHP``, so either one claims the path and setting both still claims it once.
# * ``None`` as the path setting — ``php.conf:2`` hardcodes ``location /``; PHP has no
#   configurable path, so its claim is always ``FIXED_LOCATION``.
LOCATION_FAMILIES = {
    "reverse proxy": ("REVERSE_PROXY_HOST", "REVERSE_PROXY_URL"),
    "gRPC": ("GRPC_HOST", "GRPC_URL"),
    "redirect": ("REDIRECT_TO", "REDIRECT_FROM"),
    "PHP": (("REMOTE_PHP", "LOCAL_PHP"), None),
}

# label -> the enable switch its template is wrapped in, for the families that have one.
# ``reverse-proxy.conf:1`` renders nothing unless ``USE_REVERSE_PROXY`` is ``yes`` and
# ``grpc.conf:1`` nothing unless ``USE_GRPC`` is, so a ``*_HOST`` left behind by a family that was
# switched off claims no location at all — counting it refuses saves NGINX would accept. Absent
# here: ``redirect``, whose template has no switch, and ``PHP``, whose switch *is* its triggers.
FAMILY_SWITCHES = {
    "reverse proxy": "USE_REVERSE_PROXY",
    "gRPC": "USE_GRPC",
}

# The path a family with no path setting claims — what ``php.conf`` hardcodes.
FIXED_LOCATION = "/"

# Every setting that can make a location render, flattened. The save path uses it to skip the
# whole conflict check when nothing in the incoming config could possibly emit a location.
LOCATION_TRIGGERS = tuple(t for trigger, _ in LOCATION_FAMILIES.values() for t in ((trigger,) if isinstance(trigger, str) else trigger))


# The four modifiers NGINX accepts in a ``location``. Anything else in that slot is a literal URI.
NGINX_LOCATION_MODIFIERS = ("~", "~*", "=", "^~")


def rendered_location(path_setting: str, path: str) -> str:
    """The ``location`` URI NGINX will actually see, so two spellings of one location collide.

    All three templates render an anchored path as a regex location — the ``url_is_regex`` /
    ``from_is_regex`` set in ``reverse-proxy.conf``, ``grpc.conf`` and ``redirect.conf`` — which
    makes the ``~`` implicit, so ``^/api`` and ``~ ^/api`` both produce ``location ~ ^/api`` and
    NGINX refuses the pair with *duplicate location*. Claiming the raw value lets both through
    the conflict check and the service then fails to start.

    ⚠️ ``db_methods/locations.py`` is the mutation-time mirror of this and calls this same
    function. The two must move together: normalizing one alone produces a *false refusal*, and
    ``tests/unit/db/test_redirects.py`` pins that.
    """
    parts = path.split()
    if parts and parts[0] in NGINX_LOCATION_MODIFIERS:
        return " ".join(parts)  # collapse the separator so "~  /a" and "~ /a" are one claim
    if path.startswith("^") or path.endswith("$"):
        return f"~ {path}"
    return path


def suffix_key(base: str, index: int) -> str:
    return base if index == 0 else f"{base}_{index}"


def _trigger_occupancy(config: Dict[str, Any], prefixes: List[str], trigger: str, path_setting: Optional[str]) -> Dict[int, str]:
    """``{suffix: path}`` for the locations one trigger setting renders for one server.

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
            if path_setting is None:
                taken[index] = FIXED_LOCATION
                continue
            taken[index] = str(config.get(suffix_key(f"{prefix}{path_setting}", index), "") or config.get(suffix_key(path_setting, index), "/") or "/")
    return taken


def family_occupancy(config: Dict[str, Any], prefixes: List[str], trigger: Any, path_setting: Optional[str]) -> Dict[int, str]:
    """``{suffix: path}`` for one family's locations that actually render for one server.

    A family may carry several triggers (``php.conf`` renders for ``REMOTE_PHP`` *or*
    ``LOCAL_PHP``). Each is scanned on its own and the results unioned, which is what the
    template's ``or`` means: scanning them as one pass would let a blank in the second trigger
    pop the claim the first one legitimately made.
    """
    taken: Dict[int, str] = {}
    for one_trigger in (trigger,) if isinstance(trigger, str) else trigger:
        taken.update(_trigger_occupancy(config, prefixes, one_trigger, path_setting))
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


def claim_counts(config: Dict[str, Any], prefixes: List[str], *, families: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
    """``{path: [family label, ...]}`` — *every* claim on a location, not just the first one.

    ``claimed_paths`` keeps one label per path, which is all its callers need ("taken, and by
    whom") and is exactly what made the registry blind to a collision *inside* the incoming
    config: two families landing on the same default path, or two suffixes of one family, both
    collapsed onto a single entry and nothing was ever reported. Counting has to be its own pass
    for that reason — re-reading ``claimed_paths`` would still see one claim per path.

    Suffixes are walked in numeric order so the labels, and therefore the error naming them,
    come out the same on every run.
    """
    counts: Dict[str, List[str]] = {}
    for label, (trigger, path_setting) in (families or LOCATION_FAMILIES).items():
        occupancy = family_occupancy(config, prefixes, trigger, path_setting)
        for index in sorted(occupancy):
            counts.setdefault(rendered_location(path_setting, occupancy[index]), []).append(label)
    return counts


def claimed_paths(config: Dict[str, Any], prefixes: List[str], *, families: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """``{path: family label}`` for every location that renders for one server.

    Used for conflict detection, where what matters is that the path is taken at all — not by
    which family, beyond naming it in the error. The first claim on a path wins, as it always
    has; :func:`claim_counts` is the one that can see the rest.
    """
    return {path: labels[0] for path, labels in claim_counts(config, prefixes, families=families).items()}


def family_enabled(config: Dict[str, Any], prefixes: List[str], label: str) -> bool:
    """Whether the family's template will render a location at all for one server.

    Resolved least specific first, the same merge :func:`_trigger_occupancy` applies, so a
    server-specific switch overrides the global one. An **absent** switch counts as enabled: the
    incoming config is not always the whole merged config — a scheduler env or a label save
    carries only what changed — so only an explicit ``no`` proves the location cannot render.
    """
    setting = FAMILY_SWITCHES.get(label)
    if setting is None:
        return True
    enabled = True
    for prefix in prefixes:
        value = config.get(f"{prefix}{setting}")
        if value is not None:
            enabled = str(value).strip() == "yes"
    return enabled


def inline_family_conflict(config: Dict[str, Any], server: str, prefixes: List[str]) -> str:
    """Return an error when the incoming config claims one location twice on its own.

    :func:`inline_location_conflict` only ever compares the incoming settings against what the
    service carries through *attached resources*, so a config that collides with itself — a
    reverse proxy and a redirect both defaulting to ``/``, PHP enabled next to either of them,
    or two suffixes of one family with no path of their own — passed the save untouched and
    reached NGINX as ``duplicate location``, which refuses the whole reload. Refusing here keeps
    it out of the database instead, the way the attached-resource guard already does.

    Only the families whose template will actually render are counted (:func:`family_enabled`):
    a ``GRPC_HOST`` left behind with ``USE_GRPC`` off emits nothing, and refusing on it would
    freeze *every* save — ``services.py`` and ``global_settings.py`` send the full config
    snapshot, so one service with a dormant host would take the whole fleet down with it. The
    other two consumers of the registry keep their existing semantics on purpose: this is the
    only check that reads a claim as a *veto*.
    """
    families = {label: pair for label, pair in LOCATION_FAMILIES.items() if family_enabled(config, prefixes, label)}
    for path, labels in claim_counts(config, prefixes, families=families).items():
        if len(labels) < 2:
            continue
        if labels[0] == labels[1]:
            return (
                f"Cannot save these settings: {server} would serve {path} twice through its {labels[0]} settings. "
                f"Give one of them a different path, or clear it."
            )
        return (
            f"Cannot save these settings: {server} would serve {path} through both its {labels[0]} and its {labels[1]} "
            f"settings, and NGINX refuses two locations with the same URI. Give one of them a different path, or clear it."
        )
    return ""
