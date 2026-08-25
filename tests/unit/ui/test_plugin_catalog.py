"""The community catalogue's security boundary, in pure code.

Everything here is pure: no network, no filesystem, no DB. That is deliberate and it is the point
of the design — the functions that decide whether attacker-influenced bytes ever reach an
installer are written as pure functions precisely so they can be tested exhaustively without a
fixture stack.

The chain these pin, after the 2026-08-24 re-scope (there is no manifest and no producer; the
repositories ARE the catalogue):

    pinned repo -> /releases/latest (https + exact-host allowlist + capped read)
                -> parse_release   (tag re-validated)
                -> archive URL DERIVED from the tag, never read from the body
                -> archive GET     (allowlisted, redirects walked by hand, capped)
                -> archive_entries (folder name == declared id, member-capped)
                -> digest recorded
                -> [install] freshness gate -> version gate -> re-fetch AT THE PINNED TAG
                -> verify_digest   (compare_digest, before anything is unpacked)
                -> repack_plugin / template_payload  (exactly one item, by id)
                -> ONLY THEN the existing installer

Each test below owns one link. The hostile-input corpus (ids, URLs, caps, crafted ui_data) is
carried over from the manifest-era suite unchanged where it still applies — those inputs did not
stop being hostile because the source model changed.
"""

from datetime import datetime, timedelta
from io import BytesIO
from json import dumps
from tarfile import DIRTYPE, TarInfo, open as tar_open

import pytest

from app.models.plugin_catalog import (  # type: ignore
    ARCHIVE_MAX,
    CATALOG_MAX_AGE,
    EXTRACT_MAX,
    MEMBER_MAX,
    RELEASE_MAX,
    SOURCES,
    archive_entries,
    archive_file,
    archive_root,
    archive_url,
    build_catalog_view,
    build_items,
    find_item,
    is_compatible,
    is_stale,
    item_compatible,
    item_homepage,
    parse_compatibility,
    parse_release,
    read_cached,
    release_url,
    repack_plugin,
    template_payload,
    validate_artifact_url,
    verify_digest,
)

ROOT = "bunkerity-bunkerweb-plugins-fb55b84"
TROOT = "bunkerity-bunkerweb-templates-509f350"

# The two URL shapes this flow actually walks, measured 2026-08-24 with `curl -sSL -D -`:
#   https://api.github.com/repos/bunkerity/bunkerweb-plugins/tarball/v1.11
#     --302--> https://codeload.github.com/bunkerity/bunkerweb-plugins/legacy.tar.gz/refs/tags/v1.11
# One hop. There is no `objects.`/`release-assets.githubusercontent.com` anywhere in it.
API_URL = "https://api.github.com/repos/bunkerity/bunkerweb-plugins/tarball/v1.11"
CODELOAD_URL = "https://codeload.github.com/bunkerity/bunkerweb-plugins/legacy.tar.gz/refs/tags/v1.11"


def make_archive(files, root=ROOT, mode="w:gz"):
    """A tar in the shape GitHub produces: one generated wrapper directory, then the repo."""
    buf = BytesIO()
    with tar_open(fileobj=buf, mode=mode) as tar:
        for name, blob in files.items():
            if blob is None:  # a directory
                info = TarInfo(name=f"{root}/{name}")
                info.type = DIRTYPE
                tar.addfile(info)
                continue
            if isinstance(blob, str):
                blob = blob.encode("utf-8")
            info = TarInfo(name=f"{root}/{name}")
            info.size = len(blob)
            tar.addfile(info, BytesIO(blob))
    return buf.getvalue()


_UNSET = object()


def plugin_archive(ids=("clamav",), version="1.11", root=ROOT, extra=None, declared=_UNSET):
    files = {}
    for pid in ids:
        meta = {"id": pid if declared is _UNSET else declared, "name": pid.title(), "version": version, "stream": "no", "description": f"{pid} desc"}
        files[f"{pid}/plugin.json"] = dumps(meta)
        files[f"{pid}/{pid}.lua"] = f"-- {pid}\n"
    files.update(extra or {})
    return make_archive(files, root=root)


def template_archive(ids=("nextcloud",), configs=None, root=TROOT, extra=None):
    files = {}
    for tid in ids:
        meta = {
            "id": tid,
            "name": f"{tid} template",
            "settings": {"SERVER_NAME": "www.example.com"},
            "steps": [{"title": "Step", "settings": ["SERVER_NAME"], "configs": list(configs or [])}],
        }
        if configs:
            meta["configs"] = list(configs)
            for ref in configs:
                files[f"templates/{tid}/configs/{ref}"] = f"# {ref}\n"
        files[f"templates/{tid}/template.json"] = dumps(meta)
    files.update(extra or {})
    return make_archive(files, root=root)


COMPAT = dumps({"1.8": ["1.6.0", "1.6.11"], "1.11": ["1.7.0", "1.7.1"]})


# ── The release lookup: only one field crosses, and it is re-validated ───────


def test_a_well_formed_release_yields_its_tag():
    tag, errors = parse_release(dumps({"tag_name": "v1.11", "tarball_url": "https://evil.example/x"}).encode())
    assert tag == "v1.11" and errors == []


def test_the_tarball_url_in_the_body_is_never_used():
    # The one property that makes the response body unable to aim the next request: the URL is
    # DERIVED from the validated tag. A body pointing anywhere else changes nothing.
    tag, _ = parse_release(dumps({"tag_name": "v1.11", "tarball_url": "https://evil.example/x"}).encode())
    assert archive_url(SOURCES["plugins"]["repo"], tag) == API_URL
    assert validate_artifact_url(archive_url(SOURCES["plugins"]["repo"], tag)) is True


@pytest.mark.parametrize(
    "tag",
    [
        "../../etc/passwd",
        "v1.11/../../x",
        "a/b",
        "a\\b",
        "-lead",  # must start alphanumeric
        ".lead",
        "",
        "   ",
        "v1.11\n",  # `\Z` and not `$`: a trailing newline reaches a URL
        "v1.11\x00",
        "v1.11 ",
        "v1%2e%2e",
        "x" * 65,
        None,
        1.11,
        True,
        ["v1.11"],
    ],
)
def test_a_hostile_tag_is_refused(tag):
    got, errors = parse_release(dumps({"tag_name": tag}).encode())
    assert got is None and errors


@pytest.mark.parametrize("tag", ["v1.11", "1.10", "0.6", "dev", "v0.1", "a", "release_2026-08-24"])
def test_real_tag_shapes_survive(tag):
    assert parse_release(dumps({"tag_name": tag}).encode())[0] == tag


