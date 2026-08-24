#!/usr/bin/env python3
"""Data-plane listen ports: inventory, ``reuseport`` ownership and conflict report.

Pure functions, no I/O and no NGINX, so the same code can answer at write time
(API / UI / autoconf) and at render time (Configurator / Templator) instead of
two layers disagreeing about the same configuration.

Why the module exists at all — three NGINX facts read in the vendored source
(``src/deps/src/nginx``, 1.30.4) that a Jinja template cannot express, because a
template only ever sees ONE server block while these rules are about the set of
blocks sharing an ``addr:port``:

* listen OPTIONS belong to the ``addr:port``, not to the ``server`` block. Two
  blocks that both *set* an option on one ``addr:port`` are **fatal**:
  ``ngx_http.c:1294-1300`` and ``ngx_stream.c:489-497`` emit
  ``"duplicate listen options for %V"`` and refuse to start.
* ``reuseport`` is exactly such an option — ``ngx_stream_core_module.c:1192-1196``
  and ``ngx_http_core_module.c:4225-4229`` set ``lsopt.set`` — hence
  :func:`stream_reuseport_owners`: it may be emitted only ONCE per ``addr:port``.
* ``ssl`` / ``proxy_protocol`` / ``http2`` do NOT set that flag. They are silently
  UNIONed over the blocks of a shared port (``ngx_http.c:1320-1352``): a divergence
  is a warning here, never fatal, because NGINX will start and quietly apply the
  option to services that never asked for it.

The port list of a subsystem is keyed on ``(port, type, family)``
(``ngx_stream.c:414-416``): TCP and UDP on the same number do not collide, and
neither do IPv4 and IPv6. The ``http`` and ``stream`` subsystems, on the other
hand, open their own sockets — the same TCP port in both is a plain
``EADDRINUSE`` at bind time, which is why that one IS fatal here.

Ownership assumption, stated because it is the one thing this module cannot see:
a service listed in ``SERVER_NAME`` is assumed to get its own server block. That
is what ``Configurator.get_config`` guarantees by materialising
``<service>_SERVER_NAME`` for every service (``Configurator.py:334-360``), and
what ``http.conf:105-127`` / ``stream.conf:49-78`` then include. A service that
is only an *alias* inside another service's ``SERVER_NAME`` list gets no block of
its own; it must not be passed in as a service here, or it would be handed an
ownership its block never renders.
"""

from typing import Any, Dict, FrozenSet, List, Mapping, NamedTuple, Optional, Sequence, Tuple

__all__ = (
    "HTTPS_PORT_SETTING",
    "HTTP_PORT_SETTING",
    "HEALTHCHECK_PORT",
    "Listener",
    "PortIssue",
    "PRIVILEGED_PORT_CEILING",
    "STREAM_PORT_SETTING",
    "STREAM_SSL_PORT_SETTING",
    "check_ports",
    "collect_ports",
    "inventory",
    "parse_port",
    "reserved_ports",
    "stream_reuseport_owners",
    "union_ports",
)

HTTP_PORT_SETTING = "HTTP_PORT"
HTTPS_PORT_SETTING = "HTTPS_PORT"
STREAM_PORT_SETTING = "LISTEN_STREAM_PORT"
STREAM_SSL_PORT_SETTING = "LISTEN_STREAM_PORT_SSL"

MIN_PORT = 0
MAX_PORT = 65535
# Binding below this needs CAP_NET_BIND_SERVICE; the images run as `nginx`
# (src/bw/Dockerfile:138, src/all-in-one/Dockerfile:277) so they cannot.
PRIVILEGED_PORT_CEILING = 1024

# Fixed product ports. The API ports are settings and are read from the config.
HEALTHCHECK_PORT = 6000  # src/common/confs/healthcheck.conf:7 (hardcoded)
ALL_IN_ONE_UI_PORT = 7000  # src/all-in-one/entrypoint.sh:212
ALL_IN_ONE_API_PORT = 8888  # src/all-in-one/entrypoint.sh:223

FATAL = "fatal"
WARNING = "warning"


class Listener(NamedTuple):
    """One rendered ``listen`` directive, reduced to what decides a collision."""

    service: str
    subsystem: str  # "http" | "stream"
    port: int
    proto: str  # "tcp" | "udp"
    ssl: bool
    setting: str  # the setting key the port came from, for the message


