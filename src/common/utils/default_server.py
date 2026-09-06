#!/usr/bin/env python3
"""The reserved ``default-server`` pseudo-service.

The default server is the NGINX block that answers every request matching no configured service —
an unknown SNI, a raw IP, a ``Host`` nobody serves. It used to be rendered from the GLOBAL
configuration only (``gen/Templator.py:_render_global``), so nothing about it was configurable per
se: no certificate of its own, no error pages, no headers.

Option (b) of the conception gives it one permanent row in ``bw_services`` under the id below. That
row is an ordinary service everywhere it is convenient (settings storage, per-site variables table,
UI page, API GET) and a refused one everywhere it would be wrong: it is never created, never
deleted, never renamed, never billed, and it never gets a ``server{}`` block of its own — its
settings render into ``default-server-http.conf``.

Two constants, one module, because five layers need the same answer and a second copy of the string
is how these things rot: Templator, ``http.conf``/``stream.conf`` (through ``import()``),
``db_methods/config_save.py``, ``utils/service_classification.py``, the API router and the UI.
"""

from os import sep
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from common_utils import get_integration  # type: ignore
from ports import (  # type: ignore
    HTTPS_PORT_SETTING,
    HTTP_PORT_SETTING,
    STREAM_PORT_SETTING,
    STREAM_SSL_PORT_SETTING,
    collect_ports,
    reserved_ports,
    services_from_config,
    union_ports,
)

__all__ = (
    "DEFAULT_SERVER_ID",
    "DEFAULT_SERVER_RESERVED_MESSAGE",
    "DEFAULT_SERVER_SERVER_TYPE_MESSAGE",
    "DEFAULT_SERVER_METHOD",
    "DEFAULT_SERVER_PLUGINS",
    "DEFAULT_SERVER_SEEDED_SETTINGS",
    "DEFAULT_SERVER_STREAM_PORTS_SETTING",
    "DEFAULT_SERVER_STREAM_SSL_PORTS_SETTING",
    "DEFAULT_SERVER_STREAM_TLS_SETTINGS",
    "default_server_stream_listeners",
    "default_server_stream_refusal",
    "blocked_stream_ports",
    "is_default_server",
    "is_reserved_default_server",
    "strip_default_server",
)

# The reserved service id. NOT "_": that string is already the default-server marker at runtime
# (`server_name _;`, and `utils.lua:768` / `misc/.../disable.conf:12` treat it as "no service"), and
# reusing it would mean revisiting every plugin that tests for it. A real, matchable name would be a
# hostname collision, so the id is deliberately one no public hostname can be: it has no dot, and
# `default-server` is not a registrable TLD.
DEFAULT_SERVER_ID = "default-server"

# The row is seeded with an EXISTING method value on purpose — no new value in the native
# `methods_enum` (`db/model.py:33`), because adding one is a PostgreSQL migration. "wizard" is the
# only value that is BOTH in `EDITABLE_METHODS` (`db_methods/common.py:87` — the UI and the API can
# write it) and already carries the 403-on-delete precedent
# (`api/app/routers/services.py:275`).
DEFAULT_SERVER_METHOD = "wizard"

# The one sentence every surface says when it refuses an operation on the reserved row. Here rather
# than in the API router because the UI refuses the same operations on the same id and an operator
# who reads two different explanations for one refusal learns nothing from either. The router
# appends its own "edit it with PATCH" hint; the UI page IS that hint.
DEFAULT_SERVER_RESERVED_MESSAGE = (
    f"{DEFAULT_SERVER_ID} is the reserved default server: it answers requests that match no configured "
    "service (unknown hostnames, raw IP access), so it cannot be created, renamed or deleted."
)

