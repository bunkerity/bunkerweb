"""Release publication must leave verifiable provenance for every public subject."""

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(os.environ.get("P_RELEASE_ROOT", Path(__file__).resolve().parents[3]))
WORKFLOWS = ROOT / ".github/workflows"
ATTEST = "actions/attest-build-provenance@"


def workflow(name):
    return yaml.safe_load((WORKFLOWS / name).read_text())


def test_only_attesting_jobs_receive_signing_permissions():
    expected = {
        ("release.yml", "push-images"),
        ("release.yml", "push-packages"),
        ("release.yml", "attest-assets"),
        ("push-docker.yml", "push"),
        ("push-packagecloud.yml", "push"),
    }
    actual = set()
    for name in ("release.yml", "push-docker.yml", "push-packagecloud.yml", "push-github.yml"):
        data = workflow(name)
        permissions = data.get("permissions", {})
        if isinstance(permissions, dict):
            assert permissions.get("id-token") != "write"
            assert permissions.get("attestations") != "write"
        for job_id, job in data["jobs"].items():
            perms = job.get("permissions", {})
            if perms.get("id-token") == "write" or perms.get("attestations") == "write":
                assert perms.get("id-token") == perms.get("attestations") == "write"
                actual.add((name, job_id))
                if "uses" not in job:
                    assert any(step.get("uses", "").startswith(ATTEST) for step in job["steps"])
    assert actual == expected


def test_images_attest_both_registries_using_the_pushed_index_digest():
    steps = workflow("push-docker.yml")["jobs"]["push"]["steps"]
    build = next(step for step in steps if step.get("with", {}).get("push") is True)
    assert build["id"] == "build"
    attestations = [step for step in steps if step.get("uses", "").startswith(ATTEST)]
    assert len(attestations) == 2
    assert {step["with"]["subject-name"] for step in attestations} == {
        "docker.io/bunkerity/${{ inputs.IMAGE }}",
        "ghcr.io/bunkerity/${{ inputs.IMAGE }}",
    }
    for step in attestations:
        assert steps.index(step) > steps.index(build)
        assert step["with"]["subject-digest"] == "${{ steps.build.outputs.digest }}"
        assert re.fullmatch(ATTEST + r"[0-9a-f]{40}", step["uses"])
    record = next(step for step in steps if step.get("name") == "Record published images")
    assert record["env"]["DIGEST"] == "${{ steps.build.outputs.digest }}"


def test_published_packages_attest_the_downloaded_bytes_and_record_public_urls():
    steps = workflow("push-packagecloud.yml")["jobs"]["push"]["steps"]
    upload = next(step for step in steps if step.get("uses", "").startswith("danielmundi/upload-packagecloud@"))
    attest = next(step for step in steps if step.get("uses", "").startswith(ATTEST))
    assert steps.index(attest) > steps.index(upload)
    assert attest["with"]["subject-path"] == upload["with"]["PACKAGE-NAME"]
    record = next(step["run"] for step in steps if step.get("name") == "Record published package")
    assert "sha256sum" in record and "https://packagecloud.io/" in record
    assert "download.%s" in record and '"$PACKAGE"' in record
    assert not any("Rename package" in step.get("name", "") for step in steps)


def test_release_assets_are_downloaded_then_attested_and_verified_after_publish():
    jobs = workflow("release.yml")["jobs"]
    assets = jobs["attest-assets"]
    assert "push-gh" in assets["needs"]
    download = next(step for step in assets["steps"] if "gh release download" in step.get("run", ""))
    attest = next(step for step in assets["steps"] if step.get("uses", "").startswith(ATTEST))
    assert assets["steps"].index(download) < assets["steps"].index(attest)
    assert attest["with"]["subject-path"] == "release-assets/*"
    verify = jobs["verify-release"]
    assert {"prepare", "push-images", "push-packages", "push-gh", "attest-assets"} <= set(verify["needs"])
    assert verify["permissions"] == {"contents": "read", "attestations": "read", "packages": "read"}
    script = "\n".join(step.get("run", "") for step in verify["steps"])
    for token in (
        "gh attestation verify",
        "--signer-workflow",
        "--source-ref",
        "--source-digest",
        "--deny-self-hosted-runners",
        "sha256sum --check",
        "gh release download",
    ):
        assert token in script
    image_count = len(jobs["push-images"]["strategy"]["matrix"]["image"]) * 2
    package_matrix = jobs["push-packages"]["strategy"]["matrix"]
    package_count = len(package_matrix["linux"]) * len(package_matrix["arch"])
    assert f'EXPECTED_IMAGES: "{image_count}"' in (WORKFLOWS / "release.yml").read_text()
    assert f'EXPECTED_PACKAGES: "{package_count}"' in (WORKFLOWS / "release.yml").read_text()
    assert "verify-release" in jobs["push-doc"]["needs"]


@pytest.mark.parametrize("name", ["1.7-dev.yml", "dev.yml", "staging.yml"])
def test_rolling_branches_never_publish_packages(name):
    jobs = workflow(name)["jobs"]
    assert not any(job.get("uses", "").endswith("/push-packagecloud.yml") for job in jobs.values())
    assert any("docker push" in step.get("run", "") for job in jobs.values() for step in job.get("steps", []))


