"""Execute the release pin checker against isolated trees, with read-only git responses."""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
VERSION = "1.99.0~rc5"
FINAL = VERSION.split("~")[0]
PINS = {
    "src/bw/Dockerfile": 'LABEL version="{version}"\n',
    "misc/install-bunkerweb.sh": 'DEFAULT_BUNKERWEB_VERSION="{version}"\n',
    "publiccode.yml": "softwareVersion: {version}\n",
    "pyproject.toml": 'version = "{version}"\n',
    ".github/ISSUE_TEMPLATE/bug_report.yml": "      value: {version}\n",
}


@pytest.fixture
def tree(tmp_path):
    for name, template in PINS.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(template.format(version=VERSION))
    (tmp_path / "src/VERSION").write_text(VERSION + "\n")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    git = bindir / "git"
    # Only the checker's two read operations are stubbed; grep runs on actual fixture files.
    git.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'case "$1" in\n'
        'rev-parse) printf "%s\\n" "$FIXTURE_ROOT" ;;\n'
        'grep) shopt -s globstar nullglob; grep -nE "$3" src/bw/Dockerfile publiccode.yml pyproject.toml '
        ".github/ISSUE_TEMPLATE/bug_report.yml literals.txt docs/**/*.md ;;\n"
        "*) exit 2 ;;\nesac\n"
    )
    git.chmod(0o755)
    (tmp_path / "literals.txt").write_text(f"image: bunkerweb:{VERSION.replace('~', '-')}\n")
    return tmp_path


