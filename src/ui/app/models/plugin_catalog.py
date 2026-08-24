"""The community catalogue: a pinned manifest of plugins and service templates published by the
BunkerWeb organisation on GitHub, installable in one click.

This module is the whole security boundary, and it is deliberately almost all pure functions so
that it can be tested exhaustively without a fixture stack. Nothing here installs anything: the
catalogue contributes a pinned manifest, a SHA-256 gate on the downloaded bytes *before* they
reach any extractor, an archive-identity check, and a version gate — then hands the verified
bytes to the installer that already exists (``POST /plugins/upload`` with ``method="ui"`` for
plugins, ``POST /templates`` for templates). There is deliberately no second install mechanism.

The chain, in order, and the order is the design:

    pinned URL (constant, not a setting)
      -> https + host allowlist            no request is issued to a host we did not allow
      -> capped read                       Content-Length is never trusted
      -> validate_catalog()                every field re-typed, unknown keys dropped
      -> [operator clicks Install on ONE item]
      -> item re-looked-up in the CACHED VALIDATED catalog by id (never from the POST body)
      -> freshness gate                    a manifest nobody could refresh stops being installable
      -> version gate                      fails CLOSED
      -> artifact GET                      allowlisted, redirects walked manually, capped
      -> verify_digest()                   compare_digest, BEFORE anything parses the bytes
      -> archive identity + single root    the id that reaches the filesystem is the ARCHIVE's
      -> ONLY NOW the existing installer

Two things that look like belt-and-braces and are not:

* ``archive_plugin_roots()`` exists because the id the API writes to the filesystem is the one
  inside the archive's ``plugin.json`` (``routers/plugins.py`` :333 and :389), **not** the
  manifest id every gate here keys on. Without an equality check the gates guard a name the
  install does not use.
* the single-root requirement exists because both install branches loop over *every*
  ``plugin.json`` found in the archive, so one click could otherwise install N plugins, none of
  them version-gated or named in the manifest.

What this does NOT give you: authenticity. The manifest and the artifacts it names share one
trust root (write access to ``bunkerity/bunkerweb-plugins``), so SHA-256 defends against
transfer corruption, a re-cut asset against a stale manifest, and a CDN edge that does not also
control the repo — not against a hostile publisher. Ed25519 signing is deferred; until it lands,
this catalogue's security equals that repository's write access.
"""

from datetime import datetime, timedelta
from hmac import compare_digest
from io import BytesIO
from json import JSONDecodeError, loads
from os import getenv
from pathlib import Path
from re import compile as re_compile
from tarfile import TarError, open as tar_open
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit
from zipfile import BadZipFile, ZipFile

from packaging.version import InvalidVersion, Version
from requests import get

from common_utils import bytes_hash, normalize_bunkerweb_version  # type: ignore

# ── Pinned source ───────────────────────────────────────────────────────────
#
# Hardcoded on purpose. The single most valuable property of this feature is that an operator
# cannot be tricked into pointing it at someone else's manifest, and a configuration knob gives
# that away in exchange for nothing. The kill switch below is a boolean, never a URL: disabling
# the feature removes a feature, redirecting it would remove the guarantee.
CATALOG_URL = "https://raw.githubusercontent.com/bunkerity/bunkerweb-plugins/main/catalog.json"

# ── Caps ────────────────────────────────────────────────────────────────────
#
# All three are enforced on transferred bytes, by reading at most cap+1 and rejecting on
# overflow -- never by trusting Content-Length, which is a claim and not a measurement.
#
# MANIFEST_MAX is not cosmetic: UIData rewrites the whole ui_data.json on every __setitem__, so
# an oversized manifest is a self-inflicted DoS on every later DATA write in the process. The
# real manifest for all 9 published plugins measures 4813 bytes, so 256 KB is ~54x headroom.
MANIFEST_MAX = 256 * 1024
ARTIFACT_MAX_PLUGIN = 16 * 1024 * 1024
ARTIFACT_MAX_TEMPLATE = 512 * 1024

MAX_ITEMS_PER_LIST = 200
MAX_REDIRECTS = 3

# A plugin.json read out of an archive member. The archive itself is already capped, but gzip and
# zip both amplify, so a member can declare far more than the transferred bytes suggest. Real
# manifests are a few KB.
MAX_PLUGIN_JSON = 256 * 1024

