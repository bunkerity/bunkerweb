r"""The easy-install script keeps Ubuntu Pro/ESM from shadowing the upstream CrowdSec engine.

On Ubuntu with Pro/ESM enabled, `apt install crowdsec` took the outdated ESM build, whose hub index does not
know the `bunkerity/bunkerweb` collection, so the install failed with an unexplained error. `install_crowdsec`
now writes an apt pin that excludes the ESM origin *before* installing, and when the collection still cannot
be installed it returns failure with a message that names the ESM origin (the caller then continues without
CrowdSec). The function is lifted from `misc/install-bunkerweb.sh` and run with stubbed package tools against
a temp root.

Refs #3659.
"""

import pytest
from _t7_helpers import bash, function, retarget, source

INSTALL_CROWDSEC = function(source("misc/install-bunkerweb.sh"), "install_crowdsec")

HARNESS = """
print_step() {{ echo "STEP $*"; }}
print_status() {{ echo "STATUS $*"; }}
print_warning() {{ echo "WARN $*"; }}
print_error() {{ echo "ERROR $*"; }}
run_cmd() {{
    if [ -f "{root}/etc/apt/preferences.d/99-bunkerweb-crowdsec.pref" ]; then pin=pin-present; else pin=pin-absent; fi
    echo "run_cmd $* [$pin]" >> "{root}/calls"
}}
curl() {{ while [ $# -gt 0 ]; do if [ "$1" = -o ]; then : > "$2"; fi; shift; done; }}
gpg() {{ :; }}
dpkg() {{ return 0; }}
rpm() {{ return 0; }}
apt-cache() {{ if [ "{esm}" = yes ]; then echo "     500 https://esm.ubuntu.com/apps/ubuntu noble-apps-security/main"; else echo "     500 https://packages.crowdsec.net"; fi; }}
cscli() {{
    echo "cscli $*" >> "{root}/calls"
    if [ "$1 $2 $3" = "collections install bunkerity/bunkerweb" ] && [ "{collection_fails}" = yes ]; then return 1; fi
    if [ "$1" = bouncers ]; then echo bouncer-key; fi
    return 0
}}
DISTRO_ID="{distro}"
DISTRO_FAMILY="{family}"
CROWDSEC_APPSEC_INSTALL=no
{function}
install_crowdsec
echo "rc=$?"
"""


def _run(tmp_path, *, distro="ubuntu", family="debian", esm=False, collection_fails=False):
    (tmp_path / "etc/apt/preferences.d").mkdir(parents=True)
    script = HARNESS.format(
        root=tmp_path,
        distro=distro,
        family=family,
        esm="yes" if esm else "no",
        collection_fails="yes" if collection_fails else "no",
        function=retarget(INSTALL_CROWDSEC, tmp_path, "/etc/apt/preferences.d", "/etc/crowdsec"),
    )
    result = bash(script, env={"PATH": "/usr/bin:/bin"})
    calls = (tmp_path / "calls").read_text(encoding="utf-8").splitlines() if (tmp_path / "calls").exists() else []
    return result, calls


@pytest.mark.parametrize("distro", ["ubuntu", "debian"])
def test_the_esm_origin_is_pinned_out_before_apt_installs_crowdsec(tmp_path, distro):
    result, calls = _run(tmp_path, distro=distro)

    assert "rc=0" in result.stdout, result.stdout + result.stderr
    pref = tmp_path / "etc/apt/preferences.d/99-bunkerweb-crowdsec.pref"
    assert pref.exists(), "no apt pin was written, so apt may still pick the ESM build"
    content = pref.read_text(encoding="utf-8")
    assert "Package: crowdsec*" in content
    assert 'Pin: origin "esm.ubuntu.com"' in content
    assert "Pin-Priority: -1" in content
    assert pref.stat().st_mode & 0o777 == 0o644
    assert "run_cmd apt install -y crowdsec [pin-present]" in calls, f"apt installed the engine before the pin existed: {calls}"


def test_an_rpm_distribution_gets_no_apt_pin(tmp_path):
    """Anti-vacuity: the pin is an apt concern only."""
    result, calls = _run(tmp_path, distro="fedora", family="rhel")

    assert "rc=0" in result.stdout, result.stdout + result.stderr
    assert not (tmp_path / "etc/apt/preferences.d/99-bunkerweb-crowdsec.pref").exists()
    assert "run_cmd dnf install -y crowdsec [pin-absent]" in calls


def test_an_engine_too_old_for_the_collection_fails_and_names_esm(tmp_path):
    result, calls = _run(tmp_path, esm=True, collection_fails=True)

    assert "rc=1" in result.stdout, "a failed collection install must make install_crowdsec fail so the caller can warn and continue"
    assert "ERROR The engine was installed from Ubuntu Pro/ESM" in result.stdout
    assert not any(call.startswith("cscli parsers") or call.startswith("cscli bouncers") for call in calls), f"setup went on after the failure: {calls}"


def test_the_esm_hint_is_only_printed_when_apt_picked_esm(tmp_path):
    result, _ = _run(tmp_path, esm=False, collection_fails=True)

    assert "rc=1" in result.stdout
    assert "Ubuntu Pro/ESM" not in result.stdout.split("To fix it:")[0], "blamed ESM although apt resolved the upstream repository"
