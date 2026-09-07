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
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import InsecureRequestWarning  # new

from common_utils import parse_host  # type: ignore
from logger import getLogger  # type: ignore

# Suppress urllib3 InsecureRequestWarning when verify=False (default: enabled)
if getenv("API_SUPPRESS_INSECURE_WARNING", "1").lower() in ("1", "true", "yes", "on"):
    with suppress(Exception):
        disable_warnings(InsecureRequestWarning)


class _BodyWriteTimeout(TimeoutError):
    """Raised where the write budget is armed, and nowhere else.

    A socket timeout on its own does not say which phase ran out: a connect timeout and a proxy
    connect failure both carry one in their chain, and both arrive as the same ConnectionError the
    body write does. Excluding those by class is a list that has to grow every time requests adds a
    subclass, so the write phase marks its own timeout instead and the marker is what is looked for.
    """


def _carries_write_timeout(exc: Optional[BaseException], depth: int = 4) -> bool:
    """Whether the body write's own timeout marker is somewhere inside exc.

    urllib3 turns it into a ProtocolError and requests turns that into a ConnectionError, both by
    nesting the original in args, so the class of the exception that arrives says nothing.
    """
    if exc is None or depth < 0:
        return False
    if isinstance(exc, _BodyWriteTimeout):
        return True
    if _carries_write_timeout(exc.__cause__, depth - 1) or _carries_write_timeout(exc.__context__, depth - 1):
        return True
    return any(isinstance(arg, BaseException) and _carries_write_timeout(arg, depth - 1) for arg in getattr(exc, "args", ()))


def _connection_class(base, write_timeout: float):
    """A connection that gives the body write its own deadline.

    urllib3 hands the socket the connect budget and only swaps in the read budget once the whole
    request has been written, so a peer that accepts the connection and then stops reading blocks
    an upload for as long as connecting is allowed to take. That is not a bound anyone chose for a
    large folder push.

    The deadline has to be the connection's own timeout, not a value written straight onto the
    socket: the top of HTTPConnection.request re-arms the socket from self.timeout whenever the
    socket already exists, and over HTTPS it always does, because the pool forces the connect in
    _validate_conn. So the connection is established first, under the untouched connect budget, and
    only the write runs on the write budget. The pool resets the connection to the read budget for
    the response.
    """

    class _Connection(base):
        def request(self, *args, **kwargs):
            # Establishing the connection is not the body write and keeps the connect budget.
            if self.is_closed:
                self.connect()
            saved, self.timeout = self.timeout, write_timeout
            try:
                return super().request(*args, **kwargs)
            except TimeoutError as e:
                # The connection is already established and the response is read later, so the only
                # socket timeout this call can raise belongs to the body write. Marking it here is
                # what lets the caller tell it apart after requests has rewrapped it.
                raise _BodyWriteTimeout(*e.args) from e
            finally:
                self.timeout = saved

    return _Connection


