#!/usr/bin/env python3
"""The bundled `CHANGELOG.md`, parsed into releases the UI can show.

Content comes from the file shipped in the image — never from a remote fetch, so an air-gapped
install shows the same thing as a connected one, and never from a hand-written highlights file,
which would drift from the changelog the moment somebody forgot it.

Ordering and interval selection reuse `normalize_bunkerweb_version` + PEP 440 `Version`, the
same comparator the "new version available" badge uses. No hand-rolled version compare.
"""

from dataclasses import dataclass
from html import escape
from os.path import sep
from pathlib import Path
from re import compile as re_compile
from typing import Optional, Tuple

from markupsafe import Markup
from packaging.version import InvalidVersion, Version

from common_utils import normalize_bunkerweb_version  # type: ignore

# The key this feature owns in the per-user KV, alongside the walkthrough's own.
PREFERENCE_KEY = "whatsnew"

# Shipped next to `VERSION` at the root of the BunkerWeb tree. The second candidate is the
# repository layout, which is what the tests and a `flask run` from a checkout see.
CHANGELOG_PATHS = (
    Path(sep, "usr", "share", "bunkerweb", "CHANGELOG.md"),
    Path(__file__).resolve().parents[4] / "CHANGELOG.md",
)

_HEADING = re_compile(r"^##\s+(?P<version>v?\d+\.\d+\.\d+(?:[-~][A-Za-z0-9.]+)?)\s*(?:-\s*(?P<date>\S+))?\s*$")
_ENTRY = re_compile(r"^-\s+(?:\[(?P<tag>[A-Z]+)\]\s*)?(?P<text>.+)$")
_CODE = re_compile(r"`([^`]+)`")
_BOLD = re_compile(r"\*\*([^*]+)\*\*")
_LINK = re_compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")


@dataclass(frozen=True)
class Entry:
    tag: str  # "FEATURE", "BUGFIX", … or "" when the line carries none
    html: Markup


@dataclass(frozen=True)
class Release:
    version: str  # as written in the heading, e.g. "v1.6.14~rc1"
    date: str  # as written, "??" placeholders included — never invented
    entries: Tuple[Entry, ...]

    @property
    def sortable(self) -> Optional[Version]:
        try:
            return Version(normalize_bunkerweb_version(self.version))
        except InvalidVersion:
            return None


def render_inline(text: str) -> Markup:
    """The three markups the changelog actually uses, and nothing else.

    Escaping happens first and the replacements only ever produce tags of their own, so no
    changelog content can inject markup — which matters because this file is editable by
    anyone who can write to the image.
    """
    out = escape(text)
    out = _CODE.sub(r"<code>\1</code>", out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    # `escape` already turned the URL's & into &amp;; only http(s) targets are matched at all.
    out = _LINK.sub(r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', out)
    return Markup(out)


def parse(text: str) -> Tuple[Release, ...]:
    """Split the document into releases, newest first — the order the file is written in.

    A heading that does not parse as a version is skipped along with its block rather than
    guessed at: showing an operator a release note under the wrong version is worse than
    showing nothing. `test_changelog.py` runs this against the real file, so a malformed
    heading fails the suite instead of disappearing in silence.
    """
    releases = []
    version = date = None
    entries: list = []
    lines = []

    def flush():
        if version is None:
            return
        if lines:
            entries.append(_entry(" ".join(lines)))
        releases.append(Release(version=version, date=date or "", entries=tuple(entry for entry in entries if entry)))

    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            flush()
            version, date = heading.group("version"), heading.group("date")
            entries, lines = [], []
            continue
        if version is None:
            continue
        if line.startswith("- "):
            if lines:
                entries.append(_entry(" ".join(lines)))
            lines = [line]
        elif line.strip() and lines:
            # A wrapped bullet: keep it with the bullet it belongs to.
            lines.append(line.strip())
        elif not line.strip() and lines:
            entries.append(_entry(" ".join(lines)))
            lines = []

    flush()
    return tuple(releases)


def _entry(raw: str) -> Optional[Entry]:
    match = _ENTRY.match(raw)
    if not match:
        return None
    return Entry(tag=match.group("tag") or "", html=render_inline(match.group("text").strip()))


_CACHE: dict = {}


def load(path: Optional[Path] = None) -> Tuple[Release, ...]:
    """Parsed releases, cached on the file's identity so a page render costs one dict lookup.

    Keyed on mtime and size rather than parsed once for the process lifetime, so a changelog
    replaced under a running UI (a Linux package upgrade does exactly that) is picked up.
    """
    candidates = (path,) if path else CHANGELOG_PATHS
    for candidate in candidates:
        try:
            stat = candidate.stat()
        except OSError:
            continue
        key = (str(candidate), stat.st_mtime_ns, stat.st_size)
        if key not in _CACHE:
            _CACHE.clear()  # one file, one entry: this is a cache, not a history
            _CACHE[key] = parse(candidate.read_text(encoding="utf-8"))
        return _CACHE[key]
    return ()


def releases_between(releases: Tuple[Release, ...], stored: str, running: str) -> Tuple[Release, ...]:
    """Everything the user has not seen yet: stored < version <= running.

    Both bounds matter. Without the upper one a user running an older build than the newest
    entry in its own changelog — a downgrade, or a beta shipped with notes for what follows —
    is told about releases it does not have.
    """
    try:
        low = Version(normalize_bunkerweb_version(stored))
        high = Version(normalize_bunkerweb_version(running))
    except InvalidVersion:
        return ()
    if not low < high:
        return ()
    return tuple(release for release in releases if release.sortable and low < release.sortable <= high)
