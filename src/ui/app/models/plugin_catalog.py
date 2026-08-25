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
      -> version gate               fails CLOSED
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
from json import JSONDecodeError, loads
from os import getenv
from posixpath import normpath
from re import compile as re_compile
from tarfile import TarError, TarInfo, open as tar_open
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit

from packaging.version import InvalidVersion, Version
from requests import get
from requests.exceptions import RequestException

from common_utils import bytes_hash, normalize_bunkerweb_version  # type: ignore

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
# It is read as a membership list rather than a range because that is what it is -- an explicit
# enumeration of versions, not bounds -- and inventing a range from it would claim a compatibility
# the publisher never stated.
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
    than failing the file, and an unusable file is an empty map -- which, given the gate below
    fails closed, means nothing installs. That is the correct direction to fail in.
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

    Fails CLOSED on everything: an empty or absent list, an unparseable running version, an
    unparseable entry. Deliberately the opposite stance to ``is_newer_version_available``, whose
    docstring prefers a false negative. There a parse failure costs a missed notification; here it
    costs running an unvetted plugin as code in the UI process, in the worker and in nginx.

    Comparison is on normalised ``Version`` objects, not on strings: "1.6.10" and "1.6.10" can be
    spelled differently ("v1.6.10", "1.6.10-rc1" is a different version and must stay different),
    and a string compare would both miss real matches and accept near-misses.
    """
    # No `not supported` short-circuit: an empty list already falls out of the loop below as
    # False. A guard that cannot change an outcome only looks like one.
    if not isinstance(supported, list) or not _valid_version(bw_version):
        return False
    current = Version(normalize_bunkerweb_version(bw_version))
    for candidate in supported:
        if _valid_version(candidate) and Version(normalize_bunkerweb_version(candidate)) == current:
            return True
    return False


def supported_versions(meta: Dict[str, Any], compatibility: Dict[str, List[str]]) -> List[str]:
    """The BunkerWeb versions one item declares support for, or ``[]`` when it declares none.

    ``[]`` is the honest answer for every item in the catalogue as it stands today: the plugins
    repository has published v1.9, v1.10 and v1.11 without adding a `COMPATIBILITY.json` line for
    any of them, and the templates repository has no compatibility data at all. The gate above
    then refuses, the card says why, and the moment upstream adds the line the catalogue lights up
    with no change here.
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

    * **plugins** are gated on `COMPATIBILITY.json`, and it fails closed. Today that refuses every
      plugin, because the plugins repository has shipped v1.9, v1.10 and v1.11 without adding a
      line for any of them and no line anywhere names a 1.7.x. That is upstream's statement to
      make, and the card says so rather than the page going quietly blank. The moment the line
      lands, the catalogue lights up with no change here.

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
    return is_compatible(bw_version, (item or {}).get("supported") if isinstance(item, dict) else None)


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
    return [
        {
            "id": folder,
            "name": _text(entries[folder].get("name"), _MAX_NAME) or folder,
            "description": _text(entries[folder].get("description"), _MAX_DESCRIPTION),
            "version": _text(entries[folder].get("version"), 32),
            "supported": supported_versions(entries[folder], compatibility),
            "homepage": item_homepage(kind, folder),
        }
        for folder in sorted(entries)
    ]


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
    if not RELEASE_TAG_RX.match(tag or ""):
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

    return {
        "tag": tag,
        "sha256": bytes_hash(payload, algorithm="sha256"),
        "items": build_items(kind, entries, compatibility),
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
    for kind in SOURCES:
        try:
            section, _ = fetch_source(kind)
        except (ValueError, RequestException):
            continue
        if section is not None:
            catalog[kind] = section

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
    if not CATALOG_ID_RX.match(plugin_id or ""):
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


# Config references inside a template: `<type>/<name>.conf`, where `<type>` is one of BunkerWeb's
# custom-config types. Anchored, one separator, no dots in either half beyond the extension --
# because this string is joined onto a path to read the blob out of the archive, and it is also
# what `_prepare_template_entities` splits back into a type and a name.
TEMPLATE_CONFIG_RX = re_compile(r"^[a-z][a-z0-9-]{0,31}/[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.conf\Z")

MAX_TEMPLATE_CONFIGS = 32


def template_payload(payload: Any, template_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """One template, assembled from its folder, ready for ``create_template``. ``(data, error)``.

    The manifest design could hand `create_template` the downloaded JSON as-is, because a manifest
    artifact was one self-contained blob. A repository is not shaped that way and this is the one
    place the re-scope needs genuinely new code: upstream splits a template across
    ``template.json`` and sibling files, and its ``configs`` value is a list of **relative paths**
    (``"modsec-crs/nextcloud_false_positives.conf"``), while ``_prepare_template_entities``
    (``db_methods/templates.py``) requires config **objects** carrying ``type``, ``name`` and the
    config ``data`` itself. So each reference is resolved against
    ``templates/<id>/configs/<reference>`` in the same verified archive and materialised here.

    Every reference is pattern-checked before it is used as a path, and resolution goes through
    ``archive_file``, which re-derives each member relative to the wrapper root -- so a reference
    cannot address a file outside its own template's folder even if the pattern were loose.

    Only the five fields ``create_template`` takes are carried across. The rest of an upstream
    ``template.json`` is left where it is.
    """
    if not CATALOG_ID_RX.match(template_id or ""):
        return None, f"invalid template id {template_id!r}"

    base = f"{SOURCES['templates']['subdir']}/{template_id}"
    blob = archive_file(payload, f"{base}/{SOURCES['templates']['member']}")
    if blob is None:
        return None, f"the archive contains no template named {template_id}"
    if len(blob) > MAX_MEMBER_JSON:
        return None, f"{template_id}: template.json is oversized"
    try:
        data = loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, JSONDecodeError, ValueError):
        return None, f"{template_id}: template.json is not valid UTF-8 JSON"
    if not isinstance(data, dict):
        return None, f"{template_id}: template.json is not a JSON object"

    # The same identity check the listing made, made again on the bytes actually being installed:
    # the declared id is what `create_template` writes.
    declared = data.get("id")
    if declared != template_id:
        return None, f"the payload declares id {declared!r} but the catalogue entry is {template_id!r}"

    settings = data.get("settings")
    steps = data.get("steps")
    if not isinstance(settings, dict) or not isinstance(steps, list):
        return None, f"{template_id}: settings must be an object and steps a list"

    references = data.get("configs") or []
    if not isinstance(references, list) or len(references) > MAX_TEMPLATE_CONFIGS:
        return None, f"{template_id}: configs must be a list of at most {MAX_TEMPLATE_CONFIGS} references"

    configs: List[Dict[str, Any]] = []
    for reference in references:
        if not isinstance(reference, str) or not TEMPLATE_CONFIG_RX.match(reference):
            return None, f"{template_id}: invalid config reference {reference!r}"
        blob = archive_file(payload, f"{base}/configs/{reference}")
        if blob is None:
            return None, f"{template_id}: config {reference} is missing from the archive"
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            return None, f"{template_id}: config {reference} is not valid UTF-8"
        config_type, filename = reference.split("/", 1)
        configs.append({"type": config_type, "name": filename.removesuffix(".conf"), "data": text})

    return {
        "id": template_id,
        "name": _text(data.get("name"), _MAX_NAME) or template_id,
        "settings": settings,
        "steps": steps,
        "configs": configs,
    }, None


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


def build_catalog_view(kind: str, cached: Any, installed_ids: Any, bw_version: str) -> Dict[str, Any]:
    """The template context a catalogue section needs: its items, their state, and staleness.

    Pure: the caller does the I/O and passes the results in. That is not purity for its own sake --
    it keeps this out of the route modules, so neither route has to import the other, and it makes
    the listing logic testable without a Flask app.

    Items already installed are dropped, not greyed: the installed card is the truth for those,
    and rendering both would be two cards claiming one id. Incompatible items are kept and marked
    instead -- hiding them makes the catalogue look empty and generates support tickets, while
    showing the reason makes the constraint explain itself. That distinction carries real weight
    now that upstream declares no compatibility for its current releases: every card says so, out
    loud, instead of the page rendering as an unexplained blank.

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

    installed = set(installed_ids or ())
    view = [item | {"compatible": item_compatible(kind, bw_version, item), "bw_version": bw_version} for item in items if item.get("id") not in installed]
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
