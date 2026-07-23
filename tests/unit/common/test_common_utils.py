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
    detect_local_plugin_icon,
    dict_to_frozenset,
    effective_cpu_count,
    file_hash,
    is_newer_version_available,
    normalize_bunkerweb_version,
    normalize_check_value,
    normalize_list_value,
    normalize_select_value,
    plugin_tar_exclude,
    plugin_tar_filter,
    resolve_plugin_icon,
    safe_zip_extractall,
    trim_scalar_value,
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


class TestNormalizeListValue:
    """multivalue/multiselect storage canonicalization (B1): trim items, drop empties,
    rejoin with a single separator. Only cleans the stored form — no acceptance change."""

    @pytest.mark.parametrize(
        "raw,canon",
        [
            (" 10.0.0.1 10.0.0.2 ", "10.0.0.1 10.0.0.2"),
            ("10.0.0.1  10.0.0.2", "10.0.0.1 10.0.0.2"),  # collapse the empty from the double space
            ("  a   b   c  ", "a b c"),
            ("single", "single"),
            ("", ""),
            ("   ", ""),  # only separators -> empty list
            ("a b c", "a b c"),  # already canonical
        ],
    )
    def test_space_separated(self, raw, canon):
        assert normalize_list_value(raw, " ") == canon

    def test_custom_separator(self):
        # split on ',', strip each item, drop the trailing empty, rejoin with bare ','.
        assert normalize_list_value("a , b ,c,", ",") == "a,b,c"

    @pytest.mark.parametrize("raw", [None, 1, ["a"], {"x": 1}])
    def test_non_string_passes_through(self, raw):
        assert normalize_list_value(raw, " ") == raw

    def test_empty_separator_passthrough(self):
        assert normalize_list_value("a  b", "") == "a  b"

    def test_idempotent(self):
        once = normalize_list_value(" a  b ", " ")
        assert normalize_list_value(once, " ") == once


class TestTrimScalarValue:
    """A2: surrounding whitespace stripped from scalar values at ingestion, except for the
    NO_TRIM_TYPES (password/file/text where whitespace can be meaningful), non-strings, and
    unknown/empty types. check/size/duration/list strip internally — net-new effect on
    number/select."""

    @pytest.mark.parametrize("stype", ["number", "select"])
    @pytest.mark.parametrize("raw,canon", [(" 8080 ", "8080"), ("\topt1\n", "opt1"), ("x", "x")])
    def test_scalar_types_trimmed(self, stype, raw, canon):
        assert trim_scalar_value(stype, raw) == canon

    @pytest.mark.parametrize("stype", ["password", "file", "text"])
    def test_excluded_types_not_trimmed(self, stype):
        # Surrounding whitespace can be semantically meaningful for these types.
        assert trim_scalar_value(stype, "  secret  ") == "  secret  "

    @pytest.mark.parametrize("stype,raw,canon", [("check", " on ", "on"), ("size", " 64m ", "64m"), ("duration", " 30s ", "30s")])
    def test_already_stripping_types_redundant_but_correct(self, stype, raw, canon):
        # Their own helpers re-strip downstream; trimming here is harmless and outcome-preserving.
        assert trim_scalar_value(stype, raw) == canon

    @pytest.mark.parametrize("raw", [None, 1, 0, True, ["x"], {"a": 1}])
    def test_non_string_passes_through(self, raw):
        assert trim_scalar_value("number", raw) == raw

    @pytest.mark.parametrize("stype", [None, ""])
    def test_unknown_or_empty_type_not_trimmed(self, stype):
        # An unresolved schema (no type) must never be wrongly trimmed.
        assert trim_scalar_value(stype, "  x  ") == "  x  "

    def test_empty_after_trim(self):
        assert trim_scalar_value("number", "   ") == ""

    def test_idempotent(self):
        assert trim_scalar_value("number", trim_scalar_value("number", " 8 ")) == "8"


class TestNormalizeSelectValue:
    """A3: opt-in case-insensitive select/multiselect — casefold a value to the declared
    option casing. No-op unless case_insensitive; no-match returns the original (regex rejects)."""

    OPTS = ["modern", "intermediate", "old"]

    @pytest.mark.parametrize("raw,canon", [("Modern", "modern"), ("MODERN", "modern"), ("OLD", "old"), ("modern", "modern")])
    def test_single_casefolded(self, raw, canon):
        assert normalize_select_value(raw, self.OPTS, case_insensitive=True) == canon

    def test_single_no_match_returns_original(self):
        # "Modernn" matches no option -> returned verbatim so the schema regex rejects it.
        assert normalize_select_value("Modernn", self.OPTS, case_insensitive=True) == "Modernn"

    def test_opt_out_is_noop(self):
        assert normalize_select_value("Modern", self.OPTS, case_insensitive=False) == "Modern"

    def test_empty_options_is_noop(self):
        assert normalize_select_value("Modern", [], case_insensitive=True) == "Modern"

    @pytest.mark.parametrize("raw", [None, 1, ["modern"], {"a": 1}])
    def test_non_string_passes_through(self, raw):
        assert normalize_select_value(raw, self.OPTS, case_insensitive=True) == raw

    def test_multi_per_item(self):
        # multiselect: each token mapped independently, rejoined with the separator.
        assert normalize_select_value("MODERN OLD", self.OPTS, multi=True, separator=" ", case_insensitive=True) == "modern old"

    def test_multi_mixed_match_and_miss(self):
        assert normalize_select_value("Modern nope", self.OPTS, multi=True, separator=" ", case_insensitive=True) == "modern nope"

    def test_multi_empty_separator_returns_unchanged(self):
        # Can't tokenize an empty-separator multiselect (e.g. MODSECURITY_SEC_AUDIT_LOG_PARTS).
        assert normalize_select_value("BCFH", ["b", "c"], multi=True, separator="", case_insensitive=True) == "BCFH"

    def test_casefold_collision_first_wins(self):
        # Deterministic on a lossy option set: the first declaration wins.
        assert normalize_select_value("a", ["A", "a"], case_insensitive=True) == "A"

    def test_idempotent(self):
        once = normalize_select_value("Modern", self.OPTS, case_insensitive=True)
        assert normalize_select_value(once, self.OPTS, case_insensitive=True) == once


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


