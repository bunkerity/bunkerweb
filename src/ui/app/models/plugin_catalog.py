"""The community catalogue: the plugin and service-template repositories the BunkerWeb
organisation publishes on GitHub, browsable and installable in one click.

There is no manifest and no producer. **The repositories are the catalogue**: for each of the two
sources we resolve its LATEST RELEASE, download that release's source archive once, and read the
catalogue out of the bytes we just downloaded -- one top-level folder per item, each carrying its
own ``plugin.json`` / ``template.json``. Nothing is published, generated or signed on our side,
so there is nothing on our side that can drift out of step with what the repository actually
contains.

This module is the whole security boundary, and it is deliberately almost all pure functions so
that it can be tested exhaustively without a fixture stack. Nothing here installs anything: it
produces verified bytes and hands them to the installers that already exist (``POST
/plugins/upload`` with ``method="ui"`` for plugins, ``POST /templates`` for templates). There is
deliberately no second install mechanism.

The chain, in order, and the order is the design:

    pinned repo (constant, not a setting)
      -> GET /releases/latest       https + exact-host allowlist + capped read
      -> parse_release()            tag re-validated against a strict regex
      -> archive URL is DERIVED from the validated tag, never taken from the response body
      -> GET the source archive     allowlisted, redirects walked manually, capped
      -> archive_entries()          one folder per item, read from those bytes, member-capped
      -> the digest of the archive is RECORDED alongside the entries
      -> [operator clicks Install on ONE item]
      -> item re-looked-up in the CACHED VALIDATED catalogue by id (never from the POST body)
      -> freshness gate             a catalogue nobody could refresh stops being installable
      -> version gate               no entry or a newer build passes (PO rule, 2026-09-25)
      -> archive re-fetched AT THE PINNED TAG, never at "latest"
      -> verify_digest()            compare_digest against the digest recorded at refresh
      -> the ONE folder is repacked / materialised, by id
      -> ONLY NOW the existing installer

Two things that look like belt-and-braces and are not:

* **the identity check is now structural.** The id the installer writes to the filesystem is the
  one inside the archive's ``plugin.json`` (``routers/plugins.py`` :333 and :389), not a name we
  chose. So a folder is only a catalogue item when ``folder name == plugin.json id``, and the
  tarball handed to the installer is one we build ourselves containing exactly that one folder.
  The upstream archive -- which holds nine plugins -- is never handed to an installer that loops
  over every ``plugin.json`` it can find.

* **the recorded digest is not decoration, because a git tag is not immutable.** "Release
  immutability" is the usual shorthand, but a maintainer (or anyone who takes the repository) can
  force-move a tag, and ``codeload`` will then serve different bytes for the same URL. Recording
  the digest we enumerated and comparing it at install time does not prove authorship -- it proves
  that the bytes being installed are the bytes that were listed, and the 24h staleness gate bounds
  how long that promise has to hold.

What this does NOT give you: authenticity. The catalogue and its contents share one trust root --
write access to the two ``bunkerity`` repositories -- and the transport is TLS to GitHub. That
defends against a network attacker, against transfer corruption, and against a tag moved under our
feet between listing and install. It does not defend against a hostile publisher. Ed25519 signing
is deferred; until it lands, this catalogue's security equals those repositories' write access.
"""

from datetime import datetime, timedelta
from hmac import compare_digest
from io import BytesIO
from json import JSONDecodeError, dumps, loads
from logging import getLogger
from os import getenv
from posixpath import normpath
from re import compile as re_compile
from tarfile import TarError, TarInfo, open as tar_open
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit

from packaging.version import InvalidVersion, Version
from requests import get
from requests.exceptions import RequestException

from common_utils import bytes_hash, normalize_bunkerweb_version  # type: ignore
from template_package import template_from_folder  # type: ignore

# The UI's own logger, by name: `app.utils` configures "UI" at startup, and importing it from
# there would pull the whole app into this pure module.
LOGGER = getLogger("UI")

# ── Pinned sources ──────────────────────────────────────────────────────────
#
# Hardcoded on purpose. The single most valuable property of this feature is that an operator
# cannot be tricked into pointing it at someone else's repository, and a configuration knob gives
# that away in exchange for nothing. The kill switch below is a boolean, never a URL or a repo
# name: disabling the feature removes a feature, redirecting it would remove the guarantee.
PLUGINS_REPO = "bunkerity/bunkerweb-plugins"
TEMPLATES_REPO = "bunkerity/bunkerweb-templates"

# Where each source keeps its items inside its release archive, and what file makes a folder an
# item. Plugin folders sit at the archive root; template folders sit one level down under
# `templates/`. Measured against the real archives, not assumed -- see the module tests.
#
# `version_gate` says whether that source declares BunkerWeb compatibility at all, and it is the
# single switch behind the whole version-gate question -- see `item_compatible`.
SOURCES: Dict[str, Dict[str, Any]] = {
    "plugins": {"repo": PLUGINS_REPO, "subdir": "", "member": "plugin.json", "version_gate": True},
    "templates": {"repo": TEMPLATES_REPO, "subdir": "templates", "member": "template.json", "version_gate": False},
}

# ── Caps ────────────────────────────────────────────────────────────────────
#
# Every one of these is enforced on bytes we actually counted, by reading at most cap+1 and
# rejecting on overflow -- never by trusting Content-Length, which is a claim and not a
# measurement. The measured figures behind the numbers, taken 2026-08-24 against the real
# releases (bunkerweb-plugins v1.11, bunkerweb-templates 0.6):
#
#   release JSON   4621 B (plugins) / 5220 B (templates)
#   archive        205672 B (plugins) / 398042 B (templates) transferred
#   uncompressed   601932 B over 191 members / 534707 B over 87 members
#   largest member 340232 B (the templates repo's logo.png)
#
# RELEASE_MAX is not cosmetic: UIData rewrites the whole ui_data.json on every __setitem__, so an
# oversized value is a self-inflicted DoS on every later DATA write in the process.
RELEASE_MAX = 256 * 1024

# ~40x headroom on the plugins archive, ~20x on the templates one. Deliberately far below the
# 16 MB a single plugin artifact used to be allowed: we now download one archive instead of N
# artifacts, and an archive that suddenly grew 40x is a reason to stop, not to keep reading.
ARCHIVE_MAX = 8 * 1024 * 1024

