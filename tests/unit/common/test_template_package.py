"""The template package core: one parser for every template that arrives from outside the DB.

Pure functions, no DB: what `create_template` then checks against the live settings is not
repeated here. The folder-layout cases the catalogue relies on are also pinned through its
wrapper in `tests/unit/ui/test_plugin_catalog.py`, which is the proof that the catalogue's
behaviour did not change when the parser moved.
"""

from io import BytesIO
from json import dumps
from tarfile import SYMTYPE, TarInfo, open as tar_open
from zipfile import ZipFile

import pytest

from template_package import (  # type: ignore
    MAX_TEMPLATE_CONFIGS,
    PACKAGE_FORMAT,
    PACKAGE_MAX,
    parse_package,
    template_from_archive,
    template_from_folder,
)

META = {"id": "nextcloud", "name": "Nextcloud", "settings": {"SERVER_NAME": "www.example.com"}, "steps": [{"title": "Step", "settings": ["SERVER_NAME"]}]}


def reader(files):
    return lambda relative: files.get(relative)


def folder(meta=None, configs=None):
    meta = dict(META if meta is None else meta)
    files = {}
    if configs:
        meta["configs"] = list(configs)
        files.update({f"configs/{ref}": f"# {ref}\n".encode() for ref in configs})
    files["template.json"] = dumps(meta).encode()
    return files


def package(**over):
    pkg = {"format": PACKAGE_FORMAT, **META, "configs": [{"type": "modsec_crs", "name": "nextcloud", "data": "SecRule x"}]}
    pkg.update(over)
    return pkg


def tar_bytes(files, mode="w:gz"):
    buf = BytesIO()
    with tar_open(fileobj=buf, mode=mode) as tar:
        for name, blob in files.items():
            info = TarInfo(name=name)
            info.size = len(blob)
            tar.addfile(info, BytesIO(blob))
    return buf.getvalue()


def zip_bytes(files):
    buf = BytesIO()
    with ZipFile(buf, "w") as archive:
        for name, blob in files.items():
            archive.writestr(name, blob)
    return buf.getvalue()


def prefixed(files, root="nextcloud"):
    return {f"{root}/{name}": blob for name, blob in files.items()}


# ── The folder layout ───────────────────────────────────────────────────────


def test_a_folder_becomes_the_create_template_payload():
    data, problem = template_from_folder(reader(folder(configs=["modsec-crs/fp.conf"])), "nextcloud")
    assert problem is None
    assert data == {
        "id": "nextcloud",
        "name": "Nextcloud",
        "settings": META["settings"],
        "steps": META["steps"],
        "configs": [{"type": "modsec-crs", "name": "fp", "data": "# modsec-crs/fp.conf\n"}],
    }


def test_the_declared_id_must_be_the_folder_name():
    data, problem = template_from_folder(reader(folder(meta=META | {"id": "wordpress"})), "nextcloud")
    assert data is None and "wordpress" in problem


@pytest.mark.parametrize(
    "reference", ["../x.conf", "modsec-crs/../../etc/passwd.conf", "/etc/x.conf", "x.conf", "modsec-crs/x", "modsec-crs/x.conf\n", None, 42]
)
def test_a_hostile_reference_is_refused_before_it_is_read(reference):
    asked = []

    def read(relative):
        asked.append(relative)
        return folder(meta=META | {"configs": [reference]})["template.json"] if relative == "template.json" else b""

    data, problem = template_from_folder(read, "nextcloud")
    assert data is None and "invalid config reference" in problem
    assert asked == ["template.json"]


def test_a_missing_config_and_a_missing_template_are_refused():
    assert template_from_folder(reader({"template.json": dumps(META | {"configs": ["modsec/absent.conf"]}).encode()}), "nextcloud")[0] is None
    assert "contains no template" in template_from_folder(reader({}), "nextcloud")[1]


@pytest.mark.parametrize("bad", ["", "../etc", "a/b", ".hidden", "x\n", None, 42])
def test_a_hostile_id_is_refused(bad):
    data, problem = template_from_folder(reader(folder()), bad)
    assert data is None and "invalid template id" in problem


def test_a_long_name_is_clipped_and_a_missing_one_falls_back_to_the_id():
    assert template_from_folder(reader(folder(meta=META | {"name": "n" * 300})), "nextcloud")[0]["name"] == "n" * 64
    assert template_from_folder(reader(folder(meta={k: v for k, v in META.items() if k != "name"})), "nextcloud")[0]["name"] == "nextcloud"


# ── The package format ──────────────────────────────────────────────────────


@pytest.mark.parametrize("encode", [lambda p: p, lambda p: dumps(p), lambda p: dumps(p).encode()])
def test_a_package_parses_from_an_object_text_or_bytes(encode):
    data, problem = parse_package(encode(package()))
    assert problem is None
    assert data == {"id": "nextcloud", "name": "Nextcloud", "settings": META["settings"], "steps": META["steps"], "configs": package()["configs"]}