class _InstanceAdapter(HTTPAdapter):
    """requests adapter for one instance dial. Two independent halves, either of them optional:

    - it pins the peer certificate by its SHA-256 fingerprint (urllib3 assert_fingerprint), so a
      self-signed instance cert is trusted by fingerprint rather than by CA chain;
    - it gives the body write its own deadline (see _connection_class).

    One class rather than two, because init_poolmanager is all either half overrides and they do
    not collide -- and a PINNED instance receiving a folder push needs both at once, on the same
    scheme, which two adapters cannot do: the second mount replaces the first.
    """

    def __init__(self, fingerprint: Optional[str] = None, write_timeout: Optional[float] = None, **kwargs):
        # init_poolmanager runs from HTTPAdapter.__init__, so both values have to exist first.
        self._assert_fingerprint = fingerprint
        self._write_timeout = write_timeout
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        if self._assert_fingerprint is not None:
            kwargs["assert_fingerprint"] = self._assert_fingerprint
        super().init_poolmanager(*args, **kwargs)
        if self._write_timeout is None:
            return
        # PoolManager holds the shared module-level mapping by reference, so this rebinds the
        # attribute and never mutates the dict every other PoolManager in the process reads.
        self.poolmanager.pool_classes_by_scheme = {
            "http": type("_HTTPPool", (HTTPConnectionPool,), {"ConnectionCls": _connection_class(HTTPConnection, self._write_timeout)}),
            "https": type("_HTTPSPool", (HTTPSConnectionPool,), {"ConnectionCls": _connection_class(HTTPSConnection, self._write_timeout)}),
        }


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
        revoked: bool = False,
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
        # A revoked enrollment is refused here rather than at the ~18 call sites that build an API:
        # request() is the single funnel both the scheduler and the Celery worker's push path go
        # through, and refusing at construction would only push the caller back onto the global
        # token -- which is exactly what revocation has to prevent.
        self.__revoked = revoked
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
        write_timeout: Optional[float] = None,
    ) -> tuple[bool, str, Optional[int], Optional[dict]]:
        if self.__revoked:
            self.__logger.error(f"Refusing to contact {self.__endpoint}{url}: this instance's enrollment is revoked")
            return False, "instance enrollment revoked", None, None

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
            return False, "TLS pinning requires a fingerprint", None, None

        full_url = f"{self.__endpoint}{url if not url.startswith('/') else url[1:]}"
        # DEV-2b5: every caller unpacks a four-tuple -- ApiCaller.send_to_apis does it inside a
        # thread-pool task -- so no path out of here may raise. Building the sender, the cleartext
        # retry and the JSON decode now sit inside the SAME boundary: the retry used to run inside
        # `except ConnectionError`, where its own failure escaped the sibling `except Exception`,
        # and resp.json() used to sit after the try, so an HTML 502 from a proxy took the caller
        # down instead of being reported as a failed push.
        session = None
        try:
            # timeout bounds the connect and the read; write_timeout bounds the body write, which
            # neither of them covers. With neither a pin nor a write budget the sender stays the
            # plain module-level call, so nothing about the request changes.
            if pinned or write_timeout is not None:
                session = self.__session(pinned, write_timeout)
            send = session.request if session is not None else request

            try:
                resp = send(
                    method,
                    full_url,
                    timeout=timeout,
                    headers=deepcopy(headers),
                    verify=False,  # TODO: per-instance CA verification (tls_mode "verify") is a Tier B follow-up
                    **deepcopy(kwargs),
                )
            except ConnectionError as e:
                # A body write that ran out its own budget is not a TLS problem, whatever the
                # scheme. Retrying it in cleartext spends the budget a second time and re-uploads
                # the whole archive, so the caller's write bound would silently be twice what it
                # asked for. Only the write phase's own marker counts: a connect timeout and a
                # proxy failure never reached the body and still carry a socket timeout in their
                # chain, so anything weaker reports every unreachable instance as a write that ran
                # out. Checked before the scheme, so a plain-HTTP instance gets the true reason too.
                if write_timeout is not None and _carries_write_timeout(e):
                    return False, f"Write timed out: {e}", None, None
                # An instance that comes up before its certificate is in place stays reachable over
                # the same port in plain HTTP; the retry is deliberate. Pinned instances must never
                # be silently downgraded to plaintext HTTP.
                if urlsplit(self.__endpoint).scheme != "https" or pinned:
                    return False, f"Connection error: {e}", None, None
                self.__logger.warning(f"SSL connection error when contacting {self.__endpoint}{url}, trying HTTP: {e}")
                resp = send(
                    method,
                    # replace(..., 1) strips the scheme prefix. lstrip takes a character SET, so it
                    # also ate any leading hostname character in {h, t, p, s, :, /}: an IP endpoint
                    # came through intact while a named one lost its first letters ("scheduler"
                    # arrived with its leading "s" eaten) and the retry failed to resolve.
                    f"{self.__endpoint.replace('https://', 'http://', 1)}{url if not url.startswith('/') else url[1:]}",
                    timeout=timeout,
                    headers=deepcopy(headers),
                    verify=False,
                    **deepcopy(kwargs),
                )
                self.__logger.debug(f"Response after retrying with HTTP: status={resp.status_code}, reason={resp.reason}, text={resp.text}")

            return True, "ok", resp.status_code, resp.json()
        except Exception as e:
            return False, f"Request failed: {e}", None, None
        finally:
            if session is not None:
                # The pinned session was never closed before: one connection pool leaked per dial.
                # Suppressed because this is the one statement left that could still raise out of a
                # function whose whole contract is that it never does (socket teardown can raise).
                with suppress(Exception):
                    session.close()

    def __session(self, pinned: bool, write_timeout: Optional[float]) -> Session:
        """A requests Session for one dial: the peer cert pinned by SHA-256 when the instance asks
        for it, the body write bounded when the caller asks for it, either or both."""
        session = Session()
        # Trust the self-signed instance cert by SHA-256 fingerprint, not CA chain.
        session.mount("https://", _InstanceAdapter(self.__tls_fingerprint if pinned else None, write_timeout))
        if write_timeout is not None:
            # A plain-HTTP endpoint and the cleartext retry both go through the http:// mount, and
            # the write budget has to cover them too. No fingerprint there: pinning is TLS-only.
            session.mount("http://", _InstanceAdapter(None, write_timeout))
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
        # The dedicated `credential_revoked` flag, not the derived `enrollment_state` string: a code
        # issued on a revoked row derives to "pending" (it always did), so reading the string here
        # lifted the revocation the moment an admin started the re-enrollment -- and with the
        # credential columns already cleared, the dial silently resumed on the global API_TOKEN.
        revoked = bool(instance.get("credential_revoked"))
        # `""` and not `None`: __init__ falls back to getenv("API_TOKEN") on None, so a revoked row
        # would quietly pick the global token back up if request()'s guard were ever removed.
        return cls(
            endpoint,
            host=host,
            token="" if revoked else (instance.get("credential") or token),
            tls_mode=instance.get("tls_mode", "off"),
            tls_fingerprint=instance.get("tls_fingerprint"),
            revoked=revoked,
        )

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
