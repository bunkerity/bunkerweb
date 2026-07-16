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

from common_utils import has_url_userinfo, is_valid_host  # type: ignore
from logger import getLogger  # type: ignore

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
        parsed_endpoint = urlsplit(endpoint if "://" in endpoint else f"//{endpoint}")
        if has_url_userinfo(endpoint) or parsed_endpoint.scheme not in ("http", "https") or not is_valid_host(parsed_endpoint.hostname):
            raise ValueError("Invalid API endpoint: expected an HTTP(S) URL without user information")
        # Normalize endpoint trailing slash
        self.__endpoint = endpoint if endpoint.endswith("/") else endpoint + "/"
        # Host header (defaults to API_SERVER_NAME)
        self.__host = host or getenv("API_SERVER_NAME", "bwapi")
        # Optional API token: if not provided, fallback to env var
        self.__token = token if token is not None else getenv("API_TOKEN")
        self.__logger = getLogger("API")

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
                self.__logger.debug(f"Response after retrying with HTTP: status={resp.status_code}, reason={resp.reason}, text={resp.text}")
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
            return int(getenv("API_HTTPS_PORT", "5443"))
        except Exception:
            return 5443

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
        if not isinstance(hostname_or_url, str) or not hostname_or_url or has_url_userinfo(hostname_or_url):
            raise ValueError("Invalid API hostname: URL user information is not allowed")

        has_scheme = "://" in hostname_or_url
        if not has_scheme and is_valid_host(hostname_or_url):
            hostname = hostname_or_url
            scheme = "https" if listen_https else "http"
            eff_port = None
        else:
            parsed = urlsplit(hostname_or_url if has_scheme else f"//{hostname_or_url}")
            if has_scheme and parsed.scheme not in ("http", "https"):
                raise ValueError("Invalid API hostname: only HTTP(S) URLs are supported")
            if not is_valid_host(parsed.hostname):
                raise ValueError(f"Invalid API hostname: {parsed.hostname or hostname_or_url}")
            hostname = parsed.hostname
            scheme = parsed.scheme if has_scheme else ("https" if listen_https else "http")
            eff_port = parsed.port

        if eff_port is None:
            eff_port = (
                (https_port if https_port is not None else cls.__default_https_port())
                if scheme == "https"
                else (port if port is not None else cls.__default_http_port())
            )
        host = f"[{hostname}]" if ":" in hostname else hostname
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
