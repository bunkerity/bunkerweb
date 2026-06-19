"""Drift guard for the bcrypt password helpers duplicated across the UI and the API.

`src/ui/app/utils.py` and `src/api/app/utils.py` carry byte-identical copies of the
bcrypt helpers and their security constants. The API copy can't be imported in isolation
(its module top pulls `Database` + `app.models`, booting the DB layer), so the UI copy is
the one exercised by `tests/unit/ui/test_ui_utils.py`. To stop the API copy from silently
diverging, this test parses both files with `ast` and asserts the shared functions and
constants stay structurally identical — an edit to one that isn't mirrored to the other
fails here instead of shipping a quiet auth-behavior mismatch.

Comparison is AST-based (whitespace/comments ignored) with leading docstrings stripped, so
only behavior drifts — signatures, logic, annotations, constant expressions — are flagged.
"""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
UI_UTILS = REPO_ROOT / "src" / "ui" / "app" / "utils.py"
API_UTILS = REPO_ROOT / "src" / "api" / "app" / "utils.py"

# Helpers that MUST stay identical between the two modules.
SHARED_FUNCS = (
    "_bcrypt_secret",
    "password_exceeds_bcrypt_limit",
    "gen_password_hash",
    "is_bcrypt_hash",
    "bcrypt_cost",
    "check_password",
)

# Security-relevant constants those helpers depend on (the BISCUIT_*_FILE paths are
# intentionally different per service, so they are deliberately excluded).
SHARED_CONSTANTS = (
    "USER_PASSWORD_RX",
    "BCRYPT_HASH_RX",
    "RECOMMENDED_BCRYPT_COST",
    "MIN_BCRYPT_COST",
    "MAX_PASSWORD_BYTES",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _is_docstring(stmt: ast.stmt) -> bool:
    return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str)


def _func_dump(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            if node.body and _is_docstring(node.body[0]):
                node.body = node.body[1:]  # throwaway tree — safe to mutate
            return ast.dump(node)  # name + args + returns + body + decorators; positions excluded
    return None


def _const_dump(tree: ast.Module, name: str):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.dump(node.value)
    return None


@pytest.fixture(scope="module")
def trees():
    return _tree(UI_UTILS), _tree(API_UTILS)


def test_source_files_exist():
    assert UI_UTILS.is_file(), f"missing {UI_UTILS}"
    assert API_UTILS.is_file(), f"missing {API_UTILS}"


@pytest.mark.parametrize("name", SHARED_FUNCS)
def test_bcrypt_helper_in_sync(name, trees):
    ui_tree, api_tree = trees
    ui_dump = _func_dump(ui_tree, name)
    api_dump = _func_dump(api_tree, name)
    assert ui_dump is not None, f"{name} missing from {UI_UTILS}"
    assert api_dump is not None, f"{name} missing from {API_UTILS}"
    assert ui_dump == api_dump, f"{name} diverged between ui/app/utils.py and api/app/utils.py — mirror the change to both copies"


@pytest.mark.parametrize("name", SHARED_CONSTANTS)
def test_security_constant_in_sync(name, trees):
    ui_tree, api_tree = trees
    ui_dump = _const_dump(ui_tree, name)
    api_dump = _const_dump(api_tree, name)
    assert ui_dump is not None, f"{name} missing from {UI_UTILS}"
    assert api_dump is not None, f"{name} missing from {API_UTILS}"
    assert ui_dump == api_dump, f"{name} diverged between ui/app/utils.py and api/app/utils.py — mirror the change to both copies"
