"""The changelog parser, run against the real `CHANGELOG.md`.

A fixture would prove nothing here: the failure this guards against is a heading written by
hand in a slightly different shape, which drops a whole release in silence. The real file mixes
`v1.7.0-beta` with `v1.6.14~rc1` and carries `??` placeholders in dates, so it is the only
input worth asserting on.
"""

from pathlib import Path

import pytest

from app.models.changelog import (  # noqa: E402
    CHANGELOG_PATHS,
    Release,
    load,
    parse,
    releases_between,
    render_inline,
)

CHANGELOG = Path(__file__).resolve().parents[3] / "CHANGELOG.md"

# The only `##` heading in the file that is not a release, and is not meant to be one.
NOT_A_RELEASE = "## TODO - retrospective changelog"


@pytest.fixture(scope="module")
def real_releases():
    return parse(CHANGELOG.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------
# Against the real file
# --------------------------------------------------------------------------------------
def test_every_heading_in_the_real_changelog_becomes_a_release(real_releases):
    headings = [line for line in CHANGELOG.read_text(encoding="utf-8").splitlines() if line.startswith("## ")]
    parsed = {release.version for release in real_releases}
    missed = [line for line in headings if line != NOT_A_RELEASE and line[3:].split(" - ")[0].strip() not in parsed]

    assert not missed, f"malformed headings drop a whole release in silence: {missed}"


def test_the_non_release_heading_is_not_shown_as_one(real_releases):
    assert "TODO" not in {release.version for release in real_releases}


def test_every_release_is_comparable_and_carries_entries(real_releases):
    assert [release.version for release in real_releases if release.sortable is None] == []
    assert [release.version for release in real_releases if not release.entries] == []


def test_releases_keep_the_file_order_newest_first(real_releases):
    versions = [release.sortable for release in real_releases]

    assert versions == sorted(versions, reverse=True)


def test_the_shipped_path_is_where_the_dockerfiles_put_it():
    """`COPY CHANGELOG.md CHANGELOG.md` lands next to VERSION at the root of the tree."""
    assert CHANGELOG_PATHS[0].as_posix() == "/usr/share/bunkerweb/CHANGELOG.md"


def test_load_finds_the_repository_copy_and_caches_it():
    first = load()
    assert first, "the repository fallback path is what the test suite and a dev run read"
    assert load() is first, "a page render must not re-parse 150 KB of markdown"


# --------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------
SAMPLE = """# Changelog

## v1.7.0 - 2026/07/??

- [FEATURE] `ui`: something **new**
- [BUGFIX] `api`: something fixed, see [the docs](https://docs.bunkerweb.io)

## v1.6.9~rc2 - 2026/02/26

- plain line with no tag
"""


def test_tags_dates_and_wrapped_markup_survive_the_round_trip():
    releases = parse(SAMPLE)

    assert [r.version for r in releases] == ["v1.7.0", "v1.6.9~rc2"]
    assert releases[0].date == "2026/07/??", "a `??` placeholder is what the file says; inventing a date would be worse"
    assert [entry.tag for entry in releases[0].entries] == ["FEATURE", "BUGFIX"]
    assert releases[1].entries[0].tag == ""


def test_a_debian_style_prerelease_sorts_below_its_release():
    releases = parse(SAMPLE)
    by_version = {release.version: release.sortable for release in releases}

    assert by_version["v1.6.9~rc2"] < by_version["v1.7.0"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("plain", "plain"),
        ("a `code` span", "a <code>code</code> span"),
        ("**bold**", "<strong>bold</strong>"),
        ("[docs](https://docs.bunkerweb.io)", '<a href="https://docs.bunkerweb.io" target="_blank" rel="noopener noreferrer">docs</a>'),
    ],
)
def test_the_three_markups_the_changelog_uses(raw, expected):
    assert str(render_inline(raw)) == expected


