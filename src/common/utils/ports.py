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
    "ACME_HTTP01_PORT",
    "PORT_LIST_SETTINGS",
    "check_ports",
    "collect_ports",
    "drop_inherited_ports",
    "inherited_port_keys",
    "http01_refusals",
    "inventory",
    "list_moved",
    "parse_port",
    "port_list_keys",
    "port_list_setting",
    "reserved_ports",
    "stream_reuseport_owners",
    "union_ports",
)

HTTP_PORT_SETTING = "HTTP_PORT"
HTTPS_PORT_SETTING = "HTTPS_PORT"
STREAM_PORT_SETTING = "LISTEN_STREAM_PORT"
STREAM_SSL_PORT_SETTING = "LISTEN_STREAM_PORT_SSL"

# The lists a service REPLACES rather than extends when it declares one of its own
# (conception §2.2). Stream ports are deliberately absent: they have been multisite and
# unioned since 1.6.0 and changing that would silently drop ports from working deployments.
PORT_LIST_SETTINGS = (HTTP_PORT_SETTING, HTTPS_PORT_SETTING)

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

# The only port an ACME server ever contacts for an http-01 challenge, and it follows no
# redirect to reach it (documented at src/common/core/ssl/ssl.lua:18-24).
ACME_HTTP01_PORT = 80


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
    """Raw values of ``SETTING`` and its ``SETTING_<N>`` repetitions, in SUFFIX order.

    Empty values are dropped — that is the ``and port`` guard the per-service
    templates already carry (``server-http/server.conf:24``), expressed once.

    The suffix must be all digits, which is how ``LISTEN_STREAM_PORT_SSL`` stops
    being read as a repetition of ``LISTEN_STREAM_PORT``. The templates achieve
    the same with a second ``startswith`` (``server-stream.conf:24``).

    **Ordered by suffix, not by dict order**, exactly like Lua's ``port_list``
    (``utils.lua``) — because :func:`list_moved` compares ORDERED sequences, and dict order is not a property of the configuration. Two
    ways it diverges from the list an operator wrote: a database read whose
    ``order_by`` had no suffix tiebreak (engine-dependent), and a merged view like
    ``services_from_config``, where a service key absent from the globals is
    APPENDED after the repetition that was there — so a service restating
    ``8080 8081`` over a fleet with a row for ``HTTP_PORT_1`` alone read back as
    ``['8081', '8080']`` and counted as moved. Sorting here is the one place that
    closes both, and it is a no-op wherever the keys were already in order, which
    is what keeps the default server's union byte-identical.
    """
    prefix = f"{setting}_"
    indexed = []
    for key, value in config.items():
        if key == setting:
            suffix = 0
        elif key.startswith(prefix) and key[len(prefix) :].isdigit():  # noqa: E203
            suffix = int(key[len(prefix) :])  # noqa: E203
        else:
            continue
        port = str(value).strip()
        if port:
            indexed.append((suffix, port))
    return [port for _, port in sorted(indexed, key=lambda entry: entry[0])]


def port_list_setting(key: str) -> Optional[str]:
    """The port list ``key`` is a member of (``HTTP_PORT_1`` -> ``HTTP_PORT``), or ``None``.

    The suffix must be all digits for the same reason as in :func:`collect_ports`:
    ``LISTEN_STREAM_PORT_SSL`` is not a repetition of ``LISTEN_STREAM_PORT``.
    """
    for setting in PORT_LIST_SETTINGS:
        if key == setting:
            return setting
        prefix = f"{setting}_"
        if key.startswith(prefix) and key[len(prefix) :].isdigit():  # noqa: E203
            return setting
    return None


def port_list_keys(config: Mapping[str, Any], setting: str) -> List[str]:
    """The ``SETTING`` / ``SETTING_<N>`` keys present in ``config``, in insertion order."""
    return [key for key in config if port_list_setting(key) == setting]


def inherited_port_keys(merged: Mapping[str, Any], declared: Mapping[str, Any]) -> List[str]:
    """The port-list keys of ``merged`` this service did NOT declare, i.e. the ones the
    list-REPLACEMENT rule (§2.2) takes away from it.

    A service that declares any member of a port list replaces the inherited list instead of
    adding to it: ``multiple`` settings merge as a union, and a service told to listen on 9000
    that also keeps the global ``HTTP_PORT_1=8081`` is listening somewhere nobody asked for.

    ``merged`` is global-then-service (``Templator._get_server_config``) and ``declared`` is the
    service's OWN keys, so "inherited" is exactly "in merged, not in declared". A service that
    declares nothing loses nothing, which is what keeps the render byte-identical.

    Two callers need the same answer for different reasons -- the render drops these keys from the
    server's view, and ``Templator._write_config`` keeps them out of ``variables.env`` so the Lua
    side reads the list the block really binds -- so the rule lives here once.
    """
    keys = []
    for setting in PORT_LIST_SETTINGS:
        if not any(port_list_setting(key) == setting for key in declared):
            continue
        keys.extend(key for key in port_list_keys(merged, setting) if key not in declared)
    return keys


def drop_inherited_ports(merged: Dict[str, Any], declared: Mapping[str, Any]) -> None:
    """Apply the list-REPLACEMENT rule to one service's merged configuration, in place."""
    for key in inherited_port_keys(merged, declared):
        del merged[key]


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
        if not _renders_http_listener(config, setting):
            continue
        for port in collect_ports(config, setting):
            if port not in seen:
                seen.add(port)
                ports.append(port)
    return ports