# Timeouts differ by payload size, and the difference matters. The manifest refresh runs on
# `_periodic_tasks_executor`, a ThreadPoolExecutor(max_workers=2) shared with session cleanup
# and the other GitHub fetches (main.py) -- a 30s read there occupies half the pool. The
# manifest is ~5 KB, so it gets the same timeout=3 as its neighbours in utils.py. An artifact
# can be 16 MB, so it gets a short connect and a long read.
MANIFEST_TIMEOUT = 3
ARTIFACT_TIMEOUT = (5, 30)

# A cached manifest stops being installable once it is this old. The hourly refresh gates
# whether a *fetch* is attempted and only overwrites the value on success -- fail-soft, which is
# right for a star count and wrong for a supply-chain manifest. 24h is 24 refresh attempts: a
# single failure never trips it, only a sustained outage does, and a sustained outage is exactly
# when nobody should be installing from a manifest that cannot be confirmed.
CATALOG_MAX_AGE = timedelta(hours=24)

# Stricter than the API's own `^[\w.-]{4,64}\Z`: lowercase, must start alphanumeric, no dot at
# all. A catalogue id is not operator-supplied and is also used as a dict key, a DOM id and a
# template id. `{3,63}` after the leading character gives a total length of 4..64, matching the
# API's floor -- an earlier draft used `{2,63}` and let 3-character ids through, which the API
# then rejected. `\Z` and not `$`, for the same reason the API uses it: `$` matches before a
# trailing newline, and a trailing newline is attacker-influenced input reaching a path.
CATALOG_ID_RX = re_compile(r"^[a-z0-9][a-z0-9_-]{3,63}\Z")
SHA256_RX = re_compile(r"^[0-9a-f]{64}\Z")

# Host allowlist. Without it the manifest is an SSRF primitive: the UI container sits inside the
# compose network with bw-api, the scheduler, the database and the broker one hostname away.
# That -- reachability, not authenticity -- is what this list is for.
#
# An earlier version accepted any `.githubusercontent.com` host, on the stated premise that the
# whole suffix is "GitHub-controlled". **That premise is false.** GitHub *operates* those hosts,
# but several of them serve bytes any user can write:
#
#   gist.githubusercontent.com   -- raw content of any gist, created by anyone
#   camo.githubusercontent.com   -- proxied remote images
#
# "GitHub-operated" and "GitHub-authored" are different properties, and the suffix only gave the
# first. So the list is exact, and it is the complete set actually in play:
#
#   raw.githubusercontent.com      the pinned manifest
#   release-assets.githubusercontent.com  where a release asset download 302s today (measured)
#   objects.githubusercontent.com  the previous name for that same hop, kept for a rollback
#   github.com                     the /releases/download/ URL before it redirects
#
# The rename risk that motivated the suffix is real -- GitHub has renamed this hop once already
# (`objects.` -> `release-assets.`) -- but it is the cheaper failure: a rename produces a visibly
# failed download with an allowlist error, not a compromise, and the producer side is ours to
# update. A user-writable host inside the allowlist is not recoverable in the same way.
#
# **What actually decides whether bytes get installed is the SHA-256 gate, not the hostname**, and
# that is the only claim this list makes. It narrows where we are willing to send a request; it
# says nothing about who wrote what comes back.
#
# github.com and raw. additionally require the repository path prefix. The asset hops cannot:
# their paths are opaque signed blobs.
_REPO_PATH_PREFIX = "/bunkerity/bunkerweb-plugins/"
_REPO_HOSTS = frozenset({"github.com", "raw.githubusercontent.com"})
_ASSET_HOSTS = frozenset({"release-assets.githubusercontent.com", "objects.githubusercontent.com"})

_REQUIRED_FIELDS = ("id", "name", "version", "url", "sha256", "size", "bw_min")

_MAX_NAME = 64
_MAX_DESCRIPTION = 512
_MAX_REQUIRES = 5
_MAX_REQUIRES_LEN = 200
_MAX_GENERATED_AT = 64