def test_changelog_content_cannot_inject_markup():
    """The file is editable by anyone who can write to the image, and it renders unescaped."""
    rendered = str(render_inline('<img src=x onerror="alert(1)"> [x](javascript:alert(1))'))

    assert "<img" not in rendered, "raw HTML in the changelog must render as text"
    assert "<a" not in rendered, "only http(s) targets are turned into links"
    assert "&lt;img" in rendered


# --------------------------------------------------------------------------------------
# The interval — this is what the silent-stamp rule rests on
# --------------------------------------------------------------------------------------
def _releases(*versions):
    return tuple(Release(version=version, date="", entries=()) for version in versions)


def test_only_what_is_between_the_two_versions_is_shown():
    releases = _releases("v1.7.0", "v1.6.14", "v1.6.13", "v1.6.12")

    assert [r.version for r in releases_between(releases, "1.6.13", "1.7.0")] == ["v1.7.0", "v1.6.14"]


def test_the_running_version_itself_is_included_and_the_stored_one_is_not():
    releases = _releases("v1.7.0", "v1.6.14")

    shown = [r.version for r in releases_between(releases, "1.6.14", "1.7.0")]
    assert shown == ["v1.7.0"]


def test_a_release_newer_than_the_running_version_is_never_shown():
    """The bundled changelog can list a release this build does not have — a beta shipped
    ahead of its final, or an image left behind by a downgrade. Announcing it would tell the
    operator about fixes that are not in the binary they are running."""
    releases = _releases("v1.8.0", "v1.7.0", "v1.6.14")

    assert [r.version for r in releases_between(releases, "1.6.14", "1.7.0")] == ["v1.7.0"]


def test_a_downgrade_shows_nothing():
    """Running older than stored: the interval is empty by construction, and the caller
    re-stamps rather than telling an operator about releases it does not have."""
    releases = _releases("v1.7.0", "v1.6.14")

    assert releases_between(releases, "1.7.0", "1.6.14") == ()


def test_the_same_version_shows_nothing():
    releases = _releases("v1.7.0")

    assert releases_between(releases, "1.7.0", "1.7.0") == ()


def test_an_unparsable_stored_version_shows_nothing_rather_than_everything():
    """A corrupted blob must not turn into a modal containing the entire history."""
    releases = _releases("v1.7.0", "v1.6.14")

    assert releases_between(releases, "not-a-version", "1.7.0") == ()


# --------------------------------------------------------------------------------------
# Packaging — the failure mode is one integration shipping an empty page
# --------------------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[3]


def _ui_shipping_targets():
    """Every build that ships the web UI, and therefore needs the changelog beside it."""
    return sorted(p for p in REPO.glob("src/**/Dockerfile*") if "COPY src/ui ui" in p.read_text(encoding="utf-8"))


def test_every_build_that_ships_the_ui_ships_the_changelog():
    """Precedent: the Linux packages once shipped without a worker or a broker, and nothing
    caught it because each image was looked at on its own. `/whats-new` is empty on exactly
    the integration whose build was forgotten."""
    targets = _ui_shipping_targets()

    assert len(targets) >= 12, "the UI is built by more targets than this test knows about"
    missing = [p.relative_to(REPO).as_posix() for p in targets if "COPY CHANGELOG.md" not in p.read_text(encoding="utf-8")]
    assert not missing, f"these builds would serve an empty What's new page: {missing}"


# `test_the_freebsd_package_ships_it_too` stood here. FreeBSD was the one packaging target that
# built by copying the tree by hand instead of through a Dockerfile, so it needed an assertion of
# its own -- the derivation above only sees `src/**/Dockerfile*`. The PO dropped FreeBSD packaging
# on 2026-08-20 and `src/linux/build-freebsd.sh` went with it, so the test read a file that no
# longer exists. Every remaining target is a Dockerfile and is therefore covered by the derivation,
# which needs no list to maintain: add a build that ships the UI without the changelog and it goes
# red on its own.
