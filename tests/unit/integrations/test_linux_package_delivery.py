"""How the Linux arm gets the package it installs.

Run 32820557847 died in every Linux job with ``Could not find the file
/opt/bunkerweb_1.7-dev-1_amd64.deb``. The step was extracting the package from the
``<distro>-tests`` image, and that image is ``tests/linux/Dockerfile-<distro>`` -- a bare systemd
runtime. ``71247ab38`` (the tests migration) dropped the ``COPY ./package-<distro>/*.deb /opt``
line the copy depended on, so ``/opt`` has been empty since, and the Linux arm has never executed
a spec in CI. Proof, on the tag as published: ``docker export ghcr.io/bunkerity/ubuntu-noble-tests:1.7
| tar -t`` yields 18 935 entries, of which exactly one starts with ``opt/`` -- the empty directory
-- and none is a ``.deb``, an ``.rpm`` or an ``fpm.sh``.

The arm now downloads the artefact ``linux-build.yml`` uploaded earlier in the same run, which is
the same artefact ``push-packagecloud.yml`` ships to users. That only holds while four things stay
aligned, and each is silent when it breaks:

* the artefact NAME both sides build must be the same template;
* every Linux spec must name a distro the calling workflow's ``build-packages`` matrix builds,
  in a job that waits for it;
* the architecture token in the spec must be the package-flavoured one ``linux-build.yml`` puts
  in the artefact name (``x86_64`` for rpm, ``amd64`` for deb, and the arm equivalents);
* nothing may put a package back inside ``tests/linux/Dockerfile-*`` -- the "Build Linux image"
  step builds those on a runner with no ``package-<distro>/`` directory, so a COPY of one fails
  the build.
"""

import re
from pathlib import Path

import pytest
from yaml import safe_load

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"

INTEGRATION_TESTS = (WORKFLOWS / "integration-tests.yml").read_text(encoding="utf-8")
LINUX_BUILD = (WORKFLOWS / "linux-build.yml").read_text(encoding="utf-8")

PACKAGES = safe_load((ROOT / "tests" / "utils" / "packages.yml").read_text(encoding="utf-8"))["packages_info"]
INTEGRATIONS = safe_load((ROOT / "tests" / "utils" / "integrations.yml").read_text(encoding="utf-8"))

# `linux-build.yml` maps the build arch to the one the package carries before naming the artefact:
# rpm gets x86_64/aarch64, deb keeps amd64/arm64. A spec whose arch token is on the wrong side of
# that mapping asks for an artefact name nothing ever uploaded.
ARCH_TOKENS = {"rpm": {"x86_64", "aarch64"}, "deb": {"amd64", "arm64"}}

# The package-flavoured arch tokens a caller's PLATFORMS input actually produces artefacts for. A
# spec row for an arch outside the caller's PLATFORMS asks for an artefact the run never uploads --
# the same silent name mismatch this file exists to guard, one level up.
PLATFORM_ARCHES = {"linux/amd64": {"amd64", "x86_64"}, "linux/arm64": {"arm64", "aarch64"}}

# Every workflow that runs the Linux arm, with the section of integrations.yml its parse.py call
# reads. `1.7-dev.yml`/`dev.yml`/`ui.yml` pass `--dev`. `staging.yml` (wave 11) does not -- it
# reads `staging:` instead, then its own `parse-tests-core` job further filters the 9 live
# `staging:` distros down to 4 before turning them into a matrix (GitHub's 256-job cap; see the
# comment there). That runtime filter is not this guard's concern: this checks that every distro
# the *section* declares live has a package built for it, which staging.yml's build-packages
# matrix satisfies for all 9, filtered or not.
CALLERS = (("1.7-dev.yml", "dev"), ("dev.yml", "dev"), ("ui.yml", "dev"), ("staging.yml", "staging"))


def _live_linux_specs(section):
    """(arch, spec) pairs parse.py would emit for the Linux integration -- TODO rows are skipped."""
    return [(arch, spec) for arch, specs in INTEGRATIONS[section]["Linux"].items() for spec, runner in specs.items() if runner != "TODO"]


def _build_matrix(workflow):
    """The distro legs of a caller's build-packages matrix, as written in the flow-style list."""
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    body = text.split("  build-packages:", 1)[1]
    listing = re.search(r"^        linux:\s*(?:\[(?P<inline>[^\]]*)\]|\n\s*\[(?P<block>[^\]]*)\])", body, re.M)
    assert listing, f"{workflow}: no build-packages linux matrix found"
    return {leg.strip() for leg in (listing.group("inline") or listing.group("block")).split(",") if leg.strip()}