@pytest.mark.parametrize("flag", ["draft", "prerelease"])
def test_a_draft_or_prerelease_is_refused(flag):
    # `/releases/latest` already excludes both. Reading it again means a change of behaviour on
    # GitHub's side fails closed instead of quietly shipping a prerelease to every operator.
    assert parse_release(dumps({"tag_name": "v1.11", flag: True}).encode())[0] is None


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"not json",
        b"[]",
        b'"a string"',
        b"null",
        b"123",
        dumps({}).encode(),
        dumps({"tag_name": None}).encode(),
        "\udcff".encode("utf-8", "surrogateescape"),
        None,
        "a string, not bytes",
    ],
)
def test_an_unusable_release_body_is_refused_rather_than_raising(raw):
    assert parse_release(raw)[0] is None


def test_an_oversized_release_body_is_refused_before_it_is_parsed():
    # Deliberately VALID JSON that is merely too big. An oversized blob of `x` would fail on the
    # parse instead, which passes for the wrong reason and leaves the cap untested -- that exact
    # mistake let "drop the cap" survive the first mutation run.
    body = dumps({"tag_name": "v1.11", "pad": "x" * RELEASE_MAX}).encode()
    assert len(body) > RELEASE_MAX
    assert parse_release(body)[0] is None


def test_a_release_body_exactly_at_the_cap_is_still_read():
    body = dumps({"tag_name": "v1.11", "pad": ""}).encode()
    body = dumps({"tag_name": "v1.11", "pad": "x" * (RELEASE_MAX - len(body))}).encode()
    assert len(body) == RELEASE_MAX
    assert parse_release(body)[0] == "v1.11"


def test_the_lookup_url_is_allowlisted_for_both_sources():
    for kind in SOURCES:
        assert validate_artifact_url(release_url(SOURCES[kind]["repo"])) is True


# ── The URL allowlist: without it this is an SSRF primitive ─────────────────


@pytest.mark.parametrize(
    "url",
    [
        API_URL,
        CODELOAD_URL,
        "https://api.github.com/repos/bunkerity/bunkerweb-plugins/releases/latest",
        "https://api.github.com/repos/bunkerity/bunkerweb-templates/releases/latest",
        "https://api.github.com/repos/bunkerity/bunkerweb-templates/tarball/0.6",
        "https://codeload.github.com/bunkerity/bunkerweb-templates/legacy.tar.gz/refs/tags/0.6",
    ],
)
def test_the_allowlisted_shapes_pass(url):
    assert validate_artifact_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        # Wrong scheme.
        "http://api.github.com/repos/bunkerity/bunkerweb-plugins/tarball/v1.11",
        "file:///etc/passwd",
        "ftp://api.github.com/repos/bunkerity/bunkerweb-plugins/x",
        "javascript:alert(1)",
        "//api.github.com/repos/bunkerity/bunkerweb-plugins/x",
        # Wrong host, including the near-misses.
        "https://evil.com/repos/bunkerity/bunkerweb-plugins/x",
        "https://api.github.com.evil.com/repos/bunkerity/bunkerweb-plugins/x",
        "https://evil-api.github.com/repos/bunkerity/bunkerweb-plugins/x",
        "https://codeload.github.com.evil.net/bunkerity/bunkerweb-plugins/x",
        "https://github.com/bunkerity/bunkerweb-plugins/releases/download/v1.11/x.tar.gz",
        "https://raw.githubusercontent.com/bunkerity/bunkerweb-plugins/main/catalog.json",
        # The two user-writable GitHub-operated hosts that killed the suffix premise.
        "https://gist.githubusercontent.com/attacker/aaa/raw/x",
        "https://camo.githubusercontent.com/aaa",
        # The release-asset hops of the retired manifest design: gone from the list, because this
        # flow never touches them and an unused entry is attack surface bought with nothing.
        "https://release-assets.githubusercontent.com/github-production-release-asset/1/2",
        "https://objects.githubusercontent.com/github-production-release-asset/1/2",
        # Right host, WRONG REPOSITORY. codeload serves every repo on GitHub, so the host alone
        # would let a redirect swap in a stranger's repository without leaving the allowlist.
        "https://codeload.github.com/attacker/bunkerweb-plugins/legacy.tar.gz/refs/tags/v1",
        "https://codeload.github.com/bunkerity/bunkerweb/legacy.tar.gz/refs/tags/v1",
        "https://codeload.github.com/bunkerity/bunkerweb-plugins-evil/legacy.tar.gz/refs/tags/v1",
        "https://api.github.com/repos/attacker/bunkerweb-plugins/tarball/v1",
        "https://api.github.com/repos/bunkerity/bunkerweb/tarball/v1",
        "https://api.github.com/users/bunkerity",
        # Credential smuggling: everything left of @ is userinfo, the real host is evil.com.
        "https://api.github.com@evil.com/repos/bunkerity/bunkerweb-plugins/x",
        "https://user:pass@api.github.com/repos/bunkerity/bunkerweb-plugins/x",
        # Explicit port.
        "https://api.github.com:8443/repos/bunkerity/bunkerweb-plugins/x",
        # Traversal, raw and percent-encoded.
        "https://api.github.com/repos/bunkerity/bunkerweb-plugins/../../other/x",
        "https://api.github.com/repos/bunkerity/bunkerweb-plugins/%2e%2e%2f%2e%2e%2fx",
        "https://api.github.com/repos/bunkerity/bunkerweb-plugins/%2E%2E/x",
        # A fragment: `urlsplit` drops everything after `#`, so a path check on the remainder
        # would be checking a string the server never sees.
        "https://api.github.com/repos/bunkerity/bunkerweb-plugins/tarball/v1#x",
        # The internal targets this list exists to make unreachable.
        "https://bw-api:8888/plugins",
        "https://127.0.0.1/",
        "https://169.254.169.254/latest/meta-data/",
        "https://[::1]/",
        # Junk.
        "",
        "not a url",
        None,
        123,
    ],
)
def test_everything_else_is_refused(url):
    assert validate_artifact_url(url) is False


def test_host_matching_is_case_insensitive_but_still_exact():
    assert validate_artifact_url(API_URL.replace("api.github.com", "API.GitHub.COM")) is True
    assert validate_artifact_url(API_URL.replace("api.github.com", "API.GitHub.COM.evil.net")) is False


def test_a_percent_encoded_separator_in_the_path_is_refused():
    # `%2f` decodes into a path separator without ever appearing as a literal `..` segment, so
    # neither traversal branch sees it -- only the count comparison does.
    assert validate_artifact_url("https://api.github.com/repos/bunkerity/bunkerweb-plugins/a%2fb") is False
    assert validate_artifact_url("https://codeload.github.com/bunkerity/bunkerweb-plugins/a%2Fb") is False
    # ...while the same escape in the QUERY is untouched: a redirect GitHub is entitled to hand
    # us can carry a signed query full of them.
    assert validate_artifact_url(CODELOAD_URL + "?sig=p%2Fq%2Br&rscd=attachment%3B+filename%3Dx") is True


