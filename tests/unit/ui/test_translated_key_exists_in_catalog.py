"""FIX-QA6-I18N Q6-H2: 35 `translated("dotted.key")` call sites named a key that existed in no
catalog (`qa-ui6/missing-translated-keys.txt`), so the English fallback always rendered, in every
locale. Reuses `test_flash_no_english_literal_left.py`'s file list and AST-parsing approach: any
`translated(...)` call whose first argument is a string literal must name a key that is present in
`en.json`, the source of truth every other catalog is checked against.

This only checks the key exists, not that every other locale already has it too -- a new key is
allowed to be red on the catalog-parity test until I18N-SYNC translates it (RULES-FIX.md).
"""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

TARGET_FILES = sorted((ROOT / "src/ui/app/routes").glob("*.py")) + [ROOT / "src/ui/main.py"] + sorted((ROOT / "src/common/core").glob("*/ui/*.py"))


def _catalog_keys():
    catalog = json.loads((ROOT / "src/ui/app/static/locales/en.json").read_text(encoding="utf-8"))
    keys = set()

    def walk(node, prefix):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                walk(value, path)
            else:
                keys.add(path)

    walk(catalog, "")
    return keys


def _is_translated_call(node):
    func = node.func
    name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else None)
    return name == "translated"


def _translated_key_sites(path):
    """Every (key, lineno) a `translated(...)` call in `path` names as a string literal."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    sites = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node):
            if _is_translated_call(node) and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                sites.append((node.args[0].value, node.lineno))
            self.generic_visit(node)

    Visitor().visit(tree)
    return sites


def test_every_translated_key_exists_in_en_json():
    """A key that reaches no catalog entry always falls through to its English fallback, in
    every locale -- this is exactly how Q6-H2's 35 call sites were found."""
    catalog_keys = _catalog_keys()
    offenders = []
    for path in TARGET_FILES:
        for key, lineno in _translated_key_sites(path):
            if key not in catalog_keys:
                offenders.append(f"{path.relative_to(ROOT)}:{lineno} {key}")
    assert offenders == []
