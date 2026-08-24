"""Manifest validation for the community catalogue — the whole security boundary, in pure code.

Everything here is pure: no network, no filesystem, no DB. That is deliberate and it is the
point of the design — ``validate_catalog`` / ``validate_artifact_url`` / ``is_compatible`` are
the three functions that decide whether attacker-influenced bytes ever reach an extractor, so
they are written as pure functions precisely so they can be tested exhaustively without a
fixture stack.

The chain these pin (spec §5.5):

    pinned URL -> https+host allowlist -> size cap -> validate_catalog
              -> version gate -> artifact fetch (capped, no auto-redirect)
              -> sha256 compare_digest -> ONLY THEN the existing installer

Each test below owns one link. The ordering assertions at the bottom own the arrows.
"""

from hashlib import sha256
from json import dumps

import pytest

from app.models.plugin_catalog import (  # type: ignore
    ARTIFACT_MAX_PLUGIN,
    MANIFEST_MAX,
    is_compatible,
    validate_artifact_url,
    validate_catalog,
)

GOOD_SHA = "a" * 64
GOOD_URL = "https://github.com/bunkerity/bunkerweb-plugins/releases/download/v1.11/clamav-1.11.tar.gz"


def _plugin(**over):
    item = {
        "id": "clamav",
        "name": "ClamAV",
        "description": "Automatic scan of uploaded files.",
        "version": "1.11",
        "url": GOOD_URL,
        "sha256": GOOD_SHA,
        "size": 20480,
        "bw_min": "1.7.0",
        "bw_max": None,
    }
    item.update(over)
    return item


def _manifest(plugins=None, templates=None, **over):
    body = {
        "schema_version": 1,
        "generated_at": "2026-08-24T07:03:56Z",
        "plugins": [_plugin()] if plugins is None else plugins,
        "templates": templates or [],
    }
    body.update(over)
    return dumps(body).encode("utf-8")


# ── The happy path, so every rejection below means something ──────────────────


def test_a_well_formed_manifest_is_accepted_and_normalized():
    catalog, errors = validate_catalog(_manifest())
    assert errors == []
    assert [p["id"] for p in catalog["plugins"]] == ["clamav"]
    assert catalog["templates"] == []


# ── Manifest-level rejections: these fail the WHOLE manifest ──────────────────


def test_an_oversized_manifest_is_refused_before_it_is_parsed():
    # One byte over the cap. The cap exists because UIData rewrites the entire ui_data.json on
    # every __setitem__, so an oversized manifest is a self-inflicted DoS on every later write.
    assert validate_catalog(b"[" + b" " * MANIFEST_MAX)[0] is None


def test_a_manifest_exactly_at_the_cap_is_still_read():
    body = _manifest()
    # `,"_pad":"` (9) + `"}` (2) replaces the trailing `}` (1) => +10 bytes of framing.
    padded = body[:-1] + b',"_pad":"' + b"x" * (MANIFEST_MAX - len(body) - 10) + b'"}'
    assert len(padded) == MANIFEST_MAX
    catalog, _ = validate_catalog(padded)
    assert catalog is not None


@pytest.mark.parametrize("raw", [b"", b"not json", b"[]", b'"a string"', b"null", b"\xff\xfe"])
def test_anything_that_is_not_a_json_object_is_refused(raw):
    assert validate_catalog(raw)[0] is None


@pytest.mark.parametrize("version", [0, 2, "1", 1.0, None, True])
def test_only_integer_schema_version_1_is_accepted(version):
    # "1" as a string and 1.0 as a float are both rejected: a producer that drifts on the type
    # has drifted on the contract, and silently coercing is how a v2 manifest gets read as v1.
    assert validate_catalog(_manifest(schema_version=version))[0] is None


@pytest.mark.parametrize("plugins", [{}, "clamav", 3, True])
def test_the_plugins_key_must_be_a_list(plugins):
    assert validate_catalog(_manifest(plugins=plugins))[0] is None


def test_a_list_longer_than_the_item_cap_is_refused():
    assert validate_catalog(_manifest(plugins=[_plugin(id=f"p{i:04d}") for i in range(201)]))[0] is None


