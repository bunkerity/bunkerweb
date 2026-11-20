"""A restored archive is verified link by link on disk, on every runtime.

The member list is pre-validated from the archive metadata, which cannot see where a link ends up
once earlier members have been written: `a/b -> ..` then `c -> a/b/..` reads as the root and lands
outside it. Python's `tar` filter does not look at link targets either, and the RHEL 9 packages
run Python 3.9, which has no filter at all. So each member is extracted after its parent and its
link target have been resolved on disk, the tree is checked again once it is complete, and one bad
member refuses the whole archive.
"""

import tarfile
from io import BytesIO

import pytest

import cache_restore  # type: ignore
from common_utils import safe_tar_extractall  # type: ignore


class _NoFilterRuntime(tarfile.TarFile):
    """The tarfile of Python 3.9 on RHEL 9: no `filter` parameter on the extraction calls."""

    def extractall(self, path=".", members=None, *, numeric_owner=False):
        return super().extractall(path, members, numeric_owner=numeric_owner, filter="fully_trusted")

    def extract(self, member, path="", set_attrs=True, *, numeric_owner=False):
        return super().extract(member, path, set_attrs=set_attrs, numeric_owner=numeric_owner, filter="fully_trusted")


RUNTIMES = pytest.mark.parametrize("runtime", [tarfile.TarFile, _NoFilterRuntime], ids=["native-filter", "no-filter"])


def _extract(tar, destination):
    safe_tar_extractall(tar, destination, links="contained")


def _member(name, kind, linkname="", mode=0o644, data=b""):
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = linkname
    info.mode = mode
    info.size = len(data)
    return info, data


def _directory(name, mode=0o755):
    return _member(name, tarfile.DIRTYPE, mode=mode)


def _file(name, data=b"payload", mode=0o644):
    return _member(name, tarfile.REGTYPE, data=data, mode=mode)


def _symlink(name, target):
    return _member(name, tarfile.SYMTYPE, target)


def _hardlink(name, target):
    return _member(name, tarfile.LNKTYPE, target)


def _tar(entries, runtime=tarfile.TarFile):
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for info, data in entries:
            tar.addfile(info, BytesIO(data) if data else None)
    buffer.seek(0)
    return runtime(fileobj=buffer, mode="r")


def _gz(entries) -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for info, data in entries:
            tar.addfile(info, BytesIO(data) if data else None)
    return buffer.getvalue()


# Each link reads as contained from the member list, and escapes once the earlier members exist.
CHAIN = [_symlink("a/b", ".."), _symlink("c", "a/b/..")]
LATE_TARGET = [_symlink("a/b", ".."), _symlink("l", "d/.."), _symlink("d", "a/b")]


@RUNTIMES
@pytest.mark.parametrize("entries", [CHAIN, LATE_TARGET], ids=["chain", "target-made-hostile-later"])
def test_a_link_that_ends_up_outside_the_root_refuses_the_archive(tmp_path, runtime, entries):
    root = tmp_path / "root"
    root.mkdir()
    (root / "a").mkdir()

    with pytest.raises(ValueError, match="outside target directory|could not be"):
        _extract(_tar([_directory("a"), *entries], runtime), root)


@RUNTIMES
def test_a_hardlink_through_a_link_to_the_parent_is_refused(tmp_path, runtime):
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "outside.txt").write_text("not ours")

    with pytest.raises(ValueError, match="outside target directory|could not be"):
        _extract(_tar([_directory("a"), _symlink("a/b", ".."), _hardlink("h", "a/b/../outside.txt")], runtime), root)

    assert not (root / "h").exists()


@RUNTIMES
def test_a_member_cannot_be_written_through_a_symlinked_parent(tmp_path, runtime):
    root = tmp_path / "root"
    root.mkdir()

    with pytest.raises(ValueError, match="symlinked parent|could not be"):
        _extract(_tar([_directory("real"), _symlink("alias", "real"), _file("alias/f")], runtime), root)


@RUNTIMES
def test_the_links_a_certificate_cache_carries_are_kept(tmp_path, runtime):
    entries = [
        _directory("archive"),
        _directory("archive/example.com"),
        _file("archive/example.com/cert1.pem", b"chain"),
        _directory("live"),
        _directory("live/example.com"),
        _symlink("live/example.com/cert.pem", "../../archive/example.com/cert1.pem"),
        _file("archive/example.com/cert2.pem", b"second"),
        _hardlink("copy.pem", "archive/example.com/cert2.pem"),
    ]

    _extract(_tar(entries, runtime), tmp_path)

    link = tmp_path / "live" / "example.com" / "cert.pem"
    assert link.is_symlink()
    assert link.read_bytes() == b"chain"
    assert (tmp_path / "copy.pem").read_bytes() == b"second"


@RUNTIMES
def test_a_private_key_directory_stays_private(tmp_path, runtime):
    entries = [_directory("live", 0o700), _file("live/privkey.pem", b"key", 0o600)]

    _extract(_tar(entries, runtime), tmp_path)

    assert (tmp_path / "live").stat().st_mode & 0o777 == 0o700
    assert (tmp_path / "live" / "privkey.pem").stat().st_mode & 0o777 == 0o600


@RUNTIMES
def test_group_and_other_write_bits_of_a_directory_are_dropped(tmp_path, runtime):
    _extract(_tar([_directory("open", 0o777)], runtime), tmp_path)

    assert (tmp_path / "open").stat().st_mode & 0o022 == 0


def test_a_hostile_archive_leaves_the_previous_cache_directory_alone(tmp_path):
    target = tmp_path / "cache" / "letsencrypt"
    target.mkdir(parents=True)
    (target / "privkey.pem").write_bytes(b"the only copy")

    with pytest.raises(ValueError):
        cache_restore.restore_directory(target, _gz([_directory("a"), *CHAIN]))

    assert (target / "privkey.pem").read_bytes() == b"the only copy"
    assert sorted(path.name for path in target.parent.iterdir()) == ["letsencrypt"], "a staging directory was left behind"


def test_a_valid_certificate_cache_still_restores_through_the_shared_helper(tmp_path):
    target = tmp_path / "cache" / "letsencrypt"
    data = _gz([_directory("archive"), _file("archive/cert1.pem", b"chain"), _symlink("live.pem", "archive/cert1.pem")])

    cache_restore.restore_directory(target, data)

    assert (target / "live.pem").is_symlink()
    assert (target / "live.pem").read_bytes() == b"chain"
