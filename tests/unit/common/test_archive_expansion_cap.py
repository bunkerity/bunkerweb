"""`safe_zip_extractall` / `safe_tar_extractall` refuse an archive that expands past a size or
member budget, before writing anything.

They blocked traversal only: a 50 MiB plugin download (the `EXTERNAL_PLUGIN_URLS` cap) or a UI
upload made of zeros deflates ~1000:1 and filled the disk. The budget is checked from the archive
metadata, which bounds what extraction can write: `zipfile` stops a member at its declared
`file_size`, and a tar member is exactly `size` bytes.
"""

import tarfile
import zipfile
from io import BytesIO

import pytest

import common_utils  # type: ignore
from common_utils import safe_tar_extractall, safe_zip_extractall  # type: ignore


def _zip(files):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


def _tar(files):
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, BytesIO(data))
    buffer.seek(0)
    return tarfile.open(fileobj=buffer, mode="r:gz")


BOMB = {"plugin/plugin.json": b"{}", "plugin/zeros.bin": b"\0" * 4096}
MANY = {f"plugin/f{index}": b"x" for index in range(10)}


@pytest.mark.parametrize(("build", "extract"), [(_zip, safe_zip_extractall), (_tar, safe_tar_extractall)])
def test_an_archive_expanding_past_the_size_budget_is_refused_whole(tmp_path, monkeypatch, build, extract):
    monkeypatch.setattr(common_utils, "MAX_ARCHIVE_EXTRACTED_BYTES", 1024, raising=False)
    out = tmp_path / "out"
    out.mkdir()

    with pytest.raises(ValueError, match="expands to more than"):
        extract(build(BOMB), out)

    assert list(out.iterdir()) == [], "a refused archive left files behind"


@pytest.mark.parametrize(("build", "extract"), [(_zip, safe_zip_extractall), (_tar, safe_tar_extractall)])
def test_an_archive_with_too_many_members_is_refused_whole(tmp_path, monkeypatch, build, extract):
    monkeypatch.setattr(common_utils, "MAX_ARCHIVE_MEMBERS", 5, raising=False)
    out = tmp_path / "out"
    out.mkdir()

    with pytest.raises(ValueError, match="more than 5 members"):
        extract(build(MANY), out)

    assert list(out.iterdir()) == []


@pytest.mark.parametrize(("build", "extract"), [(_zip, safe_zip_extractall), (_tar, safe_tar_extractall)])
def test_an_archive_within_budget_still_extracts(tmp_path, monkeypatch, build, extract):
    monkeypatch.setattr(common_utils, "MAX_ARCHIVE_EXTRACTED_BYTES", 8192, raising=False)
    monkeypatch.setattr(common_utils, "MAX_ARCHIVE_MEMBERS", 10, raising=False)

    extract(build(BOMB), tmp_path)
    extract(build(MANY), tmp_path / "many")

    assert (tmp_path / "plugin" / "zeros.bin").stat().st_size == 4096
    assert len(list((tmp_path / "many" / "plugin").iterdir())) == 10


def test_the_default_budget_fits_the_official_plugin_set_with_headroom():
    """bunkerweb-plugins v1.12 (the `EXTERNAL_PLUGIN_URLS` example) expands to 1.27 MB in 265
    members; the budget must never be what refuses a real plugin set."""
    assert common_utils.MAX_ARCHIVE_EXTRACTED_BYTES >= 100 * 1_270_051
    assert common_utils.MAX_ARCHIVE_MEMBERS >= 100 * 265


def test_the_members_argument_is_what_gets_budgeted(tmp_path, monkeypatch):
    """letsencrypt/ui/actions.py extracts a chosen subset: only that subset counts."""
    monkeypatch.setattr(common_utils, "MAX_ARCHIVE_EXTRACTED_BYTES", 1024, raising=False)
    tar = _tar(BOMB)
    small = [member for member in tar.getmembers() if member.name.endswith("plugin.json")]

    safe_tar_extractall(tar, tmp_path, members=small)

    assert (tmp_path / "plugin" / "plugin.json").exists()
    assert not (tmp_path / "plugin" / "zeros.bin").exists()


def test_the_sqlite_backup_restore_opts_out_of_the_budget(tmp_path, monkeypatch):
    """backup.py clears the database before it unzips the dump: a refusal there would lose it."""
    monkeypatch.setattr(common_utils, "MAX_ARCHIVE_EXTRACTED_BYTES", 1024)

    safe_zip_extractall(_zip(BOMB), tmp_path, capped=False)

    assert (tmp_path / "plugin" / "zeros.bin").stat().st_size == 4096