def test_the_item_cap_boundary_itself_is_accepted():
    catalog, _ = validate_catalog(_manifest(plugins=[_plugin(id=f"p{i:04d}") for i in range(200)]))
    assert catalog is not None and len(catalog["plugins"]) == 200


# ── Item-level rejections: these drop ONE item, never the manifest ────────────


def test_one_bad_item_does_not_black_out_the_catalogue():
    catalog, errors = validate_catalog(_manifest(plugins=[_plugin(id=".."), _plugin(id="clamav")]))
    assert [p["id"] for p in catalog["plugins"]] == ["clamav"]
    assert errors  # the drop is reported, not swallowed


@pytest.mark.parametrize(
    "bad_id",
    [
        "..",
        "../../etc/passwd",
        "a/b",
        "a\\b",
        ".hidden",
        "-lead",
        "_lead",
        "CLAMAV",  # uppercase: catalogue ids are a strict subset of _PLUGIN_ID_RX
        "clam.av",  # a dot is legal for the API and refused here on purpose
        "cl",
        # C3: 3 chars. The API's own rx is {4,64}, so this used to render as installable and
        # then fail at the last hop. The catalogue rule is a real subset of the API's now.
        "abc",
        "c" * 65,
        "",
        "   ",
        "clamav\n",  # C3: `$` matched before a trailing newline; the rule uses \Z now
        # (same reason _PLUGIN_ID_RX uses \Z: it reaches a filesystem path)
        "abc\n",
        "clam av",
        "clamav\x00",
        "сlamav",  # Cyrillic es homoglyph
    ],
)
def test_hostile_ids_are_dropped(bad_id):
    catalog, _ = validate_catalog(_manifest(plugins=[_plugin(id=bad_id)]))
    assert catalog["plugins"] == []


@pytest.mark.parametrize("good_id", ["clamav", "abcd", "a" * 64, "a-b_c", "waf2"])
def test_legal_ids_survive(good_id):
    catalog, _ = validate_catalog(_manifest(plugins=[_plugin(id=good_id)]))
    assert [p["id"] for p in catalog["plugins"]] == [good_id]


@pytest.mark.parametrize(
    "bad_sha",
    [
        "A" * 64,  # uppercase hex: refused here so it can never reach compare_digest
        "a" * 63,
        "a" * 65,
        "g" * 64,
        "0x" + "a" * 62,
        "",
        None,
        123,
        " " + "a" * 63,
    ],
)
def test_a_sha256_that_is_not_64_lowercase_hex_drops_the_item(bad_sha):
    catalog, _ = validate_catalog(_manifest(plugins=[_plugin(sha256=bad_sha)]))
    assert catalog["plugins"] == []


@pytest.mark.parametrize("bad_size", [True, False, 0, -1, 1.5, "20480", None, ARTIFACT_MAX_PLUGIN + 1])
def test_a_bad_size_drops_the_item(bad_size):
    # `True` is the one that bites: isinstance(True, int) is True in Python, so a naive
    # isinstance check accepts a boolean as a byte count.
    catalog, _ = validate_catalog(_manifest(plugins=[_plugin(size=bad_size)]))
    assert catalog["plugins"] == []


def test_the_size_cap_boundary_is_accepted():
    catalog, _ = validate_catalog(_manifest(plugins=[_plugin(size=ARTIFACT_MAX_PLUGIN)]))
    assert len(catalog["plugins"]) == 1


@pytest.mark.parametrize("field", ["id", "name", "version", "url", "sha256", "size", "bw_min"])
def test_every_required_field_is_required(field):
    item = _plugin()
    del item[field]
    catalog, _ = validate_catalog(_manifest(plugins=[item]))
    assert catalog["plugins"] == []


@pytest.mark.parametrize("bad_version", ["", "not-a-version", None, 1.11, "1.2.3.4.5.6.7-", "∞"])
def test_an_unparseable_version_drops_the_item(bad_version):
    catalog, _ = validate_catalog(_manifest(plugins=[_plugin(version=bad_version)]))
    assert catalog["plugins"] == []


