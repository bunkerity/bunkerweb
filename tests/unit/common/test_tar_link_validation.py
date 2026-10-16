"""`_validate_tar_members` / `safe_tar_extractall` judge links the way tar resolves them.

A symlink target resolves from the member's parent directory, a hardlink target from the
extraction root. Checking both from the parent let `d/x -> ../c` pass as a hardlink although tar
resolves it to `<root>/../c`. The native filter is chosen by attribute and by the signature of the
extraction call, and a `TypeError` is never answered by extracting again without the filter.
"""

import tarfile
from io import BytesIO

import pytest

from common_utils import _validate_tar_members, safe_tar_extractall  # type: ignore


def _link(name, linkname, kind):
    member = tarfile.TarInfo(name)
    member.type = kind
    member.linkname = linkname
    return member


def _hard(name, linkname):
    return _link(name, linkname, tarfile.LNKTYPE)


def _sym(name, linkname):
    return _link(name, linkname, tarfile.SYMTYPE)


def _archive(members, tar_class=tarfile.TarFile):
    """A readable tar holding a regular file `a/b` and `members` after it."""
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name in ("a", "c"):
            directory = tarfile.TarInfo(name)
            directory.type = tarfile.DIRTYPE
            directory.mode = 0o755
            tar.addfile(directory)
        data = b"payload"
        regular = tarfile.TarInfo("a/b")
        regular.size = len(data)
        tar.addfile(regular, BytesIO(data))
        for member in members:
            tar.addfile(member)
    buffer.seek(0)
    return tar_class(fileobj=buffer, mode="r")


def test_hardlink_to_a_file_under_the_root_is_accepted():
    _validate_tar_members([_hard("x", "a/b")], allow_symlinks=True)


def test_hardlink_in_a_subdirectory_resolves_from_the_root():
    _validate_tar_members([_hard("c/x", "a/b")], allow_symlinks=True)


@pytest.mark.parametrize(("name", "linkname"), [("d/x", "../c"), ("a/b/x", "../../c"), ("x", "../c")])
def test_hardlink_that_escapes_the_root_is_refused(name, linkname):
    with pytest.raises(ValueError, match="links outside target directory"):
        _validate_tar_members([_hard(name, linkname)], allow_symlinks=True)


def test_symlink_to_a_sibling_through_the_parent_is_accepted():
    _validate_tar_members([_sym("d/x", "../c")], allow_symlinks=True)


@pytest.mark.parametrize(("name", "linkname"), [("x", "../c"), ("d/x", "../../c"), ("d/e/x", "../../../c")])
def test_symlink_that_escapes_the_root_is_refused(name, linkname):
    with pytest.raises(ValueError, match="links outside target directory"):
        _validate_tar_members([_sym(name, linkname)], allow_symlinks=True)


def test_extraction_keeps_a_valid_hardlink(tmp_path):
    safe_tar_extractall(_archive([_hard("x", "a/b")]), tmp_path, links="contained")

    assert (tmp_path / "x").read_bytes() == b"payload"


def test_extraction_refuses_an_escaping_hardlink_before_writing(tmp_path):
    with pytest.raises(ValueError, match="links outside target directory"):
        safe_tar_extractall(_archive([_hard("c/x", "../c")]), tmp_path, links="contained")

    assert not (tmp_path / "a").exists()


def test_extraction_refuses_an_escaping_symlink_before_writing(tmp_path):
    with pytest.raises(ValueError, match="links outside target directory"):
        safe_tar_extractall(_archive([_sym("x", "../c")]), tmp_path, links="contained")

    assert not (tmp_path / "a").exists()


class _RejectsFilter(tarfile.TarFile):
    """A runtime whose extraction call fails on the `filter` keyword, like a bad keyword would."""

    calls = 0

    def extractall(self, path=".", members=None, *, numeric_owner=False, filter=None):
        type(self).calls += 1
        raise TypeError("unexpected keyword argument")

    def extract(self, member, path="", set_attrs=True, *, numeric_owner=False, filter=None):
        type(self).calls += 1
        raise TypeError("unexpected keyword argument")


def test_a_type_error_is_not_answered_by_extracting_without_the_filter(tmp_path):
    _RejectsFilter.calls = 0

    with pytest.raises(TypeError, match="unexpected keyword"):
        safe_tar_extractall(_archive([], _RejectsFilter), tmp_path)

    assert _RejectsFilter.calls == 1
    assert list(tmp_path.iterdir()) == []


class _NoFilterRuntime(tarfile.TarFile):
    """The tarfile of Python 3.9 on RHEL 9: no `filter` parameter anywhere."""

    seen = []

    def extractall(self, path=".", members=None, *, numeric_owner=False):
        type(self).seen.append(("extractall", {}))
        return super().extractall(path, members, numeric_owner=numeric_owner, filter=None)

    def extract(self, member, path="", set_attrs=True, *, numeric_owner=False):
        type(self).seen.append(("extract", {}))
        return super().extract(member, path, set_attrs=set_attrs, numeric_owner=numeric_owner, filter=None)


def test_a_runtime_without_the_filter_parameter_is_called_without_it(tmp_path):
    _NoFilterRuntime.seen = []

    safe_tar_extractall(_archive([_hard("x", "a/b")], _NoFilterRuntime), tmp_path, links="contained")

    assert _NoFilterRuntime.seen
    assert (tmp_path / "x").read_bytes() == b"payload"
