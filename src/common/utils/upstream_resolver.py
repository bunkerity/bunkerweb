#!/usr/bin/env python3
"""Flatten upstream pools attached to a service into backend settings.

An upstream pool is a named, reusable group of backends attached to N services. NGINX and the
core plugins know nothing about that: they consume flat, suffixed settings plus an
``upstream {}`` block. This module writes both, just before configuration is materialized.

Every consumer passes its backend through a variable — ``proxy_pass $backendN``,
``grpc_pass $grpc_backendN``, stream ``proxy_pass $backend`` — and with a variable NGINX
matches the address against the defined upstream groups before falling back to the resolver.
So attaching a pool is a matter of writing its name where the host used to be:

* ``http`` pools take the next free ``REVERSE_PROXY_*`` suffix on the service;
* ``grpc`` pools take the next free ``GRPC_*`` suffix;
* ``stream`` pools have no path — they replace the single implicit upstream the stream
  templates build per service, through ``REVERSE_PROXY_UPSTREAM``.

``http`` and ``grpc`` render a ``location`` each into the *same* server, so they share one path
namespace: a path taken by either (a pool or an inline setting) is taken for both. Inline
settings are never renumbered or removed — they keep their suffixes and their NGINX precedence,
pools take the ones left over. A path claimed twice aborts generation instead of shipping a
configuration NGINX refuses.

Like ``redirect_resolver`` it is deliberately dependency-light (no ORM import): the caller
hands it a ``db`` object exposing ``get_service_upstreams()``.
"""

from typing import Any, Dict

from location_claims import claimed_paths, family_occupancy, inline_location_conflict, suffix_key  # type: ignore
from redirect_resolver import config_servers, scan_prefixes  # type: ignore

USE_RP = "USE_REVERSE_PROXY"
USE_GRPC = "USE_GRPC"
# Set on a service whose stream server proxies to a pool; read by the stream templates in place
# of the implicit per-service upstream they otherwise build from REVERSE_PROXY_HOST.
RP_UPSTREAM = "REVERSE_PROXY_UPSTREAM"

# (host setting, url setting, enable setting) per http-context protocol. Both families render a
# ``location`` into the same server, hence the shared path namespace.
LOCATION_FAMILIES = {
    "http": ("REVERSE_PROXY_HOST", "REVERSE_PROXY_URL", USE_RP),
    "grpc": ("GRPC_HOST", "GRPC_URL", USE_GRPC),
}
SCHEMES = {("http", False): "http://", ("http", True): "https://", ("grpc", False): "grpc://", ("grpc", True): "grpcs://"}
# Stream upstream blocks are named after the service in ``stream.conf``. Prefixing the generated
# pool blocks keeps a pool from ever colliding with one of those names — the operator never sees
# it, since a stream attachment exposes no host setting.
STREAM_PREFIX = "bw_stream_"

UPSTREAM_NAME = "UPSTREAM_NAME"
UPSTREAM_PROTOCOL = "UPSTREAM_PROTOCOL"
UPSTREAM_METHOD = "UPSTREAM_METHOD"
UPSTREAM_KEEPALIVE = "UPSTREAM_KEEPALIVE"
UPSTREAM_SERVERS = "UPSTREAM_SERVERS"
# Separator between two ``server`` directives inside UPSTREAM_SERVERS_i. Not a character any
# validated address or option can contain, so the template can split on it blindly.
SERVER_SEPARATOR = ";"

# Highest suffix the generator will allocate. Well above any realistic location count, and only
# there so a corrupt attachment set cannot spin the allocator forever.
MAX_UPSTREAM_SUFFIX = 1000


class UpstreamConflictError(Exception):
    """Two backends claim the same target on one service.

    Raised rather than resolved: the mutation paths (API, save_config) already refuse to create
    this state, so reaching it means the configuration on disk would be one NGINX rejects, or
    would silently depend on ``location`` ordering nobody chose. Aborting keeps the last valid
    configuration.
    """


def _suffix_key(base: str, index: int) -> str:
    return suffix_key(base, index)


def _inline_paths(config: Dict[str, Any], server: str, multisite: bool) -> Dict[str, Dict[int, str]]:
    """Occupied suffixes per proxied family for one server, for suffix allocation."""
    prefixes = scan_prefixes(server, multisite)
    return {protocol: family_occupancy(config, prefixes, host_base, url_base) for protocol, (host_base, url_base, _) in LOCATION_FAMILIES.items()}


def server_directive(server: Dict[str, Any]) -> str:
    """Render one pool member as the arguments of an NGINX ``server`` directive.

    Built here rather than in the template because a setting value is a flat string: the
    template only splits on :data:`SERVER_SEPARATOR` and wraps each part in ``server ...;``.
    Defaults are omitted so the rendered block stays readable and diffable.
    """
    parts = [str(server["host"]).strip()]
    weight = int(server.get("weight", 1) or 1)
    if weight != 1:
        parts.append(f"weight={weight}")
    max_fails = server.get("max_fails", 1)
    if max_fails is not None and int(max_fails) != 1:
        parts.append(f"max_fails={int(max_fails)}")
    fail_timeout = str(server.get("fail_timeout", "10s") or "10s").strip()
    if fail_timeout != "10s":
        parts.append(f"fail_timeout={fail_timeout}")
    if server.get("backup"):
        parts.append("backup")
    if server.get("down"):
        parts.append("down")
    return " ".join(parts)


def nginx_name(pool: Dict[str, Any]) -> str:
    """The name the pool is declared under in the generated configuration."""
    return f"{STREAM_PREFIX}{pool['name']}" if pool.get("protocol") == "stream" else str(pool["name"])