def test_a_duplicate_id_keeps_the_first_deterministically():
    first, second = _plugin(version="1.11"), _plugin(version="9.99")
    catalog, errors = validate_catalog(_manifest(plugins=[first, second]))
    assert [p["version"] for p in catalog["plugins"]] == ["1.11"]
    assert errors


def test_the_same_id_in_plugins_and_templates_is_not_a_collision():
    catalog, _ = validate_catalog(_manifest(plugins=[_plugin(id="wordpress")], templates=[_plugin(id="wordpress")]))
    assert len(catalog["plugins"]) == 1 and len(catalog["templates"]) == 1


def test_unknown_keys_are_dropped_and_never_reach_the_output():
    catalog, _ = validate_catalog(_manifest(plugins=[_plugin(icon="<script>alert(1)</script>", exec="rm -rf /")]))
    item = catalog["plugins"][0]
    assert "icon" not in item and "exec" not in item
    # And nothing hostile rode in on a value we DO keep.
    assert set(item) <= {"id", "name", "description", "version", "url", "sha256", "size", "bw_min", "bw_max", "requires", "homepage"}


def test_the_output_is_a_fresh_object_not_the_parsed_input():
    raw = _manifest()
    catalog, _ = validate_catalog(raw)
    catalog["plugins"][0]["id"] = "mutated"
    again, _ = validate_catalog(raw)
    assert again["plugins"][0]["id"] == "clamav"


@pytest.mark.parametrize("field", ["name", "description"])
def test_overlong_text_fields_drop_the_item(field):
    catalog, _ = validate_catalog(_manifest(plugins=[_plugin(**{field: "x" * 10_000})]))
    assert catalog["plugins"] == []


def test_requires_is_bounded_in_both_dimensions():
    assert validate_catalog(_manifest(plugins=[_plugin(requires=["x"] * 6)]))[0]["plugins"] == []
    assert validate_catalog(_manifest(plugins=[_plugin(requires=["x" * 500])]))[0]["plugins"] == []
    assert validate_catalog(_manifest(plugins=[_plugin(requires="not a list")]))[0]["plugins"] == []


def test_a_homepage_is_url_validated_because_it_becomes_an_href():
    assert validate_catalog(_manifest(plugins=[_plugin(homepage="javascript:alert(1)")]))[0]["plugins"] == []


# ── The URL allowlist: without it the manifest is an SSRF primitive ───────────


@pytest.mark.parametrize(
    "url",
    [
        GOOD_URL,
        "https://raw.githubusercontent.com/bunkerity/bunkerweb-plugins/main/catalog.json",
        # Measured 2026-08-24: a real release-asset download 302s here, query string and all.
        "https://release-assets.githubusercontent.com/github-production-release-asset/203456148/x?sp=r&sig=a%2Fb&jwt=c",
        "https://objects.githubusercontent.com/github-production-release-asset/1/2",
    ],
)
def test_the_allowlisted_shapes_pass(url):
    assert validate_artifact_url(url) is True


def test_percent_escapes_in_the_query_do_not_trip_the_traversal_check():
    # The signed asset URL is almost all query string and legitimately contains %2F, %3B and %20.
    # A query-scoped traversal check would reject every real release-asset download.
    assert validate_artifact_url("https://release-assets.githubusercontent.com/a/b?rscd=attachment%3B+filename%3Dx&sig=p%2Fq%2Br") is True
    # ...but the same escape in the PATH is still refused.
    assert validate_artifact_url("https://release-assets.githubusercontent.com/a/%2e%2e%2fb") is False