def catalog_enabled() -> bool:
    """Whether the catalogue is switched on at all.

    A boolean, never a URL. Off means: no outbound request is issued (a *skip*, not a swallowed
    failure -- that distinction is the whole point for an egress-restricted install), the
    catalogue sections are not rendered, and both install routes refuse. It does not uninstall
    anything already installed; those are ordinary plugins and templates from that moment on.
    """
    return getenv("USE_PLUGIN_CATALOG", "yes").strip().lower() not in ("no", "off", "false", "0")


# ── URL allowlist ───────────────────────────────────────────────────────────


def validate_artifact_url(url: Any) -> bool:
    """True when ``url`` is one we are willing to issue a request to.

    Checked before any request is made, and again on every redirect target -- ``requests``' own
    redirect following is turned off precisely so an off-allowlist hop cannot slip through.
    """
    if not isinstance(url, str) or not url:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False

    if parts.scheme != "https" or parts.fragment:
        return False

    netloc = parts.netloc
    # Everything left of `@` is userinfo: `https://github.com@evil.com/x` has hostname evil.com.
    if "@" in netloc:
        return False
    try:
        if parts.port is not None:
            return False
    except ValueError:
        return False

    host = (parts.hostname or "").lower()
    if not host:
        return False

    # The path is traversal-checked; the query is NOT. A signed release-asset URL is almost
    # entirely query string and legitimately carries %2F, %3B and %20 -- a query-scoped check
    # would reject every real download.
    #
    # Both the raw and the decoded form are checked, and a percent-escape that decodes into a
    # new path separator is refused outright: `%2f` is how `a%2f..%2fb` smuggles a segment past
    # a naive split.
    path = parts.path
    decoded = unquote(path)
    if ".." in path.split("/") or ".." in decoded.split("/"):
        return False
    if decoded.count("/") != path.count("/"):
        return False

    if host in _REPO_HOSTS:
        return path.startswith(_REPO_PATH_PREFIX)
    return host in _ASSET_HOSTS


# ── Manifest validation ─────────────────────────────────────────────────────