def _renders_http_listener(config: Mapping[str, Any], setting: str) -> bool:
    """Whether an http{} server block will actually bind ``setting`` for this service.

    The same gates :func:`inventory` reads, and they have to agree: a stream service inherits
    ``HTTP_PORT`` like any other but renders no http block, so counting its port in the default
    server's union makes http{} bind a port ``server-stream.conf`` also binds -- plain
    ``EADDRINUSE``, and NGINX refuses to start. :func:`check_ports` cannot catch it because it
    reports on the same inventory the union would be contradicting.
    """
    if str(config.get("SERVER_TYPE", "http")).strip() == "stream":
        return False
    if setting == HTTP_PORT_SETTING:
        return str(config.get("LISTEN_HTTP", "yes")).strip() == "yes"
    return True


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


# ---------------------------------------------------------------------------------------------
# "Has this service been moved off the fleet's listener?"
#
# One question, four answers downstream: the HTTP->HTTPS redirect, the CORS `self` origin, the web
# UI's service link, and whether an http-01 challenge can still be validated. It is the whole of
# the PO ruling, and it is what keeps every existing deployment untouched.
#
# Why the comparison is against the GLOBAL list rather than against the scheme's default port:
# the rendered port is NOT the published port, and the product's own default compose relies on
# that -- misc/integrations/docker.yml:16-18 publishes 80:8080 and 443:8443. "Use the service's
# own port" applied blindly would emit https://example.com:8443/ for a service that overrode
# nothing, breaking a redirect that works today. Equal lists mean the published-port contract
# still holds and nothing may change; a different list means the operator moved this service
# deliberately, and with no NAT modelling in scope the rendered port IS the reachable one.
# ---------------------------------------------------------------------------------------------


def list_moved(service_config: Mapping[str, Any], global_config: Mapping[str, Any], setting: str) -> bool:
    """Whether ``service_config``'s port list for ``setting`` differs from the global one.

    Compared as ORDERED sequences: ``8080 8081`` and ``8081 8080`` are different listeners in a
    different order, and nothing here is entitled to decide that the operator meant the same thing.
    """
    return collect_ports(service_config, setting) != collect_ports(global_config, setting)


def http01_refusals(services: Mapping[str, Mapping[str, Any]], global_config: Mapping[str, Any]) -> Dict[str, str]:
    """``{service: why}`` for each service whose ``http-01`` challenge can no longer be validated.

    An ACME server only ever contacts **public port 80** and follows no redirect to get there. A
    service that kept the fleet's HTTP listener is reachable there exactly as before -- whatever
    the rendered port is, because the host publishes it. A service that declared a list of its own
    is not, and the failure is otherwise a job error sixty seconds after a save that answered 200.

    The message names the two ways out, because this is a hard refusal at save time and an
    operator staring at a 400 needs to know what to do rather than what went wrong.
    """
    refusals: Dict[str, str] = {}
    for service, config in services.items():
        if str(config.get("AUTO_LETS_ENCRYPT", "no")).strip() != "yes":
            continue
        if str(config.get("LETS_ENCRYPT_CHALLENGE", "http")).strip() != "http":
            continue
        # Passthrough means BunkerWeb is not the one answering the challenge.
        if str(config.get("LETS_ENCRYPT_PASSTHROUGH", "no")).strip() == "yes":
            continue
        if not list_moved(config, global_config, HTTP_PORT_SETTING):
            continue
        own = ", ".join(collect_ports(config, HTTP_PORT_SETTING)) or "none"
        # A configuration snapshot only carries the settings that are NOT at their default (that is
        # what the write paths hand over), so "no global list" here means "left at the default", not
        # "no global port". Naming a port that is not in the snapshot would be inventing one, and
        # printing "(none)" would be a plain lie -- so the clause is dropped instead.
        fleet = ", ".join(collect_ports(global_config, HTTP_PORT_SETTING))
        refusals[service] = (
            f"LETS_ENCRYPT_CHALLENGE=http cannot work for {service}: it listens on its own HTTP port(s) ({own}) instead of the "
            f"global one{'s' if ',' in fleet else ''}{f' ({fleet})' if fleet else ''}, and Let's Encrypt only ever contacts public "
            f"port {ACME_HTTP01_PORT} and follows no redirect. Either set LETS_ENCRYPT_CHALLENGE=dns and configure a DNS provider, "
            "or remove this service's HTTP_PORT override so it keeps listening on the global port that port 80 is published to."
        )
    return refusals


def services_from_config(
    config: Mapping[str, Any],
    server_names: Optional[Sequence[str]] = None,
    *,
    multisite: Optional[bool] = None,
) -> Dict[str, Dict[str, Any]]:
    """Slice a full (prefixed) config into ``{service: effective config}``.

    Global values stay as the per-service default, exactly like
    ``Templator._get_server_config`` builds a server's view: copy the global
    keys, then overwrite with the service's own. Non-multisite yields the single
    service under its ``SERVER_NAME``.

    ``multisite`` overrides what the configuration says about itself. The write
    paths need it: a snapshot they are about to persist already carries prefixed
    per-service keys, and reading ``MULTISITE`` out of it would make the answer
    depend on a setting the very same request may be changing.

    Names are matched longest-first so a service whose id is a prefix of another
    cannot claim its sibling's keys.
    """
    if server_names is None:
        server_names = str(config.get("SERVER_NAME", "")).strip().split()
    if multisite is None:
        multisite = str(config.get("MULTISITE", "no")).strip() == "yes"
    if not multisite:
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
        # Same rule the renderer applies (Templator._get_server_config): a service that declares a
        # port list replaces the inherited one. Reporting and the write-path refusals have to see
        # the ports the service will really listen on, not the union nobody renders.
        drop_inherited_ports(merged, per_service[name])
        services[name] = merged
    return services