@pytest.mark.parametrize(
    "url",
    [
        # Wrong scheme.
        "http://github.com/bunkerity/bunkerweb-plugins/x.tar.gz",
        "file:///etc/passwd",
        "ftp://github.com/bunkerity/bunkerweb-plugins/x",
        "javascript:alert(1)",
        "//github.com/bunkerity/bunkerweb-plugins/x",
        # Wrong host, including the near-misses.
        "https://evil.com/bunkerity/bunkerweb-plugins/x.tar.gz",
        "https://github.com.evil.com/bunkerity/bunkerweb-plugins/x.tar.gz",
        "https://evilgithub.com/bunkerity/bunkerweb-plugins/x.tar.gz",
        "https://raw.githubusercontent.com.evil.com/bunkerity/bunkerweb-plugins/x",
        # The suffix branch must anchor on a leading dot. A bare
        # endswith("githubusercontent.com") accepts every one of these.
        "https://evil-githubusercontent.com/a/b",
        "https://githubusercontent.com.evil.net/a/b",
        "https://notgithubusercontent.com/a/b",
        # Right host, wrong repo or org.
        "https://github.com/attacker/bunkerweb-plugins/x.tar.gz",
        "https://github.com/bunkerity/bunkerweb/x.tar.gz",
        "https://github.com/bunkerity/bunkerweb-plugins-evil/x.tar.gz",
        # Credential smuggling: everything left of @ is userinfo, the real host is evil.com.
        "https://github.com@evil.com/bunkerity/bunkerweb-plugins/x",
        "https://user:pass@github.com/bunkerity/bunkerweb-plugins/x",
        # Explicit port.
        "https://github.com:8443/bunkerity/bunkerweb-plugins/x",
        # Traversal, raw and percent-encoded.
        "https://github.com/bunkerity/bunkerweb-plugins/../../other/x",
        "https://github.com/bunkerity/bunkerweb-plugins/%2e%2e%2f%2e%2e%2fx",
        "https://github.com/bunkerity/bunkerweb-plugins/%2E%2E/x",
        # A source tarball's redirect target: GitHub-controlled, deliberately NOT allowlisted
        # because the producer contract publishes per-item assets, never whole-repo archives.
        "https://codeload.github.com/bunkerity/bunkerweb-plugins/tar.gz/refs/tags/v1.11",
        # The internal targets this list exists to make unreachable.
        "https://bw-api:8888/plugins",
        "https://127.0.0.1/",
        "https://169.254.169.254/latest/meta-data/",
        "https://[::1]/",
        # Junk.
        "",
        "not a url",
    ],
)
def test_everything_else_is_refused(url):
    assert validate_artifact_url(url) is False


def test_host_matching_is_case_insensitive_but_still_exact():
    assert validate_artifact_url(GOOD_URL.replace("github.com", "GitHub.COM")) is True
    assert validate_artifact_url(GOOD_URL.replace("github.com", "GitHub.COM.evil.net")) is False


# ── The version gate: closed on failure, unlike is_newer_version_available ────


@pytest.mark.parametrize(
    "bw,lo,hi,expected",
    [
        ("1.7.0", "1.7.0", None, True),  # inclusive lower bound
        ("1.7.1", "1.7.0", None, True),
        ("1.6.11", "1.7.0", None, False),
        ("1.7.9", "1.7.0", "2.0.0", True),
        ("2.0.0", "1.7.0", "2.0.0", False),  # EXCLUSIVE upper bound, at the boundary
        ("1.9.9", "1.7.0", "2.0.0", True),
        # Debian-style pre-release, normalized by normalize_bunkerweb_version.
        ("1.7.0~beta", "1.7.0", None, False),  # a beta is not the release
        ("1.7.0~beta", "1.7.0-beta", None, True),  # a producer can opt in explicitly
        ("1.7.0~rc2", "1.7.0-beta", None, True),
    ],
)
def test_the_bounds_behave_as_specified(bw, lo, hi, expected):
    assert is_compatible(bw, lo, hi) is expected


@pytest.mark.parametrize(
    "bw,lo,hi",
    [
        ("unknown", "1.7.0", None),  # metadata unavailable
        ("", "1.7.0", None),
        ("1.7.0", "not-a-version", None),
        ("1.7.0", "1.7.0", "not-a-version"),
        (None, "1.7.0", None),
    ],
)
def test_an_unresolvable_version_reads_as_INCOMPATIBLE(bw, lo, hi):
    # Deliberately the opposite stance to is_newer_version_available, whose docstring prefers a
    # false negative. There a parse failure costs a missed notification; here it costs running
    # an incompatible plugin as code in the UI, the worker and nginx.
    assert is_compatible(bw, lo, hi) is False


# ── The hash gate, and the ordering that makes it worth anything ─────────────