def test_the_repository_prefix_is_a_path_prefix_not_a_substring():
    # `/repos/evil/x/repos/bunkerity/bunkerweb-plugins/` contains the prefix but does not start
    # with it, and startswith is what decides.
    assert validate_artifact_url("https://api.github.com/repos/evil/x/repos/bunkerity/bunkerweb-plugins/tarball/v1") is False


# ── The archive: one wrapper root, folder name == declared id ───────────────


def test_a_real_shaped_plugin_archive_enumerates():
    entries, errors = archive_entries(plugin_archive(ids=("clamav", "coraza")), "plugins")
    assert sorted(entries) == ["clamav", "coraza"] and errors == []
    assert entries["clamav"]["name"] == "Clamav"


def test_a_real_shaped_template_archive_enumerates():
    entries, errors = archive_entries(template_archive(ids=("nextcloud", "drupal")), "templates")
    assert sorted(entries) == ["drupal", "nextcloud"] and errors == []


def test_plugin_folders_are_not_looked_for_under_the_templates_subdir():
    # The two sources have different layouts and the depth is part of the contract: a template
    # folder must not register as a plugin, or one click would install a template as code.
    assert archive_entries(template_archive(), "plugins")[0] == {}
    assert archive_entries(plugin_archive(), "templates")[0] == {}


def test_a_declared_id_that_differs_from_the_folder_is_refused():
    # THE identity check. The declared id, not the folder name, is what the installer writes to
    # the filesystem and the database -- so a `clamav/` folder declaring `blacklist` must not
    # become an item under either name.
    entries, errors = archive_entries(plugin_archive(ids=("clamav",), declared="blacklist"), "plugins")
    assert entries == {} and any("blacklist" in e for e in errors)


@pytest.mark.parametrize("declared", [None, "", 42, True, ["clamav"], {"id": "clamav"}, "CLAMAV", "clamav "])
def test_a_non_matching_declared_id_of_any_type_is_refused(declared):
    assert archive_entries(plugin_archive(ids=("clamav",), declared=declared), "plugins")[0] == {}


@pytest.mark.parametrize(
    "bad_id",
    [
        "../../etc/passwd",
        "..",
        ".",
        "a/b",
        ".hidden",
        "-lead",
        "_lead",
        "CLAMAV",  # uppercase: catalogue ids are a strict subset of the API's own rx
        "clam.av",  # a dot is legal for the API and refused here on purpose
        "cl",
        "abc",  # 3 chars: the API's rx is {4,64}, so this used to render then fail at install
        "c" * 65,
        "clam av",
        "сlamav",  # Cyrillic es homoglyph
    ],
)
def test_a_hostile_folder_name_never_becomes_an_item(bad_id):
    entries, _ = archive_entries(plugin_archive(ids=(bad_id,)), "plugins")
    assert bad_id not in entries


@pytest.mark.parametrize("good_id", ["clamav", "abcd", "a" * 64, "a-b_c", "waf2", "pi-hole", "xen-orchestra"])
def test_legal_folder_names_survive(good_id):
    assert good_id in archive_entries(plugin_archive(ids=(good_id,)), "plugins")[0]


def test_one_bad_folder_does_not_black_out_the_catalogue():
    # A single malformed folder must not be able to deny service over every other item.
    payload = make_archive(
        {
            "clamav/plugin.json": dumps({"id": "clamav", "name": "ClamAV", "version": "1.11"}),
            "coraza/plugin.json": b"{ not json",
            "matrix/plugin.json": dumps({"id": "elsewhere", "name": "Matrix", "version": "1.11"}),
        }
    )
    entries, errors = archive_entries(payload, "plugins")
    assert sorted(entries) == ["clamav"] and len(errors) == 2


def test_a_deeper_plugin_json_is_not_a_root():
    # `clamav/vendor/plugin.json` is at depth 3; only depth 2 is an item for this source.
    payload = make_archive({"clamav/vendor/plugin.json": dumps({"id": "clamav"})})
    assert archive_entries(payload, "plugins")[0] == {}


def test_an_archive_with_more_than_one_root_is_refused():
    buf = BytesIO()
    with tar_open(fileobj=buf, mode="w:gz") as tar:
        for root in ("a", "b"):
            blob = dumps({"id": "clamav"}).encode()
            info = TarInfo(name=f"{root}/clamav/plugin.json")
            info.size = len(blob)
            tar.addfile(info, BytesIO(blob))
    assert archive_entries(buf.getvalue(), "plugins")[0] == {}


@pytest.mark.parametrize("payload", [b"", b"not a tar", None, "a string", b"\x1f\x8b" + b"\x00" * 64, 42])
def test_garbage_bytes_are_refused_rather_than_raising(payload):
    entries, errors = archive_entries(payload, "plugins")
    assert entries == {} and errors


def test_an_unknown_source_is_refused():
    assert archive_entries(plugin_archive(), "nope")[0] == {}


def test_a_root_that_is_itself_dotdot_cannot_yield_a_path(monkeypatch):
    """The input class the explicit `..` guard is the ONLY thing catching.

    An earlier revision of this file called that guard defence in depth on the grounds that
    `normpath` collapses `..` and the `startswith(prefix)` test then rejects the result. That
    reasoning silently assumes the root is a normal directory name. It is not given, it is derived
    from the member names -- and an archive whose members are all `../evil/...` has exactly ONE
    root, `".."`. The prefix becomes `"../"`, `"../evil/plugin.json".startswith("../")` is True,
    and `startswith` alone hands back `evil/plugin.json` for a member outside the root.
    """
    from app.models.plugin_catalog import _safe_relpath  # type: ignore

    names = ["../evil/plugin.json", "../evil/README.md"]
    assert archive_root(names) == "..", "the premise: this shape really does produce a single root"
    for name in names:
        assert _safe_relpath(name, "..") is None


@pytest.mark.parametrize("name", ["../evil/plugin.json", "..", "../..", "../x", "a/../../b"])
def test_no_member_name_escapes_its_root_whatever_the_root_is(name):
    from app.models.plugin_catalog import _safe_relpath  # type: ignore

    for root in ("bunkerity-bunkerweb-plugins-fb55b84", "..", ".", "a"):
        assert _safe_relpath(name, root) is None or not _safe_relpath(name, root).startswith("..")