class PortIssue(NamedTuple):
    level: str  # FATAL | WARNING
    message: str


def parse_port(value: Any) -> Optional[int]:
    """``value`` as a port number, or ``None`` when it is not one.

    Empty is not an error: every port setting documents "leave empty to disable"
    (``settings.json:23``), so an empty value means "no listener", not "bad value".
    """
    text = str(value).strip()
    if not text or not text.isdigit():
        return None
    port = int(text)
    if port < MIN_PORT or port > MAX_PORT:
        return None
    return port


def collect_ports(config: Mapping[str, Any], setting: str) -> List[str]:
    """Raw values of ``SETTING`` and its ``SETTING_<N>`` repetitions, in dict order.

    Empty values are dropped — that is the ``and port`` guard the per-service
    templates already carry (``server-http/server.conf:24``), expressed once.

    The suffix must be all digits, which is how ``LISTEN_STREAM_PORT_SSL`` stops
    being read as a repetition of ``LISTEN_STREAM_PORT``. The templates achieve
    the same with a second ``startswith`` (``server-stream.conf:24``).
    """
    prefix = f"{setting}_"
    ports = []
    for key, value in config.items():
        if key != setting and not (key.startswith(prefix) and key[len(prefix) :].isdigit()):  # noqa: E203
            continue
        port = str(value).strip()
        if port:
            ports.append(port)
    return ports


def _protocols(config: Mapping[str, Any]) -> Tuple[str, ...]:
    """Stream protocols of a service, in the order ``server-stream.conf:29-30`` builds them."""
    protocols = []
    if str(config.get("USE_TCP", "yes")).strip() == "yes":
        protocols.append("tcp")
    if str(config.get("USE_UDP", "no")).strip() == "yes":
        protocols.append("udp")
    return tuple(protocols)


def stream_reuseport_owners(services: Mapping[str, Mapping[str, Any]]) -> Dict[str, FrozenSet[str]]:
    """``{service: {"<proto>:<port>", ...}}`` — who may emit ``reuseport``.

    First declarer wins, in the iteration order of ``services`` (which is
    ``SERVER_NAME`` order). Every other service sharing that ``(proto, port)``
    renders the same ``listen`` line *without* the option, which is what keeps
    NGINX from refusing to start (``ngx_stream.c:489-497``).

    A single-service deployment owns all of its own ports, so its rendering is
    byte-identical to the unconditional ``reuseport`` this replaces.
    """

    def tokens(config: Mapping[str, Any]) -> List[str]:
        return [f"{proto}:{port}" for port in collect_ports(config, STREAM_PORT_SETTING) for proto in _protocols(config)]

    owners: Dict[str, FrozenSet[str]] = {}
    claimed = set()
    # Pass 1 -- the blocks NGINX actually loads. `stream.conf:52` includes a service's
    # server-stream.conf only when its SERVER_TYPE is `stream`, and `server-stream.conf:27`
    # renders no listen line at all when LISTEN_STREAM is off. Those are the only blocks that can
    # collide, so they are the only ones that arbitrate.
    for service, config in services.items():
        if str(config.get("LISTEN_STREAM", "yes")).strip() != "yes":
            owners[service] = frozenset()
            continue
        if str(config.get("SERVER_TYPE", "http")).strip() != "stream":
            continue
        owned = set()
        for token in tokens(config):
            if token not in claimed:
                claimed.add(token)
                owned.add(token)
        owners[service] = frozenset(owned)

    # Pass 2 -- every other service. Templator renders a server-stream.conf for an HTTP service
    # too, but `stream.conf` never includes it: that file cannot collide with anything, so it must
    # keep rendering byte for byte what it rendered before, and it must NOT consume a claim from a
    # block that IS loaded. Hence a second pass rather than a branch in the first.
    for service, config in services.items():
        if service not in owners:
            owners[service] = frozenset(tokens(config))
    return owners