def test_a_matching_digest_passes_and_a_one_bit_change_does_not():
    from app.models.plugin_catalog import verify_digest  # type: ignore

    payload = b"plugin bytes"
    good = sha256(payload).hexdigest()
    assert verify_digest(payload, good) is True
    assert verify_digest(payload, good[:-1] + ("0" if good[-1] != "0" else "1")) is False
    assert verify_digest(payload[:-1], good) is False
    assert verify_digest(payload, good.upper()) is False  # never normalized at compare time


# ── Id collisions with what is already installed ─────────────────────────────
#
# Explicitly requested in the spec-approval ruling, and it found something (spec §8.2 step 4):
# `POST /plugins/upload` builds its `existing_ids` from `_type="ui"` ONLY, so a catalogue id
# colliding with a core or scheduler-installed plugin gets past it. The DB layer then refuses
# the write for real (`_uep_sync_plugin_row` rejects a non-external/ui/pro row, and rejects a
# method mismatch) -- but it refuses SILENTLY, returning "" so the API reports created: [id].
# The catalogue therefore refuses the collision itself, against the FULL plugin list.


def _installed(**by_id):
    """A stand-in for the installed-plugin index the route consults: id -> type."""
    return by_id


@pytest.mark.parametrize(
    "collision_type",
    ["core", "external", "ui", "pro"],
)
def test_an_id_already_installed_is_refused_whatever_its_type(collision_type):
    from app.models.plugin_catalog import collides_with_installed  # type: ignore

    assert collides_with_installed("blacklist", _installed(blacklist=collision_type)) is True


def test_a_free_id_does_not_collide():
    from app.models.plugin_catalog import collides_with_installed  # type: ignore

    assert collides_with_installed("clamav", _installed(blacklist="core", antibot="core")) is False


def test_the_core_ids_this_product_ships_are_the_ones_that_matter():
    # Not an exhaustive list -- the point is that these are `core` rows, which the API's
    # ui-only `existing_ids` check does not see at all.
    from app.models.plugin_catalog import collides_with_installed  # type: ignore

    installed = {name: "core" for name in ("blacklist", "antibot", "misc", "whitelist", "greylist", "dnsbl")}
    for name in installed:
        assert collides_with_installed(name, installed) is True


def test_the_collision_check_is_exact_not_a_prefix_or_substring_match():
    from app.models.plugin_catalog import collides_with_installed  # type: ignore

    installed = _installed(blacklist="core")
    assert collides_with_installed("black", installed) is False
    assert collides_with_installed("blacklist2", installed) is False
    assert collides_with_installed("blackliST", installed) is False  # ids are lowercase (§4.4)


# ── C1/C2: the archive is the thing that gets installed, not the manifest entry ──
#
# The two HIGH findings of the adversarial review, and the reason they are HIGH: every gate above
# keys on the MANIFEST id, while the installer writes `TMP_UI_ROOT / meta["id"]` where `meta` is
# the ARCHIVE's plugin.json (api/app/routers/plugins.py:333 and :389). And both install branches
# loop over every plugin.json they find, so one click could install N plugins. Without the two
# checks these tests pin, the version gate, the collision gate and the 409 all guard a name the
# install does not use.

from io import BytesIO  # noqa: E402
from tarfile import TarInfo, open as tar_open  # noqa: E402

from app.models.plugin_catalog import archive_plugin_roots, check_archive_identity  # type: ignore  # noqa: E402


def _tar(*plugins):
    """A .tar.gz carrying one `<root>/plugin.json` per (root, declared_id) pair."""
    buf = BytesIO()
    with tar_open(fileobj=buf, mode="w:gz") as tar:
        for root, declared in plugins:
            body = dumps({"id": declared, "name": declared, "version": "1.0"}).encode()
            info = TarInfo(f"{root}/plugin.json")
            info.size = len(body)
            tar.addfile(info, BytesIO(body))
    return buf.getvalue()


def test_a_well_formed_single_plugin_archive_is_accepted():
    assert check_archive_identity(_tar(("clamav", "clamav")), "clamav") is None


def test_an_archive_whose_id_differs_from_the_manifest_is_refused():
    # M9. The archive's id is what reaches the filesystem, so a manifest entry for `clamav`
    # whose tarball declares `blacklist` must not install.
    problem = check_archive_identity(_tar(("clamav", "blacklist")), "clamav")
    assert problem and "blacklist" in problem and "clamav" in problem