def check(tree):
    return subprocess.run(
        ["bash", str(ROOT / "misc/check-version-consistency.sh")],
        cwd=tree,
        env={**os.environ, "FIXTURE_ROOT": str(tree), "PATH": str(tree / "bin") + os.pathsep + os.environ["PATH"]},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_consistent_tree_passes(tree):
    result = check(tree)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"All version pins agree with {VERSION}" in result.stdout


@pytest.fixture
def nginx_trees(tree):
    for name, version in [("nginx", "1.30.7"), ("nginx-1.30.6", "1.30.6")]:
        header = tree / "src/deps/src" / name / "src/core/nginx.h"
        header.parent.mkdir(parents=True)
        header.write_text(f'#define NGINX_VERSION "{version}"\n')
    (tree / "src/deps/install.sh").write_text(
        'case "$OS:$OS_VERSION" in\n'
        '    fedora:43) NGINX_SRC_DIR="/tmp/bunkerweb/deps/src/nginx-1.30.6" ;;\n'
        '    *) NGINX_SRC_DIR="/tmp/bunkerweb/deps/src/nginx" ;;\n'
        "esac\n"
    )
    (tree / "src/linux").mkdir()
    return tree


@pytest.mark.parametrize(
    "os_name,os_version,pin,expected",
    [
        ("fedora", "43", "1.30.6", 0),
        ("fedora", "43", "1.30.7", 1),
        ("fedora", "44", "1.30.7", 0),
        ("fedora", "44", "1.30.6", 1),
        ("fedora", "45", "1.30.7", 0),
        ("fedora", "45", "1.30.6", 1),
        ("debian", "", "1.30.6", 1),
        ("debian", "", "1.30.7", 0),
    ],
)
def test_linux_nginx_pin_matches_selected_tree(nginx_trees, os_name, os_version, pin, expected):
    name = f"src/linux/Dockerfile-{os_name}" + (f"-{os_version}" if os_version else "")
    version_line = f"ENV OS_VERSION={os_version}\n" if os_version else ""
    (nginx_trees / name).write_text(f"ENV OS={os_name}\n{version_line}ENV NGINX_VERSION={pin}\n")
    result = check(nginx_trees)
    assert result.returncode == expected, result.stdout + result.stderr
    if expected:
        assert f"{name}: NGINX_VERSION={pin}" in result.stdout


@pytest.mark.parametrize(
    "os_name,os_version,pin,expected",
    [("fedora", '"43"', "1.30.7", 1), ("fedora", '"43"', "1.30.6", 0), ("'fedora'", "'43'", "1.30.6", 0), ("fedora", "44", '"1.30.7"', 0)],
)
def test_linux_nginx_pin_accepts_quoted_env(nginx_trees, os_name, os_version, pin, expected):
    release = os_version.strip("\"'")
    (nginx_trees / f"src/linux/Dockerfile-fedora-{release}").write_text(f"ENV OS={os_name}\nENV OS_VERSION={os_version}\nENV NGINX_VERSION={pin}\n")
    result = check(nginx_trees)
    assert result.returncode == expected, result.stdout + result.stderr
    if expected:
        assert "selects nginx-1.30.6 (1.30.6)" in result.stdout


@pytest.mark.parametrize("pin,expected", [("1.30.7", 1), ("1.30.6", 0)])
@pytest.mark.parametrize(
    "declaration",
    [
        "ENV OS_VERSION=43 OTHER=44",
        "ENV OTHER=44 OS_VERSION=43",
        "ENV A=1 \\\n    OS_VERSION=43",
        "ENV A=1 \\\n    # skip this comment\n    OS_VERSION=43",
        "env A=1 \\ \t\n\n    OS_VERSION=43",
        "ENV OS_VER\\\nSION=43",
    ],
    ids=["key-first", "key-second", "continuation", "comment", "lowercase-blank-line", "split-key"],
)
def test_linux_nginx_pin_reads_logical_env(nginx_trees, declaration, pin, expected):
    (nginx_trees / "src/linux/Dockerfile-fedora-43").write_text(f"ENV OS=fedora\n{declaration}\nENV NGINX_VERSION={pin}\n")
    result = check(nginx_trees)
    assert result.returncode == expected, result.stdout + result.stderr
    if expected:
        assert "selects nginx-1.30.6 (1.30.6)" in result.stdout


def test_linux_nginx_pin_reads_all_keys_on_one_line(nginx_trees):
    (nginx_trees / "src/linux/Dockerfile-fedora-43").write_text("ENV OS=fedora OS_VERSION=43 NGINX_VERSION=1.30.7\n")
    result = check(nginx_trees)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "selects nginx-1.30.6 (1.30.6)" in result.stdout


def test_linux_nginx_pin_ignores_unrelated_env(nginx_trees):
    (nginx_trees / "src/linux/Dockerfile-debian-bookworm").write_text(
        "ENV RUSTUP_HOME=/rustup \\\n    CARGO_HOME=/cargo \\\n    PATH=/cargo/bin:$PATH\n"
        'ENV OTHER="unclosed\n'
        "ENV OTHER OS_VERSION=43\n"
        "ENV OS=debian\nENV NGINX_VERSION=1.30.7\n"
    )
    result = check(nginx_trees)
    assert result.returncode == 0, result.stdout + result.stderr


def test_linux_nginx_pin_rejects_duplicate_env_across_stages(nginx_trees):
    (nginx_trees / "src/linux/Dockerfile-fedora-43").write_text(
        "FROM scratch AS builder\nENV OS=fedora\nENV OS_VERSION=43\nENV NGINX_VERSION=1.30.6\n" "FROM scratch\nENV A=1 OS_VERSION=43\n"
    )
    result = check(nginx_trees)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "unsupported ENV declaration for OS_VERSION" in result.stderr


def test_linux_nginx_pin_rejects_escape_directive(nginx_trees):
    (nginx_trees / "src/linux/Dockerfile-fedora-43").write_text(
        "# syntax=docker/dockerfile:1\n# EsCaPe = `\nFROM scratch\nENV OS=fedora\nENV A=1 `\n    OS_VERSION=43\nENV NGINX_VERSION=1.30.7\n"
    )
    result = check(nginx_trees)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "unsupported ENV declaration" in result.stderr
    assert "escape" in result.stderr.lower()


@pytest.mark.parametrize(
    "declaration",
    [
        "ENV OS_VERSION=43 44",
        'ENV OS_VERSION="43 44"',
        "ENV OS_VERSION 43",
        'ENV OS_VERSION="43',
        'ENV OTHER="unclosed \\\n    OS_VERSION=43',
        "ENV OS_VERSION=${FEDORA_VERSION}",
        "ENV OS_VERSION=",
        'ENV OS_VERSION=""',
    ],
)
def test_linux_nginx_pin_rejects_unsupported_env(nginx_trees, declaration):
    (nginx_trees / "src/linux/Dockerfile-fedora-43").write_text(f"ENV OS=fedora\n{declaration}\nENV NGINX_VERSION=1.30.7\n")
    result = check(nginx_trees)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "src/linux/Dockerfile-fedora-43: unsupported ENV declaration for OS_VERSION" in result.stderr


def test_fedora_43_pin_rejects_mismatch_with_whitespace_in_selector(nginx_trees):
    installer = nginx_trees / "src/deps/install.sh"
    installer.write_text(installer.read_text().replace("fedora:43) ", "fedora:43)  "))
    (nginx_trees / "src/linux/Dockerfile-fedora-43").write_text("ENV OS=fedora\nENV OS_VERSION=43\nENV NGINX_VERSION=1.30.7\n")
    result = check(nginx_trees)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "selects nginx-1.30.6 (1.30.6)" in result.stdout


@pytest.mark.parametrize(
    "installer_text,diagnostic",
    [
        ("# No selector\n", "NGINX selector block is missing"),
        ('case "$OS:$OS_VERSION" in\n    *) ;;\nesac\n', "NGINX_SRC_DIR is empty"),
        ('case "$OS:$OS_VERSION" in\n    *) NGINX_SRC_DIR="/tmp/bunkerweb/deps/src/nginx-missing" ;;\nesac\n', "missing vendored NGINX tree"),
    ],
    ids=["missing-block", "empty-selection", "missing-tree"],
)
def test_linux_nginx_pin_rejects_invalid_selector(nginx_trees, installer_text, diagnostic):
    (nginx_trees / "src/deps/install.sh").write_text(installer_text)
    (nginx_trees / "src/linux/Dockerfile-fedora-43").write_text("ENV OS=fedora\nENV OS_VERSION=43\nENV NGINX_VERSION=1.30.6\n")
    result = check(nginx_trees)
    assert result.returncode == 1, result.stdout + result.stderr
    assert diagnostic in result.stdout


@pytest.mark.parametrize("name", PINS)
@pytest.mark.parametrize("expected,wrong", [(VERSION, VERSION + "0"), (FINAL, VERSION)])
def test_pin_must_equal_version(tree, name, expected, wrong):
    (tree / "src/VERSION").write_text(expected + "\n")
    for pin, template in PINS.items():
        (tree / pin).write_text(template.format(version=wrong if pin == name else expected))
    (tree / "literals.txt").write_text("")
    result = check(tree)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{name}: pin is" in result.stdout


@pytest.mark.parametrize("stale", [VERSION + "0", VERSION.replace("~", "-") + "0", FINAL + "~rc3", VERSION + "-extra"])
@pytest.mark.parametrize("same_line", [False, True])
def test_stale_token_cannot_hide_behind_current_version(tree, stale, same_line):
    prefix = f"current={VERSION} " if same_line else ""
    (tree / "literals.txt").write_text(f"{prefix}stale={stale}\n")
    result = check(tree)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "literals.txt:1:" in result.stdout


@pytest.mark.parametrize("path", ["docs/features.md", "docs/fr/features.md"])
@pytest.mark.parametrize("prose", ["Requires ({rc} or later).", "Cores before {rc} differ. {rc} or later also helps.", "Requires a fix before {rc}."])
def test_features_accept_version_bounds(tree, path, prose):
    page = tree / path
    page.parent.mkdir(parents=True)
    page.write_text(prose.format(rc=FINAL + "~rc2") + "\n")
    result = check(tree)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "path,line",
    [
        ("docs/features.md", "image: bunkerweb:{tag}"),
        ("docs/fr/features.md", "Requires {rc} or later. Use image: bunkerweb:{tag}"),
        ("docs/fr/features.md", "Requires {rc} or later. Install with version={rc}"),
        ("docs/features.md", "Use image: bunkerweb:{rc} or later"),
        ("docs/features.md", "Cores before {rc}-extra differ."),
        ("docs/features.md", "Cores before {rc}:amd64 differ."),
        ("docs/guide.md", "Requires {rc} or later."),
    ],
)
def test_version_bounds_do_not_hide_stale_pins(tree, path, line):
    page = tree / path
    page.parent.mkdir(parents=True)
    stale = FINAL + "~rc2"
    page.write_text(line.format(rc=stale, tag=stale.replace("~", "-")) + "\n")
    result = check(tree)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{path}:1:" in result.stdout


def test_final_release_rejects_stale_rc_literal(tree):
    (tree / "src/VERSION").write_text(FINAL + "\n")
    for name, template in PINS.items():
        (tree / name).write_text(template.format(version=FINAL))
    result = check(tree)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "literals.txt:1:" in result.stdout