def union_ports(global_config: Mapping[str, Any], services: Mapping[str, Mapping[str, Any]], setting: str) -> List[str]:
    """Every port a block may listen on for ``setting``: global first, then per service.

    The default server must cover this union or a service-only port has no
    ``default_server`` at all, and ``DISABLE_DEFAULT_SERVER`` / strict SNI stop
    applying on it (constat C5 of the conception).

    Global values come first and keep their order, so a configuration with no
    per-service override yields exactly the list the template used to build from
    ``all.items()`` — that is what makes the byte-identity acceptance hold.
    """
    ports = []
    seen = set()
    for port in collect_ports(global_config, setting):
        if port not in seen:
            seen.add(port)
            ports.append(port)
    for config in services.values():
        for port in collect_ports(config, setting):
            if port not in seen:
                seen.add(port)
                ports.append(port)
    return ports


def inventory(services: Mapping[str, Mapping[str, Any]]) -> List[Listener]:
    """Flatten ``{service: config}`` into the listeners its blocks would render.

    Mirrors the gates of the templates, and only those:
    ``SERVER_TYPE`` picks the subsystem (``http.conf:107``, ``stream.conf:52``),
    ``LISTEN_HTTP`` gates the HTTP listeners (``server.conf:27``), the HTTPS ones
    are gated by having a port at all (``ssl-certificate-lua.conf:38``), and
    ``LISTEN_STREAM`` gates both stream families (``server-stream.conf:27``).
    """
    listeners: List[Listener] = []
    for service, config in services.items():
        server_type = str(config.get("SERVER_TYPE", "http")).strip()
        if server_type == "stream":
            if str(config.get("LISTEN_STREAM", "yes")).strip() != "yes":
                continue
            protocols = _protocols(config)
            for setting, ssl in ((STREAM_PORT_SETTING, False), (STREAM_SSL_PORT_SETTING, True)):
                # The SSL stream listener is TCP only (ssl-certificate-stream-lua.conf:40).
                for proto in (("tcp",) if ssl else protocols):
                    for raw in collect_ports(config, setting):
                        port = parse_port(raw)
                        if port is not None:
                            listeners.append(Listener(service, "stream", port, proto, ssl, setting))
            continue
        if str(config.get("LISTEN_HTTP", "yes")).strip() == "yes":
            for raw in collect_ports(config, HTTP_PORT_SETTING):
                port = parse_port(raw)
                if port is not None:
                    listeners.append(Listener(service, "http", port, "tcp", False, HTTP_PORT_SETTING))
        for raw in collect_ports(config, HTTPS_PORT_SETTING):
            port = parse_port(raw)
            if port is not None:
                listeners.append(Listener(service, "http", port, "tcp", True, HTTPS_PORT_SETTING))
    return listeners


def reserved_ports(global_config: Mapping[str, Any], *, all_in_one: bool = False) -> Dict[int, str]:
    """``{port: what holds it}`` for the ports the product binds for itself.

    Taking the API ports from the configuration rather than hardcoding 5000/5443
    matters: they are settings (``settings.json:220-237``), so an operator who
    moved the API frees the default and reserves the new one.
    """
    reserved: Dict[int, str] = {HEALTHCHECK_PORT: "the healthcheck server"}
    for setting, what in (("API_HTTP_PORT", "the internal API (HTTP)"), ("API_HTTPS_PORT", "the internal API (HTTPS)")):
        port = parse_port(global_config.get(setting, ""))
        if port is not None:
            reserved[port] = what
    if all_in_one:
        reserved.setdefault(ALL_IN_ONE_UI_PORT, "the all-in-one web UI")
        reserved.setdefault(ALL_IN_ONE_API_PORT, "the all-in-one API service")
    return reserved