def backend_value(pool: Dict[str, Any]) -> str:
    """What goes into the host setting of an http-context pool: scheme plus pool name."""
    return SCHEMES[(pool.get("protocol", "http"), bool(pool.get("backend_ssl")))] + str(pool["name"])


def _attach_location(out: Dict[str, Any], prefix: str, pool: Dict[str, Any], state: Dict[str, Any], server: str) -> None:
    """Place one http or grpc pool on the service, in its family's next free suffix."""
    protocol = pool.get("protocol", "http")
    host_base, url_base, use_setting = LOCATION_FAMILIES[protocol]
    match_path = pool["match_path"] or "/"

    if match_path in state["foreign"]:
        raise UpstreamConflictError(
            f"Upstream {pool['name']} cannot serve {match_path} on {server}: that path is already served by its "
            f"{state['foreign'][match_path]} configuration. Detach one of them, or move one to another path."
        )
    for index, path in state["claimed"].items():
        if path == match_path:
            origin = "its own inline backend" if index in state["inline"] else "another upstream"
            raise UpstreamConflictError(
                f"Upstream {pool['name']} cannot serve {match_path} on {server}: that path is already served by "
                f"{origin}. Detach one of them, or move one to another path."
            )

    next_index = state["next"][protocol]
    family_taken = state["taken"][protocol]
    while next_index in family_taken:
        next_index += 1
    if next_index > MAX_UPSTREAM_SUFFIX:
        raise UpstreamConflictError(f"Service {server} exceeds the {MAX_UPSTREAM_SUFFIX} location limit")

    out[_suffix_key(f"{prefix}{url_base}", next_index)] = match_path
    out[_suffix_key(f"{prefix}{host_base}", next_index)] = backend_value(pool)
    # The whole template of the consuming plugin is gated on it; without this an attachment on
    # a service that has no other backend of that kind would render nothing at all.
    out[f"{prefix}{use_setting}"] = "yes"

    family_taken[next_index] = match_path
    state["claimed"][(protocol, next_index)] = match_path
    state["next"][protocol] = next_index + 1


def expand_service_upstreams(config: Dict[str, Any], db: Any, logger: Any = None) -> Dict[str, Any]:
    """Return a copy of ``config`` with every attached pool flattened into settings.

    A database read failure degrades to the unchanged config (a transient DB problem must not
    take generation down), but a conflict raises :class:`UpstreamConflictError`.
    """
    if db is None:
        return config.copy()
    try:
        service_upstreams = db.get_service_upstreams()
    except Exception as exc:  # noqa: BLE001 - never break config generation over a DB read
        if logger is not None:
            logger.warning(f"Could not expand upstream resources: {exc}")
        return config.copy()
    if not service_upstreams:
        return config.copy()

    out = config.copy()
    multisite = config.get("MULTISITE", "no") == "yes"
    used: Dict[str, Dict[str, Any]] = {}
    for server in config_servers(config):
        pools = service_upstreams.get(server)
        if not pools:
            continue
        prefix = f"{server}_" if multisite else ""
        taken = _inline_paths(out, server, multisite)
        # Paths are keyed by (protocol, suffix) but compared across protocols on purpose: http
        # and grpc emit a location each into the same server.
        state: Dict[str, Any] = {
            "taken": taken,
            "inline": {(protocol, index) for protocol, suffixes in taken.items() for index in suffixes},
            "claimed": {(protocol, index): path for protocol, suffixes in taken.items() for index, path in suffixes.items()},
            "next": {protocol: 0 for protocol in LOCATION_FAMILIES},
            # Redirects render a location into the same server and are already flattened into
            # REDIRECT_* by the time this runs, so their paths are taken here too.
            "foreign": claimed_paths(out, scan_prefixes(server, multisite), families={"redirect": ("REDIRECT_TO", "REDIRECT_FROM")}),
        }
        stream_pool = ""
        for pool in pools:
            if pool.get("protocol") == "stream":
                if stream_pool:
                    raise UpstreamConflictError(f"Service {server} has two stream upstreams, {stream_pool} and {pool['name']}")
                stream_pool = pool["name"]
                out[f"{prefix}{RP_UPSTREAM}"] = nginx_name(pool)
                out[f"{prefix}{USE_RP}"] = "yes"
            else:
                _attach_location(out, prefix, pool, state, server)
            used[nginx_name(pool)] = pool

    # Only pools that are attached somewhere are declared: NGINX resolves upstream server names
    # at configuration load, so an unused pool pointing at a host that no longer exists would
    # otherwise fail the reload of an entire configuration that does not even use it.
    for index, name in enumerate(sorted(used)):
        pool = used[name]
        out[f"{UPSTREAM_NAME}_{index}"] = name
        out[f"{UPSTREAM_PROTOCOL}_{index}"] = pool.get("protocol") or "http"
        out[f"{UPSTREAM_METHOD}_{index}"] = pool.get("method") or "round_robin"
        out[f"{UPSTREAM_KEEPALIVE}_{index}"] = str(pool["keepalive"]) if pool.get("keepalive") else ""
        out[f"{UPSTREAM_SERVERS}_{index}"] = SERVER_SEPARATOR.join(server_directive(server) for server in pool.get("servers", []))

    return out


def inline_upstream_conflict(config: Dict[str, Any], server: str, attached_paths: Any, *, multisite: bool = True) -> str:
    """Return an error when a service's inline locations collide with its attached pools.

    Used by the settings save path, where the incoming value is an inline reverse-proxy or gRPC
    setting and the pools are what the service already carries — the mirror of the check the
    upstreams mixin runs when the resource side changes.
    """
    return inline_location_conflict(config, server, scan_prefixes(server, multisite), attached_paths)