def test_a_directory_name_that_matches_cannot_rescue_a_wrong_declared_id():
    # The check is on the DECLARED id, not the folder: the installer reads plugin.json.
    assert check_archive_identity(_tar(("clamav", "evil")), "clamav") is not None


def test_a_multi_root_archive_is_refused():
    # M10. Both API branches loop over every root, so this is "one click, two installs".
    problem = check_archive_identity(_tar(("clamav", "clamav"), ("extra", "extra")), "clamav")
    assert problem and "exactly one" in problem


def test_a_multi_root_archive_is_refused_even_when_the_first_root_is_correct():
    # The obvious wrong fix is to check only roots[0]. This is the test that kills it.
    assert check_archive_identity(_tar(("clamav", "clamav"), ("clamav2", "backdoor")), "clamav") is not None


def test_an_archive_with_no_plugin_json_is_refused():
    assert check_archive_identity(_tar(), "clamav") is not None


def test_a_plugin_json_with_no_id_is_refused():
    assert check_archive_identity(_tar(("clamav", "")), "clamav") is not None


def test_garbage_bytes_are_refused_rather_than_raising():
    # Reached only after the hash gate passes, but it must still not explode.
    assert check_archive_identity(b"not an archive at all", "clamav") is not None
    assert archive_plugin_roots(b"") == []


def test_nested_plugin_json_still_counts_as_a_root():
    # `_find_plugin_roots_in_tar` matches any path ending in plugin.json, however deep, so a
    # nested one is a second install and must be caught here too.
    assert check_archive_identity(_tar(("clamav", "clamav"), ("clamav/vendor/sneaky", "sneaky")), "clamav") is not None


# ── C5: the cached VALUE expires, not just the fetch ────────────────────────


def test_a_fresh_stamp_is_not_stale():
    from datetime import datetime, timedelta

    from app.models.plugin_catalog import is_stale  # type: ignore

    assert is_stale((datetime.now().astimezone() - timedelta(hours=1)).isoformat()) is False


def test_a_stamp_older_than_the_max_age_is_stale():
    # M12. The hourly gate governs whether a FETCH happens and keeps the previous value on
    # failure. Without this, a yanked vulnerable item stays installable forever.
    from datetime import datetime, timedelta

    from app.models.plugin_catalog import CATALOG_MAX_AGE, is_stale  # type: ignore

    assert is_stale((datetime.now().astimezone() - CATALOG_MAX_AGE - timedelta(minutes=1)).isoformat()) is True


@pytest.mark.parametrize("stamp", [None, "", "not-a-date", 12345, {}])
def test_an_unreadable_stamp_counts_as_stale(stamp):
    from app.models.plugin_catalog import is_stale  # type: ignore

    assert is_stale(stamp) is True


# ── read_cached / find_item: nothing but the id comes from the request ──────


def test_find_item_resolves_through_the_cached_catalog():
    from app.models.plugin_catalog import find_item  # type: ignore

    cached = {"fetched_at": "2026-08-24T12:00:00+02:00", "catalog": {"plugins": [_plugin()], "templates": []}}
    assert find_item(cached, "plugins", "clamav")["url"] == GOOD_URL
    assert find_item(cached, "plugins", "nope") is None
    assert find_item(cached, "templates", "clamav") is None


@pytest.mark.parametrize("blob", [None, "", 42, [], {"catalog": "nope"}, {"catalog": {"plugins": "nope"}}])
def test_a_crafted_ui_data_blob_never_blows_up_the_page(blob):
    # ui_data.json is a file other processes write, so it is parsed defensively, not trusted.
    from app.models.plugin_catalog import read_cached  # type: ignore

    catalog, _ = read_cached(blob)
    assert catalog == {"plugins": [], "templates": []} or catalog["plugins"] == []


# ── The kill switch ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value,expected", [("yes", True), ("", True), ("YES", True), ("no", False), ("NO", False), ("off", False), ("false", False), ("0", False)]
)
def test_the_kill_switch_reads_as_a_boolean(monkeypatch, value, expected):
    from app.models.plugin_catalog import catalog_enabled  # type: ignore

    monkeypatch.setenv("USE_PLUGIN_CATALOG", value)
    assert catalog_enabled() is expected