# The transfer cap above bounds *compressed* bytes, and gzip amplifies. These two bound how much
# a member is allowed to expand to **while we copy it**: ~53x headroom on the real uncompressed
# total, ~12x on the real largest member.
#
# What they do NOT bound, stated plainly because an earlier comment here overclaimed it: `tarfile`
# must decompress the stream to walk it, so `getmembers()` inflates the whole archive before
# either number is ever consulted. Measured here -- a 64 KB archive declaring one 64 MB member
# walks 67108880 uncompressed bytes, 1027x the transferred size, inside `getmembers()` alone,
# with every cap nominally "in force". Reaching that needs write access to one of the two pinned
# repositories, i.e. the same trust root the entire feature already rests on, so it is a
# documented limit rather than a hole. But these are a COPY budget, not a decompression budget,
# and describing them as the latter would be a claim a reviewer could rely on and be wrong.
EXTRACT_MAX = 32 * 1024 * 1024
MEMBER_MAX = 4 * 1024 * 1024

# A plugin.json / template.json read out of an archive member. Real ones are a few KB.
MAX_MEMBER_JSON = 256 * 1024

MAX_ITEMS_PER_LIST = 200
MAX_REDIRECTS = 3

# Timeouts differ by payload size, and the difference matters. The refresh runs on
# `_periodic_tasks_executor`, a ThreadPoolExecutor(max_workers=2) shared with session cleanup and
# the other GitHub fetches (main.py) -- a 30s read there occupies half the pool. The release
# lookup is ~5 KB, so it gets the same timeout=3 as its neighbours in utils.py. An archive is
# measured in hundreds of KB and capped at 8 MB, so it gets a short connect and a long read.
RELEASE_TIMEOUT = 3
ARCHIVE_TIMEOUT = (5, 30)

# A cached catalogue stops being installable once it is this old. The hourly refresh gates whether
# a *fetch* is attempted and only overwrites the value on success -- fail-soft, which is right for
# a star count and wrong for a supply-chain listing. 24h is 24 refresh attempts: a single failure
# never trips it, only a sustained outage does, and a sustained outage is exactly when nobody
# should be installing from a listing that cannot be confirmed.
#
# It is also what bounds the recorded-digest promise: a tag that moves under us is detected, and
# this is how long the window between listing and install is allowed to be.
CATALOG_MAX_AGE = timedelta(hours=24)

# Stricter than the API's own `^[\w.-]{4,64}\Z`: lowercase, must start alphanumeric, no dot at
# all. A catalogue id is a folder name from a release archive and is also used as a dict key, a
# DOM id, a template id and a path segment. `{3,63}` after the leading character gives a total
# length of 4..64, matching the API's floor. `\Z` and not `$`, for the same reason the API uses
# it: `$` matches before a trailing newline, and a trailing newline is attacker-influenced input
# reaching a path.
CATALOG_ID_RX = re_compile(r"^[a-z0-9][a-z0-9_-]{3,63}\Z")

# A release tag. Refused outright rather than escaped, because it is interpolated into the archive
# URL: no slash, no percent, nothing that could add a path segment. Real tags seen on these two
# repositories are `v1.11`, `1.10`, `0.6`, `dev`.
RELEASE_TAG_RX = re_compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")

SHA256_RX = re_compile(r"^[0-9a-f]{64}\Z")

# ── Host allowlist ──────────────────────────────────────────────────────────
#
# Without it this is an SSRF primitive: the UI container sits inside the compose network with
# bw-api, the scheduler, the database and the broker one hostname away. That -- reachability, not
# authenticity -- is what this list is for.
#
# The two hosts are the two this flow actually touches, and the chain was **measured**, not
# assumed (`curl -sSL -D -`, 2026-08-24):
#
#   https://api.github.com/repos/bunkerity/bunkerweb-plugins/tarball/v1.11
#     --302--> https://codeload.github.com/bunkerity/bunkerweb-plugins/legacy.tar.gz/refs/tags/v1.11
#     --200-->  205672 bytes, chunked (no Content-Length -- the capped read is load-bearing)
#
# One hop, and it lands on `codeload.github.com`. The `release-assets.` /
# `objects.githubusercontent.com` hops the previous manifest design allowlisted are the *release
# asset* download path; neither of these two repositories publishes the assets we need (the
# plugins repo's latest release has none at all), so this flow never goes near them and they are
# gone from the list. An allowlist entry for a host we never observe is attack surface bought
# with nothing.
#
# An earlier version of this file accepted any `.githubusercontent.com` host on the stated premise
# that the whole suffix is "GitHub-controlled". **That premise is false.** GitHub *operates* those
# hosts, but several of them serve bytes any user can write -- `gist.githubusercontent.com` (the
# raw content of anyone's gist) and `camo.githubusercontent.com` (proxied remote images). So the
# list is exact, and every entry additionally requires the repository path prefix: `codeload`
# serves the archive of *every* repository on GitHub, ours included, so the host alone would let a
# redirect swap in a stranger's repository without leaving the allowlist.
_ALLOWED = {
    "api.github.com": tuple(f"/repos/{repo}/" for repo in (PLUGINS_REPO, TEMPLATES_REPO)),
    "codeload.github.com": tuple(f"/{repo}/" for repo in (PLUGINS_REPO, TEMPLATES_REPO)),
}

_MAX_NAME = 64
_MAX_DESCRIPTION = 512
# Setting ids a listed plugin declares (C3 update preview). Real plugins declare a few dozen.
_MAX_SETTINGS = 500
_MAX_SETTING_ID = 256


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
    prefixes = _ALLOWED.get(host)
    if prefixes is None:
        return False

    # The path is traversal-checked; the query is NOT. codeload's redirect target is plain, but a
    # signed GitHub URL is almost entirely query string and legitimately carries %2F, %3B and %20
    # -- a query-scoped check would reject a redirect GitHub is entitled to hand us.
    #
    # Both the raw and the decoded form are checked, and a percent-escape that decodes into a new
    # path separator is refused outright: `%2f` is how `a%2f..%2fb` smuggles a segment past a
    # naive split.
    path = parts.path
    decoded = unquote(path)
    if ".." in path.split("/") or ".." in decoded.split("/"):
        return False
    if decoded.count("/") != path.count("/"):
        return False

    return any(path.startswith(prefix) for prefix in prefixes)


def release_url(repo: str) -> str:
    """The latest-release lookup for one pinned repository."""
    return f"https://api.github.com/repos/{repo}/releases/latest"


def archive_url(repo: str, tag: str) -> str:
    """The source-archive URL for one repository **at one pinned tag**.

    Derived, never taken from the release response. GitHub hands back a `tarball_url` and it is
    always exactly this, but deriving it means a response body cannot aim the next request: the
    only thing that crosses from the JSON into a URL is ``tag``, and ``parse_release`` has already
    forced that through ``RELEASE_TAG_RX``.

    Pinning matters at install time. Re-resolving "latest" there would let a release published in
    the seconds between listing and clicking install something the operator never saw.
    """
    return f"https://api.github.com/repos/{repo}/tarball/{tag}"


# ── The release lookup ──────────────────────────────────────────────────────