# Why `SERVER_TYPE` is refused on the reserved row rather than ignored (DS-B's open item 5). The
# value would be stored, shown on the page and do nothing: the reserved id is dropped from the
# roster both `http.conf` and `stream.conf` iterate, so it never gets a `server{}` block of either
# kind. Its HTTP half IS the default server block, and its stream half is
# `DEFAULT_SERVER_STREAM_PORTS`. A setting that is saved and inert is the exact failure mode the
# curated plugin subset exists to avoid, so both save surfaces say no.
DEFAULT_SERVER_SERVER_TYPE_MESSAGE = (
    f"SERVER_TYPE cannot be set on the reserved {DEFAULT_SERVER_ID} service: it has no server block of its own to "
    "switch. Its HTTP half is the default server block itself, and its stream half is the "
    "DEFAULT_SERVER_STREAM_PORTS setting."
)

# The curated plugin subset the default server exposes (PO ruling 5). Default-DENY: a plugin absent
# from this tuple never runs in the default block and is never offered on its page.
#
# Kept: the four `ssl_certificate` providers, the TLS knobs, the error pages, the response headers,
# the whitelist and `misc` (DISABLE_DEFAULT_SERVER / DENY_HTTP_STATUS).
# Refused: `reverseproxy`, `grpc`, `redirect` (there is no `Host` to route), `sessions`, `antibot`,
# `mtls`, `cors`, `authbasic` — everything that assumes a service identity. Rendering them here
# produces configuration that is valid and inert, which is worse than refusing them.
DEFAULT_SERVER_PLUGINS = (
    "certificates",
    "customcert",
    "errors",
    "headers",
    "letsencrypt",
    "misc",
    "selfsigned",
    "ssl",
    "whitelist",
)

# The values the reserved row is SEEDED with when it is created (PO ruling of 2026-09-03). The three
# phase runners are unconditional, so without these an upgrade would silently change what the
# catch-all block does to legitimate by-IP / unknown-`Host` traffic, on deployments that never asked
# for it:
#
# * `ssl:access` answers a plain-HTTP request with a 301 to https as soon as ONE of
#   AUTO_LETS_ENCRYPT / USE_CUSTOM_SSL / GENERATE_SELF_SIGNED_SSL is `yes` globally (the reserved row
#   inherits it) and AUTO_REDIRECT_HTTP_TO_HTTPS is `yes` -- which is the shipped default.
# * `whitelist` was SKIPPED on the default server until now (`whitelist.lua:85` returns false while
#   `ctx.bw.server_name` is `_`, and the runner rebinds it to the reserved id), and USE_WHITELIST
#   ships as `yes`. It denies nothing, but it puts a per-request rDNS/ASN lookup on catch-all
#   traffic and short-circuits the chain on a match.
#
# Deliberately NOT seeded, because they break no legitimate client and are the point of the
# chantier: ban enforcement, the `headers` chain, the `letsencrypt` ACME challenge, and
# `certificates` (which needs an inventory attachment the reserved row has none of at upgrade).
# ALLOWED_METHODS is not seeded either (PO, same ruling): `misc:access` now answers 405 to anything
# outside `GET|POST|HEAD|QUERY` on a hostname that does not exist, which is wanted.
#
# Written ONLY when the row is created -- see `db_methods/services.py:seed_default_server_service`.
# An operator's later edits are never overwritten.
DEFAULT_SERVER_SEEDED_SETTINGS = {
    "AUTO_REDIRECT_HTTP_TO_HTTPS": "no",
    "REDIRECT_HTTP_TO_HTTPS": "no",
    "USE_WHITELIST": "no",
}


def is_default_server(name: Any) -> bool:
    """True when ``name`` is the reserved id."""
    return isinstance(name, str) and name.strip() == DEFAULT_SERVER_ID


