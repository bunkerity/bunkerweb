"""common_utils — pure helpers: hashing, version compare, tar/zip safety, plugin tar.

No DB, no app package; ``common_utils`` is already on the path via the root conftest.
These run once (not engine-parametrized).
"""

import tarfile
import zipfile
from hashlib import sha256, sha512
from io import BytesIO

import pytest

from common_utils import (  # type: ignore
    _validate_tar_members,
    bytes_hash,
    create_plugin_tar_gz,
    dict_to_frozenset,
    effective_cpu_count,
    file_hash,
    is_newer_version_available,
    normalize_bunkerweb_version,
    normalize_check_value,
    plugin_tar_exclude,
    plugin_tar_filter,
    safe_zip_extractall,
)


class TestNormalizeCheckValue:
    """Boolean ('check' type) value canonicalization to 'yes'/'no'.

    The helper is type-agnostic; callers apply it only to type=='check' settings.
    Known truthy/falsy tokens map to 'yes'/'no'; anything else passes through
    unchanged so the setting's ^(yes|no)$ regex still rejects it.
    """

    @pytest.mark.parametrize(
        "raw",
        ["yes", "y", "true", "t", "on", "1", "enable", "enabled", "YES", "True", "ON", "Enabled", "  on  ", "\tTRUE\n"],
    )
    def test_truthy_tokens_map_to_yes(self, raw):
        assert normalize_check_value(raw) == "yes"

    @pytest.mark.parametrize(
        "raw",
        ["no", "n", "false", "f", "off", "0", "disable", "disabled", "NO", "False", "OFF", "Disabled", "  off  ", "\tFALSE\n"],
    )
    def test_falsy_tokens_map_to_no(self, raw):
        assert normalize_check_value(raw) == "no"

    @pytest.mark.parametrize("raw", ["maybe", "", "2", "yess", "ye s", "y e s", "enabledd", "auto"])
    def test_unknown_passes_through_unchanged(self, raw):
        # Unknown tokens are returned verbatim so the regex validator rejects them.
        assert normalize_check_value(raw) == raw

    @pytest.mark.parametrize("raw", [None, 1, 0, True, ["yes"], {"a": 1}])
    def test_non_string_passes_through_unchanged(self, raw):
        assert normalize_check_value(raw) == raw

    def test_idempotent_on_canonical(self):
        assert normalize_check_value(normalize_check_value("true")) == "yes"
        assert normalize_check_value("yes") == "yes"
        assert normalize_check_value("no") == "no"


class TestHashing:
    def test_bytes_hash_str_bytes_bytesio_equivalent(self):
        expected = sha512(b"abc").hexdigest()
        assert bytes_hash("abc") == expected
        assert bytes_hash(b"abc") == expected
        bio = BytesIO(b"abc")
        assert bytes_hash(bio) == expected
        assert bio.tell() == 0  # helper rewinds the buffer

    def test_bytes_hash_algorithm(self):
        assert bytes_hash(b"abc", algorithm="sha256") == sha256(b"abc").hexdigest()

    def test_file_hash(self, tmp_path):
        f = tmp_path / "x.bin"
        f.write_bytes(b"hello world")
        assert file_hash(f) == sha512(b"hello world").hexdigest()


class TestVersion:
    def test_normalize(self):
        assert normalize_bunkerweb_version("v1.6.9~rc2") == "1.6.9-rc2"
        assert normalize_bunkerweb_version("  1.6.9  ") == "1.6.9"

    @pytest.mark.parametrize(
        "cur,latest,expected",
        [
            ("1.0.0", "1.0.1", True),
            ("1.0.1", "1.0.0", False),
            ("1.0.0", "1.0.0", False),
            ("1.6.9~rc1", "1.6.9~rc2", True),
            ("garbage", "1.0.0", False),  # unparseable -> safe False
        ],
    )
    def test_is_newer(self, cur, latest, expected):
        assert is_newer_version_available(cur, latest) is expected


class TestDictToFrozenset:
    def test_list_sorted_tuple(self):
        assert dict_to_frozenset([3, 1, 2]) == (1, 2, 3)

    def test_dict(self):
        fs = dict_to_frozenset({"a": 1, "b": [2, 1]})
        assert ("a", 1) in fs
        assert ("b", (1, 2)) in fs

    def test_scalar_passthrough(self):
        assert dict_to_frozenset("x") == "x"


class TestPluginTar:
    @pytest.mark.parametrize("path", ["foo/__pycache__/x.py", "a.pyc", "b/.DS_Store", "x/.git/config"])
    def test_exclude_true(self, path):
        assert plugin_tar_exclude(path) is True

    def test_exclude_false_for_normal_nonexistent(self):
        # non-existent normal file: the is_file()/readable check short-circuits -> not excluded
        assert plugin_tar_exclude("plugin/myfile.py") is False

    def test_filter_normalizes_metadata(self):
        ti = tarfile.TarInfo(name="plugin/file.py")
        ti.mtime, ti.uid, ti.gid = 12345, 1000, 1000
        out = plugin_tar_filter(ti)
        assert out is not None
        assert (out.mtime, out.uid, out.gid, out.uname, out.gname) == (0, 0, 0, "root", "root")

    def test_filter_drops_excluded(self):
        assert plugin_tar_filter(tarfile.TarInfo(name="plugin/__pycache__/x.pyc")) is None

    def test_create_plugin_tar_gz_is_deterministic(self, tmp_path):
        d = tmp_path / "plug"
        d.mkdir()
        (d / "a.txt").write_text("hi")
        assert create_plugin_tar_gz(d).getvalue() == create_plugin_tar_gz(d).getvalue()


class TestEffectiveCpuCount:
    def test_returns_positive_int(self):
        n = effective_cpu_count()
        assert isinstance(n, int) and n >= 1


class TestTarZipSafety:
    def test_validate_rejects_absolute_path(self):
        with pytest.raises(ValueError):
            _validate_tar_members([tarfile.TarInfo(name="/etc/passwd")])

    def test_validate_rejects_traversal(self):
        with pytest.raises(ValueError):
            _validate_tar_members([tarfile.TarInfo(name="../escape")])

    def test_validate_rejects_symlink_when_disallowed(self):
        m = tarfile.TarInfo(name="link")
        m.type = tarfile.SYMTYPE
        m.linkname = "target"
        with pytest.raises(ValueError):
            _validate_tar_members([m], allow_symlinks=False)

    def test_validate_allows_clean_member(self):
        _validate_tar_members([tarfile.TarInfo(name="plugin/file.py")])  # no raise

    def test_safe_zip_rejects_traversal(self, tmp_path):
        z = tmp_path / "evil.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("../escape.txt", "x")
        with zipfile.ZipFile(z) as zf:
            with pytest.raises(ValueError):
                safe_zip_extractall(zf, tmp_path / "out")

    def test_safe_zip_extracts_clean(self, tmp_path):
        z = tmp_path / "ok.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("a/b.txt", "hi")
        out = tmp_path / "out"
        out.mkdir()
        with zipfile.ZipFile(z) as zf:
            safe_zip_extractall(zf, out)
        assert (out / "a" / "b.txt").read_text() == "hi"
