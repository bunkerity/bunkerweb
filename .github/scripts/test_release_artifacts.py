"""Local release provenance and fail-closed publication checks (no registry access)."""

from copy import deepcopy
from argparse import Namespace
from hashlib import sha256
from json import dumps, loads
from os import environ
from pathlib import Path
from subprocess import CalledProcessError, run
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

import release_artifacts as release
import release_integration as integration
from release_smoke import compose_config
from yaml import safe_load


class ReleaseArtifactsTest(TestCase):
    def manifest(self):
        identity = {"source_sha": "a" * 40, "version": "1.6.15~rc2", "run_id": "123", "run_attempt": "1"}
        manifest = identity | {"schema": 1, "images": {}, "packages": []}
        for image in release.IMAGES:
            manifest["images"][image] = {
                "ref": f"ghcr.io/bunkerity/{image}-tests@sha256:{'b' * 64}",
                "platforms": dict.fromkeys(release.PLATFORMS, "sha256:" + "c" * 64),
            }
        for distro, kind in release.DISTROS.items():
            for platform in release.PACKAGE_PLATFORMS:
                arch = release.package_arch(platform, kind)
                manifest["packages"].append(
                    dict(
                        distro=distro,
                        platform=platform,
                        artifact=f"package-{distro}-{arch}",
                        filename=release.package_name(identity["version"], kind, arch),
                        sha256=sha256(b"package").hexdigest(),
                    )
                )
        return manifest

    def test_inventory_requires_every_platform_and_package_variant(self):
        manifest = self.manifest()
        release.validate(manifest, manifest)
        self.assertEqual(len(manifest["packages"]), 20)
        self.assertEqual(sum(len(image["platforms"]) for image in manifest["images"].values()), 24)
        mutations = [
            lambda m: m["images"].pop("api"),
            lambda m: m["images"]["ui"]["platforms"].pop("linux/386"),
            lambda m: m["packages"].pop(),
            lambda m: m["packages"].append(m["packages"][0]),
            lambda m: m["images"]["api"].update(ref="ghcr.io/bunkerity/api-tests:testing"),
            lambda m: m["packages"][0].update(filename="../../elsewhere.deb"),
            lambda m: m["packages"][0].update(sha256=""),
            lambda m: m.update(source_sha="d" * 40),
            lambda m: m.update(version="1.6.15"),
            lambda m: m.update(run_attempt="2"),
        ]
        for mutate in mutations:
            changed = deepcopy(manifest)
            mutate(changed)
            with self.assertRaises(ValueError):
                release.validate(changed, manifest)

    def test_checksums_detect_changed_package_bytes(self):
        package = self.manifest()["packages"][0]
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / package["filename"]
            path.write_bytes(b"package")
            release.verify_package(package, path.parent)
            extra = path.parent / "unverified.deb"
            extra.write_bytes(b"other package")
            with self.assertRaises(ValueError):
                release.verify_package(package, path.parent)
            extra.unlink()
            path.write_bytes(b"rebuilt package")
            with self.assertRaises(ValueError):
                release.verify_package(package, path.parent)

    def test_index_preserves_platform_mapping_and_rejects_duplicates(self):
        descriptor = {"digest": "sha256:" + "c" * 64, "platform": {"os": "linux", "architecture": "arm", "variant": "v7"}}
        attestation = {
            "digest": "sha256:" + "d" * 64,
            "platform": {"os": "unknown", "architecture": "unknown"},
            "annotations": {"vnd.docker.reference.type": "attestation-manifest"},
        }
        self.assertEqual(release.platform_digests({"manifests": [descriptor, attestation]}), {"linux/arm/v7": descriptor["digest"]})
        with self.assertRaises(ValueError):
            release.platform_digests({"manifests": [descriptor, descriptor]})

    def test_publication_gate_rejects_failure_skipped_cancelled_and_missing(self):
        for state in ("failure", "skipped", "cancelled", ""):
            with self.assertRaises(ValueError):
                release.require_success({"candidates": {"result": "success"}, "staging-tests": {"result": state}}, {"candidates", "staging-tests"})
        with self.assertRaises(ValueError):
            release.require_success({}, {"staging-tests"})
        release.require_success({"staging-tests": {"result": "success"}}, {"staging-tests"})

    def test_copy_has_no_build_and_preserves_full_index(self):
        manifest = self.manifest()
        with patch.object(release, "command") as command:
            command.return_value = ("sha256:" + "b" * 64 + "\n").encode()
            release.promote(manifest, "api", "bunkerity/bunkerweb-api:1.6.15~rc2")
        self.assertEqual(command.call_args_list[0].args[0][:4], ["skopeo", "copy", "--all", "--preserve-digests"])
        self.assertIn("docker://ghcr.io/bunkerity/api-tests@sha256:" + "b" * 64, command.call_args_list[0].args[0])
        self.assertIn("docker://bunkerity/bunkerweb-api:1.6.15-rc2", command.call_args_list[0].args[0])
        command.return_value = b"sha256:changed\n"
        with patch.object(release, "command", return_value=b"sha256:changed\n"), self.assertRaises(ValueError):
            release.promote(manifest, "api", "bunkerity/bunkerweb-api:latest")

    def test_manifest_hash_is_checked_before_parsing_or_consuming(self):
        with TemporaryDirectory() as tmp:
            file = Path(tmp) / "release-manifest.json"
            manifest = self.manifest()
            release.write_json(file, manifest)
            checksum = sha256(file.read_bytes()).hexdigest()
            with patch.object(release, "identity", return_value=manifest):
                self.assertEqual(release.load_manifest(file, checksum), manifest)
                with patch.object(release, "identity", return_value=manifest | {"run_attempt": "2"}):
                    self.assertEqual(release.load_manifest(file, checksum), manifest)
                with patch.object(release, "identity", return_value=manifest | {"run_id": "124"}), self.assertRaises(ValueError):
                    release.load_manifest(file, checksum)
                for invalid in ("", "0" * 64):
                    with self.assertRaises(ValueError):
                        release.load_manifest(file, invalid)
                file.write_text(file.read_text() + "\n")
                with self.assertRaises(ValueError):
                    release.load_manifest(file, checksum)

    def test_assemble_binds_all_build_receipts_and_rejects_mixed_attempts(self):
        manifest = self.manifest()
        source = {key: manifest[key] for key in ("source_sha", "version", "run_id", "run_attempt")}
        descriptors = []
        for platform in release.PLATFORMS:
            os_name, arch, *variant = platform.split("/")
            descriptors.append(
                {"digest": "sha256:" + "c" * 64, "platform": dict(os=os_name, architecture=arch, **({"variant": variant[0]} if variant else {}))}
            )
        with TemporaryDirectory() as tmp:
            directory = Path(tmp) / "receipts"
            directory.mkdir()
            for image in release.IMAGES:
                for index, platform in enumerate(release.PLATFORMS):
                    release.write_json(
                        directory / f"{image}-{index}.json",
                        source | {"kind": "image", "image": image, "ref": manifest["images"][image]["ref"], "platforms": {platform: "sha256:" + "c" * 64}},
                    )
            for index, package in enumerate(manifest["packages"]):
                release.write_json(directory / f"package-{index}.json", dict(source, kind="package", **package))
            args = Namespace(directory=directory, output=Path(tmp) / "release.json")
            with patch.object(release, "identity", return_value=source), patch.object(
                release, "command", return_value=b'"sha256:' + b"b" * 64 + b'"\n'
            ) as command:
                with patch.object(release, "inspect_index", return_value={"manifests": descriptors}):
                    release.assemble(args)
                    release.validate(loads(args.output.read_text()), source)
                    self.assertFalse(any("build" in call.args[0] for call in command.call_args_list))
                    release.write_json(directory / "package-0.json", dict(source, kind="package", **manifest["packages"][0], run_attempt="2"))
                    with self.assertRaises(ValueError):
                        release.assemble(args)

    def test_smoke_uses_only_pushed_staging_images_without_source_mounts_or_builds(self):
        config = compose_config()
        self.assertEqual(set(config["services"]), set(release.IMAGES))
        for name, service in config["services"].items():
            self.assertEqual(service["image"], f"ghcr.io/bunkerity/{name}-tests:testing")
            self.assertNotIn("build", service)
            self.assertNotIn("ports", service)
            self.assertFalse(any("/usr/share/bunkerweb" in volume for volume in service["volumes"]))
            # The API and the all-in-one API refuse to start without an auth path.
            self.assertTrue(service["environment"]["API_TOKEN"])

    def test_workflow_graph_has_no_publication_bypass(self):
        root = Path(__file__).resolve().parents[1] / "workflows"
        jobs = safe_load((root / "release.yml").read_text())["jobs"]

        def ancestors(job):
            needs = jobs[job].get("needs", [])
            return set(needs).union(*(ancestors(need) for need in needs))

        self.assertEqual(set(jobs["validate-candidates"]["needs"]), release.REQUIRED_JOBS)
        self.assertEqual(set(jobs["rm-arm"]["needs"]), {"create-arm", "build-containers-arm", "build-packages"})
        self.assertIn("always()", jobs["rm-arm"]["if"])
        self.assertEqual(jobs["gate"]["environment"], "release")
        for name in ("push-images", "push-packages", "push-gh", "push-doc"):
            self.assertIn("gate", ancestors(name))
            self.assertIn("validate-candidates", ancestors(name))
        for name in ("push-images", "push-packages"):
            self.assertEqual(jobs[name]["with"]["MANIFEST_SHA256"], "${{ needs.push-gh.outputs.manifest_sha256 }}")
        # Integration suites and their cloud infrastructure belong to the staging branch only.
        for name in ("create-infras", "staging-tests", "staging-tests-arm64", "delete-infras", "delete-infras-linux"):
            self.assertNotIn(name, jobs)
        staging = safe_load((root / "staging.yml").read_text())["jobs"]
        for name in ("push-images", "push-packages"):
            self.assertIn("smoke-images", staging[name]["needs"])
            self.assertIn("staging-tests", staging[name]["needs"])
        self.assertEqual(set(staging["staging-tests"]["strategy"]["matrix"]["type"]), {"docker", "autoconf", "k8s", "linux"})
        self.assertEqual(set(staging["delete-infras"]["strategy"]["matrix"]["type"]), {"docker", "autoconf", "k8s", "linux"})
        self.assertIn("always()", staging["delete-infras"]["if"])
        matrix = jobs["build-packages"]["strategy"]["matrix"]
        self.assertEqual(set(matrix["linux"]), set(release.DISTROS))
        self.assertEqual(set(matrix["platforms"]), set(release.PACKAGE_PLATFORMS))
        self.assertNotIn("build-push-action", (root / "push-docker.yml").read_text())
        steps = safe_load((root / "staging-tests.yml").read_text())["jobs"]["tests"]["steps"]
        for step in steps:
            if "docker pull" in step.get("run", ""):
                self.assertIn("inputs.MANIFEST_SHA256 == ''", step["if"])
        package_steps = safe_load((root / "push-packagecloud.yml").read_text())["jobs"]["push"]["steps"]
        yank = next(step for step in package_steps if step.get("name") == "Yank existing package")
        self.assertEqual(yank["if"], "inputs.MANIFEST_SHA256 == ''")

    def test_signed_tag_and_existing_release_guards_execute_fail_closed(self):
        workflow = Path(__file__).resolve().parents[1] / "workflows/release.yml"
        jobs = safe_load(workflow.read_text())["jobs"]
        derive = next(step["run"] for step in jobs["prepare"]["steps"] if step.get("id") == "derive")
        gate_checks = "\n".join(step["run"] for step in jobs["gate"]["steps"] if step.get("name", "").startswith("Recheck"))
        gh_stub = r"""
gh() {
  case "$*" in
    */git/ref/tags/*) printf '%s' "$TAG_REF_JSON" ;;
    */git/tags/*) printf '%s' "$TAG_OBJECT_JSON" ;;
    */environments/release) printf '%s' "$PROTECTION_JSON" ;;
    */releases\?per_page=100)
      if [ "$RELEASE_STATUS" != ok ]; then echo "HTTP $RELEASE_STATUS" >&2; return 1; fi
      printf '%s' "$RELEASES_JSON" ;;
    *) return 99 ;;
  esac
}
"""
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "src").mkdir()
            (directory / "src/VERSION").write_text("1.6.15~rc2\n")
            changelog = directory / "CHANGELOG.md"
            changelog.write_text("## v1.6.15~rc2\nRelease fixes.\n")
            source = "a" * 40
            signed = {"verification": {"verified": True, "reason": "valid"}, "object": {"type": "commit", "sha": source}}

            def reviewer(login):
                return {"type": "User", "reviewer": {"login": login}}

            OWNERS = [reviewer("TheophileDiot"), reviewer("fl0ppy-d1sk")]
            env = environ | {
                "TAG": "v1.6.15-rc2",
                "GITHUB_SHA": source,
                "GITHUB_REPOSITORY": "bunkerity/bunkerweb",
                "GITHUB_OUTPUT": str(directory / "output"),
                "GITHUB_STEP_SUMMARY": str(directory / "summary"),
                "TAG_REF_JSON": dumps({"object": {"type": "tag", "sha": "b" * 40}}),
                "TAG_OBJECT_JSON": dumps(signed),
                "RELEASE_STATUS": "ok",
                "RELEASES_JSON": "[[]]",
                "PROTECTION_JSON": dumps(
                    {"name": "release", "protection_rules": [{"type": "required_reviewers", "prevent_self_review": False, "reviewers": OWNERS}]}
                ),
            }

            def execute(overrides):
                return run(["bash", "-c", gh_stub + derive], cwd=directory, env=dict(env, **overrides), capture_output=True)

            self.assertEqual(execute({}).returncode, 0)
            for overrides, expected in (({}, 0), ({"TAG_OBJECT_JSON": dumps(signed | {"object": {"type": "commit", "sha": "c" * 40}})}, 1)):
                result = run(["bash", "-c", gh_stub + gate_checks], cwd=directory, env=dict(env, **overrides), capture_output=True)
                self.assertEqual(result.returncode, expected)
            variants = [
                {"TAG": "v1.6.15-rc3"},
                {"TAG_REF_JSON": dumps({"object": {"type": "commit", "sha": source}})},
                {"TAG_OBJECT_JSON": dumps(signed | {"verification": {"verified": False, "reason": "unsigned"}})},
                {"TAG_OBJECT_JSON": dumps(signed | {"object": {"type": "commit", "sha": "c" * 40}})},
                {"RELEASES_JSON": dumps([[{"tag_name": "v1.6.15-rc2", "draft": True}]])},
                {"RELEASES_JSON": dumps([[{"tag_name": "v1.6.15-rc2", "draft": False}]])},
                {"RELEASES_JSON": dumps([[{"tag_name": "v1.6.14"}], [{"tag_name": "v1.6.15-rc2", "draft": True}]])},
                {"RELEASES_JSON": "invalid response"},
                {"RELEASE_STATUS": "404"},
                {"RELEASE_STATUS": "403"},
                {"PROTECTION_JSON": dumps({"name": "release", "protection_rules": []})},
                {"PROTECTION_JSON": dumps({"name": "release", "protection_rules": [{"type": "required_reviewers", "reviewers": []}]})},
                # Self-review is fine, a reviewer who is not a release owner is not: a stranger next to an owner, a team, an opaque id.
                {
                    "PROTECTION_JSON": dumps(
                        {"name": "release", "protection_rules": [{"type": "required_reviewers", "reviewers": OWNERS + [reviewer("someone-else")]}]}
                    )
                },
                {
                    "PROTECTION_JSON": dumps(
                        {
                            "name": "release",
                            "protection_rules": [{"type": "required_reviewers", "reviewers": [{"type": "Team", "reviewer": {"slug": "maintainers"}}]}],
                        }
                    )
                },
                {
                    "PROTECTION_JSON": dumps(
                        {"name": "release", "protection_rules": [{"type": "required_reviewers", "prevent_self_review": True, "reviewers": [{"id": 1}]}]}
                    )
                },
            ]
            for overrides in variants:
                self.assertNotEqual(execute(overrides).returncode, 0, overrides)
            changelog.write_text("## v1.6.15~rc20\nWrong version.\n")
            self.assertNotEqual(execute({}).returncode, 0)

    def test_release_lookup_jobs_keep_push_access(self):
        # GitHub's release listing omits drafts for tokens without push access instead of
        # erroring, so the no-republish guard silently degrades without contents: write.
        jobs = safe_load((Path(__file__).resolve().parents[1] / "workflows/release.yml").read_text())["jobs"]
        for job in ("prepare", "push-gh"):
            self.assertEqual(jobs[job]["permissions"]["contents"], "write", job)

    def test_integration_cleanup_runs_even_when_init_child_exits(self):
        for kind in ("docker", "autoconf", "kubernetes", "linux"):
            with patch.object(integration, "run", side_effect=CalledProcessError(1, "tests/main.py")), patch.object(integration, "cleanup") as cleanup:
                with self.assertRaises(CalledProcessError):
                    integration.run_suite(kind, [], "ubuntu" if kind == "linux" else None)
                cleanup.assert_called_once_with(kind, [], "ubuntu" if kind == "linux" else None)

    def test_integration_platform_filter_selects_one_platform_and_refuses_an_empty_selection(self):
        packages = [
            {"distro": "ubuntu", "platform": "linux/amd64"},
            {"distro": "ubuntu", "platform": "linux/arm64"},
            {"distro": "rhel-9", "platform": "linux/arm64"},
        ]
        self.assertEqual(integration.select_packages(packages), packages)
        self.assertEqual(integration.select_packages(packages, "linux/arm64"), packages[1:])
        with self.assertRaises(ValueError):
            integration.select_packages(packages, "linux/386")

    def test_integration_cleanup_failure_does_not_hide_the_suite_failure(self):
        with patch.object(integration, "run", side_effect=CalledProcessError(1, "tests/main.py")), patch.object(
            integration, "cleanup", side_effect=ValueError("cleanup exploded")
        ):
            with self.assertRaises(CalledProcessError):
                integration.run_suite("docker", [])

    def test_integration_cleanup_is_scoped_to_selected_manifests_and_named_container(self):
        suites = [{"name": "candidate-example", "kinds": ["docker", "autoconf", "kubernetes"]}, {"name": "unrelated", "kinds": []}]
        with patch.object(Path, "is_file", return_value=True), patch.object(Path, "is_dir", return_value=False), patch.object(
            integration, "run", return_value=Namespace(returncode=0)
        ) as run:
            integration.cleanup("autoconf", suites)
            self.assertEqual(
                [call.args[0][3] for call in run.call_args_list], ["/tmp/tests/candidate-example/autoconf.yml", "/tmp/autoconf/docker-compose.yml"]
            )
            run.reset_mock()
            integration.cleanup("kubernetes", suites)
            self.assertTrue(all("--ignore-not-found" in call.args[0] and "--all" not in call.args[0] for call in run.call_args_list))
            self.assertEqual(len(run.call_args_list), 2)
            run.reset_mock()
            with patch.object(integration, "command", return_value=b"container-id\n") as command:
                integration.cleanup("linux", suites, "ubuntu")
                self.assertEqual(command.call_args.args[0][-1], "name=^/linux-ubuntu$")
                run.assert_called_once_with(["docker", "rm", "--force", "container-id"], timeout=90, check=False)


if __name__ == "__main__":
    main()
