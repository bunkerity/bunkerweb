"""Draft claims must never turn a new build into an overwrite of a partial release."""

from copy import deepcopy
from hashlib import sha256
from json import dumps
from os import environ
from pathlib import Path
from subprocess import CalledProcessError
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

import release_claim as claim


class ReleaseClaimTest(TestCase):
    def test_create_only_claim_and_failed_job_retry_preserve_assets(self):
        manifest = {"source_sha": "a" * 40, "version": "1.6.15~rc2", "run_id": "123", "run_attempt": "1"}
        releases, uploads = [], []
        conclusion = "failure"
        with TemporaryDirectory() as temporary:
            file = Path(temporary) / "release-manifest.json"
            file.write_text("original candidate\n")
            second = Path(temporary) / "installer.sh"
            second.write_text("original installer\n")
            files = [file, second]
            fail_upload = True

            def api(endpoint, payload=None, paginated=False):
                if endpoint.endswith("/releases?per_page=100"):
                    return [deepcopy(releases)]
                if endpoint.endswith("/git/ref/tags/v1.6.15-rc2"):
                    return {"object": {"type": "tag", "sha": "b" * 40}}
                if "/git/tags/" in endpoint:
                    return {"verification": {"verified": True}, "object": {"type": "commit", "sha": manifest["source_sha"]}}
                if endpoint.endswith("/releases"):
                    self.assertIsNotNone(payload)
                    self.assertFalse(releases, "must not create a second draft")
                    releases.append(payload | {"id": 7})
                    return deepcopy(releases[0])
                if endpoint.endswith("/releases/7/assets?per_page=100"):
                    return [deepcopy(uploads)]
                if endpoint.endswith("/attempts/1/jobs?per_page=100"):
                    return [{"jobs": [{"name": "push-gh / Publish GitHub release", "conclusion": conclusion}]}]
                self.fail(f"unexpected API request {endpoint}")

            def command(args):
                nonlocal fail_upload
                self.assertIn("POST", args)
                self.assertNotIn("--clobber", args)
                uploading = Path(args[args.index("--input") + 1])
                self.assertIn(f"https://uploads.github.com/repos/bunkerity/bunkerweb/releases/7/assets?name={uploading.name}", args)
                if uploading == second and fail_upload:
                    fail_upload = False
                    raise CalledProcessError(1, "gh upload", stderr=b"network failure")
                uploaded = {"id": len(uploads) + 8, "name": uploading.name, "digest": "sha256:" + sha256(uploading.read_bytes()).hexdigest()}
                uploads.append(uploaded)
                return dumps(uploaded).encode()

            with patch.dict(environ, {"GITHUB_REPOSITORY": "bunkerity/bunkerweb", "GITHUB_RUN_ATTEMPT": "1"}), patch.object(
                claim, "api", side_effect=api
            ), patch.object(claim, "command", side_effect=command) as copy:
                with self.assertRaises(CalledProcessError):
                    claim.publish(manifest, "c" * 64, "Release notes", files, True)
                self.assertTrue(releases[0]["draft"])
                self.assertIn(manifest["source_sha"], releases[0]["body"])
                self.assertNotIn("target_commitish", releases[0], "the existing signed tag already binds the commit")
                self.assertEqual(copy.call_count, 2)
                self.assertEqual([asset["name"] for asset in uploads], [file.name])
                # The same successful attempt cannot be replayed as an upload/update.
                with self.assertRaises(ValueError):
                    claim.publish(manifest, "c" * 64, "Release notes", files, True)
                with patch.dict(environ, {"GITHUB_RUN_ATTEMPT": "2"}):
                    claim.publish(manifest, "c" * 64, "Release notes", files, True)
                    self.assertEqual(copy.call_count, 3, "only the previously missing upload is retried")
                    self.assertEqual([asset["name"] for asset in uploads], [file.name, second.name])
                    conclusion = "success"
                    with self.assertRaises(ValueError):
                        claim.publish(manifest, "c" * 64, "Release notes", files, True)
                    conclusion = "failure"
                    for changed in (manifest | {"run_id": "124"}, manifest | {"run_attempt": "2"}):
                        with self.assertRaises(ValueError):
                            claim.publish(changed, "c" * 64, "Release notes", files, True)
                    with self.assertRaises(ValueError):
                        claim.publish(manifest, "d" * 64, "Release notes", files, True)
                    file.write_text("rebuilt candidate\n")
                    with self.assertRaises(ValueError):
                        claim.publish(manifest, "c" * 64, "Release notes", files, True)

    def test_unrelated_or_published_draft_never_mutated(self):
        manifest = {"source_sha": "a" * 40, "version": "1.6.15", "run_id": "123", "run_attempt": "1"}
        for draft in (True, False):
            existing = {"id": 7, "tag_name": "v1.6.15", "draft": draft, "body": "User's existing release"}
            with patch.dict(environ, {"GITHUB_REPOSITORY": "bunkerity/bunkerweb", "GITHUB_RUN_ATTEMPT": "2"}), patch.object(
                claim, "api", return_value=[[existing]]
            ) as api:
                with self.assertRaises(ValueError):
                    claim.publish(manifest, "c" * 64, "Release notes", [], False)
                self.assertTrue(all(call.kwargs.get("payload") is None for call in api.call_args_list))

    def test_create_conflict_or_lookup_failure_has_no_update_fallback(self):
        manifest = {"source_sha": "a" * 40, "version": "1.6.15", "run_id": "123", "run_attempt": "1"}
        with patch.dict(environ, {"GITHUB_REPOSITORY": "bunkerity/bunkerweb", "GITHUB_RUN_ATTEMPT": "1"}), patch.object(
            claim, "api", side_effect=CalledProcessError(1, "gh")
        ) as api:
            with self.assertRaises(CalledProcessError):
                claim.publish(manifest, "c" * 64, "Release notes", [], False)
            self.assertEqual(api.call_count, 1)
        responses = [
            [[]],
            {"object": {"type": "tag", "sha": "b" * 40}},
            {"verification": {"verified": True}, "object": {"type": "commit", "sha": manifest["source_sha"]}},
            CalledProcessError(1, "gh", stderr=b"HTTP 422: already exists"),
        ]
        with patch.dict(environ, {"GITHUB_REPOSITORY": "bunkerity/bunkerweb", "GITHUB_RUN_ATTEMPT": "1"}), patch.object(
            claim, "api", side_effect=responses
        ) as api:
            with self.assertRaises(CalledProcessError):
                claim.publish(manifest, "c" * 64, "Release notes", [], False)
            self.assertEqual(api.call_count, 4)
            self.assertTrue(api.call_args.kwargs["payload"]["draft"])

    def test_existing_asset_digest_or_download_must_match_original_bytes(self):
        checksum = sha256(b"original").hexdigest()
        with patch.object(claim, "command") as command:
            claim.verify_asset("bunkerity/bunkerweb", {"name": "a", "digest": "sha256:" + checksum}, checksum)
            command.assert_not_called()
            with self.assertRaises(ValueError):
                claim.verify_asset("bunkerity/bunkerweb", {"name": "a", "digest": "sha256:" + "0" * 64}, checksum)
            command.return_value = b"original"
            claim.verify_asset("bunkerity/bunkerweb", {"name": "a", "id": 7}, checksum)
            self.assertIn("repos/bunkerity/bunkerweb/releases/assets/7", command.call_args.args[0])


if __name__ == "__main__":
    main()