def test_locales_and_unknown_keys_are_dropped():
    data, _ = parse_package(package(locales={"fr": {"name": "x"}}, method="core", plugin_id="evil"))
    assert set(data) == {"id", "name", "settings", "steps", "configs"}


def test_a_config_type_is_accepted_as_stored_or_as_spelt_upstream():
    for config_type in ("modsec_crs", "modsec-crs", "server-http"):
        assert parse_package(package(configs=[{"type": config_type, "name": "x", "data": ""}]))[1] is None


@pytest.mark.parametrize(
    "over",
    [
        {"format": "bunkerweb-template/2"},
        {"format": None},
        {"id": "../x"},
        {"id": None},
        {"name": ""},
        {"name": "  "},
        {"name": "n" * 257},
        {"name": 3},
        {"settings": []},
        {"steps": {}},
        {"configs": "x"},
        {"configs": [{"type": "modsec", "name": "x"}]},
        {"configs": [{"type": "modsec", "name": "../x", "data": ""}]},
        {"configs": [{"type": "MODSEC", "name": "x", "data": ""}]},
        {"configs": [{"type": "modsec", "name": "x", "data": 1}]},
        {"configs": ["modsec/x.conf"]},
        {"configs": [{"type": "modsec", "name": f"c{i}", "data": ""} for i in range(MAX_TEMPLATE_CONFIGS + 1)]},
    ],
)
def test_a_malformed_package_is_refused_whole(over):
    data, problem = parse_package(package(**over))
    assert data is None and problem


@pytest.mark.parametrize("raw", [b"not json", b"\xff", b"[]", "null", 42, None])
def test_garbage_is_refused(raw):
    assert parse_package(raw)[0] is None


def test_the_package_file_is_capped():
    raw = dumps(package(settings={"X": "y" * PACKAGE_MAX})).encode()
    data, problem = parse_package(raw)
    assert data is None and str(PACKAGE_MAX) in problem


# ── An uploaded folder archive ──────────────────────────────────────────────


@pytest.mark.parametrize("pack", [tar_bytes, lambda f: tar_bytes(f, "w:xz"), zip_bytes])
def test_an_uploaded_folder_reads_like_the_catalogue(pack):
    files = folder(configs=["modsec-crs/fp.conf"])
    data, problem = template_from_archive(pack(prefixed(files)))
    assert problem is None
    assert data == template_from_folder(reader(files), "nextcloud")[0]


def test_the_folder_name_must_match_the_declared_id():
    data, problem = template_from_archive(tar_bytes(prefixed(folder(), root="wordpress")))
    assert data is None and "nextcloud" in problem


def test_an_archive_with_two_folders_is_refused():
    blob = tar_bytes(prefixed(folder()) | prefixed(folder(meta=META | {"id": "other"}), root="other"))
    assert "exactly one template folder" in template_from_archive(blob)[1]


def test_a_traversing_member_is_never_what_the_parser_reads():
    # `nextcloud/../nextcloud/template.json` is not the exact name `nextcloud/template.json`, so
    # the parser never sees it and the folder has no template.json at all.
    blob = tar_bytes({"nextcloud/../nextcloud/template.json": dumps(META).encode(), "nextcloud/x": b""})
    assert "contains no template" in template_from_archive(blob)[1]


def test_a_symlinked_template_json_is_not_followed():
    buf = BytesIO()
    with tar_open(fileobj=buf, mode="w:gz") as tar:
        info = TarInfo(name="nextcloud/template.json")
        info.type = SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info)
        sibling = TarInfo(name="nextcloud/README.md")
        tar.addfile(sibling, BytesIO(b""))
    assert "contains no template" in template_from_archive(buf.getvalue())[1]


def test_the_expanded_template_is_capped_not_just_the_upload():
    files = folder(configs=["modsec/big.conf"])
    files["configs/modsec/big.conf"] = b"#" * (PACKAGE_MAX + 1)
    blob = tar_bytes(prefixed(files))
    assert len(blob) < PACKAGE_MAX  # it compresses: the upload cap alone would let it through
    data, problem = template_from_archive(blob)
    assert data is None and "expands past" in problem


def test_an_archive_declaring_too_much_stops_the_walk():
    blob = tar_bytes(prefixed({f"pad{i}": b"\x00" * PACKAGE_MAX for i in range(9)}))
    assert len(blob) < PACKAGE_MAX
    assert template_from_archive(blob)[1] == "the archive is too large"


@pytest.mark.parametrize("blob", [b"", b"not an archive", None, 42])
def test_garbage_uploads_are_refused(blob):
    data, problem = template_from_archive(blob)
    assert data is None and problem
