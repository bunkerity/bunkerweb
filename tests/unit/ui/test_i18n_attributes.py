"""Contracts for attribute translations applied during initial load and language changes."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
I18N_JS = ROOT / "src" / "ui" / "app" / "static" / "js" / "i18n.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_i18n_runtime_parses():
    assert subprocess.run(["node", "--check", str(I18N_JS)], capture_output=True).returncode == 0


def test_every_live_explicit_translation_attribute_has_a_runtime_target():
    source = I18N_JS.read_text(encoding="utf-8")
    for key_attribute, target_attribute in (
        ("data-i18n-aria-label", "aria-label"),
        ("data-i18n-title", "title"),
        ("data-i18n-placeholder", "placeholder"),
        ("data-i18n-empty-text", "data-empty-text"),
    ):
        assert f'"{key_attribute}": "{target_attribute}"' in source
        assert "`[${attribute}]`" in source


def test_generic_attribute_target_supports_text_and_named_attributes():
    source = I18N_JS.read_text(encoding="utf-8")
    assert 'explicitTarget === "text"' in source
    assert "element.attr(explicitTarget, translation)" in source
