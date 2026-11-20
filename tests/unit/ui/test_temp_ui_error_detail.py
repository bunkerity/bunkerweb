"""The boot UI must not echo `/var/tmp/bunkerweb/ui.error` back to the client.

`src/ui/temp.py` serves an UNAUTHENTICATED page on 0.0.0.0:7000 while the real UI starts. Its 404
and catch-all handlers used to read `ui.error` and render it: that file holds raw exception text,
which can carry the Flask secret, the TOTP/Biscuit keys, or a database error with its bound
parameters. The detail belongs in the service logs, not in an anonymous HTTP response.

Source-level (AST) assertion: temp.py cannot be imported without the packaged deps paths.
Port of dev ``e5b977fb7``.
"""

import ast
from pathlib import Path

TEMP_PY = Path(__file__).resolve().parents[3] / "src" / "ui" / "temp.py"


def _handlers():
    tree = ast.parse(TEMP_PY.read_text(encoding="utf-8"), filename=str(TEMP_PY))
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def test_no_boot_error_handler_reads_the_error_file():
    """`ERROR_FILE.is_file()` stays (it picks the message); reading its CONTENT must not."""
    handlers = _handlers()
    for name in ("not_found_handler", "catch_all"):
        assert name in handlers, f"{name} disappeared from temp.py — update this test"
        reads = [
            node
            for node in ast.walk(handlers[name])
            if isinstance(node, ast.Attribute) and node.attr in {"read_text", "read_bytes", "open"} and getattr(node.value, "id", None) == "ERROR_FILE"
        ]
        assert not reads, f"{name} reads ui.error and renders it to an unauthenticated client"


def test_the_boot_error_page_points_at_the_logs():
    source = TEMP_PY.read_text(encoding="utf-8")
    assert "Check the service logs for details." in source
    assert "ERROR_FILE.read_text()" not in source
