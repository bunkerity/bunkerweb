"""``save_config.py`` rebuilds the declared instances in ONE call, and its dict matches the reader.

The scheduler sends the whole environment-declared roster again on every config save. It used to do
that as ``update_instances([], method="manual")`` -- a DELETE of every ``manual`` row -- followed by
one ``add_instance()`` per declaration, and that shape is why an enrolled ``manual`` row lost its
credential silently at the first save (``report-L-A.md`` §3a). The PO ruling of 2026-09-02 replaces
it with a single ``update_instances(declarations, method="manual")`` whose preservation is covered
behaviourally in ``tests/unit/db/test_instance_enrollment_preservation.py``.

What is pinned here is the seam those tests cannot see: ``update_instances()`` reads the ports and
the token out of ``instance["env"]`` with ``.get(..., <default>)``, so a declaration that spells a
key differently does not raise -- every instance quietly comes back on port 5000 with no credential.
Both halves are read from the sources and compared to each other.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SAVE_CONFIG = ROOT / "src" / "common" / "gen" / "save_config.py"
DB_INSTANCES = ROOT / "src" / "common" / "db" / "db_methods" / "instances.py"


@pytest.fixture(scope="module")
def declaration():
    """The dict literal `save_config.py` builds for each declared instance."""
    for node in ast.walk(ast.parse(SAVE_CONFIG.read_text(encoding="utf-8"))):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "update_instances"):
            continue
        literals = [child for child in ast.walk(node.args[0]) if isinstance(child, ast.Dict)]
        assert literals, "update_instances() is no longer handed a dict literal per instance"
        return literals[0]
    pytest.fail("save_config.py no longer calls update_instances()")


def _keys(node):
    return {key.value for key in node.keys if isinstance(key, ast.Constant)}


def test_the_delete_then_re_add_shape_is_gone():
    """`update_instances([], ...)` wipes the rows instead of rebuilding them, and `add_instance()`
    refuses a hostname that already exists, so the pair can only work by deleting first."""
    source = SAVE_CONFIG.read_text(encoding="utf-8")
    assert "update_instances([]" not in source
    assert "db.add_instance(" not in source


def test_it_declares_every_field_the_reconcile_needs(declaration):
    assert {"hostname", "name", "status", "env", "tls_mode", "tls_fingerprint"} <= _keys(declaration)


def _env(declaration):
    env = next((value for key, value in zip(declaration.keys, declaration.values) if isinstance(key, ast.Constant) and key.value == "env"), None)
    assert isinstance(env, ast.Dict), "the declaration no longer carries an env mapping"
    return env


def test_the_credential_comes_from_the_declared_token(declaration):
    """`BUNKERWEB_INSTANCE_API_TOKEN_n` has to reach `_reconcile_credential_columns` as
    `env["API_TOKEN"]`; spelling it anything else silently drops every declared token."""
    env = _env(declaration)
    token = next(ast.unparse(value) for key, value in zip(env.keys, env.values) if isinstance(key, ast.Constant) and key.value == "API_TOKEN")
    assert "credential" in token, f'env["API_TOKEN"] is fed from {token}, not from the declared credential'


def test_every_key_the_reconcile_reads_is_actually_declared(declaration):
    """The drift this exists for: `update_instances()` reads `instance["env"].get(key, default)`,
    so a renamed or forgotten key is not an error -- the instance just comes back on the default
    port with no credential and nothing says so."""
    reconcile = next(
        node for node in ast.walk(ast.parse(DB_INSTANCES.read_text(encoding="utf-8"))) if isinstance(node, ast.FunctionDef) and node.name == "update_instances"
    )
    read = {
        node.args[0].value
        for node in ast.walk(reconcile)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Subscript)
        and isinstance(node.func.value.slice, ast.Constant)
        and node.func.value.slice.value == "env"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }

    assert read, "update_instances() no longer reads instance['env'], this test is now blind"
    assert read <= _keys(_env(declaration)), f"save_config.py never declares {sorted(read - _keys(_env(declaration)))}"