class TestDetectLocalPluginIcon:
    """First allowlisted icon file present directly in a dir, in priority order, else None."""

    def test_priority_order_icon_svg_wins(self, tmp_path):
        (tmp_path / "logo.png").write_bytes(b"x")
        (tmp_path / "icon.svg").write_bytes(b"<svg/>")
        assert detect_local_plugin_icon(tmp_path) == "icon.svg"

    def test_falls_back_down_the_list(self, tmp_path):
        (tmp_path / "logo.png").write_bytes(b"x")
        assert detect_local_plugin_icon(tmp_path) == "logo.png"

    def test_empty_dir_is_none(self, tmp_path):
        assert detect_local_plugin_icon(tmp_path) is None

    def test_missing_dir_is_none(self, tmp_path):
        assert detect_local_plugin_icon(tmp_path / "nope") is None

    def test_ignores_subdir_and_directory_named_like_icon(self, tmp_path):
        (tmp_path / "ui").mkdir()
        (tmp_path / "ui" / "icon.svg").write_bytes(b"<svg/>")  # nested, not root-level
        (tmp_path / "logo.svg").mkdir()  # a directory, not a regular file
        assert detect_local_plugin_icon(tmp_path) is None


class TestResolvePluginIcon:
    """Effective Plugins.icon marker across the blob path, the core dir_path path and back-compat."""

    def _blob(self, tmp_path, files):
        d = tmp_path / "arc"
        d.mkdir()
        (d / "plugin.json").write_text('{"id":"p"}')
        for name, content in files.items():
            (d / name).write_bytes(content)
        return create_plugin_tar_gz(d, arc_root=d.name).getvalue()

    # ── blob path (external/ui/pro) — unchanged by dir_path ──────────────────────────────
    def test_blob_shipped_file_wins_over_field(self, tmp_path):
        blob = self._blob(tmp_path, {"icon.svg": b"<svg/>"})
        assert resolve_plugin_icon(blob, "bx-shield") == "@file/icon.svg"

    def test_blob_without_file_keeps_field_verbatim_never_promoted(self, tmp_path):
        # plugin.json names icon.svg but the archive lacks it -> not promoted to an @file marker.
        blob = self._blob(tmp_path, {"readme.md": b"x"})
        assert resolve_plugin_icon(blob, "icon.svg") == "icon.svg"

    # ── core dir_path path ───────────────────────────────────────────────────────────────
    def test_dir_detected_promotion(self, tmp_path):
        (tmp_path / "icon.svg").write_bytes(b"<svg/>")
        assert resolve_plugin_icon(None, None, dir_path=tmp_path) == "@file/icon.svg"

    def test_dir_explicit_override_honored_when_present(self, tmp_path):
        # icon.svg also present, but the field explicitly names logo.png which really exists.
        (tmp_path / "icon.svg").write_bytes(b"<svg/>")
        (tmp_path / "logo.png").write_bytes(b"x")
        assert resolve_plugin_icon(None, "logo.png", dir_path=tmp_path) == "@file/logo.png"

    def test_dir_no_promotion_when_field_file_absent(self, tmp_path):
        # field names an allowlisted file that is NOT on disk, and nothing else is either ->
        # the string is returned verbatim, never an @file marker that would 404.
        assert resolve_plugin_icon(None, "icon.svg", dir_path=tmp_path) == "icon.svg"

    def test_dir_detected_wins_over_absent_field_file(self, tmp_path):
        # field names logo.png (absent) but icon.svg is present -> detection promotes icon.svg.
        (tmp_path / "icon.svg").write_bytes(b"<svg/>")
        assert resolve_plugin_icon(None, "logo.png", dir_path=tmp_path) == "@file/icon.svg"

    def test_dir_verbatim_fallthrough(self, tmp_path):
        # boxicon class, empty dir -> nothing to detect -> returned verbatim.
        assert resolve_plugin_icon(None, "bx-shield", dir_path=tmp_path) == "bx-shield"

    def test_dir_none_field_empty_dir_is_none(self, tmp_path):
        assert resolve_plugin_icon(None, None, dir_path=tmp_path) is None

    # ── back-compat: no data, no dir_path ────────────────────────────────────────────────
    def test_backcompat_field_allowlisted_promoted(self):
        assert resolve_plugin_icon(None, "icon.svg") == "@file/icon.svg"

    def test_backcompat_boxicon_verbatim(self):
        assert resolve_plugin_icon(None, "bx-shield") == "bx-shield"

    def test_backcompat_none_is_none(self):
        assert resolve_plugin_icon(None, None) is None
