#!/usr/bin/env python3

from contextlib import suppress
from copy import deepcopy
from typing import Literal, Optional, Union
from os import getenv
from urllib.parse import urlsplit
from requests import Session, request
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError
from urllib3 import disable_warnings  # new
from urllib3.exceptions import InsecureRequestWarning  # new

from common_utils import parse_host  # type: ignore
from logger import getLogger  # type: ignore

# Suppress urllib3 InsecureRequestWarning when verify=False (default: enabled)
if getenv("API_SUPPRESS_INSECURE_WARNING", "1").lower() in ("1", "true", "yes", "on"):
    with suppress(Exception):
        disable_warnings(InsecureRequestWarning)


class _FingerprintAdapter(HTTPAdapter):
    """requests adapter that pins the peer certificate by its SHA-256 fingerprint
    (urllib3 assert_fingerprint), so a self-signed instance cert is trusted by
    fingerprint rather than by CA chain."""

    def __init__(self, fingerprint: Optional[str], **kwargs):
        self._assert_fingerprint = fingerprint
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["assert_fingerprint"] = self._assert_fingerprint
        super().init_poolmanager(*args, **kwargs)


class API:
    """
    Thin HTTP client for BunkerWeb API with centralized endpoint building.

    Enhancements:
    - API.from_instance(dict) to build scheme/port/host from DB instance data
    - API.from_url_or_parts(hostname_or_url, ...) for ad-hoc construction
    - SSL verification and CA bundle controlled via env or constructor
    """

    def __init__(
        self,
        endpoint: str,
        host: Optional[str] = None,
        token: Optional[str] = None,
        *,
        tls_mode: str = "off",
        tls_fingerprint: Optional[str] = None,
    ):
        try:
            scheme, hostname, port = parse_host(endpoint)
        except ValueError as e:
            raise ValueError("Invalid API endpoint: expected an HTTP(S) URL without user information") from e
        if not scheme:
            raise ValueError("Invalid API endpoint: expected an HTTP(S) URL without user information")
        rendered_host = f"[{hostname}]" if ":" in hostname else hostname
        self.__endpoint = f"{scheme}://{rendered_host}{f':{port}' if port is not None else ''}/"
        # Host header (defaults to API_SERVER_NAME)
        self.__host = host or getenv("API_SERVER_NAME", "bwapi")
        # Optional API token: if not provided, fallback to env var
        self.__token = token if token is not None else getenv("API_TOKEN")
        # Per-instance TLS trust: "off" (unverified, legacy) or "pinned" (SHA-256)
        self.__tls_mode = tls_mode or "off"
        self.__tls_fingerprint = tls_fingerprint
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

        pinned = self.__tls_mode == "pinned" and bool(self.__tls_fingerprint)
        if self.__tls_mode == "pinned" and not self.__tls_fingerprint:
            self.__logger.warning(f"Instance {self.__endpoint} is in TLS mode 'pinned' but has no fingerprint; the connection cannot be pinned")

        full_url = f"{self.__endpoint}{url if not url.startswith('/') else url[1:]}"
        try:
            if pinned:
                # Trust the self-signed instance cert by SHA-256 fingerprint, not CA chain.
                resp = self.__pinned_session().request(method, full_url, timeout=timeout, headers=deepcopy(headers), verify=False, **deepcopy(kwargs))
            else:
                resp = request(
                    method,
                    full_url,
                    timeout=timeout,
                    headers=deepcopy(headers),
                    verify=False,  # TODO: per-instance CA verification (tls_mode "verify") is a Tier B follow-up
                    **deepcopy(kwargs),
                )
        except ConnectionError as e:
            scheme = urlsplit(self.__endpoint).scheme
            # Pinned instances must never be silently downgraded to plaintext HTTP.
            if scheme == "https" and not pinned:
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

    def __pinned_session(self) -> Session:
        """A requests Session that pins the peer cert by SHA-256 for HTTPS dials."""
        session = Session()
        session.mount("https://", _FingerprintAdapter(self.__tls_fingerprint))
        return session

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
        scheme, hostname, eff_port = parse_host(hostname_or_url)
        scheme = scheme or ("https" if listen_https else "http")

        if eff_port is None:
            eff_port = (
                (https_port if https_port is not None else cls.__default_https_port())
                if scheme == "https"
                else (port if port is not None else cls.__default_http_port())
            )
        try:
            eff_port = int(eff_port)
        except (TypeError, ValueError) as e:
            raise ValueError("Invalid API port: expected an integer") from e
        if not 1 <= eff_port <= 65535:
            raise ValueError("Invalid API port: expected a value between 1 and 65535")
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
        return cls(endpoint, host=host, token=token, tls_mode=instance.get("tls_mode", "off"), tls_fingerprint=instance.get("tls_fingerprint"))

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
        tls_mode: str = "off",
        tls_fingerprint: Optional[str] = None,
    ) -> "API":
        endpoint = cls.build_endpoint(hostname_or_url, port=port, listen_https=listen_https, https_port=https_port)
        host = server_name or getenv("API_SERVER_NAME", "bwapi")
        return cls(endpoint, host=host, token=token, tls_mode=tls_mode, tls_fingerprint=tls_fingerprint)