def parse_release(raw_bytes: Any) -> Tuple[Optional[str], List[str]]:
    """Pull the tag out of a ``/releases/latest`` body. Returns ``(tag, errors)``.

    Only one field is read, and it is re-validated: everything else GitHub sends is ignored
    rather than carried along, so there is nothing for an unexpected key to ride in on.
    """
    if not isinstance(raw_bytes, (bytes, bytearray)):
        return None, ["release response is not bytes"]
    if len(raw_bytes) > RELEASE_MAX:
        return None, [f"release response exceeds {RELEASE_MAX} bytes"]
    try:
        parsed = loads(bytes(raw_bytes).decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError, ValueError):
        return None, ["release response is not valid UTF-8 JSON"]
    if not isinstance(parsed, dict):
        return None, ["release response is not a JSON object"]

    # A draft is not published and a prerelease is not what an operator browsing a catalogue is
    # asking for. `/releases/latest` already excludes both, so this is a second reading of the
    # same fact -- cheap, and it means a change of behaviour on GitHub's side fails closed.
    if parsed.get("draft") or parsed.get("prerelease"):
        return None, ["the latest release is a draft or a prerelease"]

    tag = parsed.get("tag_name")
    if not isinstance(tag, str) or not RELEASE_TAG_RX.match(tag):
        return None, [f"invalid tag_name {tag!r}"]
    return tag, []


# ── Reading the archive ─────────────────────────────────────────────────────


def _safe_relpath(name: str, root: str) -> Optional[str]:
    """``name`` relative to the archive's single wrapper root, or None if it escapes it.

    Every member name in a GitHub source archive starts with one generated wrapper directory
    (``bunkerity-bunkerweb-plugins-fb55b84/``). This strips it and refuses anything that
    normalises out of it -- absolute paths, ``..`` segments, backslashes and NUL, none of which a
    real archive contains and all of which end up in a path if they are not refused here.
    """
    if not name or "\x00" in name or "\\" in name:
        return None
    if name.startswith("/"):
        return None
    normalised = normpath(name)
    # NOT defence in depth -- this is the only check that catches a whole input class, and an
    # earlier revision of this file wrongly claimed otherwise.
    #
    # The `startswith(prefix)` test below does subsume it *when the root is a normal directory
    # name*: `normpath("root/../../x")` is `"../x"`, which does not start with `"root/"`. But the
    # root is not a given, it is derived from the member names by `archive_root`, and an archive
    # whose members are all `../evil/...` has exactly ONE root -- `".."`. The prefix is then
    # `"../"`, `"../evil/plugin.json".startswith("../")` is True, and without this line the
    # function happily returns `evil/plugin.json` for a member that sits outside the archive root.
    if normalised.startswith("/") or normalised == ".." or normalised.startswith("../"):
        return None
    prefix = f"{root}/"
    if not normalised.startswith(prefix):
        return None
    return normalised.removeprefix(prefix) or None


def archive_root(names: List[str]) -> Optional[str]:
    """The single wrapper directory every member of a GitHub source archive sits under.

    None when there is not exactly one, which is not a shape GitHub produces -- so it is a signal
    that whatever was downloaded is not a source archive, and it stops here rather than in a loop
    that assumes the layout.
    """
    roots = {name.split("/", 1)[0] for name in names if name and not name.startswith("/")}
    roots.discard("")
    if len(roots) != 1:
        return None
    return roots.pop()


def _open_archive(payload: Any):
    """Open a downloaded source archive, or None when it is not one.

    The bytes are already capped in transfer; this only decides whether they are a gzipped tar at
    all. Nothing is extracted here.
    """
    if not isinstance(payload, (bytes, bytearray)) or not payload:
        return None
    try:
        return tar_open(fileobj=BytesIO(bytes(payload)), mode="r:*")
    except (TarError, EOFError, ValueError):
        return None


def _read_member(tar, member: TarInfo, cap: int) -> Optional[bytes]:
    """Read one regular file member, at most ``cap`` bytes, refusing anything that overruns.

    ``member.size`` is a header field, so it is a claim: it is used to refuse early, and the read
    is *still* capped at ``cap + 1`` and length-checked, so a lying header buys nothing.
    """
    if not member.isfile() or member.size > cap:
        return None
    handle = tar.extractfile(member)
    if handle is None:
        return None
    data = handle.read(cap + 1)
    return None if len(data) > cap else data