def is_reserved_default_server(service: Optional[Mapping[str, Any]]) -> bool:
    """True when this service ROW is the reserved pseudo-service, id AND method.

    The id alone is not enough. `default-server` is an ordinary string until 1.7 reserves it, so an
    upgraded database can hold a row an operator created under that name — a `ui`, `autoconf` or
    `scheduler` service with a reverse proxy behind it. The seeding refuses to adopt such a row
    (`db_methods/services.py`), and every refusal built for the reserved service — no rename, no
    delete, no draft — has to lift for it, or the operator's only exit from a site that
    `http.conf`/`stream.conf` already drop from their roster is a direct database edit.

    `wizard` is the reserved row's method (`DEFAULT_SERVER_METHOD`). A wizard-created service that
    happens to be named `default-server` is therefore indistinguishable from the reserved row and is
    treated as it — a deliberate consequence of reusing an existing `methods_enum` value instead of
    migrating for a new one, and the reason the seeding logs the collision it cannot resolve.
    """
    if not service:
        return False
    return is_default_server(service.get("id")) and service.get("method") == DEFAULT_SERVER_METHOD


def strip_default_server(names: Optional[Iterable[Any]]) -> List[Any]:
    """``names`` without the reserved id, order preserved."""
    return [name for name in (names or ()) if not is_default_server(name)]


# The reserved service's own stream port lists (`core/misc/plugin.json`). Multisite and empty by
# default, so it only ever exists as `default-server_DEFAULT_SERVER_STREAM_PORTS*` and no
# deployment gains a stream default server without asking for one.
#
# The SSL list is a SUBSET of the first, not a second set of listeners: it is the TLS switch of the
# ports already declared. It replaces the `LISTEN_STREAM_PORT_SSL` overload DS-B rendered the switch
# from -- that setting belongs to a stream SERVICE, defaults to `4242`, and lives in the `general`
# pseudo-plugin, so the reserved row inherited a value nobody typed and there was no field on the
# Default server page to change it.
DEFAULT_SERVER_STREAM_PORTS_SETTING = "DEFAULT_SERVER_STREAM_PORTS"
DEFAULT_SERVER_STREAM_SSL_PORTS_SETTING = "DEFAULT_SERVER_STREAM_PORTS_SSL"

# The TLS parameters the stream default block prints. They belong to the `ssl` plugin, which IS in
# `DEFAULT_SERVER_PLUGINS` and therefore offered on the Default server page -- but `stream.conf` is
# an ordinary GLOBAL template, so it never receives `Templator._default_server_template_vars` and
# would print the GLOBAL values while `default-server-http.conf` prints the reserved service's. One
# page, one setting, two answers. Templator hands these down derived instead
# (`DEFAULT_SERVER_TLS_RENDER`), which is the same trick `DEFAULT_SERVER_STREAM_PORTS_RENDER` uses.
DEFAULT_SERVER_STREAM_TLS_SETTINGS = ("SSL_PROTOCOLS", "SSL_CIPHERS_LEVEL", "SSL_CIPHERS_CUSTOM", "SSL_ECDH_CURVE")