def test_an_archive_rooted_outside_itself_enumerates_nothing():
    """End to end, not just the helper: the whole listing must come back empty."""
    buf = BytesIO()
    with tar_open(fileobj=buf, mode="w:gz") as tar:
        blob = dumps({"id": "clamav", "name": "ClamAV", "version": "1.11"}).encode()
        for name in ("../evil/clamav/plugin.json", "../evil/clamav/clamav.lua"):
            info = TarInfo(name=name)
            info.size = len(blob)
            tar.addfile(info, BytesIO(blob))
    # Nothing listed, and deliberately no per-item error: a member that fails `_safe_relpath` is
    # not "a broken plugin", it is not a member of this archive at all, and every real GitHub
    # archive has a couple of those (`pax_global_header`). The empty listing is what refuses --
    # `fetch_source` turns it into "<repo>@<tag> contains no plugins" one level up.
    entries, _ = archive_entries(buf.getvalue(), "plugins")
    assert entries == {}


def test_archive_root_needs_exactly_one():
    assert archive_root([f"{ROOT}/a", f"{ROOT}/b"]) == ROOT
    assert archive_root([f"{ROOT}/a", "other/b"]) is None
    assert archive_root([]) is None
    assert archive_root(["/absolute/a"]) is None


def test_an_oversized_metadata_member_does_not_expand_in_memory():
    # The ARCHIVE is capped in transfer, but gzip amplifies: a member can declare far more than
    # the transferred bytes suggest. An over-cap plugin.json is refused, not read.
    payload = make_archive({"clamav/plugin.json": b" " * (MEMBER_MAX + 1024) + b"{}"})
    entries, errors = archive_entries(payload, "plugins")
    assert entries == {} and errors


# ── The version gate: it fails CLOSED, on data upstream does not publish yet ─


def test_the_compatibility_map_drives_the_gate():
    compat = parse_compatibility(COMPAT.encode())
    assert compat["1.11"] == ["1.7.0", "1.7.1"]
    assert is_compatible("1.7.0", compat["1.11"]) is True
    assert is_compatible("1.7.2", compat["1.11"]) is False
    assert is_compatible("1.6.11", compat["1.8"]) is True


@pytest.mark.parametrize("supported", [None, [], "1.7.0", {}, 0, False, ["nonsense"], [None], [""], [123]])
def test_the_gate_fails_closed_on_anything_unusable(supported):
    assert is_compatible("1.7.0", supported) is False


@pytest.mark.parametrize("bw", [None, "", "unknown", "not-a-version", 1.7, [], "∞"])
def test_an_unresolvable_running_version_reads_as_INCOMPATIBLE(bw):
    # Deliberately the opposite stance to `is_newer_version_available`, whose docstring prefers a
    # false negative. There a parse failure costs a missed notification; here it costs running an
    # unvetted plugin as code in the UI process, in the worker and in nginx.
    assert is_compatible(bw, ["1.7.0"]) is False


def test_the_comparison_is_on_versions_not_strings():
    # "1.7.0" and "v1.7.0" are the same version; "1.7.0-rc1" is not.
    assert is_compatible("v1.7.0", ["1.7.0"]) is True
    assert is_compatible("1.7.0", ["1.7.0-rc1"]) is False


@pytest.mark.parametrize(
    "blob",
    [None, b"", b"not json", b"[]", b'"x"', b"null", dumps({"1.8": "not a list"}).encode(), dumps({"1.8": []}).encode(), dumps([1, 2]).encode()],
)
def test_an_unusable_compatibility_file_yields_nothing_and_therefore_installs_nothing(blob):
    compat = parse_compatibility(blob)
    assert compat == {} or all(v for v in compat.values())
    assert is_compatible("1.7.0", compat.get("1.11")) is False


def test_only_parseable_versions_survive_the_compatibility_map():
    compat = parse_compatibility(dumps({"1.8": ["1.6.0", "garbage", None, 42, "1.6.1"]}).encode())
    assert compat["1.8"] == ["1.6.0", "1.6.1"]


def test_the_real_repository_state_gates_everything_off_today():
    # The measured fact this whole design has to be honest about: `bunkerweb-plugins` has shipped
    # v1.9, v1.10 and v1.11 without adding a COMPATIBILITY.json line for any of them, and no line
    # anywhere names a 1.7.x. Reading that map therefore refuses every plugin. The catalogue says
    # so on each card rather than rendering an unexplained empty page.
    real_shaped = dumps({"1.8": ["1.6.0", "1.6.11"]})  # highest key upstream actually publishes
    entries, _ = archive_entries(plugin_archive(ids=("clamav",), version="1.11"), "plugins")
    items = build_items("plugins", entries, parse_compatibility(real_shaped.encode()))
    assert items[0]["supported"] == []
    assert item_compatible("plugins", "1.7.0", items[0]) is False


def test_one_upstream_line_lights_the_catalogue_up_with_no_code_change():
    entries, _ = archive_entries(plugin_archive(ids=("clamav",), version="1.11"), "plugins")
    items = build_items("plugins", entries, parse_compatibility(COMPAT.encode()))
    assert items[0]["supported"] == ["1.7.0", "1.7.1"]
    assert item_compatible("plugins", "1.7.0", items[0]) is True


def test_templates_are_not_version_gated_because_upstream_declares_nothing():
    # PO ruling 2026-08-24. There is no version field and no compatibility file in the templates
    # repository, so a bound invented here would assert a compatibility its publisher never
    # stated. `create_template` validating every setting id against the live Settings table is
    # the semantic gate, and it is a check against THIS build rather than a declared range.
    entries, _ = archive_entries(template_archive(), "templates")
    item = build_items("templates", entries, {})[0]
    assert item["supported"] == []
    assert item_compatible("templates", "1.7.0", item) is True
    assert item_compatible("templates", "unknown", item) is True


def test_the_two_halves_are_switched_by_one_flag():
    """The flag's VALUE only. Deliberately not the whole story.

    This test stays green even if a route stops consulting `item_compatible` entirely, which is a
    drift that actually happened once. What the flag is *worth* is pinned where it can break:
    `test_templates_catalog_routes.py::test_flipping_the_flag_makes_the_TEMPLATE_ROUTE_refuse`
    flips it and asserts the server refuses, not that the button vanished.
    """
    assert SOURCES["plugins"]["version_gate"] is True
    assert SOURCES["templates"]["version_gate"] is False


def test_item_compatible_survives_a_junk_item():
    for junk in (None, "x", 42, [], {}):
        assert item_compatible("plugins", "1.7.0", junk) is False


# ── Building the listing ───────────────────────────────────────────────────


