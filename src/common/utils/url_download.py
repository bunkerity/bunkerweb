"""Bounded downloads for the URL-list settings (``EXTERNAL_PLUGIN_URLS``, ``EXTERNAL_TEMPLATE_URLS``).

A URL may end with a ``#sha256=<64 hex digits>`` fragment. The fragment is never sent (it is not
part of the request), and the bytes received -- whatever the scheme, ``file:///`` included -- must
hash to it or the download is refused. A fragment that starts with ``sha256=`` but is not a full
digest is refused rather than read as "no pin": a typo must not silently unpin a URL. Any other
fragment is left alone, as before.

The scheme rule: ``https://`` and ``file:///`` always, ``http://`` only when the caller allows it,
and an https URL is never followed through a redirect to plain http, on any hop of the chain.
"""

from hashlib import sha256
from pathlib import Path
from re import compile as re_compile
from time import sleep
from typing import Optional, Tuple
from urllib.parse import urljoin, urlsplit

from requests import Session
from requests.exceptions import ConnectionError, RequestException

PIN_PREFIX = "sha256="
_DIGEST_RX = re_compile(r"^[0-9a-fA-F]{64}\Z")
_CHUNK = 64 * 1024
_MAX_REDIRECTS = 30


class DownloadError(Exception):
    """The URL was refused or could not be fetched; the message says why."""


def split_pin(url: str) -> Tuple[str, Optional[str]]:
    """``(url without the pin fragment, lowercase hex digest or None)``. Raises on a malformed pin."""
    base, separator, fragment = url.partition("#")
    if not separator or not fragment.startswith(PIN_PREFIX):
        return url, None
    digest = fragment[len(PIN_PREFIX) :]
    if not _DIGEST_RX.match(digest):
        raise DownloadError(f"invalid pin #{fragment}: expected #sha256= followed by 64 hexadecimal digits")
    return base, digest.lower()


def _too_big(size: int, max_bytes: int) -> DownloadError:
    return DownloadError(f"the download exceeds {max_bytes} bytes ({size} or more)")


def _read_file(url: str, max_bytes: int) -> bytes:
    parts = urlsplit(url)
    if parts.netloc or not parts.path.startswith("/"):
        raise DownloadError("a file URL must be absolute: file:///path/to/file")
    path = Path(parts.path)
    try:
        with path.open("rb") as file:
            data = file.read(max_bytes + 1)
    except OSError as e:
        raise DownloadError(f"cannot read {path}: {e}") from e
    if len(data) > max_bytes:
        raise _too_big(len(data), max_bytes)
    return data


def _get(session: Session, url: str, timeout: float, retries: int):
    attempt = 1
    while True:
        try:
            return session.get(url, headers={"User-Agent": "BunkerWeb"}, stream=True, timeout=timeout, allow_redirects=False)
        except ConnectionError:
            if attempt >= retries:
                raise
            attempt += 1
            sleep(3)


def _fetch(url: str, max_bytes: int, timeout: float, retries: int) -> bytes:
    # Redirects are followed by hand so the scheme rule holds on every hop: a plain-http intermediate
    # of an https chain (https -> http -> https) is refused before it is requested, not judged by
    # where the chain ended up. One session for the whole chain, so a cookie set by an earlier hop
    # is sent on the next one, as with `allow_redirects=True`.
    with Session() as session:
        for _ in range(_MAX_REDIRECTS + 1):
            resp = _get(session, url, timeout, retries)
            if not resp.is_redirect:
                break
            location = resp.headers["Location"]
            resp.close()
            target = urljoin(url, location)
            if urlsplit(url).scheme == "https" and urlsplit(target).scheme != "https":
                raise DownloadError(f"refused a redirect from https to {target}")
            url = target
        else:
            raise DownloadError(f"more than {_MAX_REDIRECTS} redirects")
        return _read_body(resp, max_bytes)


def _read_body(resp, max_bytes: int) -> bytes:
    with resp:
        if resp.status_code != 200:
            raise DownloadError(f"got HTTP status {resp.status_code}")

        declared = resp.headers.get("Content-Length", "")
        if declared.isdigit() and int(declared) > max_bytes:
            raise _too_big(int(declared), max_bytes)

        data = bytearray()
        for chunk in resp.iter_content(chunk_size=_CHUNK):
            data += chunk
            if len(data) > max_bytes:
                raise _too_big(len(data), max_bytes)
        return bytes(data)


def download(url: str, *, max_bytes: int, allow_http: bool = False, timeout: float = 10, retries: int = 3) -> bytes:
    """The bytes behind ``url``, at most ``max_bytes`` of them, checked against its pin if it has one."""
    base, pin = split_pin(url)
    scheme = urlsplit(base).scheme
    if scheme == "file":
        data = _read_file(base, max_bytes)
    elif scheme == "https" or (scheme == "http" and allow_http):
        try:
            data = _fetch(base, max_bytes, timeout, retries)
        except RequestException as e:
            raise DownloadError(str(e)) from e
    elif scheme == "http":
        raise DownloadError("plain http is refused, use https:// or file:///")
    else:
        raise DownloadError(f"unsupported URL {base!r}, use https:// or file:///")

    if pin and sha256(data).hexdigest() != pin:
        raise DownloadError(f"sha256 mismatch: expected {pin}, got {sha256(data).hexdigest()}")
    return data
