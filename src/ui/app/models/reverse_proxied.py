#!/usr/bin/env python3

from werkzeug.middleware.proxy_fix import ProxyFix
from os import getenv, sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for reverse_proxied module")


class ReverseProxied(ProxyFix):
    # Modify the WSGI environ based on the various Forwarded headers before calling the wrapped application.
    # Store the original environ values in werkzeug.proxy_fix.orig_{key} and handle reverse proxy headers safely.
    def __call__(self, environ, start_response):
        if DEBUG_MODE:
            logger.debug("ReverseProxied.__call__() called - processing WSGI environ for reverse proxy")
        
        environ_get = environ.get
        orig_remote_addr = environ_get("REMOTE_ADDR")
        orig_wsgi_url_scheme = environ_get("wsgi.url_scheme")
        orig_http_host = environ_get("HTTP_HOST")
        
        if DEBUG_MODE:
            logger.debug(f"Original environ values - REMOTE_ADDR: {orig_remote_addr}, "
                        f"wsgi.url_scheme: {orig_wsgi_url_scheme}, HTTP_HOST: {orig_http_host}")
        
        # Store original environ values for reference
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
        
        if DEBUG_MODE:
            logger.debug("Stored original environ values in werkzeug.proxy_fix.orig")

        # Process X-Forwarded-For header for real client IP
        x_for = self._get_real_value(self.x_for, environ_get("HTTP_X_FORWARDED_FOR"))
        if x_for:
            environ["REMOTE_ADDR"] = x_for
            if DEBUG_MODE:
                logger.debug(f"Updated REMOTE_ADDR from X-Forwarded-For: {x_for}")

        # Process X-Forwarded-Proto header for original protocol
        x_proto = self._get_real_value(self.x_proto, environ_get("HTTP_X_FORWARDED_PROTO"))
        if x_proto:
            environ["wsgi.url_scheme"] = x_proto
            if DEBUG_MODE:
                logger.debug(f"Updated wsgi.url_scheme from X-Forwarded-Proto: {x_proto}")

        # Process X-Forwarded-Host header for original host
        x_host = self._get_real_value(self.x_host, environ_get("HTTP_X_FORWARDED_HOST"))
        if x_host:
            environ["HTTP_HOST"] = environ["SERVER_NAME"] = x_host
            if DEBUG_MODE:
                logger.debug(f"Updated HTTP_HOST and SERVER_NAME from X-Forwarded-Host: {x_host}")
            
            # Handle IPv6 and port separation
            if ":" in x_host and not x_host.endswith("]"):
                server_name, server_port = x_host.rsplit(":", 1)
                environ["SERVER_NAME"] = server_name
                environ["SERVER_PORT"] = server_port
                if DEBUG_MODE:
                    logger.debug(f"Separated host and port - SERVER_NAME: {server_name}, SERVER_PORT: {server_port}")

        # Process X-Forwarded-Port header for original port
        x_port = self._get_real_value(self.x_port, environ_get("HTTP_X_FORWARDED_PORT"))
        if x_port:
            host = environ.get("HTTP_HOST")
            if host:
                # Handle IPv6 address without port
                if ":" in host and not host.endswith("]"):
                    host = host.rsplit(":", 1)[0]
                environ["HTTP_HOST"] = f"{host}:{x_port}"
                if DEBUG_MODE:
                    logger.debug(f"Updated HTTP_HOST with port: {environ['HTTP_HOST']}")
            
            environ["SERVER_PORT"] = x_port
            if DEBUG_MODE:
                logger.debug(f"Updated SERVER_PORT from X-Forwarded-Port: {x_port}")

        # Process X-Forwarded-Prefix header for path prefix
        x_prefix = self._get_real_value(self.x_prefix, environ_get("HTTP_X_FORWARDED_PREFIX"))
        if x_prefix:
            environ["SCRIPT_NAME"] = x_prefix
            if DEBUG_MODE:
                logger.debug(f"Updated SCRIPT_NAME from X-Forwarded-Prefix: {x_prefix}")

        # Update PATH_INFO by removing script name prefix
        script_name_len = len(environ["SCRIPT_NAME"])
        environ["PATH_INFO"] = environ["PATH_INFO"][script_name_len:]
        
        # Construct absolute URI and session cookie domain
        environ["ABSOLUTE_URI"] = f"{environ['wsgi.url_scheme']}://{environ['HTTP_HOST']}{environ['SCRIPT_NAME']}/"
        environ["SESSION_COOKIE_DOMAIN"] = environ["HTTP_HOST"]
        
        if DEBUG_MODE:
            logger.debug(f"Final environ values - PATH_INFO: {environ['PATH_INFO']}, "
                        f"ABSOLUTE_URI: {environ['ABSOLUTE_URI']}, "
                        f"SESSION_COOKIE_DOMAIN: {environ['SESSION_COOKIE_DOMAIN']}")
            logger.debug("ReverseProxied processing completed, calling wrapped application")

        try:
            return self.app(environ, start_response)
        except Exception as e:
            logger.exception("Exception occurred in wrapped application during reverse proxy processing")
            raise