def default_server_stream_listeners(
    service_configs: Mapping[str, Mapping[str, Any]],
    blocked_ports: Optional[Mapping[str, str]] = None,
) -> Tuple[List[str], List[str], Dict[str, str], List[str]]:
    """``(ports, ssl_ports, refused, orphan_ssl)`` for the stream default server.

    ``service_configs`` is ``{service: merged config}`` -- Templator's ``_service_configs()``, the
    reserved row included.

    A GLOBAL ``DEFAULT_SERVER_STREAM_PORTS`` reaches this function and opens listeners. The gate
    said it would "only ever exist as ``default-server_DEFAULT_SERVER_STREAM_PORTS*``"; that is not
    how the platform works, and reading "the reserved service's own keys" instead does not change it
    -- both config producers materialise an inherited copy of every multisite setting under every
    service name (``gen/Configurator.py:387``, ``db_methods/config_read.py:219``, with only
    ``port_list_setting()`` members exempt), so by the time the config is split there is no such
    thing as a key the reserved service did not "declare".
    ``TestWhatAGlobalWriteDoes`` in ``tests/unit/gen/test_default_server_stream.py`` renders it.

    Why a port a service declares is REFUSED rather than shared: stream has no SNI on plain TCP and
    none at all on UDP, so NGINX picks the block by ``address:port`` alone and a ``default_server``
    on that pair WINS over the service's block. Rendering both would silently move that service's
    traffic to a listener whose whole job is to answer and close. The refusal therefore fails safe
    towards the real service, never towards the catch-all -- here at generation time as well as in
    the API, because a service can declare the port after the reserved list was saved.

    ``blocked_ports`` is ``{port: what already holds it}`` for everything that is NOT a stream
    service and still cannot be shared: every http/https listener in the deployment and every port
    the product binds for itself. That is not a nicety -- ``http{}`` and ``stream{}`` open their own
    sockets, so a stream ``default_server`` on an http port makes NGINX refuse to start
    (``utils/ports.py:24-32`` documents it as the one FATAL collision), and
    ``DEFAULT_SERVER_STREAM_PORTS=8080`` is the shipped ``HTTP_PORT`` default, i.e. the single most
    likely number an operator types. ``check_ports`` cannot catch it because these ports never enter
    its inventory.

    ``ssl_ports`` is the subset of ``ports`` the reserved service also lists in
    ``DEFAULT_SERVER_STREAM_PORTS_SSL`` -- the TLS switch of the ports it already declared, not a
    second set of listeners. ``orphan_ssl`` is what that list names and the port list does not: the
    renderer cannot honour those (there is no listener to switch), so it drops them and the caller
    says so out loud rather than leaving an operator staring at a plaintext port they thought they
    had secured. Both save surfaces refuse the same thing up front
    (``default_server_stream_refusal``); this is the generation-time half, for a pair that reached
    the database another way (an env file, an autoconf label, a direct write).
    """
    reserved = service_configs.get(DEFAULT_SERVER_ID) or {}
    wanted = collect_ports(reserved, DEFAULT_SERVER_STREAM_PORTS_SETTING)
    declared_ssl = collect_ports(reserved, DEFAULT_SERVER_STREAM_SSL_PORTS_SETTING)
    ssl_ports = set(declared_ssl)

    claimed: Dict[str, str] = {}
    for service, config in service_configs.items():
        if is_default_server(service):
            continue
        # The same two conditions `stream.conf` and `server-stream.conf` render on: a service whose
        # block NGINX never loads cannot collide with anything, and refusing a port because of it
        # would be a refusal an operator cannot explain.
        if str(config.get("SERVER_TYPE", "http")).strip() != "stream":
            continue
        if str(config.get("LISTEN_STREAM", "yes")).strip() != "yes":
            continue
        for port in collect_ports(config, STREAM_PORT_SETTING) + collect_ports(config, STREAM_SSL_PORT_SETTING):
            claimed.setdefault(port, service)

    for port, holder in (blocked_ports or {}).items():
        claimed.setdefault(str(port), holder)

    ports: List[str] = []
    refused: Dict[str, str] = {}
    for port in wanted:
        if port in claimed:
            refused[port] = claimed[port]
        elif port not in ports:
            ports.append(port)
    return ports, [port for port in ports if port in ssl_ports], refused, [port for port in declared_ssl if port not in wanted]