def test_unknown_metadata_keys_never_reach_the_listing():
    payload = make_archive(
        {"clamav/plugin.json": dumps({"id": "clamav", "name": "ClamAV", "version": "1.11", "settings": {"X": 1}, "jobs": [{"name": "j"}], "exec": "rm -rf /"})}
    )
    entries, _ = archive_entries(payload, "plugins")
    item = build_items("plugins", entries, {})[0]
    assert set(item) == {"id", "name", "description", "version", "supported", "homepage"}


def test_the_listing_is_built_fresh_not_aliased_to_the_parsed_metadata():
    entries, _ = archive_entries(plugin_archive(), "plugins")
    build_items("plugins", entries, {})[0]["id"] = "mutated"
    assert build_items("plugins", entries, {})[0]["id"] == "clamav"


def test_overlong_display_text_is_clipped_not_dropped():
    # A long description is cosmetic; dropping the item over it would hide a plugin for a typo.
    payload = make_archive({"clamav/plugin.json": dumps({"id": "clamav", "name": "N" * 500, "description": "D" * 5000, "version": "1.11"})})
    item = build_items("plugins", archive_entries(payload, "plugins")[0], {})[0]
    assert len(item["name"]) == 64 and len(item["description"]) == 512


@pytest.mark.parametrize("name", [None, 42, [], {}, "", "   "])
def test_a_missing_or_junk_name_falls_back_to_the_id(name):
    payload = make_archive({"clamav/plugin.json": dumps({"id": "clamav", "name": name, "version": "1.11"})})
    assert build_items("plugins", archive_entries(payload, "plugins")[0], {})[0]["name"] == "clamav"


def test_the_homepage_is_built_here_not_read_from_the_metadata():
    # It becomes an href, and a link read out of a downloaded JSON file is a link an upstream
    # commit gets to choose. This one it does not: two trusted inputs, a repo constant and a
    # folder name that already passed CATALOG_ID_RX.
    payload = make_archive({"clamav/plugin.json": dumps({"id": "clamav", "name": "ClamAV", "version": "1.11", "homepage": "javascript:alert(1)"})})
    item = build_items("plugins", archive_entries(payload, "plugins")[0], {})[0]
    assert item["homepage"] == "https://github.com/bunkerity/bunkerweb-plugins/tree/main/clamav"


def test_the_homepage_shape_differs_by_source_because_the_layouts_do():
    assert item_homepage("plugins", "clamav") == "https://github.com/bunkerity/bunkerweb-plugins/tree/main/clamav"
    assert item_homepage("templates", "nextcloud") == "https://github.com/bunkerity/bunkerweb-templates/tree/main/templates/nextcloud"


def test_the_listing_is_ordered_deterministically():
    entries, _ = archive_entries(plugin_archive(ids=("webhook", "clamav", "matrix")), "plugins")
    assert [i["id"] for i in build_items("plugins", entries, {})] == ["clamav", "matrix", "webhook"]


# ── The digest gate: a git tag is NOT immutable ─────────────────────────────


def test_a_matching_digest_passes_and_a_one_bit_change_does_not():
    from common_utils import bytes_hash  # type: ignore

    payload = plugin_archive()
    digest = bytes_hash(payload, algorithm="sha256")
    assert verify_digest(payload, digest) is True
    assert verify_digest(payload + b"\x00", digest) is False


@pytest.mark.parametrize("expected", [None, "", "a" * 63, "a" * 65, "A" * 64, "g" * 64, 123, " " + "a" * 63, ["a" * 64]])
def test_a_digest_that_is_not_64_lowercase_hex_never_passes(expected):
    # Uppercase is refused rather than folded: normalising at this boundary would mean the value
    # compared is not the value that was recorded.
    assert verify_digest(plugin_archive(), expected) is False


@pytest.mark.parametrize("payload", [None, "a string", 42, [], {}])
def test_a_non_bytes_payload_never_passes(payload):
    from common_utils import bytes_hash  # type: ignore

    assert verify_digest(payload, bytes_hash(b"", algorithm="sha256")) is False


def test_a_tag_re_cut_under_our_feet_is_caught():
    # The whole reason this gate exists after the re-scope: a tag can be force-moved, and
    # codeload will then serve different bytes for the same URL. What was listed and what is
    # installed must be the same bytes, and this is the only thing that says so.
    from common_utils import bytes_hash  # type: ignore

    listed = plugin_archive(ids=("clamav",), version="1.11")
    re_cut = plugin_archive(ids=("clamav",), version="6.66")
    assert verify_digest(re_cut, bytes_hash(listed, algorithm="sha256")) is False


# ── Repacking: exactly one plugin, by construction ─────────────────────────


def test_only_the_requested_folder_survives_the_repack():
    # The upstream archive holds nine plugins and BOTH install branches in routers/plugins.py
    # loop over every plugin.json they find, so handing it over would install all nine on one
    # click. It is never handed over.
    payload, problem = repack_plugin(plugin_archive(ids=("clamav", "coraza", "matrix")), "clamav")
    assert problem is None
    with tar_open(fileobj=BytesIO(payload)) as tar:
        names = tar.getnames()
    assert names and all(n == "clamav" or n.startswith("clamav/") for n in names)
    assert not any("coraza" in n or "matrix" in n for n in names)


def test_the_repacked_archive_still_declares_the_right_id():
    payload, _ = repack_plugin(plugin_archive(ids=("clamav",)), "clamav")
    with tar_open(fileobj=BytesIO(payload)) as tar:
        meta = tar.extractfile("clamav/plugin.json").read()
    assert b'"id": "clamav"' in meta


def test_a_folder_that_is_not_there_is_refused():
    payload, problem = repack_plugin(plugin_archive(ids=("clamav",)), "coraza")
    assert payload is None and "coraza" in problem


@pytest.mark.parametrize("bad", ["../etc", "a/b", "", None, "CLAMAV", "cl", "clamav\n", "clam.av", "c" * 65])
def test_a_hostile_id_never_reaches_the_repack(bad):
    payload, problem = repack_plugin(plugin_archive(), bad)
    # "invalid plugin id", not "no folder named ...": a hostile id must be refused because it is
    # illegal, not because it happened not to be in this particular archive. Asserting only that
    # it refused let "delete the id check" survive the first mutation run.
    assert payload is None and "invalid plugin id" in problem


def test_a_prefix_match_is_not_a_folder_match():
    # `clamav-evil/` starts with `clamav` as a string. It is a different folder and must not be
    # swept into the tarball.
    payload, _ = repack_plugin(plugin_archive(ids=("clamav", "clamav-evil")), "clamav")
    with tar_open(fileobj=BytesIO(payload)) as tar:
        assert not any("clamav-evil" in n for n in tar.getnames())


