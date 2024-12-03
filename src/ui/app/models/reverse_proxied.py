#!/usr/bin/env python3

from logging import getLogger
from werkzeug.middleware.proxy_fix import ProxyFix


class ReverseProxied(ProxyFix):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__logger = getLogger("UI.ReverseProxied")

    def __call__(self, environ, start_response):
        """Modify the WSGI environ based on the various ``Forwarded``
        headers before calling the wrapped application. Store the
        original environ values in ``werkzeug.proxy_fix.orig_{key}``.
        """
        environ_get = environ.get
        orig_remote_addr = environ_get("REMOTE_ADDR")
        orig_wsgi_url_scheme = environ_get("wsgi.url_scheme")
        orig_http_host = environ_get("HTTP_HOST")
        environ.update(
            {
                "werkzeug.proxy_fix.orig": {
                    "REMOTE_ADDR": orig_remote_addr,
                    "wsgi.url_scheme": orig_wsgi_url_scheme,
                    "HTTP_HOST": orig_http_host,
                    "SERVER_NAME": environ_get("SERVER_NAME"),
                    "SERVER_PORT": environ_get("SERVER_PORT"),
                    "SCRIPT_NAME": environ_get("SCRIPT_NAME"),
                }
            }
        )

        x_for = self._get_real_value(self.x_for, environ_get("HTTP_X_FORWARDED_FOR"))
        if x_for:
            environ["REMOTE_ADDR"] = x_for

        x_proto = self._get_real_value(self.x_proto, environ_get("HTTP_X_FORWARDED_PROTO"))
        if x_proto:
            environ["wsgi.url_scheme"] = x_proto

        x_host = self._get_real_value(self.x_host, environ_get("HTTP_X_FORWARDED_HOST"))
        if x_host:
            environ["HTTP_HOST"] = environ["SERVER_NAME"] = x_host
            # "]" to check for IPv6 address without port
            if ":" in x_host and not x_host.endswith("]"):
                environ["SERVER_NAME"], environ["SERVER_PORT"] = x_host.rsplit(":", 1)

        x_port = self._get_real_value(self.x_port, environ_get("HTTP_X_FORWARDED_PORT"))
        if x_port:
            host = environ.get("HTTP_HOST")
            if host:
                # "]" to check for IPv6 address without port
                if ":" in host and not host.endswith("]"):
                    host = host.rsplit(":", 1)[0]
                environ["HTTP_HOST"] = f"{host}:{x_port}"
            environ["SERVER_PORT"] = x_port

        x_prefix = self._get_real_value(self.x_prefix, environ_get("HTTP_X_FORWARDED_PREFIX"))
        if x_prefix:
            environ["SCRIPT_NAME"] = x_prefix

        environ["PATH_INFO"] = environ["PATH_INFO"][len(environ["SCRIPT_NAME"]) :]  # noqa: E203
        environ["ABSOLUTE_URI"] = f"{environ['wsgi.url_scheme']}://{environ['HTTP_HOST']}{environ['SCRIPT_NAME']}/"
        environ["SESSION_COOKIE_DOMAIN"] = environ["HTTP_HOST"]

        self.__logger.debug(f"Reverse Proxy environ: {environ}")

        return self.app(environ, start_response)
