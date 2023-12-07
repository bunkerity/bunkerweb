# -*- coding: utf-8 -*-
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from logging import Formatter, getLogger
from os.path import join, sep
from sys import path as sys_path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

deps_path = join(sep, "usr", "share", "bunkerweb", "deps", "python")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from uvicorn._types import ASGI3Application, ASGIReceiveCallable, ASGISendCallable, HTTPScope, Scope, WebSocketScope
from uvicorn.config import Config
from uvicorn.workers import UvicornWorker

logger = getLogger("uvicorn.error")


class BwUvicornWorker(UvicornWorker):
    CONFIG_KWARGS: Dict[str, Any] = {
        "loop": "auto",
        "http": "auto",
        "proxy_headers": True,
        "server_header": False,
        "date_header": False,
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super(UvicornWorker, self).__init__(*args, **kwargs)

        formatter = Formatter(fmt="%(asctime)s [%(name)s] [%(process)d] [%(levelname)s] - %(message)s", datefmt="[%Y-%m-%d %H:%M:%S %z]")

        logger = getLogger("uvicorn.error")
        logger.handlers = self.log.error_log.handlers
        for handler in logger.handlers:
            handler.setFormatter(formatter)
        logger.setLevel(self.log.error_log.level)
        logger.propagate = False

        logger = getLogger("uvicorn.access")
        logger.handlers = self.log.access_log.handlers
        for handler in logger.handlers:
            handler.setFormatter(formatter)
        logger.setLevel(self.log.access_log.level)
        logger.propagate = False

        config_kwargs: dict = {
            "app": None,
            "log_config": None,
            "timeout_keep_alive": self.cfg.keepalive,
            "timeout_notify": self.timeout,
            "callback_notify": self.callback_notify,
            "limit_max_requests": self.max_requests,
            "forwarded_allow_ips": self.cfg.forwarded_allow_ips,
        }

        if self.cfg.is_ssl:
            ssl_kwargs = {
                "ssl_keyfile": self.cfg.ssl_options.get("keyfile"),
                "ssl_certfile": self.cfg.ssl_options.get("certfile"),
                "ssl_keyfile_password": self.cfg.ssl_options.get("password"),
                "ssl_version": self.cfg.ssl_options.get("ssl_version"),
                "ssl_cert_reqs": self.cfg.ssl_options.get("cert_reqs"),
                "ssl_ca_certs": self.cfg.ssl_options.get("ca_certs"),
                "ssl_ciphers": self.cfg.ssl_options.get("ciphers"),
            }
            config_kwargs.update(ssl_kwargs)

        if self.cfg.settings["backlog"].value:
            config_kwargs["backlog"] = self.cfg.settings["backlog"].value

        config_kwargs.update(self.CONFIG_KWARGS)

        self.config = CustomConfig(**config_kwargs)


class ProxyHeadersMiddleware:
    def __init__(self, app: "ASGI3Application", trusted_hosts: Union[List[str], str] = "127.0.0.1") -> None:
        self.app = app
        if isinstance(trusted_hosts, str):
            tmp_trusted_hosts = {item.strip() for item in trusted_hosts.split(",")}
        else:
            tmp_trusted_hosts = set(trusted_hosts)
        self.always_trust = "*" in tmp_trusted_hosts
        self.trusted_networks: Set[Union[IPv4Network, IPv6Network]] = {ip_network(host) for host in tmp_trusted_hosts if host != "*"}

    def get_trusted_client_host(self, x_forwarded_for_hosts: List[str]) -> Optional[str]:
        if self.always_trust:
            return x_forwarded_for_hosts[0]

        for host in reversed(x_forwarded_for_hosts):
            address_host = ip_address(host)
            for network in self.trusted_networks:
                if address_host not in network:
                    return host

        return None

    async def __call__(self, scope: "Scope", receive: "ASGIReceiveCallable", send: "ASGISendCallable") -> None:
        if scope["type"] in ("http", "websocket"):
            scope = cast(Union["HTTPScope", "WebSocketScope"], scope)
            client_addr: Optional[Tuple[str, int]] = scope.get("client")
            client_host = ip_address(client_addr[0]) if client_addr else None

            if self.always_trust or any(client_host in network for network in self.trusted_networks):
                headers = dict(scope["headers"])

                if b"x-forwarded-proto" in headers:
                    # Determine if the incoming request was http or https based on
                    # the X-Forwarded-Proto header.
                    x_forwarded_proto = headers[b"x-forwarded-proto"].decode("latin1").strip()
                    if scope["type"] == "websocket":
                        scope["scheme"] = "wss" if x_forwarded_proto == "https" else "ws"
                    else:
                        scope["scheme"] = x_forwarded_proto

                if b"x-forwarded-for" in headers:
                    # Determine the client address from the last trusted IP in the
                    # X-Forwarded-For header. We've lost the connecting client's port
                    # information by now, so only include the host.
                    x_forwarded_for = headers[b"x-forwarded-for"].decode("latin1")
                    x_forwarded_for_hosts = [item.strip() for item in x_forwarded_for.split(",")]
                    host = self.get_trusted_client_host(x_forwarded_for_hosts)
                    port = 0
                    scope["client"] = (host, port)  # type: ignore

        return await self.app(scope, receive, send)


class CustomConfig(Config):
    def load(self) -> None:
        super().load()

        if self.proxy_headers:
            self.loaded_app = ProxyHeadersMiddleware(self.loaded_app, trusted_hosts=self.forwarded_allow_ips)
