"""LX1-12: repository bootstrap runs inside a private, disposable directory."""

import re

import pytest
from _t7_helpers import bash, function, retarget, source


@pytest.mark.parametrize("kind", ["debian", "rpm"])
@pytest.mark.parametrize("failure", [None, "download", "bootstrap", "mktemp"])
def test_repository_bootstrap_is_private_and_cleaned_on_every_exit(tmp_path, kind, failure):
    shared = tmp_path / "tmp"
    shared.mkdir()
    sentinel = shared / "bunkerweb-repo.sh"
    sentinel.write_text("unrelated existing file")
    text = source("misc/install-bunkerweb.sh")
    # Include the shared helper if present, while still exercising the old call sites for red proof.
    names = ["run_cmd", f"install_bunkerweb_{kind}"]
    helper = re.search(r"^install_bunkerweb_repository\(\) \(\n.*?^\)\n", text, re.M | re.S)
    functions = retarget((helper.group(0) if helper else "") + "\n".join(function(text, name) for name in names), tmp_path, "/tmp")
    called = tmp_path / "calls"
    downloaded = tmp_path / "downloaded"
    parent_cleanup = tmp_path / "parent-cleanup"
    result = bash(f"""
        set -e
        trap 'echo parent > "{parent_cleanup}"' EXIT
        ENABLE_WIZARD=no
        BUNKERWEB_VERSION='1.6.18~rc4'
        DISTRO_ID=fedora
        print_step() {{ :; }}
        print_status() {{ :; }}
        print_error() {{ echo "$*" >&2; }}
        is_rhel_family() {{ return 1; }}
        apt() {{ echo apt >> '{called}'; }}
        apt-mark() {{ :; }}
        dnf() {{ echo dnf >> '{called}'; }}
        mktemp() {{
            if [ '{failure}' = mktemp ]; then return 1; fi
            command mktemp "$@"
        }}
        curl() {{
            while [ "$1" != -o ]; do shift; done
            echo "$2" > '{downloaded}'
            printf 'echo bootstrap >> "{called}"\nexit %s\n' '{9 if failure == "bootstrap" else 0}' > "$2"
            [ '{failure}' != download ]
        }}
        bash() {{
            stat -c '%a' "$(dirname "$1")" > '{tmp_path}/mode'
            command bash "$@"
        }}
        {functions}
        install_bunkerweb_{kind}
    """)
    assert result.returncode == (1 if failure else 0), result.stdout + result.stderr
    assert sentinel.read_text() == "unrelated existing file"
    assert list(shared.iterdir()) == [sentinel], "bootstrap artifacts survived success/failure"
    assert parent_cleanup.read_text().strip() == "parent", "helper replaced the installer's EXIT trap"
    calls = called.read_text().splitlines() if called.exists() else []
    assert any(call in ("apt", "dnf") for call in calls) is (failure is None)
    if failure in (None, "bootstrap"):
        assert (tmp_path / "mode").read_text().strip() == "700"
        assert "bootstrap" in calls
    if downloaded.exists():
        assert downloaded.read_text().strip() != str(sentinel)
