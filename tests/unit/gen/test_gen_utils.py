"""gen/utils.py has_permissions — POSIX rwx bit checking.

Loaded by file path (not ``import utils``) because both ``src/common/gen/utils.py`` and
``src/api/app/utils.py`` would be a top-level ``utils`` in a combined run. The function
inspects mode bits (not real access), so results are deterministic even under root.
"""

import importlib.util
from pathlib import Path

_GEN_UTILS = Path(__file__).resolve().parents[3] / "src" / "common" / "gen" / "utils.py"
_spec = importlib.util.spec_from_file_location("bw_gen_utils", _GEN_UTILS)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
has_permissions = _mod.has_permissions


class TestHasPermissions:
    def test_readable_writable(self, tmp_path):
        f = tmp_path / "f"
        f.write_text("x")
        f.chmod(0o600)
        assert has_permissions(str(f), ["R", "W"]) is True
        assert has_permissions(str(f), ["X"]) is False

    def test_readonly(self, tmp_path):
        f = tmp_path / "f"
        f.write_text("x")
        f.chmod(0o400)
        assert has_permissions(str(f), ["R"]) is True
        assert has_permissions(str(f), ["W"]) is False

    def test_no_permission_bits(self, tmp_path):
        f = tmp_path / "f"
        f.write_text("x")
        f.chmod(0o000)
        assert has_permissions(str(f), ["R"]) is False

    def test_other_readable(self, tmp_path):
        f = tmp_path / "f"
        f.write_text("x")
        f.chmod(0o004)
        assert has_permissions(str(f), ["R"]) is True