def archive_entries(payload: Any, kind: str) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Every catalogue item found in a release archive: ``{folder: parsed metadata}``.

    A folder is an item when, and only when, it carries the source's metadata file at its own top
    level and that file declares an ``id`` **equal to the folder name**. That equality is the
    identity check, and it is not a formality: the id the installer writes to the filesystem and
    the database is the one inside the metadata file, so a folder whose declared id differs is
    refused rather than silently installed under the other name.

    A rejected folder is dropped and recorded; it never fails the whole listing. One malformed
    folder must not be able to black out the catalogue -- that hands a single bad commit a denial
    of service over every other item.
    """
    errors: List[str] = []
    source = SOURCES.get(kind)
    if source is None:
        return {}, [f"unknown source {kind!r}"]

    tar = _open_archive(payload)
    if tar is None:
        return {}, ["the download is not a readable source archive"]

    with tar:
        try:
            members = tar.getmembers()
        except (TarError, EOFError, ValueError):
            return {}, ["the archive could not be listed"]

        names = [m.name for m in members]
        root = archive_root(names)
        if root is None:
            return {}, ["the archive does not have a single root directory"]

        # `<subdir>/<folder>/<member>` for templates, `<folder>/<member>` for plugins. Anything
        # deeper or shallower is not an item's metadata file and is skipped without comment --
        # both archives are full of ordinary repository files.
        subdir = source["subdir"]
        depth = 2 if subdir else 1
        wanted = source["member"]

        entries: Dict[str, Dict[str, Any]] = {}
        for member in members:
            relative = _safe_relpath(member.name, root)
            if relative is None:
                # Not a comment on the archive being hostile: `pax_global_header` and the root
                # entry itself both land here on every real GitHub archive.
                continue
            parts = relative.split("/")
            if len(parts) != depth + 1 or parts[-1] != wanted:
                continue
            if subdir and parts[0] != subdir:
                continue

            folder = parts[-2]
            if len(entries) >= MAX_ITEMS_PER_LIST:
                errors.append(f"more than {MAX_ITEMS_PER_LIST} items; the rest were ignored")
                break
            if not CATALOG_ID_RX.match(folder):
                errors.append(f"invalid folder name {folder!r}")
                continue
            if folder in entries:
                # Cannot happen in a real archive -- a filesystem cannot hold two folders with
                # one name -- but a hand-built tar can carry the member twice, and first-wins is
                # the deterministic answer.
                errors.append(f"duplicate folder {folder!r}, keeping the first")
                continue

            blob = _read_member(tar, member, MAX_MEMBER_JSON)
            if blob is None:
                errors.append(f"{folder}: {wanted} is missing or oversized")
                continue
            try:
                meta = loads(blob.decode("utf-8"))
            except (UnicodeDecodeError, JSONDecodeError, ValueError):
                errors.append(f"{folder}: {wanted} is not valid UTF-8 JSON")
                continue
            if not isinstance(meta, dict):
                errors.append(f"{folder}: {wanted} is not a JSON object")
                continue

            declared = meta.get("id")
            if declared != folder:
                # THE identity check. See the docstring: the declared id, not the folder name, is
                # what reaches the filesystem.
                errors.append(f"{folder}: {wanted} declares id {declared!r}")
                continue

            entries[folder] = meta

    return entries, errors


# ── The version gate ────────────────────────────────────────────────────────
#
# There is no `bw_min` to read. The nine real `plugin.json` files in `bunkerweb-plugins` v1.11
# carry exactly `description, id, name, settings, stream, version` (plus `jobs` on cloudflare),
# and the ten `template.json` files in `bunkerweb-templates` 0.6 carry `id, name, settings, steps`
# and an optional `configs` -- no compatibility field of any kind, and `version` is the *plugins
# repo's own release number* ("1.11"), not a BunkerWeb version.
#
# What the plugins repository does publish is `COMPATIBILITY.json` at its archive root: a map from
# its own release line to the list of BunkerWeb versions that line supports. That file rides
# inside the same archive we already downloaded and already trust, so it is the compatibility
# source, keyed by each plugin's `version`.
#
# How the list is read is a PO decision (2026-09-25), replacing the fail-closed exact match that
# left every card incompatible on 1.7 because upstream never listed a 1.7.x: "if not provided or
# specifically stated, it's compatible, if the semver is superior". So a release line with no
# entry declares nothing to refuse on, and a line with an entry is read as "these versions and
# anything after them". The trust root is unchanged by this -- the pinned repositories plus the
# archive digest; this only decides which verified items the button is offered for.
COMPATIBILITY_MEMBER = "COMPATIBILITY.json"
_MAX_COMPAT_LINES = 200
_MAX_COMPAT_VERSIONS = 200


def _valid_version(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        Version(normalize_bunkerweb_version(value))
    except (InvalidVersion, TypeError):
        return False
    return True


def parse_compatibility(blob: Any) -> Dict[str, List[str]]:
    """``COMPATIBILITY.json`` as ``{release line: [BunkerWeb versions]}``.

    Every key and every entry is re-typed and re-validated; an unusable line is dropped rather
    than failing the file, and an unusable file is an empty map -- which, under the PO rule the
    gate below implements, means no line declares anything and every item reads as compatible.
    """
    if not isinstance(blob, (bytes, bytearray)):
        return {}
    try:
        parsed = loads(bytes(blob).decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}

    out: Dict[str, List[str]] = {}
    for line, versions in list(parsed.items())[:_MAX_COMPAT_LINES]:
        if not isinstance(line, str) or not isinstance(versions, list):
            continue
        good = [v for v in versions[:_MAX_COMPAT_VERSIONS] if _valid_version(v)]
        if good:
            out[line.strip()] = good
    return out


def is_compatible(bw_version: Any, supported: Any) -> bool:
    """Whether an item whose release line supports ``supported`` may be installed here.

    The PO rule (2026-09-25):

    * ``supported`` is ``None`` or ``[]`` -- the release line has no entry -- so the item is
      compatible;
    * otherwise it is compatible when the running version is listed, or is strictly greater than
      every listed version (``1.7.0~alpha`` is greater than ``1.6.16``: pre-releases compare as
      ``packaging`` orders them);
    * anything else is incompatible, and so is an entry that is present but carries no
      parseable version, or is not a list at all -- that is not "no entry".

    An unparseable running version is refused whatever the entry says. That is deliberately the
    opposite stance to ``is_newer_version_available``, whose docstring prefers a false negative:
    there a parse failure costs a missed notification, here it costs running an unvetted plugin
    as code in the UI process, in the worker and in nginx.

    Comparison is on normalised ``Version`` objects, not on strings: "v1.6.10" and "1.6.10" are
    one version, "1.10.0" is greater than "1.9.0", and a string compare gets both wrong.
    """
    if not _valid_version(bw_version):
        return False
    if supported is None:
        supported = []
    if not isinstance(supported, list):
        return False
    if not supported:
        return True
    current = Version(normalize_bunkerweb_version(bw_version))
    listed = [Version(normalize_bunkerweb_version(candidate)) for candidate in supported if _valid_version(candidate)]
    return bool(listed) and (current in listed or all(current > version for version in listed))


def supported_versions(meta: Dict[str, Any], compatibility: Dict[str, List[str]]) -> List[str]:
    """The BunkerWeb versions one item declares support for, or ``[]`` when it declares none.

    ``[]`` means the item's release line has no ``COMPATIBILITY.json`` entry (or the item has no
    ``version`` to look one up by), which the gate above reads as compatible. The templates
    repository has no compatibility data at all, so every template gets ``[]``.
    """
    line = meta.get("version")
    if not isinstance(line, str):
        return []
    return list(compatibility.get(line.strip(), ()))


def item_compatible(kind: str, bw_version: Any, item: Any) -> bool:
    """Whether one catalogue item may be installed here. **The only place that decides.**

    The listing, the plugin install route and the template install route all call this, so the
    button an operator sees and the gate the server enforces cannot drift apart. That sentence was
    once aspirational: `routes/templates.py` documented the promise without ever calling this
    function, so flipping the flag below would have hidden the button and left the JSON endpoint
    installing anyway. Both routes call it now. If a third caller ever renders `compatible`
    without consulting this, the claim is false again.

    It splits by source because the two repositories are genuinely different, not to be lenient:

    * **plugins** are gated on `COMPATIBILITY.json` through ``is_compatible``: no entry for the
      item's release line, a listed running version, or a running version newer than every listed
      one is compatible (PO decision, 2026-09-25). An item that is not a dict at all is refused.

    * **templates** declare nothing to gate on -- no version field, no compatibility file, nothing
      -- so there is no bound to check and inventing one would assert a compatibility the
      publisher never stated. They are not ungated: `create_template` validates every setting id
      in the payload against the live `Settings` table and refuses with `Unknown settings: ...`,
      which is a *structural* compatibility check against this exact build and is strictly more
      informative than a declared version range would have been.

    To gate templates too, flip `version_gate` in `SOURCES` -- nothing else changes, and
    `test_flipping_the_flag_makes_the_TEMPLATE_ROUTE_refuse` is what keeps that true: it flips the
    flag and asserts the *route* refuses, because a test that only compares the flag's value stays
    green through exactly the drift this promise is about.
    """
    if not SOURCES.get(kind, {}).get("version_gate"):
        return True
    if not isinstance(item, dict):
        return False
    return is_compatible(bw_version, item.get("supported"))


# ── Building the listing ────────────────────────────────────────────────────


def _text(value: Any, limit: int) -> str:
    """One display string, clipped rather than dropped.

    A description that ran long is a cosmetic problem; dropping the item over it would hide a
    plugin for a typo. The id and the identity check are where strictness belongs.
    """
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def item_homepage(kind: str, folder: str) -> str:
    """The upstream page for one item.

    Built here from two things that are already trusted -- a repository constant and a folder name
    that passed ``CATALOG_ID_RX`` -- rather than read from the metadata. It becomes an ``href``,
    and a link taken from a JSON file in a downloaded archive is a link an upstream commit gets to
    choose. This one it does not.

    ``github.com`` is deliberately not in the request allowlist: we never fetch this URL, we only
    render it.
    """
    parts = [SOURCES[kind]["repo"], "tree/main", SOURCES[kind]["subdir"], folder]
    return "https://github.com/" + "/".join(part for part in parts if part)


def build_items(kind: str, entries: Dict[str, Dict[str, Any]], compatibility: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """Turn enumerated archive folders into the catalogue rows the UI and the install routes read.

    Every row is built fresh, field by field. The parsed metadata object is never stored or
    forwarded, so an unknown key in an upstream ``plugin.json`` -- and they are full of keys we do
    not model, ``settings`` and ``jobs`` among them -- cannot ride into DATA, into a template, or
    into an install.
    """
    items = []
    for folder in sorted(entries):
        meta = entries[folder]
        item = {
            "id": folder,
            "name": _text(meta.get("name"), _MAX_NAME) or folder,
            "description": _text(meta.get("description"), _MAX_DESCRIPTION),
            "version": _text(meta.get("version"), 32),
            "supported": supported_versions(meta, compatibility),
            "homepage": item_homepage(kind, folder),
        }
        if kind == "plugins":
            # The setting IDS, never their specs: the update preview lists what the new version
            # drops, and the DB prunes those settings with every value set for them. The archive
            # is digest-pinned, so this list is exactly what an update would install.
            settings = meta.get("settings") if isinstance(meta.get("settings"), dict) else {}
            item["settings"] = sorted(k for k in settings if isinstance(k, str) and len(k) <= _MAX_SETTING_ID)[:_MAX_SETTINGS]
        items.append(item)
    return items


# ── Freshness ───────────────────────────────────────────────────────────────


def catalog_age(fetched_at: Any) -> Optional[timedelta]:
    """Age of a cached catalogue, or None when the stamp is missing or unreadable."""
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
    """Whether a cached catalogue is too old to install from.

    An unreadable or absent stamp counts as stale: we cannot show that the listing is fresh, so we
    do not act on it.

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
    must not be able to buy an unbounded read. The archive responses measured on 2026-08-24 are
    chunked and carry no Content-Length at all, so there is nothing here to consult even if we
    wanted to.
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


