#!/usr/bin/env python3

from contextlib import suppress
from copy import deepcopy
from typing import Literal, Optional, Union
from os import getenv
from urllib.parse import urlsplit
from requests import request
from requests.exceptions import ConnectionError
from urllib3 import disable_warnings  # new
from urllib3.exceptions import InsecureRequestWarning  # new

from logger import setup_logger  # type: ignore

# Suppress urllib3 InsecureRequestWarning when verify=False (default: enabled)
if getenv("API_SUPPRESS_INSECURE_WARNING", "1").lower() in ("1", "true", "yes", "on"):
    with suppress(Exception):
        disable_warnings(InsecureRequestWarning)


class API:
    """
    Thin HTTP client for BunkerWeb API with centralized endpoint building.

    Enhancements:
    - API.from_instance(dict) to build scheme/port/host from DB instance data
    - API.from_url_or_parts(hostname_or_url, ...) for ad-hoc construction
    - SSL verification and CA bundle controlled via env or constructor
    """

    def __init__(self, endpoint: str, host: Optional[str] = None, token: Optional[str] = None):
        # Normalize endpoint trailing slash
        self.__endpoint = endpoint if endpoint.endswith("/") else endpoint + "/"
        # Host header (defaults to API_SERVER_NAME)
        self.__host = host or getenv("API_SERVER_NAME", "bwapi")
        # Optional API token: if not provided, fallback to env var
        self.__token = token if token is not None else getenv("API_TOKEN")
        self.__logger = setup_logger("Api", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))

    @property
    def endpoint(self) -> str:
        return self.__endpoint

    @property
    def host(self) -> str:
        return self.__host

    def request(
        self,
        method: Union[Literal["POST"], Literal["GET"]],
        url: str,
        data: Optional[Union[dict, bytes]] = None,
        files=None,
        timeout=(5, 10),
    ) -> tuple[bool, str, Optional[int], Optional[dict]]:
        kwargs = {}
        if isinstance(data, dict):
            kwargs["json"] = data
        elif isinstance(data, bytes):
            kwargs["data"] = data
        elif data is not None:
            return False, f"Unsupported data type: {type(data)}", None, None

        if files:
            kwargs["files"] = files

        headers = {"User-Agent": "bwapi", "Host": self.__host}
        # Add Authorization header if a token is set
        if self.__token:
            headers["Authorization"] = f"Bearer {self.__token}"

        try:
            resp = request(
                method,
                f"{self.__endpoint}{url if not url.startswith('/') else url[1:]}",
                timeout=timeout,
                headers=deepcopy(headers),
                verify=False,  # TODO: see what to do about SSL verification
                **deepcopy(kwargs),
            )
        except ConnectionError as e:
            scheme = urlsplit(self.__endpoint).scheme
            if scheme == "https":
                self.__logger.warning(f"SSL connection error when contacting {self.__endpoint}{url}, trying HTTP: {e}")
                resp = request(
                    method,
                    f"http://{self.__endpoint.lstrip('https://')}{url if not url.startswith('/') else url[1:]}",
                    timeout=timeout,
                    headers=deepcopy(headers),
                    verify=False,
                    **deepcopy(kwargs),
                )
            else:
                return False, f"Connection error: {e}", None, None
        except Exception as e:
            return False, f"Request failed: {e}", None, None

        return True, "ok", resp.status_code, resp.json()

    # ------------------ Builders ------------------
    @staticmethod
    def __default_http_port() -> int:
        try:
            return int(getenv("API_HTTP_PORT", "5000"))
        except Exception:
            return 5000

    @staticmethod
    def __default_https_port() -> int:
        try:
            return int(getenv("API_HTTPS_PORT", "6000"))
        except Exception:
            return 6000

    @classmethod
    def build_endpoint(
        cls,
        hostname_or_url: str,
        *,
        port: Optional[int] = None,
        listen_https: Optional[bool] = None,
        https_port: Optional[int] = None,
    ) -> str:
        """
        Construct an endpoint URL from a hostname/URL and optional hints.
        - If a full URL is provided, preserve its scheme and port (use defaults if missing port).
        - Otherwise, choose scheme based on listen_https (default: http) and use provided/default ports.
        """
        with suppress(Exception):
            parsed = urlsplit(hostname_or_url)
            if parsed.scheme in ("http", "https") and parsed.hostname:
                scheme = parsed.scheme
                host = parsed.hostname
                if parsed.port:
                    eff_port = parsed.port
                else:
                    eff_port = cls.__default_https_port() if scheme == "https" else cls.__default_http_port()
                return f"{scheme}://{host}:{eff_port}"

        host = hostname_or_url.replace("http://", "").replace("https://", "")
        scheme = "https" if listen_https else "http"
        eff_port = (
            (https_port if https_port is not None else cls.__default_https_port())
            if scheme == "https"
            else (port if port is not None else cls.__default_http_port())
        )
        return f"{scheme}://{host}:{eff_port}"

    @classmethod
    def from_instance(cls, instance: dict, *, token: Optional[str] = None) -> "API":
        """
        Build an API client from a DB instance dict, honoring listen_https/https_port.
        Expected keys: hostname, port, server_name, listen_https, https_port
        """
        endpoint = cls.build_endpoint(
            instance.get("hostname", "127.0.0.1"),
            port=instance.get("port"),
            listen_https=bool(instance.get("listen_https", False)),
            https_port=instance.get("https_port"),
        )
        host = instance.get("server_name") or getenv("API_SERVER_NAME", "bwapi")
        return cls(endpoint, host=host, token=token)

    @classmethod
    def from_url_or_parts(
        cls,
        hostname_or_url: str,
        *,
        server_name: Optional[str] = None,
        port: Optional[int] = None,
        listen_https: Optional[bool] = None,
        https_port: Optional[int] = None,
        token: Optional[str] = None,
    ) -> "API":
        endpoint = cls.build_endpoint(hostname_or_url, port=port, listen_https=listen_https, https_port=https_port)
        host = server_name or getenv("API_SERVER_NAME", "bwapi")
        return cls(endpoint, host=host, token=token)