def test_the_kill_switch_defaults_to_on(monkeypatch):
    from app.models.plugin_catalog import catalog_enabled  # type: ignore

    monkeypatch.delenv("USE_PLUGIN_CATALOG", raising=False)
    assert catalog_enabled() is True


def test_the_switch_off_means_no_request_is_issued(monkeypatch):
    # A *skip*, not a swallowed failure: that distinction is the whole point for an
    # egress-restricted install.
    import app.models.plugin_catalog as pc  # type: ignore

    monkeypatch.setenv("USE_PLUGIN_CATALOG", "no")
    monkeypatch.setattr(pc, "_get_allowlisted", lambda *a, **k: pytest.fail("a request was issued with the catalogue disabled"))
    assert pc.fetch_catalog() is None


# ── The caps, and the encoded-separator check ───────────────────────────────
#
# Both of these were SURVIVING mutants on the first mutation run: the code was right, the tests
# were not exercising it. A cap nothing tests is a cap that silently disappears in a refactor.


class _FakeResponse:
    """The slice of `requests.Response` that `_read_capped` touches."""

    def __init__(self, chunks):
        self._chunks = chunks
        self.closed = False

    def iter_content(self, chunk_size=None):  # noqa: ARG002 - signature match
        yield from self._chunks

    def close(self):
        self.closed = True


def test_a_body_at_the_cap_is_read():
    from app.models.plugin_catalog import _read_capped  # type: ignore

    assert _read_capped(_FakeResponse([b"x" * 100]), 100) == b"x" * 100


def test_a_body_one_byte_over_the_cap_is_refused():
    # M7. The read is cut as soon as the accumulated length passes the cap, so an unbounded
    # body cannot be buffered while we wait to find out how big it was.
    from app.models.plugin_catalog import _read_capped  # type: ignore

    assert _read_capped(_FakeResponse([b"x" * 101]), 100) is None


def test_the_cap_is_enforced_across_chunks_not_per_chunk():
    from app.models.plugin_catalog import _read_capped  # type: ignore

    assert _read_capped(_FakeResponse([b"x" * 60, b"x" * 60]), 100) is None


def test_a_lying_content_length_buys_nothing():
    # Content-Length is never consulted -- it is a claim, not a measurement -- so a response
    # advertising 10 bytes and sending 10 MB is still cut at the cap.
    from app.models.plugin_catalog import _read_capped  # type: ignore

    assert _read_capped(_FakeResponse([b"x" * 1024] * 20), 4096) is None


def test_empty_chunks_do_not_confuse_the_counter():
    from app.models.plugin_catalog import _read_capped  # type: ignore

    assert _read_capped(_FakeResponse([b"a", b"", b"b"]), 10) == b"ab"


def test_a_percent_encoded_separator_in_the_path_is_refused():
    # M17. `%2f` decodes into a path separator without ever appearing as a literal `..`
    # segment, so neither traversal branch sees it -- only the count comparison does.
    assert validate_artifact_url("https://github.com/bunkerity/bunkerweb-plugins/a%2fb") is False
    assert validate_artifact_url("https://release-assets.githubusercontent.com/a%2Fb") is False
    # ...while the same escape in the QUERY is untouched, because a signed asset URL is full
    # of them and rejecting those would break every real download.
    assert validate_artifact_url("https://release-assets.githubusercontent.com/a/b?sig=p%2Fq") is True


# ── The allowlist is exact, because the suffix admitted user-writable hosts ──
#
# An earlier version accepted any `.githubusercontent.com` host on the premise that the whole
# suffix is "GitHub-controlled". GitHub *operates* those hosts; it does not author what several
# of them serve. These two are the counter-example that killed the premise.