class GitHubRefused(ValueError):
    """GitHub answered and refused (403/429): in practice the unauthenticated rate limit, 60
    requests an hour per IP address, which every stack behind one shared IP spends together."""


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
        # Every exit below can raise -- an off-allowlist redirect, a non-200, an over-cap body, or
        # a mid-stream network error inside `_read_capped` -- and a hand-rolled close() is skipped
        # on the last of those, leaking a connection per failed download.
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
            if response.status_code in (403, 429):
                raise GitHubRefused(f"unexpected status {response.status_code}")
            if response.status_code != 200:
                raise ValueError(f"unexpected status {response.status_code}")
            data = _read_capped(response, cap)
            if data is None:
                raise ValueError(f"response exceeds {cap} bytes")
            return data
    raise ValueError("too many redirects")


def fetch_archive(repo: str, tag: str) -> bytes:
    """Download one repository's source archive at one pinned tag.

    Raises ValueError on policy failure, RequestException on network failure.
    """
    if not RELEASE_TAG_RX.match(tag or ""):  # noqa: FURB143 - keep None input on the ValueError path
        raise ValueError(f"invalid tag {tag!r}")
    return _get_allowlisted(archive_url(repo, tag), timeout=ARCHIVE_TIMEOUT, cap=ARCHIVE_MAX)