def default_server_stream_refusal(config: Mapping[str, Any], declared: Optional[Iterable[Any]] = None) -> Optional[str]:
    """Why the reserved service's stream port list cannot be saved, or ``None``.

    ``config`` is the whole flat configuration about to be persisted -- the merge, because the port
    and the service that owns it can arrive in different requests and only the merge says whether
    the pair collides.

    ``declared`` is the ports the REQUEST carries for EITHER list (``DEFAULT_SERVER_STREAM_PORTS``
    and ``DEFAULT_SERVER_STREAM_PORTS_SSL``), when the caller knows them. Only a problem on one of
    those is refused: a service can take a port the reserved list already held, and refusing every
    later save on the Default server page for it -- including one that only changes the certificate,
    on a pane that may not even show the port field -- would lock the page over stored state the
    renderer already neutralises by dropping the port. Pass nothing and every problem is refused,
    which is the right default for a caller that cannot tell.

    Two refusals, both on the reserved row's own pair:

    * a port some other listener already holds (see ``default_server_stream_listeners``);
    * an SSL port the port list does not contain. ``DEFAULT_SERVER_STREAM_PORTS_SSL`` is the TLS
      switch of the ports the default server declares, so a port only in the SSL list has no
      listener to switch and the renderer drops it -- silently, if nobody says this here.

    Shared by BOTH save surfaces on purpose. The API services router is not the UI's save path
    (`ui/app/models/config.py` goes to `save_config` directly), so a refusal that lived in the
    router alone would let the page PO ruling 7 designates for configuring the default server save
    a colliding port and have it silently dropped at generation time.
    """
    names = (config.get("SERVER_NAME", "") or "").split()
    if DEFAULT_SERVER_ID not in names:
        return None
    service_configs = services_from_config(config, names, multisite=True)
    _, _, refused, orphan_ssl = default_server_stream_listeners(service_configs, blocked_stream_ports(config, service_configs))
    if declared is not None:
        wanted = {str(port).strip() for port in declared if str(port).strip()}
        refused = {port: owner for port, owner in refused.items() if port in wanted}
        orphan_ssl = [port for port in orphan_ssl if port in wanted]
    if not refused and not orphan_ssl:
        return None
    messages = [
        f"Default server stream port {port} is refused: {owner} already listens on it. Without SNI the default server "
        "would answer that traffic instead, and on an HTTP or product port NGINX refuses to start at all."
        for port, owner in sorted(refused.items())
    ]
    messages += [
        f"Default server stream SSL port {port} is refused: {DEFAULT_SERVER_STREAM_SSL_PORTS_SETTING} must be a subset of "
        f"{DEFAULT_SERVER_STREAM_PORTS_SETTING}, and {port} is not in it. The default server has no listener on a port it "
        "does not declare, so there is nothing there to serve over TLS."
        for port in sorted(orphan_ssl)
    ]
    return "; ".join(messages)


def blocked_stream_ports(
    global_config: Mapping[str, Any], service_configs: Mapping[str, Mapping[str, Any]], all_in_one: Optional[bool] = None
) -> Dict[str, str]:
    """``{port: what holds it}`` for the ports a stream ``default_server`` may never take.

    Not the stream services -- those are elected against separately, and losing to one costs that
    service its traffic. These are the two that cost more: ``http{}`` and ``stream{}`` open their
    own sockets, so the same port in both makes NGINX refuse to START (``utils/ports.py:24-32``),
    and the product's own ports (healthcheck, the internal API) are not negotiable either.
    ``DEFAULT_SERVER_STREAM_PORTS=8080`` -- the shipped ``HTTP_PORT`` default -- is exactly that
    fatal case, and neither `check_ports` nor the stream election saw it before.

    ``all_in_one`` decides whether the two all-in-one ports (7000, the web UI; 8888, the API
    service) join the reserved set. Detected the way ``Templator._report_port_issues`` detects it
    when the caller does not say, and detected the same way in the API and UI processes because the
    all-in-one image IS one container: supervisord holds those two sockets in the same network
    namespace as NGINX, so a stream ``default_server`` on 7000 there is the same "NGINX will not
    start" class as an HTTP port, and ``check_ports`` already treats them as un-takeable for
    ordinary services.
    """
    if all_in_one is None:
        all_in_one = get_integration() != "Linux" and Path(sep, "etc", "supervisor.d").is_dir()
    blocked: Dict[str, str] = {}
    for setting, what in ((HTTP_PORT_SETTING, "an HTTP listener"), (HTTPS_PORT_SETTING, "an HTTPS listener")):
        for port in union_ports(global_config, service_configs, setting):
            blocked.setdefault(str(port), what)
    for port, what in reserved_ports(global_config, all_in_one=all_in_one).items():
        blocked.setdefault(str(port), what)
    return blocked