def check_ports(
    services: Mapping[str, Mapping[str, Any]],
    *,
    reserved: Optional[Mapping[int, str]] = None,
    containerized: bool = False,
) -> List[PortIssue]:
    """Every port problem the configuration carries, worst first.

    ``containerized`` turns on the ``< 1024`` warning: the images run as the
    ``nginx`` user and cannot bind a privileged port, while a Linux install can
    (``src/linux/scripts/start.sh:132-133``), so the same value is fine there.
    """
    issues: List[PortIssue] = []
    listeners = inventory(services)
    reserved = reserved or {}

    # Grouped by SOCKET, not by port number: NGINX keys its listening list on (port, type,
    # family) (ngx_stream.c:414-416), so TCP 8080 and UDP 8080 are two unrelated sockets and
    # neither collides with nor unions options into the other.
    by_socket: Dict[Tuple[int, str], Dict[str, List[Listener]]] = {}
    for listener in listeners:
        by_socket.setdefault((listener.port, listener.proto), {}).setdefault(listener.subsystem, []).append(listener)

    # One socket claimed by both subsystems: http{} and stream{} each open their own, so the
    # second bind() fails with EADDRINUSE and NGINX does not start.
    for (port, proto), subsystems in sorted(by_socket.items()):
        if len(subsystems) > 1:
            http_services = sorted({listener.service for listener in subsystems["http"]})
            stream_services = sorted({listener.service for listener in subsystems["stream"]})
            issues.append(
                PortIssue(
                    FATAL,
                    f"port {port}/{proto} is used by HTTP service(s) {', '.join(http_services)} and by stream service(s) "
                    f"{', '.join(stream_services)} - the http and stream subsystems cannot share a port",
                )
            )

    # A product port taken by a service.
    for listener in listeners:
        what = reserved.get(listener.port)
        if what:
            issues.append(PortIssue(FATAL, f"service {listener.service} listens on port {listener.port} ({listener.setting}), which is reserved for {what}"))

    # Options NGINX unions silently over the blocks of one socket.
    for (port, proto), subsystems in sorted(by_socket.items()):
        for subsystem, same_socket in sorted(subsystems.items()):
            if len({listener.ssl for listener in same_socket}) > 1:
                plain = sorted({listener.service for listener in same_socket if not listener.ssl})
                issues.append(
                    PortIssue(
                        WARNING,
                        f"port {port} is declared both with and without TLS ({subsystem}/{proto}) - NGINX unions listen options, "
                        f"so {', '.join(plain)} would be served as TLS too",
                    )
                )
            if subsystem == "http":
                http2 = {str(services[listener.service].get("HTTP2", "yes")).strip() for listener in same_socket}
                if len(http2) > 1:
                    issues.append(
                        PortIssue(
                            WARNING,
                            f"port {port} is shared by services with different HTTP2 settings - NGINX unions listen options, "
                            "so the setting of one service applies to all of them",
                        )
                    )

    # Privileged ports the container user cannot bind.
    if containerized:
        for port in sorted({listener.port for listener in listeners if listener.port < PRIVILEGED_PORT_CEILING}):
            holders = sorted({listener.service for listener in listeners if listener.port == port})
            issues.append(
                PortIssue(
                    WARNING,
                    f"port {port} is below {PRIVILEGED_PORT_CEILING} and requested by {', '.join(holders)} - containers run as the "
                    "nginx user and cannot bind a privileged port, publish it from the host instead (e.g. -p 80:8080)",
                )
            )

    return sorted(issues, key=lambda issue: 0 if issue.level == FATAL else 1)


def services_from_config(config: Mapping[str, Any], server_names: Optional[Sequence[str]] = None) -> Dict[str, Dict[str, Any]]:
    """Slice a full (prefixed) config into ``{service: effective config}``.

    Global values stay as the per-service default, exactly like
    ``Templator._get_server_config`` builds a server's view: copy the global
    keys, then overwrite with the service's own. Non-multisite yields the single
    service under its ``SERVER_NAME``.

    Names are matched longest-first so a service whose id is a prefix of another
    cannot claim its sibling's keys.
    """
    if server_names is None:
        server_names = str(config.get("SERVER_NAME", "")).strip().split()
    if str(config.get("MULTISITE", "no")).strip() != "yes":
        return {name: dict(config) for name in server_names[:1]}

    prefixes = sorted(server_names, key=len, reverse=True)
    globals_only: Dict[str, Any] = {}
    per_service: Dict[str, Dict[str, Any]] = {name: {} for name in server_names}
    for key, value in config.items():
        for name in prefixes:
            if key.startswith(f"{name}_"):
                per_service[name][key[len(name) + 1 :]] = value  # noqa: E203
                break
        else:
            globals_only[key] = value

    services: Dict[str, Dict[str, Any]] = {}
    for name in server_names:
        merged = dict(globals_only)
        merged.update(per_service[name])
        services[name] = merged
    return services
