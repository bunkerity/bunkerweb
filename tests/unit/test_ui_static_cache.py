"""Regression checks for direct UI static asset caching and UI data reloads."""

import ast
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src" / "ui"))

from app.models.ui_data import UIData  # noqa: E402


def static_cache_control():
    tree = ast.parse((REPO / "src" / "ui" / "main.py").read_text())
    function = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_static_cache_control"), None)
    if function is None:
        raise AssertionError("main._static_cache_control is missing")
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "main.py", "exec"), namespace)
    return namespace["_static_cache_control"]


class UIStaticCacheTest(unittest.TestCase):
    def test_versioned_static_assets_are_immutable_only_for_the_current_version(self):
        cache_control = static_cache_control()
        self.assertEqual(cache_control("1.6.16", "1.6.16"), "public, max-age=31536000, immutable")
        self.assertIsNone(cache_control(None, "1.6.16"))
        self.assertIsNone(cache_control("old", "1.6.16"))

    def test_ui_data_does_not_reread_an_unchanged_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ui_data.json"
            path.write_text('{"ready": true}')
            data = UIData(path)
            original_read_text = Path.read_text
            reads = 0

            def read_text(current, *args, **kwargs):
                nonlocal reads
                if current == path:
                    reads += 1
                return original_read_text(current, *args, **kwargs)

            with patch.object(Path, "read_text", new=read_text):
                data.load_from_file()
            self.assertEqual(reads, 0)


if __name__ == "__main__":
    unittest.main()
