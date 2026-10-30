"""The default Permissions-Policy must not name features Chromium removed.

``shared-storage`` and ``shared-storage-select-url`` are gone from Chromium: a browser logs
"Unrecognized feature" for each one on every response. The default lives in several byte-identical
copies (the plugin setting, the templates, the error and default-server pages, the UI handler); this
checks all of them, and that they still agree.
"""

from json import loads
from pathlib import Path
from re import findall

import pytest

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"
REMOVED = ("shared-storage", "shared-storage-select-url")
# Directives the default must name: denying them is the point of a deny-by-default policy.
REQUIRED = ("publickey-credentials-remote-client-data-json",)

# One quoted literal per file: the long comma-separated list that starts at the first directive.
LITERAL = r'"(accelerometer=\(\)[^"]*xr-spatial-tracking=\(\))"'
COPIES = [
    ROOT / "src" / "common" / "confs" / "default-server-http.conf",
    CORE / "errors" / "errors.lua",
    CORE / "misc" / "confs" / "default-server-http" / "page.conf",
    ROOT / "src" / "ui" / "main.py",
]


def _default():
    return loads((CORE / "headers" / "plugin.json").read_text(encoding="utf-8"))["settings"]["PERMISSIONS_POLICY"]["default"]


def _names(policy):
    return [d.strip().split("=")[0] for d in policy.split(",")]


def test_the_plugin_default_has_neither_removed_feature():
    names = _names(_default())

    assert len(names) > 80, "the default was truncated"
    assert [n for n in names if n in REMOVED] == []


@pytest.mark.parametrize("template", ["high.json", "medium.json"])
def test_the_templates_have_neither_removed_feature(template):
    policy = loads((CORE / "templates" / "templates" / template).read_text(encoding="utf-8"))["settings"]["PERMISSIONS_POLICY"]

    assert [n for n in _names(policy) if n in REMOVED] == []
    assert policy == _default()


@pytest.mark.parametrize("path", COPIES, ids=lambda p: p.name)
def test_every_hardcoded_copy_matches_the_default_and_lacks_the_removed_features(path):
    literals = findall(LITERAL, path.read_text(encoding="utf-8"))

    assert literals, f"no Permissions-Policy literal found in {path}"
    # The UI grants four features to itself (see test_security_headers_emitted.py), so compare the
    # directive names, which must agree everywhere, not the values.
    assert {tuple(_names(lit)) for lit in literals} == {tuple(_names(_default()))}
    assert [n for lit in literals for n in _names(lit) if n in REMOVED] == []


def test_the_plugin_default_denies_every_required_feature():
    policy = _default()

    for name in REQUIRED:
        assert f"{name}=()" in [d.strip() for d in policy.split(",")], f"{name} is not denied by the default"


@pytest.mark.parametrize("template", ["high.json", "medium.json"])
def test_the_templates_deny_every_required_feature(template):
    policy = loads((CORE / "templates" / "templates" / template).read_text(encoding="utf-8"))["settings"]["PERMISSIONS_POLICY"]

    assert set(REQUIRED) <= set(_names(policy))


@pytest.mark.parametrize("path", COPIES, ids=lambda p: p.name)
def test_every_hardcoded_copy_denies_every_required_feature(path):
    literals = findall(LITERAL, path.read_text(encoding="utf-8"))

    assert literals, f"no Permissions-Policy literal found in {path}"
    for lit in literals:
        assert set(REQUIRED) <= set(_names(lit)), f"{path.name} lacks {set(REQUIRED) - set(_names(lit))}"