@pytest.mark.parametrize(
    "url",
    [
        "https://gist.githubusercontent.com/attacker/deadbeef/raw/evil.tar.gz",
        "https://camo.githubusercontent.com/0123456789abcdef",
        "https://avatars.githubusercontent.com/u/1",
        "https://user-images.githubusercontent.com/1/2.png",
        "https://private-user-images.githubusercontent.com/1/2.png",
    ],
)
def test_user_writable_githubusercontent_hosts_are_refused(url):
    assert validate_artifact_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "https://release-assets.githubusercontent.com/github-production-release-asset/1/2?sig=a%2Fb",
        "https://objects.githubusercontent.com/github-production-release-asset/1/2",
    ],
)
def test_the_two_asset_hops_are_allowed_without_a_path_prefix(url):
    # Their paths are opaque signed blobs, so a repo-path prefix cannot be required here. The
    # SHA-256 gate is what decides whether the bytes are installed -- this list only decides
    # where we are willing to send a request at all.
    assert validate_artifact_url(url) is True


def test_a_repo_host_still_needs_the_repository_path():
    assert validate_artifact_url("https://raw.githubusercontent.com/bunkerity/bunkerweb-plugins/main/catalog.json") is True
    assert validate_artifact_url("https://raw.githubusercontent.com/attacker/evil/main/catalog.json") is False


# ── A stamp in the future is stale too ──────────────────────────────────────


def test_a_future_stamp_is_stale():
    """The window is closed at BOTH ends.

    A one-sided `age > CATALOG_MAX_AGE` is passed by a negative age, so a stamp dated years ahead
    read as permanently fresh -- re-opening exactly the hole the freshness gate exists to close.
    `ui_data.json` is written by other processes, and a clock that jumps backwards produces the
    same shape with nobody being hostile.
    """
    from datetime import datetime, timedelta

    from app.models.plugin_catalog import is_stale  # type: ignore

    assert is_stale((datetime.now().astimezone() + timedelta(days=4000)).isoformat()) is True
    assert is_stale((datetime.now().astimezone() + timedelta(minutes=5)).isoformat()) is True


def test_the_present_moment_is_not_stale():
    from datetime import datetime

    from app.models.plugin_catalog import is_stale  # type: ignore

    assert is_stale(datetime.now().astimezone().isoformat()) is False


# ── The declared size is the download cap ───────────────────────────────────


def test_a_declared_size_tightens_the_cap():
    from app.models.plugin_catalog import artifact_cap  # type: ignore

    assert artifact_cap(8192, ARTIFACT_MAX_PLUGIN) == 8192


def test_a_declared_size_can_never_loosen_the_cap():
    # `min`, not "trust the manifest": a hostile size must not buy a bigger read than the
    # constant already allowed.
    from app.models.plugin_catalog import artifact_cap  # type: ignore

    assert artifact_cap(ARTIFACT_MAX_PLUGIN * 100, ARTIFACT_MAX_PLUGIN) == ARTIFACT_MAX_PLUGIN


@pytest.mark.parametrize("bad", [None, 0, -1, True, False, "8192", 1.5, {}])
def test_an_unusable_declared_size_falls_back_to_the_ceiling(bad):
    from app.models.plugin_catalog import artifact_cap  # type: ignore

    assert artifact_cap(bad, ARTIFACT_MAX_PLUGIN) == ARTIFACT_MAX_PLUGIN


# ── plugin.json members are read capped ─────────────────────────────────────


def test_an_enormous_plugin_json_member_does_not_expand_in_memory():
    """gzip amplifies, so an already-capped archive can still carry a huge member.

    Read truncated, so it fails to parse, so the declared id is "" -- which the identity check
    refuses. No separate error path is needed, but the read must not be unbounded.
    """
    from io import BytesIO
    from tarfile import TarInfo, open as tar_open

    from app.models.plugin_catalog import MAX_PLUGIN_JSON, archive_plugin_roots, check_archive_identity  # type: ignore

    body = b'{"id": "clamav", "pad": "' + b"x" * (MAX_PLUGIN_JSON * 2) + b'"}'
    buf = BytesIO()
    with tar_open(fileobj=buf, mode="w:gz") as tar:
        info = TarInfo("clamav/plugin.json")
        info.size = len(body)
        tar.addfile(info, BytesIO(body))
    payload = buf.getvalue()

    roots = archive_plugin_roots(payload)
    assert roots == [("clamav", "")]
    assert check_archive_identity(payload, "clamav") is not None