def fetch_source(kind: str) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Resolve, download and enumerate one source. Returns ``(section, errors)``.

    ``section`` is what gets cached for that half of the catalogue::

        {"tag": "v1.11", "sha256": "<archive digest>", "items": [...]}

    The digest is the archive we just read, recorded so the install can prove it is installing the
    bytes that were listed. See the module docstring on why a tag is not enough on its own.
    """
    source = SOURCES[kind]
    repo = source["repo"]

    raw = _get_allowlisted(release_url(repo), timeout=RELEASE_TIMEOUT, cap=RELEASE_MAX)
    tag, errors = parse_release(raw)
    if tag is None:
        return None, errors

    payload = fetch_archive(repo, tag)

    # The plugins repository publishes its compatibility map at its own archive root, so it is
    # read out of the very bytes being enumerated -- not fetched separately, where it could be a
    # different commit than the plugins it describes.
    compatibility = parse_compatibility(archive_file(payload, COMPATIBILITY_MEMBER))

    entries, entry_errors = archive_entries(payload, kind)
    if not entries:
        return None, errors + entry_errors + [f"{repo}@{tag} contains no {kind}"]

    items = build_items(kind, entries, compatibility)
    if kind == "templates":
        # A template has no version, so its update state is a content comparison (C4). The
        # fingerprint is read out of these same bytes, so it describes exactly what an update
        # installs. A template that does not assemble gets none and the card offers no update.
        for item in items:
            item["fingerprint"] = template_fingerprint(template_payload(payload, item["id"])[0])

    return {
        "tag": tag,
        "sha256": bytes_hash(payload, algorithm="sha256"),
        "items": items,
    }, errors + entry_errors


def fetch_catalog() -> Optional[Dict[str, Any]]:
    """Fetch and validate both halves. Returns the value to store, or None to keep the old one.

    Shape stored in ``DATA["PLUGIN_CATALOG"]``::

        {"fetched_at": <ISO>, "catalog": {"plugins": {...}, "templates": {...}}}

    The stamp is what the freshness gate reads; without it a catalogue nobody has been able to
    refresh would stay installable indefinitely.

    A half that fails is DROPPED, not carried over: the dict is rebuilt from scratch each run, so
    a templates failure stores a value with no templates section and the previously cached one
    goes away. That is deliberate and it is the same stance as the staleness gate -- a listing we
    could not confirm this hour stops being installable -- but it is the opposite of what an
    earlier version of this docstring claimed. The two halves are independent only in that one
    failing does not stop the *other* from being refreshed; if both fail there is nothing to store
    and the whole previous value is kept.
    """
    if not catalog_enabled():
        return None

    catalog: Dict[str, Any] = {}
    refused: List[str] = []
    for kind in SOURCES:
        try:
            section, _ = fetch_source(kind)
        except GitHubRefused as e:
            refused.append(f"{SOURCES[kind]['repo']} ({e})")
            continue
        except (ValueError, RequestException):
            continue
        if section is not None:
            catalog[kind] = section

    # Everything else stays silent (an air-gapped install never reaches GitHub, and an hourly
    # warning about that is noise about a deployment choice). A refusal is different: GitHub is
    # reachable and said no, the catalogue stays empty or ages towards the staleness gate, and on
    # a shared IP that lasts hours. One line per refresh, no retry: retrying spends the same
    # exhausted budget.
    if refused:
        LOGGER.warning(
            f"GitHub refused the community catalogue refresh for {', '.join(refused)}; keeping the cached listing. "
            "Unauthenticated GitHub requests share a rate limit per IP address, so this clears on its own."
        )

    if not catalog:
        return None
    return {"fetched_at": datetime.now().astimezone().isoformat(), "catalog": catalog}


# ── The digest gate ─────────────────────────────────────────────────────────


def verify_digest(payload: Any, expected: Any) -> bool:
    """Whether ``payload`` hashes to ``expected``.

    ``compare_digest`` rather than ``==``: the timing channel is not a realistic attack on a
    recorded hash, but an equality check on a security decision is exactly the line a reviewer
    should not have to think about twice.

    What this proves and what it does not: ``expected`` is the digest of the archive **we
    enumerated**, not a digest anyone published, so this is not an authenticity check. It is the
    check that the bytes about to be installed are the bytes that were listed -- which is exactly
    the gap a moved git tag opens, and the only integrity claim this design can honestly make.
    """
    if not isinstance(payload, (bytes, bytearray)) or not isinstance(expected, str) or not SHA256_RX.match(expected):
        return False
    return compare_digest(bytes_hash(bytes(payload), algorithm="sha256"), expected)


# ── Pulling one item out of the archive ─────────────────────────────────────


def archive_file(payload: Any, relative: str) -> Optional[bytes]:
    """One file's bytes, addressed relative to the archive's wrapper root.

    Returns None when it is absent, is not a regular file, or is over ``MEMBER_MAX``. Used for
    ``COMPATIBILITY.json`` and for a template's config blobs -- never to write anything to disk.
    """
    tar = _open_archive(payload)
    if tar is None:
        return None
    with tar:
        try:
            members = tar.getmembers()
        except (TarError, EOFError, ValueError):
            return None
        root = archive_root([m.name for m in members])
        if root is None:
            return None
        for member in members:
            if _safe_relpath(member.name, root) == relative:
                try:
                    return _read_member(tar, member, MEMBER_MAX)
                except (TarError, EOFError, ValueError):
                    return None
    return None


def repack_plugin(payload: Any, plugin_id: str) -> Tuple[Optional[bytes], Optional[str]]:
    """A fresh ``.tar.gz`` holding exactly the one plugin folder. ``(bytes, error)``.

    This is the structural half of the identity guarantee, and it is why there is no
    "does the archive contain exactly one plugin" check any more: the upstream archive contains
    nine, and **it is never handed to the installer**. Both install branches in
    ``routers/plugins.py`` loop over every ``plugin.json`` they can find (:333, :389), so passing
    the release archive through would install all nine on one click, none of them the one that was
    clicked. What the installer receives is a tarball this function builds, and the only thing in
    it is ``<plugin_id>/...``.

    Three bounds, all of them on data an upstream commit controls:

    * every member is re-checked against the wrapper root, so nothing outside the folder is copied
      and no ``..`` survives into a name;
    * members are rewritten as ``<plugin_id>/<rest>`` -- the archive we emit cannot carry a path
      the id does not prefix, whatever the source called it;
    * the running total is capped at ``EXTRACT_MAX`` and each member at ``MEMBER_MAX``, because
      the 8 MB transfer cap bounds *compressed* bytes and gzip amplifies.

    Symlinks, hardlinks, devices and anything else that is not a regular file or a directory are
    dropped rather than copied. A plugin has no business shipping one, and a symlink is how an
    archive reaches a path its member names never mention.
    """
    if not CATALOG_ID_RX.match(plugin_id or ""):  # noqa: FURB143 - keep None input on the error-return path
        return None, f"invalid plugin id {plugin_id!r}"

    tar = _open_archive(payload)
    if tar is None:
        return None, "the download is not a readable source archive"

    out = BytesIO()
    copied = 0
    total = 0
    with tar:
        try:
            members = tar.getmembers()
        except (TarError, EOFError, ValueError):
            return None, "the archive could not be listed"
        root = archive_root([m.name for m in members])
        if root is None:
            return None, "the archive does not have a single root directory"

        prefix = f"{plugin_id}/"
        with tar_open(fileobj=out, mode="w:gz") as dest:
            for member in members:
                relative = _safe_relpath(member.name, root)
                if relative is None or not relative.startswith(prefix):
                    continue
                if not (member.isfile() or member.isdir()):
                    continue
                if member.isdir():
                    info = TarInfo(name=relative)
                    info.type = member.type
                    info.mode = 0o755
                    # Member metadata is rebuilt rather than copied: uid/gid/uname/gname and
                    # mtime all come from whoever cut the release, none of them mean anything
                    # here, and every one of them lands in the tar the API extracts.
                    info.mtime = 0
                    dest.addfile(info)
                    continue
                blob = _read_member(tar, member, MEMBER_MAX)
                if blob is None:
                    return None, f"{relative} is missing or larger than {MEMBER_MAX} bytes"
                total += len(blob)
                if total > EXTRACT_MAX:
                    return None, f"{plugin_id} expands past {EXTRACT_MAX} bytes"
                info = TarInfo(name=relative)
                info.size = len(blob)
                # The executable bit is the only permission worth carrying: a plugin's `jobs/`
                # scripts need it and everything else is noise an upstream commit gets to choose.
                info.mode = 0o755 if member.mode & 0o111 else 0o644
                info.mtime = 0
                dest.addfile(info, BytesIO(blob))
                copied += 1

    if not copied:
        return None, f"the archive contains no folder named {plugin_id}"
    return out.getvalue(), None


def template_payload(payload: Any, template_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """One catalogue template, assembled from its folder, ready for ``create_template``. ``(data, error)``.

    A thin wrapper: the parser is ``template_package.template_from_folder``, shared with template
    import and the scheduler's URL installs, so the catalogue and those paths cannot disagree on
    what a template folder is. What stays here is what only the catalogue knows -- its stricter
    id rule (``CATALOG_ID_RX``: the id is also a DOM id and a dict key here) and where its
    folders sit in the release archive. Every file is read through ``archive_file``, which
    re-derives each member relative to the wrapper root and caps it at ``MEMBER_MAX``, so a
    reference cannot address a file outside its own template's folder.
    """
    if not CATALOG_ID_RX.match(template_id or ""):  # noqa: FURB143 - keep None input on the error-return path
        return None, f"invalid template id {template_id!r}"

    base = f"{SOURCES['templates']['subdir']}/{template_id}"
    return template_from_folder(lambda relative: archive_file(payload, f"{base}/{relative}"), template_id)


# ── Reading the cache ───────────────────────────────────────────────────────


def read_cached(data: Any) -> Tuple[Dict[str, Dict[str, Any]], Optional[str]]:
    """Pull the catalogue out of ``DATA``. Returns ``(catalog, fetched_at)``.

    Tolerates every shape a crafted or truncated ``ui_data.json`` could hold -- it is a file on
    disk that other processes write, so it is parsed defensively rather than trusted.
    """
    empty: Dict[str, Dict[str, Any]] = {kind: {"tag": "", "sha256": "", "items": []} for kind in SOURCES}
    if not isinstance(data, dict):
        return empty, None
    catalog = data.get("catalog")
    if not isinstance(catalog, dict):
        return empty, None

    out: Dict[str, Dict[str, Any]] = {}
    for kind in SOURCES:
        section = catalog.get(kind)
        if not isinstance(section, dict):
            out[kind] = empty[kind]
            continue
        tag = section.get("tag")
        sha = section.get("sha256")
        out[kind] = {
            "tag": tag if isinstance(tag, str) and RELEASE_TAG_RX.match(tag or "") else "",
            "sha256": sha if isinstance(sha, str) and SHA256_RX.match(sha or "") else "",
            "items": [i for i in (section.get("items") or []) if isinstance(i, dict)],
        }

    fetched_at = data.get("fetched_at")
    return out, (fetched_at if isinstance(fetched_at, str) else None)


def collides_with_installed(item_id: str, installed: Dict[str, Any]) -> bool:
    """Whether ``item_id`` is already taken by an installed plugin **of any type**.

    Stricter than the API's own check, which builds its ``existing_ids`` from
    ``get_plugins(_type="ui")`` only and is therefore blind to core, external and pro ids. The DB
    layer does refuse to overwrite a core row, but it refuses *silently* -- the router still
    reports the id as created -- so an operator would be told an install succeeded when nothing
    happened. Exact match: ids are lowercase by construction (CATALOG_ID_RX).
    """
    return item_id in installed


def replaceable(row: Any) -> bool:
    """Whether an installed plugin row is one the catalogue may update or remove.

    Only a ``ui`` type installed by the ``ui`` method: that is what a catalogue install writes, and
    it is the only row the API's ``replace`` flag accepts. Core and pro rows belong to the image
    and the licence; an ``external`` row belongs to ``EXTERNAL_PLUGIN_URLS`` or to a mounted
    folder, whose next run would put its own copy back over ours. There is no provenance column
    (design Q1), so a hand-uploaded ``ui`` plugin with a catalogue id counts as the catalogue item;
    the update confirmation names the replaced plugin and version for exactly that case (Q2).
    """
    return isinstance(row, dict) and row.get("type") == row.get("method") == "ui"


def plugin_state(item: Dict[str, Any], row: Any) -> Dict[str, Any]:
    """The C3 state of one plugin card, from its catalogue item and its installed row (or None).

    ``available`` (not installed), ``installed`` (same version), ``update`` (another version) or
    ``managed`` (installed some other way; the card offers nothing). ``removed_settings`` is the
    update preview: the ids the installed plugin has and the listed version drops, or None when
    either side is unknown -- an installed row read without its settings, or a listing cached
    before setting ids were recorded. Never ``[]`` for "unknown": ``[]`` tells the operator that
    nothing will be deleted.
    """
    state: Dict[str, Any] = {"state": "available", "installed_version": "", "installed_type": "", "removed_settings": None}
    if row is None:
        return state
    row = row if isinstance(row, dict) else {}
    state |= {"installed_version": _text(row.get("version"), 32), "installed_type": _text(row.get("type"), 16)}
    if not replaceable(row):
        return state | {"state": "managed"}
    if state["installed_version"] == item.get("version"):
        return state | {"state": "installed"}
    listed, current = item.get("settings"), row.get("settings")
    if isinstance(listed, list) and isinstance(current, dict):
        state["removed_settings"] = sorted(set(current) - set(listed))
    return state | {"state": "update"}


# A catalogue template's fingerprint is cached with the listing, so it is bounded. Real ones are a
# few KB (the v0.7 release's largest settings block is netbird's 49 settings).
FINGERPRINT_MAX = 64 * 1024


def _config_ref(reference: str) -> str:
    """``modsec-crs/x.conf`` and ``modsec_crs/x.conf`` are one config: the DB stores the type with ``_``."""
    config_type, _, name = reference.partition("/")
    return f"{config_type.replace('-', '_').lower()}/{name}"


def template_fingerprint(data: Any) -> Optional[Dict[str, Any]]:
    """What an update of one template compares, or None when ``data`` is not a template.

    ``data`` is a template in either shape the UI sees: ``create_template``'s input (configs as
    ``{type, name, data}`` objects -- ``template_payload`` and packages) or a row of
    ``get_templates()`` (configs as ``{"type/name.conf": data}``). Both reduce to the same form:
    the DB's spelling of every config reference, stripped titles, and each config's **digest**
    rather than its text, so the cached listing stays small and never holds NGINX configuration.
    Setting values are kept as given; ``template_diff`` canonicalises them.
    """
    try:
        configs = data["configs"]
        if isinstance(configs, list):
            configs = {f"{config['type']}/{config['name']}.conf": config["data"] for config in configs}
        fingerprint = {
            "name": str(data["name"]).strip(),
            "settings": {str(key).strip(): "" if value is None else str(value) for key, value in data["settings"].items()},
            "steps": [
                [
                    str(step.get("title", "")).strip(),
                    str(step.get("subtitle") or "").strip(),
                    [str(setting).strip() for setting in step.get("settings") or []],
                    # Display order only: the DB returns a step's configs in the template's config order.
                    sorted(_config_ref(str(reference)) for reference in step.get("configs") or []),
                ]
                for step in data["steps"]
            ],
            "configs": {_config_ref(str(reference)): bytes_hash(str(text).encode("utf-8"), algorithm="sha256") for reference, text in configs.items()},
        }
    except (TypeError, KeyError, AttributeError):
        return None
    return fingerprint if len(dumps(fingerprint)) <= FINGERPRINT_MAX else None


def template_diff(listed: Any, installed: Any, canon: Optional[Callable[[str, str], str]] = None) -> Dict[str, List[Any]]:
    """What updating the installed template to the listed one changes, part by part; ``{}`` for nothing.

    ``canon(key, value)`` puts a setting value in the form the DB stores it (``20M`` -> ``20m``):
    the installed side is already canonical and the catalogue side is not, so comparing raw values
    would show every catalogue template that uses a non-canonical spelling as changed forever.
    Steps are compared by position, the way the editor shows them; a changed step is named by its
    new title. Raises on a malformed fingerprint -- the caller treats that as "unknown".
    """
    fold = canon or (lambda _key, value: value)
    new = {key: fold(key, value) for key, value in listed["settings"].items()}
    old = {key: fold(key, value) for key, value in installed["settings"].items()}
    new_steps, old_steps = listed["steps"], installed["steps"]
    new_configs, old_configs = listed["configs"], installed["configs"]
    diff = {
        "name": [installed["name"], listed["name"]] if installed["name"] != listed["name"] else [],
        "settings_added": [[key, new[key]] for key in sorted(new.keys() - old.keys())],
        "settings_changed": [[key, old[key], new[key]] for key in sorted(new.keys() & old.keys()) if new[key] != old[key]],
        "settings_removed": [[key, old[key]] for key in sorted(old.keys() - new.keys())],
        "steps_added": [step[0] for step in new_steps[len(old_steps) :]],
        "steps_changed": [new_step[0] for new_step, old_step in zip(new_steps, old_steps) if new_step != old_step],
        "steps_removed": [step[0] for step in old_steps[len(new_steps) :]],
        "configs_added": sorted(new_configs.keys() - old_configs.keys()),
        "configs_changed": sorted(key for key in new_configs.keys() & old_configs.keys() if new_configs[key] != old_configs[key]),
        "configs_removed": sorted(old_configs.keys() - new_configs.keys()),
    }
    return {part: changes for part, changes in diff.items() if changes}


def update_token(listed: Any, installed: Any) -> str:
    """Names the exact pair of templates a diff preview showed.

    The update route rebuilds both fingerprints from a freshly verified download and the live
    installed row, and refuses unless this matches what the confirmation carried: a listing that
    moved or a template edited after the preview is never replaced unseen.
    """
    return bytes_hash(dumps([listed, installed], sort_keys=True).encode("utf-8"), algorithm="sha256")


def template_state(item: Dict[str, Any], row: Any, canon: Optional[Callable[[str, str], str]] = None) -> Dict[str, Any]:
    """The C4 state of one template card, from its catalogue item and its installed row (or None).

    ``available`` (not installed), ``installed`` (same content), ``update`` (the content differs;
    ``diff`` and ``confirm`` carry the preview) or ``managed`` (a plugin owns it or another method
    wrote it: the API refuses to replace it, so the card offers nothing). ``diff`` is None when the
    comparison is impossible -- a listing cached before fingerprints existed, or a tampered one --
    and never ``{}`` for that: ``{}`` tells the operator the template matches the catalogue.
    """
    state: Dict[str, Any] = {"state": "available", "managed_by": "", "diff": None, "confirm": ""}
    if row is None:
        return state
    row = row if isinstance(row, dict) else {}
    if row.get("plugin_id") or row.get("method") != "ui":
        return state | {"state": "managed", "managed_by": _text(row.get("plugin_id") or row.get("method") or "unknown", 64)}
    listed, installed = item.get("fingerprint"), template_fingerprint(row)
    try:
        diff = template_diff(listed, installed, canon)
    except (TypeError, KeyError, AttributeError, ValueError):
        return state | {"state": "installed"}
    if not diff:
        return state | {"state": "installed", "diff": diff}
    return state | {"state": "update", "diff": diff, "confirm": update_token(listed, installed)}


def build_catalog_view(kind: str, cached: Any, installed_ids: Any, bw_version: str, canon: Optional[Callable[[str, str], str]] = None) -> Dict[str, Any]:
    """The template context a catalogue section needs: its items, their state, and staleness.

    Pure: the caller does the I/O and passes the results in. That is not purity for its own sake --
    it keeps this out of the route modules, so neither route has to import the other, and it makes
    the listing logic testable without a Flask app.

    Installed items are kept and carry a state, because the card is where update and remove live:
    ``plugin_state`` (C3) with ``installed_ids`` = ``BW_CONFIG.get_plugins()``, or
    ``template_state`` (C4) with ``installed_ids`` = ``API_CLIENT.get_templates()`` and ``canon``
    for its setting values; both are id -> row. Incompatible items are kept and marked
    instead -- hiding them makes the catalogue look empty and generates support tickets, while
    showing the reason makes the constraint explain itself.

    Everything here decides what is *drawn*. Every one of these checks is made again, server-side,
    in the install route: a disabled button is a hint, never a control.
    """
    if not catalog_enabled():
        return {"catalog_items": [], "catalog_available": False, "catalog_stale": False, "catalog_tag": ""}

    catalog, fetched_at = read_cached(cached)
    section = catalog.get(kind) or {}
    items = section.get("items") or []
    if not items:
        return {"catalog_items": [], "catalog_available": False, "catalog_stale": False, "catalog_tag": ""}

    rows = installed_ids if isinstance(installed_ids, dict) else dict.fromkeys(installed_ids or (), {})
    view = []
    for item in items:
        row = rows[item.get("id")] if item.get("id") in rows else None
        state = plugin_state(item, row) if kind == "plugins" else template_state(item, row, canon)
        view.append(item | state | {"compatible": item_compatible(kind, bw_version, item), "bw_version": bw_version})
    return {
        "catalog_items": view,
        "catalog_available": True,
        "catalog_stale": is_stale(fetched_at),
        "catalog_tag": section.get("tag") or "",
    }


def find_item(data: Any, kind: str, item_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Look one item up in the cached catalogue. Returns ``(item, section)``.

    The install routes resolve everything -- the repository, the pinned tag, the recorded digest,
    the compatibility list -- through here and take nothing but the id from the request. A
    client-supplied URL, tag or hash would hand the browser exactly the power a pinned source
    exists to remove.
    """
    catalog, _ = read_cached(data)
    section = catalog.get(kind) or {}
    for item in section.get("items") or []:
        if item.get("id") == item_id:
            return item, section
    return None, None