def _built_platforms(workflow):
    """The PLATFORMS a caller's build-packages leg passes to linux-build.yml."""
    body = (WORKFLOWS / workflow).read_text(encoding="utf-8").split("  build-packages:", 1)[1]
    line = re.search(r"^      PLATFORMS: (?P<platforms>\S.*?)\s*$", body, re.M)
    assert line, f"{workflow}: build-packages passes no PLATFORMS"
    return {platform.strip() for platform in line.group("platforms").split(",") if platform.strip()}


def test_the_package_never_comes_out_of_an_image_again():
    # A copy OUT of a container is the one with a `<container>:<path>` source; the install steps
    # copy the staged package IN, which is the same verb with the colon on the destination.
    out_of_container = re.findall(r'docker cp\s+"?[^"\s]+:[^"\s]+"?\s', INTEGRATION_TESTS)
    assert not out_of_container, f"the Linux arm is extracting the package from a container again: {out_of_container}"
    assert "docker create" not in INTEGRATION_TESTS
    assert "-tests:${RELEASE}" not in INTEGRATION_TESTS, "the Linux arm is pulling a <distro>-tests image again"


def test_the_arm_downloads_the_artefact_linux_build_uploads():
    assert "name: package-${{ inputs.LINUX }}-${{ env.LARCH }}" in LINUX_BUILD
    assert "path: package-${{ inputs.LINUX }}/*.${{ inputs.PACKAGE }}" in LINUX_BUILD
    assert "name: package-${{ needs.setup.outputs.linux_name }}-${{ needs.setup.outputs.architecture }}" in INTEGRATION_TESTS
    assert "uses: actions/download-artifact@" in INTEGRATION_TESTS


@pytest.mark.parametrize("workflow,section", CALLERS, ids=lambda value: value)
def test_every_live_linux_spec_names_a_distro_the_caller_builds(workflow, section):
    matrix = _build_matrix(workflow)
    missing = {PACKAGES[spec]["name"] for _, spec in _live_linux_specs(section) if PACKAGES[spec]["name"] not in matrix}
    assert not missing, f"{workflow} runs Linux specs for {sorted(missing)} but never builds a package for them"
    built = set().union(*(PLATFORM_ARCHES[platform] for platform in _built_platforms(workflow)))
    wrong_arch = {arch for arch, _ in _live_linux_specs(section) if arch not in built}
    assert not wrong_arch, f"{workflow} runs Linux specs on {sorted(wrong_arch)} but its PLATFORMS never builds a package for them"


@pytest.mark.parametrize("workflow,section", CALLERS, ids=lambda value: value)
def test_the_linux_jobs_wait_for_the_packages_they_download(workflow, section):
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    jobs = re.findall(r"^  (run-Linux-tests-\w+):\n(?P<body>(?:    .*\n|\n)+)", text, re.M)
    assert jobs, f"{workflow}: no run-Linux-tests-* job found"
    for name, body in jobs:
        needs = re.search(r"^    needs: \[(?P<needs>[^\]]*)\]", body, re.M)
        assert needs, f"{workflow}: {name} declares no needs"
        assert "build-packages" in needs.group("needs"), f"{workflow}: {name} downloads an artefact it does not wait for"


@pytest.mark.parametrize("section", sorted(INTEGRATIONS))
def test_every_linux_spec_carries_the_package_flavoured_arch(section):
    wrong = [
        f"{section}/{arch}/{spec}"
        for arch, specs in INTEGRATIONS[section]["Linux"].items()
        for spec in specs
        if arch not in ARCH_TOKENS[PACKAGES[spec]["package"]]
    ]
    assert not wrong, f"arch token is on the wrong side of linux-build.yml's rpm/deb mapping: {wrong}"


def test_the_test_images_stay_package_free():
    dockerfiles = sorted((ROOT / "tests" / "linux").glob("Dockerfile-*"))
    assert dockerfiles, "no tests/linux/Dockerfile-* found -- the guard below would pass vacuously"
    offenders = [path.name for path in dockerfiles if re.search(r"^COPY .*package-", path.read_text(encoding="utf-8"), re.M)]
    assert not offenders, f"a package COPY is back in {offenders}; the Build Linux image step has no package-* directory to copy from"