def test_only_versioned_release_calls_package_publisher():
    callers = []
    for path in WORKFLOWS.glob("*.yml"):
        for job in workflow(path.name).get("jobs", {}).values():
            if job.get("uses", "").endswith("/push-packagecloud.yml"):
                callers.append(path.name)
                assert "needs.prepare.outputs.version" in job["with"]["BW_VERSION"]
    assert callers == ["release.yml"]


def test_testing_release_installer_keeps_a_versioned_default():
    text = (WORKFLOWS / "push-github.yml").read_text()
    assert 'DEFAULT_BUNKERWEB_VERSION="testing"' not in text
    assert "force-bad-version" not in text


@pytest.mark.parametrize("version", ["dev", "testing", "1.7", "1.7-dev", "1.7-testing", "1.7_testing", "1.7.0", "1.7.0~alpha", "1.7.0~rc1", "1.7.0_rc1"])
def test_package_publisher_requires_version_numbers(version):
    steps = workflow("push-packagecloud.yml")["jobs"]["push"]["steps"]
    guard = next(step["run"] for step in steps if step.get("name") == "Require a versioned package")
    result = subprocess.run(["bash", "-c", guard], capture_output=True, text=True, env=os.environ | {"BW_VERSION": version})
    assert (result.returncode == 0) == version.startswith("1.7.0"), result.stdout + result.stderr


@pytest.mark.parametrize(
    "gap",
    [
        "none",
        "image_inventory",
        "package_inventory",
        "asset_inventory",
        "image_attestation",
        "package_attestation",
        "asset_attestation",
        "package_bytes",
        "asset_bytes",
    ],
)
def test_verifier_fails_closed_on_missing_or_changed_published_subjects(tmp_path, gap):
    steps = workflow("release.yml")["jobs"]["verify-release"]["steps"]
    script = next(step["run"] for step in steps if step.get("name") == "Verify every published artifact")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(f"#!{sys.executable}\n" + r"""
import os
import sys
from pathlib import Path
args = sys.argv[1:]
if args[:2] == ["release", "download"]:
    dest = Path(args[args.index("--dir") + 1])
    dest.mkdir()
    for name in ("doc.pdf", "install.sh", "install.sh.sha256"):
        (dest / name).write_bytes(b"asset" + (b"changed" if os.environ["GAP"] == "asset_bytes" else b""))
elif args[:2] == ["attestation", "verify"]:
    target = args[2]
    kind = "image" if target.startswith("oci://") else "package" if target.endswith("/package") else "asset"
    signer = {"image": "push-docker.yml", "package": "push-packagecloud.yml", "asset": "release.yml"}[kind]
    assert args[args.index("--signer-workflow") + 1] == "bunkerity/bunkerweb/.github/workflows/" + signer
    assert args[args.index("--source-ref") + 1] == "refs/tags/v1.7.0"
    assert args[args.index("--source-digest") + 1] == "a" * 40
    assert "--deny-self-hosted-runners" in args
    sys.exit(1 if os.environ["GAP"] == kind + "_attestation" else 0)
else:
    sys.exit(99)
""")
    curl = bin_dir / "curl"
    curl.write_text(f"#!{sys.executable}\n" + r"""
import os
import sys
from pathlib import Path
Path(sys.argv[sys.argv.index("--output") + 1]).write_bytes(b"package" + (b"changed" if os.environ["GAP"] == "package_bytes" else b""))
""")
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    for executable in (gh, curl, sleep):
        executable.chmod(0o755)
    inventory = tmp_path / "inventory"
    for kind in ("image", "package", "assets"):
        directory = inventory / ("release-inventory-assets" if kind == "assets" else f"release-inventory-{kind}-one")
        directory.mkdir(parents=True)
        if gap == ("asset_inventory" if kind == "assets" else kind + "_inventory"):
            continue
        if kind == "image":
            (directory / "images.txt").write_text("docker.io/bunkerity/bunkerweb@sha256:" + "b" * 64 + "\n")
        elif kind == "package":
            (directory / "package.sha256").write_text(hashlib.sha256(b"package").hexdigest() + "  package\n")
            (directory / "package.url").write_text("https://packagecloud.io/example/download.deb\n")
        else:
            (directory / "assets.sha256").write_text(
                "".join(hashlib.sha256(b"asset").hexdigest() + "  release-assets/" + name + "\n" for name in ("doc.pdf", "install.sh", "install.sh.sha256"))
            )
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=os.environ
        | {
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "GAP": gap,
            "EXPECTED_IMAGES": "1",
            "EXPECTED_PACKAGES": "1",
            "GITHUB_REPOSITORY": "bunkerity/bunkerweb",
            "GITHUB_REF": "refs/tags/v1.7.0",
            "GITHUB_REF_NAME": "v1.7.0",
            "GITHUB_SHA": "a" * 40,
        },
    )
    assert (result.returncode == 0) == (gap == "none"), result.stdout + result.stderr