def _valid_version(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        Version(normalize_bunkerweb_version(value))
    except (InvalidVersion, TypeError):
        return False
    return True


def _validate_item(raw: Any, artifact_max: int, errors: List[str], seen: set) -> Optional[Dict[str, Any]]:
    """Validate one manifest entry. Returns a freshly built dict, or None (and records why).

    A rejected item is dropped; it never fails the whole manifest. One bad row must not be able
    to black out the catalogue -- that would hand a single malformed entry a denial of service
    over every other item.
    """
    if not isinstance(raw, dict):
        errors.append("item is not an object")
        return None

    for field in _REQUIRED_FIELDS:
        if field not in raw:
            errors.append(f"item is missing required field {field!r}")
            return None

    item_id = raw["id"]
    if not isinstance(item_id, str) or not CATALOG_ID_RX.match(item_id):
        errors.append(f"invalid id {item_id!r}")
        return None
    if item_id in seen:
        # First wins, deterministically: a JSON array has a stable order, so this is not a
        # coin flip. A later duplicate cannot shadow an earlier entry's url or checksum.
        errors.append(f"duplicate id {item_id!r}, keeping the first")
        return None

    sha = raw["sha256"]
    # Lowercase only, and never case-folded here: normalising at this boundary would mean the
    # value compared at the hash gate is not the value the manifest published.
    if not isinstance(sha, str) or not SHA256_RX.match(sha):
        errors.append(f"{item_id}: invalid sha256")
        return None

    size = raw["size"]
    # `isinstance(True, int)` is True in Python, so a bare isinstance check accepts a boolean
    # as a byte count.
    if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= artifact_max:
        errors.append(f"{item_id}: invalid size {size!r}")
        return None

    if not validate_artifact_url(raw["url"]):
        errors.append(f"{item_id}: url is not allowlisted")
        return None

    if not _valid_version(raw["version"]) or not _valid_version(raw["bw_min"]):
        errors.append(f"{item_id}: unparseable version or bw_min")
        return None

    bw_max = raw.get("bw_max")
    if bw_max is not None and not _valid_version(bw_max):
        errors.append(f"{item_id}: unparseable bw_max")
        return None

    name = raw["name"]
    if not isinstance(name, str) or not name.strip() or len(name) > _MAX_NAME:
        errors.append(f"{item_id}: invalid name")
        return None

    description = raw.get("description", "")
    if not isinstance(description, str) or len(description) > _MAX_DESCRIPTION:
        errors.append(f"{item_id}: invalid description")
        return None

    requires = raw.get("requires") or []
    if not isinstance(requires, list) or len(requires) > _MAX_REQUIRES:
        errors.append(f"{item_id}: invalid requires")
        return None
    for line in requires:
        if not isinstance(line, str) or len(line) > _MAX_REQUIRES_LEN:
            errors.append(f"{item_id}: invalid requires entry")
            return None

    homepage = raw.get("homepage")
    if homepage is not None and not validate_artifact_url(homepage):
        # It becomes an href, so it gets the same treatment as a download target.
        errors.append(f"{item_id}: homepage is not allowlisted")
        return None

    seen.add(item_id)
    # Built fresh, field by field. The parsed input object is never stored or forwarded, so an
    # unknown key cannot ride into DATA, into a template, or into an install.
    return {
        "id": item_id,
        "name": name,
        "description": description,
        "version": raw["version"],
        "url": raw["url"],
        "sha256": sha,
        "size": size,
        "bw_min": raw["bw_min"],
        "bw_max": bw_max,
        "requires": list(requires),
        "homepage": homepage,
    }


def validate_catalog(raw_bytes: Any) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Parse and validate a raw ``catalog.json`` body.

    Returns ``(catalog, errors)``. ``catalog`` is None only when the manifest is unusable as a
    whole (too big, not JSON, wrong schema version, malformed lists); a per-item problem drops
    that item and shows up in ``errors``.
    """
    errors: List[str] = []

    if not isinstance(raw_bytes, (bytes, bytearray)):
        return None, ["manifest is not bytes"]
    if len(raw_bytes) > MANIFEST_MAX:
        return None, [f"manifest exceeds {MANIFEST_MAX} bytes"]

    try:
        parsed = loads(bytes(raw_bytes).decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError, ValueError):
        return None, ["manifest is not valid UTF-8 JSON"]
    if not isinstance(parsed, dict):
        return None, ["manifest is not a JSON object"]

    # `True` again: isinstance(True, int) would let `"schema_version": true` through. A string
    # "1" is refused too -- a producer that drifts on the type has drifted on the contract, and
    # coercing silently is how a v2 manifest gets read as v1.
    version = parsed.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        return None, [f"unsupported schema_version {version!r}"]

    generated_at = parsed.get("generated_at", "")
    if not isinstance(generated_at, str) or len(generated_at) > _MAX_GENERATED_AT:
        return None, ["invalid generated_at"]

    out: Dict[str, Any] = {"schema_version": 1, "generated_at": generated_at}
    for key, artifact_max in (("plugins", ARTIFACT_MAX_PLUGIN), ("templates", ARTIFACT_MAX_TEMPLATE)):
        raw_list = parsed.get(key, [])
        if raw_list is None:
            raw_list = []
        if not isinstance(raw_list, list):
            return None, [f"{key} is not a list"]
        if len(raw_list) > MAX_ITEMS_PER_LIST:
            return None, [f"{key} holds more than {MAX_ITEMS_PER_LIST} items"]

        # Scoped per list, so the same id may name a plugin and a template without colliding.
        seen: set = set()
        out[key] = [item for item in (_validate_item(raw, artifact_max, errors, seen) for raw in raw_list) if item is not None]

    return out, errors


# ── Version gate ────────────────────────────────────────────────────────────


def is_compatible(bw_version: Any, bw_min: Any, bw_max: Any = None) -> bool:
    """Whether an item declaring ``bw_min``/``bw_max`` may be installed on ``bw_version``.

    Lower bound inclusive, **upper bound exclusive** so a producer can write ``"2.0.0"`` to mean
    "all of 1.x" without enumerating.

    Fails CLOSED on anything unparseable -- deliberately the opposite stance to
    ``is_newer_version_available``, whose docstring prefers a false negative. There a parse
    failure costs a missed notification; here it costs running an incompatible plugin as code in
    the UI process, in the worker and in nginx.
    """
    if not _valid_version(bw_version) or not _valid_version(bw_min):
        return False
    if bw_max is not None and not _valid_version(bw_max):
        return False

    current = Version(normalize_bunkerweb_version(bw_version))
    if current < Version(normalize_bunkerweb_version(bw_min)):
        return False
    if bw_max is not None and current >= Version(normalize_bunkerweb_version(bw_max)):
        return False
    return True


def collides_with_installed(item_id: str, installed: Dict[str, Any]) -> bool:
    """Whether ``item_id`` is already taken by an installed plugin **of any type**.

    Stricter than the API's own check, which builds its ``existing_ids`` from
    ``get_plugins(_type="ui")`` only and is therefore blind to core, external and pro ids. The
    DB layer does refuse to overwrite a core row, but it refuses *silently* -- the router still
    reports the id as created -- so an operator would be told an install succeeded when nothing
    happened. Exact match: ids are lowercase by construction (CATALOG_ID_RX).
    """
    return item_id in installed


# ── Freshness ───────────────────────────────────────────────────────────────


def catalog_age(fetched_at: Any) -> Optional[timedelta]:
    """Age of a cached manifest, or None when the stamp is missing or unreadable."""
    if not isinstance(fetched_at, str) or not fetched_at:
        return None
    try:
        stamp = datetime.fromisoformat(fetched_at)
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.astimezone()
    return datetime.now().astimezone() - stamp


def is_stale(fetched_at: Any) -> bool:
    """Whether a cached manifest is too old to install from.

    An unreadable or absent stamp counts as stale: we cannot show that the manifest is fresh, so
    we do not act on it.

    **A stamp in the future counts as stale too**, and that is not pedantry. The bound used to be
    a one-sided ``age > CATALOG_MAX_AGE``, which a negative age passes -- so a stamp dated 2037
    read as permanently fresh and re-opened exactly the hole the freshness gate exists to close.
    ``ui_data.json`` is a file other processes write (see ``read_cached``), and a clock that jumps
    backwards produces the same shape without anyone being hostile. The window is closed at both
    ends: an age must be inside ``[0, CATALOG_MAX_AGE]``.
    """
    age = catalog_age(fetched_at)
    return age is None or not (timedelta(0) <= age <= CATALOG_MAX_AGE)


# ── Fetching ────────────────────────────────────────────────────────────────


def _read_capped(response, cap: int) -> Optional[bytes]:
    """Read at most ``cap`` bytes, returning None if the body is larger.

    Content-Length is never consulted: it is a claim by the server, and a lying or absent header
    must not be able to buy an unbounded read.
    """
    buf = BytesIO()
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > cap:
            return None
        buf.write(chunk)
    return buf.getvalue()


def _get_allowlisted(url: str, *, timeout, cap: int) -> bytes:
    """GET an allowlisted URL, walking redirects ourselves so each hop is re-validated.

    Raises ValueError on any policy failure (bad URL, off-allowlist redirect, too many hops,
    non-200, oversized body). Network errors propagate as RequestException.
    """
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        if not validate_artifact_url(current):
            raise ValueError("URL is not allowlisted")
        # `with` rather than a trailing close(): these are streamed responses, so the connection
        # stays checked out of the pool until the body is drained or the response is released.
        # Every exit below can raise -- an off-allowlist redirect, a non-200, an over-cap body,
        # or a mid-stream network error inside `_read_capped` -- and the hand-rolled close() this
        # replaces was skipped on the last of those, leaking a connection per failed download.
        with get(
            current,
            headers={"User-Agent": "BunkerWeb"},
            timeout=timeout,
            stream=True,
            allow_redirects=False,
        ) as response:
            if response.is_redirect or response.is_permanent_redirect:
                target = response.headers.get("Location", "")
                if not target:
                    raise ValueError("redirect without a target")
                current = target
                continue
            if response.status_code != 200:
                raise ValueError(f"unexpected status {response.status_code}")
            data = _read_capped(response, cap)
            if data is None:
                raise ValueError(f"response exceeds {cap} bytes")
            return data
    raise ValueError("too many redirects")


def fetch_catalog() -> Optional[Dict[str, Any]]:
    """Fetch and validate the manifest. Returns the value to store, or None to keep the old one.

    Shape stored in ``DATA["PLUGIN_CATALOG"]``: ``{"fetched_at": <ISO>, "catalog": {...}}``. The
    stamp is what the freshness gate reads; without it a manifest nobody has been able to
    refresh would stay installable indefinitely.
    """
    if not catalog_enabled():
        return None
    raw = _get_allowlisted(CATALOG_URL, timeout=MANIFEST_TIMEOUT, cap=MANIFEST_MAX)
    catalog, _ = validate_catalog(raw)
    if catalog is None:
        return None
    return {"fetched_at": datetime.now().astimezone().isoformat(), "catalog": catalog}


def artifact_cap(declared_size: Any, ceiling: int) -> int:
    """The byte cap for one artifact download: the smaller of what it declares and the ceiling.

    ``size`` was being validated in the manifest and then never used -- every download was capped
    at the type ceiling (16 MB for a plugin, 512 KB for a template) no matter what the entry said.
    A validated field nothing reads is a field that silently stops meaning anything, so it is
    wired up here rather than dropped: an entry declaring 8 KB now gets an 8 KB cap.

    It is a floor on nothing and a ceiling on everything: ``min`` means a manifest can only make
    the limit *tighter*, never looser, so a hostile ``size`` cannot buy a bigger read than the
    constant already allowed. A missing or unusable value falls back to the ceiling.

    This is a resource bound, not an integrity check -- SHA-256 is what decides whether the bytes
    are right. Its value is that a truncated or substituted body stops being buffered the moment
    it passes what the entry claimed, instead of at 16 MB.
    """
    if isinstance(declared_size, bool) or not isinstance(declared_size, int) or declared_size <= 0:
        return ceiling
    return min(declared_size, ceiling)


def fetch_artifact(url: str, cap: int) -> bytes:
    """Download an artifact. Raises ValueError on policy failure, RequestException on network."""
    return _get_allowlisted(url, timeout=ARTIFACT_TIMEOUT, cap=cap)


# ── The hash gate ───────────────────────────────────────────────────────────


def verify_digest(payload: Any, expected: Any) -> bool:
    """Whether ``payload`` hashes to ``expected``.

    ``compare_digest`` rather than ``==``: the timing channel is not a realistic attack on a
    published hash, but an equality check on a security decision is exactly the line a reviewer
    should not have to think about twice. ``expected`` is never normalised -- an uppercase
    digest was already refused by ``validate_catalog``, and folding it here would mean comparing
    against something the manifest did not publish.
    """
    if not isinstance(payload, (bytes, bytearray)) or not isinstance(expected, str):
        return False
    return compare_digest(bytes_hash(bytes(payload), algorithm="sha256"), expected)


# ── Archive identity ────────────────────────────────────────────────────────


def archive_plugin_roots(payload: bytes) -> List[Tuple[str, str]]:
    """Every ``(root, declared_id)`` pair in a plugin archive.

    Called only on bytes that already passed ``verify_digest``, so a tampered archive never
    reaches a parser.

    This exists because of a mismatch that makes the rest of the gates decorative if ignored:
    the API writes ``TMP_UI_ROOT / meta["id"]`` where ``meta`` is the **archive's**
    ``plugin.json`` (``routers/plugins.py`` :333, :389), while every check in this module keys
    on the *manifest* id. A manifest entry for ``clamav`` whose tarball declares
    ``id: "blacklist"`` would otherwise pass everything and land under the other name.

    Returning every root (not just the first) is what lets the caller refuse a multi-root
    archive: both API branches loop over all of them, so one click would otherwise install N
    plugins, none version-gated and none named in the manifest.
    """
    roots: List[Tuple[str, str]] = []

    def _record(name: str, blob: bytes) -> None:
        parent = str(Path(name).parent)
        try:
            meta = loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, JSONDecodeError, ValueError):
            meta = {}
        declared = meta.get("id") if isinstance(meta, dict) else None
        roots.append(("" if parent == "." else parent, declared if isinstance(declared, str) else ""))

    try:
        with tar_open(fileobj=BytesIO(payload), mode="r:*") as tar:
            for member in tar.getmembers():
                if not member.isfile() or Path(member.name).name != "plugin.json":
                    continue
                handle = tar.extractfile(member)
                if handle is None:
                    continue
                # Capped: a plugin.json member declaring a huge size expands in memory here even
                # though the *archive* was already capped, because gzip amplifies. A real
                # plugin.json is a couple of KB; anything past the cap is read truncated, fails
                # to parse as JSON, and lands as a declared id of "" -- which the identity check
                # then refuses. No separate error path needed.
                _record(member.name, handle.read(MAX_PLUGIN_JSON + 1))
        return roots
    except (TarError, EOFError, ValueError):
        roots = []

    try:
        with ZipFile(BytesIO(payload)) as zipf:
            for name in zipf.namelist():
                if name.endswith("/") or Path(name).name != "plugin.json":
                    continue
                with zipf.open(name) as handle:
                    _record(name, handle.read(MAX_PLUGIN_JSON + 1))
    except (BadZipFile, KeyError, ValueError):
        return []
    return roots


def check_archive_identity(payload: bytes, manifest_id: str) -> Optional[str]:
    """None when the archive is exactly the one plugin the manifest named; else why not.

    Two refusals, both mandatory, and neither is belt-and-braces:

    * more than one ``plugin.json`` -- the installer would install every one of them;
    * a declared id that is not ``manifest_id`` -- that declared id, not ours, is what reaches
      the filesystem and the database.
    """
    roots = archive_plugin_roots(payload)
    if not roots:
        return "the archive contains no plugin.json"
    if len(roots) > 1:
        return f"the archive contains {len(roots)} plugins; a catalogue artifact must contain exactly one"
    declared = roots[0][1]
    if declared != manifest_id:
        return f"the archive declares id {declared!r} but the catalogue entry is {manifest_id!r}"
    return None


# ── Reading the cache ───────────────────────────────────────────────────────


def read_cached(data: Any) -> Tuple[Dict[str, List[Dict[str, Any]]], Optional[str]]:
    """Pull the catalogue out of ``DATA``. Returns ``(catalog, fetched_at)``.

    Tolerates every shape a crafted or truncated ``ui_data.json`` could hold -- it is a file on
    disk that other processes write, so it is parsed defensively rather than trusted.
    """
    empty: Dict[str, List[Dict[str, Any]]] = {"plugins": [], "templates": []}
    if not isinstance(data, dict):
        return empty, None
    catalog = data.get("catalog")
    if not isinstance(catalog, dict):
        return empty, None
    fetched_at = data.get("fetched_at")
    return {
        "plugins": [i for i in catalog.get("plugins", []) if isinstance(i, dict)],
        "templates": [i for i in catalog.get("templates", []) if isinstance(i, dict)],
    }, (fetched_at if isinstance(fetched_at, str) else None)


def build_catalog_view(kind: str, cached: Any, installed_ids: Any, bw_version: str) -> Dict[str, Any]:
    """The template context a catalogue section needs: its items, their state, and staleness.

    Pure: the caller does the I/O and passes the results in. That is not purity for its own sake
    -- it keeps this out of the route modules, so neither route has to import the other, and it
    makes the listing logic testable without a Flask app.

    Items already installed are dropped, not greyed: the installed card is the truth for those,
    and rendering both would be two cards claiming one id. Incompatible items are kept and marked
    instead -- hiding them makes the catalogue look empty and generates support tickets, while
    showing the reason makes the constraint explain itself.

    Everything here decides what is *drawn*. Every one of these checks is made again, server-side,
    in the install route: a disabled button is a hint, never a control.
    """
    if not catalog_enabled():
        return {"catalog_items": [], "catalog_available": False, "catalog_stale": False}

    catalog, fetched_at = read_cached(cached)
    items = catalog.get(kind, [])
    if not items:
        return {"catalog_items": [], "catalog_available": False, "catalog_stale": False}

    installed = set(installed_ids or ())
    view = [
        item | {"compatible": is_compatible(bw_version, item.get("bw_min"), item.get("bw_max")), "bw_version": bw_version}
        for item in items
        if item.get("id") not in installed
    ]
    return {"catalog_items": view, "catalog_available": True, "catalog_stale": is_stale(fetched_at)}


def find_item(data: Any, kind: str, item_id: str) -> Optional[Dict[str, Any]]:
    """Look one item up in the cached, validated catalogue.

    The install routes resolve everything -- url, sha256, size, bounds -- through here and take
    nothing but the id from the request. A client-supplied URL or hash would hand the browser
    exactly the power the pinned manifest exists to remove.
    """
    catalog, _ = read_cached(data)
    for item in catalog.get(kind, []):
        if item.get("id") == item_id:
            return item
    return None
