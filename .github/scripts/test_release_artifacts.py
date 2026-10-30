"""Local release provenance and fail-closed publication checks (no registry access)."""

from copy import deepcopy
from argparse import Namespace
from hashlib import sha256
from contextlib import chdir, redirect_stdout
from io import StringIO
from json import dumps, loads
from os import environ
from pathlib import Path
from re import fullmatch
from shutil import copyfile
from subprocess import CalledProcessError, run
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import call, patch

import release_artifacts as release
from release_smoke import compose_config, start_services
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
                release.require_success({"candidates": {"result": "success"}, "plumber": {"result": state}}, {"candidates", "plumber"})
        with self.assertRaises(ValueError):
            release.require_success({}, {"plumber"})
        release.require_success({"plumber": {"result": "success"}}, {"plumber"})

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

    @patch("release_smoke.run")
    def test_smoke_seeds_shared_volume_before_starting_services(self, mocked_run):
        compose = ["docker", "compose", "--project-name", "staging-smoke", "--file", "compose.json"]

        start_services(compose)

        self.assertEqual(
            mocked_run.call_args_list,
            [
                call([*compose, "create", "--no-build", "scheduler"], check=True),
                call([*compose, "up", "--detach", "--wait", "--wait-timeout", "600", "--no-build"], check=True),
            ],
        )

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
        # Integration suites belong to the staging and dev branches only.
        self.assertEqual([name for name in jobs if name.startswith(("run-", "parse-tests-"))], [])
        staging = safe_load((root / "staging.yml").read_text())["jobs"]
        suites = {
            "run-Docker-tests-core",
            "run-Autoconf-tests-core",
            "run-Linux-tests-core",
            "run-Kubernetes-tests-core",
            "run-All-in-one-tests-core",
            "run-Docker-tests-api",
        }
        for name in ("push-images", "push-packages"):
            self.assertIn("smoke-images", staging[name]["needs"])
            self.assertTrue(suites <= set(staging[name]["needs"]), name)
        matrix = jobs["build-packages"]["strategy"]["matrix"]
        self.assertEqual(set(matrix["linux"]), set(release.DISTROS))
        self.assertEqual(set(matrix["platforms"]), set(release.PACKAGE_PLATFORMS))
        self.assertNotIn("build-push-action", (root / "push-docker.yml").read_text())
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
            (directory / "misc").mkdir()
            copyfile(Path.cwd() / "misc/check-version-consistency.sh", directory / "misc/check-version-consistency.sh")
            pins = {
                "src/bw/Dockerfile": 'LABEL version="1.6.15~rc2"\n',
                "misc/install-bunkerweb.sh": 'DEFAULT_BUNKERWEB_VERSION="1.6.15~rc2"\n',
                "publiccode.yml": "softwareVersion: 1.6.15~rc2\n",
                "pyproject.toml": 'version = "1.6.15~rc2"\n',
                ".github/ISSUE_TEMPLATE/bug_report.yml": "      value: 1.6.15~rc2\n",
            }
            for name, content in pins.items():
                target = directory / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
            run(["git", "init", "--quiet"], cwd=directory, check=True, capture_output=True)
            run(["git", "add", "."], cwd=directory, check=True, capture_output=True)
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

    def test_attestation_subjects_cover_every_image_and_package(self):
        manifest = self.manifest()
        subjects = release.image_subjects(manifest)
        self.assertEqual(len(subjects), len(release.IMAGES) * len(release.REGISTRIES))
        self.assertIn(("docker.io/bunkerity/bunkerweb-scheduler", "sha256:" + "b" * 64), subjects)
        self.assertIn(("registry.gitlab.com/bunkerity/bunkerweb/bunkerweb-all-in-one", "sha256:" + "b" * 64), subjects)
        lines = release.package_checksums(manifest)
        self.assertEqual(len(lines), len(release.DISTROS) * len(release.PACKAGE_PLATFORMS))
        self.assertIn(f"{sha256(b'package').hexdigest()}  package-ubuntu-amd64/bunkerweb_1.6.15~rc2-1_amd64.deb", lines)
        # Every manifest entry needs a subject: a missing image, a bad digest, a short or blank package list all stop the release.
        mutations = [
            lambda m: m["images"].pop("api"),
            lambda m: m["images"]["ui"].update(ref="ghcr.io/bunkerity/ui-tests:testing"),
            lambda m: m["images"]["ui"].update(ref="ghcr.io/bunkerity/ui-tests@sha256:short"),
            lambda m: m["packages"].pop(),
            lambda m: m["packages"][0].update(sha256=""),
        ]
        for mutate in mutations:
            changed = deepcopy(manifest)
            mutate(changed)
            with self.assertRaises(ValueError):
                release.image_subjects(changed)
                release.package_checksums(changed)
        with self.assertRaises(ValueError):
            release.image_digest(manifest, "unknown")

    def test_image_subject_prints_github_output_lines(self):
        manifest = self.manifest()
        stdout = StringIO()
        with patch.object(release, "load_manifest", return_value=manifest), patch(
            "sys.argv", ["release_artifacts.py", "image-subject", "--image", "scheduler"]
        ), redirect_stdout(stdout):
            release.main()
        self.assertEqual(
            stdout.getvalue().splitlines(),
            [
                "digest=sha256:" + "b" * 64,
                "docker_io=docker.io/bunkerity/bunkerweb-scheduler",
                "ghcr_io=ghcr.io/bunkerity/bunkerweb-scheduler",
                "gitlab=registry.gitlab.com/bunkerity/bunkerweb/bunkerweb-scheduler",
            ],
        )
        with TemporaryDirectory() as tmp, patch.object(release, "load_manifest", return_value=manifest):
            for output in ("release-manifest.json", str(Path(tmp) / "packages.checksums")):
                with patch("sys.argv", ["release_artifacts.py", "package-checksums", "--output", output]):
                    if output == "release-manifest.json":
                        # The default output is the manifest itself: never overwrite it with checksums.
                        with self.assertRaises(ValueError):
                            release.main()
                    else:
                        release.main()
                        self.assertEqual(len(Path(output).read_text().splitlines()), 20)

    def test_attestation_verification_fails_closed_on_missing_or_foreign_attestation(self):
        manifest = self.manifest()
        verify = lambda: release.verify_attestations(manifest, "packages")  # noqa: E731
        calls = []

        def gh(missing):
            def run_gh(args):
                calls.append(args)
                if args[3] in missing:
                    raise CalledProcessError(1, args, b"", b"no attestations found")
                return b""

            return run_gh

        with patch.object(release, "sleep") as pause:
            with patch.object(release, "command", gh(set())):
                targets = verify()
            self.assertEqual(len(targets), 18 + 20)
            self.assertEqual(len(calls), 38)
            for args in calls:
                self.assertEqual(args[:3], ["gh", "attestation", "verify"])
                self.assertEqual(args[args.index("--repo") + 1], "bunkerity/bunkerweb")
                self.assertEqual(args[args.index("--signer-workflow") + 1], "bunkerity/bunkerweb/.github/workflows/release.yml")
                self.assertEqual(args[args.index("--source-ref") + 1], "refs/tags/v1.6.15-rc2")
                self.assertEqual(args[args.index("--source-digest") + 1], "a" * 40)
                self.assertIn("--deny-self-hosted-runners", args)
            self.assertEqual(sum(args[3].startswith("oci://") for args in calls), 18)
            self.assertIn("packages/package-rhel-9-x86_64/bunkerweb-1.6.15~rc2-1.x86_64.rpm", [args[3] for args in calls])
            pause.assert_not_called()
            # One image on one registry, then one package file, never attested (or attested by another identity): each stops the release.
            for missing in (f"oci://docker.io/bunkerity/bunkerweb-ui@sha256:{'b' * 64}", "packages/package-ubuntu-amd64/bunkerweb_1.6.15~rc2-1_amd64.deb"):
                calls.clear()
                with patch.object(release, "command", gh({missing})), self.assertRaisesRegex(ValueError, "missing or foreign attestation"):
                    verify()
                self.assertEqual(len(calls), 38 + (release.REGISTRY_ATTEMPTS - 1))
            # An attestation that shows up late is accepted, only the missing target is asked again.
            attempts = []

            def late(args):
                attempts.append(args[3])
                if args[3].startswith("oci://ghcr.io") and attempts.count(args[3]) < 2:
                    raise CalledProcessError(1, args, b"", b"not yet")
                return b""

            pause.reset_mock()
            with patch.object(release, "command", late):
                verify()
            self.assertEqual(len(attempts), 38 + 6)
            pause.assert_called_once_with(release.REGISTRY_DELAY)
        incomplete = deepcopy(manifest)
        incomplete["packages"].pop()
        with patch.object(release, "command", gh(set())), self.assertRaises(ValueError):
            release.verify_attestations(incomplete, "packages")

    def test_provenance_bundle_gathers_every_attested_subject(self):
        manifest = self.manifest()
        for index, image in enumerate(manifest["images"].values()):
            image["ref"] = f"ghcr.io/bunkerity/x-tests@sha256:{index:064x}"
        for package in manifest["packages"]:
            package["sha256"] = sha256(package["artifact"].encode()).hexdigest()
        expected = [f"{index:064x}" for index in range(len(release.IMAGES))] + [package["sha256"] for package in manifest["packages"]]
        calls = []

        def download(missing=None, content=None):
            def run_gh(args, cwd=None):
                calls.append(args)
                # gh writes the bundles of the subject digest to <alg>:<hex>.jsonl in its working directory, and nothing (exit 0) when there are none.
                hexdigest = args[3].rpartition("sha256:")[2] if args[3].startswith("oci://") else sha256(Path(args[3]).read_bytes()).hexdigest()
                if hexdigest != missing:
                    (Path(cwd) / f"sha256:{hexdigest}.jsonl").write_text(content if content is not None else dumps({"subject": hexdigest}) + "\n")
                return b""

            return run_gh

        with TemporaryDirectory() as tmp:
            packages = Path(tmp) / "packages"
            for package in manifest["packages"]:
                file = packages / package["artifact"] / package["filename"]
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(package["artifact"].encode())
            output = Path(tmp) / "out.intoto.jsonl"  # codespell:ignore intoto
            with patch.object(release, "command", download()):
                self.assertEqual(release.provenance_bundle(manifest, packages, output), len(expected))
            # One bundle per line, one per attested subject: the 6 image index digests and the 20 package files.
            self.assertEqual(sorted(loads(line)["subject"] for line in output.read_text().splitlines()), sorted(expected))
            self.assertEqual(len(calls), 26)
            for args in calls:
                self.assertEqual(args[:3], ["gh", "attestation", "download"])
                self.assertEqual(args[args.index("--repo") + 1], "bunkerity/bunkerweb")
                self.assertEqual(args[args.index("--predicate-type") + 1], "https://slsa.dev/provenance/v1")
            self.assertEqual(sum(args[3].startswith("oci://ghcr.io/bunkerity/bunkerweb") for args in calls), 6)
            # A subject with no bundle (no file, an empty file, a non-JSON line, a non-object line) or a failed download stops the release.
            for missing, content in ((expected[0], None), (None, ""), (None, "not json\n"), (None, "[1]\n")):
                output.unlink(missing_ok=True)
                with patch.object(release, "command", download(missing, content)), self.assertRaises(ValueError):
                    release.provenance_bundle(manifest, packages, output)
                self.assertFalse(output.exists())
            with patch.object(release, "command", side_effect=CalledProcessError(1, "gh")), self.assertRaises(CalledProcessError):
                release.provenance_bundle(manifest, packages, output)
            (packages / manifest["packages"][3]["artifact"] / manifest["packages"][3]["filename"]).unlink()
            with patch.object(release, "command", download()), self.assertRaisesRegex(ValueError, "package file missing"):
                release.provenance_bundle(manifest, packages, output)
        self.assertEqual(release.provenance_name(manifest), "bunkerweb-1.6.15-rc2.intoto.jsonl")  # codespell:ignore intoto

    def test_provenance_bundle_cli_writes_the_release_asset_name(self):
        manifest = self.manifest()
        stdout = StringIO()
        with TemporaryDirectory() as tmp, patch.object(release, "load_manifest", return_value=manifest), patch.object(
            release, "provenance_bundle", return_value=26
        ) as gather, patch("sys.argv", ["release_artifacts.py", "provenance-bundle", "--directory", "packages"]), redirect_stdout(stdout), chdir(tmp):
            release.main()
        # The name is derived from the manifest, never from --output (whose default is the release manifest itself).
        gather.assert_called_once_with(manifest, "packages", Path("bunkerweb-1.6.15-rc2.intoto.jsonl"))  # codespell:ignore intoto
        self.assertEqual(stdout.getvalue().splitlines(), ["file=bunkerweb-1.6.15-rc2.intoto.jsonl"])  # codespell:ignore intoto

    def test_workflow_attaches_provenance_after_verification_and_before_docs(self):
        jobs = safe_load((Path(__file__).resolve().parents[1] / "workflows/release.yml").read_text())["jobs"]

        def ancestors(job):
            needs = jobs[job].get("needs", [])
            return set(needs).union(*(ancestors(need) for need in needs))

        job = jobs["attach-provenance"]
        # The asset is gathered once the attestations verified, and the docs wait for it: the release is complete before a human publishes it.
        self.assertTrue({"prepare", "push-gh", "verify-release"} <= set(job["needs"]))
        self.assertIn("gate", ancestors("attach-provenance"))
        self.assertIn("attach-provenance", jobs["push-doc"]["needs"])
        # Only this job gains contents: write (to upload to the draft); it reads attestations and signs nothing.
        self.assertEqual(job["permissions"], {"contents": "write", "attestations": "read"})
        self.assertEqual(
            {name for name, other in jobs.items() if other.get("permissions", {}).get("contents") == "write"},
            {"prepare", "push-gh", "push-doc", "attach-provenance"},
        )
        self.assertEqual(jobs["verify-release"]["permissions"], {"contents": "read", "attestations": "read"})
        steps = {step.get("name", ""): step for step in job["steps"]}
        gather = next(step for name, step in steps.items() if "provenance" in name.lower() and "gather" in name.lower())
        self.assertIn("provenance-bundle", gather["run"])
        upload = next(step for step in job["steps"] if "gh release upload" in step.get("run", ""))
        # One file, this tag, overwritten on a rerun: no glob, no other asset is touched.
        command = upload["run"]
        self.assertIn('gh release upload "$TAG" "$FILE" --clobber', command)
        self.assertNotIn("*", command)
        self.assertNotIn("gh release delete", command)
        for step in job["steps"]:
            self.assertNotIn("continue-on-error", step)
            if "uses" in step:
                self.assertTrue(fullmatch(r"[\w./-]+@[0-9a-f]{40}", step["uses"]), step["uses"])
                self.assertFalse(step["uses"].startswith(("actions/attest", "docker/login-action")))

    def test_workflow_attests_before_publication_and_verifies_before_docs(self):
        root = Path(__file__).resolve().parents[1] / "workflows"
        jobs = safe_load((root / "release.yml").read_text())["jobs"]

        def ancestors(job):
            needs = jobs[job].get("needs", [])
            return set(needs).union(*(ancestors(need) for need in needs))

        # Images and packages are attested before any registry or packagecloud receives them; docs wait for the verification of everything published.
        self.assertIn("attest-packages", jobs["push-packages"]["needs"])
        self.assertIn("attest-images", jobs["push-images"]["needs"])
        self.assertNotIn("push-images", ancestors("attest-images"))
        self.assertTrue({"push-images", "push-packages", "attest-images", "attest-packages"} <= set(jobs["verify-release"]["needs"]))
        self.assertIn("verify-release", jobs["push-doc"]["needs"])
        # Only an approved candidate gets attested: both attest jobs descend from the human gate, like the publication they guard.
        for name in ("attest-images", "attest-packages", "verify-release"):
            self.assertIn("gate", ancestors(name))
        self.assertTrue(set(jobs["attest-images"]["needs"]) >= {"prepare", "candidates", "push-gh"})
        # Least privilege: only the attesting jobs may sign, and the verifier only reads.
        signers = {name for name, job in jobs.items() if job.get("permissions", {}).get("attestations") == "write"}
        self.assertEqual(signers, {"attest-images", "attest-packages"})
        for name in signers:
            self.assertEqual(jobs[name]["permissions"], {"contents": "read", "id-token": "write", "attestations": "write"}, name)
            for step in jobs[name]["steps"]:
                if "uses" in step:
                    self.assertTrue(fullmatch(r"[\w./-]+@[0-9a-f]{40}", step["uses"]), step["uses"])
                    # Attestations live only in GitHub's store: no bundle goes to a registry, and no registry login exists here.
                    self.assertFalse(step["uses"].startswith("docker/login-action"), name)
                    if step["uses"].startswith("actions/attest"):
                        self.assertNotIn("push-to-registry", step.get("with", {}), name)
        self.assertEqual(jobs["verify-release"]["permissions"], {"contents": "read", "attestations": "read"})
        self.assertEqual(set(jobs["attest-images"]["strategy"]["matrix"]["image"]), set(release.IMAGES))
        verify = next(step for step in jobs["verify-release"]["steps"] if step.get("name", "").startswith("Verify the attestations"))
        self.assertIn("verify-attestations", verify["run"])
        self.assertNotIn("continue-on-error", verify)
        # The names and registries the attestations pin are the ones the promotion publishes.
        include = {entry["source"]: entry["image"] for entry in jobs["push-images"]["strategy"]["matrix"]["include"] if "source" in entry}
        self.assertEqual(include, release.PUBLISHED)
        promotion = (root / "push-docker.yml").read_text()
        for prefix in release.REGISTRIES.values():
            self.assertIn(prefix, promotion)

    def test_release_lookup_jobs_keep_push_access(self):
        # GitHub's release listing omits drafts for tokens without push access instead of
        # erroring, so the no-republish guard silently degrades without contents: write.
        jobs = safe_load((Path(__file__).resolve().parents[1] / "workflows/release.yml").read_text())["jobs"]
        for job in ("prepare", "push-gh"):
            self.assertEqual(jobs[job]["permissions"]["contents"], "write", job)


if __name__ == "__main__":
    main()