def test_a_symlink_member_is_dropped_rather_than_copied():
    # A symlink is how an archive reaches a path its member names never mention.
    buf = BytesIO()
    with tar_open(fileobj=buf, mode="w:gz") as tar:
        blob = dumps({"id": "clamav", "name": "ClamAV", "version": "1.11"}).encode()
        info = TarInfo(name=f"{ROOT}/clamav/plugin.json")
        info.size = len(blob)
        tar.addfile(info, BytesIO(blob))
        link = TarInfo(name=f"{ROOT}/clamav/escape")
        link.type = __import__("tarfile").SYMTYPE
        link.linkname = "../../../../etc/passwd"
        tar.addfile(link)
    payload, problem = repack_plugin(buf.getvalue(), "clamav")
    assert problem is None
    with tar_open(fileobj=BytesIO(payload)) as tar:
        assert [m.name for m in tar.getmembers() if not m.isfile()] == []
        assert "clamav/escape" not in tar.getnames()


def test_upstream_member_metadata_is_rebuilt_not_carried():
    # uid/gid/uname/gname/mtime all come from whoever cut the release and every one of them lands
    # in the tar the API extracts.
    buf = BytesIO()
    with tar_open(fileobj=buf, mode="w:gz") as tar:
        blob = dumps({"id": "clamav", "name": "ClamAV", "version": "1.11"}).encode()
        info = TarInfo(name=f"{ROOT}/clamav/plugin.json")
        info.size = len(blob)
        info.uid, info.gid, info.uname, info.gname, info.mtime, info.mode = 1234, 5678, "root", "root", 2_000_000_000, 0o666
        tar.addfile(info, BytesIO(blob))
    payload, _ = repack_plugin(buf.getvalue(), "clamav")
    with tar_open(fileobj=BytesIO(payload)) as tar:
        member = tar.getmember("clamav/plugin.json")
    assert member.uid == 0 and member.gid == 0 and member.mtime == 0 and member.mode == 0o644


def test_the_executable_bit_is_the_one_permission_carried():
    buf = BytesIO()
    with tar_open(fileobj=buf, mode="w:gz") as tar:
        for name, mode in ((f"{ROOT}/clamav/plugin.json", 0o644), (f"{ROOT}/clamav/jobs/run.py", 0o755)):
            blob = dumps({"id": "clamav", "name": "ClamAV", "version": "1.11"}).encode() if name.endswith("plugin.json") else b"#!/usr/bin/env python3\n"
            info = TarInfo(name=name)
            info.size = len(blob)
            info.mode = mode
            tar.addfile(info, BytesIO(blob))
    payload, _ = repack_plugin(buf.getvalue(), "clamav")
    with tar_open(fileobj=BytesIO(payload)) as tar:
        assert tar.getmember("clamav/jobs/run.py").mode == 0o755
        assert tar.getmember("clamav/plugin.json").mode == 0o644


def test_an_oversized_member_stops_the_repack():
    payload = plugin_archive(ids=("clamav",), extra={"clamav/big.bin": b"\x00" * (MEMBER_MAX + 1)})
    out, problem = repack_plugin(payload, "clamav")
    assert out is None and "big.bin" in problem


@pytest.mark.parametrize("payload", [b"", b"not a tar", None, 42])
def test_repacking_garbage_is_refused_rather_than_raising(payload):
    out, problem = repack_plugin(payload, "clamav")
    assert out is None and problem


def test_the_extraction_budget_is_a_running_total_not_a_per_member_check():
    # The 8 MB transfer cap bounds COMPRESSED bytes and gzip amplifies, so many members each
    # under MEMBER_MAX can still expand past what we are willing to hold.
    chunk = MEMBER_MAX - 1024
    extra = {f"clamav/pad{i}.bin": b"\x00" * chunk for i in range(EXTRACT_MAX // chunk + 2)}
    out, problem = repack_plugin(plugin_archive(ids=("clamav",), extra=extra), "clamav")
    assert out is None and "expands past" in problem


# ── Templates: the payload upstream ships is NOT the payload the API takes ──


def test_a_template_is_assembled_from_its_folder():
    data, problem = template_payload(template_archive(configs=["modsec-crs/nextcloud_fp.conf"]), "nextcloud")
    assert problem is None
    assert set(data) == {"id", "name", "settings", "steps", "configs"}
    # Upstream ships a PATH; `_prepare_template_entities` requires an OBJECT with the data in it.
    assert data["configs"] == [{"type": "modsec-crs", "name": "nextcloud_fp", "data": "# modsec-crs/nextcloud_fp.conf\n"}]


def test_a_template_with_no_configs_is_fine():
    data, problem = template_payload(template_archive(ids=("drupal",)), "drupal")
    assert problem is None and data["configs"] == []


def test_a_template_that_is_not_there_is_refused():
    assert template_payload(template_archive(ids=("drupal",)), "nextcloud")[0] is None


def test_the_declared_id_is_re_checked_on_the_bytes_being_installed():
    payload = make_archive({"templates/nextcloud/template.json": dumps({"id": "wordpress", "settings": {}, "steps": [{"title": "x"}]})}, root=TROOT)
    data, problem = template_payload(payload, "nextcloud")
    assert data is None and "wordpress" in problem


@pytest.mark.parametrize(
    "reference",
    [
        "../../../etc/passwd",
        "modsec-crs/../../../etc/passwd.conf",
        "/etc/passwd.conf",
        "modsec-crs/x.conf/../../y.conf",
        "modsec-crs//x.conf",
        "x.conf",  # no type segment
        "modsec-crs/x",  # no .conf
        "modsec-crs/x.conf\n",
        "MODSEC/x.conf",
        "modsec-crs/.hidden.conf",
        "modsec-crs/x.CONF",
        "",
        None,
        42,
        ["modsec-crs/x.conf"],
    ],
)
def test_a_hostile_config_reference_never_becomes_a_path(reference):
    payload = make_archive(
        {"templates/nextcloud/template.json": dumps({"id": "nextcloud", "settings": {}, "steps": [{"title": "x"}], "configs": [reference]})},
        root=TROOT,
    )
    data, problem = template_payload(payload, "nextcloud")
    # Again the reason, not just the refusal: a traversing reference cannot resolve to a member
    # anyway, so "missing from the archive" would pass with the pattern check deleted.
    assert data is None and "invalid config reference" in problem


def test_a_reference_naming_a_file_that_is_not_in_the_archive_is_refused():
    payload = make_archive(
        {"templates/nextcloud/template.json": dumps({"id": "nextcloud", "settings": {}, "steps": [{"title": "x"}], "configs": ["modsec/absent.conf"]})},
        root=TROOT,
    )
    assert template_payload(payload, "nextcloud")[0] is None


def test_the_config_list_is_bounded():
    refs = [f"modsec/c{i}.conf" for i in range(64)]
    payload = make_archive(
        {"templates/nextcloud/template.json": dumps({"id": "nextcloud", "settings": {}, "steps": [{"title": "x"}], "configs": refs})}, root=TROOT
    )
    assert template_payload(payload, "nextcloud")[0] is None


@pytest.mark.parametrize("bad", ["../etc", "a/b", "", None, "NEXTCLOUD", "ab"])
def test_a_hostile_template_id_never_reaches_the_archive(bad):
    data, problem = template_payload(template_archive(), bad)
    assert data is None and "invalid template id" in problem


@pytest.mark.parametrize(
    "meta",
    [
        {"id": "nextcloud", "settings": "not a dict", "steps": []},
        {"id": "nextcloud", "settings": {}, "steps": "not a list"},
        {"id": "nextcloud", "settings": {}},
        {"id": "nextcloud", "steps": []},
    ],
)
def test_a_structurally_wrong_template_is_refused(meta):
    payload = make_archive({"templates/nextcloud/template.json": dumps(meta)}, root=TROOT)
    assert template_payload(payload, "nextcloud")[0] is None


def test_a_config_blob_that_is_not_utf8_is_refused():
    payload = make_archive(
        {
            "templates/nextcloud/template.json": dumps({"id": "nextcloud", "settings": {}, "steps": [{"title": "x"}], "configs": ["modsec/x.conf"]}),
            "templates/nextcloud/configs/modsec/x.conf": b"\xff\xfe\x00binary",
        },
        root=TROOT,
    )
    assert template_payload(payload, "nextcloud")[0] is None


def test_archive_file_addresses_relative_to_the_wrapper_root():
    payload = make_archive({"COMPATIBILITY.json": COMPAT, "clamav/plugin.json": dumps({"id": "clamav"})})
    assert archive_file(payload, "COMPATIBILITY.json") == COMPAT.encode()
    assert archive_file(payload, "clamav/plugin.json") is not None
    assert archive_file(payload, "absent.json") is None
    assert archive_file(payload, f"{ROOT}/COMPATIBILITY.json") is None  # already relative


# ── Freshness: the window is closed at BOTH ends ────────────────────────────


def _stamp(**delta):
    return (datetime.now().astimezone() - timedelta(**delta)).isoformat()


def test_a_fresh_stamp_is_not_stale():
    assert is_stale(_stamp(minutes=5)) is False


def test_a_stamp_older_than_the_max_age_is_stale():
    assert is_stale(_stamp(seconds=int(CATALOG_MAX_AGE.total_seconds()) + 60)) is True


def test_a_future_stamp_is_stale():
    # A one-sided `age > MAX_AGE` passes a negative age, so a stamp dated 2037 read as
    # permanently fresh and re-opened exactly the hole the gate exists to close. ui_data.json is
    # a file other processes write, and a clock that jumps backwards produces the same shape.
    assert is_stale((datetime.now().astimezone() + timedelta(days=3650)).isoformat()) is True


@pytest.mark.parametrize("stamp", [None, "", "not a date", 42, [], {}, "2026-13-45T99:99:99"])
def test_an_unreadable_stamp_counts_as_stale(stamp):
    assert is_stale(stamp) is True


# ── Reading the cache: ui_data.json is a file other processes write ─────────


def _cached(plugins=None, templates=None, fetched_at=None, tag="v1.11", sha="a" * 64):
    return {
        "fetched_at": fetched_at or datetime.now().astimezone().isoformat(),
        "catalog": {
            "plugins": {"tag": tag, "sha256": sha, "items": plugins if plugins is not None else [{"id": "clamav", "name": "ClamAV", "supported": ["1.7.0"]}]},
            "templates": {"tag": "0.6", "sha256": "b" * 64, "items": templates or [{"id": "nextcloud", "name": "Nextcloud", "supported": []}]},
        },
    }


@pytest.mark.parametrize(
    "blob",
    [
        None,
        42,
        "a string",
        [],
        {},
        {"catalog": None},
        {"catalog": "x"},
        {"catalog": []},
        {"catalog": {"plugins": "x"}},
        {"catalog": {"plugins": {"items": "x"}}},
        {"catalog": {"plugins": {"items": [1, 2, "three"]}}},
        {"fetched_at": 42, "catalog": {}},
    ],
)
def test_a_crafted_ui_data_blob_never_blows_up_the_page(blob):
    catalog, fetched_at = read_cached(blob)
    assert set(catalog) == set(SOURCES)
    assert all(isinstance(section["items"], list) for section in catalog.values())
    assert fetched_at is None or isinstance(fetched_at, str)


@pytest.mark.parametrize("tag", ["../evil", "a/b", "", None, 42, "x" * 200, "tag\n"])
def test_a_crafted_tag_in_the_cache_is_scrubbed(tag):
    # The tag is interpolated into the install-time archive URL. A cache file is not a trust
    # boundary we get to skip just because we wrote it last.
    catalog, _ = read_cached(_cached(tag=tag))
    assert catalog["plugins"]["tag"] == ""


@pytest.mark.parametrize("sha", ["zz", "A" * 64, "a" * 63, "", None, 42])
def test_a_crafted_digest_in_the_cache_is_scrubbed(sha):
    catalog, _ = read_cached(_cached(sha=sha))
    assert catalog["plugins"]["sha256"] == ""


def test_a_scrubbed_tag_or_digest_leaves_nothing_installable():
    # Both install routes refuse when either is empty -- that is what makes scrubbing a safe
    # response instead of a silent downgrade.
    item, section = find_item(_cached(tag="../evil"), "plugins", "clamav")
    assert item is not None and section["tag"] == ""


def test_find_item_resolves_through_the_cache_and_returns_its_section():
    item, section = find_item(_cached(), "plugins", "clamav")
    assert item["id"] == "clamav" and section["tag"] == "v1.11" and section["sha256"] == "a" * 64


def test_find_item_on_an_absent_id_returns_nothing_at_all():
    assert find_item(_cached(), "plugins", "nope") == (None, None)
    assert find_item(_cached(), "plugins", "nextcloud") == (None, None)  # right id, wrong half


# ── The rendered view ───────────────────────────────────────────────────────


def test_the_view_marks_rather_than_hides_an_incompatible_item():
    # Hiding makes the catalogue look empty and generates support tickets; showing the reason
    # makes the constraint explain itself. With upstream declaring nothing today, this is the
    # difference between a blank page and a page that says why.
    view = build_catalog_view("plugins", _cached(plugins=[{"id": "clamav", "supported": []}]), set(), "1.7.0")
    assert view["catalog_available"] is True
    assert [i["compatible"] for i in view["catalog_items"]] == [False]


def test_an_installed_item_is_dropped_not_greyed():
    view = build_catalog_view("plugins", _cached(), {"clamav"}, "1.7.0")
    assert view["catalog_items"] == [] and view["catalog_available"] is True


def test_the_view_carries_the_release_tag_for_the_notice():
    assert build_catalog_view("plugins", _cached(), set(), "1.7.0")["catalog_tag"] == "v1.11"


def test_an_empty_half_reports_unavailable():
    view = build_catalog_view("plugins", _cached(plugins=[]), set(), "1.7.0")
    assert view == {"catalog_items": [], "catalog_available": False, "catalog_stale": False, "catalog_tag": ""}


def test_the_view_reports_staleness_without_hiding_anything():
    view = build_catalog_view("plugins", _cached(fetched_at=_stamp(days=30)), set(), "1.7.0")
    assert view["catalog_stale"] is True and len(view["catalog_items"]) == 1


def test_the_kill_switch_empties_the_view_entirely(monkeypatch):
    monkeypatch.setenv("USE_PLUGIN_CATALOG", "no")
    assert build_catalog_view("plugins", _cached(), set(), "1.7.0")["catalog_available"] is False


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


# ── The caps, on transferred bytes, never on a header ───────────────────────


class _FakeResponse:
    """The slice of `requests.Response` that `_read_capped` touches."""

    def __init__(self, chunks):
        self._chunks = chunks

    def iter_content(self, chunk_size=None):  # noqa: ARG002 - signature match
        yield from self._chunks


def test_a_body_at_the_cap_is_read():
    from app.models.plugin_catalog import _read_capped  # type: ignore

    assert _read_capped(_FakeResponse([b"x" * 100]), 100) == b"x" * 100


def test_a_body_one_byte_over_the_cap_is_refused():
    # The read is cut as soon as the accumulated length passes the cap, so an unbounded body
    # cannot be buffered while we wait to find out how big it was.
    from app.models.plugin_catalog import _read_capped  # type: ignore

    assert _read_capped(_FakeResponse([b"x" * 101]), 100) is None


def test_the_cap_is_enforced_across_chunks_not_per_chunk():
    from app.models.plugin_catalog import _read_capped  # type: ignore

    assert _read_capped(_FakeResponse([b"x" * 60, b"x" * 60]), 100) is None


def test_a_lying_content_length_buys_nothing():
    # Content-Length is never consulted -- it is a claim, not a measurement. The real archive
    # responses are chunked and carry no Content-Length at all (measured 2026-08-24).
    from app.models.plugin_catalog import _read_capped  # type: ignore

    assert _read_capped(_FakeResponse([b"x" * 1024] * 20), 4096) is None


def test_empty_chunks_do_not_confuse_the_counter():
    from app.models.plugin_catalog import _read_capped  # type: ignore

    assert _read_capped(_FakeResponse([b"a", b"", b"b"]), 10) == b"ab"


def test_the_caps_are_ordered_the_way_the_pipeline_needs():
    # Transfer < what a member may expand to < the whole extraction budget. If MEMBER_MAX ever
    # crept above EXTRACT_MAX the running total would be unreachable.
    assert RELEASE_MAX < ARCHIVE_MAX <= EXTRACT_MAX
    assert MEMBER_MAX < EXTRACT_MAX


# ── Redirects are walked by hand so every hop is re-validated ───────────────


class _Redirect:
    is_redirect = True
    is_permanent_redirect = False
    status_code = 302

    def __init__(self, target):
        self.headers = {"Location": target}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Ok:
    is_redirect = False
    is_permanent_redirect = False
    status_code = 200

    def __init__(self, body):
        self._body = body

    def iter_content(self, chunk_size=None):  # noqa: ARG002 - signature match
        yield self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_the_measured_one_hop_chain_is_walked(monkeypatch):
    import app.models.plugin_catalog as pc  # type: ignore

    seen = []

    def fake_get(url, **kwargs):
        assert kwargs["allow_redirects"] is False, "requests must never follow a hop unchecked"
        assert kwargs["stream"] is True, "the cap must bound the transfer, not a buffered body"
        seen.append(url)
        return _Redirect(CODELOAD_URL) if url == API_URL else _Ok(b"payload")

    monkeypatch.setattr(pc, "get", fake_get)
    assert pc._get_allowlisted(API_URL, timeout=3, cap=1024) == b"payload"
    assert seen == [API_URL, CODELOAD_URL]


def test_an_off_allowlist_redirect_is_refused(monkeypatch):
    import app.models.plugin_catalog as pc  # type: ignore

    monkeypatch.setattr(pc, "get", lambda url, **k: _Redirect("https://evil.example/payload"))
    with pytest.raises(ValueError):
        pc._get_allowlisted(API_URL, timeout=3, cap=1024)


def test_a_redirect_loop_terminates(monkeypatch):
    import app.models.plugin_catalog as pc  # type: ignore

    monkeypatch.setattr(pc, "get", lambda url, **k: _Redirect(API_URL))
    with pytest.raises(ValueError, match="too many redirects"):
        pc._get_allowlisted(API_URL, timeout=3, cap=1024)


def test_a_redirect_without_a_target_is_refused(monkeypatch):
    import app.models.plugin_catalog as pc  # type: ignore

    class _Headless(_Redirect):
        def __init__(self):
            self.headers = {}

    monkeypatch.setattr(pc, "get", lambda url, **k: _Headless())
    with pytest.raises(ValueError):
        pc._get_allowlisted(API_URL, timeout=3, cap=1024)


def test_a_non_200_is_refused(monkeypatch):
    import app.models.plugin_catalog as pc  # type: ignore

    class _NotFound(_Ok):
        status_code = 404

    monkeypatch.setattr(pc, "get", lambda url, **k: _NotFound(b""))
    with pytest.raises(ValueError, match="404"):
        pc._get_allowlisted(API_URL, timeout=3, cap=1024)


@pytest.mark.parametrize("tag", ["../../etc/passwd", "a/b", "", None, "v1.11\n", "x" * 65])
def test_fetch_archive_refuses_a_hostile_tag_without_issuing_a_request(monkeypatch, tag):
    import app.models.plugin_catalog as pc  # type: ignore

    monkeypatch.setattr(pc, "get", lambda *a, **k: pytest.fail("a request was issued for an invalid tag"))
    # `match=` is the point: the allowlist would refuse most of these a moment later anyway, so
    # only the message distinguishes "the tag was rejected" from "the URL happened not to match".
    with pytest.raises(ValueError, match="invalid tag"):
        pc.fetch_archive(SOURCES["plugins"]["repo"], tag)
